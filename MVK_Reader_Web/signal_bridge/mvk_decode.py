#!/usr/bin/env python3
"""Read-only PCAPNG/TCP/MVK analyzer. Standard library only."""
import argparse, collections, csv, json, math, pathlib, struct

DEVICE='192.0.2.84'; HOST='192.0.2.248'; PORT=10230
MARKER=0xFF800ADC

def u16(b,o=0): return struct.unpack_from('<H',b,o)[0]
def u32(b,o=0): return struct.unpack_from('<I',b,o)[0]

def pcapng(path, stats):
    """Read validated blocks incrementally. Yield (timestamp_seconds, linktype, frame)."""
    endian=None; interfaces=[]
    with open(path,'rb') as f:
        while True:
            start=f.tell(); head=f.read(8)
            if not head: break
            if len(head)!=8: raise ValueError(f'truncated block header at {start}')
            if head[:4]==b'\x0a\x0d\x0d\x0a':
                bom=f.read(4)
                if bom==b'\x4d\x3c\x2b\x1a': endian='<'
                elif bom==b'\x1a\x2b\x3c\x4d': endian='>'
                else: raise ValueError(f'bad SHB BOM at {start}')
                length=struct.unpack(endian+'I',head[4:])[0]
                if length<28 or length%4: raise ValueError('invalid SHB length')
                f.seek(start+8)
                interfaces=[]
            else:
                if endian is None: raise ValueError('no section')
                length=struct.unpack(endian+'I',head[4:])[0]
            if length<12 or length%4: raise ValueError(f'invalid length {length} at {start}')
            body=f.read(length-12); tail=f.read(4)
            if len(body)!=length-12 or len(tail)!=4: raise ValueError(f'truncated block at {start}')
            if struct.unpack(endian+'I',tail)[0]!=length: raise ValueError(f'bad end length at {start}')
            typ=struct.unpack(endian+'I',head[:4])[0]
            stats['blocks']+=1; stats['block_types'][str(typ)]+=1
            if typ==1:
                if len(body)<8: raise ValueError('short IDB')
                link,snap=struct.unpack_from(endian+'HxxI',body)
                tsres=1e-6; pos=8
                while pos+4<=len(body):
                    opt,sz=struct.unpack_from(endian+'HH',body,pos); pos+=4
                    if pos+sz>len(body): raise ValueError('bad IDB option')
                    if opt==9 and sz==1:
                        v=body[pos]; tsres=(2**-(v&127)) if v&128 else 10**-v
                    pos+=(sz+3)&~3
                    if opt==0: break
                interfaces.append((link,snap,tsres))
                stats['interfaces'].append({'linktype':link,'snaplen':snap,'ts_resolution':tsres})
            elif typ==6:
                if len(body)<20: raise ValueError('short EPB')
                i,hi,lo,cap,orig=struct.unpack_from(endian+'IIIII',body)
                if i>=len(interfaces) or cap>orig or 20+((cap+3)&~3)>len(body): raise ValueError('bad EPB')
                link,snap,res=interfaces[i]
                if snap and cap>snap: raise ValueError('captured length exceeds snaplen')
                stats['packets']+=1
                yield (hi*2**32+lo)*res,link,body[20:20+cap]

def parse_tcp(frame,link):
    if link!=1 or len(frame)<14: return None
    off=12; et=struct.unpack_from('!H',frame,off)[0]; p=14
    while et in (0x8100,0x88a8,0x9100):
        if p+4>len(frame): return None
        et=struct.unpack_from('!H',frame,p+2)[0];p+=4
    if et!=0x0800 or p+20>len(frame): return None
    verihl=frame[p]; ihl=(verihl&15)*4
    if verihl>>4!=4 or ihl<20 or p+ihl>len(frame): return None
    total=struct.unpack_from('!H',frame,p+2)[0]
    frag=struct.unpack_from('!H',frame,p+6)[0]
    if total<ihl or p+total>len(frame) or (frag&0x3fff): return None
    if frame[p+9]!=6: return None
    src='.'.join(map(str,frame[p+12:p+16])); dst='.'.join(map(str,frame[p+16:p+20]))
    t=p+ihl
    if t+20>p+total: return None
    sport,dport,seq,ack,flags_offset,flags=struct.unpack_from('!HHIIBB',frame,t)
    thl=(flags_offset>>4)*4
    if thl<20 or t+thl>p+total: return None
    return src,dst,sport,dport,seq,flags,frame[t+thl:p+total]

