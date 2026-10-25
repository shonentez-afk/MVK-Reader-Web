"""Read-only local preflight. Never opens connection to instruments."""
import sys,json,importlib,sqlite3
from pathlib import Path
print('Python:',sys.version.split()[0]); print('Interpreter:',sys.executable)
for module in ('fastapi','uvicorn','numpy','scipy','openpyxl','reportlab','httpx','multipart'):
 try: m=importlib.import_module(module); print('OK',module,getattr(m,'__version__',''))
 except Exception as e:print('MISSING',module,repr(e))
config=json.loads((Path(__file__).parent/'collector'/'devices.json').read_text(encoding='utf-8'))
for d in config['devices']:
 safe=(not d.get('enabled',False)) and d.get('interval_seconds') is None
 print('Device',d['number'],'safe_disabled=',safe)
 if not safe:raise SystemExit('UNSAFE: device config enables polling')
try:
 from integrated import app
 from fastapi.testclient import TestClient
 with TestClient(app) as c:
  for path in ('/','/api/health','/api/recordings','/collector/api/health','/collector/api/devices','/collector/api/server-status'):
   r=c.get(path);print('HTTP',r.status_code,path);assert r.status_code==200
 print('PREFLIGHT PASSED')
except Exception as exc:
 print('PREFLIGHT FAILED:',repr(exc));raise
