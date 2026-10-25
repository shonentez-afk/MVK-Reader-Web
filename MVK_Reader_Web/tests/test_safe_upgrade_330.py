import json,sqlite3,tempfile
from pathlib import Path
from TRANSFER_OLD_DATA import transfer
import pytest

def make(root):
    (root/'collector').mkdir()
    (root/'collector'/'devices.json').write_text(json.dumps({'devices':[{'number':44,'enabled':False,'interval_seconds':None}]}))
    with sqlite3.connect(root/'collector'/'collector.sqlite3') as con:
        con.execute('CREATE TABLE readings (value INTEGER)')
        con.execute('INSERT INTO readings VALUES (123)')

def test_transfer_keeps_data_and_config(tmp_path):
    old=tmp_path/'old';new=tmp_path/'new';old.mkdir();new.mkdir();make(old);(new/'collector').mkdir()
    transfer(old,new)
    with sqlite3.connect(new/'collector'/'collector.sqlite3') as con:
        assert con.execute('SELECT value FROM readings').fetchone()[0]==123
    assert json.loads((new/'collector'/'devices.json').read_text())['devices'][0]['number']==44

def test_refuses_overwrite(tmp_path):
    old=tmp_path/'old';new=tmp_path/'new';old.mkdir();new.mkdir();make(old);make(new)
    with pytest.raises(FileExistsError):transfer(old,new)
    with sqlite3.connect(new/'collector'/'collector.sqlite3') as con:
        assert con.execute('SELECT value FROM readings').fetchone()[0]==123

def test_refuses_enabled_polling(tmp_path):
    old=tmp_path/'old';new=tmp_path/'new';old.mkdir();new.mkdir();make(old);(new/'collector').mkdir()
    c=old/'collector'/'devices.json';j=json.loads(c.read_text());j['devices'][0]['enabled']=True;c.write_text(json.dumps(j))
    with pytest.raises(ValueError):transfer(old,new)
    assert not (new/'collector'/'collector.sqlite3').exists()
