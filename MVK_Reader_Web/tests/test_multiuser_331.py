import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]

def test_local_concurrent_read_only_http(tmp_path):
    import subprocess, os, sys
    script="""from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor
from integrated import app
paths=['/api/health','/collector/api/health','/collector/api/devices','/collector/api/storage-diagnostics','/api/recordings']
with TestClient(app) as client:
 def get(i):
  p=paths[i%len(paths)]
  return (p,client.get(p).status_code)
 with ThreadPoolExecutor(max_workers=8) as pool:
  results=list(pool.map(get,range(40)))
 assert all(code==200 for _,code in results),results
"""
    env=dict(os.environ,MVK_DATA_DIR=str(tmp_path/'archive'))
    env['PYTHONPATH']=str(ROOT)+os.pathsep+str(ROOT/'reader_web')
    proc=subprocess.run([sys.executable,'-c',script],env=env,cwd=ROOT,capture_output=True,text=True,timeout=25)
    assert proc.returncode==0,proc.stdout+proc.stderr

def test_safe_launch_remains_loopback_only():
    launcher=(ROOT/'START_READER.py').read_text(encoding='utf-8')
    assert "host='127.0.0.1'" in launcher
    assert '0.0.0.0' not in launcher

def test_multiuser_tool_uses_safe_get_only():
    source=(ROOT/'VERIFY_MULTIUSER.py').read_text(encoding='utf-8')
    assert 'urlopen' in source
    assert 'Request(' not in source
    assert "'/collector/api/storage-diagnostics'" in source
