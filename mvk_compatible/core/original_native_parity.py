"""Stage111Z.27: local-only *observational* original BIN/TSXML vs Native R6.1.

An original BIN/TSXML pair has no RAW SHA or ADC first sample sequence index.
Even identical bytes alone cannot attest that both exports came from the SAME
instrument session. This comparison NEVER applies FRange and NEVER treats
similar timestamps or matching sample rates as a same-run proof.

No socket, Qt, firmware, original private source or writes to input files.
Only small aggregate metadata belongs in a shareable QA report; real BIN/RAW
and original TSXML must remain on the operator's computer.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import zipfile

import numpy as np

from .direct_bin_session import DirectBinSession, MAX_TSXML_BYTES
from .offline_export import (
    open_zip_file, require_members, MAX_BIN_SAMPLES,
)
from .original_tsxml_contract import inspect_original_tsxml

_COMPARE_BLOCK = 65_536
_MAX_EXAMPLES = 6


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bits_diagnostics(original: np.ndarray, native: np.ndarray) -> dict:
    """Exact IEEE754 Single bits and bounded numerical *diagnostics*.

    Float equality by itself would wrongly accept +0 vs -0, while comparing
    in-place arrays or applying gain would modify original measurements.
    """
    count = min(len(original), len(native))
    mismatches = 0
    max_abs = 0.0
    sum_sq = 0.0
    value_equal = 0
    examples = []
    ratio_values = []
    for start in range(0, count, _COMPARE_BLOCK):
        end = min(start + _COMPARE_BLOCK, count)
        a = original[start:end]
        b = native[start:end]
        oa = a.view("<u4")
        nb = b.view("<u4")
        bad = np.flatnonzero(oa != nb)
        mismatches += len(bad)
        value_equal += int(np.count_nonzero(a == b))
        delta = a.astype(np.float64) - b.astype(np.float64)
        if len(delta):
            max_abs = max(max_abs, float(np.max(np.abs(delta))))
            sum_sq += float(np.dot(delta, delta))
        for pos in bad[:max(0, _MAX_EXAMPLES-len(examples))]:
            j = start + int(pos)
            examples.append({
                "index_in_compared_file": j,
                "original_u32_hex": f"0x{int(oa[pos]):08x}",
                "native_u32_hex": f"0x{int(nb[pos]):08x}",
                "original_f32": float(a[pos]),
                "native_f32": float(b[pos]),
            })
        if len(ratio_values) < 3:
            # Diagnostic ratios only, never a scale correction.
            keep = (np.abs(b) > 1e-5) & (np.abs(a) > 1e-5)
            select = np.flatnonzero(keep)[:min(64, 64-len(ratio_values))]
            ratio_values.extend((a[select].astype(np.float64) /
                                 b[select].astype(np.float64)).tolist())
    result = {
        "compared_samples_from_file_start": count,
        "original_samples": len(original),
        "native_samples": len(native),
        "lengths_equal": len(original) == len(native),
        "bitwise_mismatch_count_on_common_prefix": int(mismatches),
        "numeric_value_equal_count_on_common_prefix": value_equal,
        "first_bitwise_mismatches": examples,
        "max_absolute_numeric_difference": max_abs,
        "rms_numeric_difference": math.sqrt(sum_sq/count) if count else None,
        "observed_bin_bitwise_equal": bool(count and
            len(original) == len(native) and mismatches == 0),
        "median_original_over_native_nonzero": (
            float(np.median(ratio_values)) if ratio_values else None),
    }
    return result


def _offset_hint(original: np.ndarray, native: np.ndarray, *,
                 window: int = 4096, anchor: int = 16) -> dict:
    """A bounded raw-byte anchor search, not an automatic alignment.

    The original TSXML does not contain the TCP first-sample index; two
    recordings at different times may show a plausible matching motif.
    """
    if min(len(original), len(native)) < anchor:
        return {"offset_samples_hypothesis": None, "alignment_proven": False}
    a = original[:window].tobytes()
    b = native[:window].tobytes()
    width = anchor*4
    # Only exact Float32 bit strings; no floating 'near match' acceptance.
    p = a.find(b[:width])
    if p >= 0 and p % 4 == 0:
        guess = p//4
    else:
        p = b.find(a[:width])
        guess = -(p//4) if p >= 0 and p % 4 == 0 else None
    return {"offset_samples_hypothesis": guess, "alignment_proven": False}


def _original_contract(entry) -> dict:
    m = entry.source_metadata
    return {
        "real_data_type": m.data_type,
        "channel_number": m.channel_number,
        "sample_rate_hz": m.sample_rate_hz,
        "data_length_bytes": m.data_length_bytes,
        "data_offset_bytes": m.data_offset_bytes,
        "internal_channel_gain_single": m.internal_gain_single,
        "f_range_loader_candidate_only": m.original_f_range_single_candidate,
        "gain_loader_branch": m.gain_loader_branch,
        "units_declared": m.channel_units_text,
        "source_meta_complete": m.source_meta_complete,
    }


def _native_contract(xml: bytes, filename: str, max_bytes: int) -> dict:
    m = inspect_original_tsxml(xml, actual_bin_filename=filename,
                              max_data_bytes=max_bytes)
    if m.data_type != "Single":
        raise ValueError("Native R6.1 ADC TSXML must declare Single, not Byte/Count")
    return {
        "real_data_type": m.data_type,
        "channel_number": m.channel_number,
        "sample_rate_hz": m.sample_rate_hz,
        "data_length_bytes": m.data_length_bytes,
        "data_offset_bytes": m.data_offset_bytes,
        "internal_channel_gain_single": m.internal_gain_single,
        "units_declared": m.channel_units_text,
        "source_meta_complete": m.source_meta_complete,
    }


def compare_original_native(original_bin: str | Path,
                            native_verified_zip: str | Path) -> dict:
    """Compare local original ADC BIN+TSXML against completed Native ZIP.

    Standard original eight-ADC groups are detected via filename. Unusual
    original names are accepted as one independent declared ADC, but cannot
    receive the eight-channel parity label. No original data is exported.
    """
    original = DirectBinSession.open(original_bin)
    native_path = open_zip_file(Path(native_verified_zip))
    report = {
        "schema": "MVK_STAGE111Z27_ORIGINAL_NATIVE_LOCAL_COMPARISON_V1",
        "provenance_level": "OBSERVATIONAL_UNATTESTED_SAME_RUN",
        "original_same_run_proven": False,
        "original_same_run_evidence": "Original BIN/TSXML contains neither raw SHA nor TCP sample-index identity",
        "original_binary_modified": False,
        "native_binary_modified": False,
        "no_network_or_device_access": True,
        "auto_applied_f_range_to_original": False,
        "auto_applied_f_range_to_native": False,
        "compared_adc": list(original.available_channels),
        "channels": [],
    }
    with zipfile.ZipFile(native_path, "r") as archive:
        names, audit = require_members(archive)
        if original.serial != "LOCAL_BIN_SINGLE_CHANNEL" and original.serial != audit["instrument_serial"]:
            raise ValueError("Original and Native serial labels identify different instruments")
        channel_audits = {
            x.get("adc"): x for x in audit.get("channels", [])
            if isinstance(x, dict)
        }
        if set(channel_audits) != set(range(1, 9)):
            raise ValueError("Native export audit must contain eight unique ADC channel records")
        report["native_instrument_serial"] = audit["instrument_serial"]
        report["original_serial_from_filename"] = original.serial
        report["native_raw_sha256"] = audit.get("source_raw_sha256")
        report["native_capture_started_utc"] = audit.get("capture_started_utc")
        report["native_capture_ended_utc"] = audit.get("capture_ended_utc")
        report["native_frame_count"] = audit.get("application_frames")
        report["original_sample_index_source"] = "NOT_DECLARED_IN_ORIGINAL_TSXML"
        report["native_sample_index_source"] = "NATIVE_EXPORT_AUDIT"
        for entry in original.channel_files:
            adc = entry.adc
            native_name = names[adc - 1]
            native_xml_name = native_name + ".tsxml"
            ninfo = archive.getinfo(native_name)
            if (ninfo.file_size == 0 or ninfo.file_size % 4 or
                    ninfo.file_size > MAX_BIN_SAMPLES*4):
                raise ValueError(f"Native ADC{adc} BIN outside offline 10M-sample limit")
            nbytes = archive.read(native_name)
            nch = channel_audits[adc]
            expected = nch.get("bin_sha256")
            if not isinstance(expected, str) or _sha(nbytes) != expected:
                raise ValueError(f"Native ADC{adc}: physical BIN SHA256 differs from audit")
            if (nch.get("bin_filename") not in (None, native_name) or
                    nch.get("bin_bytes",len(nbytes)) != len(nbytes) or
                    nch.get("samples",len(nbytes)//4) != len(nbytes)//4):
                raise ValueError(f"Native ADC{adc}: count or filename differs from audit")
            native_xml = archive.read(native_xml_name)
            if len(native_xml)>MAX_TSXML_BYTES:
                raise ValueError("Native TSXML too large")
            native_meta = _native_contract(native_xml, native_name,
                                            MAX_BIN_SAMPLES*4)
            original_bytes = entry.bin_path.read_bytes()
            original_xml = entry.tsxml_path.read_bytes()
            if (_sha(original_bytes) != entry.bin_sha256 or
                    _sha(original_xml) != entry.tsxml_sha256):
                raise ValueError(f"Original ADC{adc}: source changed since opening")
            offset=entry.data_offset_bytes
            original_payload = memoryview(original_bytes)[offset:offset+entry.data_length_bytes]
            src=np.frombuffer(original_payload, dtype="<f4")
            dst=np.frombuffer(nbytes, dtype="<f4")
            if not bool(np.isfinite(src).all()) or not bool(np.isfinite(dst).all()):
                raise ValueError("Non-finite original/Native data; comparison refused")
            diffs = _bits_diagnostics(src,dst)
            norm = _original_contract(entry)
            metadata_diff = {
                field: {"original": norm.get(field), "native": native_meta.get(field)}
                for field in (
                    "real_data_type","channel_number","sample_rate_hz",
                    "data_length_bytes","data_offset_bytes",
                    "internal_channel_gain_single","units_declared",
                )
                if norm.get(field) != native_meta.get(field)
            }
            capture_rate=nch.get("sample_rate_hz")
            if capture_rate is not None and capture_rate != native_meta["sample_rate_hz"]:
                raise ValueError(f"Native ADC{adc}: producer audit rate differs from TSXML")
            capture_gain=nch.get("gain")
            if capture_gain is not None and (
                    not math.isfinite(float(capture_gain)) or float(capture_gain)<=0):
                raise ValueError(f"Native ADC{adc}: invalid audited gain")
            diffs.update({
                "adc": adc,
                "original_bin_sha256": entry.bin_sha256,
                "original_tsxml_sha256": entry.tsxml_sha256,
                "native_bin_sha256": expected,
                "native_tsxml_sha256": _sha(native_xml),
                "tsxml_byte_equal": original_xml == native_xml,
                "full_bin_file_byte_equal": original_bytes == nbytes,
                "original_metadata": norm,
                "native_metadata": native_meta,
                "native_capture_gain_float32": capture_gain,
                "native_first_sample_index": nch.get("first_sample_index"),
                "metadata_differences": metadata_diff,
                "alignment": _offset_hint(src,dst),
                "sample_time_origin_aligned_by_evidence": False,
                "original_and_native_calibration_domain_proven_identical": False,
            })
            report["channels"].append(diffs)
    reports=report["channels"]
    report["all_eight_adc_present_in_original"]=len(reports)==8
    report["bin_bytes_equal_on_matching_file_starts"]=all(
        x["observed_bin_bitwise_equal"] for x in reports)
    report["tsxml_bytes_equal"]=all(x["tsxml_byte_equal"] for x in reports)
    report["metadata_identical_on_selected_fields"]=all(
        not x["metadata_differences"] for x in reports)
    report["verdict"]=(
        "OBSERVED_BIN_EQUAL_BUT_SAME_RUN_NOT_ATTESTED"
        if report["bin_bytes_equal_on_matching_file_starts"]
        else "OBSERVED_BIN_DIFFERENCES_SAME_RUN_NOT_ATTESTED"
    )
    if not report["all_eight_adc_present_in_original"]:
        report["verdict"]="PARTIAL_CHANNEL_COMPARISON_SAME_RUN_NOT_ATTESTED"
    report["next_required_evidence"]=(
        "Provide operator-local original MVKView ADC1..8 BIN+TSXML and "
        "the completed Native ZIP from the IDENTICAL source measurement, "
        "plus independent provenance connecting original files to Native RAW "
        "(not just similar timestamps). Verify original buffer start offset "
        "and FRange at runtime before declaring original byte parity."
    )
    return report
