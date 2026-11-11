"""Stage111Z31BF: original TMvkCellList register-space reader (offline only).

Derived from private _Unit115.pas GetDword 007CF328, GetFloat 007CF360,
GetValueText 007CF4A4 and source constructors in _Unit125.pas.
The original Data pointer includes AddrOffset * 2, and a relative
register address R is accessed at Data + R * 2 (32-bit little endian).
This source fact is NOT a claim that arbitrary BIN/TSXML is a config
snapshot, or that a file contains current live device registers.

This module has no I/O, Qt, mutating operations or device commands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import struct

from .original_config_semantics import (
    AdvancedCell, MODBUS_ENDIAN, HF_MODE, section_fields,
)

SOURCE = "IDR_TMvkCellList_REGISTERS_BF"
MAX_LOCAL_REGISTER_IMAGE_BYTES = 131072
KNOWN_ADVANCED = {"modbus_endian": MODBUS_ENDIAN, "hf_mode": HF_MODE}


@dataclass(frozen=True)
class SourceEnumConstructor:
    kind: str
    source_key_prefix: str
    source_entry_count: int
    uses_composite: bool
    source_ids_recovered: bool

# _Unit125:00802EB7, 00802EEC, 00802F21, 00803FDB.
# The helper 0080250C builds labels PREFIX + "Cell" + IntToStr(ID)
# and consumes a private ID table. Only counts/key construction are
# independently proven; we do not guess table values from 0..N.
SOURCE_ENUM_CONSTRUCTORS = (
    SourceEnumConstructor("num_groups", "ConfigNumGroups", 2, False, False),
    SourceEnumConstructor("option", "Option", 4, False, False),
    SourceEnumConstructor("wifi_mode", "WifiMode", 3, False, False),
    SourceEnumConstructor("alarm_band", "AlarmBand", 4, False, False),
)


def extract_source_advanced_bits(raw_u32: int, bits: int, bit_start: int) -> int:
    """_Unit115:007CF4F6..007CF50D, 0 Bits = full original DWORD."""
    if type(raw_u32) is not int or not 0 <= raw_u32 <= 0xFFFFFFFF:
        raise ValueError("Source register must be UInt32")
    if (type(bits) is not int or type(bit_start) is not int
            or not 0 <= bits <= 32 or not 0 <= bit_start <= 31
            or (bits > 0 and bits + bit_start > 32)):
        raise ValueError("Invalid original bit field width/offset")
    if bits == 0:
        return raw_u32
    return (raw_u32 >> bit_start) & ((1 << bits) - 1)


@dataclass(frozen=True)
class LocalRegisterImage:
    """User-provided explicit register memory evidence, never live/authenticated."""
    data: bytes = field(repr=False)
    source_kind: str = "UNVERIFIED_EXPLICIT_LOCAL_REGISTER_IMAGE"

    @classmethod
    def from_bytes(cls, raw: bytes) -> "LocalRegisterImage":
        if (type(raw) is not bytes or len(raw) < 4
                or len(raw) > MAX_LOCAL_REGISTER_IMAGE_BYTES
                or len(raw) % 2):
            raise ValueError("Explicit bounded even-length register bytes required")
        return cls(raw)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    def read_u32(self, address: int) -> int:
        """Original 16-bit register address; 4-byte value starts at 2*addr."""
        if (type(address) is not int or address < 0 or address > 0xFFFE
                or address % 2):
            raise ValueError("An even source register address is required")
        offset = address * 2
        if offset + 4 > len(self.data):
            raise ValueError("Requested register not present in local image")
        return struct.unpack_from("<I", self.data, offset)[0]

    def read_f32(self, address: int) -> float:
        """No x87 arithmetic: exact Single storage reinterpretation."""
        bits = self.read_u32(address)
        return struct.unpack("<f", struct.pack("<I", bits))[0]

    def preview_source_field(self, section: str, row_index: int,
                             *, adc: int | None = None) -> dict:
        """Only proven raw types; passwords and long strings never exposed."""
        fields, base = section_fields(section, adc=adc)
        if type(row_index) is not int or not 0 <= row_index < len(fields):
            raise IndexError("No original config field at this row")
        original = fields[row_index]
        address = base + original.offset
        # Source SSID/Password types are long-field and cannot be decoded
        # from a single uint32, so no truncated/accidentally leaked string.
        sensitive = original.key == "ConfigWifiPassword"
        if sensitive or original.cell_type in (13, 14):
            return {
                "address": f"0x{address:04X}",
                "source_key": original.key,
                "source_type": original.cell_type,
                "raw_value": "REDACTED" if sensitive else "NOT_DECODED",
                "verified_live_device_value": False,
                "writable": False,
            }
        raw = self.read_u32(address)
        info = {
            "address": f"0x{address:04X}",
            "source_key": original.key,
            "source_type": original.cell_type,
            "raw_u32": f"0x{raw:08X}",
            "interpretation": "UNKNOWN_FORMAT",
            "verified_live_device_value": False,
            "writable": False,
        }
        if original.cell_type == 0:
            value = self.read_f32(address)
            info["interpretation"] = "SOURCE_FLOAT32_STORAGE"
            info["float32"] = (repr(value) if math.isfinite(value)
                               else "non-finite")
        elif original.cell_type == 10 and original.advanced in KNOWN_ADVANCED:
            known = KNOWN_ADVANCED[original.advanced]
            info["interpretation"] = "SOURCE_ADVANCED_ID"
            info["advanced_id"] = f"0x{raw:08X}"
            info["advanced_source_title"] = known.get_title_by_id(raw)
            info["original_translation_verified"] = False
        return info

    def report(self) -> dict:
        return {
            "source": SOURCE,
            "sha256": self.sha256,
            "source_kind": self.source_kind,
            "byte_length": len(self.data),
            "original_register_addr_to_byte_offset": "address * 2",
            "snapshot_is_live_device_verified": False,
            "original_win32_parity_verified": False,
            "device_io_supported": False,
            "device_writes_allowed": False,
        }
