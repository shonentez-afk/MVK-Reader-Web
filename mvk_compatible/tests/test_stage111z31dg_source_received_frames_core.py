"""Source _Unit125.pas packet dispatch verified on private IDP, offline only."""
from __future__ import annotations

import struct
import pytest

from ..core.original_mode2_received_frames import (
    TYPE_IDENTITY, TYPE_ADCDATA, TYPE_TACHDATA, TYPE_REGISTERS,
    TYPE_ACK, TYPE_DENIED, OriginalSourceReadFramer, OriginalSourceRxError,
    OriginalSourceOperationDenied,
)


def frame(typ, words=()):
    content=b"".join(struct.pack("<I",word) for word in words)
    return struct.pack("<II",typ,8+len(content))+content


def param(addr=0x3100,count=2):
    # Five header uint32 after T/L; fifth is register-block count.
    # Descriptor = (WordCount << 16) | Addr. Source stores 16-bit values.
    content=struct.pack("<5I",0,0,0,0,1)
    content+=struct.pack("<I",(count<<16)|addr)
    content+=bytes(count*2)
    return struct.pack("<II",TYPE_REGISTERS,8+len(content))+content


def sample(typ=TYPE_ADCDATA,channel=0,rate=65536,n=256):
    words=[0,0,0,channel,rate]+[0]*n
    return frame(typ,words)


def test_source_accepted_frame_types_source_stage_not_tcp_connection():
    src=OriginalSourceReadFramer()
    r=src.receipt()
    assert r["original_source_stage_simulated"]==0
    assert not r["device_command_sent"]
    identity=src.feed(frame(TYPE_IDENTITY,[10,20]))
    assert len(identity)==1
    assert identity[0].kind=="IDENTITY_DRAIN"
    assert src.receipt()["original_source_stage_simulated"]==0
    ack=src.feed(frame(TYPE_ACK))
    assert ack[0].kind=="ACK_OBSERVED"
    assert src.receipt()["operation_acks_observed"]==1
    # An ACK does NOT prove the read-only Go client set the sample rate.
    assert src.receipt()["original_source_stage_simulated"]==0
    # A complete sample frame before register metadata may be processed
    # by the original source but it does NOT establish Stage 1.
    observed=src.feed(sample())
    assert observed[0].kind=="ADC"
    assert observed[0].processed
    assert src.receipt()["original_source_stage_simulated"]==0
    reg=src.feed(param())
    assert len(reg)==1
    assert reg[0].kind=="PARAM"
    assert reg[0].processed
    assert reg[0].register_block_count==1
    assert reg[0].source_stage==1
    assert src.receipt()["original_source_stage_simulated"]==1
    assert src.receipt()["frames_with_register_blocks"]==1
    assert not src.receipt()["delphi_equivalence_proven_on_live_device"]


def test_split_tcp_frames_are_reassembled_without_replay_or_dropped_bytes():
    wire=sample()+param()
    src=OriginalSourceReadFramer()
    assert src.feed(wire[:3])==()
    assert src.feed(wire[3:8])==()
    assert src.feed(wire[8:66])==()
    items=src.feed(wire[66:])
    assert [x.kind for x in items]==["ADC","PARAM"]
    assert src.receipt()["total_complete_frames"]==2
    assert src.receipt()["recv_tail_bytes"]==0
    assert src.receipt()["original_source_stage_simulated"]==1


def test_live_source_freeze_drains_without_processing_while_stage_transitions():
    src=OriginalSourceReadFramer()
    src.freeze(True)
    assert not src.feed(sample())[0].processed
    assert not src.feed(sample(TYPE_TACHDATA,channel=8,n=64))[0].processed
    state=src.feed(param())[0]
    assert not state.processed
    assert state.source_stage==1  # source Stage0->1 even if frozen
    assert src.receipt()["source_buffer_chunks_drained"]==2
    src.freeze(False)
    assert src.feed(sample())[0].processed
    # Wrong source rate must be fully consumed, NEVER shown as a
    # sample from the operator-selected 65536Hz channel.
    assert not src.feed(sample(rate=32768))[0].processed
    src.set_rate_after_original_menu_click(32768)
    assert src.feed(sample(rate=32768))[0].processed


def test_unknown_source_frame_is_drained_but_not_treated_as_verified_sample():
    src=OriginalSourceReadFramer()
    out=src.feed(frame(0xBA5E0001,[123,456]))
    assert out[0].kind=="UNKNOWN_DRAIN"
    assert not out[0].processed
    assert src.receipt()["source_unknown_types_drained"]==1
    assert src.receipt()["original_source_stage_simulated"]==0


@pytest.mark.parametrize("typ,size", [
    (TYPE_ADCDATA,6),(TYPE_ADCDATA,9),(TYPE_ADCDATA,0x20004),
])
def test_bad_original_envelope_fails_closed_without_resynchronization(typ,size):
    src=OriginalSourceReadFramer()
    with pytest.raises(OriginalSourceRxError):
        src.feed(struct.pack("<II",typ,size))
    assert src.receipt()["failed_closed"]
    with pytest.raises(OriginalSourceRxError):
        src.feed(frame(TYPE_ACK))


def test_invalid_register_descriptor_fails_closed_and_never_marks_stage1():
    src=OriginalSourceReadFramer()
    broken=frame(TYPE_REGISTERS,[0,0,0,0,1,(0xffff<<16)|0x3100])
    with pytest.raises(OriginalSourceRxError):
        src.feed(broken)
    assert src.receipt()["original_source_stage_simulated"]==0
    assert src.receipt()["failed_closed"]


def test_short_register_frame_fails_closed_before_source_5_word_underflow():
    src=OriginalSourceReadFramer()
    with pytest.raises(OriginalSourceRxError):
        src.feed(frame(TYPE_REGISTERS,[0,0,0]))
    assert src.receipt()["failed_closed"]


def test_denied_is_source_exception_not_our_command_acknowledgment():
    src=OriginalSourceReadFramer()
    with pytest.raises(OriginalSourceOperationDenied):
        src.feed(frame(TYPE_DENIED))
    assert src.receipt()["operation_denials_observed"]==1
    assert src.receipt()["failed_closed"]
    assert src.receipt()["original_source_stage_simulated"]==0
    assert src.receipt()["device_command_sent"] is False


@pytest.mark.parametrize("kind,ch",[(TYPE_ADCDATA,8),(TYPE_TACHDATA,0)])
def test_source_type_to_channel_8adc_2tach_gate(kind,ch):
    src=OriginalSourceReadFramer()
    r=src.feed(sample(kind,channel=ch,n=64))[0]
    assert not r.processed
    assert src.receipt()["source_buffer_chunks_processed"]==0
    assert src.receipt()["source_buffer_chunks_drained"]==1


def test_original_source_ack_and_undersized_empty_param_do_not_mark_readiness():
    src=OriginalSourceReadFramer()
    assert src.feed(frame(TYPE_ACK))[0].source_stage==0
    assert src.receipt()["frames_with_register_blocks"]==0
    # 0080839E requires at least 6 body DWORDS. With 0 descriptor
    # count a raw 5-word header is undersized (28 bytes), so it cannot
    # transition Stage 0 -> 1 or silently become a synthetic status.
    empty=frame(TYPE_REGISTERS,[0,0,0,0,0])
    with pytest.raises(OriginalSourceRxError):
        src.feed(empty)
    assert src.receipt()["original_source_stage_simulated"]==0
    assert src.receipt()["failed_closed"]
