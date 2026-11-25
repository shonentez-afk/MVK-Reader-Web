"""Public synthetic coverage; no original BIN/IDP or memory images."""
from datetime import datetime, timezone

import numpy as np
import pytest

from .test_desktop_qt import qt_app
from .test_stage111z31bv_adc_spectrum_actions_core import _native
from ..core.original_mode2_source_files import build_original_tsxml_compatible
from ..core.original_adc_spectrum_actions import (
    OriginalSpectrumAction, append_source_spec_freq_csv,
)
from ..core.direct_bin_session import DirectBinSession


def _saved_adc(tmp_path):
    n, fs, gain = 134000, 65536, 12.25
    name = "MVK00000001-ADC1-2026-11-24--10-10-00.bin"
    path = tmp_path / name
    t = np.arange(n, dtype=float)/fs
    path.write_bytes(np.asarray((1+t)*np.sin(2*np.pi*128*t), dtype="<f4").tobytes())
    xml, _ = build_original_tsxml_compatible(
        channel=1,binary_basename=name,size_bytes=n*4,rate_hz=fs,
        local_time=datetime(2026,11,24,10,10,3,tzinfo=timezone.utc),
        device_label="MVK00000001",channel_label="ADC1",adc_units="m/s2",adc_gain=gain)
    sidecar=tmp_path/(name+".tsxml")
    sidecar.write_bytes(xml)
    return path, sidecar, fs, gain


def test_complete_mode1_pair_but_not_arbitrary_renamed_bin(tmp_path):
    path,sidecar,_,gain=_saved_adc(tmp_path)
    s=DirectBinSession.open(path)
    assert s.mode1_adc_range(1)==gain
    assert s.mode1_adc_range(2) is None
    renamed=tmp_path/"research.bin"
    renamed.write_bytes(path.read_bytes())
    renamed.with_suffix(".tsxml").write_bytes(sidecar.read_bytes().replace(
        path.name.encode(),renamed.name.encode()))
    assert DirectBinSession.open(renamed).mode1_adc_range(1) is None


def test_mode1_uses_one_right_endpoint_and_no_export_for_empty_history(
        tmp_path, qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ..desktop.main_window import MainWindow
    monkeypatch.setattr(QMessageBox,"warning",lambda *args: pytest.fail(str(args[-1])))
    path,_,fs,gain=_saved_adc(tmp_path)
    w=MainWindow()
    try:
        w.open_archive(path)
        assert w.wave_seconds.value()==.5
        assert not w.spec_last.isChecked()
        bar=w.original_shell.view_slider
        assert bar.value()==bar.maximum()
        end=w._source_view_time.selected_start_sample
        d=w._full_spectrum
        assert d['input_source_window']['last_archive_sample_exclusive']==end
        assert d['f_range_used']==gain
        assert d['input_domain']=='original_float_storage'
        assert not d['physical_units_verified']
        assert w._source_wave_trace['input_source_window']['last_archive_sample_exclusive']==end
        assert w._source_wave_trace['window_samples']==fs//2
        w.spec_n.setCurrentText('8192')
        bar.setValue(bar.maximum()//2)
        d=w._full_spectrum
        end=w._source_view_time.selected_start_sample
        assert d['input_source_window']['last_archive_sample_exclusive']==end
        assert w._source_wave_trace['input_source_window']['last_archive_sample_exclusive']==end
        manual=w.session.spectrum(1,8192,w.spec_mode.currentIndex(),(end-8192)/fs,
            max_hz=1e9,max_points=4096,f_range=gain,input_domain='original_float_storage')
        np.testing.assert_array_equal(d['amplitude'],manual['amplitude'])
        bar.setValue(0)
        assert w._full_spectrum is None and not w.spec_save_button.isEnabled()
        assert w._source_wave_trace is None
        assert 'только отображение' in w.spec_hint.text()
        bar.setValue(bar.maximum())
        assert w._full_spectrum is not None
        from ..core.envelope_idr_candidate import EnvelopeProfile
        banks=np.zeros((10,512),dtype="<f4")
        banks[:,0]=1.
        w.set_envelope_profile(EnvelopeProfile(banks,provenance="SYNTHETIC_QA"))
        w.spec_n.setCurrentText('8192')
        w._select_original_hscale(12800)
        w.spec_envelope_code.setCurrentIndex(w.spec_envelope_code.findData(31))
        w.spec_envelope_button.setChecked(True)
        assert w._full_spectrum['n_fft'] < 8192
        assert w.spec_plot.getViewBox().viewRange()[0]==pytest.approx([0,12800])
        w.spec_envelope_code.setCurrentIndex(w.spec_envelope_code.findData(0))
        assert w._full_spectrum['n_fft']==8192
        assert w.spec_plot.getViewBox().viewRange()[0]==pytest.approx([0,12800])
        assert w.spec_hscale_button.text()=='12800 Гц'
    finally:
        w.close()


def test_spec_freq_honors_selected_numeric_locale_without_mixing_rows(tmp_path):
    _,flow,spectrum=_native(tmp_path)
    action=OriginalSpectrumAction.from_view(flow,spectrum)
    dest=tmp_path/"SPEC-FREQ-2026-11-24.csv"
    for _ in range(2):
        append_source_spec_freq_csv(action,flow,dest,spectrum=spectrum,decimal_separator='.')
    raw=dest.read_bytes()
    assert raw.count(b"sep=|")==1
    assert raw.split(b"\r\n")[2:4]==[action.pipe_row(decimal_separator='.').encode()]*2
    with pytest.raises(ValueError, match="decimal separator"):
        append_source_spec_freq_csv(action,flow,dest,spectrum=spectrum,decimal_separator=',')
    assert dest.read_bytes()==raw
