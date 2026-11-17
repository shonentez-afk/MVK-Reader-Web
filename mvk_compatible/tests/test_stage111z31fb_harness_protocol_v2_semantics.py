"""Stage111Z31FB: reject Harness V2's false ADC/PARAM/ack reconstruction.

All data are synthetic and processed IN MEMORY ONLY: no network, QProcess,
original executable, firmware, instrument, external files or device writes.
"""
from __future__ import annotations
from struct import pack
import pytest

from ..core.original_mode2_received_frames import (
    OriginalSourceReadFramer, OriginalSourceRxError,
    TYPE_IDENTITY, TYPE_ADCDATA, TYPE_TACHDATA, TYPE_REGISTERS, TYPE_ACK,
)
from ..core.original_mode2_status_cells import SOURCE_INDEX_ADDR, SOURCE_INDEX_LABEL
from ..core.original_mode2_command_queue import OriginalMode2CommandQueue
from ..core.original_mode2_wire_word_candidate import plan_verified_source_rate_command
from ..core.original_runtime_tabs import original_runtime_visible_pages


def packet(typ: int, *words: int) -> bytes:
    return pack('<II',typ,8+len(words)*4)+b''.join(pack('<I',w) for w in words)


def samples(typ=TYPE_ADCDATA, channel=0, rate=65536, n=8) -> bytes:
    return packet(typ,0,0,0,channel,rate,*([0]*n))


def param(addr: int, value: int=0) -> bytes:
    return packet(TYPE_REGISTERS,0,0,0,0,1,(2<<16)|addr,value)


def test_type_one_drain_and_ack_are_not_data_or_status_parameters():
    core=OriginalSourceReadFramer()
    a=core.feed(packet(TYPE_IDENTITY,0x100,0x200,0x300))[0]
    assert (a.kind,a.processed,a.source_stage)==('IDENTITY_DRAIN',False,0)
    ack=core.feed(packet(TYPE_ACK))[0]
    assert (ack.kind,ack.processed,ack.source_stage)==('ACK_OBSERVED',False,0)
    state=core.receipt()
    assert state['source_buffer_chunks_processed']==0
    assert state['frames_with_register_blocks']==0
    assert state['device_command_sent'] is False


def test_source_sample_branch_processes_adcs_and_both_tachs_below_ten():
    core=OriginalSourceReadFramer()
    for ch in range(8):
        r=core.feed(samples(TYPE_ADCDATA,ch))[0]
        assert (r.kind,r.channel,r.processed)==('ADC',ch,True)
    for ch in (8,9):
        r=core.feed(samples(TYPE_TACHDATA,ch))[0]
        assert (r.kind,r.channel,r.processed)==('TACH',ch,True)
    assert core.receipt()['source_buffer_chunks_processed']==10
    assert core.receipt()['original_source_stage_simulated']==0


def test_00808339_channel_ten_is_invalid_not_tach():
    core=OriginalSourceReadFramer()
    with pytest.raises(OriginalSourceRxError,match='channel must be <10'):
        core.feed(samples(TYPE_TACHDATA,10))
    assert core.receipt()['failed_closed']
    assert core.receipt()['source_buffer_chunks_processed']==0


def test_sample_payload_word_formula_excludes_eight_byte_header():
    raw=samples(TYPE_ADCDATA,2,n=7)
    expected_bytes=7*4
    assert len(raw)==8+5*4+expected_bytes
    assert (len(raw)-8)//4 - 5 == 7
    assert ((len(raw)-8)//4-5)*4 == expected_bytes
    assert (len(raw)//4-5)*4 != expected_bytes  # Harness TESTS_SPEC bug
    core=OriginalSourceReadFramer()
    r=core.feed(raw)[0]
    assert (r.size,r.channel,r.processed)==(len(raw),2,True)


def test_fs_mismatch_and_freeze_discard_but_never_relabel_type_one():
    core=OriginalSourceReadFramer()
    assert core.feed(samples(rate=32768))[0].processed is False
    core.freeze(True)
    assert core.feed(samples())[0].processed is False
    core.freeze(False)
    assert core.feed(samples())[0].processed is True
    assert core.receipt()['source_buffer_chunks_drained']==2


def test_stage_one_requires_valid_param_not_specific_register_3100():
    core=OriginalSourceReadFramer()
    assert core.feed(param(0x3000))[0].source_stage==1
    assert core.receipt()['frames_with_register_blocks']==1
    assert core.receipt()['device_command_sent'] is False
    another=OriginalSourceReadFramer()
    assert another.feed(param(0x3100))[0].source_stage==1
    assert another.receipt()['source_statuscells0_raw_uint32'] is None
    assert another.receipt()['device_command_sent'] is False


def test_fourteen_statuscells_are_addresses_not_fourteen_packet_descriptors():
    assert len(SOURCE_INDEX_ADDR)==len(SOURCE_INDEX_LABEL)==14
    assert SOURCE_INDEX_ADDR[:4]==(0x1006,0x1038,0x1030,0x1032)
    assert SOURCE_INDEX_ADDR[-2:]==(0x3004,0x3104)
    core=OriginalSourceReadFramer()
    r=core.feed(param(0x3000))[0] # just ONE PARAM descriptor
    assert r.register_block_count==1
    assert core.receipt()['frames_with_register_blocks']==1


def test_writer_is_eight_header_calls_and_one_data_call_only_for_setrate():
    queue=OriginalMode2CommandQueue()
    command=queue.set_rate(65536)
    plan=plan_verified_source_rate_command(command)
    assert len(plan.header_words)==8
    assert len(plan.additional_words)==1
    assert plan.header_words==(0xFF800C0D,36,0,0,0,0,1,0x0002000E)
    assert plan.additional_words==(65536,)
    assert len(plan.indy_uint32_stream_bytes())==36
    assert plan.receipt()['network_or_device_calls_made'] is False
    assert queue.take_one(0) is None
    assert queue.take_one(1) == command
    assert queue.receipt()['device_commands_sent']==0


def test_real_source_mode2_tabs_are_visible_without_socket_or_research_ui():
    shown=original_runtime_visible_pages(
        has_measurement=False, measurement_requested=True, technical=False,
        current_page='PageStart')
    assert shown==('PageStart','PageStatus','PageAdc','PageSpectrum','PageFile')