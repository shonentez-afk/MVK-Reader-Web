"""Exact original VALUES *trigger* timeline from one SHA-checked Native RAW.

Original private triple-source evidence:
  mvkview.idp + Projects.7z/_Unit125.pas + mvk_idr(1).sqlite.
  TMVKThread.Execute 008085A5..008085BD calls its values-row writer
  when a received PARAM descriptor has address 0x3100 and ValuesFile exists.
A 4700-byte AUX frame supplies a different counter; it is not a VALUES row.

This reads ONLY the operator's own local incoming.raw. No device socket,
writing to hardware, private source copies or claimed original CSV format.
The latest AUX index is only a correlated, earlier decoded snapshot,
NOT an assertion that Delphi GetValueText produced identical numbers.
"""
from __future__ import annotations

from hashlib import sha256
from contextlib import nullcontext
from dataclasses import dataclass
from .original_param_gate_proof import OriginalParamGateReader
from .original_local_tach_latch import TachGateReader,TACH_TYPE
from pathlib import Path
import re
import struct

PARAM = 0xFF800C0D
MAX_FRAME = 0x20000
MAX_RAW = 2048 * 1024 * 1024
MAX_EVENTS_PER_WINDOW = 64
MAX_WINDOWS = 8
RAW_SHA = re.compile(r"[0-9a-f]{64}\Z")
REGISTER_WORDS = 0x4000
MAX_PARAM_DESCRIPTORS = 4096


