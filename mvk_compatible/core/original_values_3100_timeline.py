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
from pathlib import Path
import re
import struct

PARAM = 0xFF800C0D
MAX_FRAME = 0x20000
MAX_RAW = 2048 * 1024 * 1024
MAX_EVENTS_PER_WINDOW = 64
MAX_WINDOWS = 8
RAW_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _counter(v: object, label: str, limit: int = (1 << 64) - 1) -> int:
    if type(v) is not int or not 0 <= v <= limit:
        raise ValueError(f"Original VALUES 0x3100: invalid {label}")
    return v


def _parameter_blocks(frame: bytes):
    """Bounded exact PARAM record layout also checked by Native Go."""
    if len(frame) < 32:
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

    digest = sha256()
    aux = 0
    ticks = 0
    read_total = 0
    with path.open("rb") as src:
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
            if frame_type != PARAM:
                continue
            blocks = list(_parameter_blocks(frame))
            if length == 4700:
                aux += 1
            triggers = [(words, data) for addr, words, data in blocks
                        if addr == 0x3100]
            if len(triggers) > 1:
                # Go currently counts at most one 0x3100 tick per frame.
                # Do not silently diverge from its own independently
                # authenticated frame-mark / summary counters.
                raise ValueError("Original VALUES 0x3100: repeated trigger in one PARAM")
            if triggers:
                words, raw = triggers[0]
                for number, begin, end in intervals:
                    if begin <= ticks < end:
                        chosen[number].append({
                            "source_tick_index": ticks,
                            "frame_index": frame_index,
                            "source_register_address": "0x3100",
                            "register_words": words,
                            "register_bytes_hex": raw.hex(),
                            "register_payload_sha256": sha256(raw).hexdigest(),
                            "latest_earlier_aux_index": aux - 1 if aux else None,
                            "source_values_is_not_aux_tick": True,
                        })
                ticks += 1
        final = src.read(MAX_FRAME)
        if len(final) != tail or src.read(1):
            raise ValueError("Original VALUES 0x3100: terminal RAW tail mismatched")
        digest.update(final)
        read_total += len(final)
    if (read_total != total or digest.hexdigest() != expected_sha256
            or ticks != final_ticks or aux != final_aux):
        raise ValueError("Original VALUES 0x3100: SHA/frame/AUX/trigger proof mismatch")
    for number, start, end in intervals:
        if len(chosen[number]) != end - start:
            raise ValueError("Original VALUES 0x3100: selected event gap")
    return chosen
