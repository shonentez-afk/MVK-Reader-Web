"""Stage111Z31BN: original-source vertical viewport for current SHA-bound spectrum.

Core-only reconstruction of _Unit128 0084B5D3..B882 (FRange/GraphDefaultVScale)
and 0084C5AC..C748 / 0084C770..C800 (mode page, vertical scrollbar,
TQGrapher ScrHeight/ScrBottom). No Qt, device access, invented calibration,
proprietary Pascal or original test measurement is distributed.

Explicit source scopes:
* original same-window Power/Y + SHA-bound visible FFT (operator attestation)
* positive current-channel TSXML InternalChannelGain (static loader candidate)
* mode 0 dB menu geometry independent of any FRange
* linear mode with no source-backed FRange remains in Qt research fallback
"""
from __future__ import annotations

import hashlib
import math
import struct

import numpy as np

from .offline_measurement_flow import OfflineMeasurementFlow
from .original_spectrum_view_binding import (
    SourceSpectrumGain, SOURCE_GAIN, source_spectrum_gain,
)
from .mvk_spectrum_menu_runtime_idr_candidate import source_vertical_page
from .tqgrapher_spectrum_scroll_idr_candidate import source_spectrum_v_scr
from .spectrum_graph_default_vscale_idr_candidate import spectrum_graph_default_vscale

SOURCE = "MVK_SOURCE_BOUND_SPECTRUM_VERTICAL_VIEW_STAGE111Z31BN"
PAIR_SCHEMA = "MVKVIEW_VISIBLE_ORIGINAL_SAME_WINDOW_PAIR_V1"
ORIGIN_PAIRED = "OPERATOR_ASSERTED_SAME_WINDOW_ORIGINAL_POWER_Y"
ORIGIN_TSXML = "POSITIVE_CURRENT_CHANNEL_TSXML_FRANGE_STATIC_CANDIDATE"
ORIGIN_DB = "ORIGINAL_DB_FIXED_RANGE_INDEPENDENT_OF_FRANGE"


def _f32_bits(value: float) -> int:
    scalar = float(value)
    if not math.isfinite(scalar) or scalar <= 0:
        raise ValueError("Source FRange must be finite and positive")
    raw = struct.pack("<f", scalar)
    word = struct.unpack("<I", raw)[0]
    if (word & 0x7F800000) == 0x7F800000 or word == 0:
        raise ValueError("Source FRange not representable as positive Single")
    return word


