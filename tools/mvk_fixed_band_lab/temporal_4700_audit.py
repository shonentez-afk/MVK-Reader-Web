"""Offline 4700 vs trailing 2-second ADC window, sampling every 5th 4700 frame.
Run from tools/mvk_fixed_band_lab; accepts PCAPNG paths. Not clock-aligned proof.
Requires numpy scipy. Private captures stay local.
"""
import sys,struct,csv
from pathlib import Path
import numpy as np
from instrument_reconstructed_v3 import predict

def packets(path):
 with open(path,"rb") as h:
  while q:=h.read(8):
   typ,n=struct.unpack("<II",q)
   if not 12<=n<=20000000:raise ValueError("PCAP block length")
   b=h.read(n-8)
   if len(b)!=n-8:break
   if typ!=6 or len(b)<20:continue
   l=struct.unpack_from("<I",b,12)[0]
   p=b[20:20+l]
   if len(p)<54 or p[12:14]!=b"\\x08\\x00":continue
   ip=p[14:];ihl=(ip[0]&15)*4
   if ip[9]!=6:continue
   tcp=ip[ihl:]
   if len(tcp)<20 or struct.unpack_from("!H",tcp)[0]!=10230:continue
   th=(tcp[12]>>4)*4
   length=struct.unpack_from("!H",ip,2)[0]-ihl-th
   if length>0:yield struct.unpack_from("!I",tcp,4)[0],tcp[th:th+length]

def stream(path):
 pieces=list(packets(path))
 first=pieces[0][0];unique={}
 for seq,blob in pieces:
  idx=(seq-first)&0xffffffff
  if idx<0x80000000:unique.setdefault(idx,blob)
 out=bytearray();gaps=[]
 for i,b in sorted(unique.items()):
  if i>len(out):gaps.append([len(out),i]);out.extend(bytes(i-len(out)))
  if i+len(b)>len(out):out.extend(b[max(0,len(out)-i):])
 return out,gaps

def audit(path):
 buf,gaps=stream(path);j=buf.find(b"VAST_MVK")-24
 if j<0:raise ValueError("VAST_MVK not found")
 gain=[struct.unpack_from("<f",buf,j+836+i*512)[0] for i in range(8)]
 chunks=[[] for _ in range(8)];markers=[];pos=j+33064
 while pos+8<=len(buf):
  marker,n=struct.unpack_from("<II",buf,pos)
  if n<8 or n>100000 or pos+n>len(buf):break
  if marker==0xff800adc and n==1052:
   ch=struct.unpack_from("<I",buf,pos+20)[0]
   if ch<8:chunks[ch].append(np.frombuffer(buf,dtype="<f4",count=256,offset=pos+28).copy())
  elif marker==0xff800c0d and n==4700:
   if len(markers)%5==0:
    markers.append((len(markers),[len(a)*256 for a in chunks],
      [struct.unpack_from("<f",buf,pos+28+584*c+4+48*4)[0] for c in range(8)]))
   else:markers.append(None)
  pos+=n
 samples=[np.concatenate(c).astype(float)*gain[i] for i,c in enumerate(chunks)]
 rows=[]
 for ident,rec in enumerate(markers):
  if rec is None:continue
  _,counts,reference=rec
  for ch in range(8):
   end=counts[ch];start=end-131072
   if start<0:continue
   m=predict(samples[ch][start:end])["10-3000"];v=reference[ch]
   rows.append({"file":Path(path).name,"calc_index":ident,"adc":ch+1,
                "model":m,"instrument":v,"error_pct":100*(m/v-1) if v>0 else "",
                "tcp_gaps":len(gaps),"window_s":2})
 return rows

if __name__=="__main__":
 rows=[r for p in sys.argv[1:] for r in audit(p)]
 with open("temporal_4700_rows.csv","w",newline="") as h:
  w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(len(rows),"comparison rows")
