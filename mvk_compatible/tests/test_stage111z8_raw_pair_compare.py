"""Stage111Z.8 synthetic-only two-BIN original FFT comparator regression.

No uploaded original memory dumps, archive samples, private executable or
IDP are stored in GitHub. Fixture arrays are fabricated at test time.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import idr_power_spectrum
from mvk_compatible.private_getspectrum_raw_pair_compare import (
    SOURCE, compare_original_fft_raw_pair,
)


def _make_synthetic_files(tmp_path, n: int = 1024):
    t=np.arange(n, dtype=np.float64)
    # Deliberate DC: source pre-FFT input is taken as-is, NO recentering.
    source=np.asarray(
        1.5 + 0.35*np.sin(2*np.pi*17*t/n)
        - 0.07*np.cos(2*np.pi*41*t/n), dtype="<f4"
    )
    expected,_=idr_power_spectrum(source, "idr_float32", remove_dc=False)
    before=tmp_path/"before_fft.bin"
    after=tmp_path/"after_power.bin"
    source.tofile(before)
    expected.tofile(after)
    return before,after,source,expected


def test_metadata_free_synthetic_pair_bitwise_matches_source_derived(tmp_path):
    before,after,source,power=_make_synthetic_files(tmp_path)
    report=compare_original_fft_raw_pair(before,after)
    assert report["source"] == SOURCE
    assert report["fft_n"] == source.size
    assert report["capture_quality"]["capture_status"] == "NONZERO_INPUT_AND_POWER"
    assert report["fft_numeric_comparison_performed"] is True
    assert report["input_recentered_or_calibrated_by_comparator"] is False
    assert report["capture_sample_rate_hz_or_mode_inferred"] is False
    assert report["input_original_provenance_authenticated"] is False
    assert report["same_original_GetSpectrum_invocation_authenticated"] is False
    assert report["original_Delphi_FFT_complete_parity_accepted"] is False
    source_report=report["comparisons"]["source_derived_float32_fft"]
    assert source_report["bins"] == len(power)
    assert source_report["float32_bitwise_equal_count"] == len(power)
    assert source_report["max_float32_ulp_distance"] == 0
    assert "numpy_float64_fft_cast_to_single" in report["comparisons"]
    exposed=json.dumps(report)
    assert str(tmp_path) not in exposed
    assert "before_fft.bin" not in exposed
    assert "after_power.bin" not in exposed


def test_single_modified_power_bit_is_reported_as_one_ulp(tmp_path):
    before,after,signal,power=_make_synthetic_files(tmp_path)
    altered=power.copy()
    index=17
    assert altered[index] > 0
    words=altered.view("<u4")
    words[index]=np.uint32(int(words[index])+1)
    altered.tofile(after)
    report=compare_original_fft_raw_pair(before,after)
    check=report["comparisons"]["source_derived_float32_fft"]
    assert check["float32_bitwise_equal_count"] == len(power)-1
    assert check["float32_bitwise_unequal_count"] == 1
    assert check["max_float32_ulp_distance"] == 1


def test_completely_zero_pair_returns_uninformative_without_fake_fft_parity(tmp_path):
    before,after,signal,power=_make_synthetic_files(tmp_path)
    np.zeros(signal.size,dtype="<f4").tofile(before)
    np.zeros(power.size,dtype="<f4").tofile(after)
    report=compare_original_fft_raw_pair(before,after)
    assert report["capture_quality"]["capture_status"] == "EMPTY_INPUT_AND_POWER"
    assert report["fft_numeric_comparison_performed"] is False
    assert report["comparisons"] == {}
    assert report["original_Delphi_FFT_complete_parity_accepted"] is False


def test_inconsistent_zero_input_and_power_is_not_bitwise_certified(tmp_path):
    before,after,signal,power=_make_synthetic_files(tmp_path)
    np.zeros(signal.size,dtype="<f4").tofile(before)
    report=compare_original_fft_raw_pair(before,after)
    assert report["capture_quality"]["capture_status"] == (
        "ZERO_INPUT_WITH_NONZERO_POWER_INCONSISTENT"
    )
    assert report["comparisons"] == {}


@pytest.mark.parametrize("n",[1024,8192,262144])
def test_synthetic_multiple_fft_sizes_work_without_manifest(tmp_path,n):
    before,after,_,power=_make_synthetic_files(tmp_path,n)
    report=compare_original_fft_raw_pair(before,after)
    assert report["fft_n"]==n
    assert report["comparisons"]["source_derived_float32_fft"][
        "float32_bitwise_equal_count"]==n//2


def test_invalid_lengths_negative_powers_and_nonfinite_values(tmp_path):
    before,after,signal,power=_make_synthetic_files(tmp_path)
    after.write_bytes(after.read_bytes()[:-4])
    with pytest.raises(ValueError):
        compare_original_fft_raw_pair(before,after)
    power[4]=np.float32(-1)
    power.tofile(after)
    with pytest.raises(ValueError):
        compare_original_fft_raw_pair(before,after)
    power[4]=np.float32(1)
    power.tofile(after)
    signal[4]=np.float32(np.nan)
    signal.tofile(before)
    with pytest.raises(ValueError):
        compare_original_fft_raw_pair(before,after)


def test_private_files_symlink_and_same_path_are_rejected(tmp_path):
    before,after,_,_=_make_synthetic_files(tmp_path)
    with pytest.raises(ValueError):
        compare_original_fft_raw_pair(before,before)
    link=tmp_path/"link.bin"
    try:
        link.symlink_to(before)
    except (OSError,NotImplementedError):
        pytest.skip("Host filesystem does not allow symlinks")
    with pytest.raises(ValueError):
        compare_original_fft_raw_pair(link,after)
