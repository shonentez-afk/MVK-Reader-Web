"""Stage111Z31BX: actual Qt source ADC reverse-X, FRange Y and linked FFT."""
from __future__ import annotations
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair


def test_source_getsignal_x_and_mouse_cursor_vs_original_buffer_order(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    p=fixture_zip(tmp_path,sample_count=8192)
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(p)
        w.original_root_tabs.setCurrentIndex(3)
        w.wave_hscale_menu.actions()[9].trigger() # source 20 ms, 1310 samples
        qt_app.processEvents()
        axes=w._source_wave_xaxes_model
        assert w.wave_order.currentIndex()==2
        assert w._source_wave_trace["display_order"]=="getsignal_buffer"
        assert axes["axis_unit"]=="мс"
        assert axes["scr_width_single"]==-20.
        assert axes["series_samples"]==1310
        vb=w.wave_plot.getViewBox()
        assert vb.state["xInverted"] is True
        bounds=vb.viewRange()[0]
        assert bounds[0]==pytest.approx(0.,abs=1e-4)
        assert bounds[1]==pytest.approx(20.,abs=1e-4)
        point=vb.mapViewToScene(QPointF(10.,0.))
        w._wave_at_scene_pos(point,force=True)
        qt_app.processEvents()
        assert w.wave_line.isVisible()
        assert "GetSignal" in w.wave_hint.text()
        assert "исходная обратная ось" in w.wave_hint.text()
        assert w._source_adc_spectrum_joint_receipt is not None
        assert w._source_adc_spectrum_joint_receipt["adc"]==1
        assert w._source_adc_spectrum_joint_receipt["source_bin_sha256"]==(
            axes["source_bin_sha256"])
        # Research chronological view remains available, explicitly separate.
        w.wave_order.setCurrentIndex(0)
        w.refresh_wave()
        assert w._source_wave_xaxes_model is None
        assert w.wave_plot.getViewBox().state["xInverted"] is False
        w.adc.setCurrentIndex(1)
        qt_app.processEvents()
        assert w._source_adc_spectrum_joint_receipt is not None
        assert w._source_adc_spectrum_joint_receipt["adc"]==2
    finally:
        w.close()
        qt_app.processEvents()


def test_direct_bin_current_tsxml_f_range_drives_adc_and_spectrum_separately(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    p,xml,_=_make_pair(tmp_path,adc=4,n=8192)
    xml.write_text(xml.read_text(encoding="utf-8").replace(
        "</Channel>","<InternalChannelGain>6.25</InternalChannelGain></Channel>"),
        encoding="utf-8")
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(p)
        w.original_root_tabs.setCurrentIndex(3)
        w.wave_hscale_menu.actions()[9].trigger()
        w.wave_vscale_menu.actions()[2].trigger()
        qt_app.processEvents()
        y=w._source_wave_scale_model
        assert y["source_f_range_single"]==6.25
        assert y["graph_default_vscale_candidate"]==10.
        assert y["y_min"]==-2. and y["y_max"]==2.
        assert "условн" in y["unit"]
        assert w._source_wave_xaxes_model["selected_adc"]==4
        y_range=w.wave_plot.getViewBox().viewRange()[1]
        assert y_range[0]==pytest.approx(-2.)
        assert y_range[1]==pytest.approx(2.)
        w.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        assert w._source_spectrum_gain is not None
        assert w._source_spectrum_gain.frange_single==6.25
        assert w._source_adc_spectrum_joint_receipt is not None
        assert w._source_adc_spectrum_joint_receipt["adc"]==4
        assert "original Win32 runtime" in w.spec_core_triplet.toolTip()
        w._close_session()
        assert w._source_wave_xaxes_model is None
        assert w._source_adc_spectrum_joint_receipt is None
    finally:
        w.close()
        qt_app.processEvents()
