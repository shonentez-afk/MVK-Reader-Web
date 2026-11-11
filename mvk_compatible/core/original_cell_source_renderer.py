"""Stage111Z31BG: source TMvkCellList.GetValueText display dispatch, OFFLINE.

Derived from private IDR _Unit115:007CE6E4 and _Unit114:007B2224,
007B22E4, 007B2390, 007B2428, 007B27CC, 007B28F8, 007B29D4,
007B2D98. The cases below preserve the original switch topology and
byte width, not a claimed runtime or locale string parity. The original
float formatter, date conversion and non-ASCII ANSI codepage remain
unverified and are never silently emulated.

This is a bounded, side-effect-free decoder of a user-explicit local
register image. It does not read devices or issue config writes.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct

from .original_config_idp_tables import source_type_description
from .original_config_semantics import SOURCE_ADVANCED_OPTIONS, section_fields
from .original_config_register_image import (
    LocalRegisterImage, extract_source_advanced_bits,
)

SOURCE = "IDR_TMvkCellList_GetValueText_007CE6E4_STAGE111Z31BG"
UNKNOWN = "—"
# Jump-table group indexes transcribed from _Unit115:007CE718..007CE71F,
# indexed by exact original type 0..29.
SOURCE_DISPATCH_CASES = (
    1, 2, 3, 4, 6, 7, 8, 8, 9, 9, 10, 9, 5, 9, 9, 8,
    12, 12, 12, 12, 12, 12, 12, 12, 13, 13, 13, 13, 11, 10,
)
assert len(SOURCE_DISPATCH_CASES) == 30


@dataclass(frozen=True)
class RenderedSourceCell:
    register_address: int
    type_id: int
    source_format_char: str
    source_storage_bytes: int
    kind: str
    display: str
    source_branch_verified: bool
    original_runtime_text_verified: bool = False
    original_live_device_verified: bool = False
    mutable: bool = False

    def report(self) -> dict:
        return {
            "source": SOURCE,
            "register": f"0x{self.register_address:04X}",
            "type": self.type_id,
            "format_char": self.source_format_char,
            "size_bytes": self.source_storage_bytes,
            "kind": self.kind,
            "display": self.display,
            "source_branch_verified": self.source_branch_verified,
            "original_runtime_text_verified": self.original_runtime_text_verified,
            "original_live_device_verified": self.original_live_device_verified,
            "device_write_allowed": self.mutable,
        }


def _source_integer(raw: bytes) -> int:
    return struct.unpack_from("<I", raw, 0)[0]


def _ascii_until_zero(raw: bytes) -> tuple[str, bool]:
    text = raw.split(b"\x00", 1)[0]
    if any(byte < 32 or byte > 126 for byte in text):
        return UNKNOWN, False  # original Windows ANSI conversion is not proven
    return text.decode("ascii"), True


def render_source_cell(
    image: LocalRegisterImage, address: int, cell_type: int, *,
    key: str = "", advanced: str | None = None,
    bits: int = 0, bit_start: int = 0, sensitive: bool = False,
) -> RenderedSourceCell:
    """Read exactly original type width; no conversion from arbitrary BIN.

    source_branch_verified means the IDR switch target was identified,
    NOT that this output was compared with running Delphi. Advanced label
    strings are source KEY/fallback text, never verified translations.
    """
    if not isinstance(image, LocalRegisterImage):
        raise ValueError("Requires explicit local register-image evidence")
    if not isinstance(key, str) or len(key) > 128:
        raise ValueError("Invalid source cell key")
    spec = source_type_description(cell_type)
    if type(address) is not int or not 0 <= address <= 0xFFFE or address % 2:
        raise ValueError("Source cell address must be even UInt16 word")
    start = address * 2
    width = spec["source_storage_bytes"]
    if start + width > len(image.data):
        raise ValueError("Source cell extends beyond bounded local image")
    if type(sensitive) is not bool:
        raise ValueError("Sensitive marker must be explicit Boolean")
    # Always validate bit parameters, even for non-advanced cells.
    if (type(bits) is not int or type(bit_start) is not int
            or not 0 <= bits <= 32 or not 0 <= bit_start <= 31
            or (bits != 0 and bits + bit_start > 32)):
        raise ValueError("Invalid advanced bit-range")
    # Original layout: ConfigWifiPassword is a 64-byte cell. Never leak its
    # first DWORD, raw string, hex bytes or hashlib snippet into UI/QA logs.
    if sensitive or key == "ConfigWifiPassword":
        return RenderedSourceCell(address, cell_type, spec["format_char"],
                                  width, "sensitive-redacted", "••••••••",
                                  True)
    if advanced is not None and (
            not isinstance(advanced, str) or len(advanced) > 64):
        raise ValueError("Bad advanced selector kind")
    raw = memoryview(image.data)[start:start+width].tobytes()
    value = _source_integer(raw)
    case = SOURCE_DISPATCH_CASES[cell_type]
    kind = "unresolved"
    display = UNKNOWN
    branch_supported = True
    if case == 1:  # Delphi _Unit114:007B2090 special branches.
        number = struct.unpack("<f", raw[:4])[0]
        kind = "float32-storage"
        if (value & 0x7F800000) == 0x7F800000 and (
                value & 0x007FFFFF):
            # Source sub_007B1CC0 detects only NaN, not +/- infinity.
            display = "NAN"
        elif value & 0x7FFFFFFF == 0:
            # Original returns 0 also for negative zero.
            display = "0"
        elif math.isfinite(number):
            display = repr(number)
            branch_supported = False  # Delphi FormatFloat unverified
        else:
            display = "non-finite"
            branch_supported = False  # original INF formatting unknown
    elif case == 2:
        kind, display = "int32", str(struct.unpack("<i", raw[:4])[0])
    elif case == 3:
        kind, display = "uint32", str(value)
    elif case == 4:
        kind = "datetime-delphi-source-unresolved"
        branch_supported = False  # missing original DateTime helpers
    elif case == 5:
        kind = "hms-from-uint32-seconds"
        display = f"{value // 3600:02d}:{(value // 60) % 60:02d}:{value % 60:02d}"
    elif case == 6:
        kind, display = "hex-bytes-concatenated", raw[:16].hex().upper()
    elif case == 7:
        indexes = [str(bit) for bit in range(32) if value & (1 << bit)]
        kind, display = "set-bit-indexes", ",".join(indexes) if indexes else "---"
    elif case == 8:
        kind, display = "ipv4-source-network-order", ".".join(
            str((value >> shift) & 255) for shift in (24, 16, 8, 0))
    elif case == 9:
        kind = "ansi-nul-terminated"
        display, branch_supported = _ascii_until_zero(raw)
    elif case == 10:
        kind, display = "hex-uint32", f"0x{value:08X}"
    elif case == 11:
        kind, display = "hex-uint16", f"0x{value & 65535:04X}"
    elif case == 12:
        count = (cell_type - 16) * 4 + 4
        kind = "lsb-first-bits-nibble-spaces"
        display = "".join(
            ("1" if value & (1 << i) else "0") +
            (" " if i % 4 == 3 else "") for i in range(count))
    elif case == 13:
        count = cell_type - 24 + 1
        kind, display = "hex-bytes-spaced", "".join(
            f"{raw[i]:02X} " for i in range(count))
    else:
        branch_supported = False

    # The original overrides type-10 text with source AdvancedCell data.
    if cell_type == 10 and advanced in SOURCE_ADVANCED_OPTIONS:
        extracted = extract_source_advanced_bits(value, bits, bit_start)
        source_list = SOURCE_ADVANCED_OPTIONS[advanced]
        display = source_list.get_title_by_id(extracted)
        kind = "advanced-source-ID-untranslated-title"
        branch_supported = False  # numeric ID derived, runtime text not
    return RenderedSourceCell(address, cell_type, spec["format_char"],
                              width, kind, display, branch_supported)


def render_source_section(
    image: LocalRegisterImage, section: str, *, adc: int | None = None,
) -> tuple[dict, ...]:
    """Typed read-only decoder over source constructor order, 15/10/11."""
    fields, base = section_fields(section, adc=adc)
    return tuple(
        render_source_cell(
            image, base + f.offset, f.cell_type, key=f.key,
            advanced=f.advanced,
        ).report() | {"source_key": f.key, "source_suffix": f.suffix}
        for f in fields
    )
