"""Stage111Z31BH: original TMvkCellList.InputValue -> LOCAL-ONLY draft.

Evidence: private _Unit115.pas 007CF624 (text InputValue), 007CFA2C
(AdvancedCellID), 007D0474 (SetBounds), 007D0564 (SetProtection),
007CED60 (30-case input dispatch); private _Unit114.pas conversion
helpers 007B24F0 (hex), 007B2688 (bits), 007B2AA0 (IPv4),
007B2C60 (contiguous prefix mask), 007B2E0C/007B2E8C (ANSI).

No device operations, network, disk writes, configuration upload or
original executable. All edits exist ONLY in an immutable Python
snapshot created explicitly from locally supplied unverified bytes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import re
import struct

from .original_config_idp_tables import source_type_description
from .original_config_semantics import (
    SOURCE_ADVANCED_OPTIONS, check_uint32, section_fields,
)
from .original_config_register_image import LocalRegisterImage

SOURCE = "IDR_TMvkCellList_INPUTVALUE_DRAFT_STAGE111Z31BH"
# Exact source jump table _Unit115:007CEDB8 for input, NOT display table.
SOURCE_INPUT_CASES = (
    1, 2, 3, 0, 0, 0, 5, 5, 7, 7, 11, 7, 4, 8, 8, 6,
    9, 9, 9, 9, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11,
)
# Original SetBounds and InputValue condition ~007CF68D / 007D04A5.
SOURCE_BOUND_TYPES = frozenset((0, 1, 2, 5, 10, *range(16, 30)))
SOURCE_DISPATCH_SHA256 = (
    "2e81b332909a4f65930cc193175ac5fdfc915d06c25821e0311733b9a5f9bccf"
)
assert len(SOURCE_INPUT_CASES) == 30
assert hashlib.sha256(bytes(SOURCE_INPUT_CASES)).hexdigest() == SOURCE_DISPATCH_SHA256
_DECIMAL = re.compile(r"[+-]?[0-9]+\Z", re.ASCII)
_HEX = re.compile(r"(?:0[xX])?[0-9A-Fa-f]{1,8}\Z", re.ASCII)
_IPV4 = re.compile(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}\Z", re.ASCII)


class SourceInputRejected(ValueError):
    """Named original localization key; never include input secrets."""
    def __init__(self, source_key: str):
        self.source_key = source_key
        super().__init__(source_key)


@dataclass(frozen=True)
class SourceInputPatch:
    address: int
    type_id: int
    source_key: str
    format_char: str
    payload: bytes = field(repr=False)
    mode: str = "text"
    source_validation: str = SOURCE
    original_runtime_parity_verified: bool = False
    device_write_allowed: bool = False

    def report(self) -> dict:
        return {
            "register": f"0x{self.address:04X}",
            "source_key": self.source_key,
            "type_id": self.type_id,
            "format_char": self.format_char,
            "patch_bytes": len(self.payload),
            "mode": self.mode,
            "payload_sha256": hashlib.sha256(self.payload).hexdigest(),
            "original_runtime_parity_verified": False,
            "device_write_allowed": False,
        }


def _parse_int32(text: str) -> int:
    # Conservative StrToInt subset. Delphi accepts locale-specific input
    # that is intentionally NOT attributed to original runtime here.
    if not _DECIMAL.fullmatch(text):
        raise SourceInputRejected("ctInvalidFormat")
    value = int(text)
    if not -(1 << 31) <= value < (1 << 31):
        raise SourceInputRejected("ctInvalidFormat")
    return value


def _parse_uint32_hex(text: str) -> int:
    # _Unit114:007B24F0 accepts at most eight hexadecimal digits, with
    # optional 0x/0X prefix. Do not confuse with decimal StrToInt.
    if not _HEX.fullmatch(text):
        raise SourceInputRejected("ctInvalidFormat")
    return int(text[2:] if text.lower().startswith("0x") else text, 16)


def _parse_ipv4(text: str) -> int:
    if not _IPV4.fullmatch(text):
        raise SourceInputRejected("ctInvalidFormat")
    parts = [int(p) for p in text.split(".")]
    if len(parts) != 4 or any(p > 255 for p in parts):
        raise SourceInputRejected("ctInvalidFormat")
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]


def _is_source_prefix_mask(value: int) -> bool:
    # _Unit114:007B2C60: LSB must be zero; some trailing zero bits,
    # then consecutive 1 bits extending ALL the way through MSB.
    # Original rejects 0.0.0.0 (/0) and 255.255.255.255 (/32).
    if value == 0 or value == 0xffffffff or value & 1:
        return False
    complement = (~value) & 0xffffffff
    return (complement & (complement + 1)) == 0


def _ascii_buffer(text: str, width: int, terminator: bool) -> bytes:
    # Original ANSI depends on Windows process code page. ASCII is a
    # source-compatible subset; arbitrary UTF-8 or CP1251 is NOT guessed.
    if "\x00" in text or any(ord(x) < 32 or ord(x) > 126 for x in text):
        raise SourceInputRejected("ctInvalidFormat")
    value = text.encode("ascii")
    capacity = width - int(terminator)
    return value[:capacity].ljust(capacity, b"\x00") + (
        b"\x00" if terminator else b""
    )


def _source_numeric_bounds(type_id: int, payload: bytes,
                           bounds: tuple[str, str] | None) -> None:
    if bounds is None:
        return
    if type_id not in SOURCE_BOUND_TYPES:
        raise SourceInputRejected("ctNoMinMaxSupported")
    lo, hi = bounds
    if type_id == 0:
        value = struct.unpack("<f", payload)[0]
        if not math.isfinite(value):
            raise SourceInputRejected("ctInvalidFormat")
        try:
            low = struct.unpack("<f", struct.pack("<f", float(lo)))[0]
            high = struct.unpack("<f", struct.pack("<f", float(hi)))[0]
        except (ValueError, OverflowError, struct.error) as exc:
            raise SourceInputRejected("ctInvalidFormat") from exc
    elif type_id == 1:
        value = struct.unpack("<i", payload[:4])[0]
        low, high = _parse_int32(lo), _parse_int32(hi)
    else:
        value = struct.unpack("<I", payload[:4])[0]
        # Source SetBounds unsigned branch uses DWORD values.
        # For decimal bounds, negative StrToInt is reinterpreted uint32.
        low, high = _parse_int32(lo) & 0xffffffff, _parse_int32(hi) & 0xffffffff
    # Original comparison order: TooBig first, then TooSmall.
    if value > high:
        raise SourceInputRejected("ctTooBig")
    if value < low:
        raise SourceInputRejected("ctTooSmall")


def encode_source_text(
    cell_type: int, text: str, *,
    bounds: tuple[str, str] | None = None,
    protected: bool = False,
    sensitive: bool = False,
) -> bytes:
    """Source-constrained text input; does NOT call any device or write disk."""
    if type(protected) is not bool or type(sensitive) is not bool:
        raise SourceInputRejected("ctInvalidFormat")
    if protected or sensitive:
        raise SourceInputRejected("ctProtectedValue")
    try:
        info = source_type_description(cell_type)
    except ValueError as exc:
        raise SourceInputRejected("ctInvalidCellType") from exc
    if not isinstance(text, str) or len(text) > 4096:
        raise SourceInputRejected("ctInvalidFormat")
    case = SOURCE_INPUT_CASES[cell_type]
    width = info["source_storage_bytes"]
    if not case:
        raise SourceInputRejected("ctNoEntrySupported")
    try:
        if case == 1:
            # Narrow explicit dot-decimal Float32 subset of StrToFloat.
            if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
                raise SourceInputRejected("ctInvalidFormat")
            value = float(text)
            if not math.isfinite(value):
                raise SourceInputRejected("ctInvalidFormat")
            payload = struct.pack("<f", value)
        elif case in (2, 3):
            payload = struct.pack("<i", _parse_int32(text))
        elif case in (4, 5, 6):
            number = _parse_ipv4(text)
            if case == 6 and not _is_source_prefix_mask(number):
                raise SourceInputRejected("ctInvalidFormat")
            payload = struct.pack("<I", number)
        elif case in (7, 8):
            payload = _ascii_buffer(text, width, terminator=(case == 8))
        elif case == 9:
            if not 1 <= len(text) <= 32 or any(c not in " 01" for c in text):
                raise SourceInputRejected("ctInvalidFormat")
            weight = 1
            number = 0
            for c in text:
                if c == "1":
                    number |= weight
                    weight <<= 1
                elif c == "0":
                    weight <<= 1
            if number >= 1 << 32:
                raise SourceInputRejected("ctInvalidFormat")
            payload = struct.pack("<I", number)
        elif case in (10, 11):
            payload = struct.pack("<I", _parse_uint32_hex(text))
        else:
            raise SourceInputRejected("ctNoEntrySupported")
    except (OverflowError, struct.error, UnicodeError) as exc:
        raise SourceInputRejected("ctInvalidFormat") from exc
    if len(payload) != width:
        raise SourceInputRejected("ctInvalidCellType")
    _source_numeric_bounds(cell_type, payload, bounds)
    return payload


def _field_contract(section: str, row: int, adc: int | None):
    fields, base = section_fields(section, adc=adc)
    if type(row) is not int or not 0 <= row < len(fields):
        raise SourceInputRejected("ctIndexOutOfBounds")
    f = fields[row]
    return f, base + f.offset


@dataclass(frozen=True)
class LocalConfigDraft:
    """Immutable overlay; no persist/commit/upload/save API by design."""
    original: LocalRegisterImage = field(repr=False)
    patches: tuple[SourceInputPatch, ...] = ()

    @classmethod
    def from_local_image(cls, image: LocalRegisterImage) -> "LocalConfigDraft":
        if not isinstance(image, LocalRegisterImage):
            raise ValueError("An explicit local register image is required")
        return cls(image)

    def _record(self, address: int, f, blob: bytes, mode: str):
        first = address * 2
        last = first + len(blob)
        if first < 0 or last > len(self.original.data):
            raise SourceInputRejected("ctInvalidAddress")
        # Reject aliased ranges from separate cells, including adjacent
        # long ASCII fields. Editing same address replaces old local patch.
        for previous in self.patches:
            prev_first = previous.address * 2
            prev_last = prev_first + len(previous.payload)
            if previous.address != address and (
                max(first, prev_first) < min(last, prev_last)
            ):
                raise SourceInputRejected("ctInvalidAddress")
        patch = SourceInputPatch(
            address=address, type_id=f.cell_type, source_key=f.key,
            format_char=source_type_description(f.cell_type)["format_char"],
            payload=blob, mode=mode,
        )
        return LocalConfigDraft(
            self.original,
            tuple(p for p in self.patches if p.address != address) + (patch,),
        )

    def preview_text(self, section: str, row: int, text: str, *,
                     adc: int | None = None, protected: bool = False):
        f, address = _field_contract(section, row, adc)
        blob = encode_source_text(
            f.cell_type, text, bounds=f.bounds, protected=protected,
            sensitive=(f.key == "ConfigWifiPassword"))
        return self._record(address, f, blob, "text")

    def preview_advanced_id(self, section: str, row: int, selected_id: int, *,
                            adc: int | None = None, protected: bool = False):
        f, address = _field_contract(section, row, adc)
        if protected:
            raise SourceInputRejected("ctProtectedValue")
        # Source 007CFA2C verifies advanced pointer and type=10, then
        # writes supplied DWORD. It does NOT call GetIndexByID.
        if f.cell_type != 10 or f.advanced not in SOURCE_ADVANCED_OPTIONS:
            raise SourceInputRejected("ctInvalidCellType")
        try:
            check_uint32(selected_id)
        except ValueError as exc:
            raise SourceInputRejected("ctInvalidFormat") from exc
        return self._record(
            address, f, struct.pack("<I", selected_id), "advanced-id")

    def as_local_image(self) -> LocalRegisterImage:
        copy = bytearray(self.original.data)
        for item in self.patches:
            start = item.address * 2
            copy[start:start + len(item.payload)] = item.payload
        # Always new bytes. The user's original input remains untouched.
        return LocalRegisterImage.from_bytes(bytes(copy))

    def summary(self) -> dict:
        return {
            "source": SOURCE,
            "original_local_image_sha256": self.original.sha256,
            "preview_image_sha256": self.as_local_image().sha256,
            "patch_count": len(self.patches),
            "patches": [item.report() for item in self.patches],
            "original_input_was_modified": False,
            "original_runtime_input_parity_verified": False,
            "source_language_format_settings_verified": False,
            "device_write_allowed": False,
            "disk_write_performed": False,
        }
