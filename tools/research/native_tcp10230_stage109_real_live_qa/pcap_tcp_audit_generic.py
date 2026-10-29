#!/usr/bin/env python3
"""Offline independent parser: PCAPNG Ethernet/IPv4/TCP, exact TCP-sequence reassembly,
no access to instrument, no external network, no Python third-party modules."""
import collections, datetime, hashlib, ipaddress, json, mmap, os, pathlib, struct, sys
U16=struct.Struct('<H').unpack_from;U32=struct.Struct('<I').unpack_from

def option_list(mv,start,end):
    out={};off=start
    while off+4<=end:
        code,ln=struct.unpack_from('<HH',mv,off);off+=4
        if code==0:break
        if off+ln>end:break
        out.setdefault(code,[]).append(bytes(mv[off:off+ln]))
        off+=(ln+3)&~3
    return out

def inspect(path,instrument,output_dir):
  print('PARSE',path,flush=True)
  fd=os.open(path,os.O_RDONLY);mm=mmap.mmap(fd,0,access=mmap.ACCESS_READ);mv=memoryview(mm)
  try:
   total=len(mm);ofs=0;eps=[];packets=collections.Counter();interfaces=[];section=0
   tcp_segs=collections.defaultdict(list);flows=collections.Counter();flags=collections.defaultdict(lambda:collections.Counter());all_snaps=[];tcp_edge_events=[]
   errors=[];earliest=None;latest=None;non_tcp=collections.Counter()
   while ofs+12<=total:
    typ=U32(mv,ofs)[0];sz=U32(mv,ofs+4)[0]
    if sz<12 or ofs+sz>total or U32(mv,ofs+sz-4)[0]!=sz:
        errors.append(['bad-block',ofs,hex(typ),sz]);break
    packets[typ]+=1
    if typ==0x0A0D0D0A:
        bom=U32(mv,ofs+8)[0]
        if bom!=0x1A2B3C4D:raise ValueError('big endian unsupported '+hex(bom))
        section+=1
    if typ==1:
        link,snap=struct.unpack_from('<HI',mv,ofs+8)[0], U32(mv,ofs+12)[0]
        opts=option_list(mv,ofs+16,ofs+sz-4)
        name=opts.get(2,[b''])[0].decode('utf8','replace')
        desc=opts.get(3,[b''])[0].decode('utf8','replace')
        res=opts.get(9,[b'\x06'])[0][0]
        factor=1/(2**(res&0x7f) if res&0x80 else 10**res)
        offset=int.from_bytes(opts.get(14,[b'\0'*8])[0],'little',signed=True)
        interfaces.append(dict(linktype=link,snaplen=snap,name=name,description=desc,ts_factor=factor,ts_offset=offset))
    if typ==6:
        ifaceid,thi,tlo,caplen,packetlen=struct.unpack_from('<IIIII',mv,ofs+8)
        if ifaceid>=len(interfaces):errors.append(['unknown-interface',ifaceid]);ofs+=sz;continue
        iface=interfaces[ifaceid]
        start=ofs+28
        if start+caplen>ofs+sz-4:errors.append(['trunc-epb',ofs]);ofs+=sz;continue
        t=((thi<<32)|tlo)*iface['ts_factor']+iface['ts_offset']
        earliest=min(earliest,t) if earliest is not None else t
        latest=max(latest,t) if latest is not None else t
        packet=bytes(mv[start:start+caplen])
        if iface['linktype']==1:
            if len(packet)<14:ofs+=sz;continue
            etype=int.from_bytes(packet[12:14],'big');nip=14
            for _ in range(3):
                if etype in (0x8100,0x88a8,0x9100) and len(packet)>=nip+4:
                    etype=int.from_bytes(packet[nip+2:nip+4],'big');nip+=4
                else:break
            if etype!=0x0800:
                non_tcp['ethertype-'+hex(etype)]+=1;ofs+=sz;continue
        elif iface['linktype']==101:nip=0
        else:non_tcp['linktype-'+str(iface['linktype'])]+=1;ofs+=sz;continue
        if len(packet)<nip+20:ofs+=sz;continue
        vihl=packet[nip];v=vihl>>4;ihl=(vihl&15)*4
        if v!=4 or ihl<20 or len(packet)<nip+ihl:ofs+=sz;continue
        totlen=int.from_bytes(packet[nip+2:nip+4],'big');proto=packet[nip+9]
        ipfrag=int.from_bytes(packet[nip+6:nip+8],'big')
        if ipfrag&0x1fff:
            non_tcp['ip-fragment']+=1;ofs+=sz;continue
        src='.'.join(str(x) for x in packet[nip+12:nip+16]);dst='.'.join(str(x) for x in packet[nip+16:nip+20])
        if proto!=6:non_tcp['IP-proto-'+str(proto)]+=1;ofs+=sz;continue
        toff=nip+ihl
        if len(packet)<toff+20:ofs+=sz;continue
        sport,dport,seq,ack,dofflags,window=struct.unpack_from('!HHIIHH',packet,toff)
        doff=((dofflags>>12)&15)*4;flag=dofflags&0x1ff
        if doff<20 or len(packet)<toff+doff:errors.append(['bad-tcp-offset',ofs]);ofs+=sz;continue
        payload_len=max(0,min(len(packet),nip+totlen)-toff-doff)
        fl=(src,sport,dst,dport);flows[fl]+=1
        for mask,label in [(0x002,'SYN'),(0x010,'ACK'),(0x001,'FIN'),(0x004,'RST'),(0x008,'PSH'),(0x020,'URG'),(0x040,'ECE'),(0x080,'CWR')]:
            if flag&mask:flags[fl][label]+=1
        if flag & (0x2|0x1|0x4):tcp_edge_events.append(dict(t=fmt(t),flow=str(fl),flags=hex(flag),seq=seq,ack=ack,payload_len=payload_len))
        if payload_len:
            payload=bytes(packet[toff+doff:toff+doff+payload_len]);tcp_segs[fl].append((seq,payload,t,flag,ack))
        if len(all_snaps)<12:all_snaps.append(dict(t=t,src=src,sport=sport,dst=dst,dport=dport,flag=hex(flag),seq=seq,ack=ack,payload=payload_len,iface=ifaceid))
    ofs+=sz
   print('BLOCKS',packets,'INTERFACES',interfaces,'errors',errors[:8], 'non_tcp',non_tcp,flush=True)
   result={'filename':str(path),'filesize':total,'sections':section,'blocks':{str(k):v for k,v in packets.items()},'interfaces':interfaces,'first_packet_utc':fmt(earliest),'last_packet_utc':fmt(latest),'frames_errors':errors,'non_tcp':dict(non_tcp),'flow_summaries':[],'tcp_handshake_samples':all_snaps,'tcp_edge_events':tcp_edge_events}
   for flow,ct in flows.items():
      segs=tcp_segs.get(flow,[]);sq=sorted(segs,key=lambda x:x[0]); total_payload=sum(len(s[1]) for s in segs)
      if sq:
          base=sq[0][0];nextseq=base;overlapbytes=0;diffbytes=0;gapbytes=0;unique=0;reconst=bytearray();old=0; overlap_details=[]
          for seq,data,t,flag,ack in sq:
              end=seq+len(data)
              if seq>nextseq:
                  gap=seq-nextseq;gapbytes+=gap
                  # Fill missing with zero to keep alignment; distinguish unverified in report
                  reconst.extend(b'\0'*gap);nextseq=seq
              if seq<nextseq:
                  overlap=min(nextseq-seq,len(data));overlapbytes+=overlap
                  if len(reconst)>=(seq-base+overlap) and seq>=base:
                      old=reconst[seq-base:seq-base+overlap]
                      mismatch=[i for i,(x,y) in enumerate(zip(old,data[:overlap])) if x!=y];diffbytes+=len(mismatch);overlap_details.append(dict(t=fmt(t),tcp_seq=seq,segment_len=len(data),overlap_bytes=overlap,mismatches=[dict(raw_offset=seq-base+i,original=old[i],new=data[i]) for i in mismatch[:30]]))
              newoffset=max(nextseq-seq,0)
              if newoffset<len(data):
                  reconst.extend(data[newoffset:]);nextseq=end;unique+=len(data)-newoffset
          unique=len(reconst)-gapbytes
          dsha=hashlib.sha256(reconst).hexdigest()
          reconstpath=pathlib.Path(output_dir)/(pathlib.Path(path).stem+('_server_stream.raw' if flow[0]==instrument else '_client_stream.raw'))
          if flow[0]==instrument and flow[1]==10230:
              reconstpath.write_bytes(reconst)
          res={'flow':f'{flow[0]}:{flow[1]} -> {flow[2]}:{flow[3]}','packets':ct,'payload_segments':len(segs),'total_payload_bytes':total_payload,'reassembled_bytes_including_gaps':len(reconst),'unique_bytes':unique,'tcp_overlap_bytes':overlapbytes,'conflicting_overlap_bytes':diffbytes,'tcp_gap_bytes':gapbytes,'sha256':dsha,'earliest_payload_utc':fmt(min(s[2] for s in segs)),'latest_payload_utc':fmt(max(s[2] for s in segs)), 'flags':dict(flags[flow]),'overlap_details':overlap_details,'first_seq':base,'last_seq':nextseq}
          result['flow_summaries'].append(res)
      else:
          result['flow_summaries'].append({'flow':f'{flow[0]}:{flow[1]} -> {flow[2]}:{flow[3]}','packets':ct,'payload_segments':0,'total_payload_bytes':0,'flags':dict(flags[flow])})
   reportpath=pathlib.Path(output_dir)/(pathlib.Path(path).stem+'_pcap_audit.json')
   reportpath.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
   print('WRITTEN',reportpath,flush=True)
   print(json.dumps({k:result[k] for k in ['first_packet_utc','last_packet_utc','flow_summaries','tcp_handshake_samples']},ensure_ascii=False,indent=2),flush=True)
   return result
  finally:
   mv.release();mm.close();os.close(fd)

def fmt(t):
    if t is None:return None
    return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat(timespec='microseconds')
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser(description='Offline PCAPNG Ethernet/IPv4/TCP integrity, no networking')
 ap.add_argument('pcapng')
 ap.add_argument('--server-ip', required=True, help='IPv4 address of MVK server for payload reconstruction')
 ap.add_argument('--out-dir', required=True, help='directory to save audit and reconstructed device stream')
 args=ap.parse_args()
 pathlib.Path(args.out_dir).mkdir(parents=True,exist_ok=True)
 inspect(args.pcapng,args.server_ip,args.out_dir)

