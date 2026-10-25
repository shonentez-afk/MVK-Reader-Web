"""Local-only simulated Modbus devices: zero real-network traffic."""
import json, socket, sqlite3, struct, tempfile, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from collector.core import Collector, ProtocolError

class Simulator:
    def __init__(self, start=100, broken=False):
        self.start=start; self.broken=broken; self.requests=[]; self.stop=threading.Event()
        self.sock=socket.socket(); self.sock.bind(('127.0.0.1',0)); self.sock.listen(12)
        self.sock.settimeout(.15); self.port=self.sock.getsockname()[1]
        self.thread=threading.Thread(target=self._serve,daemon=True); self.thread.start()
    def _serve(self):
        while not self.stop.is_set():
            try:conn,_=self.sock.accept()
            except socket.timeout:continue
            except OSError:break
            with conn:
                conn.settimeout(1)
                try:
                    packet=conn.recv(12)
                    if len(packet)!=12:continue
                    tid,_,_,unit,code,address,count=struct.unpack('>HHHBBHH',packet)
                    self.requests.append((code,address,count))
                    if self.broken:continue
                    values=[(self.start+i) % 65536 for i in range(count)]
                    data=struct.pack('>'+('H'*count),*values)
                    pdu=bytes([3,len(data)])+data
                    conn.sendall(struct.pack('>HHHB',tid,0,len(pdu)+1,unit)+pdu)
                except (OSError,ValueError):pass
    def close(self):
        self.stop.set(); self.sock.close(); self.thread.join(timeout=2)

def config(devices):return {'devices':[{'id':name,'number':str(idx+1),'ip':'127.0.0.1','port':s.port,'enabled':True,'read_ranges':[{'address':0x1000,'count':2}],'interval_seconds':None} for idx,(name,s) in enumerate(devices)]}

def test_multiple_simulated_devices_and_isolated_history():
    a,b=Simulator(101),Simulator(202)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'devices.json').write_text(json.dumps(config([('mvk_a',a),('mvk_b',b)])))
            c=Collector(root/'devices.json',root/'db.sqlite3')
            with ThreadPoolExecutor(max_workers=2) as pool:
                f1=pool.submit(c.poll_once,'mvk_a');f2=pool.submit(c.poll_once,'mvk_b')
                assert f1.result()['ranges'][0]['values']==[101,102]
                assert f2.result()['ranges'][0]['values']==[202,203]
            assert c.history('mvk_a')[0]['values']==[101,102]
            assert c.history('mvk_b')[0]['values']==[202,203]
            assert all(x[0]==3 for x in a.requests+b.requests)
            with sqlite3.connect(root/'db.sqlite3') as db:
                assert db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0]==2
    finally:a.close();b.close()

def test_connection_loss_does_not_represent_old_reading_as_current():
    a=Simulator(500)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'devices.json').write_text(json.dumps(config([('mvk_a',a)])))
            c=Collector(root/'devices.json',root/'db.sqlite3')
            c.poll_once('mvk_a');a.close()
            try:c.poll_once('mvk_a')
            except (OSError,ProtocolError):pass
            else:raise AssertionError('Expected connection failure')
            assert c.public_devices()[0]['status']=='connection_error'
            assert 'ranges' not in c.live['mvk_a']
            assert len(c.history('mvk_a'))==1
            with sqlite3.connect(root/'db.sqlite3') as db:
                assert db.execute("SELECT COUNT(*) FROM events WHERE status='connection_error'").fetchone()[0]==1
    finally:a.close()

def test_browser_cache_read_never_calls_modbus():
    a=Simulator()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'devices.json').write_text(json.dumps(config([('mvk_a',a)])))
            c=Collector(root/'devices.json',root/'db.sqlite3')
            with patch('collector.core.modbus_read',side_effect=AssertionError('Unexpected instrument read')):
                for _ in range(100):
                    c.public_devices();c.history('mvk_a');c.series('mvk_a','adc',1,'rms','10-3000:velocity')
            assert len(a.requests)==0
    finally:a.close()

def test_enabled_device_requires_explicit_read_ranges():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); (root/'devices.json').write_text(json.dumps({'devices':[{'id':'bad','ip':'127.0.0.1','port':502,'enabled':True,'read_ranges':[], 'interval_seconds':None}]}))
        try:Collector(root/'devices.json',root/'db.sqlite3')
        except ValueError as e:assert 'read_ranges' in str(e)
        else:raise AssertionError('Enabled empty configuration accepted')
