"""Actual Qt source screenshot popup menus + data-bounded horizontal width.

No physical hardware or private original files. Native original H table is
static, while low-Fs Qt DATA VIEW intentionally prevents empty frequencies.
"""
import hashlib

import numpy as np
import pytest
pytest.importorskip("PySide6")

from ..core.mvk_original_scale_tables_idr_candidate import (
    HORIZONTAL_HZ,PHYSICAL_Y_DIVISORS,DB_Y_RANGES,
    original_physical_y_caption)
from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair


def _with_gain(path, gain):
    raw=path.read_text(encoding="utf-8")
    path.write_text(raw.replace(
        "</Channel>",f"<InternalChannelGain>{gain}</InternalChannelGain></Channel>"),
        encoding="utf-8")


def _f32_spectrum_sha(win):
    return hashlib.sha256(np.asarray(
        win._full_spectrum["amplitude"],dtype="<f4").tobytes()).hexdigest()


def test_original_menu_screenshot_all_units_Y_with_same_current_tsxml_frange(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    p,sidecar,_=_make_pair(tmp_path,adc=4,n=8192,fs=65536)
    _with_gain(sidecar,"510.6")
    w=MainWindow()
    w.show()
    try:
        w.open_archive(p)
        qt_app.processEvents()
        assert [a.text() for a in w.spec_type_menu.actions()]==[
            "Логарифмич.","Линейный ВУ","Линейный ВС","Линейный ВП"]
        assert [a.text() for a in w.spec_lines_menu.actions()]==[
            "1/4 Гц/лин","1/2 Гц/лин","1 Гц/лин",
            "2 Гц/лин","4 Гц/лин","8 Гц/лин"]
        assert [a.text() for a in w.spec_hscale_menu.actions()]==[
            f"{hz} Гц" for hz in HORIZONTAL_HZ]
        assert [a.text() for a in w.spec_vscale_menu.actions()]==[
            f"{db} дБ" for db in DB_Y_RANGES]
        assert w.spec_plot.getAxis("left").labelText=="дБ"
        assert w._spec_original_vscale_tag==0

        for mode,basis,unit in ((1,1000,"м/с²"),(2,10000,"мм/с"),
                                (3,100000,"мкм")):
            w.spec_mode.setCurrentIndex(mode)
            qt_app.processEvents()
            assert w._source_spectrum_gain.frange_single==pytest.approx(510.6,rel=1e-6)
            assert w._spec_original_vscale_tag==3
            assert w.spec_plot.getAxis("left").labelText==unit
            expected=[original_physical_y_caption(mode,basis/d)
                      for d in PHYSICAL_Y_DIVISORS]
            assert [a.text() for a in w.spec_vscale_menu.actions()]==expected
            assert w.spec_vscale_button.text()==expected[3]
            assert sum(a.isChecked() for a in w.spec_vscale_menu.actions())==1
            assert w._spec_vscroll_source_candidate[
                "source_tsxml_f_range_static_candidate_used"] is True
            before=_f32_spectrum_sha(w)
            w._select_original_vscale(5)
            qt_app.processEvents()
            assert w.spec_vscale_button.text()==expected[5]
            assert _f32_spectrum_sha(w)==before
            w._select_original_vscale(3)
        w.spec_mode.setCurrentIndex(0)
        qt_app.processEvents()
        assert w.spec_plot.getAxis("left").labelText=="дБ"
        assert [a.text() for a in w.spec_vscale_menu.actions()]==[
            f"{db} дБ" for db in DB_Y_RANGES]
    finally:
        w.close()
        qt_app.processEvents()


def test_no_frange_research_local_Y_numeric_labels_not_divisors(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    p,_,_=_make_pair(tmp_path,adc=4,n=8192)
    w=MainWindow()
    w.show()
    try:
        w.open_archive(p)
        w.spec_mode.setCurrentIndex(1)
        qt_app.processEvents()
        assert w._source_spectrum_gain.frange_single is None
        model=w._spec_vscroll_source_candidate
        assert model["qt_y_baseline_from_local_spectrum"]
        base=model["research_local_full_y_baseline"]
        assert base>0
        assert [a.text() for a in w.spec_vscale_menu.actions()]==[
            original_physical_y_caption(1,base/d)
            for d in PHYSICAL_Y_DIVISORS]
        assert w.spec_vscale_button.text().endswith(" м/с²")
        assert all("÷" not in action.text() for action in w.spec_vscale_menu.actions())
        assert "калибровка" in w.spec_vscale_button.toolTip()
        assert "не подтверждена" in w.spec_plot.getAxis("left").toolTip()
    finally:
        w.close()
        qt_app.processEvents()


def test_ten_hz_rows_adapt_to_true_3200_band_without_fake_25600_bins(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    p,_,_=_make_pair(tmp_path,adc=4,n=8192,fs=8192)
    w=MainWindow()
    w.show()
    try:
        w.open_archive(p)
        qt_app.processEvents()
        assert w._full_spectrum is not None
        axis_end=w._spec_display_contract["grapher_axis_end_frequency_hz"]
        assert axis_end==pytest.approx(3200)
        assert [a.text() for a in w.spec_hscale_menu.actions()]==[
            f"{hz} Гц" for hz in HORIZONTAL_HZ]
        assert [a.isEnabled() for a in w.spec_hscale_menu.actions()]==[
            False,False,False,True,True,True,True,True,True,True]
        assert w._spec_visible_max_hz==pytest.approx(3200)
        before=_f32_spectrum_sha(w)
        with pytest.raises(ValueError,match="Ширина"):
            w._select_original_hscale(6400)
        assert _f32_spectrum_sha(w)==before
        w.spec_hscale_menu.actions()[8].trigger() # 100 Hz
        qt_app.processEvents()
        assert w._spec_original_hscale_selected==100
        assert w._spec_source_h_view is None  # do not claim original 25600 viewport
        assert w.spec_hscale_button.text()=="100 Гц"
        assert w.spec_hscroll.maximum()==3100
        x=w.spec_plot.getViewBox().viewRange()[0]
        assert x[0]==pytest.approx(0,abs=.5)
        assert x[1]-x[0]==pytest.approx(100,abs=.5)
        w.spec_hscroll.setValue(3000)
        qt_app.processEvents()
        x=w.spec_plot.getViewBox().viewRange()[0]
        assert x[0]==pytest.approx(3000,abs=.5)
        assert x[1]==pytest.approx(3100,abs=.5)
        w.refresh_spec()
        qt_app.processEvents()
        assert w._spec_original_hscale_selected==100
        x=w.spec_plot.getViewBox().viewRange()[0]
        assert x[0]==pytest.approx(3000,abs=.5)
        assert x[1]-x[0]==pytest.approx(100,abs=.5)
        w.spec_mode.setCurrentIndex(2)
        qt_app.processEvents()
        assert w.spec_plot.getAxis("left").labelText=="мм/с"
        assert w._spec_original_hscale_selected==100
        assert _f32_spectrum_sha(w)!=before # different display mode, same input
        assert w.spec_hscroll.maximum()==3100
        assert w.spec_hscale_menu.actions()[0].isEnabled() is False
    finally:
        w.close()
        qt_app.processEvents()
