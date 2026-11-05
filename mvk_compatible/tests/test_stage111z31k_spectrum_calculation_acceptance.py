"""Stage111Z31K spectrum math gate: synthetic fixtures, no private samples."""
import json
import hashlib
import sys

import numpy as np
import pytest

from mvk_compatible.core.spectrum_calculation_acceptance import (
    MODE_NAMES, spectrum_calculation_acceptance, main,
)
from .test_stage111z31a_x32dbg_visual_reference import (
    create_reference_fixture,
)


def _all_four(tmp_path):
    return [create_reference_fixture(
        tmp_path/f"mode_{m}",mode=m,n=1024,fs=65536)[0]
        for m in range(4)]


def test_without_original_captures_must_never_claim_full_numerical_parity():
    result=spectrum_calculation_acceptance()
    assert result["source"].endswith("STAGE111Z31K")
    assert result["local_manifest_count"]==0
    assert result["replayed_modes"]==[]
    assert result["missing_modes"]==[0,1,2,3]
    assert result["verified_post_fft_y_float32_bins"]==0
    assert not result["full_mvkview_spectrum_recovered"]
    assert not result["original_universal_fft_and_spectrum_calculation_parity_verified"]
    assert not result["calculation_stages"][
        "float32_radix2_fft_and_power"
    ]["original_full_power_from_same_raw_window_bitwise_verified"]
    assert result["calculation_stages"][
        "hann_rms_262144_table"]["original_entries_bitwise_verified"]==4
    assert result["privacy"]["network_or_instrument_access"] is False


def test_four_mode_source_model_replay_does_not_assert_original_provenance(
        tmp_path):
    paths=_all_four(tmp_path)
    result=spectrum_calculation_acceptance(paths)
    assert result["replayed_modes"]==[0,1,2,3]
    assert result["local_manifest_count"]==4
    assert len(result["captures"])==4
    assert result["verified_post_fft_y_float32_bins"]==4*512
    assert result["operator_summary_three_words_verified_captures"]==4
    assert result["source_model_post_fft_all_four_modes_replayed_from_local_inputs"]
    assert result["source_model_three_summary_words_each_mode_replayed"]
    assert all(case["source_model_display_y_equal_bins"]==512
               and case["source_model_display_y_max_ulp"]==0
               and case["operator_supplied_summary_hex_matched"]
               and not case["original_runtime_same_frame_independently_authenticated"]
               for case in result["captures"])
    assert result["mode_names"]==list(MODE_NAMES)
    assert not result["original_manifest_provenance_independently_authenticated"]
    assert not result["full_mvkview_spectrum_recovered"]
    assert not result["original_universal_fft_and_spectrum_calculation_parity_verified"]
    # User filenames and stored buffers are *never* in the returned JSON.
    out=json.dumps(result,ensure_ascii=False)
    assert "reference.json" not in out
    assert "power_after_mode.bin" not in out
    assert "display_y.bin" not in out
    assert str(tmp_path) not in out
    for manifest in paths:
        assert str(manifest) not in out


def test_different_fft_sizes_and_fs_are_explicitly_visible(tmp_path):
    paths=[
        create_reference_fixture(tmp_path/"case_a",mode=0,n=1024,fs=65536)[0],
        create_reference_fixture(tmp_path/"case_b",mode=3,n=2048,fs=32768)[0],
    ]
    result=spectrum_calculation_acceptance(paths)
    assert result["replayed_modes"]==[0,3]
    assert result["missing_modes"]==[1,2]
    assert result["verified_post_fft_y_float32_bins"]==1536
    assert [(x["n_fft"],x["sample_rate_hz"]) for x in result["captures"]]==[
        (1024,65536),(2048,32768)]
    assert not result["source_model_post_fft_all_four_modes_replayed_from_local_inputs"]


def test_missing_operator_summary_hex_is_not_pass_or_three_words(tmp_path):
    ref,meta,_,_=create_reference_fixture(tmp_path/"sample",mode=0)
    meta.pop("summary_hex")
    ref.write_text(json.dumps(meta),encoding="utf-8")
    case=spectrum_calculation_acceptance([ref])["captures"][0]
    assert case["source_model_display_y_bits_equal"]
    assert case["operator_supplied_summary_hex_missing"]
    assert not case["operator_supplied_summary_hex_matched"]


def test_manifests_may_be_all_four_without_summary_attestation(tmp_path):
    paths=_all_four(tmp_path)
    metadata=json.loads(paths[-1].read_text(encoding="utf-8"))
    metadata.pop("summary_hex")
    paths[-1].write_text(json.dumps(metadata),encoding="utf-8")
    result=spectrum_calculation_acceptance(paths)
    assert result["source_model_post_fft_all_four_modes_replayed_from_local_inputs"]
    assert not result["source_model_three_summary_words_each_mode_replayed"]
    assert result["operator_summary_three_words_verified_captures"]==3


def test_reject_duplicate_original_reference_so_four_cannot_be_faked(tmp_path):
    a=_all_four(tmp_path)[0]
    with pytest.raises(ValueError,match="Duplicate"):
        spectrum_calculation_acceptance([a,a])


def test_reject_more_than_sixteen_and_non_path_manifests():
    with pytest.raises(ValueError):
        spectrum_calculation_acceptance("not a manifest list")
    with pytest.raises(ValueError):
        spectrum_calculation_acceptance([None])
    with pytest.raises(ValueError):
        spectrum_calculation_acceptance(["untrusted"]*17)


def test_detect_mutated_original_power_with_valid_sha_fail_closed(tmp_path):
    manifest,metadata,power,_=create_reference_fixture(tmp_path/"bad")
    bad=power.copy()
    bad[19]=np.float32(123.)
    payload=bad.tobytes()
    (manifest.parent / metadata["power_file"]).write_bytes(payload)
    metadata["power_sha256"]=hashlib.sha256(payload).hexdigest()
    manifest.write_text(json.dumps(metadata),encoding="utf-8")
    with pytest.raises(ValueError,match="Original Power/Y do not agree"):
        spectrum_calculation_acceptance([manifest])


def test_reject_wrong_operator_summary_hex_even_if_display_y_matches(tmp_path):
    manifest,metadata,_,_=create_reference_fixture(tmp_path/"badsummary")
    metadata["summary_hex"][0]="00000000"
    manifest.write_text(json.dumps(metadata),encoding="utf-8")
    with pytest.raises(ValueError,match="summary"):
        spectrum_calculation_acceptance([manifest])


def test_cli_four_mode_gate_can_fail_without_originals(capsys):
    assert main([])==0
    out=json.loads(capsys.readouterr().out)
    assert not out["full_mvkview_spectrum_recovered"]
    assert main(["--require-four-modes"])==2
    capsys.readouterr()


def test_cli_four_mode_gate_runs_with_local_synthetic_references(tmp_path,capsys):
    refs=_all_four(tmp_path)
    args=["--require-four-modes"]
    for ref in refs:
        args.extend(["--manifest",str(ref)])
    assert main(args)==0
    data=json.loads(capsys.readouterr().out)
    assert data["source_model_three_summary_words_each_mode_replayed"]
    assert data["original_universal_fft_and_spectrum_calculation_parity_verified"] is False
