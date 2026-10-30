"""Stage111U: original spectrum GraphDefaultVScale path (PRIVATE source-derived).

The original _Unit128 sub_0084B4E8 (0084B5D3..0084B882) first reads the
selected TMvkChannelStorage.FRange at +0x04. SpectrumType/Tag 2 multiplies
by 10, Tag 3 by 100; the others use FRange. Next the original calls
log10/trunc and base-10 power helpers, branches around log10(2)/log10(5),
and stores several intermediates/results as Single (32-bit float).

The underlying *algorithm structure* is source-verified. The helper's exact
x87 extended rounding, threshold equality, the true per-archive FRange and
original runtime GraphDefaultVScale are NOT verified. Do not substitute
this diagnostic for true Delphi reference measurements or DSP AUX4700.
"""
from __future__ import annotations
import math
import numbers
import struct
from decimal import Decimal

SOURCE = 'APP_DERIVED_ORIGINAL_SPECTRUM_GRAPH_DEFAULT_VSCALE_IDR_CANDIDATE'
MODE_MULTIPLIERS = (1, 1, 10, 100)
# Stage111W: directly read at VA 008C2028 in original PRIVATE IDR v3 .data.
# The on-disk initial CW does not authenticate Get8087CW during GraphDraw.
SOURCE_STATIC_X87_CW = 0x1332
_LOG2 = math.log10(2.0)
_LOG5 = math.log10(5.0)
_MAX_SINGLE = 3.4028234663852886e38


def _single(value: float) -> float:
    try:
        return struct.unpack('<f', struct.pack('<f', float(value)))[0]
    except (OverflowError, ValueError) as exc:
        raise ValueError('Value is not representable as finite Delphi Single') from exc


def _positive_single(value: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(field + ' must be a finite positive number')
    v = float(value)
    if not math.isfinite(v) or not 0 < v <= _MAX_SINGLE:
        raise ValueError(field + ' must be a finite positive Single')
    result = _single(v)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(field + ' underflows/overflows the original Single')
    return result


def _ideal_125_ceiling(value: float) -> float:
    """Independent exact rational 1/2/5 ceiling, NOT x87 reference."""
    dec = Decimal.from_float(value)
    decade = dec.adjusted()
    scale = Decimal(10) ** decade
    for multiplier in (1, 2, 5, 10):
        proposed = scale * multiplier
        if proposed >= dec:
            return float(proposed)
    raise AssertionError('Unreachable: 1/2/5/10 decade ceiling')


def spectrum_graph_default_vscale(f_range_candidate: float, spectrum_mode: int) -> dict:
    """Reconstruct source scale stage from an EXPLICIT, unverified FRange.

    Source arithmetic is approximated with Python float64 logs followed by
    Single stores. It must be compared to original x87 before certification.
    Spectrum mode 0=dB, 1=acceleration, 2=velocity, 3=displacement.
    """
    if (isinstance(spectrum_mode, bool) or
            not isinstance(spectrum_mode, numbers.Integral) or
            int(spectrum_mode) not in range(4)):
        raise ValueError('Spectrum mode must be original 0..3 integer')
    f_range = _positive_single(f_range_candidate, 'candidate channel FRange')
    factor = MODE_MULTIPLIERS[int(spectrum_mode)]
    multiplied = _positive_single(f_range * factor, 'mode-scaled FRange')
    log_value = math.log10(multiplied)
    decade_toward_zero = math.trunc(log_value)
    # Original 0084B65E: FSTP Single of log10(x)-TRUNC(log10(x)).
    fraction_single = _single(log_value - decade_toward_zero)
    if fraction_single > 0:
        shifted_decade = decade_toward_zero
        fraction_for_comparison = fraction_single
    else:
        shifted_decade = decade_toward_zero - 1
        fraction_for_comparison = _single(fraction_single + 1.0)
    if fraction_for_comparison < _LOG2:
        step = 2
    elif fraction_for_comparison < _LOG5:
        step = 5
    else:
        step = 10
    # Original code calls base-10 power and finally stores as Single.
    exponent = shifted_decade + math.log10(float(step))
    reconstructed = _positive_single(10.0 ** exponent, 'GraphDefaultVScale')
    ideal = _ideal_125_ceiling(multiplied)
    # The source uses 80-bit FYL2X, not Python float64 math.log10. For
    # example under the on-disk CW=0x1332, native log10(1000) can be a
    # positive 80-bit ULP above 3 while Python math.log10(1000)==3.
    # This marks numerical risk; it NEVER substitutes a measured Delphi
    # runtime output, FRange, or the unobserved process FPU control word.
    near_integer_decade = abs(log_value-round(log_value)) <= 1e-12
    near_step_threshold = min(
        abs(fraction_for_comparison-_LOG2),
        abs(fraction_for_comparison-_LOG5)) <= 2e-7
    return {
        'source': SOURCE,
        'spectrum_mode': int(spectrum_mode),
        'source_mode_multiplier': factor,
        'candidate_f_range_single': f_range,
        'mode_scaled_f_range_single': multiplied,
        'log10_truncated_toward_zero': decade_toward_zero,
        'fraction_after_single_store': fraction_single,
        'selected_nice_step': step,
        'candidate_graph_default_vscale_single': reconstructed,
        'independent_exact_125_ceiling': ideal,
        'ideal_matches_reconstructed_single': reconstructed == _single(ideal),
        'source_multiply_mode_and_125_branch_verified': True,
        'original_idr_static_initial_x87_cw_hex': f'0x{SOURCE_STATIC_X87_CW:04X}',
        'original_idr_static_initial_cw_verified': True,
        'original_idr_static_initial_pc': '64_bit',
        'original_idr_static_initial_rounding': 'nearest',
        'original_process_cw_at_spectrum_verified': False,
        'native_x87_extended_log10_integer_decade_risk': near_integer_decade,
        'native_x87_single_comparison_threshold_risk': near_step_threshold,
        'original_x87_boundary_requires_runtime_reference': (
            near_integer_decade or near_step_threshold),
        'local_f_range_is_original_channel_frange_verified': False,
        'original_math_helpers_x87_rounding_verified': False,
        'original_delphi_graph_default_vscale_numeric_parity_verified': False,
        'original_qt_y_canvas_parity_verified': False,
    }
