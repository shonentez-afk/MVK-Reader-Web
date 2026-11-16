"""Original 0080937C write-CALL argument parity, no transport/emulation IO."""
import pytest

from ..core.original_mode2_command_queue import OriginalMode2CommandQueue
from ..core.original_mode2_wire_word_candidate import (
    HEADER_WRITES, RATE_COMMAND_WRITES, SOURCE_HEADER,
    header_source_words, plan_verified_source_rate_command,
)


def test_exact_eight_source_uint32_writer_call_arguments_are_stable():
    expected=(0xff800c0d,36,0,0,0,0,1,0x0002000e)
    assert header_source_words(2,0x0e)==expected
    assert len(expected)==HEADER_WRITES==8
    # Source width words differ from the 12-byte in-memory TList command.
    assert expected[1]==9*4
    assert header_source_words(0,0)==(
        SOURCE_HEADER,32,0,0,0,0,1,0)


def test_source_set_rate_writer_ninth_word_is_data_but_not_socket_bytes():
    model=OriginalMode2CommandQueue()
    assert model.set_rate(309) is None
    command=model.set_rate(101)
    plan=plan_verified_source_rate_command(command)
    assert len(plan.all_words)==RATE_COMMAND_WRITES==9
    assert plan.all_words==(
        SOURCE_HEADER,36,0,0,0,0,1,0x0002000e,101)
    assert model.take_one(1)==command
    evidence=plan.receipt()
    assert evidence["source_header_write_calls"]==8
    assert evidence["source_followup_write_calls"]==1
    assert evidence["write_argument_uint32_hex"][-1]=="0x00000065"
    assert not evidence["network_byte_order_proven"]
    assert not evidence["tcp_packet_bytes_verified"]
    assert not evidence["device_reply_ack_proven"]
    assert not evidence["device_command_sender_implemented"]
    assert not evidence["network_or_device_calls_made"]
    assert model.receipt()["device_commands_sent"]==0


@pytest.mark.parametrize("payload_hint,addr",[
    (-1,0),(1<<32,0),(False,0),(1,True),
    (0,-1),(0,1<<32),(0x20000,0)])
def test_source_word_plan_fails_closed_on_unverified_size_or_address(
        payload_hint,addr):
    with pytest.raises(ValueError):
        header_source_words(payload_hint,addr)


def test_unknown_command_never_becomes_a_device_write_plan():
    model=OriginalMode2CommandQueue()
    unrelated=model.queue_command(3,0x20,50)
    with pytest.raises(ValueError,match="Only source-verified SetRate"):
        plan_verified_source_rate_command(unrelated)
    with pytest.raises(TypeError):
        plan_verified_source_rate_command(None)
