#!/usr/bin/env python3
"""Offline same-measurement spectral CSV comparison; no interpolation or calibration fitting."""
import argparse,csv,json,math
from pathlib import Path
def load(p,f,v):
 with open(p,encoding='utf-8-sig',newline='') as handle:
  reader=csv.DictReader(handle)
  if not reader.fieldnames or f not in reader.fieldnames or v not in reader.fieldnames: raise ValueError('required columns missing')
  rows=[(float(x[f]),float(x[v])) for x in reader]
 if not rows or any(not(math.isfinite(x) and math.isfinite(y)) or x<0 for x,y in rows): raise ValueError('invalid values')
 if any(rows[i][0]>=rows[i+1][0] for i in range(len(rows)-1)): raise ValueError('frequency grid must increase')
 return rows
def compare(c,r,eps=1e-6,floor=1e-9):
 if len(c)!=len(r) or any(abs(a[0]-b[0])>eps for a,b in zip(c,r)):
  raise ValueError('frequency grids differ: no interpolation allowed')
 diff=[a[1]-b[1] for a,b in zip(c,r)]
 rel=[100*(a[1]-b[1])/abs(b[1]) for a,b in zip(c,r) if abs(b[1])>floor]
 ic=max(range(len(c)),key=lambda i:c[i][1])
 ir=max(range(len(r)),key=lambda i:r[i][1])
 return {'bins':len(c),'max_abs_error':max(map(abs,diff)),
 'mean_abs_error':sum(map(abs,diff))/len(diff),
 'max_abs_relative_error_percent':max(map(abs,rel)) if rel else None,
 'relative_error_bins':len(rel),'candidate_peak':list(c[ic]),'reference_peak':list(r[ir]),
 'peak_frequency_difference_hz':c[ic][0]-r[ir][0],
 'peak_value_difference':c[ic][1]-r[ir][1]}
def main():
 p=argparse.ArgumentParser()
 for name in ('candidate','reference','manifest','out'): p.add_argument('--'+name,required=True,type=Path)
 p.add_argument('--candidate-column',default='linear_candidate')
 p.add_argument('--reference-column',required=True)
 p.add_argument('--candidate-frequency-column',default='frequency_hz')
 p.add_argument('--reference-frequency-column',default='frequency_hz')
 p.add_argument('--grid-tolerance',type=float,default=1e-6)
 p.add_argument('--relative-floor',type=float,default=1e-9)
 a=p.parse_args()
 meta=json.loads(a.manifest.read_text(encoding='utf-8'))
 needed=('channel','source','time_range','n_fft','window','units','spectrum_mode','same_measurement_confirmed')
 if any(k not in meta for k in needed): raise ValueError('manifest incomplete')
 if meta['same_measurement_confirmed'] is not True: raise ValueError('not confirmed same measurement')
 if a.grid_tolerance<0 or a.relative_floor<0:raise ValueError('negative tolerance')
 c=load(a.candidate,a.candidate_frequency_column,a.candidate_column)
 r=load(a.reference,a.reference_frequency_column,a.reference_column)
 result={'status':'METRICS_ONLY_NOT_NUMERICAL_EQUIVALENCE_PROOF','provenance':meta,
 'metrics':compare(c,r,a.grid_tolerance,a.relative_floor)}
 a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
