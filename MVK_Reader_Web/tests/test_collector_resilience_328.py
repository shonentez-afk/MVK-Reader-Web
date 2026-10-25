import json,sqlite3,threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from collector.core import Collector

def make_collector(tmp_path):
    conf=tmp_path/'devices.json'
    conf.write_text(json.dumps({'devices':[{'id':'MVK44','ip':'127.0.0.1','port':502,'enabled':False,'interval_seconds':None}]}))
    return Collector(conf,tmp_path/'live.sqlite3')

def test_concurrent_readers_and_online_backup(tmp_path):
    c=make_collector(tmp_path)
    with c._connect() as db:
        db.executemany('INSERT INTO measurements(device_id,received_at,channel_type,channel,metric,band,value,unit,source) VALUES (?,?,?,?,?,?,?,?,?)',
            [('MVK44',f'2026-01-01T00:{i//60:02}:{i%60:02}Z','ADC',1,'rms','',float(i),'mm/s','test') for i in range(500)])
    def read(_): return c.series_range('MVK44','ADC',1,'rms',limit=1000)['total']
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs=[pool.submit(read,i) for i in range(24)]
        backup=pool.submit(c.backup_sqlite,tmp_path/'backup.sqlite3')
        assert all(f.result()==500 for f in jobs)
        assert backup.result()['integrity']=='ok'
    with sqlite3.connect(tmp_path/'backup.sqlite3') as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0]==500

def test_backup_nonoverwrite_and_cleanup(tmp_path,monkeypatch):
    c=make_collector(tmp_path)
    dest=tmp_path/'backup.sqlite3'
    assert c.backup_sqlite(dest)['integrity']=='ok'
    original=dest.read_bytes()
    with pytest.raises(FileExistsError): c.backup_sqlite(dest)
    assert dest.read_bytes()==original
    assert not list(tmp_path.glob('*.partial'))
    with pytest.raises(ValueError):c.backup_sqlite(c.database)

def test_partial_collision(tmp_path):
    c=make_collector(tmp_path)
    (tmp_path/'a.sqlite3.partial').write_text('other backup is running')
    with pytest.raises(FileExistsError):c.backup_sqlite(tmp_path/'a.sqlite3')
    assert not (tmp_path/'a.sqlite3').exists()
