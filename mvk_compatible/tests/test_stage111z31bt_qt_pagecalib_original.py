"""BT original Delphi PageCalib UI+Core end-to-end synthetic Win DPI150.

Original 49 source checkboxes + 11x77 source grid + two result modes +
source 155x41 Save/Clear/Generate buttons + linked PageConfig candidate.
No connected COM generator/device; private operator originals never uploaded.
"""
from dataclasses import replace
from hashlib import sha256
import json
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,QLabel,QListWidget,QPlainTextEdit,QPushButton,
    QTabWidget,QTableWidget,QWidget,QComboBox,
)
from .test_desktop_qt import qt_app
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested)
from ..core.original_calibration_workbench import (
    GRID_COLS,GRID_ROWS,STEP_GROUPS,DFM_SAVE_BUTTONS,DFM_UNIT_BUTTONS,
    OriginalCalibrationWorkspace,
)


def _synthetic_sources(tmp_path):
    raw=OriginalCalibrationWorkspace.initial()
    rows=[list(r) for r in raw.grid]
    rows[8][2]="1.0"
    for adc in range(8):
        rows[8][3+adc]="1.0"
    workspace=replace(raw,grid=tuple(tuple(r) for r in rows))
    source=tmp_path/"CALIB-operator-synthetic.csv"
    workspace.export_csv(source)
    config=tmp_path/"original-calib-gains.cfg"
    config.write_text(
        "; synthetic source only (NOT instrument calibration)\n"
        "+0x0000\n"+
        "".join(f"0x{0x20+i*2:04X} f:{1+i*.1:.2f}\n"
                for i in range(8)),encoding="utf-8")
    return source,config


