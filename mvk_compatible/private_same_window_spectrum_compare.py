"""Stage111Z31Q: match an archived RAW Float32 window to ORIGINAL full Y.

Unlike the existing post-power original Golden, this test recomputes N/2
bins from a *real local* BIN/TSXML or audited Native R6.1 ZIP. It refuses
an original Y reference unless the operator additionally supplies the SHA
of the same original raw Single window and exact channel/window metadata.

A manifest assertion is NOT an independently authenticated Win32 capture.
No measurement, reference BIN, IDP, paths or original DLL code is uploaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .core.direct_bin_session import DirectBinSession
from .core.envelope_idr_candidate import EnvelopeProfile
from .core.envelope_spectrum_idr_candidate import required_original_history
from .core.offline_export import OfflineSession
from .core.original_spectrum_x32dbg_reference import load_original_spectrum_reference
from .core.storage_f_range_idr_candidate import (
    DOMAIN_CALIBRATED_BIN, DOMAIN_ORIGINAL_STORAGE,
)
from .private_getspectrum_prefft_envelope_compare import _ordered_f32_words

SCHEMA = "MVKVIEW_ORIGINAL_SAME_RAW_WINDOW_FULL_Y_V1"
PROVENANCE = "OPERATOR_ASSERTED_ORIGINAL_RAW_SINGLE_WINDOW"
SOURCE = "LOCAL_BIN_TO_ORIGINAL_FULL_Y_OPERATOR_PAIRED_STAGE111Z31Q"
_REQUIRED = frozenset({
    "schema", "original_window_provenance", "channel", "fft_n",
    "raw_sample_rate_hz", "spectrum_mode", "envelope_code",
    "first_archive_sample_index", "last_archive_sample_exclusive",
    "original_raw_window_float32_sha256", "input_domain",
})
_SHA = set("0123456789abcdef")


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64
        and all(ch in _SHA for ch in value)
    )


def _evidence(path: str | Path) -> dict:
    p = Path(path)
    if (p.is_symlink() or not p.is_file() or p.suffix.lower() != ".json"
            or not 1 <= p.stat().st_size <= 4096):
        raise ValueError("Missing or invalid same-window evidence JSON")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if (not isinstance(obj, dict) or set(obj) != _REQUIRED
            or obj["schema"] != SCHEMA
            or obj["original_window_provenance"] != PROVENANCE):
        raise ValueError("Incomplete original window evidence: no identity assertion")
    for key, minimum, maximum in (
        ("channel", 1, 8), ("fft_n", 1024, 262144),
        ("raw_sample_rate_hz", 100, 1000000), ("spectrum_mode", 0, 3),
        ("envelope_code", 0, 31), ("first_archive_sample_index", 0, 200000000),
        ("last_archive_sample_exclusive", 1, 200000000),
    ):
        value = obj[key]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError("Invalid original matched-window integer metadata")
    if obj["fft_n"] & (obj["fft_n"] - 1):
        raise ValueError("Original FFT N is not a power of two")
    if obj["last_archive_sample_exclusive"] <= obj["first_archive_sample_index"]:
        raise ValueError("Invalid original window interval")
    if not _is_sha(obj["original_raw_window_float32_sha256"]):
        raise ValueError("Original source window SHA256 is required")
    if obj["input_domain"] not in (DOMAIN_CALIBRATED_BIN, DOMAIN_ORIGINAL_STORAGE):
        raise ValueError("Original storage domain must be explicitly selected")
    return obj


def compare_original_same_window_spectrum(
        source_archive: str | Path, original_reference: str | Path,
        window_evidence: str | Path, *, original_idp: str | Path | None = None,
) -> dict:
    """Validate metadata and raw bytes *before* comparing any FFT Y bins.

    The original Y/reference manifest is validated by the established
    Stage31A original loader; its Power->Y 4-mode Golden is never reimplemented.
    The original raw window SHA MUST be supplied independently by the operator
    and matched against the archived data. A screenshot alone is insufficient.
    """
    expected = _evidence(window_evidence)
    original = load_original_spectrum_reference(original_reference)
    mode = expected["spectrum_mode"]
    n = expected["fft_n"]
    code = expected["envelope_code"]
    first = expected["first_archive_sample_index"]
    last = expected["last_archive_sample_exclusive"]
    channel = expected["channel"]
    if original.n_fft != n or original.mode != mode:
        raise ValueError("Original full Y mode/N does not match source evidence")
    source = Path(source_archive)
    if source.suffix.lower() in (".bin", ".tsxml"):
        session = DirectBinSession.open(source)
    elif source.suffix.lower() == ".zip":
        session = OfflineSession.open(source)
    else:
        raise ValueError("Only local BIN/TSXML or audited Native R6.1 ZIP")
    samples, fs, _, _ = session.samples(channel)
    if fs != expected["raw_sample_rate_hz"]:
        raise ValueError("Original and archive ADC sample rates disagree")
    if last > len(samples):
        raise ValueError("Insufficient recorded archive history; no padding")
    if code:
        if original_idp is None:
            raise ValueError("Envelope comparison needs the original local IDP")
        planned = required_original_history(n, int(fs), code)
        if last - first != planned["input_samples"]:
            raise ValueError("Original FIR history is not an exact full FFT window")
        profile = EnvelopeProfile.from_original_local_idp(original_idp)
    else:
        if original_idp is not None:
            raise ValueError("Plain FFT must not load an envelope IDP")
        if last - first != n:
            raise ValueError("Original plain FFT window must contain exactly N samples")
        profile = None

    # Check the actual ORIGINAL-DECLARED RAW input segment, not a candidate
    # spectrum's selected chart points. This is an explicit data gate.
    selected = np.asarray(samples[first:last], dtype="<f4")
    digest = hashlib.sha256(selected.tobytes()).hexdigest()
    if digest != expected["original_raw_window_float32_sha256"]:
        raise ValueError("Original raw-window SHA256 mismatch: NOT same input data")

    arguments = dict(
        mode=mode, backend="idr_float32", f_range=original.f_range,
        input_domain=expected["input_domain"],
    )
    if code:
        derived = session.spectrum_envelope(
            channel, code, n, profile, end_s=last / fs, **arguments)
    else:
        derived = session.spectrum(
            channel, n, start_s=first / fs, max_hz=1e9,
            max_points=n // 2, **arguments)
    window = derived["input_source_window"]
    if (window["first_archive_sample_index"] != first
            or window["last_archive_sample_exclusive"] != last
            or window["source_float32_le_sha256"] != digest
            or derived["n_fft"] != n or derived["mode"] != mode):
        raise ValueError("Recomputed spectrum selected a different source window")
    actual_fs = float(derived["df_hz"]) * n
    if not math.isclose(actual_fs, original.fs_hz, rel_tol=0, abs_tol=1e-6):
        raise ValueError("Original Y and candidate output FFT frequency grids differ")
    if len(derived["frequency_hz"]) != n//2 or len(derived["amplitude"]) != n//2:
        raise ValueError("Full N/2 Float32 display curve required; no decimation")
    calculated = np.asarray(derived["amplitude"], dtype="<f4")
    original_y = np.asarray(original.display_y, dtype="<f4")
    if not np.isfinite(calculated).all():
        raise ValueError("Nonfinite full candidate Y not comparable")
    match = calculated.view("<u4") == original_y.view("<u4")
    ulp = np.abs(_ordered_f32_words(calculated.view("<u4")) -
                 _ordered_f32_words(original_y.view("<u4")))
    differences = np.abs(calculated.astype(np.float64) -
                         original_y.astype(np.float64))
    mismatches = np.flatnonzero(~match)
    df = float(derived["df_hz"])
    return {
        "schema": SCHEMA, "source": SOURCE,
        "spectrum_mode": mode, "envelope_code": code, "fft_n": n,
        "channel": channel, "raw_sample_rate_hz": int(fs),
        "output_sample_rate_hz": original.fs_hz,
        "input_window_sample_count": last-first,
        "first_archive_sample_index": first,
        "last_archive_sample_exclusive": last,
        "input_domain": expected["input_domain"],
        "archive_source_window_sha256_matches_operator_original_claim": True,
        "source_window_float32_sha256": digest,
        "original_full_y_sha256": original.display_y_sha256,
        "candidate_full_y_sha256": hashlib.sha256(calculated.tobytes()).hexdigest(),
        "full_y_bins": n//2,
        "full_y_bitwise_equal_bins": int(np.count_nonzero(match)),
        "full_y_all_bitwise_equal": bool(np.all(match)),
        "first_differing_bin": (
            int(mismatches[0]) if len(mismatches) else None),
        "maximum_absolute_y_difference": float(np.max(differences)),
        "maximum_float32_ulp_difference": int(np.max(ulp)),
        "candidate_max_y_frequency_hz": float(np.argmax(calculated) * df),
        "original_max_y_frequency_hz": float(np.argmax(original_y) * df),
        "original_power_to_y_reused_not_recomputed": True,
        "original_runtime_same_thread_window_independently_authenticated": False,
        "operator_attestation_is_not_cryptographic_runtime_proof": True,
        "original_envelope_prefft_runtime_verified_by_this_tool": False,
        "original_arbitrary_Fs_N_ADC_universally_verified": False,
        "private_original_paths_or_values_in_report": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="LOCAL original full Y vs exact SHA-bound BIN input window")
    p.add_argument("--source-archive", required=True)
    p.add_argument("--original-power-y-manifest", required=True)
    p.add_argument("--original-window-evidence", required=True)
    p.add_argument("--original-idp", default=None)
    opts = p.parse_args(argv)
    try:
        result = compare_original_same_window_spectrum(
            opts.source_archive, opts.original_power_y_manifest,
            opts.original_window_evidence, original_idp=opts.original_idp)
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            RuntimeError, json.JSONDecodeError):
        p.exit(2, "Original raw-window pairing invalid; private details withheld\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["full_y_all_bitwise_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
