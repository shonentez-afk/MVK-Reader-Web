"""PageAdc popup acceptance against four owner screenshots (2026-11-23).

All Qt windows use synthetic BIN/TSXML. This is a screenshot-based UI
regression, NOT a physical-device or Win32/x87 calibration oracle.
"""
import pytest

from ..core.original_adc_view_controls import (
    ADC_HORIZONTAL_MS, ADC_VERTICAL_DIVISORS,
    original_adc_vertical_options, original_adc_vertical_physical_caption,
)
from ..core.original_envelope_shared_menu import SOURCE_ORIGINAL_FILTER_CAPTIONS
from .test_desktop_qt import qt_app


def test_original_wave_popup_tables_and_1000_reference():
    assert ADC_HORIZONTAL_MS == (
        20000,10000,5000,2000,1000,500,200,100,50,20,10,5,2,1)
    assert ADC_VERTICAL_DIVISORS == (
        1,2,5,10,20,50,100,200,500,1000,2000,5000,10000)
    assert len(SOURCE_ORIGINAL_FILTER_CAPTIONS)==32
    assert [r["caption"] for r in original_adc_vertical_options(
        baseline_m_s2=1000.)] == [
        "1000 м/с2", "500 м/с2", "200 м/с2", "100 м/с2",
        "50 м/с2", "20 м/с2", "10 м/с2", "5 м/с2",
        "2 м/с2", "1 м/с2", "0,5 м/с2", "0,2 м/с2",
        "0,1 м/с2",
    ]
    with pytest.raises(ValueError):
        original_adc_vertical_physical_caption(13,1000.)
    with pytest.raises(ValueError):
        original_adc_vertical_physical_caption(0,float("nan"))
    with pytest.raises(ValueError):
        original_adc_vertical_physical_caption(0,0.)
    assert original_adc_vertical_physical_caption(2,200.)=="40 м/с2"


def test_wave_qt_4_original_popup_menus_and_selection(qt_app,tmp_path):
    pytest.importorskip("PySide6")
    from ..desktop.main_window import MainWindow
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    path,sidecar,_ = _make_pair(tmp_path,adc=4,n=8192,fs=65536)
    raw=sidecar.read_text(encoding="utf-8")
    sidecar.write_text(raw.replace(
        "</Channel>",
        "<InternalChannelGain>510.6</InternalChannelGain></Channel>"),
        encoding="utf-8")
    win=MainWindow()
    win.show()
    try:
        win.open_archive(path)
        win.tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert [a.text() for a in win.wave_type_menu.actions()]==["AC","AC+DC"]
        assert [a.text() for a in win.wave_hscale_menu.actions()]==[
            "20 с","10 с","5 с","2 с","1 с","500 мс","200 мс",
            "100 мс","50 мс","20 мс","10 мс","5 мс","2 мс","1 мс"]
        assert [a.text() for a in win.wave_vscale_menu.actions()]==[
            r["caption"] for r in original_adc_vertical_options(
                baseline_m_s2=1000.)]
        assert len(win.original_envelope_menu.actions())==32
        assert [a.text() for a in win.original_envelope_menu.actions()]==list(
            SOURCE_ORIGINAL_FILTER_CAPTIONS)
        assert win.wave_vscale_button.text()=="1000 м/с2"
        assert [i for i,a in enumerate(win.wave_vscale_menu.actions())
                if a.isChecked()]==[0]
        win.wave_type_menu.actions()[1].trigger()
        win.wave_hscale_menu.actions()[5].trigger()
        win.wave_vscale_menu.actions()[10].trigger()
        qt_app.processEvents()
        assert win.wave_type_button.text()=="AC+DC"
        assert win.wave_hscale_button.text()=="500 мс"
        assert win.wave_vscale_button.text()=="0,5 м/с2"
        assert [i for i,a in enumerate(win.wave_vscale_menu.actions())
                if a.isChecked()]==[10]
        assert "калибровка не подтверждена" in (
            win.wave_vscale_button.toolTip())
        assert win._source_wave_scale_model is not None
        assert win._source_wave_scale_model[
            "axis_baseline_m_s2_nominal"]==pytest.approx(1000.)
    finally:
        win.close()


def test_wave_no_frange_numeric_labels_disclose_local_fallback(qt_app,tmp_path):
    pytest.importorskip("PySide6")
    from ..desktop.main_window import MainWindow
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    path,_,_=_make_pair(tmp_path,adc=1,n=8192,fs=65536)
    win=MainWindow()
    win.show()
    try:
        win.open_archive(path)
        win.tabs.setCurrentIndex(1)
        qt_app.processEvents()
        captions=[a.text() for a in win.wave_vscale_menu.actions()]
        assert len(captions)==13
        assert all("м/с2" in item for item in captions)
        assert not any("диапазона" in item for item in captions)
        assert win.wave_vscale_button.text()==captions[win._wave_vscale_tag]
        assert "калибровка не подтверждена" in (
            win.wave_vscale_button.toolTip())
        assert win._source_wave_scale_model["source_f_range_single"] is None
    finally:
        win.close()
