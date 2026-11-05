"""Stage111Z31K: stage-correct local radix2-vs-original FFT Power diagnostics.

Synthetic fixtures are NOT real original Win32 samples. Private captures
remain local and are never part of GitHub/CI.
"""
import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import idr_power_spectrum
from mvk_compatible.core.original_spectrum_independent_check import (
    compare_source_idr_fft_capture_pair,
)


def _synthetic_prefft_pair(folder, *, n=1024):
    folder.mkdir(parents=True,exist_ok=True)
    i=np.arange(n,dtype=np.float64)
    raw=np.asarray(
        np.sin(2.*np.pi*61.*i/n)
        +0.23*np.sin(2.*np.pi*113.*i/n),dtype="<f4")
    power,_=idr_power_spectrum(
        raw,backend="idr_float32",remove_dc=False)
    before=folder/"before_fft_f32.bin"
    after=folder/"after_fft_power_f32.bin"
    before.write_bytes(raw.tobytes())
    after.write_bytes(power.tobytes())
    return before,after,raw,power


def _check(before,after,**overrides):
    kwargs=dict(
        pre_fft_is_after_original_dc_and_filters=True,
        reference_power_is_before_low_bin_and_mode_changes=True,
        sample_rate_hz=65536)
    kwargs.update(overrides)
    return compare_source_idr_fft_capture_pair(before,after,**kwargs)


def test_source_candidate_exact_for_synthetic_generated_power_and_privacy(
        tmp_path):
    before,after,raw,power=_synthetic_prefft_pair(tmp_path/"pair")
    orig_before=before.read_bytes()
    orig_after=after.read_bytes()
    result=_check(before,after)
    assert result["captured_n_fft"]==1024
    assert result["captured_power_float32_bins"]==512
    assert result["idr_float32_fft_bitwise_equal_bins"]==512
    assert result["idr_float32_fft_bitwise_equal_fraction"]==1.
    assert result["source_candidate_p99_relative_error"]==0.
    assert result["same_peak_bin"]
    assert result["source_candidate_max_absolute_power_error"]==0.
    assert result["no_dc_removed_again"]
    assert result["input_stage_declared_by_operator_not_proven_by_tool"]
    assert result["power_stage_declared_by_operator_not_proven_by_tool"]
    assert not result["same_source_window_authenticated_by_original_runtime"]
    assert not result["original_all_fft_input_bitwise_parity_verified"]
    assert not result["network_or_instrument_access"]
    assert not result["private_file_paths_in_result"]
    assert not result["raw_samples_in_result"]
    assert before.read_bytes()==orig_before
    assert after.read_bytes()==orig_after
    assert str(tmp_path) not in str(result)
    assert result["source_candidate_peak_bin"] in (61,113)


def test_source_power_diff_is_detected_not_hidden_by_peak_or_double_baseline(
        tmp_path):
    before,after,raw,power=_synthetic_prefft_pair(tmp_path/"pair")
    altered=power.copy()
    altered[81]=np.float32(float(altered[81])+1.)
    after.write_bytes(altered.tobytes())
    result=_check(before,after)
    assert result["idr_float32_fft_bitwise_equal_bins"]==511
    assert result["source_candidate_max_absolute_power_error"]>0.
    assert result["same_peak_bin"]
    assert not result["original_all_fft_input_bitwise_parity_verified"]


def test_2048_fft_valid_and_no_second_mean_removal(tmp_path):
    before,after,raw,power=_synthetic_prefft_pair(
        tmp_path/"pair",n=2048)
    result=_check(before,after)
    assert result["idr_float32_fft_bitwise_equal_bins"]==1024
    assert result["no_dc_removed_again"]


@pytest.mark.parametrize("patch",[
    dict(pre_fft_is_after_original_dc_and_filters=False),
    dict(reference_power_is_before_low_bin_and_mode_changes=False),
    dict(pre_fft_is_after_original_dc_and_filters=1),
    dict(reference_power_is_before_low_bin_and_mode_changes=None),
    dict(sample_rate_hz=65536.0),
    dict(sample_rate_hz=-1),
])
def test_fft_comparison_requires_explicit_provenance_flags(tmp_path,patch):
    before,after,_,_=_synthetic_prefft_pair(tmp_path/"pair")
    with pytest.raises(ValueError):
        _check(before,after,**patch)


def test_fft_comparison_rejects_truncated_or_negative_reference(tmp_path):
    before,after,raw,power=_synthetic_prefft_pair(tmp_path/"pair")
    after.write_bytes(power[:-1].tobytes())
    with pytest.raises(ValueError):
        _check(before,after)
    broken=power.copy()
    broken[23]=-1.
    after.write_bytes(broken.tobytes())
    with pytest.raises(ValueError):
        _check(before,after)
