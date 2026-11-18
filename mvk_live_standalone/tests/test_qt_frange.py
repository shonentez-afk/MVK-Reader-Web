"""Qt displays native per-channel FRange without processing ADC twice."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")


@pytest.fixture
def gui():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6 import QtWidgets
    from mvk_live_standalone.app import LiveWindow
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w=LiveWindow()
    yield w
    w.close()
    w.deleteLater()
    app.processEvents()


def _frange_session():
    return {
        "phase":"RECORDING",
        "full_register_snapshots":1,
        "adc_frange_from_config":[510.5650329589844,24.,1.,1.,1.,1.,1.,1.],
    }


def test_gui_shows_real_frange_for_selected_adc_no_second_gain(gui):
    gui._last_status=_frange_session()
    gui._update_frange_label()
    label=gui.frange_info.text()
    assert "510.565033" in label
    assert "0x010E" in label
    assert "ровно один раз" in label
    assert "НЕ умножает второй раз" in label
    gui.adc.setCurrentIndex(1)
    gui._update_frange_label()
    assert "FRange АЦП 2 = 24" in gui.frange_info.text()
    assert "0x020E" in gui.frange_info.text()


def test_gui_does_not_show_invented_factor_before_config_or_after_clear(gui):
    gui._last_status={"phase":"RECORDING","full_register_snapshots":0}
    gui._update_frange_label()
    assert "ещё не получена" in gui.frange_info.text()
    gui._last_status=_frange_session()
    gui._update_frange_label()
    gui._clear("Новая запись")
    assert gui._last_status is None
    assert "неизвестна" in gui.frange_info.text()


def test_gui_refuses_invalid_gain_as_calibration(gui):
    session=_frange_session()
    session["adc_frange_from_config"][0]=0.
    gui._last_status=session
    gui._update_frange_label()
    assert "ОТКЛОНЁН" in gui.frange_info.text()
