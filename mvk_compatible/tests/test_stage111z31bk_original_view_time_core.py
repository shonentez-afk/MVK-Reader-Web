"""Stage111Z31BK: original pnView timing -> actual GetSignal/FFT readout Core.

Synthetic BIN/TSXML and Native R6.1 ZIP only. No original process,
instrument, reference bitmap or private material. Source branches are
not claims of Delphi runtime/pixel parity.
"""
import math
import pytest

from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.direct_bin_session import DirectBinSession
from mvk_compatible.core.offline_measurement_flow import OfflineMeasurementFlow
from mvk_compatible.core.original_view_time_source import (
    SOURCE,source_view_time,source_wave_readout,
    source_spectrum_readout,source_linked_caption,
)


@pytest.mark.parametrize("n,fs,expected_tag,step",(
    (8192,65536,0,0.01),  # <60 s, hundredths
    (600,10,1,0.1),      # exactly 60 s, tenths
    (6000,10,2,1.),      # exactly 600 s, seconds
    (8192,1,3,10.),      # >6000 s, tens
))
def test_four_original_time_scale_branches_on_real_checked_bin(
        tmp_path,n,fs,expected_tag,step):
    path,_,_=_make_pair(tmp_path,adc=4,n=n,fs=fs)
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(path))
    source=flow.source_record()
    time=source_view_time(flow)
    assert time.source_tag==expected_tag
    assert time.seconds_per_position==step
    assert time.adc==4
    assert time.bin_sha256==source["source_bin_sha256"]
    assert time.minimum==(1 if expected_tag==3 else 0)
    assert not time.source_runtime_parity_verified
    assert not time.write_to_instrument_allowed
    p=time.minimum if time.minimum else min(3,time.maximum)
    active=source_view_time(flow,position=p)
    assert active.selected_start_sample==min(
        n-1,max(0,round(p*step*fs)))
    assert active.selected_start_seconds==pytest.approx(
        active.selected_start_sample/fs,abs=1e-9)
    assert active.position==p
    assert active.summary()["instrument_write_enabled"] is False


def test_original_time_roundtrip_clamping_and_out_of_range(tmp_path):
    path,_,_=_make_pair(tmp_path,n=8192)
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(path))
    p=source_view_time(flow,position=5)
    assert p.label.startswith("00:00:00.")
    assert p.selected_start_sample>0
    again=source_view_time(flow,requested_start_s=p.selected_start_seconds)
    assert again.position==p.position
    assert again.bin_sha256==p.bin_sha256
    last=source_view_time(flow,requested_start_s=99999)
    assert last.position==last.maximum
    with pytest.raises(ValueError):
        source_view_time(flow,position=last.maximum+1)
    with pytest.raises(ValueError):
        source_view_time(flow,position=True)
    with pytest.raises(ValueError):
        source_view_time(flow,requested_start_s=float("nan"))
    with pytest.raises(ValueError):
        source_view_time(flow,position=1,requested_start_s=.01)


def test_real_core_getsignal_rms_and_spectrum_summary_share_source(tmp_path):
    path,_,_=_make_pair(tmp_path,adc=4,n=8192,fs=65536)
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(path))
    view=source_view_time(flow,position=3)
    wave=flow.waveform(view.selected_start_seconds,.06,"ac",points=1000)
    label=source_wave_readout(flow,wave,view)
    assert label["rms_from_core"]==pytest.approx(wave["rms_m_s2"])
    assert label["removed_dc_from_core"]==pytest.approx(
        wave["removed_mean_m_s2"])
    assert label["source_start_sample"]==view.selected_start_sample
    assert not label["physical_calibration_verified"]
    assert "VALUES/AUX НЕТ" in source_linked_caption(flow,view)
    spec=flow.spectrum(4096,1,0.,max_hz=65536,max_points=2048,
                       backend="idr_float32")
    summary=source_spectrum_readout(
        flow,spec,4096,archive_end=True,view_time=view)
    assert summary["fft_bins"]==2048
    assert summary["spectrum_rms_from_core"]==pytest.approx(
        spec["spectrum_summary"]["output_mean"])
    assert summary["peak_frequency_hz_from_core"]==pytest.approx(
        spec["spectrum_summary"]["output_peak_frequency_hz"])
    assert summary["peak_y_from_core"]==pytest.approx(
        spec["spectrum_summary"]["output_peak_y"])
    assert summary["df_hz"]==pytest.approx(16.)
    assert summary["archive_end_selected"] is True
    assert summary["source"]==SOURCE
    assert summary["physical_calibration_verified"] is False
    assert summary["original_runtime_parity_verified"] is False


def test_reject_mixed_source_adc_and_status_tick(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=8192))
    a=OfflineMeasurementFlow.bind(session,channel=1,tick_index=1)
    b=a.select(channel=2)
    tb=source_view_time(b)
    wave=a.waveform(0,.05,"ac")
    with pytest.raises(ValueError,match="provenance mismatch"):
        source_wave_readout(a,wave,tb)
    spec=a.spectrum(4096,1,0.,max_hz=10000.,max_points=2048)
    with pytest.raises(ValueError,match="provenance mismatch"):
        source_spectrum_readout(
            a,spec,4096,archive_end=False,view_time=tb)
    with pytest.raises(ValueError,match="mixed"):
        source_linked_caption(a,tb)
    ta=source_view_time(a)
    verified=a.status_snapshot()
    assert "VALUES 2/2" in source_linked_caption(
        a,ta,verified_status=verified)
    stale=a.select(tick_index=0)
    with pytest.raises(ValueError,match="Stale"):
        source_linked_caption(stale,ta,verified_status=verified)
    with pytest.raises(ValueError,match="source-derived"):
        source_spectrum_readout(
            a,{**spec,"spectrum_summary":None},4096,
            archive_end=True,view_time=ta)
    with pytest.raises(ValueError,match="N/2"):
        source_spectrum_readout(
            a,spec,8192,archive_end=True,view_time=ta)
