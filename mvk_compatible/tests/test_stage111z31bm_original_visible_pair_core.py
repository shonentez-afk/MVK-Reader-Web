"""BM: synthetic Core evidence for all modes, FIR and fail-closed inputs."""
import hashlib
import numpy as np
import pytest

from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31q_same_window_spectrum import _manifest, SOURCE_N, SOURCE_FS
from .test_envelope_idr_candidate import fake_profile
from ..core.direct_bin_session import DirectBinSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.envelope_idr_candidate import EnvelopeProfile
from ..core.envelope_spectrum_idr_candidate import required_original_history
from ..core.original_visible_spectrum_pair import compare_visible_original_spectrum_pair


def _make_visible(tmp_path, *, mode=1):
    path, _, samples = _make_pair(tmp_path, adc=4, n=SOURCE_N * 3)
    offset = SOURCE_N
    ref, evidence, _ = _manifest(
        tmp_path / "capture", samples[offset:offset + SOURCE_N],
        mode=mode, code=0, offset=offset)
    flow = OfflineMeasurementFlow.bind(DirectBinSession.open(path), channel=4)
    spectrum = flow.spectrum(
        SOURCE_N, mode, start_s=offset / SOURCE_FS,
        max_hz=1e9, max_points=SOURCE_N // 2,
        backend="idr_float32", f_range=1.)
    return flow, spectrum, ref, evidence


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_four_original_modes_same_window_full_y(tmp_path, mode):
    flow, spectrum, ref, evidence = _make_visible(tmp_path, mode=mode)
    original_bits = np.asarray(spectrum["amplitude"], dtype="<f4").view("<u4").copy()
    result = compare_visible_original_spectrum_pair(flow, spectrum, ref, evidence)
    assert result["paired_numeric_pass"]
    assert result["visible_y_matching_bins"] == SOURCE_N // 2
    assert result["recomputed_y_matching_bins"] == SOURCE_N // 2
    assert result["maximum_visible_float32_ulp_difference"] == 0
    assert result["original_f_range_float32_hex"] == "3F800000"
    assert not result["original_win32_runtime_and_pixel_parity_verified"]
    assert not result["hardware_calibration_or_device_commands_used"]
    assert not result["private_paths_or_signal_arrays_in_report"]
    np.testing.assert_array_equal(
        np.asarray(spectrum["amplitude"], dtype="<f4").view("<u4"), original_bits)


def test_recomputed_model_pass_but_visible_y_different_is_not_accepted(tmp_path):
    flow, spectrum, ref, evidence = _make_visible(tmp_path)
    changed = dict(spectrum, amplitude=list(spectrum["amplitude"]))
    changed["amplitude"][10] += 1.
    result = compare_visible_original_spectrum_pair(flow, changed, ref, evidence)
    assert result["recomputed_y_exact"]
    assert not result["visible_y_exact"]
    assert not result["paired_numeric_pass"]
    assert result["first_visible_differing_bin"] == 10


@pytest.mark.parametrize("field", ["channel", "mode", "f_range_used",
    "input_source_window", "fft_backend", "input_domain"])
def test_fails_closed_when_current_screen_changes(tmp_path, field):
    flow, spectrum, ref, evidence = _make_visible(tmp_path)
    changed = dict(spectrum)
    if field == "channel":
        changed[field] = 5
    elif field == "mode":
        changed[field] = 2
    elif field == "f_range_used":
        changed[field] = 2.
    elif field == "fft_backend":
        changed[field] = "numpy"
    elif field == "input_domain":
        changed[field] = "original_float_storage"
    else:
        changed[field] = dict(changed[field])
        changed[field]["first_archive_sample_index"] += 1
    with pytest.raises(ValueError):
        compare_visible_original_spectrum_pair(flow, changed, ref, evidence)


def test_envelope_uses_output_fs_and_actual_full_fir_history(tmp_path, monkeypatch):
    code = 20
    profile = fake_profile()
    length = required_original_history(SOURCE_N, SOURCE_FS, code)["input_samples"]
    path, _, samples = _make_pair(tmp_path, adc=4, n=length + 32)
    ref, evidence, _ = _manifest(
        tmp_path / "envelope", samples[32:32 + length],
        mode=1, code=code, profile=profile, offset=32)
    flow = OfflineMeasurementFlow.bind(DirectBinSession.open(path), channel=4)
    spectrum = flow.spectrum_envelope(
        code, SOURCE_N, profile, end_s=(32 + length) / SOURCE_FS,
        mode=1, backend="idr_float32", f_range=1.)
    monkeypatch.setattr(EnvelopeProfile, "from_original_local_idp",
        classmethod(lambda cls, path: profile))
    result = compare_visible_original_spectrum_pair(
        flow, spectrum, ref, evidence,
        envelope_code=code, original_idp=tmp_path / "local.idp")
    assert result["paired_numeric_pass"]
    assert result["envelope_code"] == code
