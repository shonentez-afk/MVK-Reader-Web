"""Stage111Z31DC: original Mode2 command memory FIFO and Native lifecycle.

Offline/synthetic only. A 12-byte Delphi in-memory record is *not*
a verified TCP packet. No sockets, no hardware writes and no private files.
"""
from __future__ import annotations

import struct
import pytest

from ..core.original_mode2_command_queue import (
    DEFAULT_RATE_CODE, COMMAND_STRUCT_BYTES, RATE_COMMAND, RATE_ADDRESS,
    OriginalCommandRecord, OriginalMode2CommandQueue,
    OriginalMode2FaultRoutes, SOURCE_EXCEPTION_ROUTES,
)
from ..core.original_mode2_runtime_trace import OriginalMode2RuntimeTrace
from .test_stage111z31cr_connected_core import source_test_transport
from .test_stage111z31cz_source_write_stages_core import source_status, RUN


def test_source_command_fifo_memory_records_and_rate_only_if_changed():
    queue=OriginalMode2CommandQueue()
    assert queue.source_rate_code==DEFAULT_RATE_CODE==309
    assert queue.set_rate(309) is None
    a=queue.queue_command(7,0x11223344,0x99abcdef)
    b=queue.set_rate(0x4321)
    c=queue.queue_command(-1,0,0xffffffff)
    assert a.memory_record()==struct.pack("<iII",7,0x11223344,0x99abcdef)
    assert len(a.memory_record())==COMMAND_STRUCT_BYTES==12
    assert (b.cmd,b.addr,b.data)==(RATE_COMMAND,RATE_ADDRESS,0x4321)
    assert c.memory_record()==struct.pack("<iII",-1,0,0xffffffff)
    assert queue.set_rate(0x4321) is None
    assert len(queue.pending)==3
    # Source executes one FIFO element when Stage == 1 ONLY.
    assert queue.take_one(0) is None
    assert queue.take_one(2) is None
    assert [queue.take_one(1) for _ in range(3)]==[a,b,c]
    assert queue.take_one(1) is None
    assert [x.ordinal for x in queue.taken]==[1,2,3]
    receipt=queue.receipt()
    assert not receipt["original_wire_serialization_verified"]
    assert not receipt["original_device_write_enabled"]
    assert receipt["device_commands_sent"]==0
    assert queue.shutdown()["device_commands_sent"]==0
    assert queue.receipt()["queue_closed"]
    with pytest.raises(ValueError):
        queue.queue_command(1,0,2)


@pytest.mark.parametrize("cmd,addr,data",[
    (True,0,0), (2**31,0,0), (0,-1,0), (0,2**32,0),
    (0,0,-1), (0,0,2**32), ("1",0,0)])
def test_offline_model_refuses_non_delphi_command_fields(cmd,addr,data):
    with pytest.raises(ValueError):
        OriginalMode2CommandQueue().queue_command(cmd,addr,data)


def test_rate_change_rejects_invalid_source_code_without_fake_hz():
    queue=OriginalMode2CommandQueue()
    for bad in (-1,2**32,True,"65536"):
        with pytest.raises(ValueError):
            queue.set_rate(bad)
    assert queue.source_rate_code==DEFAULT_RATE_CODE
    assert not queue.pending
    with pytest.raises(ValueError):
        queue.take_one(3)
    assert queue.receipt()["five_original_rate_tags_independently_verified"] is False


def test_source_and_native_faults_have_disjoint_provenance():
    faults=OriginalMode2FaultRoutes()
    assert len(SOURCE_EXCEPTION_ROUTES)==5
    for kind,(_,_,localization) in SOURCE_EXCEPTION_ROUTES.items():
        assert faults.record_source_exception(kind)["localization_key"]==localization
    assert faults.record_source_internal_error("invalid_packet")[
        "localization_key"]=="errInvalidPacket"
    assert not faults.record_native_fault("REFUSED")[
        "matched_to_delphi_exception"]
    assert not faults.receipt()["native_error_equivalence_proven"]
    with pytest.raises(ValueError):
        faults.record_native_fault("EIdReadTimeout")
    faults.finish()
    with pytest.raises(ValueError):
        faults.record_source_exception("read_timeout")