def source_spectrum_vertical_view(
    flow: OfflineMeasurementFlow,
    spectrum: dict, choice: dict, *,
    source_gain: SourceSpectrumGain | None = None,
    visible_pair: dict | None = None,
) -> dict | None:
    """Resolve exact source menu page + viewport against one selected BIN.

    Returns None ONLY for non-dB without any source-backed positive FRange;
    Qt may then use its explicitly labelled approximate local-data baseline.
    A stale/forged pair or wrong selected ADC is rejected, never used to anchor
    an original-looking Y axis. We NEVER multiply original waveform or FFT.
    """
    if type(flow) is not OfflineMeasurementFlow or type(spectrum) is not dict:
        raise ValueError("Current checked offline FFT flow required")
    mode = spectrum.get("mode")
    if type(mode) is not int or mode not in range(4):
        raise ValueError("Current spectrum Tag0..3 required")
    current = source_spectrum_gain(flow, spectrum, mode=mode)
    source = flow.source_record()
    if spectrum.get("channel") != flow.channel:
        raise ValueError("Vertical axis selected another ADC")
    if source_gain is not None:
        if (not isinstance(source_gain, SourceSpectrumGain)
                or source_gain.channel != flow.channel
                or source_gain.source_bin_sha256 != source["source_bin_sha256"]
                or source_gain.spectrum_mode != mode
                or source_gain.frange_single != current.frange_single
                or source_gain.origin != current.origin):
            raise ValueError("Stale source FRange or wrong BIN/ADC for this axis")

    if not isinstance(choice, dict):
        raise ValueError("Native original vertical menu selection required")
    tag = choice.get("source_menu_tag")
    if type(tag) is not int:
        raise ValueError("Original V scale Tag must be integer")
    required = source_vertical_page(mode, tag)
    full, page = required["full"], required["page"]
    position = choice.get("delphi_position")
    if (type(position) is not int or not 0 <= position <= full-page
            or choice.get("page") != page or choice.get("full") != full
            or choice.get("qt_maximum") != full-page):
        raise ValueError("Source vertical menu Page/Position contract changed")

    source_window = spectrum.get("input_source_window")
    if not isinstance(source_window, dict):
        raise ValueError("No SHA-verified FFT source window")
    f_range = current.frange_single
    origin = ORIGIN_TSXML if f_range is not None else None
    pair_accepted = False
    if visible_pair is not None:
        if not isinstance(visible_pair, dict):
            raise ValueError("Invalid operator original pair")
        values = np.asarray(spectrum.get("amplitude"), dtype="<f4")
        if (values.ndim != 1 or values.size != spectrum["n_fft"]//2
                or not bool(np.isfinite(values).all())):
            raise ValueError("Original pair needs complete finite visible Y")
        digest = hashlib.sha256(values.tobytes()).hexdigest()
        if (visible_pair.get("schema") != PAIR_SCHEMA
                or visible_pair.get("paired_numeric_pass") is not True
                or visible_pair.get("source_bin_sha256") != source["source_bin_sha256"]
                or visible_pair.get("source_window_sha256") !=
                   source_window.get("source_float32_le_sha256")
                or visible_pair.get("original_full_y_sha256") != digest
                or visible_pair.get("fft_n") != spectrum["n_fft"]
                or visible_pair.get("full_y_bins") != values.size
                or visible_pair.get("channel") != flow.channel
                or visible_pair.get("spectrum_mode") != mode
                or visible_pair.get("input_domain") != spectrum.get("input_domain")
                or spectrum.get("fft_backend") != "idr_float32"):
            raise ValueError("Original pair no longer matches current visible Y/ADC/FFT")
        word = visible_pair.get("original_f_range_float32_hex")
        if (not isinstance(word, str) or len(word)!=8
                or any(c not in "0123456789ABCDEF" for c in word)):
            raise ValueError("Original pair Single FRange word missing")
        pair_range = struct.unpack("<f", struct.pack("<I", int(word,16)))[0]
        if (_f32_bits(pair_range) != int(word,16)
                or _f32_bits(spectrum["f_range_used"]) != int(word,16)):
            raise ValueError("Current FFT FRange differs from original matched Power/Y")
        f_range = pair_range
        origin = ORIGIN_PAIRED
        pair_accepted = True
    elif f_range is not None and current.origin != SOURCE_GAIN:
        raise ValueError("Untrusted source FRange origin")

    if mode == 0:
        # 0084C789..C7BE: dB has literal ScrHeight=Page, bottom=-Page-Position.
        # The scalar 1 in this call is ignored by the original dB branch.
        native = source_spectrum_v_scr(
            position,page,full,db_mode=True,
            graph_default_v_scale=1.,scale_divisor=1)
        default_scale = None
        if origin is None:
            origin = ORIGIN_DB
    else:
        if f_range is None:
            return None
        candidate = spectrum_graph_default_vscale(f_range,mode)
        default_scale = candidate["candidate_graph_default_vscale_single"]
        native = source_spectrum_v_scr(
            position,page,full,db_mode=False,
            graph_default_v_scale=default_scale,
            scale_divisor=int(required["physical_divisor"]))
    lower = native["scr_bottom_single"]
    upper = lower + native["scr_height_single"]
    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        raise ValueError("Source graph Y bounds are not finite or ordered")
    return {
        "source": SOURCE,
        "channel": flow.channel,
        "source_bin_sha256": source["source_bin_sha256"],
        "source_window_float32_sha256": source_window["source_float32_le_sha256"],
        "spectrum_mode": mode, "n_fft": spectrum["n_fft"],
        "source_menu_tag": tag, "delphi_position": position,
        "delphi_full": full, "delphi_page": page,
        "f_range_origin": origin,
        "f_range_single": f_range,
        "graph_default_vscale_candidate": default_scale,
        "native_scroll": native,
        "y_min": lower, "y_max": upper,
        "source_anchored_without_local_y_offset": True,
        "operator_original_y_pair_matched": pair_accepted,
        "source_tsxml_static_gain_used": (
            origin == ORIGIN_TSXML),
        "original_runtime_f_range_verified": False,
        "original_win32_canvas_pixel_parity_verified": False,
        "original_delphi_x87_boundary_parity_verified": False,
        "source_float32_fft_mutated": False,
        "physical_calibration_verified": False,
    }
