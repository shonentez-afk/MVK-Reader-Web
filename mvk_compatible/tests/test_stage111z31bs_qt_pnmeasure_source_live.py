"""Stage111Z31BS integrated original pnMeasure DFM + actual Qt/Core actions.

Synthetic Native R6.1 ZIP and synthetic LivePreview only; ZERO device I/O.
"""
import csv
from datetime import datetime,timezone
from hashlib import sha256

import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import (QWidget,QPushButton,QLabel,QFileDialog)
from PySide6.QtCore import Qt

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested)
from ..core.native_r6_live_preview import LivePreview,PreviewADC
from ..core.original_measure_controls import DFM_BUTTONS


def _preview(session="SYNTHETIC-ONLY-LIVE",rate=65536):
    samples=np.sin(2*np.pi*120*np.arange(4096)/rate).astype("<f4")
    adc=PreviewADC(
        number=1,rate_hz=rate,first_index=0,next_index=4096,
        samples=samples,sha256=sha256(samples.tobytes()).hexdigest())
    return LivePreview(
        session_id=session,updated_utc=datetime(2026,11,12,tzinfo=timezone.utc),
        raw_bytes=9000,frames_decoded=800,channels={1:adc})


def test_original_global_toolbar_source_geometry_and_live_preview_freeze(
        qt_app,monkeypatch):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        panel=win.original_measure_controls
        assert panel is win.original_shell.measure_controls
        assert panel.panel.objectName()=="pnMeasure"
        assert panel.controls.objectName()=="pnMeasureControls"
        assert panel.panel.height()==53
        assert panel.controls.width()==843
        assert not panel.panel.isVisible()  # DFM Visible=False, before source
        assert panel.status.objectName()=="lbStatus"
        assert panel.indicator.objectName()=="imStatusGood"
        for name,x,y,w,h,tag,order in DFM_BUTTONS:
            button=panel.controls.findChild(QPushButton,name)
            assert button is not None
            rect=button.geometry()
            assert (rect.x(),rect.y(),rect.width(),rect.height())==(x,y,w,h)
            assert button.property("SourceDFMTag")==tag
            assert button.property("SourceDFMTabOrder")==order
        assert panel.rate_menu.objectName()=="popSampleRate"
        assert len(panel.rate_menu.actions())>=2
        assert all(not action.isEnabled() for action in panel.rate_menu.actions())
        assert win._source_live_view_frozen is False

        win._begin_live_capture()  # NO actual socket, QProcess or Native EXE
        qt_app.processEvents()
        assert win._live_active
        assert panel.panel.isVisible()
        assert panel.state.mode=="live"
        assert panel.freeze.isEnabled()
        assert not panel.buttons["bWriteAdc"].isEnabled()
        assert not panel.buttons["bWriteValues"].isEnabled()
        assert not panel.buttons["bWriteTable"].isEnabled()
        assert not panel.state.report()["device_commands_sent"]
        observed=[]
        monkeypatch.setattr(win,"_render_live_wave",
                            lambda:observed.append("wave"))
        monkeypatch.setattr(win,"_render_live_spectrum",
                            lambda:observed.append("spectrum"))
        panel.freeze.click()
        assert win._source_live_view_frozen
        assert panel.state.frozen
        assert "Возобновить" in panel.freeze.text()
        win._receive_live_preview(_preview())
        assert observed==[]  # live decoder continues; Qt view frozen
        assert panel.state.observed_sample_rate_hz==65536
        assert "65536" in panel.rate.text()
        assert "пауза экрана" in panel.status.text()
        capture_synthetic_ui_if_requested(
            win,qt_app,"22_bs_original_pnmeasure_live_preview_freeze")
        panel.freeze.click()
        assert observed==["wave","spectrum"]
        assert not win._source_live_view_frozen
        assert not panel.state.frozen
        win._receive_live_preview(_preview(rate=32000))
        assert observed[-2:]==["wave","spectrum"]
        assert len(observed)==4
        assert panel.state.observed_sample_rate_hz==32000
        assert "32000" in panel.rate.text()
        win._invalidate_live_preview("synthetic stale status")
        assert panel.state.observed_sample_rate_hz is None
        assert win._live_preview is None
        win._end_live_capture(False)
        qt_app.processEvents()
        assert not win._live_active
        assert panel.state.mode=="idle"
        assert not panel.panel.isVisible()
        assert not win._source_live_view_frozen
    finally:
        win.close()
        qt_app.processEvents()


