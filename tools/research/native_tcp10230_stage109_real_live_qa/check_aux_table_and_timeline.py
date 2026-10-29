import sys,csv,json,datetime,statistics
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2]);exp=root/'BIN_TSXML_VALUES_TABLE_RECONSTRUCTED'
def readcsv(name):
 with (exp/name).open(encoding='cp1251',newline='') as f:return list(csv.reader(f,delimiter='|'))
t=readcsv('TABLE_LAST_AUX_RECONSTRUCTED.csv');v=readcsv('VALUES_ALL_ADC_RECONSTRUCTED.csv')
audit=json.loads((exp/'EXPORT_AUDIT.json').read_text())
assert len(t)==40 and len(v)==3+audit['aux4700_updates'] and len(v[-1])==585
m=[]
for row in range(30):
 n=43+row
 for ch in range(8):
  a=t[2+row][1+ch]
  b=v[-1][1+73*ch+n]
  if a!=b:m.append((row,ch+1,a,b))
updates=json.loads((exp/'TIMELINE.json').read_text())
ts=[datetime.datetime.fromisoformat(x['tick_received_utc'].replace('Z','+00:00')).timestamp() for x in updates]
intervals=[b-a for a,b in zip(ts[:-1],ts[1:])]
status_counts={}
for ch in range(8):
 fields=[r[1+73*ch+45] for r in v[3:]]
 status_counts[str(ch+1)]={s:fields.count(s) for s in sorted(set(fields))}
result={'table_compared_to_last_aux_values':240,'table_mismatch_count':len(m),'table_mismatch_examples':m[:12],'values_rows':len(v)-3,'values_columns':len(v[-1]),'table_rows':len(t)-1,'update_intervals_seconds':{'n':len(intervals),'mean':round(statistics.mean(intervals),6),'min':round(min(intervals),6),'max':round(max(intervals),6),'stdev':round(statistics.stdev(intervals),6)},'sensor_status_rows':status_counts}
print(json.dumps(result,ensure_ascii=False,indent=2))
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
assert not m
