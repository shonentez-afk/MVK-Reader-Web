"""Restore ORIGINAL PageSpectrum bSpecLines pre-FIR semantics in archive GUI.

Source facts (private user Pascal, not bundled):
_Unit128:0084C4C8 menu Tag→bSpecLines;
_Unit115:007D1462 GetAdjustedEnvelopeLength on selected PRE-FIR count;
_Unit115:007D1C48/007D1E70 decimate and reduce Params.Count;
_Unit115:007D1518/007D1546 perform FFT using POST-FIR count.

All test bytes/coefficients are newly SYNTHETIC. A successful synthetic
regression is not an original MVK01 Win32/x87 bitwise parity certificate.
"""
import numpy as np
import pytest

from ..core.envelope_spectrum_idr_candidate import (
    source_selected_envelope_fft_plan,
    source_selected_envelope_spectrum_candidate,
    required_original_history,
)
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile
from .test_desktop_qt import qt_app


def test_original_selected_n_changes_fft_after_fir_and_matches_full_core(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=12000))
    profile=fake_profile(i=1.,q=.4)
    source_plan=source_selected_envelope_fft_plan(4096,65536,20)
    assert source_plan["source_getadjusted_length_samples"]==4147
    assert source_plan["original_params_count_after_fir"]==2048
    assert source_plan["post_fir_fft_n"]==2048
    assert source_plan["post_fir_df_hz"]==pytest.approx(16.)

    expected_raw=session.samples(1)[0][-4147:].copy()
    input_digest=expected_raw.tobytes()
    got=session.spectrum_envelope(
        1,20,4096,profile,
        source_selected_bspec_lines=True,mode=1,backend="numpy")
    expected=source_selected_envelope_spectrum_candidate(
        expected_raw,65536,20,profile,
        selected_bspec_lines_n=4096,mode=1,backend="numpy")
    assert got["source_bspec_lines_before_fir"]==4096
    assert got["source_bspec_lines_interpretation"]=="ORIGINAL_SELECTED_PRE_FIR"
    assert got["n_fft"]==2048
    assert got["df_hz"]==pytest.approx(16.)
    assert len(got["amplitude"])==1024
    assert got["source_history_samples"]==4147
    assert got["archive_input_start_s"]==pytest.approx((12000-4147)/65536)
    assert got["input_source_window"]["source_sample_count"]==4147
    np.testing.assert_array_equal(
        np.asarray(got["amplitude"],dtype="<f4").view("<u4"),
        np.asarray(expected["amplitude"],dtype="<f4").view("<u4"))
    assert expected_raw.tobytes()==input_digest
    assert got["original_delphi_numerical_parity_verified"] is False

    # The PREVIOUS research API retains its *explicit POST-FIR* meaning
    # so specialist callers are not silently reassigned a different FFT.
    legacy=session.spectrum_envelope(1,20,4096,profile,
                                     mode=1,backend="numpy")
    assert legacy["n_fft"]==4096
    assert legacy["source_history_samples"]==required_original_history(
        4096,65536,20)["input_samples"]
    assert legacy["source_bspec_lines_interpretation"]==(
        "RESEARCH_EXPLICIT_POST_FIR_N")
    assert len(legacy["amplitude"])==2048


@pytest.mark.parametrize("mode,unit",[
    (0,"дБ, IDR-кандидат"),(1,"м/с²"),(2,"мм/с"),(3,"мкм")])
def test_original_filter_menu_recomputes_actual_four_spectrum_modes(
        tmp_path,mode,unit):
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=9000))
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    result=flow.spectrum_envelope(
        20,4096,fake_profile(i=1.,q=.4),
        source_selected_bspec_lines=True,mode=mode,backend="numpy")
    assert result["mode"]==mode
    assert result["unit"]==unit
    assert result["n_fft"]==2048
    assert result["original_source_fft_plan"]["post_fir_fft_n"]==2048
    assert result["df_hz"]==pytest.approx(16.)
    assert len(result["frequency_hz"])==len(result["amplitude"])==1024
    assert np.isfinite(result["amplitude"]).all()
    if mode==0:
        assert result["amplitude"][0]==-180.
    else:
        assert result["amplitude"][0]==0.


def test_original_pre_fir_filter_history_fails_closed_without_padding(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=4146))
    profile=fake_profile()
    with pytest.raises(ValueError,match="Insufficient actual BIN history"):
        session.spectrum_envelope(
            1,20,4096,profile,
            source_selected_bspec_lines=True,backend="numpy")
    with pytest.raises(ValueError):
        session.spectrum_envelope(
            1,20,4096,profile,
            source_selected_bspec_lines="yes",backend="numpy")


