import json, sqlite3, tempfile
from pathlib import Path
from unittest.mock import patch
from collector.core import Collector

def build(tmp):
    root=Path(tmp)
    (root/'devices.json').write_text(json.dumps({'devices':[{'id':'44','number':'44','ip':'127.0.0.1','port':502,'enabled':False,'read_ranges':[],'interval_seconds':None}]}))
    return Collector(root/'devices.json',root/'collector.sqlite3')

def test_backup_is_valid_and_read_only_for_instrument():
    with tempfile.TemporaryDirectory() as td:
        c=build(td)
        with c._connect() as db:
            db.execute('INSERT INTO events(device_id,at,status,detail) VALUES (?,?,?,?)',('44','2026-10-22T00:00:00+00:00','test','ok'))
        with patch('collector.core.modbus_read',side_effect=AssertionError('No device calls permitted')):
            result=c.backup_sqlite(Path(td)/'backup.sqlite3')
            assert result['integrity']=='ok'
            assert c.storage_stats()['events']==1
            assert c.connection_stats()['scheduled_devices']==0
        with sqlite3.connect(Path(td)/'backup.sqlite3') as db:
            assert db.execute('SELECT COUNT(*) FROM events').fetchone()[0]==1
            assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'

def test_backup_never_overwrites_existing_file_or_live_database():
    with tempfile.TemporaryDirectory() as td:
        c=build(td)
        try:c.backup_sqlite(c.database)
        except ValueError:pass
        else:raise AssertionError('Live db overwritten')
        p=Path(td)/'copy.sqlite3';p.write_bytes(b'KEEP')
        try:c.backup_sqlite(p)
        except FileExistsError:pass
        else:raise AssertionError('Overwrote previous backup')
        assert p.read_bytes()==b'KEEP'
