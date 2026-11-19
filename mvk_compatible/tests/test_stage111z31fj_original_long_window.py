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
    submit_source_long_window,submit_source_fft_window,
    load_source_long_window,
)
from mvk_compatible.core.native_r6_live_preview import (
    provisional_waveform,provisional_spectrum,
)
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
            input_domain="ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32" if samples else "",
            original_live_f_range_single=1.0 if samples else None,
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
        input_domain="ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32",
        calibration_already_applied=True,provisional_not_audited=True,
        raw_bytes=status["raw_bytes"],frames_decoded=status["frames_decoded"],
        sha256=sha_override or hashlib.sha256(data).hexdigest(),
        envelope_code=request.envelope_code,
        original_bspec_lines=request.original_bspec_lines)
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


def test_source_short_getsignal_selected_from_real_go_ring_not_preview(tmp_path):
    root,status=long_source_status(tmp_path)
    n=65536*20
    # The incoming TCP stream includes an extra 256 frozen samples.
    # Native preview could include them; original ring FRxPos never did.
    status["channels"][0]["samples"]=n+256
    status["source_original_receive_gate_verified"]=True
    status["source_original_receive_gate"]={
        "selected_rate_hz":65536,"freeze_update":False,
        "channels":[{
            "channel":i+1,
            "accepted_elements":n if i==0 else 0,
            "freeze_skipped_elements":256 if i==0 else 0,
            "rate_skipped_elements":0,
            "freeze_skipped_frames":1 if i==0 else 0,
            "rate_skipped_frames":0,
        } for i in range(10)],
    }
    req=submit_source_long_window(
        root,status,1,5,request_id="12341234123412341234123412341234")
    assert req is not None and req.samples==32768
    assert req.capture_end==n
    data=response_fixture(root,status,req)
    ready=load_source_long_window(root,status,req)
    assert ready is not None and ready.preview.channels[1].sha256==hashlib.sha256(data).hexdigest()
    waveform=provisional_waveform(
        ready.preview,1,source_h_tag=5,capture_rxpos=req.capture_end)
    assert waveform["window_samples"]==32768
    assert waveform["source_getsignal_exact_selected_count"]
    assert waveform["source_getsignal_readiness"]["source_rxpos_64"]==n
    # The same data window has not been tampered with by applying FRange
    # twice or padding a TCP preview with virtual samples.
    assert ready.preview.channels[1].samples[0]==0.
    assert ready.preview.channels[1].samples[-1]==32767.


def test_source_getspectrum_uses_exact_source_ring_n_and_sha(tmp_path):
    root,status=long_source_status(tmp_path)
    req=submit_source_fft_window(
        root,status,1,65536,request_id="abcdabcdabcdabcdabcdabcdabcdabcd")
    assert req is not None and req.h_tag==-1
    assert req.samples==65536
    assert json.loads((root/REQUEST_NAME).read_text())["source_h_tag"]==-1
    assert load_source_long_window(root,status,req) is None
    actual=response_fixture(root,status,req)
    ready=load_source_long_window(root,status,req)
    assert ready is not None and ready.preview.channels[1].sha256==hashlib.sha256(actual).hexdigest()
    spectrum=provisional_spectrum(ready.preview,1,mode=1,n_fft=req.samples)
    assert spectrum["n_fft"]==65536
    assert spectrum["source_fft_n_matches_requested_bSpecLines"]
    assert spectrum["original_delphi_numerical_parity"] is False
    assert spectrum["f_range_used"]==1.
    assert spectrum["input_domain"]=="original_float_storage"
    assert spectrum["source_history_uses_original_live_f_range1_float32"]
    assert not spectrum["source_history_uses_exact_calibrated_float32"]
    assert spectrum["original_storage_read_divided_by_range"] is False
    assert spectrum["source_fft_full_power_bins"]==32768
    # Mis-tagged ZIP, wrong channel, and a made-up N must fail closed.
    response_fixture(root,status,req,override=lambda m:m.update(source_h_tag=5))
    with pytest.raises(ValueError,match="malformed source window"):
        load_source_long_window(root,status,req)
    for invalid in (True,512,2048,1000,262145,524288):
        with pytest.raises(ValueError,match="original HTag or FFT N"):
            submit_source_fft_window(root,status,1,invalid)
    status["source_original_storage_verified"]=False
    with pytest.raises(ValueError,match="trustworthy"):
        submit_source_fft_window(root,status,1,65536)


def test_source_short_window_never_uses_unavailable_ring_history(tmp_path):
    root,status=long_source_status(tmp_path)
    row=status["source_original_storage"]["channels"][0]
    row["available_elements"]=8192
    assert submit_source_long_window(root,status,1,5) is None
    assert submit_source_fft_window(root,status,1,65536) is None
    # If Go has not validated its actual original 2M ring, the normal
    # Native preview is NOT acceptable as a substitute for it.
    status["source_original_storage_verified"]=False
    with pytest.raises(ValueError,match="trustworthy"):
        submit_source_long_window(root,status,1,5)
