"""IDR _Unit125.pas 0080937C: NON-TRANSMITTING source word-call plan.

Reconstructs TIdIOHandler.Write UInt32 *call arguments* from disassembly.
Additional PRIVATE _Unit123.pas 007F3E58 proves AConvert=False bypasses
byte swap, and _Unit116.pas 007D8968 ToBytes(LongWord) copies a DWORD
into four bytes on Win32: little-endian UInt32 stream bytes are source-
verified. This does NOT prove TCP packet boundaries, replies, handshake or
safe instrument transactions. No IO in this file: NEVER send to hardware.

- 0080937C..008093FA: eight sequential TIdIOHandler.Write calls.
- 00807F2F..00807F52: queue command calls 0080937C with ECX=2,
  EDX=CurrentCommand.Addr, then writes Data in one additional call.
- 00809364: SetRate queues Cmd=1 Addr=0x0E Data=MvkSampleRate.
- 00809330: 12 bytes are the TList in-memory record, NOT packet header.

No claim about TCP segmentation, device ACK, handshake or retry timing.
"""
from __future__ import annotations

from dataclasses import dataclass

from .original_mode2_command_queue import OriginalCommandRecord, RATE_COMMAND, RATE_ADDRESS

SOURCE = "SOURCE_IDR_0080937C_WRITE_UINT32_CALLS_OFFLINE_ONLY"
SOURCE_HEADER = 0xFF800C0D
HEADER_WRITES = 8
RATE_COMMAND_WRITES = 9


def _source_u32(v: int, name: str) -> int:
    if type(v) is not int or v < 0 or v > 0xffffffff:
        raise ValueError("Source writer UInt32 out of range: " + name)
    return v


@dataclass(frozen=True)
class SourceWordCallPlan:
    """Ordered source WriteUInt32 arguments, never sendable bytes."""

    header_words: tuple[int, ...]
    additional_words: tuple[int, ...]
    kind: str

    def __post_init__(self):
        if len(self.header_words) != HEADER_WRITES:
            raise ValueError("Original source header requires eight writes")
        for v in self.header_words + self.additional_words:
            _source_u32(v, "Write uint32 call argument")

    @property
    def all_words(self) -> tuple[int, ...]:
        return self.header_words + self.additional_words

    def indy_uint32_stream_bytes(self) -> bytes:
        """Pure offline byte concatenation of AConvert=False UInt32 calls.

        Source 007F3E58 (Indy Cardinal Write) bypasses conversion when
        ECX=0; ToBytes(LongWord) 007D8968 copies the 32-bit value in
        Win32 memory order. Does NOT open sockets or model TCP frames.
        """
        return b"".join(word.to_bytes(4, "little") for word in self.all_words)

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "source_procedure_address": "0080937C",
            "source_header_write_calls": len(self.header_words),
            "source_followup_write_calls": len(self.additional_words),
            "write_argument_uint32_hex": tuple(
                f"0x{w:08X}" for w in self.all_words),
            "source_32bit_write_arguments_reconstructed": True,
            "source_uint32_write_overload_address": "007F3E58",
            "source_uint32_to_bytes_address": "007D8968",
            "source_win32_uint32_stream_byte_order": "little-endian",
            "source_uint32_stream_endianness_verified": True,
            "source_uint32_stream_bytes_hex": self.indy_uint32_stream_bytes().hex(),
            "source_uint32_stream_length_bytes": 4 * len(self.all_words),
            "network_byte_order_proven": False,
            "tcp_packet_bytes_verified": False,
            "device_reply_ack_proven": False,
            "one_tcp_packet_per_write_assumed": False,
            "device_command_sender_implemented": False,
            "network_or_device_calls_made": False,
        }


def header_source_words(payload_hint: int, addr: int) -> tuple[int, ...]:
    """Exactly eight Write EDX arguments in 0080937C.

    For queue-command call site 00807F40, payload_hint=ECX=2, not Cmd.
    Second word: ((payload_hint >> 1) + 8) * 4.
    Eighth word: (payload_hint << 16) + addr, modulo UInt32.
    """
    _source_u32(payload_hint, "source ECX")
    _source_u32(addr, "source EDX/Addr")
    if payload_hint > 0x1ffff:
        raise ValueError("Unknown large source request width")
    length_word = ((payload_hint >> 1) + 8) * 4
    if length_word > 0xffffffff:
        raise ValueError("Source write length overflow")
    return (
        SOURCE_HEADER,
        length_word,
        0, 0, 0, 0,
        1,
        ((payload_hint << 16) + addr) & 0xffffffff,
    )


def plan_verified_source_rate_command(
        command: OriginalCommandRecord) -> SourceWordCallPlan:
    """Only source-verified SetRate route, strictly offline call model."""
    if not isinstance(command, OriginalCommandRecord):
        raise TypeError("Expected original in-memory command record")
    if (command.cmd, command.addr) != (RATE_COMMAND, RATE_ADDRESS):
        raise ValueError("Only source-verified SetRate command supported")
    return SourceWordCallPlan(
        header_words=header_source_words(2, command.addr),
        additional_words=(command.data,),
        kind="ORIGINAL_SET_RATE_CALL_ARGUMENTS_ONLY",
    )
