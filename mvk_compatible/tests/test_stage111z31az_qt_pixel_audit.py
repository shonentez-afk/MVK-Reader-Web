"""Stage111Z31AZ Windows Qt PNG export/readback + operator parity CLI QA.

No PRIVATE original image, BIN, x32dbg, network or auto-screenshots.
"""
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

pytest.importorskip("PySide6")
from .test_desktop_qt import qt_app
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture
from mvk_compatible.desktop.source_pixel_audit_io import (
    save_source_graph_pixel_audit,read_png_rgba)
from mvk_compatible.core.spectrum_graph_pixel_audit import (
    compare_local_graph_pixel_audit)


def test_export_local_current_gdi_source_bitmap_and_readback(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    assert not win.spec_pixel_audit_export_button.isEnabled()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/"original_data",mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    for c in (win.spec_source_grid_checkbox,
              win.spec_source_raster_checkbox,
              win.spec_source_series_checkbox):
        c.click()
        qt_app.processEvents()
    assert win.spec_pixel_audit_export_button.isEnabled()
    model=win._spec_source_grid_model
    assert model['combined_preview_active']
    base=win._spec_source_raster_data.copy()
    fft_before=np.asarray(
        win._full_spectrum['amplitude'],dtype='<f4').view('<u4').copy()
    xr,yr=win.spec_plot.getViewBox().viewRange()
    exported=save_source_graph_pixel_audit(
        tmp_path,
        bitmap=base,canvas=model['combined_canvas'],
        spectrum=win._full_spectrum,
        view_x=tuple(xr),view_y=tuple(yr),
        qt_device_pixel_ratio=float(
            win.spec_plot.viewport().devicePixelRatioF()),
        textout_diagnostics=model.get('spectrum_textout_native_metrics'))
    assert exported.parent==tmp_path
    png=exported/"candidate_source_bitmap.png"
    src=exported/"candidate_manifest.json"
    assert png.is_file() and src.is_file()
    actual=read_png_rgba(png)
    np.testing.assert_array_equal(actual,base)
    j=json.loads(src.read_text(encoding="utf-8"))
    assert j["source_pixel_rect_ltrb"]==[
        model['combined_canvas'][k] for k in (
            'pixel_left','pixel_top','pixel_right','pixel_bottom')]
    assert j["candidate_png_filename"]=="candidate_source_bitmap.png"
    assert j["original_png_is_not_present"] is True
    assert not j["original_runtime_font_and_dpi_verified"]
    # No private original reference path or Power/Y binary content.
    assert str(manifest) not in src.read_text(encoding="utf-8")
    assert 'amplitude' not in j
    compare=compare_local_graph_pixel_audit(base,actual,j)
    assert compare["exact_rgb_equal_without_alignment"]
    assert not compare["complete_mvkview_pixel_parity_verified"]
    np.testing.assert_array_equal(
        np.asarray(win._full_spectrum['amplitude'],
                   dtype='<f4').view('<u4'),fft_before)
    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert not win.spec_pixel_audit_export_button.isEnabled()
    win.close()
    qt_app.processEvents()


def test_pixel_audit_cli_reads_local_png_and_never_attests_origin(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from tools.research.compare_stage111z31az_spectrum_pixel_audit import run
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/"case",mode=3,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    for c in (win.spec_source_grid_checkbox,
              win.spec_source_raster_checkbox,
              win.spec_source_series_checkbox):
        c.click()
        qt_app.processEvents()
    model=win._spec_source_grid_model
    xr,yr=win.spec_plot.getViewBox().viewRange()
    folder=save_source_graph_pixel_audit(
        tmp_path,bitmap=win._spec_source_raster_data,
        canvas=model['combined_canvas'],spectrum=win._full_spectrum,
        view_x=xr,view_y=yr,
        qt_device_pixel_ratio=win.spec_plot.viewport().devicePixelRatioF(),
        textout_diagnostics=model.get('spectrum_textout_native_metrics'))
    original=tmp_path/"operator_supplied_synthetic_original.png"
    shutil.copyfile(folder/"candidate_source_bitmap.png",original)
    report=tmp_path/"local_report.json"
    status=run([
        "--original",str(original),
        "--candidate",str(folder/"candidate_source_bitmap.png"),
        "--manifest",str(folder/"candidate_manifest.json"),
        "--report",str(report),
        "--operator-same-window",
        "--shift-radius","0"])
    assert status==0
    summary=json.loads(report.read_text(encoding="utf-8"))
    assert summary["operator_declared_same_measurement_and_window"]
    assert not summary["complete_mvkview_pixel_parity_verified"]
    assert summary["exact_rgb_equal_without_alignment"]
    assert str(original) not in str(summary)
    assert str(folder) not in str(summary)
    win.close()
    qt_app.processEvents()
