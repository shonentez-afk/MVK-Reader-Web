"""Stage111Z31DB: current transport must authorize EVERY live preview delivery.

No physical MVK device, sockets, or original private captures.
"""
from __future__ import annotations

from dataclasses import replace
import pytest

from .test_stage111z26b_live_preview import make_preview, now
from ..core.native_r6_live_preview import load_live_preview
from ..core.original_live_view_gate import gate_live_preview, SOURCE


def _pair(tmp_path):
    root, status, _ = make_preview(tmp_path)
    return status, load_live_preview(root, status, now=now())


def test_validated_live_preview_requires_same_healthy_native_run(tmp_path):
    status, preview = _pair(tmp_path)
    result = gate_live_preview(status, preview)
    assert result.allowed
    assert result.phase == "RECORDING"
    assert result.receipt()["source"] == SOURCE
    assert not result.receipt()["device_commands_sent"]
    assert not result.receipt()["original_delphi_live_parity_verified"]


@pytest.mark.parametrize("change,phase", [
    ({"phase": "CONNECTING"}, "CONNECTING"),
    ({"phase": "REFUSED"}, "REFUSED"),
    ({"snapshot_stale": True}, "RECORDING"),
    ({"seconds_since_last_packet": 5.1}, "RECORDING"),
    ({"invalid_frames": 2}, "STREAM_ERRORS"),
    ({"capture_only": True}, "CAPTURE_ONLY"),
    ({"session_id": "TEST_FOREIGN"}, "FOREIGN_RUN"),
    ({"frames_decoded": 899}, "COUNTER_MISMATCH"),
    ({"raw_bytes": 499999}, "COUNTER_MISMATCH"),
])
def test_failed_connection_or_new_session_never_authorizes_preview(tmp_path,change,phase):
    status, preview = _pair(tmp_path)
    assert not gate_live_preview(status | change, preview).allowed


def test_stop_and_invalid_status_take_precedence_over_valid_preview(tmp_path):
    status, preview = _pair(tmp_path)
    assert gate_live_preview(status,preview).allowed
    assert not gate_live_preview(status,preview,stop_requested=True).allowed
    assert gate_live_preview(status,preview,stop_requested=True).phase == "STOPPING"
    assert not gate_live_preview(None,preview).allowed
    assert not gate_live_preview({},preview).allowed
    assert not gate_live_preview(status,None).allowed


def test_channel_sample_bounds_and_frequency_must_match_latest_status(tmp_path):
    status, preview = _pair(tmp_path)
    bad_status=dict(status)
    bad_status["channels"]=[dict(x) for x in status["channels"]]
    bad_status["channels"][0]["samples"]=100
    assert gate_live_preview(bad_status,preview).phase == "CHANNEL_MISMATCH"
    changed=dict(preview.channels)
    changed[1]=replace(changed[1],rate_hz=12345)
    assert gate_live_preview(status,replace(preview,channels=changed)).phase == "CHANNEL_MISMATCH"


def test_boolean_stop_flag_is_not_coerced(tmp_path):
    status, preview = _pair(tmp_path)
    with pytest.raises(ValueError):
        gate_live_preview(status,preview,stop_requested=1)


def test_source_mode2_stop_display_is_not_connected_or_green(tmp_path):
    from ..core.original_measurement_mode import source_connection_display
    status,_ = _pair(tmp_path)
    running=source_connection_display(
        selected=True,capture_started=True,status=status)
    assert running.transport_verified
    stopping=source_connection_display(
        selected=True,capture_started=True,status=status,stop_requested=True)
    assert stopping.phase=="STOPPING"
    assert stopping.indicator=="waiting"
    assert not stopping.transport_verified
    assert stopping.text=="Завершение приёма"
    with pytest.raises(ValueError):
        source_connection_display(
            selected=True,capture_started=False,stop_requested=True)


def test_short_verified_source_ring_is_not_classified_as_tcp_preview(tmp_path):
    # A source-ring 32768 sample window is shorter than the ordinary
    # 262144 preview, but must use the *original* accepted FRxPos after
    # FreezeUpdate, not the forensic total TCP sample count.
    status,preview=_pair(tmp_path)
    ch_count=65536
    rows=[]
    for number,channel in enumerate(status["channels"],1):
        rows.append({
            "channel":number,
            "input_domain":"ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32",
            "original_live_f_range_single":1.0,
            "rx_pos_64":ch_count,
            "first_readable_pos_64":0,
            "next_device_sample_index":4096+ch_count,
        })
    validated={
        **status,
        "source_original_storage_verified":True,
        "source_original_storage":{"channels":rows},
    }
    # Status data is produced by the validated Go ring receipt in a
    # real session; these synthetic fields only exercise view routing.
    win=replace(preview,input_domain="ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32",
                source_ring_provenance_verified=True)
    assert gate_live_preview(validated,win).allowed
    # Explicit source provenance may NEVER fall back to a legacy TCP
    # preview when the current validated Go ring disappears.
    denied=gate_live_preview(
        {**validated,"source_original_storage_verified":False,
         "source_original_storage":None},win)
    assert denied.phase=="SOURCE_RING_UNVERIFIED"
    # A 262145-element fake Native preview without a SHA-ring receipt
    # must not be classified as a source GetSignal merely by N.
    import numpy as np
    large_ch=replace(preview.channels[1],
                     samples=np.zeros(262145,dtype="<f4"))
    fake=replace(preview,channels={1:large_ch})
    assert not gate_live_preview(validated,fake).allowed
