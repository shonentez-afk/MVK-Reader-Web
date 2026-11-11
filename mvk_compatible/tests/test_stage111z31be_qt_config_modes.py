"""Stage111Z31BE: original Mode4/5/6 read-only Qt regression, no device."""
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QPushButton,QTabWidget
from .test_desktop_qt import qt_app
from mvk_compatible.core.original_config_readonly import UNKNOWN

def test_original_basic_modes_safely_render_local_file(qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    sample=tmp_path/"source.txt"
    sample.write_text(
        "0x0004 D:16909060\n0x000A D:502\n"
        "0x0060 S:sensitive-value\n0x0020 F:2.5\n"
        "0x0012 F:25\n+0x0100\n0x0002 F:1.25\n",encoding="utf-8")
    window=MainWindow()
    window.show()
    qt_app.processEvents()
    try:
        panel=window.original_config_panel
        assert panel.source_mode==6
        assert panel.page.findChild(QTabWidget,"tcConfig").count()==2
        assert not panel.basic_table.isVisible()
        panel.load_local_file(sample)
        button=window.original_start_launcher.findChild(
            QPushButton,"bTaskConfigIP")
        assert button.isEnabled()
        button.click()
        qt_app.processEvents()
        assert panel.source_mode==4
        assert window.original_root_tabs.currentIndex()==1
        assert panel.basic_table.isVisible()
        assert not panel.page_tabs.isVisible()
        assert panel.basic_table.rowCount()==15
        assert panel.basic_table.item(0,3).text()=="D:16909060"
        assert panel.basic_table.item(3,3).text()=="D:502"
        assert "sensitive-value" not in repr([
            panel.basic_table.item(i,3).text()
            for i in range(panel.basic_table.rowCount())])
        dialog=panel.basic_detail_dialog(0,3)
        try:
            assert dialog.edVal.isReadOnly() and not dialog.bOk.isEnabled()
        finally:
            dialog.close()
        panel.set_source_mode(5)  # gated source Calibration, no device action
        qt_app.processEvents()
        assert panel.basic_table.rowCount()==10
        assert panel.basic_table.item(0,1).text()=="0x0020"
        assert panel.basic_table.item(0,3).text()=="F:2.5"
        assert panel.basic_table.item(8,1).text()=="0x0012"
        assert panel.basic_table.item(8,3).text()=="F:25"
        panel.set_source_mode(6)
        qt_app.processEvents()
        assert panel.page_tabs.isVisible()
        assert not panel.basic_table.isVisible()
        assert panel.alarm_table.rowCount()==64
        assert panel.alarm_table.item(0,3).text()==UNKNOWN
        for name in ("bConfigSave","bConfigReset",
                     "bConfigDownload","bConfigUpload"):
            assert not panel.page.findChild(QPushButton,name).isEnabled()
        with pytest.raises(ValueError):panel.set_source_mode(3)
    finally:
        window.close()
        qt_app.processEvents()

def test_rejected_local_config_clears_basic_modes(qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    good=tmp_path/"good.txt"
    good.write_text("0x0004 D:4\n0x0020 F:9\n",encoding="utf-8")
    bad=tmp_path/"bad.txt"
    bad.write_text("@../secret.txt\n",encoding="utf-8")
    window=MainWindow()
    window.show()
    qt_app.processEvents()
    try:
        panel=window.original_config_panel
        panel.load_local_file(good)
        panel.set_source_mode(4)
        assert panel.basic_table.item(0,3).text()=="D:4"
        with pytest.raises(ValueError):panel.load_local_file(bad)
        assert panel.basic_table.item(0,3).text()==UNKNOWN
        panel.set_source_mode(5)
        assert panel.basic_table.item(0,3).text()==UNKNOWN
    finally:
        window.close()
        qt_app.processEvents()
