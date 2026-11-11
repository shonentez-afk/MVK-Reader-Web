"""Stage111Z31BD Qt source Config/Channels/Alarms & safe Tmvkeditform.

Synthetic files only. No original MVKView / device, no private IDP
or copied Delphi resources. Tested at Windows Qt DPI150 in CI.
"""
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton,QTabWidget,QLabel

from .test_desktop_qt import qt_app
from mvk_compatible.core.original_config_readonly import UNKNOWN


def test_original_config_two_tabs_64_slots_512_unknown_by_default(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        panel=w.original_config_panel
        assert panel.page.objectName()=="PageConfig"
        assert panel.channel_table.objectName()=="tabConfigChannels"
        assert panel.alarm_table.objectName()=="tabConfigAlarms"
        assert panel.basic_table.objectName()=="tabConfigBasic"
        assert not panel.basic_table.isVisible()
        assert panel.page.findChild(
            QTabWidget,"tcConfig").count()==2
        assert panel.channel_table.rowCount()==8
        assert panel.alarm_table.rowCount()==64
        assert panel.alarm_table.columnCount()==11
        assert panel.alarm_table.item(0,3).text()==UNKNOWN
        assert panel.channel_table.item(0,2).text()=="0"
        assert panel.load_button.isEnabled()
        assert panel.load_button.text()==""
        assert "не подтверждена" in panel.source_note.text().lower()
        for object_name in ("bConfigSave","bConfigReset","bConfigDownload","bConfigUpload"):
            action=panel.page.findChild(QPushButton,object_name)
            assert action is not None and not action.isEnabled()
            assert action.text()==""
    finally:
        w.close()
        qt_app.processEvents()


def test_local_config_file_show_same_register_and_preview_dialog_readonly(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    p=tmp_path/"original_config.txt"
    p.write_text(
        "; original IDR bounded text format\n"
        "+0x0100\n"
        "0x0060 D:44 ; parameter ID not decoded into title\n"
        "0x0062 F:2.50 ; yellow threshold\n"
        "+0x0200\n"
        "0x0060 D:6 ; ADC2\n",encoding="utf-8")
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        panel=w.original_config_panel
        report=panel.load_local_file(p)
        assert report["parsed_cells"]==3
        assert report["alarm_registers_present"]==3
        assert panel.channel_table.item(0,2).text()=="2"
        assert panel.channel_table.item(1,2).text()=="1"
        assert panel.alarm_table.item(0,3).text()=="D:44"
        assert panel.alarm_table.item(0,4).text()=="F:2.50"
        assert panel.alarm_table.item(8,3).text()=="D:6"
        assert panel.alarm_table.item(0,5).text()==UNKNOWN
        assert panel.alarm_table.item(0,3).data(Qt.UserRole)["address"]=="0x0160"
        assert "3/512" in panel.source_note.text()
        assert not report["original_live_device_config_verified"]
        assert not report["device_actions_allowed"]
        assert "3" in panel.source_note.text()

        # The original editor's real source local edit behavior is not
        # silently enabled on unverified file-only configuration.
        box=panel.alarm_detail_dialog(0,3)
        try:
            assert box.objectName()=="mvkeditform"
            assert "AlarmBand" in box.findChild(QLabel,"lbVal").text()
            assert box.edVal.text()=="D:44"
            assert box.edVal.isReadOnly()
            assert not box.bOk.isEnabled()
            assert box.bCancel.text()=="Закрыть"
            box._accept_selected()
            assert box.result()==0
            assert not box.bRecalc.isVisible()
        finally:
            box.close()

        invalid=tmp_path/"invalid.txt"
        invalid.write_text("@../secret.txt\n",encoding="utf-8")
        with pytest.raises(ValueError):
            panel.load_local_file(invalid)
        assert panel.document.report()["parsed_cells"]==0
        assert panel.alarm_table.item(0,3).text()==UNKNOWN
        assert "0/512" in panel.source_note.text()
    finally:
        w.close()
        qt_app.processEvents()