def test_mode2_tabs_before_native_then_exact_single_run_stop_and_finish():
    trace=OriginalMode2RuntimeTrace()
    with pytest.raises(ValueError):
        trace.native_started()
    assert trace.enter_mode2()["mode2_phase"]=="MODE2_BEFORE_TCP"
    assert trace.receipt()["source_ui_before_tcp"]
    assert trace.receipt()["original_queue"]["pending_count"]==0
    assert trace.native_started()["mode2_phase"]=="CONNECTING"
    healthy=source_status(
        session=RUN,adc_samples=512,tach_samples=64,frames=42,raw=82000,aux=1)
    receipt=trace.observe_native(healthy)
    assert receipt["mode2_phase"]=="RECORDING"
    assert receipt["native_run_bound"]
    assert receipt["native_frames_decoded"]==42
    assert not receipt["recording_commands_allowed"]
    assert receipt["hardware_commands_sent"]==0
    assert trace.request_stop()["mode2_phase"]=="STOPPING"
    assert trace.observe_native(healthy)["mode2_phase"]=="STOPPING"
    assert trace.complete(accepted=False)["mode2_phase"]=="STOPPED_WITHOUT_ARCHIVE"
    assert trace.receipt()["original_queue"]["queue_closed"]
    assert trace.leave_after_native()["mode2_phase"]=="IDLE"
    with pytest.raises(ValueError):
        trace.native_started()


def test_source_native_faults_silence_and_recovery_do_not_change_device():
    trace=OriginalMode2RuntimeTrace()
    trace.enter_mode2()
    trace.native_started()
    valid=source_status(session=RUN,adc_samples=512,frames=30,raw=50000)
    assert trace.observe_native(valid)["mode2_phase"]=="RECORDING"
    assert trace.observe_native(
        valid|{"seconds_since_last_packet":5.5})["mode2_phase"]=="SILENT"
    assert trace.observe_native(valid)["mode2_phase"]=="RECORDING"
    trace.status_rejected()
    assert trace.receipt()["mode2_phase"]=="STATUS_REJECTED"
    assert trace.observe_native(valid)["mode2_phase"]=="RECORDING"
    error=trace.receipt()["original_faults"]["events"]
    assert any(x["kind"]=="NO_PACKET" for x in error)
    assert any(x["kind"]=="STATUS_REJECTED" for x in error)
    assert all(x.get("matched_to_delphi_exception") is False for x in error)
    assert trace.complete(accepted=True)["mode2_phase"]=="VERIFIED_ARCHIVE"
    assert trace.receipt()["original_delphi_device_parity_verified"] is False


def test_bound_native_replay_is_refused_and_sparse_old_ui_is_unbound():
    trace=OriginalMode2RuntimeTrace()
    trace.enter_mode2()
    trace.native_started()
    t=source_test_transport(frames=100)
    trace.observe_native(t)
    # These old synthetic transport snapshots lack a source session ID.
    trace.observe_native(source_test_transport(phase="REFUSED",frames=8))
    trace.observe_native(source_status(session=RUN,frames=101,raw=50000))
    with pytest.raises(ValueError,match="changed"):
        trace.observe_native(source_status(
            session="TEST_OTHER",frames=102,raw=51000))
    with pytest.raises(ValueError,match="rolled back"):
        trace.observe_native(source_status(
            session=RUN,frames=100,raw=49000))


def test_mode2_exit_without_tcp_never_claims_transport():
    trace=OriginalMode2RuntimeTrace()
    trace.enter_mode2()
    trace.exit_before_native()
    assert trace.receipt()["mode2_phase"]=="IDLE"
    assert not trace.receipt()["native_capture_started"]
    assert trace.receipt()["events_seen"]==2
    assert trace.receipt()["hardware_commands_sent"]==0


def test_bound_run_cannot_silently_drop_identity_after_valid_status():
    trace=OriginalMode2RuntimeTrace()
    trace.enter_mode2()
    trace.native_started()
    trace.observe_native(source_status(session=RUN,frames=42,raw=42000))
    with pytest.raises(ValueError,match="lost source session identity"):
        trace.observe_native(source_test_transport(frames=43))
    assert trace.receipt()["native_run_bound"]
    assert trace.receipt()["native_frames_decoded"]==42


def test_long_live_fault_trace_is_bounded_and_rate_failure_is_atomic():
    faults=OriginalMode2FaultRoutes()
    for _ in range(90):
        faults.record_native_fault("NO_PACKET")
    report=faults.receipt()
    assert report["event_count"]==90
    assert report["events_retained"]==64
    assert len(report["events"])==64
    queue=OriginalMode2CommandQueue()
    for index in range(256):
        queue.queue_command(2,0,index)
    with pytest.raises(ValueError,match="exhausted"):
        queue.set_rate(32768)
    assert queue.source_rate_code==DEFAULT_RATE_CODE
    assert len(queue.pending)==256
    assert queue.shutdown()["pending_discarded"]==256
