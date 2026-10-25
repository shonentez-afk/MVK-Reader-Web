"""Reader UI and read-only Collector on one ASGI server; explicit worker lifespan."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'reader_web'))
from server import app
from collector.service import app as collector_app, lifespan as collector_lifespan

@asynccontextmanager
async def integrated_lifespan(main_app):
    async with collector_lifespan(collector_app):
        yield

app.router.lifespan_context = integrated_lifespan
app.mount('/collector',collector_app)


# Defense in depth: reject any non-loopback HTTP client even when an operator
# accidentally launches Uvicorn with --host 0.0.0.0. Proxy headers are ignored.
# Starlette TestClient uses the non-routable name "testclient" in the ASGI scope.
from starlette.responses import PlainTextResponse
from ipaddress import ip_address

@app.middleware('http')
async def reject_remote_clients(request, call_next):
    host = request.scope.get('client', ('', 0))[0]
    try:
        allowed = ip_address(host).is_loopback
    except ValueError:
        allowed = host == 'testclient'
    if not allowed:
        return PlainTextResponse('Local access only. LAN access requires a separately secured deployment.', status_code=403)
    return await call_next(request)

# v0.3.33 additive read-only ADC interface
from signal_bridge.api import router as signal_router
app.include_router(signal_router)

# v0.3.37 non-mutating device selection API
from mvk_device_selector import router as mvk_router
app.include_router(mvk_router)
