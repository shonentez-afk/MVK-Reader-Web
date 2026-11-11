"""Stage111Z31BH: Qt source InputValue validation is local-only.

No original application, device, calibration, external files or GUI typing.
"""
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QPushButton, QTabWidget
from .test_desktop_qt import qt_app


def test_source_config_local_validation_does_not_enable_edit_or_device(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        panel=w.original_config_panel
        assert panel.source_mode==6
        assert w.original_root_tabs.currentIndex()==0
        assert w.original_start_launcher.findChild(
            QPushButton,"bTaskConfigIP").isEnabled()
        panel.set_source_mode(4)
        w.original_root_tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert panel.basic_table.rowCount()==15
        assert panel.page.findChild(QTabWidget,"tcConfig").count()==2
        before=panel.document.report()["parsed_cells"]
        title=panel.source_note.text()

        good=panel.preview_local_value_input(3,"502")
        assert good["source_subset_syntax_valid"]
        assert good["payload_bytes"]==4
        assert good["source_field"]=="ConfigModbusPort"
        assert good["source_mode"]==4
        assert not good["source_protection_state_known"]
        assert not good["original_runtime_acceptance_verified"]
        assert not good["device_config_write_allowed"]
        assert not good["local_text_file_mutated"]

        small=panel.preview_local_value_input(3,"0")
        big=panel.preview_local_value_input(3,"65536")
        assert small["reason_source_key"]=="ctTooSmall"
        assert big["reason_source_key"]=="ctTooBig"
        secret=panel.preview_local_value_input(14,"fake password")
        assert secret["reason_source_key"]=="ctProtectedValue"
        assert "fake password" not in repr(secret)

        panel.set_source_mode(5)
        assert panel.preview_local_value_input(0,"1.75")[
            "source_subset_syntax_valid"]
        assert panel.preview_local_value_input(8,"10001")[
            "reason_source_key"]=="ctTooBig"
        assert panel.preview_local_value_input(9,"0")[
            "source_subset_syntax_valid"]

        with pytest.raises(ValueError):
            panel.preview_local_value_input(10,"123")
        panel.set_source_mode(6)
        with pytest.raises(ValueError):
            panel.preview_local_value_input(0,"1")

        assert panel.document.report()["parsed_cells"]==before==0
        for name in ("bConfigSave","bConfigReset","bConfigDownload",
                     "bConfigUpload"):
            assert not panel.page.findChild(QPushButton,name).isEnabled()
        panel.set_source_mode(4)
        dialog=panel.basic_detail_dialog(3,3)
        try:
            assert dialog.edVal.isReadOnly() and not dialog.bOk.isEnabled()
        finally:
            dialog.close()
    finally:
        w.close()
        qt_app.processEvents()
