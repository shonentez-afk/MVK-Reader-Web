"""Stage111Z31BF: private-series SHA receipt and failure guard tests."""
import hashlib
import json
from pathlib import Path
import pytest
from tools.research.summarize_private_mvkview_parity import (
    summarize_private_captures, FORMAT, CAPTURE_PREFIX,
)

PNG=b"\x89PNG\r\n\x1a\n" + b"synthetic-tests-not-image-pixels"

def case(root, *, scenario="ConfigIP", diff=False, changed=False):
    p=root/(CAPTURE_PREFIX+scenario)
    p.mkdir()
    orig=p/"original_client.png"
    compat=p/"compatible_client.png"
    orig.write_bytes(PNG)
    compat.write_bytes(PNG + (b"z" if changed else b""))
    receipt={
        "original_window_pid":1234,"compatible_window_pid":5678,
        "automatic_original_program_launch":False,
        "original_window_inputs_sent":False,
        "original_debugger_or_process_memory_access":False,
        "full_window_1to1_verified":False,
        "scenario_id_operator_declared":scenario,
        "original_png_sha256":hashlib.sha256(orig.read_bytes()).hexdigest(),
        "compatible_png_sha256":hashlib.sha256(compat.read_bytes()).hexdigest(),
        "identical_client_pixel_dimensions":not diff,
        "operator_data_sha256_unverified":None,
        "selected_regions":{
            "rejected":diff,
            **({} if diff else {"region_results":[
                {"name":"config","pixel_identical":not changed,
                 "pixel_count":100,"changed_pixels_any_channel_gt_1":
                     int(changed)}]})
        },
    }
    if not diff:
        receipt["unshifted_pixel_identical_this_capture"]=not changed
    (p/"comparison.json").write_text(json.dumps(receipt),encoding="utf-8")
    return p, receipt


def test_multi_capture_strict_sha_and_case_metrics(tmp_path):
    case(tmp_path,scenario="ConfigIP")
    case(tmp_path,scenario="ConfigCalib",changed=True)
    result=summarize_private_captures(tmp_path)
    assert result["format"]==FORMAT
    assert result["paired_capture_count"]==2
    assert result["scenarios"]["ConfigIP"]["whole_client_equal_pixels_count"]==1
    assert result["scenarios"]["ConfigCalib"]["roi_count"]==1
    assert result["scenarios"]["ConfigCalib"]["roi_identical_count"]==0
    assert not result["functional_1to1_acceptance"]
    assert not result["all_original_runtime_behaviors_verified"]
    assert not result["device_io_performed"]
    assert "synthetic-tests" not in repr(result)


def test_tampered_private_capture_rejected(tmp_path):
    folder,_=case(tmp_path)
    with (folder/"original_client.png").open("ab") as stream:
        stream.write(b"tampering")
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        summarize_private_captures(tmp_path)


def test_safety_receipt_not_assumed_if_missing(tmp_path):
    folder,receipt=case(tmp_path)
    del receipt["original_window_inputs_sent"]
    (folder/"comparison.json").write_text(json.dumps(receipt),encoding="utf-8")
    with pytest.raises(ValueError,match="read-only safety"):
        summarize_private_captures(tmp_path)


def test_dimensions_mismatch_is_not_interpreted_as_equal(tmp_path):
    case(tmp_path,diff=True)
    result=summarize_private_captures(tmp_path)
    assert result["captures"][0]["whole_client_pixel_identical"] is None
    assert result["scenarios"]["ConfigIP"]["mismatched_dimensions_count"]==1


def test_private_capture_symlinks_denied(tmp_path):
    folder,_=case(tmp_path)
    original=folder/"original_client.png"
    original.unlink()
    try:
        original.symlink_to(folder/"compatible_client.png")
    except (OSError,NotImplementedError):
        pytest.skip("Symlinks unsupported")
    with pytest.raises(ValueError,match="Missing local PNG"):
        summarize_private_captures(tmp_path)


def test_missing_or_invalid_case_directory_denied(tmp_path):
    with pytest.raises(ValueError,match="1..64"):
        summarize_private_captures(tmp_path)
    (tmp_path/(CAPTURE_PREFIX+"invalid")).mkdir()
    with pytest.raises(ValueError,match="receipt"):
        summarize_private_captures(tmp_path)