def max_source_values_ticks(frames: int, raw_bytes: int | None = None) -> int:
    """Conservative wire bound: envelope and every trigger cost >=8 bytes."""
    frame_limit = frames * MAX_PARAM_DESCRIPTORS
    if raw_bytes is None:
        return frame_limit
    return min(frame_limit, max(0, raw_bytes - frames * 8) // 8)


@dataclass(frozen=True)
class RegisterPrefixSnapshot:
    """Internal replay evidence; never serialized or exported as a register dump."""
    data: bytes
    valid: bytes
    current: bytes
    tach_projection: tuple | None = None

    def dword_hex(self, addr: int, *, current: bool = False) -> str | None:
        if self.tach_projection is not None and addr in (0x30fe,0x31fe):
            mask,value=self.tach_projection[(addr-0x30fe)//0x100]
            if mask:
                return value
        if not 0 <= addr < REGISTER_WORDS - 1:
            return None
        if not self.valid[addr] or not self.valid[addr + 1]:
            return None
        if current and (not self.current[addr] or not self.current[addr + 1]):
            return None
        return self.data[addr * 2:(addr + 2) * 2].hex()



def _counter(v: object, label: str, limit: int = (1 << 64) - 1) -> int:
    if type(v) is not int or not 0 <= v <= limit:
        raise ValueError(f"Original VALUES 0x3100: invalid {label}")
    return v


def _parameter_blocks(frame: bytes):
    """Bounded exact PARAM record layout also checked by Native Go."""
    # Delphi _Unit125:0080844F consumes an empty 28-byte PARAM as a
    # valid no-op, never as a fabricated 0x3100 event.
    if len(frame) < 28:
        raise ValueError("Original VALUES 0x3100: truncated PARAM")
    count = struct.unpack_from("<I", frame, 24)[0]
    if count > MAX_PARAM_DESCRIPTORS:
        raise ValueError("Original VALUES 0x3100: too many PARAM descriptors")
    pos = 28
    for _ in range(count):
        if pos + 4 > len(frame):
            raise ValueError("Original VALUES 0x3100: truncated descriptor")
        desc = struct.unpack_from("<I", frame, pos)[0]
        pos += 4
        addr, words = desc & 0xFFFF, desc >> 16
        end = pos + words * 2
        if (words == 0 or words % 2 or addr + words > 0x4000
                or end > len(frame)):
            raise ValueError("Original VALUES 0x3100: invalid register block")
        yield addr, words, frame[pos:end]
        pos = end
    if pos != len(frame):
        raise ValueError("Original VALUES 0x3100: trailing PARAM bytes")


def scan_original_values_3100(
    raw_path: Path | str, *, expected_sha256: str, expected_raw_bytes: int,
    expected_frames: int, expected_aux: int, expected_ticks: int,
    expected_tail_bytes: int, ranges: list[tuple[int, int, int]],
    param_gate_path: Path | str | None = None,
    expected_param_gate_sha256: str | None = None,
    expected_param_gate_records: int = 0,
    expected_frozen_param_frames: int = 0,
    expected_frozen_aux: int = 0,
    expected_frozen_values: int = 0,
    capture_register_prefix: bool = False,
    tach_gate_path: Path | str | None = None,
    expected_tach_gate_sha256: str | None = None,
    expected_tach_gate_records: int = 0,
) -> dict[int, list[dict]]:
    """Replay complete frames and collect only the chosen 0x3100 events.

    A range is (window number, start original tick count, end tick count).
    Frame mark counters refer to state BEFORE the next complete RX frame.
    Every raw byte including a permitted partial final frame participates
    in the original SHA, without changing or rewriting incoming.raw.
    """
    path = Path(raw_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original VALUES 0x3100: absent/linked RAW source")
    if not isinstance(expected_sha256, str) or not RAW_SHA.fullmatch(expected_sha256):
        raise ValueError("Original VALUES 0x3100: invalid RAW digest")
    total = _counter(expected_raw_bytes, "RAW size", MAX_RAW)
    frames = _counter(expected_frames, "frame count", total // 8)
    final_aux = _counter(expected_aux, "AUX count", frames)
    max_ticks = max_source_values_ticks(frames, total)
    final_ticks = _counter(expected_ticks, "source 0x3100 tick count", max_ticks)
    final_frozen_param = _counter(expected_frozen_param_frames, "frozen PARAM", frames)
    final_frozen_aux = _counter(expected_frozen_aux, "frozen AUX", frames)
    final_frozen_values = _counter(expected_frozen_values, "frozen VALUES", max_ticks)
    if (param_gate_path is None and
            (expected_param_gate_sha256 is not None or
             expected_param_gate_records or final_frozen_param or
             final_frozen_aux or final_frozen_values)):
        raise ValueError("Original VALUES 0x3100: Freeze requires verified PARAM gate")
    tail = _counter(expected_tail_bytes, "final incomplete tail", MAX_FRAME - 1)
    if path.stat().st_size != total:
        raise ValueError("Original VALUES 0x3100: RAW length changed")
    if type(ranges) is not list or len(ranges) > MAX_WINDOWS:
        raise ValueError("Original VALUES 0x3100: invalid selected intervals")
    chosen: dict[int, list[dict]] = {}
    for number, start, end in ranges:
        _counter(number, "window number", MAX_WINDOWS)
        _counter(start, "window start tick", final_ticks)
        _counter(end, "window end tick", final_ticks)
        if number == 0 or number in chosen or start > end or (
                end - start > MAX_EVENTS_PER_WINDOW):
            raise ValueError("Original VALUES 0x3100: invalid tick bounds")
        chosen[number] = []
    intervals = [(number, start, end) for number, start, end in ranges]
    if type(capture_register_prefix) is not bool:
        raise ValueError("Original VALUES 0x3100: invalid prefix proof flag")
    # Optional and bounded: only selected ticks retain immutable snapshots.
    register_data = bytearray(REGISTER_WORDS * 2) if capture_register_prefix else None
    register_valid = bytearray(REGISTER_WORDS) if capture_register_prefix else None

    digest = sha256()
    aux = 0
    ticks = 0
    read_total = 0
    frozen_param = 0
    frozen_aux = 0
    frozen_values = 0
    gate_context = (
        OriginalParamGateReader(
            param_gate_path,
            expected_sha256=expected_param_gate_sha256,
            expected_records=expected_param_gate_records,
            expected_frames=frames,
        ) if param_gate_path is not None else nullcontext(None)
    )
    if tach_gate_path is None and (expected_tach_gate_sha256 is not None or expected_tach_gate_records):
        raise ValueError("Source local TACH: missing gate path")
    if tach_gate_path is not None and param_gate_path is None:
        raise ValueError("Source local TACH: PARAM gate also required")
    tach_context=TachGateReader(tach_gate_path,
        expected_sha256=expected_tach_gate_sha256,
        expected_records=expected_tach_gate_records,
        expected_frames=frames) if tach_gate_path is not None else nullcontext(None)
    with path.open("rb") as src, gate_context as gate, tach_context as tach_gate:
        for frame_index in range(frames):
            header = src.read(8)
            if len(header) != 8:
                raise ValueError("Original VALUES 0x3100: early frame EOF")
            frame_type, length = struct.unpack("<II", header)
            if length < 8 or length % 4 or length > MAX_FRAME:
                raise ValueError("Original VALUES 0x3100: malformed frame size")
            payload = src.read(length - 8)
            if len(payload) != length - 8:
                raise ValueError("Original VALUES 0x3100: truncated frame body")
            frame = header + payload
            digest.update(frame)
            read_total += length
            if frame_type == TACH_TYPE and tach_gate is not None:
                tach_gate.consume(frame_index+1,frame)
            if frame_type != PARAM:
                continue
            blocks = list(_parameter_blocks(frame))
            trigger_count = sum(addr == 0x3100 for addr, _, _ in blocks)
            frozen = gate.consume(
                frame_index=frame_index + 1, frame=frame,
                descriptors=len(blocks), values3100_count=trigger_count,
            ) if gate is not None else False
            if frozen:
                # A frame excluded by the source gate contributes no live
                # rows, even with more than one trigger descriptor.
                frozen_param += bool(blocks)
                frozen_aux += (length == 4700)
                frozen_values += trigger_count
                continue
            needs_snapshot = capture_register_prefix and trigger_count and any(
                begin < ticks + trigger_count and ticks < end
                for _, begin, end in intervals)
            current = bytearray(REGISTER_WORDS) if needs_snapshot else None
            for descriptor_index, (addr, words, data) in enumerate(blocks):
                if tach_gate is not None:
                    tach_gate.state.block(addr, words)
                if capture_register_prefix:
                    end_addr = addr + words
                    register_data[addr * 2:end_addr * 2] = data
                    register_valid[addr:end_addr] = bytes([1]) * words
                    if current is not None:
                        current[addr:end_addr] = bytes([1]) * words
                if addr != 0x3100:
                    continue
                selected = [number for number, begin, end in intervals
                            if begin <= ticks < end]
                if selected:
                    event = {
                        "source_tick_index": ticks,
                        "frame_index": frame_index,
                        "source_param_descriptor_index": descriptor_index,
                        "source_values_3100_descriptor_count": trigger_count,
                        "source_register_address": "0x3100",
                        "register_words": words,
                        "register_bytes_hex": data.hex(),
                        "register_payload_sha256": sha256(data).hexdigest(),
                        "latest_earlier_aux_index": aux - 1 if aux else None,
                        "source_values_is_not_aux_tick": True,
                    }
                    if capture_register_prefix:
                        event["_register_prefix"] = RegisterPrefixSnapshot(
                            bytes(register_data), bytes(register_valid), bytes(current),
                            tach_gate.state.projection(register_data, register_valid)
                            if tach_gate is not None else None)
                    for number in selected:
                        chosen[number].append(event.copy())
                # The original projects TACH into each row before clearing
                # both DWORDs; later descriptors can then overwrite them.
                if tach_gate is not None:
                    tach_gate.state.tick()
                ticks += 1
            # AUX is decoded only after processing the entire PARAM. It is
            # not available as an earlier snapshot for its own triggers.
            if length == 4700:
                aux += 1
        final = src.read(MAX_FRAME)
        if len(final) != tail or src.read(1):
            raise ValueError("Original VALUES 0x3100: terminal RAW tail mismatched")
        digest.update(final)
        read_total += len(final)
        if gate is not None:
            gate.finish()
        if tach_gate is not None:
            tach_gate.finish()
    if (read_total != total or digest.hexdigest() != expected_sha256
            or ticks != final_ticks or aux != final_aux or
            frozen_param != final_frozen_param or
            frozen_aux != final_frozen_aux or
            frozen_values != final_frozen_values):
        raise ValueError("Original VALUES 0x3100: SHA/frame/AUX/trigger proof mismatch")
    for number, start, end in intervals:
        if len(chosen[number]) != end - start:
            raise ValueError("Original VALUES 0x3100: selected event gap")
    return chosen
