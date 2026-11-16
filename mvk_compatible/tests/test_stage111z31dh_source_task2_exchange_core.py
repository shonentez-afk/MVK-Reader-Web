"""Stage111Z31DH original TMVKThread Task2 full offline transaction replay.

No equipment, ports, Qt dialogs, network calls, or firmware bytes. All
input is constructed as exact-length app frames from private source IDR.
"""
from __future__ import annotations

from struct import pack

import pytest

from ..core.original_mode2_task2_exchange import OriginalTask2OfflineExchange
from ..core.original_mode2_received_frames import (
    OriginalSourceOperationDenied, OriginalSourceRxError,
    TYPE_ACK, TYPE_DENIED, TYPE_REGISTERS, TYPE_ADCDATA, TYPE_TACHDATA,
)


def message(typ: int, *words: int) -> bytes:
    return pack("<II",typ,8+len(words)*4)+b"".join(
        pack("<I",w) for w in words)


def registers() -> bytes:
    # Original PARAM has five header DWORDS, then a descriptor
    # words=2, address=0x3100 followed by two 16-bit values.
    return message(TYPE_REGISTERS, 0,0,0,0,1,0x00023100,0x12340001)


def adc(channel=0,rate=65536) -> bytes:
    return message(TYPE_ADCDATA,0,0,0,channel,rate,*([0]*256))


def tach(channel=8,rate=65536) -> bytes:
    return message(TYPE_TACHDATA,0,0,0,channel,rate,*([0]*64))


def test_exact_source_sequence_initial_setrate_waits_for_param_stage1():
    x=OriginalTask2OfflineExchange()
    assert x.receipt()["original_stage_simulated"]==0
    with pytest.raises(ValueError):
        x.before_next_source_read()
    x.start()
    assert x.receipt()["command_list"]["pending_count"]==1
    assert not x.receipt()["physical_tcp_client_created"]
    x.tcp_connected_in_offline_model()
    assert x.before_next_source_read() is None
    assert x.receive(message(TYPE_ACK))[0].kind=="ACK_OBSERVED"
    assert x.receipt()["original_stage_simulated"]==0
    assert x.receipt()["source_acks_observed_unattributed"]==1
    assert x.before_next_source_read() is None
    # Receiving an ADC packet does not alter source Stage.
    assert x.receive(adc())[0].processed
    assert x.receipt()["original_stage_simulated"]==0
    assert x.receive(registers())[0].source_stage==1
    assert x.receipt()["original_stage_simulated"]==1
    first=x.before_next_source_read()
    assert first["source_header_write_calls"]==8
    assert first["source_followup_write_calls"]==1
    assert first["source_uint32_stream_length_bytes"]==36
    assert first["source_uint32_stream_bytes_hex"]==(
        "0d0c80ff24000000"+"00000000"*4+
        "01000000"+"0e000200"+"00000100")
    assert first["source_tcp_bytes_physically_sent"] is False
    assert x.before_next_source_read() is None
    assert x.receipt()["source_dry_run_write_call_plans"]==1
    assert x.receipt()["command_list"]["pending_count"]==0
    assert x.receipt()["source_acks_observed_unattributed"]==1
    assert not x.receipt()["original_setrate_ack_proven"]
    assert x.receipt()["device_commands_sent"]==0


def test_freeze_drains_tach_adc_and_preserves_param_stage_and_command():
    x=OriginalTask2OfflineExchange()
    x.start()
    x.tcp_connected_in_offline_model()
    x.set_freeze(True)
    assert not x.receive(adc())[0].processed
    assert not x.receive(tach())[0].processed
    assert x.receive(registers())[0].source_stage==1
    first=x.before_next_source_read()
    assert first is not None
    assert not first["source_tcp_bytes_physically_sent"]
    assert x.receipt()["buffer_chunks_processed_simulated"]==0
    assert x.receipt()["buffer_chunks_drained_simulated"]==2
    x.set_freeze(False)
    assert x.receive(tach())[0].processed
    x.select_original_rate(32768)
    assert not x.receive(adc(rate=65536))[0].processed
    assert x.receive(adc(rate=32768))[0].processed
    next_command=x.before_next_source_read()
    assert next_command["write_argument_uint32_hex"][-1]=="0x00008000"
    assert x.receipt()["command_list"]["pending_count"]==0


def test_incoming_denied_triggers_real_source_exception_route_and_retry_plan():
    x=OriginalTask2OfflineExchange()
    x.start()
    x.tcp_connected_in_offline_model()
    x.receive(registers())
    x.before_next_source_read()
    with pytest.raises(OriginalSourceOperationDenied):
        x.receive(message(TYPE_DENIED))
    report=x.receipt()
    assert report["original_stage_simulated"]==0
    assert not report["source_tcp_connected_simulated"]
    assert report["last_source_error"]=="operation_denied"
    assert report["source_denied_exceptions_simulated"]==1
    assert report["source_retry"]["last_step"]["source_wait_ms"]==250
    assert report["command_list"]["pending_count"]==1
    assert report["source_faults"]["events"][-1][
        "localization_key"]=="errOperationDenied"
    # Original Task2 retries only after failure and explicit new connect.
    with pytest.raises(ValueError):
        x.before_next_source_read()
    x.tcp_connected_in_offline_model()
    assert x.before_next_source_read() is None
    x.receive(registers())
    retransmission=x.before_next_source_read()
    assert retransmission["write_argument_uint32_hex"][-1]=="0x00010000"
    assert report["device_commands_sent"]==0


def test_source_typed_network_fault_requeues_once_on_initial_pause():
    x=OriginalTask2OfflineExchange()
    x.start()
    x.tcp_connected_in_offline_model()
    first=x.source_transport_failure("connect_timeout")
    assert first.local_wait_ms==250
    assert first.source_requeues_set_rate
    assert x.receipt()["command_list"]["pending_count"]==2
    x.tcp_connected_in_offline_model()
    x.receive(registers())
    x.before_next_source_read()
    x.before_next_source_read()
    assert x.receipt()["command_list"]["taken_count"]==2
    assert x.receipt()["source_dry_run_write_call_plans"]==2
    assert x.receipt()["source_faults"]["events"][0][
        "delphi_exception_class"]=="EIdConnectTimeout"


def test_failed_source_frame_refuses_replay_and_stop_discards_tlist():
    x=OriginalTask2OfflineExchange()
    x.start()
    x.tcp_connected_in_offline_model()
    with pytest.raises(OriginalSourceRxError):
        x.receive(pack("<II", TYPE_REGISTERS, 9))
    assert x.receipt()["source_faults"]["events"][0][
        "localization_key"]=="errInvalidPacket"
    assert x.receipt()["original_stage_simulated"]==0
    x.stop()
    assert x.receipt()["source_stopped"]
    assert x.receipt()["command_list"]["queue_closed"]
    with pytest.raises(ValueError):
        x.tcp_connected_in_offline_model()
    assert x.receipt()["device_commands_sent"]==0


def test_task2_chunk_boundaries_and_other_source_types_fail_safe():
    x=OriginalTask2OfflineExchange()
    x.start()
    x.tcp_connected_in_offline_model()
    wire=registers()+adc()+message(TYPE_ACK)
    for i in range(0,len(wire),11):
        x.receive(wire[i:i+11])
    assert x.receipt()["original_stage_simulated"]==1
    assert x.receipt()["source_acks_observed_unattributed"]==1
    assert x.receipt()["buffer_chunks_processed_simulated"]==1
    assert x.receipt()["source_dry_run_write_call_plans"]==0
    x.stop()
    assert x.receipt()["physical_tcp_client_created"] is False
