"""Source TMVKThread.Execute receive semantics, pure OFFLINE TCP-frame model.

Inspected from PRIVATE Projects.7z/_Unit125.pas and mvk_idr(1).sqlite:
  00807F74..00808019 ReadUInt32 Type,Length; enforce 8<=L<=0x20000,
                 L%4==0; L is a length in BYTES including 8-byte header.
  00808060 Type 1 identity: drain remaining UInt32.
  0080807B Type 0x00010FF0: operation success reply.
  008080AC Type 0x00010FFF: operation denied (source raises).
  008080EB Types 0xFF8001AC / 0xFF800ADC: read five header words,
                 4th=channel 0..9, 5th=rate Tag; ProcessBufferChunk
                 only if same selected rate and FreezeUpdate is FALSE.
  0080839E Type 0xFF800C0D: header of 5 words (5th block count),
                 descriptor low16=register address, high16=word count;
                 count>0 makes Stage 0->1 at 00808617, NOT TCP Connect.
  008087BB unknown types: log and drain, NEVER turn into a measurement.
  00808762 actual source Stage 3 requires StatusCells>0; cannot infer
                 that from Go packet counters or from a received ACK.

This source emulator is strictly receive-only; no socket, command writer,
physical connection, device ACK assumption or acquired DSP values.
For actual live data, Go R6.1 remains the ONE passive TCP client.
"""
from __future__ import annotations

from dataclasses import dataclass
from struct import unpack_from
from .original_mode2_status_cells import SOURCE_INDEX_ADDR

SOURCE = "IDR_TMVKTHREAD_00807F74_00808019_00808617_RX_SIM_ONLY"
TYPE_IDENTITY = 0x00000001
TYPE_ADCDATA = 0xFF800ADC
TYPE_TACHDATA = 0xFF8001AC
TYPE_REGISTERS = 0xFF800C0D
TYPE_ACK = 0x00010FF0
TYPE_DENIED = 0x00010FFF
SOURCE_LENGTH_MAX = 0x20000
REGISTER_WORDS = 0x4000
MAX_BUFFERED_BYTES = SOURCE_LENGTH_MAX
ALLOWED_SAMPLE_RATES = (512,2048,8192,32768,65536)


class OriginalSourceRxError(ValueError):
    """A malformed source input; no resynchronization after bad framing."""


class OriginalSourceOperationDenied(OriginalSourceRxError):
    """Source 008080AC denial; NOT proof that our receiver sent a command."""


@dataclass(frozen=True)
class SourceReceivedFrame:
    source_type: int
    size: int
    kind: str
    processed: bool
    source_stage: int
    channel: int | None = None
    sample_rate: int | None = None
    register_block_count: int | None = None

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "original_frame_type_hex": f"0x{self.source_type:08X}",
            "bytes_received": self.size,
            "kind": self.kind,
            "source_process_buffer_chunk": self.processed,
            "source_stage_after": self.source_stage,
            "channel_zero_based": self.channel,
            "rate_source_tag": self.sample_rate,
            "register_block_count": self.register_block_count,
            "source_hardware_write_performed": False,
            "device_command_reply_matches_our_write": False,
            "source_dsp_result_verified": False,
        }


