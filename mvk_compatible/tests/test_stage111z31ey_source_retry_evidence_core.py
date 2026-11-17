"""Stage111Z31EY: source 00808AAF..00808B15 real Task2 retry evidence.

Three private source files are only used offline for audit. This test
does not perform instrument I/O or issue a hardware command.
"""
from __future__ import annotations
import pytest
from ..core.native_r6_live_status import validate_live_status
from ..core.original_measurement_mode import source_connection_display
from ..core.original_mode2_retry_timing import OriginalSourceRetryPlan
from .test_stage111z26_native_live_status import fixture_state,now


def _connecting_retry():
    state=fixture_state()
    state["phase"]="CONNECTING"
    state["source_initial_retry_attempts"]=2
    state["source_retry_last_error"]="REMOTE_DISCONNECTED"
    state["source_retry_wait_ms"]=360
    state["source_reconnect_approved"]=True
    return state


def test_source_retry_real_backoff_and_connection_ui_never_green():
    p=_connecting_retry()
    result=validate_live_status(
        p,expected_run=p["session_id"],now=now())
    assert result["source_retry_evidence_verified"]
    assert result["source_initial_retry_attempts"]==2
    assert result["source_retry_wait_ms"]==360
    view=source_connection_display(
        selected=True,capture_started=True,status=result)
    assert view.phase=="RECONNECTING"
    assert not view.transport_verified
    assert view.indicator=="waiting"
    assert "Повторное" in view.text


def test_delphi_round_inc_single_overshoot_reconciled_with_go():
    plan=OriginalSourceRetryPlan()
    waits=[plan.after_failure().local_wait_ms for _ in range(14)]
    assert waits==[260,360,510,720,1010,1420,2010,2840,
                   4010,5670,8010,11320,11320,11320]
    assert plan.receipt()["source_stable_max_wait_ms"]==11320


@pytest.mark.parametrize("update",[
    {"source_initial_retry_attempts":-1},
    {"source_retry_wait_ms":250},
    {"source_retry_wait_ms":8020},
    {"source_retry_last_error":"UNVERIFIED_DRIVER_FAILURE"},
    {"source_reconnect_approved":"yes"},
    {"source_initial_retry_attempts":0},
])
def test_invalid_retry_provenance_refused_before_ui(update):
    data=_connecting_retry()
    data.update(update)
    with pytest.raises(ValueError,match="retry evidence|invalid"):
        validate_live_status(data,expected_run=data["session_id"],now=now())


def test_retries_after_raw_cannot_be_marked_without_original_permission():
    data=_connecting_retry()
    data.update(source_tcp_connection_count=2,
                source_tcp_multi_socket=True,
                source_tcp_reconnects_after_raw=1,
                source_reconnect_approved=False)
    with pytest.raises(ValueError,match="retry evidence"):
        validate_live_status(data,expected_run=data["session_id"],now=now())


def test_pre_source_go_telemetry_remains_backward_compatible():
    data=fixture_state()
    result=validate_live_status(data,expected_run=data["session_id"],now=now())
    assert result["source_initial_retry_attempts"]==0
    assert result["source_retry_wait_ms"]==0
    assert not result["source_retry_evidence_verified"]
