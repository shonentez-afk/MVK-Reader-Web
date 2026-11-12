"""BQ: real original PageConfig bLoad/bSave, 3 modes and mvkeditform.

Synthetic source only, no device. Test actual GUI and independent saved file
readback, not another source comparison screen.
"""
import hashlib
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import (QFileDialog,QPushButton,QDialog,
                               QTableWidget,QMessageBox)
from .test_desktop_qt import qt_app
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested)
from ..core.original_config_readonly import inspect_original_local_config
from ..core.original_config_input_draft import SourceInputRejected


def _file(tmp_path):
    file=tmp_path/"synthetic_local_config.cfg"
    file.write_text(
        "0x000A w:502\n0x0020 f:2.5\n"
        "+0x0100\n0x0002 f:1.25\n0x0062 f:2.50\n",
        encoding="utf-8")
    return file


def test_real_original_config_toolbar_load_edit_save_reload_and_discard(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    from ..desktop.original_value_edit_dialog import OriginalValueEditDialog
    source=_file(tmp_path)
    src_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        panel=w.original_config_panel
        w.original_root_tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert panel.page.objectName()=="PageConfig"
        assert panel.page.findChild(QPushButton,"bConfigLoad").isEnabled()
        assert not panel.page.findChild(QPushButton,"bConfigSave").isEnabled()
        assert not panel.discard_button.isEnabled()
        assert panel.page_tabs.count()==2
        assert panel.channel_fields.objectName()=="sourceConfigSelectedAdcFields"
        assert panel.channel_table.rowCount()==8
        assert panel.alarm_table.rowCount()==64
        panel.load_local_file(source)
        assert panel.save_button.isEnabled()    # bConfigSave NOW WORKS LOCALLY
        assert not panel.page.findChild(QPushButton,"bConfigUpload").isEnabled()
        assert not panel.page.findChild(QPushButton,"bConfigDownload").isEnabled()
        assert not panel.page.findChild(QPushButton,"bConfigReset").isEnabled()

        # Mode4 IP real double-click now opens original Tmvkeditform editing
        # its actual candidate, rather than a permanently read-only dialog.
        panel.set_source_mode(4)
        qt_app.processEvents()
        assert panel.basic_table.item(3,3).text()=="w:502"
        def input_503(dlg):
            assert dlg.objectName()=="mvkeditform"
            assert not dlg.edVal.isReadOnly()
            assert dlg.bOk.isEnabled()
            dlg.edVal.setText("503")
            return QDialog.Accepted
        monkeypatch.setattr(OriginalValueEditDialog,"exec",input_503)
        panel.show_basic_details(3,3)
        assert panel.basic_table.item(3,3).text()=="w:503"
        assert panel.workspace.changed_count==1
        assert panel.discard_button.isEnabled()
        assert "Изменено в памяти: 1" in panel.source_note.text()

        # Mode5 calibrator parameters: edit LOCAL cell only, calibration
        # generator / physical device remain blocked.
        panel.set_source_mode(5)
        panel.edit_local_field("calib",0,"3.25")
        assert panel.basic_table.item(0,3).text()=="f:3.25"
        panel.set_source_mode(6)
        qt_app.processEvents()
        assert panel.channel_fields.isVisible()
        assert panel.channel_fields.rowCount()==11
        panel.edit_local_field("adc",0,"1.75",adc=1)
        assert panel.channel_fields.item(0,3).text()=="f:1.75"
        panel.page_tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert panel.alarm_table.item(0,4).text()=="f:2.50"
        panel.edit_local_alarm(1,1,"yellow_threshold","4.5")
        assert panel.alarm_table.item(0,4).text()=="f:4.5"
        assert not panel.channel_fields.isVisible()
        assert panel.workspace.changed_count==4
        assert panel.save_button.isEnabled()
        w.original_root_tabs.setCurrentIndex(1)
        capture_synthetic_ui_if_requested(
            w,qt_app,"18_bq_local_config_edited_all_modes")

        output=tmp_path/"local_config_saved_new.txt"
        monkeypatch.setattr(
            QFileDialog,"getSaveFileName",
            staticmethod(lambda *a,**kw:(str(output),"txt")))
        panel.save_button.click()
        qt_app.processEvents()
        assert output.exists()
        doc=inspect_original_local_config(output)
        assert doc.value(0x000A).formatted=="w:503"
        assert doc.value(0x0020).formatted=="f:3.25"
        assert doc.value(0x0102).formatted=="f:1.75"
        assert doc.value(0x0162).formatted=="f:4.5"
        assert hashlib.sha256(source.read_bytes()).hexdigest()==src_sha
        assert "Локальный файл сохранён" in panel.source_note.text()
        panel.discard_button.click()
        assert panel.workspace.changed_count==0
        assert panel.alarm_table.item(0,4).text()=="f:2.50"
        assert not panel.discard_button.isEnabled()
        panel.load_local_file(output)
        assert not panel.workspace.changed
        assert panel.alarm_table.item(0,4).text()=="f:4.5"
        assert panel.save_button.isEnabled()
        assert w.original_window_man is not None
    finally:
        w.close()
        qt_app.processEvents()


def test_validation_failed_load_clears_old_save_state_and_bad_edits(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    p=_file(tmp_path)
    invalid=tmp_path/"unsafe.cfg"
    invalid.write_text("@../not_allowed.cfg\n",encoding="utf-8")
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        panel=w.original_config_panel
        panel.load_local_file(p)
        assert panel.save_button.isEnabled()
        with pytest.raises(SourceInputRejected,match="ctTooSmall"):
            panel.edit_local_field("ip",3,"0")
        assert panel.workspace.changed_count==0
        with pytest.raises(ValueError):
            panel.load_local_file(invalid)
        assert panel.workspace is None
        assert not panel.save_button.isEnabled()
        assert panel.alarm_table.item(0,4).text()=="—"
        assert not panel.page.findChild(QPushButton,"bConfigUpload").isEnabled()
        with pytest.raises(ValueError):
            panel.save_local_file(tmp_path/"never_saved.cfg")
    finally:
        w.close()
        qt_app.processEvents()