def test_source_toolbar_offline_table_values_and_original_file_selection(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    source=fixture_zip(tmp_path,sample_count=4096)
    old_sha=sha256(source.read_bytes()).hexdigest()
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(source)
        qt_app.processEvents()
        panel=win.original_measure_controls
        assert panel.panel.isVisible()
        assert panel.state.mode=="offline"
        assert not panel.freeze.isEnabled()
        assert panel.buttons["bWriteTable"].isEnabled()
        assert panel.buttons["bWriteAdc"].isEnabled()
        assert panel.buttons["bWriteValues"].isEnabled()
        assert panel.state.observed_sample_rate_hz is not None
        assert all(not x.isEnabled() for x in panel.rate_menu.actions())
        assert "ОФЛАЙН" in panel.status.text()
        assert panel.state.report()["original_thread_write_adc_flag_set"] is False
        capture_synthetic_ui_if_requested(
            win,qt_app,"23_bs_original_pnmeasure_native_zip_offline")

        # bWriteTableClick source writes TABLE-*; our version writes a
        # real independent VALUES snapshot of all eight checked banks.
        all_table=tmp_path/"TABLE-2026-11-12--15-35-01.csv"
        monkeypatch.setattr(
            QFileDialog,"getSaveFileName",
            staticmethod(lambda *a,**k:(str(all_table),"CSV")))
        panel.buttons["bWriteTable"].click()
        assert all_table.exists()
        with all_table.open(encoding="utf-8-sig",newline="") as fp:
            rows=list(csv.reader(fp,delimiter=";"))
        assert len(rows)==1+8*(24+43)
        assert "536" in panel.status.text()
        assert sha256(source.read_bytes()).hexdigest()==old_sha

        # This selected export consumes the REAL check states in PageFile,
        # not a parallel shadow model in the global toolbar.
        page=win.original_shell
        for adc in range(1,8):
            page.file_channels.item(adc).setCheckState(Qt.Unchecked)
        for spec in range(43):
            page.file_spec.item(spec).setCheckState(
                Qt.Unchecked if spec!=5 else Qt.Checked)
        for value in range(67):
            page.file_values.item(value).setCheckState(
                Qt.Checked if value in (0,24) else Qt.Unchecked)
        assert len(page.file_record_selection.checked("channels"))==1
        assert len(page.file_record_selection.checked("spec"))==1
        assert len(page.file_record_selection.checked("values"))==2
        selected=tmp_path/"TABLE-selected-only.csv"
        monkeypatch.setattr(
            QFileDialog,"getSaveFileName",
            staticmethod(lambda *a,**k:(str(selected),"CSV")))
        panel.buttons["bWriteValues"].click()
        with selected.open(encoding="utf-8-sig",newline="") as fp:
            rows=list(csv.reader(fp,delimiter=";"))
        assert len(rows)==4  # one VALUE, one BAND, one SPEC
        assert all(row[0]=="1" for row in rows[1:])
        assert sha256(source.read_bytes()).hexdigest()==old_sha

        out=tmp_path/"local_adc_export"
        out.mkdir()
        monkeypatch.setattr(
            QFileDialog,"getExistingDirectory",
            staticmethod(lambda *a,**k:str(out)))
        panel.buttons["bWriteAdc"].click()
        assert len(list(out.iterdir()))==1
        assert (next(out.iterdir())/"PAGEFILE_SELECTION.json").exists()
        assert sha256(source.read_bytes()).hexdigest()==old_sha
        assert not panel.state.report()["original_thread_write_adc_flag_set"]
        assert not panel.state.report()["native_recorder_filter_or_sample_rate_changed"]
    finally:
        win.close()
        qt_app.processEvents()


def test_source_toolbar_direct_single_only_has_real_adc_local_export(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    src,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(src)
        qt_app.processEvents()
        panel=win.original_measure_controls
        assert panel.state.mode=="offline"
        assert panel.panel.isVisible()
        assert not panel.buttons["bWriteTable"].isEnabled()
        assert not panel.buttons["bWriteValues"].isEnabled()
        assert panel.buttons["bWriteAdc"].isEnabled()
        assert not panel.freeze.isEnabled()
        assert "DSP нет" in panel.status.text()
        assert panel.rate_menu.actions()[0].isEnabled() is False
    finally:
        win.close()
        qt_app.processEvents()
