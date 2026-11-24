"""Strict local IPC metadata for source physical Float32 storage.

Only the observed normal positive finite Single path is accepted.
This validates consistency, not physical calibration or Delphi runtime.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import struct

METADATA_DOMAIN = "ORIGINAL_LIVE_ADC_LATCHED_RANGE_FLOAT32"
LEGACY_DOMAIN = "ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32"


@dataclass(frozen=True)
class SourceADCMetadata:
    socket_epoch: int
    from_descriptor: bool
    range_raw_bits: int
    range_current_socket: bool
    units_known: bool
    units: str
    units_current_socket: bool

    @property
    def factor(self):
        f = struct.unpack("<f", struct.pack("<I", self.range_raw_bits))[0]
        return 1.0 if f == 0 else f

    def wire(self):
        return asdict(self)


def parse_source_adc_metadata(obj):
    if (not isinstance(obj, dict) or set(obj) != set(SourceADCMetadata.__annotations__)):
        raise ValueError("Source ADC metadata: invalid fields")
    m = SourceADCMetadata(**obj)
    if (type(m.socket_epoch) is not int or not 1 <= m.socket_epoch < 1 << 64 or
            type(m.range_raw_bits) is not int or not 0 <= m.range_raw_bits < 1 << 32 or
            any(type(getattr(m, key)) is not bool for key in
                ("from_descriptor", "range_current_socket", "units_known", "units_current_socket")) or
            type(m.units) is not str or len(m.units) > 32 or
            any(not 1 <= ord(c) <= 255 for c in m.units) or
            (not m.units_known and (m.units or m.units_current_socket)) or
            (not m.from_descriptor and (m.range_current_socket or m.units_current_socket)) or
            (m.socket_epoch == 1 and not m.from_descriptor and
                (m.range_raw_bits != 0x3f800000 or m.units != "" or not m.units_known)) or
            not math.isfinite(m.factor) or m.factor <= 0):
        raise ValueError("Source ADC metadata: invalid factor/units/epoch")
    return m


def metadata_for_ring_row(row):
    domain = row.get("input_domain")
    if domain == LEGACY_DOMAIN:
        if row.get("original_live_f_range_single") != 1.0 or row.get("source_adc_metadata") is not None:
            raise ValueError("Original live FRange: invalid legacy Single 1.0")
        return None
    if domain == METADATA_DOMAIN:
        if row.get("source_adc_metadata") is None:
            raise ValueError("Source ADC metadata: missing valid current range")
        return parse_source_adc_metadata(row["source_adc_metadata"])
    raise ValueError("Source ADC metadata: foreign storage domain")


def source_derived_units(metadata, mode=None):
    """Original 007D1268: base units, special acceleration, else ~ / ~~ suffix.

    Log plot label is dB; its underlying base/summary unit remains FUnits.
    Unknown/empty is not silently labelled m/s2 in the new metadata domain.
    """
    if metadata is None:
        return ("м/с²" if mode is None else ("дБ", "м/с²", "мм/с", "мкм")[mode])
    if mode == 0:
        return "дБ"
    if not metadata.units_known:
        return "ед. неизвестны"
    unit = metadata.units
    if mode is None or mode == 1:
        return unit
    # 0042AA10 only maps ASCII A..Z to lower case; do not translate or
    # silently interpret a different byte string as acceleration.
    if unit == "м/с2":
        return "мм/с" if mode == 2 else "мкм"
    return unit + ("~" if mode == 2 else "~~")