def test_original_pagecalib_source_geometry_modes_group_toggle_and_local_files(
        tmp_path,qt_app,monkeypatch):
    from ..desktop.main_window import MainWindow
    path,config=_synthetic_sources(tmp_path)
    path_sha=sha256(path.read_bytes()).hexdigest()
    config_sha=sha256(config.read_bytes()).hexdigest()
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.original_root_tabs.setCurrentIndex(6)
        qt_app.processEvents()
        panel=w.original_calib_panel
        page=panel.page
        assert w.original_root_stack.currentWidget() is page
        assert page.objectName()=="PageCalib"
        assert page.findChild(QWidget,"splCalib") is not None
        assert panel.param_tabs.count()==1
        assert panel.tabs.count()==2
        assert page.findChild(QWidget,"pnCalibTools").height()==63
        assert page.findChild(QWidget,"pnCalibSelect").height()==51
        toolbar=page.findChild(QWidget,"pnCalibResult")
        assert toolbar.geometry().getRect()==(4,42,607,63)
        assert page.findChild(QPushButton,"bCalibStart").geometry().getRect()==(
            6,8,107,41)
        assert not page.findChild(QPushButton,"bCalibStart").isEnabled()
        assert not page.findChild(QComboBox,"cbCalibGenPort").isEnabled()
        assert len(STEP_GROUPS)==5
        assert panel.steps.count()==49
        assert all(panel.steps.item(i).checkState()==Qt.Checked
                   for i in range(49))
        for short,tag,x,y,width,height in DFM_UNIT_BUTTONS:
            group=page.findChild(QPushButton,"bCalib"+short)
            assert group.property("SourceDFMTag")==tag
            assert group.property("SourceDFMTabOrder")==tag-1
            assert group.geometry().getRect()==(x,y,width,height)
        for name,x,y,width,height in DFM_SAVE_BUTTONS:
            assert page.findChild(QPushButton,name).geometry().getRect()==(
                x,y,width,height)
        assert panel.grid.rowCount()==GRID_ROWS
        assert panel.grid.columnCount()==GRID_COLS
        assert panel.grid.objectName()=="tabCalibResult"
        assert panel.log.objectName()=="logCalibResult"
        assert panel.log.isReadOnly()
        assert not panel.buttons["bCalibGenerate"].isEnabled()
        assert not panel.buttons["localCalibSaveProposal"].isEnabled()
        panel.tabs.setCurrentIndex(0)
        capture_synthetic_ui_if_requested(
            w,qt_app,"24_bt_source_calib_original_log_and_49_steps")
        panel.tabs.setCurrentIndex(1)

        # DFM original 5 group buttons perform actual source boolean
        # propagation, rather than enabling a fake generator.
        panel.groups[1].click()
        assert panel.workspace.checked_steps==49-11
        assert all(panel.steps.item(i).checkState()==Qt.Unchecked
                   for i in range(11))
        assert all(panel.steps.item(i).checkState()==Qt.Checked
                   for i in range(11,49))
        panel.groups[1].click()
        assert panel.workspace.checked_steps==49

        w.original_config_panel.load_local_file(config)
        panel.load_csv(path)
        qt_app.processEvents()
        assert panel.workspace.source_grid_loaded
        assert panel.tabs.currentIndex()==1
        assert panel.grid.item(8,2).text()=="1.0"
        assert panel.grid.item(8,3).text()=="1.0"
        assert panel.grid.item(8,10).text()=="1.0"
        assert panel.buttons["bCalibGenerate"].isEnabled()
        assert panel.workspace.source_sha256==path_sha
        capture_synthetic_ui_if_requested(
            w,qt_app,"25_bt_original_calib_77_by_11_imported")

        original_log=tmp_path/"calib-local.log"
        original_log.write_text(
            "Синтетический журнал; TMVKCalibThread не запускался\n"
            "Только проверка интерфейса\n",encoding="utf-8")
        panel.load_log(original_log)
        assert "TMVKCalibThread" in panel.log.toPlainText()
        assert panel.tabs.currentIndex()==0
        panel.tabs.setCurrentIndex(1)
        candidate=panel.make_proposal()
        assert candidate is not None and len(candidate.entries)==8
        assert panel.preview.rowCount()==8
        assert panel.preview.isVisible()
        assert panel.buttons["localCalibSaveProposal"].isEnabled()
        assert "8 локальных" in panel.hint.text()
        assert "1.001001" in panel.preview.item(0,2).text()
        assert panel.preview.item(0,3).text().startswith("0.999")
        capture_synthetic_ui_if_requested(
            w,qt_app,"26_bt_source_calib_eight_gain_candidates")

        # bCalibSaveClick source: sep=| followed by all 11x77 cells.
        out=tmp_path/"CALIB-local-export.csv"
        monkeypatch.setattr(
            QFileDialog,"getSaveFileName",
            staticmethod(lambda *a,**kw:(str(out),"CSV")))
        panel.buttons["bCalibSave"].click()
        assert out.exists()
        assert out.read_text(encoding="utf-8-sig").startswith("sep=|\n")
        reopened=OriginalCalibrationWorkspace.load_csv(out)
        assert reopened.grid==panel.workspace.grid
        assert sha256(path.read_bytes()).hexdigest()==path_sha

        result_path=tmp_path/"CALIB-review-only.json"
        result=panel.save_proposal(result_path)
        assert result["adc_gain_candidates"]==8
        payload=json.loads(result_path.read_text(encoding="utf-8"))
        assert len(payload["entries"])==8
        assert payload["device_commands_sent"] is False
        assert payload["uploadable_original_calib_txt_created"] is False
        assert sha256(config.read_bytes()).hexdigest()==config_sha

        panel.buttons["bCalibClear"].click()
        assert not panel.workspace.source_grid_loaded
        assert panel.grid.item(8,2) is None
        assert "TMVKCalibThread" in panel.log.toPlainText()
        assert not panel.buttons["bCalibGenerate"].isEnabled()
        assert not panel.buttons["localCalibSaveProposal"].isEnabled()
        assert path.read_bytes()
        assert sha256(path.read_bytes()).hexdigest()==path_sha
        assert not page.findChild(QPushButton,"bCalibStart").isEnabled()
    finally:
        w.close()
        qt_app.processEvents()


def test_original_calib_source_rejects_absent_data_and_no_hardware_start(
        tmp_path,qt_app):
    from ..desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.original_root_tabs.setCurrentIndex(6)
        panel=w.original_calib_panel
        assert panel.steps.count()==49
        assert panel.workspace.grid[8][2]==""
        assert not panel.buttons["bCalibGenerate"].isEnabled()
        assert not panel.buttons["bCalibStart"].isEnabled()
        bogus=tmp_path/"fake-calib.csv"
        bogus.write_text("sep=|\nnot an original 77x11 matrix",encoding="utf-8")
        with pytest.raises(ValueError,match="77 rows"):
            panel.load_csv(bogus)
        assert panel.workspace.source_file is None
        assert not panel.buttons["bCalibStart"].isEnabled()
        assert not panel.buttons["bCalibGenerate"].isEnabled()
        assert panel.log.toPlainText()==""
    finally:
        w.close()
        qt_app.processEvents()
