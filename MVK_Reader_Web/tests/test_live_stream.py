"""SSE must never open device socket or alter collector polling policy."""
import asyncio
from collector import service

def test_sse_cache_snapshot_and_no_poll(monkeypatch):
    calls=[]
    monkeypatch.setattr(service.collector,'poll_once',lambda *a,**k: calls.append(a))
    response=asyncio.run(service.events())
    assert response.media_type=='text/event-stream'
    async def one():
        it=response.body_iterator
        value=await anext(it)
        await it.aclose()
        return value
    chunk=asyncio.run(one())
    assert 'event: devices' in chunk
    assert 'data:' in chunk
    assert not calls

def test_polling_still_disabled():
    sample=service.collector.devices['mvk44']
    assert sample['enabled'] is False
    assert sample['interval_seconds'] is None
