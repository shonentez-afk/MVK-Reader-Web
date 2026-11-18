"""Original MVKView result-status GetValueText byte/ID reconstruction.

Original triple-source provenance, checked together:
- private mvkview.idp: TMvkCellList.GetValueText 007CF4A4,
  TMvkAdvancedCell.GetTitleByID 007D0808, 00804A97/00804AD3/00804B0F
- private Projects.7z/_Unit125.pas: original result constructor
- private mvk_idr(1).sqlite: indexed function/call sites

Per ADC, one verified instrument ResultStatus DWORD resides at
0x2000 + (adc-1)*0x200 + 0x120. Three TMvkCellList fields read the
SAME word: Overload bits[0:1], Buffers bits[4:7], Sensor bits[10:12].
No invented sensor-health conclusion or translated Delphi title.
No hardware, network I/O, register mutation, config secrets or DSP.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .original_config_register_image import extract_source_advanced_bits
from .original_config_semantics import SOURCE_ADVANCED_OPTIONS

SOURCE = "IDP_GETVALUETEXT_007CF4A4_RESULT_STATUS_00804A97_00804AD3_00804B0F"
STATUS_HEX = re.compile(r"0x[0-9A-Fa-f]{8}\Z")
FIELDS = (
    ("ResultOverload","result_overload",1,0),
    ("ResultBuffers","result_buffers",3,4),
    ("ResultSensorState","result_sensor_state",2,10),
)


@dataclass(frozen=True)
class SourceResultField:
    key: str
    kind: str
    bits: int
    bit_start: int
    numeric_id: int
    title_key: str

    def receipt(self) -> dict:
        return {
            "source_field": self.key,
            "source_advanced_kind": self.kind,
            "source_bits": self.bits,
            "source_bit_start": self.bit_start,
            "source_numeric_id": self.numeric_id,
            "source_get_title_by_id": self.title_key,
            "original_translated_title_verified": False,
        }


@dataclass(frozen=True)
class SourceResultStatus:
    adc: int
    source_register_word: int
    raw_uint32: int
    fields: tuple[SourceResultField, ...]
    source: str = SOURCE

    def field(self, key: str) -> SourceResultField:
        for field in self.fields:
            if field.key == key:
                return field
        raise KeyError("Unknown original ResultStatus selector")

    def receipt(self) -> dict:
        return {
            "source": self.source,
            "adc": self.adc,
            "source_register_word_address": f"0x{self.source_register_word:04X}",
            "source_raw_register_uint32": f"0x{self.raw_uint32:08X}",
            "original_selector_fields": [f.receipt() for f in self.fields],
            "original_get_value_text_bitfield_branch_verified": True,
            "original_delphi_localized_title_verified": False,
            "source_live_device_parity_verified": False,
            "device_commands_sent": False,
        }


def decode_source_result_status(raw: str | int, adc: int) -> SourceResultStatus:
    """Decode only an observed unsigned ResultStatus, never infer health.

    Caller must obtain the source word from a verified register snapshot.
    This function cannot itself attest the origin of a supplied value.
    """
    if type(adc) is not int or not 1 <= adc <= 8:
        raise ValueError("Original ResultStatus ADC must be 1..8")
    if type(raw) is str:
        if not STATUS_HEX.fullmatch(raw):
            raise ValueError("Original ResultStatus requires exact 8-hex DWORD")
        value = int(raw[2:], 16)
    elif type(raw) is int and 0 <= raw <= 0xFFFFFFFF:
        value = raw
    else:
        raise ValueError("Original ResultStatus requires observed UInt32")
    fields = tuple(SourceResultField(
        key=key, kind=kind, bits=width, bit_start=start,
        numeric_id=(code:=extract_source_advanced_bits(value,width,start)),
        title_key=SOURCE_ADVANCED_OPTIONS[kind].get_title_by_id(code),
    ) for key,kind,width,start in FIELDS)
    return SourceResultStatus(
        adc=adc,
        source_register_word=0x2000+(adc-1)*0x200+0x120,
        raw_uint32=value, fields=fields,
    )


def source_result_sensor_display(raw: str | int, adc: int) -> str:
    """Compact original status row without claiming Russian locale parity."""
    result=decode_source_result_status(raw,adc)
    sensor=result.field("ResultSensorState")
    return f"0x{result.raw_uint32:08X} · {sensor.title_key}"
