#!/usr/bin/env python3
"""MVK01 calibration reader: Modbus TCP FC03 only. No automatic connection."""
import argparse, datetime, ipaddress, json, pathlib, socket, struct, time

def frame(tid, unit, addr, count):
    assert 1 <= count <= 125
    return struct.pack('>HHHBBHH', tid, 0, 6, unit, 3, addr, count)

def recv_exact(s, n):
    b = bytearray()
    while len(b) < n:
        p = s.recv(n - len(b))
        if not p: raise ConnectionError('Connection closed by device')
        b.extend(p)
    return bytes(b)

def get(s, tid, unit, addr, count):
    s.sendall(frame(tid, unit, addr, count))
    h = recv_exact(s, 7)
    rt, proto, length, ru = struct.unpack('>HHHB', h)
    if rt != tid or proto != 0 or ru != unit or length < 2 or length > 254: raise ValueError('Invalid Modbus MBAP header')
    pdu = recv_exact(s, length-1)
    record = {'address': '0x%04X'%addr, 'count':count, 'request_hex':frame(tid, unit, addr, count).hex(), 'response_hex':(h+pdu).hex()}
    if pdu[0] == 0x83:
        record['exception_code'] = pdu[1] if len(pdu)>1 else None
        return record
    if pdu[0] != 3 or len(pdu) < 2 or pdu[1] != count*2 or len(pdu) != 2+count*2: raise ValueError('Invalid FC03 response')
    raw = pdu[2:]
    record['raw_hex'] = raw.hex()
    record['float32_candidates'] = []
    for i in range(0, len(raw)-3, 4):
        w=raw[i:i+4]
        candidates={}
        for k, b in {'ABCD':w, 'CDAB':w[2:4]+w[:2], 'BADC':bytes([w[1],w[0],w[3],w[2]]),'DCBA':w[::-1]}.items():
            v=struct.unpack('>f',b)[0]
            candidates[k]=v if abs(v)<1e30 and v==v else None
        record['float32_candidates'].append({'register':'0x%04X'%(addr+i//2), 'raw':w.hex(), 'orders':candidates})
    return record

def main():
    p=argparse.ArgumentParser(description='MVK01 read-only calibration probe (FC03)')
    p.add_argument('--host',required=True);p.add_argument('--port',type=int,default=502);p.add_argument('--unit',type=int,default=1)
    p.add_argument('--output',default='calibration_results.json');p.add_argument('--timeout',type=float,default=2.0)
    p.add_argument('--confirm-read',action='store_true',help='Explicitly permit active FC03 probes')
    a=p.parse_args()
    ipaddress.ip_address(a.host)
    if not 1<=a.port<=65535 or not 0<=a.unit<=255: p.error('Invalid port/unit')
    if not a.confirm_read: p.error('No connection performed. Add --confirm-read for authorized FC03 diagnostic.')
    probes=[('adc_calibration_volts',0x0020,16)]
    for ch in range(8):
        base=0x100+ch*0x100
        probes.extend([('adc%d_sensor_sensitivity'%(ch+1),base+2,2),('adc%d_conversion'%(ch+1),base+14,2)])
    results=[]
    for n,(name,addr,count) in enumerate(probes,1):
        entry={'name':name,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        try:
            with socket.create_connection((a.host,a.port),timeout=a.timeout) as s:
                s.settimeout(a.timeout)
                entry.update(get(s,n,a.unit,addr,count))
        except Exception as exc:
            entry.update({'address':'0x%04X'%addr,'count':count,'error':str(exc)})
        results.append(entry)
        print('%-28s %-8s %s'%(name,entry['address'],'ERROR '+entry['error'] if 'error' in entry else 'exception '+str(entry['exception_code']) if 'exception_code' in entry else entry.get('raw_hex','')))
        time.sleep(0.12)
    obj={'source':'MVK01 Modbus TCP FC03 only','device':a.host,'port':a.port,'unit':a.unit,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'records':results}
    pathlib.Path(a.output).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf8')
    print('SAVED',a.output)
if __name__=='__main__':main()
