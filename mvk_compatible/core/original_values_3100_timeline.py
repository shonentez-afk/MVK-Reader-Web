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
from .original_tach_gate_proof import OriginalTachGateReader, TACH, apply_tach_bytes, set_latch
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


@dataclass(frozen=True)
class RegisterPrefixSnapshot:
    """Internal replay evidence; never serialized or exported as a register dump."""
    data: bytes
    valid: bytes
    current: bytes
    tach_latch: bool = False

    def dword_hex(self, addr: int, *, current: bool = False) -> str | None:
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
    if count > 4096:
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
    final_ticks = _counter(expected_ticks, "source 0x3100 tick count", frames)
    final_frozen_param = _counter(expected_frozen_param_frames, "frozen PARAM", frames)
    final_frozen_aux = _counter(expected_frozen_aux, "frozen AUX", frames)
    final_frozen_values = _counter(expected_frozen_values, "frozen VALUES", frames)
    if (param_gate_path is None and
            (expected_param_gate_sha256 is not None or
             expected_param_gate_records or final_frozen_param or
             final_frozen_aux or final_frozen_values)):
        raise ValueError("Original VALUES 0x3100: Freeze requires verified PARAM gate")
    if (tach_gate_path is None and (expected_tach_gate_sha256 is not None or expected_tach_gate_records)
            or tach_gate_path is not None and param_gate_path is None):
        raise ValueError("Original TACH gate: requires complete TACH and PARAM evidence")
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
    tach_context = (OriginalTachGateReader(tach_gate_path, expected_sha256=expected_tach_gate_sha256,
                    expected_records=expected_tach_gate_records, expected_frames=frames)
                    if tach_gate_path is not None else nullcontext(None))
    last_tach = [0, 0]
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
            if frame_type == TACH and tach_gate is not None:
                channel, admitted = tach_gate.consume(frame_index=frame_index + 1, frame=frame)
                if admitted and capture_register_prefix:
                    apply_tach_bytes(register_data, register_valid, last_tach, channel, frame[28:])
            if frame_type != PARAM:
                continue
            blocks = list(_parameter_blocks(frame))
            triggers = [(words, data) for addr, words, data in blocks
                        if addr == 0x3100]
            if len(triggers) > 1:
                # Go currently counts at most one 0x3100 tick per frame.
                # Do not silently diverge from its own independently
                # authenticated frame-mark / summary counters.
                raise ValueError("Original VALUES 0x3100: repeated trigger in one PARAM")
            frozen = gate.consume(
                frame_index=frame_index + 1, frame=frame,
                descriptors=len(blocks), values3100=bool(triggers),
            ) if gate is not None else False
            if frozen:
                # Original _Unit125:0080850C reads and discards each
                # PARAM block while frozen; RAW remains unchanged, but
                # neither AUX nor 0x3100 advances any VALUES counter.
                frozen_param += bool(blocks)
                frozen_aux += (length == 4700)
                frozen_values += bool(triggers)
                continue
            prefix = None
            if capture_register_prefix:
                selected = bool(triggers) and any(
                    begin <= ticks < end for _, begin, end in intervals)
                current = bytearray(REGISTER_WORDS) if selected else None
                for addr, count, block in blocks:
                    end_addr = addr + count
                    register_data[addr * 2:end_addr * 2] = block
                    register_valid[addr:end_addr] = bytes([1]) * count
                    if current is not None:
                        current[addr:end_addr] = bytes([1]) * count
                        if addr == 0x3100:
                            prefix = RegisterPrefixSnapshot(
                                bytes(register_data), bytes(register_valid), bytes(current),
                                tach_latch=tach_gate is not None)
                            current = None
                    # Reset after inclusive snapshot, even when no writer is open.
                    if addr == 0x3100 and tach_gate is not None:
                        set_latch(register_data, register_valid, 0, 0)
                        set_latch(register_data, register_valid, 1, 0)
            if length == 4700:
                aux += 1
            if triggers:
                words, raw = triggers[0]
                for number, begin, end in intervals:
                    if begin <= ticks < end:
                        event = {
                            "source_tick_index": ticks,
                            "frame_index": frame_index,
                            "source_register_address": "0x3100",
                            "register_words": words,
                            "register_bytes_hex": raw.hex(),
                            "register_payload_sha256": sha256(raw).hexdigest(),
                            "latest_earlier_aux_index": aux - 1 if aux else None,
                            "source_values_is_not_aux_tick": True,
                        }
                        if capture_register_prefix:
                            if prefix is None:
                                raise ValueError("Original VALUES 0x3100: missing prefix proof")
                            event["_register_prefix"] = prefix
                        chosen[number].append(event)
                ticks += 1
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
