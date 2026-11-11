#!/usr/bin/env python3
"""Stage111Z31BF: aggregate a private series of TWO-PID MVKView captures.

Read-only: no Windows API, app launch, UI input, x32dbg, memory, device I/O.
Each capture must be produced by the revised compare_running_mvkview_windows
tool, with image SHA256 receipts. Only numeric, anonymized summary is written
in a private folder OUTSIDE Git checkout. This is a comparison plan/evidence
tool, NOT original runtime functional-parity certification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets

CAPTURE_PREFIX = "MVK_DIRECT_WINDOW_QA_"
FORMAT = "MVK_SOURCE_PRIVATE_MULTI_SCENARIO_PARITY_V1"
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
MAX_CAPTURE_CASES = 64
MAX_FILE_BYTES = 24 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _read_receipt(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not (
            1 <= path.stat().st_size <= 128 * 1024):
        raise ValueError("Missing or unsafe local capture receipt")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Capture receipt must be a JSON object")
    return obj


def _checked_png_sha(path: Path, expected: str) -> str:
    if not isinstance(expected, str) or not SHA_RE.fullmatch(expected):
        raise ValueError("Missing original/compatible PNG SHA256 receipt")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing local PNG")
    size = path.stat().st_size
    if not 8 <= size <= MAX_FILE_BYTES:
        raise ValueError("Bad PNG byte count")
    with path.open("rb") as stream:
        if stream.read(8) != PNG_SIGNATURE:
            raise ValueError("Invalid original/compatible PNG signature")
        stream.seek(0)
        hasher = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    actual = hasher.hexdigest()
    if actual != expected:
        raise ValueError("Source capture PNG SHA256 mismatch")
    return actual


def summarize_private_captures(private_root: Path) -> dict:
    """Strict no-symlinks, immutable source receipt and provenance checking."""
    folder = Path(private_root)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Expected an existing private directory")
    entries = sorted(p for p in folder.iterdir()
                     if p.name.startswith(CAPTURE_PREFIX))
    if not 1 <= len(entries) <= MAX_CAPTURE_CASES:
        raise ValueError("Expected 1..64 source pair capture directories")
    cases = []
    for child in entries:
        if child.is_symlink() or not child.is_dir():
            raise ValueError("Private capture folder must not be a symlink")
        receipt = _read_receipt(child/"comparison.json")
        pid_a = receipt.get("original_window_pid")
        pid_b = receipt.get("compatible_window_pid")
        if (type(pid_a) is not int or type(pid_b) is not int
                or pid_a <= 0 or pid_b <= 0 or pid_a == pid_b):
            raise ValueError("Paired original/compatible PID evidence required")
        if not (receipt.get("automatic_original_program_launch") is False
                and receipt.get("original_window_inputs_sent") is False
                and receipt.get("original_debugger_or_process_memory_access") is False
                and receipt.get("full_window_1to1_verified") is False):
            raise ValueError("Original read-only safety receipt is missing")
        name = receipt.get("scenario_id_operator_declared")
        if not isinstance(name, str) or not ID_RE.fullmatch(name):
            raise ValueError("Valid operator-declared scenario ID required")
        original_sha = _checked_png_sha(
            child/"original_client.png", receipt.get("original_png_sha256"))
        compatible_sha = _checked_png_sha(
            child/"compatible_client.png", receipt.get("compatible_png_sha256"))
        equal_dims = receipt.get("identical_client_pixel_dimensions")
        if type(equal_dims) is not bool:
            raise ValueError("Missing client geometry comparison result")
        full_exact = receipt.get("unshifted_pixel_identical_this_capture")
        if equal_dims and type(full_exact) is not bool:
            raise ValueError("Missing exact original/candidate pixel result")
        if not equal_dims and full_exact is not None:
            raise ValueError("Mismatched windows cannot have pixel pass")
        rois = receipt.get("selected_regions")
        roi_details = []
        if rois is not None:
            if not isinstance(rois, dict) or type(rois.get("rejected")) is not bool:
                raise ValueError("Invalid selected ROI comparison")
            if rois["rejected"] != (not equal_dims):
                raise ValueError("ROI and whole-frame dimension decisions conflict")
            if equal_dims:
                items = rois.get("region_results")
                if not isinstance(items, list) or not 1 <= len(items) <= 32:
                    raise ValueError("Missing verified ROI result rows")
                names = set()
                for item in items:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid ROI result")
                    region_name = item.get("name")
                    identical = item.get("pixel_identical")
                    if (not isinstance(region_name,str)
                            or not ID_RE.fullmatch(region_name)
                            or region_name in names
                            or type(identical) is not bool):
                        raise ValueError("Bad ROI identity or comparison")
                    names.add(region_name)
                    roi_details.append({"name":region_name,
                                        "pixel_identical":identical,
                                        "pixel_count":item.get("pixel_count"),
                                        "changed_gt1":item.get(
                                            "changed_pixels_any_channel_gt_1")})
        source_hash = receipt.get("operator_data_sha256_unverified")
        if source_hash is not None and (
                not isinstance(source_hash,str)
                or not SHA_RE.fullmatch(source_hash.lower())):
            raise ValueError("Operator-declared source SHA is invalid")
        cases.append({
            "scenario_id":name,
            "pair_capture_folder":child.name,
            "original_png_sha256":original_sha,
            "compatible_png_sha256":compatible_sha,
            "original_pid_operator_selected":pid_a,
            "compatible_pid_operator_selected":pid_b,
            "operator_data_sha256_unverified":source_hash,
            "same_client_pixel_size":equal_dims,
            "whole_client_pixel_identical":full_exact if equal_dims else None,
            "roi_results":roi_details,
            "source_runtime_verification_claimed":False,
        })
    by_scenario = {}
    for row in cases:
        entry=by_scenario.setdefault(row["scenario_id"],{
            "captured_pairs":0,
            "whole_client_equal_pixels_count":0,
            "mismatched_dimensions_count":0,
            "roi_count":0,
            "roi_identical_count":0,
        })
        entry["captured_pairs"] += 1
        entry["whole_client_equal_pixels_count"] += int(
            row["whole_client_pixel_identical"] is True)
        entry["mismatched_dimensions_count"] += int(
            row["same_client_pixel_size"] is False)
        entry["roi_count"] += len(row["roi_results"])
        entry["roi_identical_count"] += sum(
            bool(r["pixel_identical"]) for r in row["roi_results"])
    return {
        "format":FORMAT,
        "paired_capture_count":len(cases),
        "scenarios":by_scenario,
        "captures":cases,
        "original_process_identity_independently_verified":False,
        "original_same_measurement_file_independently_verified":False,
        "all_original_runtime_behaviors_verified":False,
        "functional_1to1_acceptance":False,
        "original_window_inputs_automated":False,
        "device_io_performed":False,
        "private_original_or_candidate_images_embedded":False,
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-captures",required=True,type=Path)
    args=parser.parse_args(argv)
    folder=args.private_captures
    checkout=Path(__file__).resolve().parents[2]
    full=folder.resolve()
    if full==checkout or checkout in full.parents:
        parser.error("Private source evidence must stay OUTSIDE Git checkout")
    summary=summarize_private_captures(folder)
    name=("MVK_PRIVATE_SERIES_SUMMARY_"+
          datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_")+
          secrets.token_hex(4)+".json")
    target=folder/name
    with target.open("x",encoding="utf-8") as stream:
        json.dump(summary,stream,ensure_ascii=False,indent=2,sort_keys=True)
        stream.write("\n")
    print("PRIVATE summary:",target)
    print("Captured original/candidate pairs:",summary["paired_capture_count"])
    print("Full MVKView 1:1 parity: NOT ATTESTED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
