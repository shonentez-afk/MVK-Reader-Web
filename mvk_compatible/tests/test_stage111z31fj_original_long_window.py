"""Go 2M ring long selection -> SHA-bound Python GetSignal, all offline."""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import json
import zipfile

import numpy as np
import pytest

from mvk_compatible.core.original_source_long_window import (
    REQUEST_NAME,RESULT_NAME,RESULT_SCHEMA,
    submit_source_long_window,load_source_long_window,
)
from mvk_compatible.core.native_r6_live_preview import provisional_waveform
from mvk_compatible.core.original_source_ring_receipt import BUFFER_ELEMENTS


def long_source_status(tmp_path):
    count=65536*20
    run=tmp_path/"TEST_2026-11-17_12-00-00.000"
    run.mkdir()
    rows=[]
    chans=[]
    for i in range(10):
        adc=i<8
        samples=count if i==0 else 0
        chans.append(dict(channel=i+1,type="ADC" if adc else "TACH",
            samples=samples,frames=samples//256,
            sample_rates_hz=[65536] if samples else [],
            sequence_discontinuities=0,nonfinite_samples=0,
            next_sample_index=4096 if i==0 else None))
        rows.append(dict(channel=i+1,sample_width_bytes=4 if adc else 1,
            rx_pos_64=samples,valid_pos_64=0,
            first_readable_pos_64=0,available_elements=samples,
            last_sample_rate_hz=65536 if samples else 0,
            next_device_sample_index=4096 if i==0 else None,
            input_domain="CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32" if samples else "",
            sequence_gaps=0,rate_changes=0,rejected_nonfinite_frames=0))
    status=dict(phase="RECORDING",capture_only=False,invalid_frames=0,
        source_tcp_multi_socket=False,
        source_rate_transition_during_live=False,
        snapshot_stale=False,source_original_storage_verified=True,
        source_original_storage=dict(buffer_elements_per_channel=BUFFER_ELEMENTS,
                                     channels=rows),
        seconds_since_last_packet=0.5,
        run_directory=str(run),session_id=run.name,
        raw_bytes=50_000_000,frames_decoded=5000,channels=chans)
    return run,status


def response_fixture(run,status,request,*,sha_override=None,
                     override=None):
    data=np.arange(request.samples,dtype="<f4").tobytes()
    manifest=dict(schema=RESULT_SCHEMA,session_id=request.session_id,
        request_id=request.request_id,phase="RECORDING",
        updated_utc=datetime.now(timezone.utc).isoformat(),
        adc=request.adc,source_h_tag=request.h_tag,
        entry=f"ADC{request.adc}.f32",samples=request.samples,
        capture_end=request.capture_end,sample_rate_hz=request.sample_rate_hz,
        first_sample_index=(request.device_end_index-request.samples)&0xffffffff,
        next_sample_index=request.device_end_index,
        input_domain="CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32",
        calibration_already_applied=True,provisional_not_audited=True,
        raw_bytes=status["raw_bytes"],frames_decoded=status["frames_decoded"],
        sha256=sha_override or hashlib.sha256(data).hexdigest())
    if override is not None:
        override(manifest)
    with zipfile.ZipFile(run/RESULT_NAME,"w",compression=zipfile.ZIP_STORED) as z:
        z.writestr(manifest["entry"],data)
        z.writestr("MANIFEST.json",json.dumps(manifest))
    return data


def test_source_long_window_only_selected_actual_20_seconds(tmp_path):
    root,status=long_source_status(tmp_path)
    req=submit_source_long_window(root,status,1,0,
        request_id="0123456789abcdef0123456789abcdef")
    assert req is not None
    assert req.samples==65536*20 and req.samples>262144
    assert req.capture_end==req.samples
    assert json.loads((root/REQUEST_NAME).read_text())["device_end_index"]==4096
    assert load_source_long_window(root,status,req) is None
    data=response_fixture(root,status,req)
    ready=load_source_long_window(root,status,req)
    assert ready is not None and ready.received_samples==req.capture_end
    ch=ready.preview.channels[1]
    assert len(ch.samples)==65536*20
    assert ch.first_index>ch.next_index  # valid uint32 wrap
    assert ch.sha256==hashlib.sha256(data).hexdigest()
    assert ch.samples[0]==0 and ch.samples[-1]==req.samples-1
    wave=provisional_waveform(
        ready.preview,1,source_h_tag=0,
        capture_rxpos=req.capture_end,source_allow_overlap=True)
    assert wave["window_samples"]==req.samples
    assert wave["source_getsignal_readiness"]["verified_preview_window_ready"]
    assert wave["source_getsignal_exact_selected_count"]
    assert len(wave["time_s"])<=4000 and len(wave["amplitude"])<=4000


