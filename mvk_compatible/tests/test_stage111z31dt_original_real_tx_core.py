"""Actual SetRate evidence is validated independently of UI and a real MVK."""
from __future__ import annotations

import pytest
from .test_stage111z31dm_original_tx_evidence_core import snapshot
from ..core.original_mode2_transmit_evidence import FIELD,validate_original_task2_tx
from ..core.original_mode2_active_tx_provenance import verify_source_native_tx_origin
from ..core.original_mode2_runtime_trace import OriginalMode2RuntimeTrace
from ..core.native_r6_bridge import CaptureSpec


def approved_source_tx():
    p=snapshot(value=0,param=1)
    p["read_only_no_app_payload_sent"]=False
    p[FIELD].update({
        "source_go_device_app_bytes_sent":36,
        "source_tx_explicitly_approved":True,
        "source_tx_sent_commands":1,
        "source_tx_last_rate_hz":65536,
        "source_tx_ack_observed_after_send":0,
        "source_tx_denied_observed_after_send":0,
        "source_tx_write_fault":"",
    })
    return p


def test_real_original_setrate_receipt_is_not_falsely_readonly():
    p=approved_source_tx()
    assert verify_source_native_tx_origin(p)
    result=validate_original_task2_tx(p)
    assert result.approved and result.producer_sent_bytes==36
    assert result.sent_commands==1 and result.current_rate==65536
    assert not result.receipt()["original_delphi_command_physically_observed"]


def test_source_full_mode2_core_counts_actual_tx_and_prevents_rollback():
    p=approved_source_tx()
    trace=OriginalMode2RuntimeTrace()
    trace.enter_mode2()
    trace.native_started()
    result=trace.observe_native(p)
    receipt=trace.receipt()
    assert receipt["hardware_commands_sent"]==1
    assert receipt["source_initial_device_setrate_sent"]
    assert receipt["source_initial_write_calls_physically_sent"]
    assert receipt["recording_commands_allowed"]
    assert receipt["source_mode2_tx_evidence"]["source_tx_last_rate_hz"]==65536
    rolled=approved_source_tx()
    rolled["read_only_no_app_payload_sent"]=True
    rolled[FIELD]["source_go_device_app_bytes_sent"]=0
    rolled[FIELD]["source_tx_sent_commands"]=0
    rolled[FIELD]["source_tx_last_rate_hz"]=0
    with pytest.raises(ValueError,match="rolled back"):
        trace.observe_native(rolled)


@pytest.mark.parametrize("mutation",[
    lambda p:p.update(read_only_no_app_payload_sent=True),
    lambda p:p[FIELD].update(source_tx_explicitly_approved=False),
    lambda p:p[FIELD].update(source_tx_sent_commands=0),
    lambda p:p[FIELD].update(source_tx_sent_commands=2),
    lambda p:p[FIELD].update(source_tx_last_rate_hz=309),
    lambda p:p[FIELD].update(source_go_device_app_bytes_sent=40),
    lambda p:p[FIELD].update(source_tx_ack_observed_after_send=2),
    lambda p:p[FIELD].update(source_tx_denied_observed_after_send=2),
])
def test_unproven_source_tx_fails_closed(mutation):
    p=approved_source_tx()
    mutation(p)
    with pytest.raises(ValueError):
        validate_original_task2_tx(p)


def test_capture_args_require_separate_approval_for_source_tx(tmp_path):
    for tx in (False,True):
        spec=CaptureSpec("192.168.0.30","192.168.0.2",10,256,tmp_path,
                         source_rate_tx=tx)
        root=spec.create_root()
        args=spec.native_args(root)
        assert ("-source-setrate-tx=true" in args)==tx
        assert ("-source-setrate-tx-approved=true" in args)==tx
    with pytest.raises(ValueError):
        CaptureSpec("192.168.0.30","192.168.0.2",10,256,tmp_path,
                    source_rate_tx=1).validate()
