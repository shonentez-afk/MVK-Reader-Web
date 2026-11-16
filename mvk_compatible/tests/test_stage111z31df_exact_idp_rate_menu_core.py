"""Stage111Z31DF: private IDR .data rates reconstructed, tested WITHOUT IDP.

The operator-supplied IDP itself is deliberately NOT packaged in GitHub.
One pointer dword at 008D3AEC was independently matched to array 008D2F7C.
The code immediate at 0080618E is 09 03 00 00 = 0x309.
"""
from __future__ import annotations

import pytest

from ..core.original_mode2_rate_menu_source import (
    RATE_ARRAY_ADDRESS, RATE_POINTER_ADDRESS, SOURCE_RATE_CODES_IN_MEMORY,
    SOURCE_RATE_MENU_TAGS, SOURCE_DEFAULT_MENU_TAG,
    SOURCE_THREAD_INITIAL_CODE, ORIGINAL_MENU_COUNT,
    original_rate_menu_items, validate_original_rate_tag,
    source_initial_rate_provenance,
)
from ..core.original_mode2_command_queue import (
    DEFAULT_RATE_CODE, RATE_COMMAND, RATE_ADDRESS,
    OriginalMode2CommandQueue,
)
from ..core.original_mode2_runtime_trace import OriginalMode2RuntimeTrace
from ..core.original_mode2_wire_word_candidate import (
    plan_verified_source_rate_command,
)


def test_private_idp_pointer_and_five_exact_uint32_codes_are_reproduced():
    assert (RATE_POINTER_ADDRESS, RATE_ARRAY_ADDRESS)==(
        0x008D3AEC, 0x008D2F7C)
    assert SOURCE_RATE_CODES_IN_MEMORY == (512,2048,8192,32768,65536)
    assert SOURCE_RATE_MENU_TAGS == (65536,32768,8192,2048,512)
    assert len(SOURCE_RATE_MENU_TAGS) == ORIGINAL_MENU_COUNT == 5
    assert SOURCE_THREAD_INITIAL_CODE == 0x309 == 777
    assert DEFAULT_RATE_CODE==SOURCE_THREAD_INITIAL_CODE
    assert SOURCE_DEFAULT_MENU_TAG==65536
    assert DEFAULT_RATE_CODE != SOURCE_DEFAULT_MENU_TAG
    options=original_rate_menu_items()
    assert [item.position for item in options] == list(range(5))
    assert [item.tag for item in options] == list(SOURCE_RATE_MENU_TAGS)
    assert [item.caption for item in options] == [
        "65536 Гц","32768 Гц","8192 Гц","2048 Гц","512 Гц"]
    assert all(item.receipt()["hardware_rate_change_enabled"] is False
               for item in options)
    assert all(item.receipt()["device_commands_sent"]==0 for item in options)


def test_independent_source_initial_rate_choice_matches_real_menu_item_zero():
    trace=OriginalMode2RuntimeTrace()
    before=trace.enter_mode2()
    assert before["mode2_phase"]=="MODE2_BEFORE_TCP"
    assert not before["source_initial_rate_queued_offline"]
    assert trace.command_model.source_rate_code == 777
    assert trace.command_model.pending == ()
    live=trace.native_started()
    assert live["mode2_phase"]=="CONNECTING"
    assert live["source_selected_sample_rate_code"]==65536
    assert live["source_initial_rate_queued_offline"]
    assert not live["source_initial_device_setrate_sent"]
    assert live["recording_commands_allowed"] is False
    assert trace.command_model.source_rate_code==65536
    assert len(trace.command_model.pending)==1
    first=trace.command_model.pending[0]
    assert (first.ordinal,first.cmd,first.addr,first.data)==(
        1,RATE_COMMAND,RATE_ADDRESS,65536)
    # The exact source Win32 Indy calls are known, but no actual socket exists.
    plan=plan_verified_source_rate_command(first)
    raw=plan.indy_uint32_stream_bytes()
    assert len(raw)==9*4
    assert raw[:8]==bytes.fromhex("0d 0c 80 ff 24 00 00 00")
    assert raw[28:32]==bytes.fromhex("0e 00 02 00")
    assert raw[32:36]==bytes.fromhex("00 00 01 00")
    assert not plan.receipt()["device_command_sender_implemented"]
    assert live["original_queue"]["device_commands_sent"]==0


def test_core_rate_array_rejects_unknown_codes_without_fabrication():
    for known in SOURCE_RATE_MENU_TAGS:
        assert validate_original_rate_tag(known)==known
    for invalid in (0x309,309,0,32000,12345,-1,True,False,"65536"):
        with pytest.raises(ValueError):
            validate_original_rate_tag(invalid)
    receipt=source_initial_rate_provenance()
    assert receipt["source_pointer_data_address"]=="008D3AEC"
    assert receipt["source_original_rate_array_address"]=="008D2F7C"
    assert receipt["initial_menu_tag"]==65536
    assert receipt["original_initial_source_thread_code_hex"]=="0x309"
    assert receipt["original_initial_source_thread_code_decimal"]==777
    assert receipt["original_menu_count"]==5
    assert not receipt["hardware_command_sender_enabled"]
    assert receipt["device_commands_sent"]==0


def test_original_rate_queue_only_issues_one_initial_dry_run_setrate():
    queue=OriginalMode2CommandQueue()
    assert queue.source_rate_code==777
    assert queue.set_rate(777) is None
    initial=queue.set_rate(SOURCE_DEFAULT_MENU_TAG)
    assert len(queue.pending)==1
    assert initial.data==65536
    assert queue.set_rate(SOURCE_DEFAULT_MENU_TAG) is None
    assert len(queue.pending)==1
    assert queue.take_one(0) is None
    assert queue.take_one(1)==initial
    assert queue.take_one(1) is None
    assert queue.receipt()["five_original_rate_tags_independently_verified"]
    assert queue.receipt()["original_rate_menu_codes"]==list(
        SOURCE_RATE_MENU_TAGS)
    assert queue.receipt()["device_commands_sent"]==0
