"""Explicit 4-mode x87 acceptance file manifest and guard rails.

The synthetic identical RAW is not a Win32 MVKView run and must never
certify original hardware/Delphi, even when every tagged file matches.
"""
import numpy as np
import pytest
from ..core.original_mode2_paired_acceptance import compare_original_mode2_pair


def _synthetic_four_modes(tmp_path):
    ref=tmp_path/"reference"
    candidate=tmp_path/"candidate"
    ref.mkdir();candidate.mkdir()
    raw=b"SYNTHETIC_RAW_SOURCE_FOR_FOUR_TAGS_ONLY"
    files=[{"kind":"GETSPECTRUM_PRE_HANN_F32",
            "reference_name":"pre.bin","candidate_name":"pre.bin"},
           {"kind":"GETSPECTRUM_WINDOWED_F32",
            "reference_name":"hann.bin","candidate_name":"hann.bin"},
           {"kind":"GETSPECTRUM_FFT_COMPLEX_F32",
            "reference_name":"complex.bin","candidate_name":"complex.bin"},
           {"kind":"GETSPECTRUM_POWER_F32",
            "reference_name":"power.bin","candidate_name":"power.bin"}]
    data={"incoming.raw":raw}
    for name,n in (("pre.bin",64),("hann.bin",64),
                   ("complex.bin",64),("power.bin",32)):
        data[name]=np.arange(n,dtype="<f4").tobytes()
    for mode in range(4):
        for kind,prefix in (("GETSPECTRUM_Y_F32","Y"),
                            ("GETSPECTRUM_POSTMODE_POWER_F32","P")):
            # Different binary file for every mode, one source SHA stream.
            name=f"{prefix}{mode}.bin"
            data[name]=np.asarray(np.arange(32,dtype=np.float64)+mode,
                                  dtype="<f4").tobytes()
            files.append({"kind":kind,"reference_name":name,
                          "candidate_name":name,
                          "source_spectrum_mode":mode})
    for root in (ref,candidate):
        for name,payload in data.items():(root/name).write_bytes(payload)
    return ref,candidate,files


def _run(ref,candidate,files):
    return compare_original_mode2_pair(
        ref,candidate,files=files,session_id="ONLY_SYNTHETIC_SAME_RAW",
        reference_raw_name="incoming.raw",candidate_raw_name="incoming.raw")


def test_four_explicit_tags_plus_postmode_power_prove_only_compared_bytes(tmp_path):
    ref,candidate,files=_synthetic_four_modes(tmp_path)
    proof=_run(ref,candidate,files)
    assert proof["source_four_mode_y_tags_explicitly_supplied"]==[0,1,2,3]
    assert proof["source_integrated_postmode_power_tags_explicitly_supplied"]==[0,1,2,3]
    assert proof["source_four_mode_y_tag_coverage_complete"]
    assert proof["source_same_raw_four_mode_numeric_comparison_complete"]
    assert proof["source_same_raw_four_mode_numeric_pairs_byte_identical"]
    assert proof["same_input_tcp_raw_verified"]
    assert not proof["source_all_four_modes_original_win32_same_window_attested"]
    assert not proof["source_stop_boundary_authenticated_with_original_win32"]
    assert not proof["original_1_to_1_release_gate_passed"]
    assert not proof["original_delphi_compatibility_verified"]


def test_one_missing_mode_never_reports_complete(tmp_path):
    ref,candidate,files=_synthetic_four_modes(tmp_path)
    rest=[x for x in files if not(x["kind"]=="GETSPECTRUM_Y_F32" and
                                    x.get("source_spectrum_mode")==3)]
    result=_run(ref,candidate,rest)
    assert result["source_four_mode_y_tags_explicitly_supplied"]==[0,1,2]
    assert not result["source_four_mode_y_tag_coverage_complete"]
    assert not result["source_same_raw_four_mode_numeric_comparison_complete"]
    assert not result["source_same_raw_four_mode_numeric_pairs_byte_identical"]


def test_one_ulp_in_tag3_breaks_numeric_equality_without_fake_runtime_claim(tmp_path):
    ref,candidate,files=_synthetic_four_modes(tmp_path)
    p=candidate/"Y3.bin"
    mutated=bytearray(p.read_bytes())
    mutated[0]^=1
    p.write_bytes(mutated)
    result=_run(ref,candidate,files)
    assert result["source_same_raw_four_mode_numeric_comparison_complete"]
    assert not result["source_same_raw_four_mode_numeric_pairs_byte_identical"]
    row=next(x for x in result["pairs"]
             if x["kind"]=="GETSPECTRUM_Y_F32"
             and x["source_spectrum_mode"]==3)
    assert row["different_float32_words"]==1
    assert not result["original_delphi_compatibility_verified"]


@pytest.mark.parametrize("bad",[
    {"source_spectrum_mode":True},
    {"source_spectrum_mode":4},
    {"source_spectrum_mode":-1},
    {"source_spectrum_mode":"3"},
])
def test_mode_tag_type_rejected(tmp_path,bad):
    ref,candidate,files=_synthetic_four_modes(tmp_path)
    entry=dict(files[-2])
    entry.update(bad)
    files[-2]=entry
    with pytest.raises(ValueError):
        _run(ref,candidate,files)


def test_mode_tag_for_csv_or_reuse_of_same_original_file_denied(tmp_path):
    ref,candidate,files=_synthetic_four_modes(tmp_path)
    illegal=dict(files[0],source_spectrum_mode=0)
    with pytest.raises(ValueError):
        _run(ref,candidate,[illegal])
    files[-2]=dict(files[-2],reference_name="Y2.bin")
    with pytest.raises(ValueError,match="reused"):
        _run(ref,candidate,files)


def test_mode_tags_without_raw_never_label_complete(tmp_path):
    ref,candidate,files=_synthetic_four_modes(tmp_path)
    proof=compare_original_mode2_pair(
        ref,candidate,files=files,session_id="NO_RAW_TEST")
    assert proof["source_four_mode_y_tag_coverage_complete"]
    assert not proof["source_same_raw_four_mode_numeric_comparison_complete"]
    assert not proof["source_same_raw_four_mode_numeric_pairs_byte_identical"]
