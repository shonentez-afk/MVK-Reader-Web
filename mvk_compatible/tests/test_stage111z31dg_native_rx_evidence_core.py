"""Source receive readiness must come from actual one-run Go counters."""
from __future__ import annotations

import pytest

from ..core.original_mode2_rx_evidence import (
    OriginalMode2ReceiveEvidence, FIELDS,
)
from ..core.native_r6_live_status import validate_live_status
from ..core.original_mode2_runtime_trace import OriginalMode2RuntimeTrace
from .test_stage111z26_native_live_status import fixture_state,now
from .test_stage111z31cz_source_write_stages_core import source_status,RUN


def _go_status(*,params=0,acks=0,denied=0,frames=1200):
    raw=fixture_state()
    raw["frames_decoded"]=frames
    raw[FIELDS[0]]=params
    raw[FIELDS[1]]=acks
    raw[FIELDS[2]]=denied
    return validate_live_status(raw,expected_run=raw["session_id"],now=now())


def test_source_rx_ready_needs_received_nonempty_register_not_just_tcp_or_adc():
    receiver=OriginalMode2ReceiveEvidence()
    before=receiver.receipt()
    assert not before["native_protocol_evidence_available"]
    assert before["original_source_stage_candidate_from_rx"] is None
    src=receiver.observe_native(_go_status())
    assert src["native_protocol_evidence_available"]
    assert src["original_source_stage_candidate_from_rx"]==0
    assert not src["denial_seen"]
    after=receiver.observe_native(_go_status(params=1))
    assert after["original_source_stage_candidate_from_rx"]==1
    assert after["native_receive_register_frames_with_blocks"]==1
    assert not after["original_source_stage_is_actually_running"]
    assert not after["original_setrate_command_ack_verified"]
    assert after["device_commands_sent"]==0


def test_source_received_ack_unattributed_and_new_denied_once_only():
    rec=OriginalMode2ReceiveEvidence()
    x=rec.observe_native(_go_status(params=1,acks=2,denied=0))
    assert x["native_received_ack_unattributed"]==2
    assert not x["new_denial_observed_this_snapshot"]
    x=rec.observe_native(_go_status(params=1,acks=2,denied=1,frames=1201))
    assert x["denial_seen"]
    assert x["new_denial_observed_this_snapshot"]
    assert x["native_received_denied_unattributed"]==1
    assert not x["original_setrate_command_ack_verified"]
    again=rec.observe_native(_go_status(params=1,acks=2,denied=1,frames=1201))
    assert not again["new_denial_observed_this_snapshot"]


@pytest.mark.parametrize("mutation", [
    lambda x: x.pop(FIELDS[2]),
    lambda x: x.__setitem__(FIELDS[0],-1),
    lambda x: x.__setitem__(FIELDS[1],True),
    lambda x: x.__setitem__(FIELDS[1],1201),
    lambda x: x.__setitem__(FIELDS[2],"1"),
])
def test_native_status_rejects_fabricated_incomplete_or_oversized_go_counters(
        mutation):
    x=fixture_state()
    x.update(zip(FIELDS,(1,1,1)))
    mutation(x)
    with pytest.raises(ValueError):
        validate_live_status(x,expected_run=x["session_id"],now=now())


def test_source_receipt_refuses_counter_rollback_and_missing_bound_field():
    rec=OriginalMode2ReceiveEvidence()
    rec.observe_native(_go_status(params=2,acks=1,denied=1,frames=1200))
    with pytest.raises(ValueError,match="rolled back"):
        rec.observe_native(_go_status(params=1,acks=1,denied=1,frames=1201))
    with pytest.raises(ValueError,match="disappeared"):
        rec.observe_native(source_status(session=RUN,frames=1202,raw=62000))


def test_legacy_native_fixture_without_go_fields_is_unknown_not_stage1():
    rec=OriginalMode2ReceiveEvidence()
    snap=source_status(session=RUN,frames=900,raw=50000)
    x=rec.observe_native(snap)
    assert not x["native_protocol_evidence_available"]
    assert x["original_source_stage_candidate_from_rx"] is None


def test_integrated_original_mode2_core_receipt_keeps_ack_out_of_dry_run_queue():
    src=OriginalMode2RuntimeTrace()
    src.enter_mode2()
    src.native_started()
    assert len(src.command_model.pending)==1
    original=src.command_model.pending[0]
    status=source_status(session=RUN,frames=900,raw=50000)
    status.update(zip(FIELDS,(1,1,0)))
    read=src.observe_native(status)
    assert read["original_receive_protocol"][
        "original_source_stage_candidate_from_rx"]==1
    assert read["original_receive_protocol"]["native_received_ack_unattributed"]==1
    assert len(src.command_model.pending)==0
    assert src.command_model.taken==(original,)
    offline=read["source_initial_rate_write_calls_dry_run"]
    assert offline["source_header_write_calls"]==8
    assert offline["source_followup_write_calls"]==1
    assert offline["write_argument_uint32_hex"][-1]=="0x00010000"
    assert not offline["device_command_sender_implemented"]
    assert not read["source_initial_write_calls_physically_sent"]
    assert read["hardware_commands_sent"]==0
    status.update({FIELDS[2]:1,"frames_decoded":901})
    read=src.observe_native(status)
    assert read["last_events"][-2][1]=="PASSIVE_RX_OPERATION_DENIED"
    assert read["original_receive_protocol"]["denial_seen"]
    assert len(src.command_model.pending)==0
    assert src.command_model.taken==(original,)