@pytest.mark.parametrize("override",[
    lambda m:m.update(input_domain="RAW_DEVICE_FLOAT32_NOT_YET_CALIBRATED"),
    lambda m:m.update(calibration_already_applied=False),
    lambda m:m.update(samples=262144),
    lambda m:m.update(next_sample_index=42),
    lambda m:m.update(session_id="OTHER_RUN"),
    lambda m:m.update(adc=8),
    lambda m:m.update(source_h_tag=1),
    lambda m:m.update(capture_end=111),
])
def test_source_long_window_fails_closed_on_forged_manifest(tmp_path,override):
    root,status=long_source_status(tmp_path)
    req=submit_source_long_window(root,status,1,0)
    response_fixture(root,status,req,override=override)
    with pytest.raises(ValueError):
        load_source_long_window(root,status,req)


def test_source_long_window_rejects_sha_tamper_and_foreign_response(tmp_path):
    root,status=long_source_status(tmp_path)
    req=submit_source_long_window(root,status,1,0)
    response_fixture(root,status,req,sha_override="f"*64)
    with pytest.raises(ValueError,match="SHA"):
        load_source_long_window(root,status,req)
    response_fixture(root,status,req,override=lambda m:m.update(
        request_id="a"*32))
    assert load_source_long_window(root,status,req) is None


def test_source_long_window_rejects_overwrite_and_accepts_late_status(tmp_path):
    root,status=long_source_status(tmp_path)
    req=submit_source_long_window(root,status,1,0)
    response_fixture(root,status,req)
    status["channels"][0]["samples"]+=256
    status["channels"][0]["next_sample_index"]=(4096+256)&0xffffffff
    row=status["source_original_storage"]["channels"][0]
    row["rx_pos_64"]+=256
    row["next_device_sample_index"]=(4096+256)&0xffffffff
    row["available_elements"]+=256
    assert load_source_long_window(root,status,req) is not None
    # The Go long-window ZIP was valid earlier but the source ring has
    # subsequently overwritten its first sample: do not redisplay it.
    row["rx_pos_64"]+=BUFFER_ELEMENTS
    row["first_readable_pos_64"]=req.capture_end+256
    row["available_elements"]=BUFFER_ELEMENTS
    status["channels"][0]["samples"]=row["rx_pos_64"]
    status["channels"][0]["next_sample_index"]=(
        row["next_device_sample_index"]+BUFFER_ELEMENTS)&0xffffffff
    row["next_device_sample_index"]=status["channels"][0]["next_sample_index"]
    with pytest.raises(ValueError,match="stale"):
        load_source_long_window(root,status,req)


def test_source_long_window_refuses_missing_history_or_other_run(tmp_path):
    root,status=long_source_status(tmp_path)
    status["source_original_storage"]["channels"][0]["available_elements"]=262144
    assert submit_source_long_window(root,status,1,0) is None
    status["source_original_storage"]["channels"][0]["available_elements"]=65536*20
    assert submit_source_long_window(root,status,1,0)
    status["source_tcp_multi_socket"]=True
    with pytest.raises(ValueError,match="trustworthy"):
        submit_source_long_window(root,status,1,0)
    status["source_tcp_multi_socket"]=False
    with pytest.raises(ValueError,match="foreign"):
        submit_source_long_window(tmp_path,status,1,0)


def test_long_source_getsignal_recovers_after_original_freeze_thaw(tmp_path):
    root,status=long_source_status(tmp_path)
    n=65536*20
    # Frozen native packets were still read as RAW, but were never
    # admitted into Delphi-compatible FRxPos. The fresh real 20s window
    # AFTER thaw is still available and must not be permanently blocked.
    status["channels"][0]["samples"]=n+256
    status["channels"][0]["frames"]+=(1)
    rows=[]
    for i,live in enumerate(status["channels"]):
        admitted=live["samples"]*(4 if i>=8 else 1)
        skipped=256 if i==0 else 0
        rows.append(dict(channel=i+1,
            accepted_elements=admitted-skipped,
            freeze_skipped_elements=skipped,rate_skipped_elements=0,
            freeze_skipped_frames=1 if i==0 else 0,
            rate_skipped_frames=0,
            last_skipped_native_samples=256 if i==0 else 0))
    status["source_original_receive_gate_verified"]=True
    status["source_original_receive_gate"]=dict(
        selected_rate_hz=65536,freeze_update=False,
        channels=rows)
    req=submit_source_long_window(root,status,1,0)
    assert req is not None and req.samples==n
    response_fixture(root,status,req)
    answer=load_source_long_window(root,status,req)
    assert answer is not None and answer.received_samples==n
    assert len(answer.preview.channels[1].samples)==n
    status["source_original_receive_gate"]["freeze_update"]=True
    with pytest.raises(ValueError,match="FreezeUpdate"):
        submit_source_long_window(root,status,1,0)
