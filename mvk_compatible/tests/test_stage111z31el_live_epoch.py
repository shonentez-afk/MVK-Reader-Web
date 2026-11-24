"""Live window IPC epoch/summary proof. No hardware or original bytes."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import struct

import pytest

from .test_stage111z26_native_live_status import fixture_state
from .test_stage111z31fj_original_long_window import response_fixture
from ..core.live_spectrum_triplet import current_live_spectrum_triplet, DISCLAIMER
from ..core.native_r6_live_preview import provisional_spectrum
from ..core.native_r6_live_status import validate_live_status
from ..core.original_live_spectrum_view import bind_live_spectrum_view
from ..core.original_live_view_gate import gate_live_preview
from ..core.original_receive_gate_receipt import SCHEMA as GATE_SCHEMA
from ..core.original_source_long_window import (
    REQUEST_NAME,submit_source_fft_window,load_source_long_window,
)
from ..core.original_source_ring_receipt import (
    SCHEMA,BUFFER_ELEMENTS,SOURCE_LIVE_ADC_DOMAIN,
)


def epoch_state(tmp_path, *, attempt=2, generation=3, rate=8192,
                capture_end=4096, epoch_start=2048, create=True):
    raw=fixture_state()
    root=tmp_path/raw["session_id"]
    if create:
        root.mkdir()
    now=datetime.now(timezone.utc)
    raw.update(updated_utc=now.isoformat(),run_directory=str(root),
        source_tcp_connection_count=attempt,source_tcp_multi_socket=attempt>1,
        source_tcp_reconnects_after_raw=attempt-1,
        source_initial_retry_attempts=attempt-1,source_reconnect_approved=True,
        source_retry_wait_ms=260 if attempt>1 else 0,
        source_retry_last_error="REMOTE_DISCONNECTED" if attempt>1 else "",
        source_rate_transition_during_live=True)
    ring,gate=[],[]
    for ch in raw["channels"]:
        i=ch["channel"]
        n=capture_end if i==1 else 0
        ch.update(samples=n,frames=n//256,
            sample_rates_hz=sorted({rate,65536}) if n else [],
            sequence_discontinuities=1 if n else 0,
            next_sample_index=512+n if n else None,
            dsp_sensor_status_hex=None)
        source_range=(dict(single=1.,origin="REGISTER_FLOAT32",
            register_word=0x10e,register_raw_le=struct.pack("<f",1).hex(),
            units_raw_le="",latched_frame=5 if attempt>1 else 1,
            socket_attempt=attempt,usable=True) if n else None)
        ring.append(dict(channel=i,sample_width_bytes=4 if i<=8 else 1,
            rx_pos_64=n,valid_pos_64=epoch_start if n else 0,
            first_readable_pos_64=epoch_start if n else 0,
            available_elements=n-epoch_start if n else 0,
            last_sample_rate_hz=rate if n else 0,
            next_device_sample_index=ch["next_sample_index"],
            input_domain=SOURCE_LIVE_ADC_DOMAIN if n else "",
            original_live_f_range_single=1. if n else None,
            source_range_state=source_range,sequence_gaps=1 if n else 0,
            rate_changes=1 if n else 0,rejected_nonfinite_frames=0,
            source_epoch=(dict(socket_attempt=attempt,continuity_generation=generation,
                start_pos_64=epoch_start) if n else None)))
        gate.append(dict(channel=i,accepted_elements=n,rate_skipped_elements=0,
            freeze_skipped_elements=0,rate_skipped_frames=0,freeze_skipped_frames=0,
            last_skipped_native_samples=0))
    raw["source_original_storage"]=dict(schema=SCHEMA,
        buffer_elements_per_channel=BUFFER_ELEMENTS,channels=ring)
    raw["source_original_receive_gate"]=dict(schema=GATE_SCHEMA,
        initial_thread_rate_hz=777,source_initial_menu_rate_hz=65536,
        selected_rate_hz=rate,source_menu_selected=True,selection_changes=2,
        freeze_changes=0,freeze_update=False,physical_setrate_not_inferred=True,
        original_delphi_parity_verified=False,channels=gate)
    return root,raw,now


def validated(raw, now):
    return validate_live_status(raw,expected_run=raw["session_id"],now=now)


def available_window(root,status):
    req=submit_source_fft_window(root,status,1,1024)
    assert req is not None
    response_fixture(root,status,req,override=lambda m:m.update(
        source_range_state=req.source_range_state,source_epoch=req.source_epoch))
    return load_source_long_window(root,status,req)


def test_epoch_requires_full_history_and_never_rebinds_old_result(tmp_path):
    root,raw,now=epoch_state(tmp_path,epoch_start=3500)
    status=validated(raw,now)
    assert submit_source_fft_window(root,status,1,1024) is None
    assert not (root/REQUEST_NAME).exists()
    bad=deepcopy(raw)
    bad["source_original_storage"]["channels"][0]["source_epoch"]["socket_attempt"]=1
    with pytest.raises(ValueError,match="epoch"):
        validated(bad,now)
    root,raw,now=epoch_state(tmp_path,create=False)
    status=validated(raw,now)
    window=available_window(root,status)
    assert gate_live_preview(status,window.preview).allowed
    assert json.loads((root/REQUEST_NAME).read_text())["source_epoch"]==window.request.source_epoch
    # Same rate/ADC/end-index and identical payload, but a different
    # epoch must still reject both an old IPC result and the old display.
    root,new,now=epoch_state(tmp_path,generation=4,create=False)
    new=validated(new,now)
    with pytest.raises(ValueError,match="stale source epoch"):
        load_source_long_window(root,new,window.request)
    assert not gate_live_preview(new,window.preview).allowed
    current=available_window(root,new)
    assert gate_live_preview(new,current.preview).allowed
    forged=deepcopy(new)
    forged["source_rx_denied_responses"]=1
    assert not gate_live_preview(forged,current.preview).allowed
    forged=deepcopy(new)
    forged["channels"][0]["nonfinite_samples"]=1
    assert not gate_live_preview(forged,current.preview).allowed
    forged=deepcopy(new)
    forged["source_original_receive_gate"]["freeze_update"]=True
    assert not gate_live_preview(forged,current.preview).allowed


def test_live_local_triplet_never_exports_stale_or_to_vendor_file(tmp_path):
    root,raw,now=epoch_state(tmp_path)
    status=validated(raw,now)
    window=available_window(root,status)
    result=provisional_spectrum(window.preview,1,mode=0,n_fft=1024,full_bins=True)
    view=bind_live_spectrum_view(window.preview,1,result,selected_n=1024,code=0,mode=0)
    view["live_source_request_id"]=window.request.request_id
    kwargs=dict(adc=1,mode=0,selected_n=1024,code=0)
    action=current_live_spectrum_triplet(status,window,view,**kwargs)
    out=tmp_path/"MVK-COMPATIBLE-LIVE-ADC1.csv"
    action.save_new(out)
    assert len(action.clipboard_text().splitlines()[1].split("\t"))==3
    saved=out.read_text(encoding="utf-8")
    assert DISCLAIMER in saved
    assert len(saved.splitlines()[-1].split("|"))==3
    with pytest.raises(FileExistsError):
        action.save_new(out)
    vendor=tmp_path/"SPEC-FREQ-2026-11-24.csv"
    with pytest.raises(ValueError):
        action.save_new(vendor)
    assert not vendor.exists()
    with pytest.raises(ValueError,match="окно изменились"):
        current_live_spectrum_triplet(status,window,
            view|{"live_source_request_id":"f"*32},**kwargs)
    with pytest.raises(ValueError,match="устарело"):
        current_live_spectrum_triplet(status,window,view,**kwargs,
            now=window.preview.updated_utc+timedelta(seconds=9))
    with pytest.raises(ValueError):
        current_live_spectrum_triplet(status,replace(window,
            preview=replace(window.preview,source_ring_provenance_verified=False)),
            view,**kwargs)
