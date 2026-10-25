"""Standalone FastAPI Collector. Configuration changed only in local JSON file."""
import os, threading, asyncio, json, time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from .core import Collector
from .scheduler import PollScheduler
ROOT=Path(__file__).resolve().parent
collector=Collector(Path(os.getenv('MVK_DEVICES_CONFIG',str(ROOT/'devices.json'))),Path(os.getenv('MVK_COLLECTOR_DB',str(ROOT/'collector.sqlite3'))))
stop=threading.Event()
thread=None
scheduler=PollScheduler(collector)

def loop():
    while not stop.wait(.25):
        try:
            scheduler.step()
        except Exception:
            # Keep polling lifecycle alive; individual poll errors are recorded in core.
            import logging
            logging.getLogger(__name__).exception('Unexpected scheduler failure')

@asynccontextmanager
async def lifespan(app):
    global thread
    stop.clear()
    thread=threading.Thread(target=loop, name='mvk-collector-poller',daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        await asyncio.to_thread(thread.join, 3.0)
        if thread.is_alive():
            import logging
            logging.getLogger(__name__).warning('Poller did not terminate in 3s (in-flight device operation)')
        else:
            thread=None

app=FastAPI(title='MVK Collector Server',version='0.3.17-lab',lifespan=lifespan)
@app.get('/api/health')
def health():return {'status':'ok','version':'0.3.17-lab','read_only':True,'polling_policy':'disabled_unless_interval_configured'}
@app.get('/api/server-status')
def server_status():
    return {'connections':collector.connection_stats(),'storage':collector.storage_stats(),'read_only_instrument':True,'polling_scheduler':scheduler.status()}

@app.get('/api/storage-diagnostics')
def storage_diagnostics():
    return collector.database_diagnostics()

@app.get('/api/devices')
def devices():return collector.public_devices()
@app.get('/api/devices/{device_id}/live')
def live(device_id:str):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    return collector.live_view(device_id)
@app.get('/api/devices/{device_id}/history')
def history(device_id:str,limit:int=100):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    return collector.history(device_id,max(1,min(limit,1000)))

@app.get('/api/devices/{device_id}/measurements')
def measurements(device_id:str):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    data=collector.live_view(device_id)
    if data.get('status')=='not_polled':return {'id':device_id,'status':'not_polled','channels':[],'tachometers':[]}
    if data.get('status')!='connected':return {'id':device_id,'status':data.get('status'),'channels':[],'tachometers':[]}
    return data.get('decoded',{'id':device_id,'channels':[],'tachometers':[]})

@app.get('/api/devices/{device_id}/series')
def series(device_id:str,channel_type:str='adc',channel:int=1,metric:str='rms',band:str='10-3000:velocity',limit:int=500):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    if channel_type not in ('adc','tachometer'):raise HTTPException(422,'Invalid channel type')
    if not 1<=channel<=(8 if channel_type=='adc' else 2):raise HTTPException(422,'Invalid channel')
    return {'id':device_id,'channel_type':channel_type,'channel':channel,'metric':metric,'band':band,'points':collector.series(device_id,channel_type,channel,metric,band,limit)}

@app.get('/api/devices/{device_id}/series-range')
def series_range(device_id:str,channel_type:str='adc',channel:int=1,metric:str='rms',band:str='10-3000:velocity',start:str|None=None,end:str|None=None,limit:int=Query(default=5000,ge=1,le=20000)):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    if channel_type not in ('adc','tachometer'):raise HTTPException(422,'Invalid channel type')
    if not 1<=channel<=(8 if channel_type=='adc' else 2):raise HTTPException(422,'Invalid channel')
    from datetime import datetime,timezone
    def parse(v):
        if not v:return None
        try:
            dt=datetime.fromisoformat(v.replace('Z','+00:00'))
            if dt.tzinfo is None:raise ValueError('Timezone required')
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:raise HTTPException(422,'Invalid ISO date/time with timezone')
    a,b=parse(start),parse(end)
    if a and b and a>b:raise HTTPException(422,'Start later than end')
    result=collector.series_range(device_id,channel_type,channel,metric,band,a,b,limit)
    return {'id':device_id,'channel_type':channel_type,'channel':channel,'metric':metric,'band':band,**result}

@app.get('/api/devices/{device_id}/history-export.csv')
def history_export_csv(device_id:str,channel_type:str='adc',channel:int=1,metric:str='rms',band:str='10-3000:velocity',start:str|None=None,end:str|None=None):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    if channel_type not in ('adc','tachometer') or not 1<=channel<=(8 if channel_type=='adc' else 2):raise HTTPException(422,'Invalid channel')
    a,b=_history_time_range(start,end)
    import csv,io
    def emit():
        yield '\ufeff'
        def line(fields):
            buf=io.StringIO();csv.writer(buf,delimiter=';').writerow(fields);return buf.getvalue()
        yield line(['timestamp_utc','device_id','channel_type','channel','metric','band','value','unit','source'])
        for ts,value,unit,source in collector.export_series_rows(device_id,channel_type,channel,metric,band,a,b):
            yield line([ts,device_id,channel_type,channel,metric,band,value,unit,source])
    return StreamingResponse(emit(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="mvk_history.csv"','Cache-Control':'no-store'})

@app.get('/api/devices/{device_id}/series-overview')
def series_overview(device_id:str,channel_type:str='adc',channel:int=1,metric:str='rms',band:str='10-3000:velocity',start:str|None=None,end:str|None=None,buckets:int=Query(default=1000,ge=1,le=2000)):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    if channel_type not in ('adc','tachometer') or not 1<=channel<=(8 if channel_type=='adc' else 2):raise HTTPException(422,'Invalid channel')
    a,b=_history_time_range(start,end)
    return {'id':device_id,'channel_type':channel_type,'channel':channel,'metric':metric,'band':band,**collector.series_overview(device_id,channel_type,channel,metric,band,a,b,buckets)}

def _history_time_range(start,end):
    from datetime import datetime,timezone
    def parse(v):
        if not v:return None
        try:
            dt=datetime.fromisoformat(v.replace('Z','+00:00'))
            if dt.tzinfo is None:raise ValueError('Timezone required')
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:raise HTTPException(422,'Invalid ISO date/time with timezone')
    a,b=parse(start),parse(end)
    if a and b and a>b:raise HTTPException(422,'Start later than end')
    return a,b

@app.get('/api/devices/{device_id}/diagnostics')
def diagnostics(device_id:str):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    data=collector.live_view(device_id)
    if data.get('status')!='connected':
        return {'id':device_id,'status':data.get('status','not_polled') if data else 'not_polled','system':None}
    return {'id':device_id,'status':'connected','received_at':data.get('received_at'), 'system':data.get('decoded',{}).get('system')}

@app.get('/api/devices/{device_id}/third-octave')
def third_octave(device_id:str,channel:int=1):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    if not 1<=channel<=8:raise HTTPException(422,'Channel must be 1..8')
    snapshot=collector.live_view(device_id)
    if snapshot.get('status')!='connected':
        return {'id':device_id,'channel':channel,'status':snapshot.get('status','not_polled') if snapshot else 'not_polled','bands':[], 'source':'unavailable'}
    decoded=snapshot.get('decoded',{})
    adc=next((v for v in decoded.get('channels',[]) if v['channel']==channel),None)
    if adc is None: 
        return {'id':device_id,'channel':channel,'status':'no_channel_data','bands':[], 'source':'unavailable'}
    frequencies=adc.get('third_octave_hz',[])
    readings=adc.get('third_octave_acceleration_m_s2',[])
    return {'id':device_id,'channel':channel,'status':'connected', 'received_at':snapshot['received_at'],
        'source':'mvk01_modbus_fc03_decoded', 'quantity':'rms_acceleration', 'unit':'m/s2',
        'bands':[{'center_hz':f,'rms_m_s2':v} for f,v in zip(frequencies,readings)],
        'available_count':sum(v is not None for v in readings),
        'note':'Только документированный третьоктавный массив ускорения. Недоступные полосы показаны без значений. Данные не подтверждены реальным прибором.'}

@app.get('/api/devices/{device_id}/channel-status')
def channel_status(device_id:str, channel:int=1):
    if device_id not in collector.devices:raise HTTPException(404,'Unknown device')
    if not 1<=channel<=8:raise HTTPException(422,'Channel must be 1..8')
    snap=collector.live_view(device_id)
    if snap.get('status')!='connected':
        return {'id':device_id,'channel':channel,'status':'not_available','indicators':None}
    dec=snap.get('decoded',{})
    c=next((a for a in dec.get('channels',[]) if a['channel']==channel),None)
    return {'id':device_id,'channel':channel,'status':'connected',
            'received_at':snap.get('received_at'),
            'indicators':c.get('channel_status') if c else None,
            'source':'manual_3.5.7_modbus_fc03_read_only'}


@app.get('/api/events')
async def events():
    """SSE over server cache only: no Modbus operation on subscriber connection."""
    async def stream():
        previous=None
        while True:
            # Take an immutable, public view of cached state. Never request devices here.
            state=collector.public_devices()
            signature=json.dumps(state,sort_keys=True,ensure_ascii=False)
            if signature!=previous:
                yield 'event: devices\ndata: '+signature+'\n\n'
                previous=signature
            else:
                yield ': heartbeat\n\n'
            await asyncio.sleep(2)
    return StreamingResponse(stream(),media_type='text/event-stream', headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
