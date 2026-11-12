"""Stage111Z31BW actual Qt PageAdc source menus + all-pages measurement path."""
from __future__ import annotations

from hashlib import sha256

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication,QTableWidget

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from ..core.original_adc_view_controls import (
    ADC_HORIZONTAL_MS,ADC_VERTICAL_DIVISORS,
    source_adc_horizontal_view,source_adc_vertical_view,
)


def test_source_adc_scale_menu_14_13_changes_real_core_wave_and_qt_y(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    original=fixture_zip(tmp_path,sample_count=8192)
    digest=sha256(original.read_bytes()).hexdigest()
    window=MainWindow()
    window.show()
    qt_app.processEvents()
    try:
        window.open_archive(original)
        window.original_root_tabs.setCurrentIndex(3)
        qt_app.processEvents()
        assert window.wave_hscale_button.objectName()=="bAdcHScale"
        assert window.wave_vscale_button.objectName()=="bAdcVScale"
        assert len(window.wave_hscale_menu.actions())==14
        assert len(window.wave_vscale_menu.actions())==13
        assert tuple(a.data() for a in window.wave_hscale_menu.actions())==tuple(range(14))
        assert tuple(a.data() for a in window.wave_vscale_menu.actions())==tuple(range(13))
        window.wave_hscale_menu.actions()[9].trigger()  # 20ms exactly 1310 samples
        qt_app.processEvents()
        flow=window._current_offline_flow()
        h=window._source_wave_hscale_model
        assert h["requested_samples"]==int(flow.source_record()["sample_rate_hz"])*20//1000
        assert h["actual_window_samples"]==h["requested_samples"]
        assert window.wave_seconds.value()==.02
        assert window._source_wave_trace["window_samples"]==h["requested_samples"]
        window.wave_vscale_menu.actions()[2].trigger()  # /5 from full GetSignal
        qt_app.processEvents()
        bound=window._source_wave_scale_model
        assert bound["divisor"]==5
        assert bound["source_bin_sha256"]==flow.source_record()["source_bin_sha256"]
        bounds=window.wave_plot.getViewBox().viewRange()[1]
        assert bounds[0]==pytest.approx(bound["y_min"],rel=1e-5,abs=1e-6)
        assert bounds[1]==pytest.approx(bound["y_max"],rel=1e-5,abs=1e-6)
        assert window.wave_vscale_menu.actions()[2].isChecked()
        assert "1/5" in window.wave_vscale_button.text()
        # Switching real ADC refreshes both Core provenance and Qt visible plot.
        window.adc.setCurrentIndex(1)
        qt_app.processEvents()
        flow2=window._current_offline_flow()
        assert flow2.channel==2
        assert window._source_wave_scale_model["selected_adc"]==2
        assert window._source_wave_scale_model["source_bin_sha256"]==flow2.source_record()["source_bin_sha256"]
        assert window._source_wave_scale_model["source_bin_sha256"]!=bound["source_bin_sha256"]
        assert sha256(original.read_bytes()).hexdigest()==digest
    finally:
        window.close()
        qt_app.processEvents()


def test_one_native_session_full_seven_page_route_with_readbacks(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    from ..desktop.original_windowman_form import OriginalWindowManForm
    from ..desktop.original_value_edit_dialog import OriginalValueEditDialog
    original=fixture_zip(tmp_path,sample_count=8192)
    digest=sha256(original.read_bytes()).hexdigest()
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.original_start_controller.set_library(tmp_path)
        w.open_archive(original)
        flow=w._current_offline_flow()
        selected_sha=flow.source_record()["source_bin_sha256"]
        # PageStart: local library is real and device TCP is not triggered.
        w.original_root_tabs.setCurrentIndex(0)
        qt_app.processEvents()
        assert w.original_start_controller.workspace.directory()==tmp_path
        # PageConfig: source editor and original 2 tabs are actual widgets.
        w.original_root_tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert w.original_shell.config_page.objectName()=="PageConfig"
        assert w.original_shell.config_page.findChild(QTableWidget,"tabConfigChannels")
        # PageStatus: verified tick 43-band source table follows same session.
        w.original_root_tabs.setCurrentIndex(2)
        w.original_shell.status_tabs.setCurrentIndex(5)
        qt_app.processEvents()
        assert w.original_shell.status_table.rowCount()==43
        assert w.original_shell._source_status_projection.source_digest==selected_sha
        # PageAdc: actual integer H request and linked measured samples.
        w.original_root_tabs.setCurrentIndex(3)
        w.wave_hscale_menu.actions()[9].trigger()
        w.wave_vscale_menu.actions()[2].trigger()
        qt_app.processEvents()
        assert w._source_wave_hscale_model["actual_window_samples"]==1310
        assert w._source_wave_scale_model["selected_adc"]==flow.channel
        # PageSpectrum: visible N/2 FFT and selected source-bound Copy.
        w.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        assert w._full_spectrum is not None
        action_flow,action=w._current_original_spectrum_action()
        assert action_flow.source_record()["source_bin_sha256"]==selected_sha
        assert len(w._full_spectrum["amplitude"])==w._full_spectrum["n_fft"]//2
        w.spec_copy_button.click()
        qt_app.processEvents()
        assert QApplication.clipboard().text()==action.clipboard_text(decimal_separator=",")
        # PageFile: source selection tied to same open ZIP, not synthetic placeholder.
        w.original_root_tabs.setCurrentIndex(5)
        qt_app.processEvents()
        assert w.original_shell.file_channels.count()>=8
        assert w.original_shell.file_export_button.isEnabled()
        assert w.original_shell._file_flow.source_record()["source_bin_sha256"]==selected_sha
        # PageCalib: 49 test steps, 77x11 grid, never activate hardware.
        w.original_root_tabs.setCurrentIndex(6)
        qt_app.processEvents()
        assert w.original_calib_panel.steps.count()==49
        assert w.original_calib_panel.page.objectName()=="PageCalib"
        # Third-party original Delphi form types must be instantiated,
        # not merely counted as navigation labels.
        edit=OriginalValueEditDialog(prompt="Local verified source",
            value="1",read_only=True,parent=w)
        messages=OriginalWindowManForm(parent=w)
        assert edit.objectName()=="mvkeditform"
        assert messages.objectName()=="WindowManForm"
        assert not edit.bOk.isEnabled()
        edit.close()
        messages.close()
        assert sha256(original.read_bytes()).hexdigest()==digest
        assert w._current_offline_flow().source_record()["source_bin_sha256"]==selected_sha
    finally:
        w.close()
        qt_app.processEvents()
