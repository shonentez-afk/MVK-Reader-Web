"""Stage111Z31A: local read-only original x32dbg GetSpectrum Power/Y visual reference.

This is a *comparison input* for the existing Qt spectrum canvas, never a
synthetic sensor archive, DSP reading, or replacement for GetSpectrum.
Source is an explicit manifest alongside two user-owned binary snapshots at
original 007D17E7: post-mode Power [EBP-2C], displayed Y [EBP-30].
The source-derived Y implementation MUST reproduce all Float32 words or the
reference is rejected. Original per-call provenance and Qt pixel parity remain
open. Never upload raw measurements to GitHub, CI, an API, or a device.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import struct

import numpy as np

from .spectrum_display_source import source_derived_mode_display
from .spectrum_metrics_idr_candidate import original_spectrum_summary
from .tqgrapher_display_idr_candidate import spectrum_display_contract

SOURCE = "LOCAL_OPERATOR_X32DBG_GETSPECTRUM_DISPLAY_Y_REFERENCE"
SCHEMA = "MVKVIEW_X32DBG_SPECTRUM_POWERY_REFERENCE_V1"
MAX_MANIFEST_BYTES = 8192
_REQUIRED = frozenset({
    "schema", "fft_n", "sample_rate_hz", "spectrum_mode",
    "f_range_bits", "stop_va", "power_file", "display_y_file",
    "power_sha256", "display_y_sha256",
})
_OPTIONAL = frozenset({"summary_hex"})
_FILE_NAME = re.compile(r"[A-Za-z0-9_(). -]{1,100}\.bin\Z", flags=re.ASCII)
_SHA = re.compile(r"[a-f0-9]{64}\Z", flags=re.ASCII)
_HEX = re.compile(r"(?:0x)?[0-9a-fA-F]{8}\Z")


def _hex_word(value: str, field: str) -> int:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise ValueError(field + ": expected 8 hex digits")
    return int(value, 16)


def _bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def _read_capture_file(root: Path, filename: str, checksum: str,
                       expected_size: int) -> np.ndarray:
    if (not isinstance(filename, str) or not _FILE_NAME.fullmatch(filename)
            or filename.strip() != filename
            or filename in (".", "..")
            or not isinstance(checksum, str) or not _SHA.fullmatch(checksum)):
        raise ValueError("Original reference requires safe relative BIN filenames and SHA256")
    source = root / filename
    if (not source.is_file() or source.is_symlink()
            or source.resolve().parent != root.resolve()
            or source.stat().st_size != expected_size):
        raise ValueError("Original reference BIN missing, symlinked, or wrong-sized: " + filename)
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != checksum:
        raise ValueError("Original reference SHA256 mismatch: " + filename)
    return np.frombuffer(data, dtype="<f4")


@dataclass(frozen=True)
class OriginalSpectrumReference:
    n_fft: int
    fs_hz: int
    mode: int
    f_range: float
    power: np.ndarray
    display_y: np.ndarray
    summary: dict
    power_sha256: str
    display_y_sha256: str
    original_summary_words_equal: bool | None

    def to_spectrum_record(self, *, channel: int) -> dict:
        if type(channel) is not int or not 1 <= channel <= 8:
            raise ValueError("Reference preview requires an explicit ADC context")
        df = float(np.float32(self.fs_hz / self.n_fft))
        contract = spectrum_display_contract(self.n_fft, self.fs_hz)
        return {
            "source": SOURCE,
            "channel": channel,
            "n_fft": self.n_fft,
            "mode": self.mode,
            "unit": ("дБ", "м/с²", "мм/с", "мкм")[self.mode],
            "frequency_hz": np.arange(self.n_fft // 2, dtype=np.float64) * df,
            "amplitude": self.display_y,
            "df_hz": df,
            "fft_backend": "ORIGINAL_LOCAL_X32DBG_CAPTURE_NOT_RECALCULATED",
            "grapher_series_bins": contract["grapher_series_bins"],
            "spectrum_summary": self.summary,
            "original_capture_reference_only": True,
            "original_runtime_provenance_independently_verified": False,
            "original_qt_pixel_parity_verified": False,
        }

    def report(self) -> dict:
        return {
            "source": SOURCE,
            "capture_stop_va": "007D17E7",
            "spectrum_mode": self.mode,
            "n_fft": self.n_fft,
            "sample_rate_hz": self.fs_hz,
            "float32_bins": self.n_fft // 2,
            "full_display_y_float32_bitwise_equal": True,
            "float32_ulp_max": 0,
            "power_sha256": self.power_sha256,
            "display_y_sha256": self.display_y_sha256,
            "summary_3x_float32_equal_when_operator_words_given":
                self.original_summary_words_equal,
            "original_archive_window_verified": False,
            "original_runtime_same_thread_frame_verified": False,
            "original_qt_pixel_parity_verified": False,
            "only_local_read_only_preview": True,
        }


def load_original_spectrum_reference(manifest_path: str | Path
                                     ) -> OriginalSpectrumReference:
    """Validate and read one user-supplied reference without mutating anything.

    Refuse missing fields, unexpected keys, unsafe file locations, short
    arrays, NaNs, wrong mode/Y, and mismatch against optional original words.
    No fallback to a calculated FFT or an assumed FRange is allowed.
    """
    path = Path(manifest_path)
    if (not path.is_file() or path.is_symlink() or
            path.suffix.lower() != ".json" or
            not 0 < path.stat().st_size <= MAX_MANIFEST_BYTES):
        raise ValueError("Choose a regular, small local x32dbg reference JSON")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not _REQUIRED <= config.keys() or (
        config.keys() - (_REQUIRED | _OPTIONAL)
    ):
        raise ValueError("Unrecognized or incomplete x32dbg Power/Y reference manifest")
    if config["schema"] != SCHEMA or config["stop_va"] != "007D17E7":
        raise ValueError("Manifest must describe original GetSpectrum at 007D17E7")
    n = config["fft_n"]
    fs = config["sample_rate_hz"]
    mode = config["spectrum_mode"]
    if (type(n) is not int or not 1024 <= n <= 262144 or n & (n - 1)
            or type(fs) is not int or not 100 <= fs <= 1_000_000
            or type(mode) is not int or mode not in (0, 1, 2, 3)):
        raise ValueError("Invalid original N, Fs, or spectrum mode")
    fr_bits = _hex_word(config["f_range_bits"], "f_range_bits")
    f_range = struct.unpack("<f", struct.pack("<I", fr_bits))[0]
    if not math.isfinite(f_range) or f_range <= 0:
        raise ValueError("Original Float32 FRange must be positive and finite")
    size = (n // 2) * 4
    power = _read_capture_file(
        path.parent, config["power_file"], config["power_sha256"], size)
    display_y = _read_capture_file(
        path.parent, config["display_y_file"], config["display_y_sha256"], size)
    if config["power_file"] == config["display_y_file"]:
        raise ValueError("Power and Y must be distinct original buffers")
    if (not bool(np.isfinite(power).all()) or not bool(np.isfinite(display_y).all())
            or bool((power < 0).any()) or bool(np.any(power[:2] != 0))):
        raise ValueError("Invalid original post-mode Power/Y values or lower bins")
    expected_y = source_derived_mode_display(
        power, n_fft=n, mode=mode, f_range=f_range)
    equal = np.array_equal(expected_y.view("<u4"), display_y.view("<u4"))
    if not equal:
        mismatches = int(np.count_nonzero(
            expected_y.view("<u4") != display_y.view("<u4")))
        raise ValueError(
            f"Original Power/Y do not agree with current source-derived mode: "
            f"{mismatches} differing Float32 bins")
    summary = original_spectrum_summary(
        power, n_fft=n, fs_out=fs, f_range=f_range, spectrum_mode=mode)
    original_words_equal = None
    if "summary_hex" in config:
        words = config["summary_hex"]
        if not isinstance(words, list) or len(words) != 3:
            raise ValueError("summary_hex requires exactly three original Float32 words")
        expected_words = tuple(_hex_word(x, "summary_hex") for x in words)
        actual_words = tuple(_bits(summary[key]) for key in (
            "output_mean", "output_peak_x_bin", "output_peak_y"))
        if actual_words != expected_words:
            raise ValueError("Original summary word(s) differ from source-derived summary")
        original_words_equal = True
    return OriginalSpectrumReference(
        n_fft=n, fs_hz=fs, mode=mode, f_range=f_range,
        power=power, display_y=display_y, summary=summary,
        power_sha256=config["power_sha256"],
        display_y_sha256=config["display_y_sha256"],
        original_summary_words_equal=original_words_equal)
