#!/usr/bin/env python3
"""Independent byte-level check of Stage107 outputs against ORIGINAL Native R5/R5.1 RAW.
Offline and read-only; uses numpy for vectorized whole-record comparisons.
Run: python verify_export_independent.py <incoming.raw> <EXPORT_DIRECTORY> --report <output.json>
"""
import argparse,collections,csv,hashlib,json,math,pathlib,struct,sys,xml.etree.ElementTree as ET
import numpy as np

P=argparse.ArgumentParser();P.add_argument('raw');P.add_argument('export');P.add_argument('--report');a=P.parse_args()
out=pathlib.Path(a.export); rep=json.loads((out/'EXPORT_AUDIT.json').read_text(encoding='utf-8'))
raw=pathlib.Path(a.raw).read_bytes()
source_sha=hashlib.sha256(raw).hexdigest()
assert source_sha==rep['source_raw_sha256']
frames=collections.Counter();adc=[bytearray() for _ in range(8)]; aux=[]; statuses=[collections.Counter() for _ in range(8)]
pos=0
tail=rep.get('ignored_incomplete_terminal_frame_bytes', 0)
assert isinstance(tail, int) and 0 <= tail < 32800
while pos<len(raw)-tail:
 assert pos+8<=len(raw)
 typ,length=struct.unpack_from('<II',raw,pos)
 assert length>=8 and length%4==0 and pos+length<=len(raw)
 frames[(typ,length)]+=1
 if typ==0xFF800ADC:
  assert length==1052
  _,seq,_,c,fs=struct.unpack_from('<5I',raw,pos+8)
  assert c<8 and fs==65536
  adc[c].extend(raw[pos+28:pos+1052])
 if typ==0xFF800C0D and length==4700:
  cnt=struct.unpack_from('<I',raw,pos+24)[0];assert cnt==8
  cursor=pos+28;rows=[]
  for ch in range(8):
   desc,=struct.unpack_from('<I',raw,cursor);cursor+=4
   addr,words=desc&0xffff,desc>>16
   assert addr==0x2000+ch*0x200 and words==0x122
   buf=memoryview(raw)[cursor:cursor+words*2];cursor+=words*2
   f=lambda off:struct.unpack_from('<f',buf,off*2)[0]
   u=lambda off:struct.unpack_from('<I',buf,off*2)[0]
   status=u(0x120); statuses[ch][status&0xC00]+=1
   rows.append([*[f(2+2*k) for k in range(43)], f(0),f(0x5e),f(0x5c),*[f(0x60+2*k) for k in range(24)]])
  assert cursor==pos+length
  aux.append(rows)
 pos+=length
assert pos==len(raw)-tail, (pos,len(raw))
if tail:
 assert pos+8<=len(raw)
 typ,declared=struct.unpack_from('<II',raw,pos)
 assert declared>tail>=8 and typ in (0xFF800ADC,0xFF8001AC,0xFF800C0D), (typ,declared,tail)
assert len(aux)==rep['aux4700_updates']
mismatches=[];sums=[];num_compared=0
for ch,info in enumerate(rep['channels']):
 buf=np.frombuffer(adc[ch],dtype='<f4')
 assert len(buf)==info['samples']==info['frames']*256,(ch,len(buf),info)
 # float32 gain from frame snapshot (not from rounded TSXML)
 gain=struct.unpack_from('<f',raw,836+ch*512)[0]
 assert struct.pack('<f',gain)==struct.pack('<f',info['gain'])
 expected=(buf.astype('float64')*float(gain)).astype('<f4')
 dest=out/info['bin_filename']
 actual=np.fromfile(dest,dtype='<f4')
 if len(expected)!=len(actual):mismatches.append(('length',ch,len(expected),len(actual)))
 else:
  ok=expected.view('u4')==actual.view('u4')
  nbad=int((~ok).sum());num_compared+=len(ok)
  if nbad:
   positions=np.nonzero(~ok)[0][:6]
   mismatches.append(('samples',ch,nbad,[int(x) for x in positions]))
 xml=ET.fromstring((out/(info['bin_filename']+'.tsxml')).read_bytes())
 assert xml.findtext('FrequencyPerChannel')=='65536'
 assert xml.findtext('ChannelsQuantity')=='1'
 assert xml.findtext('./Channels/Channel/ChannelNumber')==str(ch+1)
 assert xml.findtext('./Channels/Channel/DataLength')==str(len(buf)*4)
 assert abs(float(xml.findtext('To'))-len(buf)*1000/65536)<=0.0051
 assert xml.findtext('./Channels/Channel/Units')=='м/с2'
 assert sum(info['sensor_status_counts'].values())==len(aux)
 sums.append({'adc':ch+1,'samples_compared':len(buf),'byte_exact':nbad==0,'computed_bin_sha256':hashlib.sha256(expected.tobytes()).hexdigest(), 'actual_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(), 'status_counts':dict(statuses[ch])})
 # both hash values computed independently
 assert sums[-1]['computed_bin_sha256']==sums[-1]['actual_sha256']==info['bin_sha256']
# compare user-visible recovered VALUES values to independent register decoder with 4-digit original-style numeric rounding
with (out/'VALUES_ALL_ADC_RECONSTRUCTED.csv').open(encoding='cp1251',newline='') as f: v=list(csv.reader(f,delimiter='|'))
assert v[0][0]=='sep=' and len(v)==3+len(aux) and all(len(row)==585 for row in v[1:])
for i,sample in enumerate(aux):
 for ch,vals in enumerate(sample):
  fields=v[3+i][1+73*ch:1+73*(ch+1)]
  assert len(fields)==73
  actuals=fields[:43]+[fields[46],fields[47],fields[48]]+fields[49:]
  assert len(actuals)==len(vals)==70
  for j,(x,text) in enumerate(zip(vals,actuals)):
   f=float(text.replace(',','.'))
   # 4 significant decimal places, with a small margin for Go representation
   if abs(x-f)>max(abs(x)*0.00052,1e-12):
    mismatches.append(('VALUES',i,ch,j,x,text))
   num_compared+=1
result={'source_sha256':source_sha,'decoded_frames':sum(frames.values()),'samples_and_values_compared':num_compared,'channels':sums,'aux_updates':len(aux),'values_rows':len(v)-3,'mismatches':mismatches[:30], 'total_mismatches':len(mismatches), 'checks':'full float32-bit comparison of every ADC sample, 4-digit CSV rounding vs independently decoded AUX registers, TSXML schema/length/gain'}
if a.report:pathlib.Path(a.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'samples_and_values_compared':num_compared,'aux_updates':len(aux),'mismatches':len(mismatches),'per_adc_samples':[s['samples_compared'] for s in sums]},ensure_ascii=False))
sys.exit(0 if not mismatches else 1)
