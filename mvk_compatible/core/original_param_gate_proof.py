"""Bounded verification of original PARAM FreezeUpdate per-frame provenance.

The real source RX gate exists in the Go Task2 reader, not the immutable
TCP byte stream. Delphi _Unit125.pas 0080850C..008085E1 drains PARAM bytes
on Freeze without applying values. A post-hoc RAW-only replay cannot
reconstruct local operator Freeze timing. Use a separate SHA-verified,
frame-SHA-tied Go ledger, or refuse to claim exact original VALUES timing.

Private mvkview.idp/Projects.7z/mvk_idr(1).sqlite are the research evidence;
none of their bytes are embedded here. No device connections or commands.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

SOURCE_PARAM_GATE_NAME = "SOURCE_ORIGINAL_PARAM_FRAME_GATE.jsonl"
SOURCE_PARAM_GATE_SCHEMA = "MVK_SOURCE_ORIGINAL_PARAM_GATE_V1"
MAX_PARAM_GATE_BYTES = 384 * 1024 * 1024
MAX_PARAM_GATE_RECORDS = 1_000_000
MAX_PARAM_GATE_LINE = 512
SHA = re.compile(r"[0-9a-f]{64}\Z")


class OriginalParamGateReader:
    """Constant-memory, fail-closed replay against the exact RAW PARAM order."""

    def __init__(self, path: Path | str, *, expected_sha256: str,
                 expected_records: int, expected_frames: int):
        self.path = Path(path)
        if (self.path.is_symlink() or not self.path.is_file()
                or self.path.stat().st_size > MAX_PARAM_GATE_BYTES):
            raise ValueError("Original PARAM gate: missing, linked or oversized file")
        if type(expected_sha256) is not str or not SHA.fullmatch(expected_sha256):
            raise ValueError("Original PARAM gate: invalid SHA")
        if (type(expected_records) is not int
                or not 0 <= expected_records <= MAX_PARAM_GATE_RECORDS
                or type(expected_frames) is not int or expected_frames < 0
                or expected_records > expected_frames):
            raise ValueError("Original PARAM gate: impossible frame/record count")
        self.expected_sha256 = expected_sha256
        self.expected_records = expected_records
        self.expected_frames = expected_frames
        self.digest = sha256()
        self.count = 0
        self.last_index = 0
        self.file = None

    def __enter__(self):
        self.file = self.path.open("rb")
        return self

    def __exit__(self, *_):
        if self.file is not None:
            self.file.close()
        self.file = None

    def consume(self, *, frame_index: int, frame: bytes,
                descriptors: int, values3100_count: int) -> bool:
        if self.file is None:
            raise ValueError("Original PARAM gate: reader not opened")
        raw = self.file.readline(MAX_PARAM_GATE_LINE + 1)
        if (not raw or len(raw) > MAX_PARAM_GATE_LINE
                or not raw.endswith(b"\n")):
            raise ValueError("Original PARAM gate: missing/oversized event")
        self.digest.update(raw)
        self.count += 1
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Original PARAM gate: invalid JSON") from exc
        fields = {
            "schema", "frame_index_one_based", "frame_sha256",
            "descriptor_count", "freeze_update", "is_aux4700",
            "contains_values_3100"
        }
        count_field = "source_values_3100_descriptor_count"
        if not isinstance(record, dict) or set(record) not in (fields, fields | {count_field}):
            raise ValueError("Original PARAM gate: unknown or partial fields")
        # Legacy evidence only encoded a flag. This is sufficient when a
        # frame contains at most one trigger; repeated triggers require the
        # new independent count, not a silently equivalent-looking flag.
        count = record.get(count_field, int(bool(values3100_count)))
        if type(count) is not int or count != values3100_count:
            raise ValueError("Original PARAM gate: trigger descriptor count contradicts RAW")
        index = record["frame_index_one_based"]
        digest = record["frame_sha256"]
        frozen = record["freeze_update"]
        if (record["schema"] != SOURCE_PARAM_GATE_SCHEMA
                or type(index) is not int or index != frame_index
                or index <= self.last_index or index > self.expected_frames
                or type(digest) is not str or not SHA.fullmatch(digest)
                or digest != sha256(frame).hexdigest()
                or type(record["descriptor_count"]) is not int
                or record["descriptor_count"] != descriptors
                or type(frozen) is not bool
                or type(record["is_aux4700"]) is not bool
                or record["is_aux4700"] != (len(frame) == 4700)
                or type(record["contains_values_3100"]) is not bool
                or record["contains_values_3100"] != bool(values3100_count)):
            raise ValueError("Original PARAM gate: event contradicts RAW")
        self.last_index = index
        return frozen

    def finish(self):
        if self.file is None:
            raise ValueError("Original PARAM gate: reader not opened")
        if (self.file.read(1) or self.count != self.expected_records
                or self.digest.hexdigest() != self.expected_sha256):
            raise ValueError("Original PARAM gate: extra entries/count/SHA mismatch")
        return {"verified_source_param_gate_records": self.count,
                "verified_source_param_gate_sha256": self.expected_sha256}