class OriginalSourceReadFramer:
    """Incremental source receive emulator with a small bounded tail.

    The model never stores a full recording: frames are returned and
    discarded as they become complete. Its Stage is a *simulation* of
    original TMVKThread Task=2, not a claim the Go recorder became Delphi.
    """

    def __init__(self, *, source_rate_tag: int=65536):
        if type(source_rate_tag) is not int or source_rate_tag not in ALLOWED_SAMPLE_RATES:
            raise ValueError("One original SetRate menu Tag is required")
        self.rate_tag = source_rate_tag
        self.stage = 0
        self.frozen = False
        self._tail = bytearray()
        self.total_frames = 0
        self.ack_observed = 0
        self.denied_observed = 0
        self.register_frames_with_blocks = 0
        # Track ONLY source-backed 14×2 16-bit words, not a fabricated
        # 0x4000 register image or the 0xFFFFFFFF Delphi UNKNOWN value.
        self._status_word_halves:dict[int,int] = {}
        self.source_statuscells0_observed: int | None = None
        self.source_stage3_confirmed_by_valid_register = False
        self.source_data_processed = 0
        self.source_data_drained = 0
        self.unknown_drained = 0
        self.failed = False
        self.last_frame: SourceReceivedFrame | None = None

    def freeze(self, value: bool) -> None:
        if type(value) is not bool:
            raise ValueError("Source FreezeUpdate must be Boolean")
        self.frozen = value

    def set_rate_after_original_menu_click(self, value: int) -> None:
        if type(value) is not int or value not in ALLOWED_SAMPLE_RATES:
            raise ValueError("Invalid original source sample-rate Tag")
        self.rate_tag = value

    @staticmethod
    def _word(buf: bytes, offset: int) -> int:
        return unpack_from("<I", buf, offset)[0]

    def feed(self, chunk: bytes) -> tuple[SourceReceivedFrame, ...]:
        if self.failed:
            raise OriginalSourceRxError("Failed source stream cannot be resumed")
        if not isinstance(chunk, bytes):
            raise TypeError("Source receiver requires immutable bytes")
        # Application framing is bounded by original Source max 0x20000.
        self._tail.extend(chunk)
        out: list[SourceReceivedFrame] = []
        try:
            while len(self._tail) >= 8:
                typ=self._word(self._tail,0)
                size=self._word(self._tail,4)
                if size<8 or size>SOURCE_LENGTH_MAX or size%4:
                    raise OriginalSourceRxError("Source 00807F8B invalid packet length")
                if len(self._tail)<size:
                    break
                frame=bytes(self._tail[:size])
                del self._tail[:size]
                found=self._one(typ,frame)
                self.last_frame=found
                self.total_frames+=1
                out.append(found)
            # A large unbounded trailing junk fragment is never permitted.
            if len(self._tail)>MAX_BUFFERED_BYTES:
                raise OriginalSourceRxError("Source frame tail exceeds maximum")
        except OriginalSourceRxError:
            self.failed=True
            self._tail.clear()
            raise
        return tuple(out)

    def _one(self, typ: int, frame: bytes) -> SourceReceivedFrame:
        n=len(frame)
        body_words=(n-8)//4
        if typ==TYPE_IDENTITY:
            return SourceReceivedFrame(typ,n,"IDENTITY_DRAIN",False,self.stage)
        if typ==TYPE_ACK:
            if body_words:
                raise OriginalSourceRxError("Reply with unverified nonempty body")
            self.ack_observed+=1
            return SourceReceivedFrame(typ,n,"ACK_OBSERVED",False,self.stage)
        if typ==TYPE_DENIED:
            if body_words:
                raise OriginalSourceRxError("Denial with unverified nonempty body")
            self.denied_observed+=1
            raise OriginalSourceOperationDenied("Original errOperationDenied: incoming frame")
        if typ in (TYPE_ADCDATA,TYPE_TACHDATA):
            if body_words<5 or body_words>0x10004:
                raise OriginalSourceRxError("Source 008080EB sample header/size")
            channel=self._word(frame,20)
            rate=self._word(frame,24)
            if channel>=10:
                raise OriginalSourceRxError("Source 00808339 channel must be <10")
            # The deployed Go R6.1 parser enforces 8 ADC + 2 TACH and
            # five verified codes. Do not allow a synthetic incompatible
            # type/rate to count as a legitimate processed sample.
            kind_ok=(channel<8 if typ==TYPE_ADCDATA else channel>=8)
            valid=(kind_ok and rate in ALLOWED_SAMPLE_RATES
                   and body_words>5 and rate==self.rate_tag
                   and not self.frozen)
            if valid:
                self.source_data_processed+=1
            else:
                self.source_data_drained+=1
            return SourceReceivedFrame(
                typ,n,"ADC" if typ==TYPE_ADCDATA else "TACH",
                valid,self.stage,channel=channel,sample_rate=rate)
        if typ==TYPE_REGISTERS:
            # _Unit125.pas 0080844B..0080844F permits exactly five
            # words (28-byte frame) with descriptor count zero.
            if body_words<5:
                raise OriginalSourceRxError("Source 0080839E PARAM header")
            count=self._word(frame,24)
            if count>(body_words-5):
                raise OriginalSourceRxError("Source PARAM descriptor count too large")
            pos=28
            status_updates:dict[int,int]={}
            for _ in range(count):
                if pos+4>n:
                    raise OriginalSourceRxError("Truncated source PARAM descriptor")
                desc=self._word(frame,pos);pos+=4
                addr=desc&0xffff
                words=desc>>16
                if not words or words&1 or addr+words>REGISTER_WORDS or pos+2*words>n:
                    raise OriginalSourceRxError("Source 00808485 invalid PARAM block")
                if not self.frozen:
                    # Source _Unit125:0080850F reads into shared form
                    # buffer and only then 00805D08 compares StatusCells.
                    # No source processing of PARAM payload when frozen.
                    for source_addr in SOURCE_INDEX_ADDR:
                        for reg in (source_addr,source_addr+1):
                            if addr<=reg<addr+words:
                                status_updates[reg]=unpack_from(
                                    "<H",frame,pos+2*(reg-addr))[0]
                pos+=2*words
            if pos!=n:
                raise OriginalSourceRxError("Source PARAM frame contains trailing bytes")
            self._status_word_halves.update(status_updates)
            lo=self._status_word_halves.get(SOURCE_INDEX_ADDR[0])
            hi=self._status_word_halves.get(SOURCE_INDEX_ADDR[0]+1)
            if lo is not None and hi is not None:
                self.source_statuscells0_observed=lo | (hi<<16)
            if count:
                self.register_frames_with_blocks+=1
                if self.stage==0:
                    self.stage=1
                # Original 0080872D uses unsigned StatusCells[0]>0.
                # Our RX simulator suppresses an unobserved FF sentinel;
                # only TWO actually received words can confirm Stage3.
                if (self.source_statuscells0_observed is not None and
                        self.source_statuscells0_observed>0):
                    self.stage=3
                    self.source_stage3_confirmed_by_valid_register=True
            return SourceReceivedFrame(typ,n,"PARAM",bool(count and not self.frozen),
                                       self.stage,register_block_count=count)
        self.unknown_drained+=1
        return SourceReceivedFrame(typ,n,"UNKNOWN_DRAIN",False,self.stage)

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "source_model_only_no_actual_tcp": True,
            "original_source_stage_simulated": self.stage,
            "original_stage1_requires_nonempty_param": True,
            "source_rate_menu_tag": self.rate_tag,
            "freeze_update": self.frozen,
            "total_complete_frames": self.total_frames,
            "frames_with_register_blocks": self.register_frames_with_blocks,
            "source_statuscells0_two_halves_observed":
                self.source_statuscells0_observed is not None,
            "source_statuscells0_raw_uint32":self.source_statuscells0_observed,
            "source_stage3_confirmed_only_by_observed_register":
                self.source_stage3_confirmed_by_valid_register,
            "unobserved_source_FFFFFFFF_sentinel_not_a_go_measurement":True,
            "source_buffer_chunks_processed": self.source_data_processed,
            "source_buffer_chunks_drained": self.source_data_drained,
            "source_unknown_types_drained": self.unknown_drained,
            "operation_acks_observed": self.ack_observed,
            "operation_denials_observed": self.denied_observed,
            "recv_tail_bytes": len(self._tail),
            "failed_closed": self.failed,
            "device_command_sent": False,
            "delphi_equivalence_proven_on_live_device": False,
        }
