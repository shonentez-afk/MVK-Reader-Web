import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from fastapi.testclient import TestClient
from collector.core import Collector
from collector.scheduler import PollScheduler


def test_integrated_lifespan_clean_shutdown():
    from integrated import app
    from collector import service
    with TestClient(app) as client:
        response=client.get('/collector/api/health')
        assert response.status_code == 200
        assert service.thread is not None and service.thread.is_alive()
    assert service.thread is None or not service.thread.is_alive()


def test_many_cycles_two_devices_no_unrequested_poll():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        conf={'devices':[{'id':n,'number':n,'ip':'127.0.0.1','port':15020,
                          'enabled':True,'read_ranges':[{'address':4096,'count':2}],
                          'interval_seconds':None} for n in ('44','50')]}
        config=root/'devices.json';config.write_text(json.dumps(conf))
        c=Collector(config,root/'db.sqlite3')
        scheduler=PollScheduler(c)
        with patch.object(c,'poll_once',side_effect=AssertionError('unexpected read')):
            for _ in range(1000):
                scheduler.step()
                c.public_devices()
                c.storage_stats()
        assert c.storage_stats()['snapshots']==0
        assert scheduler.status()=={}


def test_scheduler_recovers_independently_for_many_cycles():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        config=root/'devices.json'
        config.write_text(json.dumps({'devices':[{'id':n,'number':n,'ip':'127.0.0.1','port':15020,
             'enabled':True,'read_ranges':[{'address':4096,'count':2}], 'interval_seconds':1}
             for n in ('44','50')]}))
        c=Collector(config,root/'db.sqlite3')
        now=[0.0];s=PollScheduler(c,lambda:now[0]);seen={'44':0,'50':0}
        def fake(device):
            seen[device]+=1
            if device=='44' and seen[device]%3==1:raise OSError('simulated')
        with patch.object(c,'poll_once',side_effect=fake):
            for step in range(300):
                now[0]=float(step);s.step()
        assert seen['50']==300
        assert seen['44']>50
        assert s.status()['50']['consecutive_failures']==0
