"""MVK Collector core. Modbus FC03 ONLY. Never writes to instrument."""
from __future__ import annotations
import json, os, socket, sqlite3, struct, threading, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .decoder import decode_snapshot

class ProtocolError(Exception): pass

def modbus_read(ip: str, port: int, address: int, count: int, timeout=1.0) -> list[int]:
    """One transaction per fresh TCP connection, 03 read holding registers."""
    if not (0 <= address <= 65535 and 1 <= count <= 125 and address+count <= 65536):
        raise ValueError('Invalid register range')
    if not (1 <= port <= 65535): raise ValueError('Invalid TCP port')
    tid=0x4D56
    request=struct.pack('>HHHBBHH',tid,0,6,1,3,address,count)
    def recv_exact(sock, size):
        data=b''
        while len(data)<size:
            part=sock.recv(size-len(data))
            if not part: raise ProtocolError('Incomplete Modbus reply')
            data+=part
        return data
    with socket.create_connection((ip,port),timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(request)
        header=recv_exact(s,7)
        rt,proto,length,unit=struct.unpack('>HHHB',header)
        if rt!=tid or proto!=0 or unit!=1 or length<2 or length>253:
            raise ProtocolError('Invalid MBAP header')
        pdu=recv_exact(s,length-1)
        if pdu[0]==0x83: raise ProtocolError(f'Modbus exception {pdu[1] if len(pdu)>1 else "?"}')
        if pdu[0]!=3 or len(pdu)!=2+count*2 or pdu[1]!=count*2:
            raise ProtocolError('Unexpected read payload')
        return list(struct.unpack('>'+('H'*count),pdu[2:]))

class Collector:
    def __init__(self, config: Path, database: Path):
        self.config=config; self.database=database
        self.lock=threading.RLock()
        self.live:dict[str,dict[str,Any]]={}
        self.device_locks:dict[str,threading.Lock]={}
        self._init_db()
        self.reload()
    def _connect(self):
        db=sqlite3.connect(self.database,timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        return db
    def _init_db(self):
        self.database.parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, received_at TEXT NOT NULL, address INTEGER NOT NULL, values_json TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_snapshot_device_time ON snapshots(device_id,received_at)')
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, at TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, received_at TEXT NOT NULL, channel_type TEXT NOT NULL, channel INTEGER NOT NULL, metric TEXT NOT NULL, band TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, source TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_meas_series ON measurements(device_id,channel_type,channel,metric,band,received_at)')
    def reload(self):
        conf=json.loads(self.config.read_text(encoding='utf-8'))
        devices=conf.get('devices')
        if not isinstance(devices,list):raise ValueError('devices must be list')
        found=set(); validated=[]
        for d in devices:
            if not isinstance(d,dict) or not isinstance(d.get('id'),str) or not d['id'].strip():raise ValueError('Invalid device ID')
            if d['id'] in found:raise ValueError('Duplicate device ID')
            found.add(d['id'])
            if not isinstance(d.get('ip'),str) or not d['ip']:raise ValueError('Invalid device IP')
            if not isinstance(d.get('port'),int) or not 1<=d['port']<=65535:raise ValueError('Invalid device port')
            ranges=d.get('read_ranges',[])
            if not isinstance(ranges,list):raise ValueError('Invalid ranges')
            if d.get('enabled',False) and not ranges:raise ValueError('Enabled device requires explicit read_ranges')
            for r in ranges:
                if not isinstance(r.get('address'),int) or not isinstance(r.get('count'),int) or not (0<=r['address']<=65535 and 1<=r['count']<=125 and r['address']+r['count']<=65536):raise ValueError('Invalid range')
            interval=d.get('interval_seconds')
            if interval is not None and (not isinstance(interval,(int,float)) or interval<1):raise ValueError('interval_seconds must be null or >=1')
            validated.append(d)
        with self.lock:
            self.devices={d['id']:d for d in validated}
            for d in validated:self.device_locks.setdefault(d['id'],threading.Lock())
        return len(validated)
    def live_view(self, device_id: str) -> dict[str, Any]:
        """Annotated snapshot from memory; NEVER issues a device request.

        A configured polling interval is necessary to interpret freshness.
        With no agreed polling period, data age is shown but not labelled stale.
        """
        with self.lock:
            device = self.devices[device_id]
            snap = dict(self.live.get(device_id, {'id': device_id, 'status': 'not_polled', 'ranges': []}))
        stamp = snap.get('received_at')
        age = None
        if stamp:
            try:
                age = max(0., (datetime.now(timezone.utc)-datetime.fromisoformat(stamp.replace('Z','+00:00'))).total_seconds())
            except (ValueError, TypeError):
                pass
        interval = device.get('interval_seconds')
        max_age = interval * 3 if interval is not None else None
        stale = bool(snap.get('status') == 'connected' and max_age is not None and age is not None and age > max_age)
        snap['age_seconds'] = round(age, 3) if age is not None else None
        snap['freshness'] = ('stale' if stale else 'current' if snap.get('status') == 'connected' and max_age is not None and age is not None else 'unknown')
        snap['freshness_threshold_seconds'] = max_age
        snap['last_data_status'] = snap.get('status')
        if stale:
            snap['status'] = 'stale'
        return snap

    def public_devices(self):
        with self.lock:
            devices = list(self.devices.values())
        return [{"id":d['id'],"number":d.get('number',d['id']),"enabled":bool(d.get('enabled',False)),"status":view['status'],"received_at":view.get('received_at'),"age_seconds":view['age_seconds'],"freshness":view['freshness']} for d in devices for view in [self.live_view(d['id'])]]
    def poll_once(self,device_id:str):
        with self.lock:
            d=dict(self.devices[device_id])
        if not d.get('enabled',False):raise ValueError('Device disabled')
        guard=self.device_locks[device_id]
        if not guard.acquire(blocking=False):raise ValueError('Poll already in progress for this device')
        try:return self._poll_device(device_id,d)
        finally:guard.release()
    def _poll_device(self,device_id,d):
        stamp=datetime.now(timezone.utc).isoformat()
        try:
            ranges=[]
            for r in d.get('read_ranges',[]):
                values=modbus_read(d['ip'],d['port'],r['address'],r['count'])
                ranges.append({'address':r['address'],'values':values})
            snapshot={'id':device_id,'status':'connected','received_at':stamp,'ranges':ranges,'source':'modbus_fc03_raw'}
            snapshot['decoded']=decode_snapshot(snapshot)
            with self._connect() as db:
                for r in ranges:db.execute('INSERT INTO snapshots(device_id,received_at,address,values_json) VALUES (?,?,?,?)',(device_id,stamp,r['address'],json.dumps(r['values'])))
                for row in self._measurement_rows(device_id,stamp,snapshot['decoded']):
                    db.execute('INSERT INTO measurements(device_id,received_at,channel_type,channel,metric,band,value,unit,source) VALUES (?,?,?,?,?,?,?,?,?)',row)
            with self.lock:self.live[device_id]=snapshot
            return snapshot
        except (OSError,ProtocolError,ValueError) as exc:
            with self.lock:self.live[device_id]={'id':device_id,'status':'connection_error','received_at':stamp,'error':str(exc)}
            with self._connect() as db:db.execute('INSERT INTO events(device_id,at,status,detail) VALUES (?,?,?,?)',(device_id,stamp,'connection_error',str(exc)[:300]))
            raise
    @staticmethod
    def _measurement_rows(device_id,stamp,decoded):
        import math
        for c in decoded['channels']:
            for metric,field,unit in [('sensor_voltage','voltage_v','V'),('wide_acceleration_rms','acceleration_rms_up_to_25khz_m_s2','m/s2')]:
                v=c.get(field)
                if isinstance(v,(int,float)) and math.isfinite(v):
                    yield (device_id,stamp,'adc',c['channel'],metric,'',v,unit,'mvk01_modbus_fc03_decoded')
            for metric in ('rms','peak_equivalent','peak_peak_equivalent'):
                for band,entry in c.get(metric,{}).items():
                    v=entry.get('value')
                    if isinstance(v,(int,float)) and math.isfinite(v):
                        yield (device_id,stamp,'adc',c['channel'],metric,band,v,entry['unit'],'mvk01_modbus_fc03_decoded')
        for t in decoded['tachometers']:
            for metric,field,unit in [('rotation_frequency','frequency_hz','Hz'),('frequency_increment','average_frequency_increment_hz_per_rev','Hz/rev')]:
                v=t.get(field)
                if isinstance(v,(int,float)) and math.isfinite(v):
                    yield (device_id,stamp,'tachometer',t['channel'],metric,'',v,unit,'mvk01_modbus_fc03_decoded')

    def series(self,device_id,channel_type,channel,metric,band='',limit=500):
        with self._connect() as db:
            rows=db.execute('SELECT received_at,value,unit,source FROM measurements WHERE device_id=? AND channel_type=? AND channel=? AND metric=? AND band=? ORDER BY id DESC LIMIT ?', (device_id,channel_type,channel,metric,band,min(max(limit,1),2000))).fetchall()
        return [{'received_at':t,'value':v,'unit':u,'source':src} for t,v,u,src in reversed(rows)]

    def series_range(self,device_id,channel_type,channel,metric,band='',start=None,end=None,limit=5000):
        """Filter on SQL before pagination; read-only, never contacts a device."""
        if start and end and start > end:
            raise ValueError('Start date exceeds end date')
        where=['device_id=?','channel_type=?','channel=?','metric=?','band=?']
        args=[device_id,channel_type,channel,metric,band]
        if start: where.append('received_at>=?');args.append(start)
        if end: where.append('received_at<=?');args.append(end)
        clause=' AND '.join(where)
        with self._connect() as db:
            total=db.execute('SELECT COUNT(*) FROM measurements WHERE '+clause,args).fetchone()[0]
            rows=db.execute('SELECT received_at,value,unit,source FROM measurements WHERE '+clause+' ORDER BY received_at DESC,id DESC LIMIT ?',args+[limit]).fetchall()
        return {'total':total,'points':[{'received_at':t,'value':v,'unit':u,'source':src} for t,v,u,src in reversed(rows)],'truncated':total>len(rows)}

    def export_series_rows(self, device_id, channel_type, channel, metric, band='', start=None, end=None, chunk_size=1024):
        """Bounded-memory SQL iterator, no instrument access. Connection held while streaming."""
        if start and end and start > end:
            raise ValueError('Start date exceeds end date')
        where=['device_id=?','channel_type=?','channel=?','metric=?','band=?']
        args=[device_id,channel_type,channel,metric,band]
        if start: where.append('received_at>=?');args.append(start)
        if end: where.append('received_at<=?');args.append(end)
        with self._connect() as db:
            cursor=db.execute('SELECT received_at,value,unit,source FROM measurements WHERE '+' AND '.join(where)+' ORDER BY received_at,id',args)
            while True:
                batch=cursor.fetchmany(chunk_size)
                if not batch: break
                for row in batch: yield row

    def series_overview(self,device_id,channel_type,channel,metric,band='',start=None,end=None,buckets=1000):
        """Deterministic min/max envelope over all matching rows; preserves spikes."""
        if not 1<=buckets<=2000:raise ValueError('Invalid buckets count')
        where=['device_id=?','channel_type=?','channel=?','metric=?','band=?']
        args=[device_id,channel_type,channel,metric,band]
        if start:where.append('received_at>=?');args.append(start)
        if end:where.append('received_at<=?');args.append(end)
        clause=' AND '.join(where)
        with self._connect() as db:
            n=db.execute('SELECT COUNT(*) FROM measurements WHERE '+clause,args).fetchone()[0]
            if not n:return {'total':0,'points':[],'sampled':False}
            # Stream rows directly in index order. Avoid ROW_NUMBER/window sorting
            # on large archives; memory stays bounded by one envelope bucket.
            cur=db.execute('SELECT received_at,value,unit,id FROM measurements WHERE '
                           +clause+' ORDER BY received_at,id',args)
            pts=[]; group=[]; last_bucket=None
            for idx,(ts,val,unit,row_id) in enumerate(cur):
                bucket=(idx*buckets)//n
                if bucket!=last_bucket and group:
                    low=min(group,key=lambda x:x[1]); high=max(group,key=lambda x:x[1])
                    pts.extend(sorted({low,high},key=lambda x:x[3])); group=[]
                group.append((ts,val,unit,idx)); last_bucket=bucket
            if group:
                low=min(group,key=lambda x:x[1]); high=max(group,key=lambda x:x[1])
                pts.extend(sorted({low,high},key=lambda x:x[3]))
        return {'total':n,'points':[{'received_at':ts,'value':val,'unit':unit} for ts,val,unit,_ in pts],'sampled':n>len(pts)}

    def storage_stats(self):
        """SQL metadata only; never queries the physical instrument."""
        with self._connect() as db:
            page_count=db.execute('PRAGMA page_count').fetchone()[0]
            page_size=db.execute('PRAGMA page_size').fetchone()[0]
            snap=db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0]
            meas=db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0]
            errors=db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
            latest=db.execute('SELECT MAX(received_at) FROM snapshots').fetchone()[0]
        return {'database_bytes_approx':page_count*page_size,'snapshots':snap,
                'measurements':meas,'events':errors,'last_snapshot_utc':latest}

    def backup_sqlite(self,destination:Path):
        """Create verified online SQLite snapshot, publish only after success.

        The live database is never replaced and device I/O is never used.
        """
        destination=Path(destination).resolve()
        source=self.database.resolve()
        if destination==source:raise ValueError('Backup must not overwrite live database')
        if destination.suffix.lower() not in ('.sqlite3','.db'):
            raise ValueError('Backup filename must end in .sqlite3 or .db')
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():raise FileExistsError('Backup already exists')
        temp=destination.with_name(destination.name+'.partial')
        if temp.exists():raise FileExistsError('Partial backup already exists')
        try:
            with self._connect() as src, sqlite3.connect(temp,timeout=5) as dst:
                src.backup(dst,pages=100,sleep=0.05)
                result=dst.execute('PRAGMA integrity_check').fetchone()[0]
                if result!='ok':raise RuntimeError('Backup integrity check failed: '+str(result))
            # Avoid overwriting a backup made concurrently by another process.
            os.link(temp,destination)
            temp.unlink()
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        return {'path':str(destination),'size_bytes':destination.stat().st_size,'integrity':'ok'}

    def database_diagnostics(self):
        """Read-only bounded diagnostic probe. No instrument requests."""
        started=time.perf_counter()
        try:
            with self._connect() as db:
                db.execute('SELECT 1').fetchone()
                mode=db.execute('PRAGMA journal_mode').fetchone()[0]
                info=db.execute('PRAGMA quick_check(1)').fetchone()[0]
                tables={name:bool(db.execute('SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=?',(name,)).fetchone())
                        for name in ('measurements','snapshots','events')}
            elapsed=round((time.perf_counter()-started)*1000,2)
            return {'status':'ok' if info=='ok' and all(tables.values()) else 'degraded',
                    'database_accessible':True,'journal_mode':mode,'schema_tables':tables,
                    'quick_check':info,'probe_duration_ms':elapsed,'device_requests':0}
        except (sqlite3.Error,OSError) as exc:
            return {'status':'error','database_accessible':False,'error_type':type(exc).__name__,
                    'probe_duration_ms':round((time.perf_counter()-started)*1000,2),'device_requests':0}

    def connection_stats(self):
        with self.lock:
            devices=list(self.devices.values())
            current={d['id']:self.live.get(d['id'],{}) for d in devices}
        return {'configured_devices':len(devices),
                'enabled_devices':sum(bool(d.get('enabled')) for d in devices),
                'scheduled_devices':sum(bool(d.get('enabled')) and d.get('interval_seconds') is not None for d in devices),
                'device_status':[{'number':d.get('number',d['id']),
                                  'status':current[d['id']].get('status','not_polled'),
                                  'last_received_utc':current[d['id']].get('received_at')} for d in devices]}

    def history(self,device_id:str,limit:int=100):
        with self._connect() as db:
            rows=db.execute('SELECT received_at,address,values_json FROM snapshots WHERE device_id=? ORDER BY id DESC LIMIT ?',(device_id,limit)).fetchall()
        return [{'received_at':r[0],'address':r[1],'values':json.loads(r[2])} for r in rows]
