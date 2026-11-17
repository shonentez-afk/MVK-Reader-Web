"""Stage111Z31FA: Harness protocol claims must not override existing Source Core.

All inputs synthetic and in-process. NO network, file writes or equipment.
"""
from __future__ import annotations

from struct import pack
from ..core.original_mode2_command_queue import OriginalMode2CommandQueue
from ..core.original_mode2_wire_word_candidate import plan_verified_source_rate_command
from ..core.original_mode2_received_frames import (
    OriginalSourceReadFramer, TYPE_IDENTITY, TYPE_ACK, TYPE_REGISTERS,
    TYPE_ADCDATA, TYPE_TACHDATA,
)


def frame(kind, *words):
    return pack("<II", kind, 8+4*len(words)) + b"".join(pack("<I", x) for x in words)


def test_harness_identity_is_drained_not_a_measured_adc():
    model = OriginalSourceReadFramer()
    item = model.feed(frame(TYPE_IDENTITY, 0x1234, 0x5678))[0]
    assert item.kind == "IDENTITY_DRAIN"
    assert item.processed is False
    assert model.receipt()["source_buffer_chunks_processed"] == 0
    assert model.receipt()["original_source_stage_simulated"] == 0


def test_harness_ack_is_not_param_and_parameter_blocks_are_not_command_acks():
    model = OriginalSourceReadFramer()
    ack = model.feed(frame(TYPE_ACK))[0]
    assert ack.kind == "ACK_OBSERVED"
    assert ack.source_stage == 0
    assert model.receipt()["frames_with_register_blocks"] == 0
    # Five Source PARAM header words; 1 descriptor + 2 register words.
    param = model.feed(frame(TYPE_REGISTERS,0,0,0,0,1,0x00023100,0))[0]
    assert param.kind == "PARAM"
    assert param.register_block_count == 1
    assert param.source_stage == 1
    assert model.receipt()["operation_acks_observed"] == 1


def test_harness_adc_tach_are_data_and_all_ten_channel_addresses_are_supported():
    model = OriginalSourceReadFramer()
    adc = model.feed(frame(TYPE_ADCDATA,0,0,0,7,65536,*([0]*8)))[0]
    tach = model.feed(frame(TYPE_TACHDATA,0,0,0,9,65536,*([0]*8)))[0]
    assert (adc.kind,adc.channel,adc.processed) == ("ADC",7,True)
    assert (tach.kind,tach.channel,tach.processed) == ("TACH",9,True)
    assert model.receipt()["source_buffer_chunks_processed"] == 2
    assert model.receipt()["device_command_sent"] is False


def test_harness_nine_word_setrate_is_eight_header_calls_plus_one_data_call():
    queue = OriginalMode2CommandQueue()
    entry = queue.set_rate(65536)
    plan = plan_verified_source_rate_command(entry)
    assert len(plan.header_words)==8
    assert len(plan.additional_words)==1
    assert len(plan.indy_uint32_stream_bytes())==36
    assert plan.header_words == (
        0xFF800C0D, 36, 0,0,0,0, 1, 0x0002000E)
    assert plan.additional_words == (65536,)
    assert queue.set_rate(65536) is None
    receipt=plan.receipt()
    assert receipt["source_header_write_calls"]==8
    assert receipt["source_followup_write_calls"]==1
    assert receipt["network_or_device_calls_made"] is False