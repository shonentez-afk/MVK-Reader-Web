"""Safe local device registry; never sends commands to an instrument."""
import json, ipaddress, os, tempfile, threading
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from collector.service import scheduler
from collector.service import collector

router=APIRouter(prefix="/api/mvk")
registry_lock=threading.RLock()
class DevicePayload(BaseModel):
    id:str=Field(min_length=1,max_length=40,pattern=r"^[A-Za-z0-9_-]+$")
    number:str=Field(min_length=1,max_length=60)
    ip:str
    modbus_port:int=Field(default=502,ge=1,le=65535)
    signal_port:int=Field(default=10230,ge=1,le=65535)

def validate_payload(item):
    try:
        ipaddress.ip_address(item.ip)
    except ValueError: raise HTTPException(422,'IP address must be IPv4 or IPv6 literal')
    if item.modbus_port==item.signal_port: raise HTTPException(422,'Ports must be different')

def device_list():
    with collector.lock:
        return [{"id":d['id'],"name":"МВК01 №"+str(d.get('number',d['id'])),"number":str(d.get('number',d['id'])),"ip":d['ip'],"modbus_port":d['port'],"signal_port":d.get('signal_port',10230),"enabled":bool(d.get('enabled',False)),"signal_live_ready":False,"modbus_status":collector.live_view(d['id'])['status'],"signal_status":"not_implemented"} for d in collector.devices.values()]

@router.get('/devices')
def devices(): return {'devices':device_list(),'source':'collector-config','read_only':False}

@router.get('/capabilities')
def capabilities(): return {'tabs':{'calculated':{'port':502,'protocol':'modbus-tcp','status':'collector-existing'},'wave':{'port':10230,'protocol':'mvk-signal','status':'offline-only'},'spectrum':{'port':10230,'protocol':'mvk-signal','status':'offline-only'}},'can_start_signal_live':False,'can_write_device':False,'can_edit_device_registry':True}

def write_config(new_config):
    path=Path(collector.config)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.devices-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(new_config,f,ensure_ascii=False,indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(temp,path)
        collector.reload()
    finally:
        if os.path.exists(temp):os.unlink(temp)

def mutate(item,existing_id=None):
    validate_payload(item)
    with registry_lock:
        with collector.lock: rows=[dict(d) for d in collector.devices.values()]
        index=next((i for i,d in enumerate(rows) if d['id']==existing_id),None) if existing_id else None
        if existing_id and index is None: raise HTTPException(404,'Unknown device')
        if any(d['id']==item.id and i!=index for i,d in enumerate(rows)):raise HTTPException(409,'Duplicate device id')
        if index is not None:
            previous=rows[index]
            if previous.get('enabled'):raise HTTPException(409,'Disable device in configuration before modifying connection details')
        else:previous={}
        result={**previous,'id':item.id,'number':item.number,'ip':item.ip,'port':item.modbus_port,'signal_port':item.signal_port,'enabled':False,'read_ranges':previous.get('read_ranges',[]),'interval_seconds':None}
        if index is None:rows.append(result)
        else:rows[index]=result
        write_config({'devices':rows})
        return result

@router.post('/devices',status_code=201)
def create_device(item:DevicePayload):return mutate(item)
@router.put('/devices/{device_id}')
def update_device(device_id:str,item:DevicePayload):return mutate(item,device_id)
@router.delete('/devices/{device_id}')
def delete_device(device_id:str):
    with registry_lock:
        with collector.lock:rows=[dict(d) for d in collector.devices.values()]
        found=next((d for d in rows if d['id']==device_id),None)
        if found is None:raise HTTPException(404,'Unknown device')
        if found.get('enabled'):raise HTTPException(409,'Cannot delete enabled device')
        write_config({'devices':[d for d in rows if d['id']!=device_id]})
        return {'removed':device_id}


class PollControl(BaseModel):
    interval_seconds: float = Field(default=5.0, ge=1.0, le=3600.0)

@router.get('/devices/{device_id}/connection')
def connection_state(device_id: str):
    with collector.lock:
        d = collector.devices.get(device_id)
        if d is None: raise HTTPException(404, 'Unknown device')
        enabled = bool(d.get('enabled', False))
        interval = d.get('interval_seconds')
    view = collector.live_view(device_id)
    return {'id':device_id,'modbus':{'enabled':enabled,'status':view['status'],
        'interval_seconds':interval,'received_at':view.get('received_at'),
        'age_seconds':view.get('age_seconds'), 'freshness':view.get('freshness'),
        'scheduler':scheduler.status().get(device_id)},
        'signal':{'status':'blocked_unverified_handshake','enabled':False,'port':d.get('signal_port',10230)},
        'note':'Status is based on cached reads; enabling polls the instrument via FC03 only.'}

@router.post('/devices/{device_id}/modbus/start')
def modbus_start(device_id: str, options: PollControl):
    with registry_lock:
        with collector.lock:
            rows=[dict(d) for d in collector.devices.values()]
        match=next((d for d in rows if d['id']==device_id),None)
        if match is None: raise HTTPException(404,'Unknown device')
        if not match.get('read_ranges'):
            raise HTTPException(409,'Configure explicitly approved Modbus FC03 read ranges before starting')
        if match.get('enabled'):
            raise HTTPException(409,'Polling is already enabled; disconnect before changing interval')
        match['interval_seconds']=options.interval_seconds
        match['enabled']=True
        write_config({'devices':rows})
    return {'id':device_id,'modbus_polling':'enabled', 'interval_seconds':options.interval_seconds,
        'read_ranges':match['read_ranges'],'signal_live_enabled':False}

@router.post('/devices/{device_id}/modbus/stop')
def modbus_stop(device_id: str):
    with registry_lock:
        with collector.lock: rows=[dict(d) for d in collector.devices.values()]
        match=next((d for d in rows if d['id']==device_id),None)
        if match is None: raise HTTPException(404,'Unknown device')
        match['enabled']=False
        match['interval_seconds']=None
        write_config({'devices':rows})
    return {'id':device_id,'modbus_polling':'disabled',
        'note':'Existing in-flight FC03 request may finish; future scheduling is disabled.',
        'signal_live_enabled':False}
