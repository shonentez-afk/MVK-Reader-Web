"""Stage111Z31BO: real current Qt PageSpectrum screenshot pixel QA action.

Only synthetic SHA-verified Power/Y and generated PNGs. Original Windows
process, private data, hardware and outbound requests are NEVER opened.
"""
from __future__ import annotations

import hashlib
import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog, QScrollArea, QMessageBox

from .test_desktop_qt import qt_app
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested,
)


def _save_rgba(path, frame):
    h,w=frame.shape[:2]
    packed=np.ascontiguousarray(frame,dtype=np.uint8)
    image=QImage(
        packed.tobytes(),w,h,w*4,QImage.Format_RGBA8888).copy()
    assert image.save(str(path),"PNG")
    return path


def _source_composite(win,qt_app):
    win.spec_inspector.show()
    win.original_root_tabs.setCurrentIndex(4)
    qt_app.processEvents()
    for toggle in (
        win.spec_source_grid_checkbox,
        win.spec_source_raster_checkbox,
        win.spec_source_series_checkbox):
        if not toggle.isChecked():
            toggle.click()
            qt_app.processEvents()
    model=win._spec_source_grid_model
    assert model is not None and model["combined_preview_active"]
    assert win._spec_source_raster_data is not None
    assert win.spec_original_pixel_compare_button.isEnabled()
    return win._spec_source_raster_data.copy()


def _forbid_modal(monkeypatch):
    def unexpected(*a,**kw):
        raise AssertionError("No modal warning while pixel QA")
    for name in ("critical","warning","information","question"):
        monkeypatch.setattr(QMessageBox,name,staticmethod(unexpected))


@pytest.mark.parametrize("mode",[0,3])
def test_compare_exact_current_original_bitmap_from_research_dock_and_invalidate(
        qt_app,tmp_path,monkeypatch,mode):
    from ..desktop.main_window import MainWindow
    _forbid_modal(monkeypatch)
    win=MainWindow()
    win.show()
    try:
        manifest,_,_,_=create_reference_fixture(
            tmp_path/f"ref_{mode}",mode=mode,n=1024,fs=65536)
        win.show_original_spectrum_reference(manifest)
        qt_app.processEvents()
        base=_source_composite(win,qt_app)
        original=_save_rgba(tmp_path/f"same_window_{mode}.png",base)
        sha=hashlib.sha256(np.asarray(
            win._full_spectrum["amplitude"],dtype="<f4").tobytes()).hexdigest()
        assert not win.spec_original_pixel_operator_claim.isChecked()
        assert win.compare_current_original_graph_pixels() is None
        assert "ОТКАЗ" in win.spec_original_pixel_status.text()
        win.spec_original_pixel_operator_claim.setChecked(True)
        monkeypatch.setattr(QFileDialog,"getOpenFileName",
            staticmethod(lambda *a,**kw:(str(original),"PNG")))
        report=win.compare_current_original_graph_pixels()
        assert report["exact_rgb_equal_without_alignment"]
        assert report["full_canvas"]["pixels_any_rgb_channel_gt_1"]==0
        assert report["original_full_y_sha256"]==sha
        assert not report["independent_original_capture_authentication"]
        assert not report["original_gdi_canvas_dpi_parity_verified"]
        assert win._visible_original_pixel_report is report
        assert "все пиксели равны: ДА" in win.spec_original_pixel_status.text()
        assert "не удостоверен" in win.spec_original_pixel_status.text()
        assert not win.spec_original_pixel_diff_preview.pixmap().isNull()
        if mode==0:
            scroll=win.spec_inspector.findChild(
                QScrollArea,"spectrumResearchScroll")
            assert scroll is not None
            scroll.ensureWidgetVisible(win.spec_original_pixel_status)
            qt_app.processEvents()
            capture_synthetic_ui_if_requested(
                win,qt_app,"17_bo_current_original_screenshot_exact")
        assert hashlib.sha256(np.asarray(
            win._full_spectrum["amplitude"],dtype="<f4").tobytes()).hexdigest()==sha

        # The returned PNG score is valid for ONLY this view. A native
        # X pan rerenders the bitmap and removes stale diagnosis.
        vb=win.spec_plot.getViewBox()
        xr=vb.viewRange()[0]
        vb.setXRange(xr[0]+1.,xr[1]+1.,padding=0)
        qt_app.processEvents()
        win._sync_source_tqgrapher_grid_candidate()
        assert win._visible_original_pixel_report is None
        assert "ещё не сравнивался" in win.spec_original_pixel_status.text()
        assert win.spec_original_pixel_diff_preview.pixmap() is None
        win.spec_reference_restore_button.click()
        qt_app.processEvents()
        assert not win.spec_original_pixel_compare_button.isEnabled()
        assert win._visible_original_pixel_report is None
    finally:
        win.close()
        qt_app.processEvents()


def test_real_qt_pixel_mismatch_in_plot_and_axes_and_wrong_image_rejection(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    _forbid_modal(monkeypatch)
    win=MainWindow()
    win.show()
    try:
        manifest,_,_,_=create_reference_fixture(
            tmp_path/"ref",mode=1,n=1024,fs=65536)
        win.show_original_spectrum_reference(manifest)
        qt_app.processEvents()
        base=_source_composite(win,qt_app)
        frame=base.copy()
        canvas=win._spec_source_grid_model["combined_canvas"]
        inside=(canvas["pixel_top"]+10,canvas["pixel_left"]+10)
        outside=(0,0)
        for (y,x) in (inside,outside):
            frame[y,x,0]=np.uint8(255-int(frame[y,x,0]))
        original=_save_rgba(tmp_path/"mismatch.png",frame)
        sha=hashlib.sha256(base.tobytes()).hexdigest()
        win.spec_original_pixel_operator_claim.setChecked(True)
        monkeypatch.setattr(QFileDialog,"getOpenFileName",
            staticmethod(lambda *a,**kw:(str(original),"PNG")))
        report=win.compare_current_original_graph_pixels()
        assert report is not None
        assert not report["exact_rgb_equal_without_alignment"]
        assert report["plot_pixels"]["pixels_any_rgb_channel_gt_1"]>=1
        assert report["axes_text_and_margins"]["pixels_any_rgb_channel_gt_1"]>=1
        assert "все пиксели равны: НЕТ" in win.spec_original_pixel_status.text()
        assert hashlib.sha256(
            win._spec_source_raster_data.tobytes()).hexdigest()==sha
        # Same-name local PNG with wrong pixel dimensions may not be
        # auto-scaled, cropped or given a misleading PASS.
        wrong=_save_rgba(tmp_path/"wrong.png",frame[:-1])
        monkeypatch.setattr(QFileDialog,"getOpenFileName",
            staticmethod(lambda *a,**kw:(str(wrong),"PNG")))
        assert win.compare_current_original_graph_pixels() is None
        assert win._visible_original_pixel_report is None
        assert "ОТКАЗ" in win.spec_original_pixel_status.text()
    finally:
        win.close()
        qt_app.processEvents()
