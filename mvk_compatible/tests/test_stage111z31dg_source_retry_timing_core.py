"""Source TMVKThread retry math validated against _Unit125.pas 008089A3."""
from __future__ import annotations
import math

from ..core.original_mode2_retry_timing import (
    OriginalSourceRetryPlan, SOURCE_CONNECT_TIMEOUT_MS,
    SOURCE_READ_TIMEOUT_MS, START_PAUSE_CENTISECONDS,
)


def test_original_connect_read_timeouts_and_backoff_initial_steps():
    model=OriginalSourceRetryPlan()
    assert model.receipt()["original_connect_timeout_ms"]==1000
    assert model.receipt()["original_read_timeout_ms"]==5000
    assert model.pause_centiseconds==25.0
    first=model.after_failure()
    assert first.local_wait_ms==250
    assert first.source_requeues_set_rate
    assert first.pause_after_centiseconds==model.pause_centiseconds
    assert math.isclose(model.pause_centiseconds,25*math.sqrt(2),rel_tol=1e-7)
    second=model.after_failure()
    assert not second.source_requeues_set_rate
    assert second.local_wait_ms==350  # round(35.355) *10
    assert model.receipt()["source_task2_attempts_modeled"]==2
    assert not model.receipt()["automated_hardware_retry_enabled"]
    assert model.receipt()["device_command_sent"] is False


def test_source_pause_is_bounded_and_resets_only_after_actual_connection():
    model=OriginalSourceRetryPlan()
    history=[model.after_failure() for _ in range(30)]
    assert history[0].source_requeues_set_rate
    assert all(not s.source_requeues_set_rate for s in history[1:])
    assert history[-1].pause_after_centiseconds==(
        history[-1].pause_before_centiseconds)
    assert model.pause_centiseconds>=801
    assert model.pause_centiseconds<1603
    model.connected()
    assert model.pause_centiseconds==START_PAUSE_CENTISECONDS
    again=model.after_failure()
    assert again.source_requeues_set_rate
    assert again.local_wait_ms==250
    assert model.receipt()["device_command_sent"] is False


def test_retry_source_proof_exposed_in_real_mode2_without_auto_execution():
    from ..core.original_mode2_runtime_trace import OriginalMode2RuntimeTrace
    trace=OriginalMode2RuntimeTrace()
    trace.enter_mode2()
    trace.native_started()
    receipt=trace.receipt()
    plan=receipt["original_retry_plan_only"]
    assert plan["original_connect_timeout_ms"]==SOURCE_CONNECT_TIMEOUT_MS
    assert plan["original_read_timeout_ms"]==SOURCE_READ_TIMEOUT_MS
    assert plan["source_task2_attempts_modeled"]==0
    assert plan["automated_hardware_retry_enabled"] is False
    assert receipt["hardware_commands_sent"]==0
