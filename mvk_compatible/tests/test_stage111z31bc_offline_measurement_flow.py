"""Stage111Z31BC: one verified source for File, ADC, Spectrum and Status.

All Native ZIP/TSXML files in this test are synthetic and local.  The
existing FFT, GetSignal and DSP validators are executed without mocks.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.direct_bin_session import DirectBinSession
from mvk_compatible.core.offline_measurement_flow import (
    OfflineMeasurementFlow, SOURCE, SOURCE_ZIP, SOURCE_BIN,
)
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair


def test_native_one_session_provenance_tick_channel_and_four_surfaces(tmp_path):
    source=OfflineSession.open(fixture_zip(tmp_path, sample_count=4096))
    flow=OfflineMeasurementFlow.bind(source)
    assert flow.session is source
    assert flow.channel==1 and flow.tick_index==source.updates-1
    record=flow.source_record()
    assert record["source"]==SOURCE
    assert record["measurement_kind"]==SOURCE_ZIP
    assert record["selected_channel"]==1
    assert record["available_channels"]==list(range(1,9))
    assert record["selected_dsp_tick_index"]==source.updates-1
    assert record["dsp_values_available"]
    assert record["source_identity_not_crossed"]
    assert not record["original_runtime_parity_verified"]
    assert not record["physical_calibration_original_runtime_verified"]
    assert len(record["source_bin_sha256"])==64
    assert not record["fft_or_signal_recomputed_by_flow"]
    assert "path" not in record and "bin_bytes" not in record
    assert str(tmp_path) not in str(record)

    status=flow.status_snapshot()
    assert status is not None
    assert status["serial"]==source.serial and status["tick"]==flow.tick_index
    assert status["channels"][0]["channel"]==1
    assert len(status["channels"][0]["third_octave"])==43
    assert len(flow.status_table(5).bands_for_plot)==43

    waved=flow.waveform(0,.04,"ac",points=300,display_order="chronological")
    baseline_wave=source.waveform(1,0,.04,"ac",points=300,
                                  display_order="chronological")
    for key in ("window_samples","rms_m_s2","removed_mean_m_s2","source"):
        assert waved[key]==baseline_wave[key]
    np.testing.assert_array_equal(waved["amplitude"],baseline_wave["amplitude"])
    np.testing.assert_array_equal(waved["time_s"],baseline_wave["time_s"])

    fft=flow.spectrum(1024,0,0,max_hz=1e9,max_points=512)
    baseline_fft=source.spectrum(1,1024,0,0,max_hz=1e9,max_points=512)
    np.testing.assert_array_equal(
        fft["amplitude"].astype("<f4").view("<u4"),
        baseline_fft["amplitude"].astype("<f4").view("<u4"))
    assert fft["channel"]==status["channels"][0]["channel"]
    assert fft["source"]==baseline_fft["source"]


def test_select_new_tick_and_channel_never_reuses_previous_dsp(tmp_path):
    s=OfflineSession.open(fixture_zip(tmp_path, sample_count=4096))
    f=OfflineMeasurementFlow.bind(s,channel=3,tick_index=0)
    assert f.status_snapshot()["tick"]==0
    g=f.select(channel=8,tick_index=1)
    assert g.channel==8 and g.tick_index==1
    assert g.status_snapshot()["channels"][g.channel-1]["channel"]==8
    assert g.status_table(12).index==12
    assert f.channel==3 and f.tick_index==0
    assert g.source_record()["selected_dsp_tick_index"]==1
    assert g.source_record()["selected_channel"]==8
    # Different opened session object is never a compatible source,
    # even when the private serial or bytes look identical.
    second=OfflineSession.open(s.path)
    assert second is not s
    with pytest.raises(ValueError,match="Unrelated sessions"):
        f.require_session(second)


def test_direct_bin_is_only_selected_adc_without_dsp_or_fake_units(tmp_path):
    p,sidecar,original=_make_pair(tmp_path,adc=4,n=8192)
    s=DirectBinSession.open(p)
    f=OfflineMeasurementFlow.bind(s)
    assert f.available_channels==(4,)
    assert f.channel==4 and f.tick_index==0
    rec=f.source_record()
    assert rec["measurement_kind"]==SOURCE_BIN
    assert rec["available_channels"]==[4]
    assert rec["selected_dsp_tick_index"] is None
    assert rec["dsp_values_available"] is False
    assert rec["physical_units_unverified_for_direct_bin"] is True
    assert rec["source_bin_sha256"]==s.channel_files[0].bin_sha256
    assert f.status_snapshot() is None
    assert f.status_table(0).bands_for_plot is None
    assert f.status_table(5).bands_for_plot is None
    assert not any("43 полосы" in str(x) for x in f.status_table(5).rows)
    assert "Нет подтверждённого" in f.status_table(5).note

    wave=f.waveform(0,.04,"ac",points=300)
    assert wave["physical_units_verified"] is False
    spec=f.spectrum(4096,1,0,max_hz=1e9,max_points=2048)
    assert spec["physical_units_verified"] is False
    assert spec["channel"]==4
    with pytest.raises(ValueError):
        f.select(channel=1)
    with pytest.raises(ValueError):
        f.select(tick_index=1)


@pytest.mark.parametrize("alter",[
    lambda f:f.select(channel=True),
    lambda f:f.select(channel=9),
    lambda f:f.select(tick_index=-1),
    lambda f:f.select(tick_index=1_000_000),
])
def test_context_selection_rejects_invalid_or_fabricated_evidence(tmp_path,alter):
    s=OfflineSession.open(fixture_zip(tmp_path))
    with pytest.raises(ValueError):
        alter(OfflineMeasurementFlow.bind(s))


def test_mutated_original_direct_bin_is_detected_again_by_coordinator(tmp_path):
    p,_,_= _make_pair(tmp_path,adc=4,n=8192)
    s=DirectBinSession.open(p)
    f=OfflineMeasurementFlow.bind(s)
    assert f.source_record()["sample_count"]==8192
    raw=bytearray(p.read_bytes())
    raw[8]^=1
    p.write_bytes(raw)
    with pytest.raises(ValueError):
        f.source_record()
    with pytest.raises(ValueError):
        f.waveform(0,.04,"ac",points=300)


def test_bad_cross_session_or_unverified_object_cannot_bind(tmp_path):
    with pytest.raises(ValueError):
        OfflineMeasurementFlow.bind(object())
    s=OfflineSession.open(fixture_zip(tmp_path))
    with pytest.raises(ValueError):
        OfflineMeasurementFlow(s,channel=0)
    with pytest.raises(ValueError):
        OfflineMeasurementFlow(s,channel=False)
    with pytest.raises(ValueError):
        OfflineMeasurementFlow(s,tick_index=True)
