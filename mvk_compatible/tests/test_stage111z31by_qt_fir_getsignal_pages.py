"""Stage111Z31BY: visible original Qt FIR X/filtered cursor & both pages.

Synthetic ZIP and synthetic FIR banks, no instrument or private IDP.
"""
from __future__ import annotations
from hashlib import sha256

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile
from ..core.original_adc_spectrum_actions import OriginalEnvelopeCursor
from ..core.original_adc_source_axes import source_adc_envelope_cursor


def test_filtered_source_adc_horizontal_time_and_cursor_from_full_fir(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    source=fixture_zip(tmp_path,sample_count=120000)
    original_sha=sha256(source.read_bytes()).hexdigest()
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(source)
        w.original_root_tabs.setCurrentIndex(3)
        w.wave_start.setValue(.75)
        w.wave_hscale_menu.actions()[9].trigger() # 20ms, 1310 raw samples
        w.set_envelope_profile(fake_profile(i=1.,q=.4))
        w.wave_envelope_code.setCurrentIndex(20)
        qt_app.processEvents()
        axis=w._source_wave_xaxes_model
        full=w._source_envelope_cursor
        assert axis is not None and axis["kind"]=="SOURCE_FIR"
        assert isinstance(full,OriginalEnvelopeCursor)
        assert full.code==20
        assert axis["series_samples"]==len(full.full_values)
        assert axis["series_samples"]>len(w._source_wave_trace["amplitude"])
        assert axis["output_sample_rate_hz"]==32768
        assert axis["required_input_samples"]==1412
        assert axis["series_xscale_single"]==pytest.approx(1000/32768,rel=1e-6)
        assert axis["axis_unit"]=="мс"
        assert axis["scr_left_single"]==20. and axis["scr_width_single"]==-20.
        vb=w.wave_plot.getViewBox()
        assert vb.state["xInverted"] is True
        assert vb.viewRange()[0]==pytest.approx([0.,20.],abs=1e-4)
        assert w.wave_plot.getPlotItem().getAxis('bottom').labelText=="мс"
        assert w._source_wave_readout is None  # FIR is NOT plain GetSignal
        assert "1412 реальной истории" in w.wave_mean_primary.toolTip()
        point=vb.mapViewToScene(QPointF(10.,0.))
        w._wave_at_scene_pos(point,force=True)
        qt_app.processEvents()
        assert w.wave_line.isVisible()
        assert "полный FIR[" in w.wave_hint.text()
        assert "OutputSampleRate" in w.wave_hint.text()
        mapped=source_adc_envelope_cursor(
            w._current_offline_flow(),w._source_wave_trace,axis,10.)
        same=full.pick(mapped["output_buffer_relative_s"])
        assert f"FIR[{same['output_index']}]" in w.wave_hint.text()
        assert "Win32" in w.wave_hint.text()
        # The original Spectrum envelope Tag is mirrored from same menu,
        # but physical spectrum mode is still opt-in and independently safe.
        assert w.spec_envelope_code.currentData()==20
        assert sha256(source.read_bytes()).hexdigest()==original_sha
    finally:
        w.close()
        qt_app.processEvents()


def test_source_envelope_tag_switch_on_spectrum_refreshes_hidden_adc_and_fft(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    source=fixture_zip(tmp_path,sample_count=120000)
    original_sha=sha256(source.read_bytes()).hexdigest()
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(source)
        w.wave_start.setValue(.75)
        w.wave_hscale_menu.actions()[9].trigger()
        w.set_envelope_profile(fake_profile(i=1.,q=.4))
        w.wave_envelope_code.setCurrentIndex(20)
        qt_app.processEvents()
        assert w._source_wave_xaxes_model["envelope_code"]==20
        # Both source pages use the same original EnvelopeCode Tag.
        w.original_root_tabs.setCurrentIndex(4)
        w.spec_n.setCurrentText("8192")
        w.spec_envelope_button.setChecked(True)
        qt_app.processEvents()
        assert w.spec_envelope_button.isChecked()
        assert w.spec_envelope_code.currentData()==20
        assert w._full_spectrum is not None
        assert len(w._full_spectrum["amplitude"])==w._full_spectrum["n_fft"]//2
        assert w._source_adc_spectrum_joint_receipt is not None
        old_full=w._source_envelope_cursor
        # Changing PageSpectrum's code while PageAdc is hidden must
        # invalidate the old FIR and calculate both source views.
        w.spec_envelope_code.setCurrentIndex(1)
        qt_app.processEvents()
        assert w.wave_envelope_code.currentData()==1
        assert w._source_envelope_cursor is not old_full
        assert w._source_wave_xaxes_model["envelope_code"]==1
        assert w._source_wave_xaxes_model["output_sample_rate_hz"]==16384
        assert w.spec_envelope_button.isChecked()
        assert w._full_spectrum is not None
        assert w._source_adc_spectrum_joint_receipt is not None
        # Source Tag0 from PageSpectrum turns both views unfiltered.
        w.spec_envelope_code.setCurrentIndex(0)
        qt_app.processEvents()
        assert w.wave_envelope_code.currentData()==0
        assert w._source_envelope_cursor is None
        assert not w.spec_envelope_button.isChecked()
        assert w._full_spectrum is not None
        assert w._source_wave_xaxes_model is not None
        assert w._source_wave_xaxes_model.get("kind")!="SOURCE_FIR"
        # Confirm the remaining five pages still share the same ZIP/ADC.
        for index in (0,1,2,5,6):
            w.original_root_tabs.setCurrentIndex(index)
            qt_app.processEvents()
            assert w._current_offline_flow().channel==1
            assert w.session is not None
        assert sha256(source.read_bytes()).hexdigest()==original_sha
    finally:
        w.close()
        qt_app.processEvents()
