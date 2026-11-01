"""Stage111Z.13: original Copy click 3/3 visible-field regression.

Operator observed four exact Float32 words at original x32dbg 0084BC8C
and three visible Copy columns. The message did not preserve raw TAB/CRLF
bytes; this tests text fields only, not whole clipboard byte parity.
Original EXE/IDP/archives/FFT captures are never included.
"""
import struct
import numpy as np
from mvk_compatible.core.cursor_format_candidate import cursor_decimal_mask_candidate
from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text

ORIGINAL_COPY_WORDS = {
    "mean": 0x40DC8F5E,
    "peak_bin": 0x466D8095,
    "amplitude": 0x3F475279,
    "graph_xscale": 0x3E800000,
}
ORIGINAL_COPY_COLUMNS = ("6,89", "3800", "0,7786")


def _f32(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def _bits(value):
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def test_original_selected_copy_4_single_words_roundtrip():
    assert all(_bits(_f32(v)) == v for v in ORIGINAL_COPY_WORDS.values())
    assert _f32(ORIGINAL_COPY_WORDS["graph_xscale"]) == 0.25
    freq = np.float32(_f32(ORIGINAL_COPY_WORDS["peak_bin"]) * 0.25)
    assert _bits(freq) == 0x456D8095
    assert float(freq) == 3800.036376953125


def test_original_same_click_three_visible_fields_equal_candidate():
    inputs = {k:_f32(v) for k,v in ORIGINAL_COPY_WORDS.items()}
    frequency = float(np.float32(inputs["peak_bin"] * inputs["graph_xscale"]))
    summary = {
        "source": "APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE",
        "output_mean": inputs["mean"],
        "output_peak_frequency_hz": frequency,
        "output_peak_y": inputs["amplitude"],
    }
    observed = spectrum_triplet_text(
        summary, decimal_separator=",").split("\t")
    assert tuple(observed) == ORIGINAL_COPY_COLUMNS
    digits = tuple(
        cursor_decimal_mask_candidate(v,p,",")["decimal_places"]
        for v,p in zip((inputs["mean"],frequency,inputs["amplitude"]),(3,4,4))
    )
    assert digits == (2,0,4)
