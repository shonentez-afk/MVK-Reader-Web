"""Stage111Z31A: same Qt Spectrum plot renders local original reference only.

Synthetic-only offscreen UI; actual operator x32dbg capture remains private.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture
from mvk_compatible.core.original_spectrum_x32dbg_reference import SOURCE
from mvk_compatible.core.tqgrapher_display_idr_candidate import (
    spectrum_display_contract,
)


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_qt_same_archive_plot_can_temporarily_show_original_operator_y(
        tmp_path, qt_app, mode):
    from PySide6.QtCore import QPointF, Qt
    from mvk_compatible.desktop.main_window import MainWindow

    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    calculated=win._full_spectrum
    original_widget=win.spec_plot
    old_mode=win.spec_mode.currentIndex()
    old_fft_index=win.spec_n.currentIndex()
    old_copy=win.spec_copy_button.isEnabled()
    old_title=win.title.text()
    old_title_tip=win.title.toolTip()
    old_adc_tip=win.adc.toolTip()
    assert "MVK" in old_title
    assert win.spec_plot.getPlotItem().getAxis("left").labelText=="дБ"
    
    manifest,config,p,y=create_reference_fixture(
        tmp_path/f"original_{mode}",mode=mode,fs=65536,n=1024)
    result=win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()

    assert win.spec_plot is original_widget
    assert win._full_spectrum["source"]==SOURCE
    assert win._full_spectrum["mode"]==mode
    assert win._full_spectrum["n_fft"]==1024
    assert win.spec_n.currentData()==1024
    assert win.spec_mode.currentIndex()==mode
    assert win.spec_avg.currentIndex()==(0 if mode==0 else 1)
    assert win._full_spectrum["original_capture_reference_only"]
    assert result["full_display_y_float32_bitwise_equal"]
    assert result["float32_bins"]==512
    assert result["original_qt_pixel_parity_verified"] is False
    assert not win.spec_copy_button.isEnabled()
    assert not win.spec_save_button.isEnabled()
    assert not win.spec_original_copy_compare.isEnabled()
    assert win.spec_reference_restore_button.isEnabled()
    assert not win.spec_mode.isEnabled()
    assert not win.spec_n.isEnabled()
    assert "ЭТАЛОН x32dbg" in win.title.text()
    assert "MVK" not in win.title.text()
    assert "АЦП ?" in win.title.text()
    assert "АЦП, исходное окно" in win.title.toolTip()
    assert "НЕ доказанный канал эталона" in win.adc.toolTip()
    from mvk_compatible.core.spectrum_summary_export_candidate import (
        spectrum_triplet_text)
    fields=spectrum_triplet_text(
        win._spectrum_summary,decimal_separator=',').split('\t')
    assert "СКЗ: " + fields[0] in win.spec_mean_primary.text()
    assert "Пик: " + fields[1] + " Гц" in win.spec_mean_primary.text()
    assert "Ампл.: " + fields[2] in win.spec_mean_primary.text()
    assert "Ориг. HEX: 3/3" in win.spec_mean_primary.text()
    assert "Физические единицы" in win.spec_mean_primary.toolTip()
    # The entire 4-line source summary fits the original fixed-height panel.
    from PySide6.QtCore import Qt
    text_box=win.spec_mean_primary.fontMetrics().boundingRect(
        0,0,win.spec_mean_primary.width(),1000,
        Qt.TextWordWrap,win.spec_mean_primary.text())
    assert text_box.height()<=win.spec_mean_primary.height()
    assert "ЭТАЛОН оригинального GetSpectrum" in win.spec_mean.text()
    assert "0 ULP" in win.spec_mean.text()
    assert "оригинал" in win.spec_hint.text().lower() or "x32dbg" in win.spec_hint.text().lower()
    assert win.spec_plot.getPlotItem().getAxis("bottom").labelText=="Гц"

    plot_items=win.spec_plot.listDataItems()
    assert len(plot_items)==1
    xp,yp=plot_items[0].getData()
    contract=spectrum_display_contract(1024,65536)
    count=contract["grapher_series_bins"]
    assert len(xp)==len(yp)==count
    np.testing.assert_array_equal(yp.astype("<f4").view("<u4"),y[:count].view("<u4"))
    assert xp[-1]==(count-1)*64
    assert contract["grapher_axis_end_frequency_hz"]==25600
    assert win._spec_visible_max_hz==25600

    # Cursor must continue to work on actual Float32 series, not a decimated
    # screenshot or a newly calculated FFT.
    rect=win.spec_plot.getViewBox().sceneBoundingRect()
    assert rect.width()>3
    class Click:
        def button(self): return Qt.LeftButton
        def scenePos(self):return QPointF(rect.left()+rect.width()*0.25,
                                           rect.center().y())
    win._spec_click(Click())
    assert win._spec_last_cursor is not None
    assert win._spec_last_cursor["full_bin_count"]==512
    assert win._spec_last_cursor["grapher_series_bins"]==count
    assert win._spec_last_cursor["fft_source"]==SOURCE

    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert win._full_spectrum is not None
    assert win._full_spectrum["source"]==calculated["source"]
    assert not win.spec_reference_restore_button.isEnabled()
    assert win.spec_mode.isEnabled()
    assert win.spec_n.isEnabled()
    assert win.spec_mode.currentIndex()==old_mode
    assert win.spec_n.currentIndex()==old_fft_index
    assert win.spec_copy_button.isEnabled()==old_copy
    assert win.title.text()==old_title
    assert win.title.toolTip()==old_title_tip
    assert win.adc.toolTip()==old_adc_tip
    assert win.spec_plot.getPlotItem().getAxis("left").labelText=="дБ"
    assert not win._full_spectrum.get("original_capture_reference_only",False)
    win.close()
    qt_app.processEvents()


def test_qt_invalid_original_reference_is_atomic_and_does_not_disable_copy(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    previous=win._full_spectrum
    assert win.spec_copy_button.isEnabled()
    manifest,config,p,y=create_reference_fixture(tmp_path/"tampered")
    config["display_y_sha256"]="0"*64
    manifest.write_text(json.dumps(config),encoding="utf-8")
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        win.show_original_spectrum_reference(manifest)
    assert win._full_spectrum is previous
    assert win._spectrum_reference is None
    assert not win.spec_reference_restore_button.isEnabled()
    assert win.spec_copy_button.isEnabled()
    win.close()
    qt_app.processEvents()


def test_qt_reference_rejected_during_live_without_opening_external_data(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    manifest,config,p,y=create_reference_fixture(tmp_path/"operator")
    win._live_active=True
    with pytest.raises(ValueError,match="во время записи Native"):
        win.show_original_spectrum_reference(manifest)
    win._live_active=False
    assert win._spectrum_reference is None
    win.close()
    qt_app.processEvents()


def test_qt_x32dbg_reference_standalone_without_any_archive(tmp_path,qt_app):
    """No dummy archive, no fictitious window/ADC provenance, no FFT needed."""
    from PySide6.QtCore import QPointF,Qt
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    assert win.session is None
    assert not win.tabs.isTabEnabled(2)
    assert win.tabs.currentIndex()==0
    initial_title=win.title.text()
    manifest,_,_,y=create_reference_fixture(tmp_path/"standalone",mode=0,
                                            n=1024,fs=65536)
    report=win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    assert report["float32_bins"]==512
    assert win.session is None
    assert win.tabs.isTabEnabled(2)
    assert win.tabs.currentIndex()==2
    assert win._spectrum_reference is not None
    assert "ЭТАЛОН x32dbg" in win.title.text()
    assert "Tag0" in win.title.text()
    assert "АЦП ?" in win.title.text()
    assert not win.spec_copy_button.isEnabled()
    assert win.spec_plot.getPlotItem().getAxis("bottom").labelText=="Гц"
    assert win._full_spectrum["source"]==SOURCE
    assert win.spec_hscale_button.text()=="25600 Гц"
    assert win._spec_vscroll_source_candidate[
        "operator_reference_f_range_word_used"] is True
    rect=win.spec_plot.getViewBox().sceneBoundingRect()
    assert rect.width()>3
    class Click:
        def button(self): return Qt.LeftButton
        def scenePos(self):return QPointF(
            rect.left()+rect.width()*0.3,rect.center().y())
    win._spec_click(Click())
    assert win._spec_last_cursor is not None
    assert win._spec_last_cursor["fft_source"]==SOURCE
    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert win.session is None
    assert win._full_spectrum is None
    assert win._spectrum_reference is None
    assert not win.tabs.isTabEnabled(2)
    assert win.tabs.currentIndex()==0
    assert win.title.text()==initial_title
    assert not win.spec_reference_restore_button.isEnabled()
    assert not win.spec_copy_button.isEnabled()
    assert win.spec_mean_primary.text()=="Сначала откройте измерение"
    assert len(win.spec_plot.listDataItems())==0
    # Opening a real archive AFTER standalone x32dbg preview also works.
    win.open_archive(fixture_zip(tmp_path))
    assert win.session is not None
    assert win._full_spectrum is not None
    assert win.tabs.isTabEnabled(2)
    assert win._full_spectrum["source"]!=SOURCE
    win.close()
    qt_app.processEvents()


def test_qt_reference_without_original_summary_words_labels_as_unverified(
        tmp_path,qt_app):
    """Power→Y exact does NOT by itself verify a missing original triplet."""
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    manifest,config,_,_=create_reference_fixture(
        tmp_path/"no_original_triplet",mode=0)
    config.pop("summary_hex")
    manifest.write_text(json.dumps(config),encoding="utf-8")
    report=win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    assert report["summary_3x_float32_equal_when_operator_words_given"] is None
    assert "Нет HEX: из Power" in win.spec_mean_primary.text()
    assert "Ориг. HEX: 3/3" not in win.spec_mean_primary.text()
    assert "Power/Y" in win.spec_mean.text() or "Y" in win.spec_mean.text()
    win.spec_reference_restore_button.click()
    win.close()
    qt_app.processEvents()



@pytest.mark.parametrize("archive_open", [False, True])
def test_z31d_separate_original_frange_and_measure_qt_viewbox_not_delphi(
        tmp_path, qt_app, archive_open):
    """Real Qt scene bounds and original FRange are distinct from TSXML/manual."""
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.qt_spectrum_viewport_observation import SOURCE as OBSERVED
    win = MainWindow()
    if archive_open:
        win.open_archive(fixture_zip(tmp_path))
    win.show()
    qt_app.processEvents()
    archive_guess = win.spec_f_range.value()
    assert archive_guess == 1.0
    assert "не открыт" in win.spec_x32dbg_f_range_label.text()

    manifest, _, _, _ = create_reference_fixture(
        tmp_path / f"original_z31d_{archive_open}", mode=0,
        n=1024, fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    label = win.spec_x32dbg_f_range_label.text()
    assert "ОРИГИНАЛ x32dbg" in label
    assert "0x43FF4853" in label
    assert "510,565" not in label  # JSON Float32 is displayed independent of locale.
    assert "510.565" in label
    assert "гипотезы архива" in label
    assert win.spec_manual_f_range_label.text() == (
        "FRange гипотезы архива · НЕ x32dbg")
    assert win.spec_f_range.value() == archive_guess
    assert "x32dbg JSON" in win.spec_graph_default_label.text()
    assert "FRange гипотезы архива и x87" not in (
        win.spec_graph_default_label.text())
    assert "FRange" in win.spec_source_gain_label.text()
    assert "x32dbg" not in win.spec_source_gain_label.text()  # R6.1 ZIP/TSXML source stays independent

    win.spec_inspector.show()
    qt_app.processEvents()
    d = win._collect_canvas_geometry_candidate()
    o = d["qt_measured_runtime_geometry"]
    assert o["source"] == OBSERVED
    assert o["research_dock_visible"] is True
    assert o["qt_viewport_size_logical"]["width"] == (
        win.spec_plot.viewport().width())
    assert o["qt_viewport_size_logical"]["height"] == (
        win.spec_plot.viewport().height())
    assert o["qt_device_pixel_ratio_observed"] == pytest.approx(
        win.spec_plot.viewport().devicePixelRatioF())
    assert o["qt_logical_dpi_observed"]["x"] == (
        win.spec_plot.viewport().logicalDpiX())
    assert o["qt_plot_size_logical"]["width"] > 0
    assert o["qt_plot_size_logical"]["height"] > 0
    assert o["qt_plot_size_nominal_device_pixels_if_uniform_dpr"]["width"] == pytest.approx(
        o["qt_plot_size_logical"]["width"] *
        o["qt_device_pixel_ratio_observed"])
    assert d["qt_scene_plot_rect_source"] == (
        "OBSERVED_QT_VIEWBOX_NOT_ORIGINAL_DELPHI")
    assert d["original_pixel_rectangle_verified"] is False
    assert o["original_tpaintbox_runtime_rectangle_verified"] is False
    assert o["qt_to_delphi_pixel_parity_verified"] is False
    assert d["qt_to_tpaintbox_bridge_candidate"][
        "original_delphi_pixel_parity_verified"] is False

    win.spec_inspector.hide()
    qt_app.processEvents()
    d_after = win._collect_canvas_geometry_candidate()
    assert d_after["qt_measured_runtime_geometry"]["research_dock_visible"] is False
    assert d_after["qt_measured_runtime_geometry"]["qt_plot_size_logical"]["width"] > 0
    # Do not assert dock-free and dock-open pixels MUST coincide with some
    # original Win32 TPaintBox: that remains unmeasured at runtime.

    win.restore_archive_spectrum_after_reference()
    qt_app.processEvents()
    assert "не открыт" in win.spec_x32dbg_f_range_label.text()
    assert win.spec_f_range.value() == archive_guess
    assert win._spectrum_reference is None
    win.close()
    qt_app.processEvents()
