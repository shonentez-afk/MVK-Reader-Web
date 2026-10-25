import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from collector.core import Collector
from collector.scheduler import PollScheduler

class Clock:
    def __init__(self):self.t=100.0
    def __call__(self):return self.t
    def advance(self,n):self.t+=n

def make_collector(root):
    config={'devices':[{'id':'mvk44','number':'44','ip':'127.0.0.1','port':15020,
        'enabled':True,'read_ranges':[{'address':4096,'count':2}], 'interval_seconds':10},
        {'id':'mvk50','number':'50','ip':'127.0.0.1','port':15021,
        'enabled':True,'read_ranges':[{'address':4096,'count':2}], 'interval_seconds':10}]}
    path=root/'devices.json';path.write_text(json.dumps(config))
    return Collector(path,root/'db.sqlite3')

def test_backoff_after_error_then_recovery_no_extra_calls():
    with tempfile.TemporaryDirectory() as tmp:
        c=make_collector(Path(tmp)); clock=Clock(); scheduler=PollScheduler(c,clock)
        calls=[]
        def fake(device):
            calls.append((device,clock.t))
            if device=='mvk44' and len([x for x in calls if x[0]=='mvk44'])==1:
                raise OSError('simulated disconnect')
        with patch.object(c,'poll_once',side_effect=fake):
            scheduler.step()
            assert len(calls)==2
            assert scheduler.status()['mvk44']['consecutive_failures']==1
            assert scheduler.status()['mvk50']['state']=='ok'
            clock.advance(10);scheduler.step()
            assert [x[0] for x in calls].count('mvk44')==1
            assert [x[0] for x in calls].count('mvk50')==2
            clock.advance(10);scheduler.step()
            assert [x[0] for x in calls].count('mvk44')==2
            assert scheduler.status()['mvk44']['consecutive_failures']==0


def test_no_interval_no_poll_and_disable_removes_schedule():
    with tempfile.TemporaryDirectory() as tmp:
        c=make_collector(Path(tmp));clock=Clock(); scheduler=PollScheduler(c,clock)
        with c.lock:c.devices['mvk44']['interval_seconds']=None;c.devices['mvk50']['enabled']=False
        with patch.object(c,'poll_once',side_effect=AssertionError('No polling allowed')):
            scheduler.step();clock.advance(999);scheduler.step()
        assert scheduler.status()=={}


def test_read_only_core_no_write_modbus_operations():
    import inspect
    from collector.core import modbus_read
    assert "struct.pack('>HHHBBHH',tid,0,6,1,3,address,count)" in inspect.getsource(modbus_read)
