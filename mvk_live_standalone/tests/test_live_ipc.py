"""LocalIPC contract tests: real loopback HTTP, no instrument socket."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

import numpy as np
import pytest

from mvk_live_standalone.live_ipc import (
    SCHEMA, NAME, DOMAIN, LocalIPC, IPCNotReady, discover_local_ipc,
)


def test_verified_calibrated_ipc_and_header_integrity():
    data=np.arange(256,dtype="<f4").tobytes()
    expected_hash=hashlib.sha256(data).hexdigest()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Authorization")!="Bearer "+"a"*64:
                self.send_response(401);self.end_headers();return
            assert self.path=="/v1/adc/2/window?count=256"
            self.send_response(200)
            for key,value in {
                "Content-Type":"application/octet-stream",
                "Content-Length":str(len(data)),
                "X-MVK-Schema":SCHEMA,"X-MVK-Session":"TEST_SESS",
                "X-MVK-Domain":DOMAIN,"X-MVK-ADC":"2",
                "X-MVK-Count":"256","X-MVK-Rate":"65536",
                "X-MVK-RxPos":"512","X-MVK-NextIndex":"4096",
                "X-MVK-Available":"256","X-MVK-FirstReadable":"256",
                "X-MVK-SHA256":expected_hash,
            }.items():
                self.send_header(key,value)
            self.end_headers()
            self.wfile.write(data)
        def log_message(self,*args):
            return

    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    task=threading.Thread(target=server.serve_forever,daemon=True)
    task.start()
    try:
        client=LocalIPC(server.server_port,"a"*64,"TEST_SESS")
        response=client.read_channel(2,256)
        assert response.input_domain==DOMAIN
        assert response.channels[2].captured_samples==512
        assert response.channels[2].next_index==4096
        np.testing.assert_array_equal(response.channels[2].samples,np.arange(256))
        with pytest.raises(ValueError,match="401"):
            LocalIPC(server.server_port,"b"*64,"TEST_SESS").read_channel(2,256)
        with pytest.raises(ValueError,match="Invalid"):
            client.read_channel(0,256)
        with pytest.raises(ValueError,match="Invalid"):
            client.read_channel(2,262145)
    finally:
        server.shutdown()
        server.server_close()
        task.join(timeout=1)


def test_no_untrusted_host_or_session_in_descriptor(tmp_path):
    root=tmp_path/"GUI_ROOT"
    run=root/"TEST_2026-11-17_00-00-00.000"
    run.mkdir(parents=True)
    status={
        "phase":"RECORDING","run_directory":str(run),
        "session_id":run.name,"capture_only":False,"invalid_frames":0,
        "read_only_no_app_payload_sent":True,
    }
    assert discover_local_ipc(root,status) is None
    descriptor={
        "schema":SCHEMA,"session_id":run.name,"host":"127.0.0.1",
        "port":12345,"token":"f"*64,"read_only":True,
        "source_domain":DOMAIN,"max_window_samples":262144,
    }
    file=run/NAME
    file.write_text(json.dumps(descriptor),encoding="utf-8")
    client=discover_local_ipc(root,status)
    assert client.port==12345 and client.session_id==run.name
    descriptor["host"]="192.168.1.10"
    file.write_text(json.dumps(descriptor),encoding="utf-8")
    with pytest.raises(ValueError,match="Unrecognized"):
        discover_local_ipc(root,status)
    descriptor["host"]="127.0.0.1"
    descriptor["session_id"]="other-run"
    file.write_text(json.dumps(descriptor),encoding="utf-8")
    with pytest.raises(ValueError,match="Unrecognized"):
        discover_local_ipc(root,status)
    file.unlink()
    status["capture_only"]=True
    assert discover_local_ipc(root,status) is None


def test_no_redirect_proxies_or_non_loopback_connection():
    # http.client.HTTPConnection is constructed with literal loopback host;
    # no requests/urllib proxy configuration or redirects are used.
    import inspect
    from mvk_live_standalone import live_ipc
    code=inspect.getsource(live_ipc.LocalIPC.read_channel)
    assert 'HTTPConnection("127.0.0.1"' in code
    assert "requests.get" not in code and "urlopen" not in code
