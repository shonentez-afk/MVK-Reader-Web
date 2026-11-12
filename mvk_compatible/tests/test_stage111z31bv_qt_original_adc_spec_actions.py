"""BV integration: original PageAdc full FIR cursor and PageSpectrum Copy/Save.

Synthetic Native ZIP + fake FIR profile only. 150% Windows Qt E2E,
with all 7 source pages and 3 reconstructed original Delphi form types.
No physical device, no telemetry or original runtime process.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from pathlib import Path
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF,Qt
from PySide6.QtWidgets import QApplication,QPushButton

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested)
from ..core.original_adc_spectrum_actions import (
    OriginalEnvelopeCursor,OriginalSpectrumAction,
    SPEC_CSV_HEADER,SPECTRUM_COPY_SOURCE,SPECTRUM_SAVE_SOURCE,
)


def test_original_spectrum_copy_and_daily_save_source_3_values_live_qt_controls(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    source=fixture_zip(tmp_path,sample_count=4096)
    original_sha=sha256(source.read_bytes()).hexdigest()
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(source)
        w.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        assert w.spec_copy_button.objectName()=="bSpecCopyValue"
        assert w.spec_save_button.objectName()=="bSpecSaveValue"
        assert w.spec_copy_button.isEnabled()
        assert w.spec_save_button.isEnabled()
        assert w._full_spectrum is not None
        flow,action=w._current_original_spectrum_action()
        assert action.adc==w._ch()
        assert action.receipt()["original_clipboard_handler"]==SPECTRUM_COPY_SOURCE
        assert action.receipt()["original_csv_handler"]==SPECTRUM_SAVE_SOURCE
        assert action.n_fft==int(w.spec_n.currentText())
        capture_synthetic_ui_if_requested(
            w,qt_app,"31_bv_page_spectrum_original_three_values")

        QApplication.clipboard().setText("before-copy-untrusted")
        w.spec_copy_button.click()
        qt_app.processEvents()
        copied=QApplication.clipboard().text()
        assert copied==action.clipboard_text(decimal_separator=",")
        assert len(copied.split("\t"))==3
        assert "\n" not in copied
        assert "GetSpectrum" in w.statusBar().currentMessage()

        # Original bSpecSaveValue uses the chosen edLibraryPath and
        # auto-appends to SPEC-FREQ-yyyy-mm-dd.csv. Never need dialog
        # for an explicitly configured original local folder.
        w.original_start_controller.set_library(tmp_path)
        date_name="SPEC-FREQ-"+date.today().strftime("%Y-%m-%d")+".csv"
        daily=tmp_path/date_name
        assert not daily.exists()
        w.spec_save_button.click()
        qt_app.processEvents()
        assert daily.exists()
        first=daily.read_bytes()
        assert first.startswith(
            ("sep=|\r\n"+SPEC_CSV_HEADER+"\r\n").encode("utf-8"))
        assert len(first.splitlines())==3
        assert len(first.splitlines()[2].split(b"|"))==3
        w.spec_save_button.click()
        qt_app.processEvents()
        second=daily.read_bytes()
        assert len(second.splitlines())==4
        assert second.startswith(first)
        assert second.count(b"sep=|")==1
        assert sha256(source.read_bytes()).hexdigest()==original_sha

        # Changing ADC changes BOTH Core source and selected original
        # tcSpectrum Qt tab, not just the text of the save button.
        w.adc.setCurrentIndex(1)
        qt_app.processEvents()
        assert w.original_root_tabs.currentIndex()==4
        flow2,action2=w._current_original_spectrum_action()
        assert action2.adc==2
        assert action2.source_bin_sha256!=action.source_bin_sha256
        assert action2.receipt()["source_tick_index"]==action.receipt()["source_tick_index"]
        with pytest.raises(ValueError,match="stale"):
            action.validate_flow(flow2)
        w.spec_save_button.click()
        assert len(daily.read_bytes().splitlines())==5
        assert sha256(source.read_bytes()).hexdigest()==original_sha
    finally:
        w.close()
        qt_app.processEvents()


def test_original_adc_filtered_getsignal_cursor_uses_full_fir_not_lod(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    source=fixture_zip(tmp_path,sample_count=4096)
    sha=sha256(source.read_bytes()).hexdigest()
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(source)
        w.original_root_tabs.setCurrentIndex(3)
        w.set_envelope_profile(fake_profile(i=1.,q=.4))
        w.wave_start.setValue(.04)
        w.wave_seconds.setValue(.02)
        w.wave_envelope_code.setCurrentIndex(20)
        w.refresh_wave()
        qt_app.processEvents()
        cursor=w._source_envelope_cursor
        assert isinstance(cursor,OriginalEnvelopeCursor)
        assert cursor.channel==1 and cursor.code==20
        assert w.wave_line is not None
        assert len(cursor.full_values)>30
        assert w._source_wave_readout is None  # downsampled FIR != raw GetSignal
        box=w.wave_plot.getViewBox()
        view=box.viewRange()
        # Move onto real, internal filtered sample, not a LOD/mean line.
        mid=min(len(cursor.full_values)//2,128)
        x=mid/cursor.output_hz
        y=(view[1][0]+view[1][1])*0.5
        scene=box.mapViewToScene(QPointF(x,y))
        w._wave_at_scene_pos(scene,force=True)
        qt_app.processEvents()
        expected=cursor.pick(x)
        assert expected["output_index"]==mid
        assert f"FIR[{mid}]" in w.wave_hint.text()
        assert w.wave_line.isVisible()
        assert "время относительно буфера" in w.wave_hint.text()
        assert "Win32 исходное время" in w.wave_hint.text()
        capture_synthetic_ui_if_requested(
            w,qt_app,"32_bv_page_adc_full_filtered_source_cursor")

        # Exiting envelope/closing source must never leave stale filtered
        # samples bound to new ADC/BIN or the unfiltered GetSignal plot.
        w.wave_envelope_code.setCurrentIndex(0)
        w.refresh_wave()
        assert w._source_envelope_cursor is None
        w._close_session()
        assert w._source_envelope_cursor is None
        assert w.session is None
        assert sha256(source.read_bytes()).hexdigest()==sha
    finally:
        w.close()
        qt_app.processEvents()


def test_one_source_original_all_seven_pages_three_form_types_safe(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    from ..desktop.original_windowman_form import OriginalWindowManForm
    from ..desktop.original_value_edit_dialog import OriginalValueEditDialog
    from ..core.original_ui_form_contract import ORIGINAL_ROOT_PAGES
    path=fixture_zip(tmp_path,sample_count=4096)
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(path)
        assert w.original_root_tabs.count()==7
        assert tuple(page.object_name for page in ORIGINAL_ROOT_PAGES)==(
            "PageStart","PageConfig","PageStatus","PageAdc",
            "PageSpectrum","PageFile","PageCalib")
        assert w.original_root_stack.objectName()=="OriginalPageBodies"
        for index,source_page in enumerate(ORIGINAL_ROOT_PAGES):
            w.original_root_tabs.setCurrentIndex(index)
            qt_app.processEvents()
            assert w.original_root_tabs.currentIndex()==index
            assert w.original_root_tabs.tabData(index)==source_page.object_name
            assert w.session is not None
            assert w.original_shell.view_state is not None
            assert w.original_shell.status_tabs.count()==15
        assert w.original_root_stack.currentWidget() is w.original_calib_panel.page
        assert w.original_calib_panel.steps.count()==49
        assert w.original_shell.status_grid_stack.count()==4
        assert w.original_start_controller.host.objectName()=="SourcePageStartLauncher"

        # Three original forms are objects with actual source DFM controls,
        # not merely plans/dummy route names. Never open operator hardware.
        edit=OriginalValueEditDialog(
            prompt="Synthetic local register",value="1",read_only=True,parent=w)
        messages=OriginalWindowManForm(parent=w)
        assert edit.objectName()=="mvkeditform"
        assert edit.edVal.isReadOnly()
        assert not edit.bOk.isEnabled()
        assert messages.objectName()=="WindowManForm"
        assert messages.property("deviceCommandAllowed") is None
        assert not messages.img.isEnabled()
        assert w.windowTitle()=="ТПО МВК"
        edit.close()
        messages.close()
    finally:
        w.close()
        qt_app.processEvents()