def test_original_archive_spectrum_gui_binds_actual_post_fir_bins(qt_app,tmp_path):
    pytest.importorskip("PySide6")
    from ..desktop.main_window import MainWindow
    # Registered shared Qt fixture lives at module scope.
    w=MainWindow()
    w.show()
    try:
        w.open_archive(fixture_zip(tmp_path,sample_count=10000))
        w.set_envelope_profile(fake_profile(i=1.,q=.4))
        # Select menu N first to ensure the resulting original filter
        # uses that PRE-FIR window, not the historical post-FIR inverse.
        w.spec_n.setCurrentText("4096")
        w._select_original_envelope_popup_tag(20)
        qt_app.processEvents()
        w.refresh_spec()
        d=w._full_spectrum
        assert d is not None
        assert d["source_bspec_lines_before_fir"]==4096
        assert d["n_fft"]==2048
        assert d["source_history_samples"]==4147
        assert w._spec_display_contract["grapher_series_bins"]<1024
        assert len(d["amplitude"])==1024
        assert w._source_spectrum_readout["n_fft"]==2048
        assert "bSpecLines 4096" in w.spec_core_triplet.text()
        assert "FFT 2048" in w.spec_core_triplet.text()
    finally:
        w.close()
        qt_app.processEvents()


@pytest.mark.parametrize("code,post_n,required",[
    (20,512,1075),(1,256,1121),(4,128,1217),
])
def test_original_bspec_1024_pre_fir_has_short_real_fft_no_fake_4096(
        tmp_path,code,post_n,required):
    """Original 007CC198 FFT accepts post-FIR powers of 2 below 1024."""
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=4096))
    raw_sha=session.samples(1)[0].tobytes()
    plan=source_selected_envelope_fft_plan(1024,65536,code)
    assert plan["post_fir_fft_n"]==post_n
    assert plan["source_getadjusted_length_samples"]==required
    out=session.spectrum_envelope(
        1,code,1024,fake_profile(i=1.,q=.4),
        source_selected_bspec_lines=True,backend="numpy",mode=1)
    assert out["source_bspec_lines_before_fir"]==1024
    assert out["n_fft"]==post_n
    assert len(out["amplitude"])==post_n//2
    assert out["df_hz"]==pytest.approx(65536/1024)
    assert out["source_history_samples"]==required
    assert out["spectrum_summary"]["n_fft"]==post_n
    assert np.isfinite(out["amplitude"]).all()
    assert session.samples(1)[0].tobytes()==raw_sha
    assert out["original_delphi_numerical_parity_verified"] is False


@pytest.mark.parametrize("n,expected",[(8,3),(16,6),(512,200)])
def test_post_fir_tqgrapher_pixel_series_handles_short_source_n(n,expected):
    from ..core.tqgrapher_display_idr_candidate import spectrum_display_contract
    from ..core.spectrum_display_source import source_derived_mode_display
    from ..core.spectrum_metrics_idr_candidate import original_spectrum_summary
    source=spectrum_display_contract(n,65536)
    assert source["grapher_series_bins"]==expected
    a=np.ones(n//2,dtype="<f4")
    a[:2]=0
    for mode in range(4):
        y=source_derived_mode_display(a,n_fft=n,mode=mode,f_range=1.)
        assert len(y)==n//2
        assert np.isfinite(y).all()
        summary=original_spectrum_summary(
            a,n_fft=n,fs_out=65536,f_range=1.,spectrum_mode=mode)
        assert summary["n_fft"]==n
        assert summary["original_delphi_numerical_parity_verified"] is False


def test_live_original_bspec_short_fft_is_accepted_only_with_verified_ring():
    from ..core.original_live_envelope_provenance import (
        original_live_envelope_provenance)
    result=original_live_envelope_provenance(
        envelope_code=20,n_fft=1024,sample_rate_hz=65536,
        profile_available=True,source_ring_verified=True,
        available_elements=1075)
    assert result["source_post_fir_fft_n"]==512
    assert result["source_get_adjusted_envelope_length_samples"]==1075
    assert result["original_and_candidate_window_lengths_identical"]
    assert result["local_fir_candidate_can_compute"] is True
    assert result["live_original_fir_result_verified"] is False
    assert result["device_command_sent"] is False
    insufficient=original_live_envelope_provenance(
        envelope_code=20,n_fft=1024,sample_rate_hz=65536,
        profile_available=True,source_ring_verified=True,
        available_elements=1074)
    assert insufficient["local_fir_candidate_can_compute"] is False
    assert insufficient["reason_code"]=="SOURCE_FIR_HISTORY_INCOMPLETE"
