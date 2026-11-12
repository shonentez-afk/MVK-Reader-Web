"""Stage111Z31BL: source-bound FRange/H display does NOT alter GetSpectrum.

All fixtures are synthetic, no original private bytes, device, IDP or
Delphi running-process parity. Verifies channel/sha, Float32 source gain
and original 10 Hz pages with one same-file full N/2 FFT.
"""
import pytest
import numpy as np

from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_offline_core import fixture_zip
from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.direct_bin_session import DirectBinSession
from mvk_compatible.core.offline_measurement_flow import OfflineMeasurementFlow
from mvk_compatible.core.original_spectrum_view_binding import (
    source_spectrum_gain,source_spectrum_h_view,SOURCE_GAIN,
    SOURCE_MISSING,HORIZONTAL_HZ,
)


def _flow_and_spectrum(tmp_path,*,gain=None,n=16384,adc=4):
    path,sidecar,raw=_make_pair(tmp_path,adc=adc,n=n)
    if gain is not None:
        text=sidecar.read_text(encoding="utf-8")
        sidecar.write_text(text.replace(
            "</Channel>",f"<InternalChannelGain>{gain}</InternalChannelGain>"
            "</Channel>"),encoding="utf-8")
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(path))
    spec=flow.spectrum(4096,0,0.,max_hz=1e9,max_points=2048,
                       backend="idr_float32")
    assert len(spec["amplitude"])==2048
    return flow,spec


@pytest.mark.parametrize("gain,expect_value,expect_origin",[
    ("6.25",6.25,SOURCE_GAIN),
    ("0",None,SOURCE_MISSING),
    ("-2",None,SOURCE_MISSING),
    (None,None,SOURCE_MISSING),
])
def test_source_frange_is_explicit_tsxml_single_not_manual_calibration(
        tmp_path,gain,expect_value,expect_origin):
    flow,spec=_flow_and_spectrum(tmp_path,gain=gain)
    context=source_spectrum_gain(flow,spec,mode=0)
    assert context.channel==4
    assert context.source_bin_sha256==flow.source_record()["source_bin_sha256"]
    assert context.frange_single==expect_value
    assert context.origin==expect_origin
    assert not context.original_runtime_frange_verified
    assert not context.source_bin_physical_calibration_verified
    assert context.provenance()["fft_scaled_by_this_view"] is False
    if expect_value is None:
        assert context.graph_default_vscale_candidate is None
        assert "не установлен" in context.label
    else:
        assert context.graph_default_vscale_candidate>0
        assert "не калибровка" in context.label
        assert context.original_loader_branch==(
            "DECLARED_POSITIVE_NO_APPLY_RANGE_SOURCE_BRANCH")
    # Display-only gain is not a source of new FFT samples or AUX4700.
    assert flow.status_snapshot() is None


def test_source_gain_changes_original_mode_candidate_not_original_sample_bytes(
        tmp_path):
    flow,first=_flow_and_spectrum(tmp_path,gain="3.5")
    raw_samples=flow.samples()[0].copy().view("<u4")
    s0=source_spectrum_gain(flow,first,mode=0)
    second=flow.spectrum(4096,2,0.,max_hz=1e9,max_points=2048,
                        backend="idr_float32")
    s2=source_spectrum_gain(flow,second,mode=2)
    assert s0.frange_single==s2.frange_single==3.5
    assert s0.graph_default_vscale_candidate!=(
        s2.graph_default_vscale_candidate)
    np.testing.assert_array_equal(
        flow.samples()[0].copy().view("<u4"),raw_samples)
    assert second["channel"]==first["channel"]==4


@pytest.mark.parametrize("hz",HORIZONTAL_HZ)
def test_all_ten_source_h_scale_pages_leave_full_fft_unchanged(
        tmp_path,hz):
    flow,spec=_flow_and_spectrum(tmp_path)
    words=np.asarray(spec["amplitude"],dtype="<f4").view("<u4").copy()
    max_pos=HORIZONTAL_HZ[0]-hz
    state=source_spectrum_h_view(
        flow,spec,selected_hz=hz,position_hz=min(1500,max_pos))
    assert state.channel==4
    assert state.n_fft==4096
    assert state.fft_bins==2048
    assert state.source_series_bins<=state.fft_bins
    assert state.selected_page_hz==hz
    assert state.x_bounds[1]-state.x_bounds[0]==hz
    assert state.native_qt_maximum==max_pos
    assert state.source_bin_sha256==flow.source_record()["source_bin_sha256"]
    assert not state.original_runtime_canvas_verified
    assert state.provenance()["fft_values_changed"] is False
    np.testing.assert_array_equal(
        np.asarray(spec["amplitude"],dtype="<f4").view("<u4"),words)


def test_no_mixed_bin_adc_or_truncated_fft_used_to_draw_original_scope(
        tmp_path):
    flow,spec=_flow_and_spectrum(tmp_path,gain="1.125")
    wrong=flow.select(channel=4)  # still same; explicitly tamper FFT ADC
    cross={**spec,"channel":3}
    with pytest.raises(ValueError,match="ADC"):
        source_spectrum_h_view(flow,cross,selected_hz=6400)
    with pytest.raises(ValueError,match="ADC"):
        source_spectrum_gain(flow,cross,mode=0)
    partial={**spec,"amplitude":spec["amplitude"][:-1]}
    with pytest.raises(ValueError,match="N/2"):
        source_spectrum_h_view(flow,partial,selected_hz=6400)
    with pytest.raises(ValueError,match="mode"):
        source_spectrum_gain(flow,spec,mode=2)
    with pytest.raises(ValueError):
        source_spectrum_h_view(flow,spec,selected_hz=1234)
    with pytest.raises(ValueError):
        source_spectrum_h_view(flow,spec,selected_hz=6400,position_hz=20000)
    # A valid Native ZIP is not given a fabricated TSXML gain.
    zip_flow=OfflineMeasurementFlow.bind(
        OfflineSession.open(fixture_zip(tmp_path,sample_count=8192)))
    zip_fft=zip_flow.spectrum(4096,0,0.,max_hz=1e9,max_points=2048)
    context=source_spectrum_gain(zip_flow,zip_fft,mode=0)
    assert context.frange_single is None and context.origin==SOURCE_MISSING
    assert context.graph_default_vscale_candidate is None
