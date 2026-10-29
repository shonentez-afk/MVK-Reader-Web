#!/usr/bin/env python3
"""Independent read-only integrity of frames/chunks/ZIP/audit for saved R6.1 run.
No network, no live device access. Not a substitute for matching original MVKView export.
"""
from pathlib import Path
import sys,json,csv,hashlib,struct,zipfile,collections,re,datetime
from xml.etree import ElementTree

root=Path(sys.argv[1]); out=Path(sys.argv[2]); raw_path=root/'incoming.raw'; exp=root/'BIN_TSXML_VALUES_TABLE_RECONSTRUCTED'
raw=raw_path.read_bytes(); m=memoryview(raw); rep=json.loads((exp/'EXPORT_AUDIT.json').read_text()); summary=json.loads((root/'summary.json').read_text()); status=json.loads((root/'STAGE108_EXPORT_STATUS.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
errors=[]; checked=0
if sha(raw)!=summary['raw_sha256'] or sha(raw)!=rep['source_raw_sha256'] or sha(raw)!=status['source_raw_sha256']: errors.append('RAW hash across reports')
frame_index=0; frames=collections.Counter(); ch_seq=[None]*8; adcs=[0]*8; tailsz=summary['incomplete_final_frame_bytes']; pos=0
with (root/'frames.csv').open(newline='',encoding='utf-8') as f:
 rows=csv.DictReader(f)
 for r in rows:
  frame_index+=1
  if int(r['frame_index'])!=frame_index: errors.append('frame_index'+str(frame_index))
  if pos+8>len(raw): errors.append('truncated header');break
  typ,length=struct.unpack_from('<II',m,pos)
  typ_text='0x%08X'%typ
  if typ_text!=r['type_hex'] or length!=int(r['length']): errors.append('frame type/size idx '+str(frame_index))
  if length < 8 or pos+length>len(raw): errors.append('truncated frame idx '+str(frame_index));break
  frames[f'{typ:08X}/{length}']+=1
  if typ==0xFF800ADC:
   seq=struct.unpack_from('<I',m,pos+12)[0];ch=struct.unpack_from('<I',m,pos+20)[0];rate=struct.unpack_from('<I',m,pos+24)[0]
   if ch>=8: errors.append('invalid adc channel')
   else:
    if seq != int(r['sequence_index']) or ch+1!=int(r['channel']) or rate!=int(r['rate_hz']):errors.append('ADC header mismatch idx '+str(frame_index))
    if ch_seq[ch] is not None and seq!=ch_seq[ch]+256:errors.append('ADC sample gap ch '+str(ch))
    ch_seq[ch]=seq;adcs[ch]+=256
  pos+=length
  checked+=1
if frame_index != summary['frames_decoded'] or pos != len(raw)-tailsz:errors.append('frame counts/terminal tail mismatch')
if frames.get('FF800ADC/1052')!=summary['frame_counts'].get('FF800ADC/1052'):errors.append('ADC frames mismatch')
# chunks cover exact RAW (checks repeated offsets, missing chunks, size)
rows=0; chunk_pos=0
with (root/'chunks.csv').open(newline='',encoding='utf-8') as f:
 for r in csv.DictReader(f):
  if int(r['raw_offset_bytes'])!=chunk_pos:errors.append('chunk discontinuity at '+str(rows))
  chunk_pos+=int(r['bytes']);rows+=1
if chunk_pos!=len(raw) or rows!=summary['tcp_read_chunks']:errors.append('chunks coverage mismatch')
# all physical file checks including meta files
hash_files=0; hash_fail=[]
for name,expected in rep['output_file_sha256'].items():
 p=exp/name
 if not p.exists() or sha(p.read_bytes())!=expected:hash_fail.append(name)
 else:hash_files+=1
if hash_fail:errors.append('output hashes:'+str(hash_fail))
# no lingering temp files, all bins xml files present
pending=list(root.rglob('*.partial'))
if pending:errors.append('partial files left')
with zipfile.ZipFile(root/'MVK10230_TEST_RESULTS.zip') as z:
 zip_fail=z.testzip();zi={'compressed_bytes':(root/'MVK10230_TEST_RESULTS.zip').stat().st_size, 'entry_count':len(z.infolist()),'crc_error_file':zip_fail,'names':z.namelist()[:25]}
 if zip_fail:errors.append('diagnostic ZIP CRC failed')
# trailing incomplete ADC header + PCAP completion where available
terminal=dict(excluded= tailsz,raw_bytes=len(raw),complete_prefix_bytes=pos,trailing_hex=bytes(m[pos:pos+28]).hex(' '))
if len(raw)-pos>=28:
 tp,tl=struct.unpack_from('<II',m,pos)
 terminal.update(partial_type=hex(tp),partial_len_declared=tl)
 if tp==0xFF800ADC and len(raw)-pos>=28:
  terminal.update(adc_index=struct.unpack_from('<I',m,pos+12)[0],adc_channel=struct.unpack_from('<I',m,pos+20)[0]+1)
print(json.dumps({'frame_rows_checked':checked,'adc_samples':adcs,'chunk_rows':rows,'raw_integrity_checked':True,'output_hashes_checked':hash_files,'errors':errors,'trailing':terminal,'results_zip':zi},ensure_ascii=False,indent=2)[:8000])
result={'frame_rows_checked':checked,'decoded_types':dict(frames),'adc_samples':adcs,'chunk_rows_checked':rows,'raw_size':len(raw),'raw_sha256':sha(raw),'raw_integrity_ok':not errors,'output_hashes_checked':hash_files,'pending_files':len(pending),'errors':errors,'terminal_frame':terminal,'results_zip':zi}
out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
if errors:sys.exit(2)
