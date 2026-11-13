"""Stage111Z31CK: source mvkeditform.bRecalcClick 008404E8, offline-only.

Operator-private _Unit128.pas: StrToFloat -> Float32 -> multiply by
Extended constant 0.00010194 -> Float32 -> FloatToStr. Exact original
Win32 x87/RTL locale and FloatToStr tie rounding remain unverified.
Neither source file nor device is changed by this pure function.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
import struct

SOURCE = "SOURCE_DERIVED_MVKEDITFORM_RECALC_008404E8_STAGE111Z31CK"
SOURCE_FACTOR_DECIMAL = Decimal("0.00010194")


def _as_float32(value):
    try:
        result = struct.unpack("<f", struct.pack("<f", float(value)))[0]
    except (OverflowError, ValueError, struct.error) as exc:
        raise ValueError("Out-of-range source Float32 sensitivity") from exc
    if not math.isfinite(result):
        raise ValueError("Non-finite source Float32 sensitivity")
    return result


@dataclass(frozen=True)
class SourceSensitivityConversion:
    source: str
    original_text: str
    original_single: float
    source_factor: str
    converted_single: float
    formatted_candidate: str
    original_x87_extended_parity_verified: bool = False
    original_delphi_float_to_str_parity_verified: bool = False
    configuration_mutated: bool = False
    instrument_write_sent: bool = False


def source_recalc_millivolt_g(text):
    """The original arithmetic boundary with a locale-explicit candidate.

    Accept one decimal dot OR comma. Reject thousand grouping, arbitrary
    expressions, nonfinite values and invalid numeric types. No app state.
    """
    if not isinstance(text, str) or not 1 <= len(text) <= 80:
        raise ValueError("Original sensitivity must be a bounded text value")
    stripped = text.strip()
    if (not stripped or stripped.count(",") > 1
            or ("," in stripped and "." in stripped)
            or any(ch not in "+-0123456789,.eE" for ch in stripped)):
        raise ValueError("Original sensitivity must be a decimal number")
    try:
        original = Decimal(stripped.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Invalid original sensitivity decimal") from exc
    if not original.is_finite():
        raise ValueError("Nonfinite original sensitivity cannot be converted")
    single = _as_float32(float(original))
    converted = _as_float32(
        float(Decimal.from_float(single) * SOURCE_FACTOR_DECIMAL))
    formatted = format(converted, ".9g")
    if "," in stripped:
        formatted = formatted.replace(".", ",")
    return SourceSensitivityConversion(
        source=SOURCE, original_text=text, original_single=single,
        source_factor=str(SOURCE_FACTOR_DECIMAL),
        converted_single=converted, formatted_candidate=formatted)