def assemble(records):
    if not records:return b'',{'gaps':[],'overlap_bytes':0,'conflict_bytes':0,'unique_bytes':0}
    base=records[0][0]; intervals=[]
    for seq,data in records:
        rel=(seq-base)&0xffffffff
        if rel>=0x80000000: rel-=0x100000000
        intervals.append((rel,data))
    intervals.sort(key=lambda x:x[0]); start=intervals[0][0]; cursor=start; out=bytearray(); gaps=[]; overlaps=conflicts=0
    # track byte locations via contiguous runs; on gap preserve discontinuity
    runs=[]; current=bytearray(); run_start=cursor
    for pos,data in intervals:
        end=pos+len(data)
        if pos>cursor:
            gaps.append([cursor,pos]); runs.append((run_start,bytes(current)));current=bytearray();run_start=pos;cursor=pos
        if pos<cursor:
            n=min(cursor-pos,len(data));overlaps+=n
            # Compare all retained run bytes overlapping the incoming segment
            for rs,rd in runs+[(run_start,current)]:
                a=max(pos,rs);b=min(pos+n,rs+len(rd))
                if a<b: conflicts+=sum(x!=y for x,y in zip(data[a-pos:b-pos],rd[a-rs:b-rs]))
            data=data[n:]
        if data:current.extend(data);cursor=max(cursor,end)
    runs.append((run_start,bytes(current)))
    return runs,{'gaps':gaps,'overlap_bytes':overlaps,'conflict_bytes':conflicts,'unique_bytes':sum(len(x[1]) for x in runs)}

def messages(run,counts,channels,examples,unknown,write_samples=None):
    pos=0
    while pos+8<=len(run):
        marker,length=struct.unpack_from('<II',run,pos)
        if length<8 or length>10000000 or pos+length>len(run):
            unknown.append({'offset':pos,'remaining':len(run)-pos,'marker':hex(marker),'length':length});break
        counts[f'0x{marker:08X}/{length}']+=1
        if marker==MARKER and length==1052:
            channel=struct.unpack_from('<I',run,pos+20)[0]
            channels[str(channel)]+=1
            if channel<8:
                if str(channel) not in examples:
                    vals=struct.unpack_from('<256f',run,pos+28)
                    examples[str(channel)]={'header28':run[pos:pos+28].hex(),'first8_samples':list(vals[:8]),'finite':all(math.isfinite(v) for v in vals)}
                if write_samples is not None:
                    write_samples[channel].write(run[pos+28:pos+1052])
        pos+=length
    return pos

def analyze(path,outdir,export=False):
    stats={'blocks':0,'block_types':collections.Counter(),'packets':0,'interfaces':[],'tcp_counts':collections.Counter(),'flags':collections.Counter()}
    rec=collections.defaultdict(list);times=[]
    for ts,link,frame in pcapng(path,stats):
        if not times:times.append(ts)
        last=ts
        parsed=parse_tcp(frame,link)
        if not parsed:continue
        src,dst,sp,dp,seq,flags,payload=parsed
        if {src,dst}!={DEVICE,HOST} or (sp!=PORT and dp!=PORT):continue
        direction='device_to_host' if src==DEVICE else 'host_to_device'
        stats['tcp_counts'][direction+'_packets']+=1
        stats['tcp_counts'][direction+'_payload_bytes']+=len(payload)
        for n,b in [('syn',2),('fin',1),('rst',4)]:
            if flags&b:stats['flags'][direction+'_'+n]+=1
        if payload:rec[(src,sp,dst,dp)].append((seq,payload))
    stats['duration_seconds']=last-times[0] if times else 0
    streams={}; total_counts=collections.Counter();channels=collections.Counter();examples={};unknown=[]
    writers={}
    if export:
        for c in range(8):writers[c]=open(outdir/f'channel_{c}.f32le','wb')
    try:
        for key,records in rec.items():
            runs,quality=assemble(records)
            skey=f'{key[0]}:{key[1]} -> {key[2]}:{key[3]}'
            streams[skey]={'packets_with_payload':len(records),'runs':len(runs),**quality}
            if key[0]==DEVICE and key[1]==PORT:
                for _,run in runs:
                    consumed=messages(run,total_counts,channels,examples,unknown,writers if export else None)
                    streams[skey].setdefault('consumed_bytes',0);streams[skey]['consumed_bytes']+=consumed
    finally:
        for f in writers.values():f.close()
    report={'file':str(path),'size_bytes':path.stat().st_size,'pcapng':{k:(dict(v) if isinstance(v,collections.Counter) else v) for k,v in stats.items()},'streams':streams,'message_types':dict(total_counts),'channels':dict(channels),'channel_examples':examples,'parse_errors':unknown[:20], 'parse_error_count':len(unknown)}
    (outdir/(path.stem+'_report.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('files',nargs='+',type=pathlib.Path);p.add_argument('--out',type=pathlib.Path,default=pathlib.Path('.'));p.add_argument('--export-samples',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    for path in a.files:
        print('ANALYZING',path,flush=True)
        rep=analyze(path,a.out,a.export_samples)
        print(json.dumps({k:rep[k] for k in ['size_bytes','message_types','channels','parse_error_count','streams']},indent=2),flush=True)
if __name__=='__main__':main()
