"""Stage111Z31BJ integrated visible Qt File->Wave->Spectrum->Status QA.

Each interaction operates against an already validated offline session;
no live device, original executable, x32dbg or private original data.
"""
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QTabWidget

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from mvk_compatible.core.direct_bin_session import DirectBinSession


def test_source_file_workspace_real_values_and_actual_graph_navigation(
        qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        ui=win.original_shell
        assert win.original_root_tabs.count()==7
        start=win.original_start_launcher.findChild(QPushButton,"bTaskView")
        assert start is not None
        start.click()
        qt_app.processEvents()
        assert win.original_root_tabs.currentIndex()==5
        assert ui.file_metadata.rowCount()==0
        assert ui.file_action_buttons["fileGoSignal"].isEnabled() is False
        assert ui.file_action_buttons["fileGoSpectrum"].isEnabled() is False
        assert ui.file_action_buttons["fileGoStatus"].isEnabled() is False

        win.open_archive(fixture_zip(tmp_path,sample_count=4096))
        qt_app.processEvents()
        assert win.session is not None
        assert ui.file_page.findChild(QTabWidget,"tcFileActions").count()==2
        assert ui.file_metadata.rowCount()>=10
        assert ui.file_spec.count()==43
        assert ui.file_values.count()==24
        assert "АЦП1" in ui.file_summary.text()
        assert "VALUES/AUX" in ui.file_summary.text()
        assert ui.file_action_buttons["fileGoSignal"].isEnabled()
        assert ui.file_action_buttons["fileGoSpectrum"].isEnabled()
        assert ui.file_action_buttons["fileGoStatus"].isEnabled()
        assert any("SHA256" in ui.file_metadata.item(i,0).text()
                   for i in range(ui.file_metadata.rowCount()))
        # Source PageFile actions route to the same EXISTING working graph,
        # without opening a second data session or replacing FFT samples.
        saved=win._full_spectrum
        ui.file_action_buttons["fileGoSignal"].click()
        qt_app.processEvents()
        assert win.original_root_tabs.currentIndex()==3
        assert win.tabs.currentIndex()==1
        assert win.wave_plot.listDataItems()
        win.original_root_tabs.setCurrentIndex(5)
        ui.file_action_buttons["fileGoSpectrum"].click()
        qt_app.processEvents()
        assert win.original_root_tabs.currentIndex()==4
        assert win.tabs.currentIndex()==2
        assert win.spec_plot.listDataItems()
        assert win._full_spectrum is saved
        win.original_root_tabs.setCurrentIndex(5)
        ui.file_action_buttons["fileGoStatus"].click()
        qt_app.processEvents()
        assert win.original_root_tabs.currentIndex()==2
        assert ui.status_table.rowCount()>1

        win.adc.setCurrentIndex(6)
        qt_app.processEvents()
        assert "АЦП7" in ui.file_summary.text()
        assert ui.file_channels.currentItem().data(Qt.UserRole)==7
        assert win._full_spectrum["channel"]==7
        assert ui.file_values.count()==24 and ui.file_spec.count()==43

        win.tick.setValue(1)
        qt_app.processEvents()
        assert "обновление 1/" in ui.file_summary.text()
        assert ui.file_spec.count()==43
        assert ui.file_values.count()==24

        win._close_session()
        qt_app.processEvents()
        assert win.session is None
        assert ui.file_values.count()==0
        assert ui.file_spec.count()==0
        assert ui.file_metadata.rowCount()==0
        assert all(not button.isEnabled()
                   for button in ui.file_action_buttons.values())
    finally:
        win.close()
        qt_app.processEvents()


def test_zip_to_direct_bin_clears_24_and_43_original_values(
        qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    bin_path,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    win=MainWindow()
    win.show()
    try:
        ui=win.original_shell
        win.open_archive(fixture_zip(tmp_path,sample_count=4096))
        assert ui.file_values.count()==24
        assert ui.file_spec.count()==43

        win.open_archive(bin_path)
        qt_app.processEvents()
        assert isinstance(win.session,DirectBinSession)
        assert ui.file_channels.count()==1
        assert ui.file_values.count()==1
        assert ui.file_spec.count()==1
        assert "Нет подтверждённых" in ui.file_values.item(0).text()
        assert "не подтверждён" in ui.file_spec.item(0).text()
        assert "АЦП4" in ui.file_summary.text()
        assert "нет аппаратных VALUES/AUX" in ui.file_summary.text()
        assert ui.file_action_buttons["fileGoSignal"].isEnabled()
        assert ui.file_action_buttons["fileGoSpectrum"].isEnabled()
        assert ui.status_table.rowCount()==1
        assert not ui.status_plot.isVisible()

        ui.file_action_buttons["fileGoSpectrum"].click()
        qt_app.processEvents()
        assert win.original_root_tabs.currentIndex()==4
        assert win._full_spectrum["channel"]==4
        assert win._full_spectrum["physical_units_verified"] is False
    finally:
        win.close()
        qt_app.processEvents()
