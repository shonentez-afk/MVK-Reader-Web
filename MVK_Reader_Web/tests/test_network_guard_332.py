from fastapi.testclient import TestClient
from integrated import app

def test_remote_client_denied_even_for_health():
    # Force an ASGI client address: protection must not trust HTTP forwarding headers.
    async def request(scope, receive, send):
        scope['client']=('10.80.12.34', 40000)
        await app(scope,receive,send)
    from httpx import ASGITransport, AsyncClient
    import asyncio
    async def run():
        async with AsyncClient(transport=ASGITransport(app=request),base_url='http://example.test') as c:
            for path in ['/','/collector/api/health','/api/recordings']:
                r=await c.get(path,headers={'X-Forwarded-For':'127.0.0.1'})
                assert r.status_code==403,(path,r.status_code)
    asyncio.run(run())

def test_loopback_and_testclient_allowed():
    with TestClient(app) as c:
        assert c.get('/api/health').status_code==200
        assert c.get('/collector/api/health').status_code==200
