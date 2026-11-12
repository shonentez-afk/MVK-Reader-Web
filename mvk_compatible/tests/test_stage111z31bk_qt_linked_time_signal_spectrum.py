"""Stage111Z31BK: one visible tbViewTime -> real waveform, spectrum, status.

No original Win32 process or instrument; synthetic ZIP/BIN test fixtures.
The screenshot artifact shows OUR Qt application, NOT original pixel parity.
"""
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QLabel, QSlider
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested,
)
from mvk_compatible.core.direct_bin_session import DirectBinSession


def test_visible_original_time_controls_drive_same_core_wave_and_fft(
        qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        shell=win.original_shell
        slider=win.findChild(QSlider,"tbViewTime")
        stamp=win.findChild(QLabel,"lbViewTime")
        caption=win.findChild(QLabel,"sourceViewTimeContext")
        assert slider is shell.view_slider
        assert stamp is shell.view_time_label
        assert caption is shell.view_context
        assert not shell.view_panel.isVisible()
        assert not slider.isEnabled()

        win.open_archive(fixture_zip(tmp_path,sample_count=16384))
        qt_app.processEvents()
        flow=win._current_offline_flow()
        assert shell.view_panel.isVisible()
        assert slider.maximum()>5
        assert slider.value()==0
        assert stamp.text()=="00:00:00.000"
        assert shell._source_view_time.bin_sha256==flow.source_record()[
            "source_bin_sha256"]
        assert "АЦП1" in caption.text()
        assert "VALUES 2/2" in caption.text()
        assert win._source_wave_readout is not None
        assert win._source_spectrum_readout is not None
        assert win._source_spectrum_readout["n_fft"]==int(win.spec_n.currentText())
        assert "СКЗ спектра" in win.spec_core_triplet.text()
        assert "Пик спектра" in win.spec_core_triplet.text()
        assert "Амплитуда" in win.spec_core_triplet.text()
        assert "FFT N=" in win.spec_mean_primary.toolTip()
        assert "Δf=" in win.spec_mean_primary.toolTip()
        assert win.spec_lines_button.text().endswith("Гц/лин")
        win.original_root_tabs.setCurrentIndex(3)
        capture_synthetic_ui_if_requested(win,qt_app,"07_linked_wave_start")

        slider.setValue(5)  # exact verified source window, no device command
        qt_app.processEvents()
        selected=shell._source_view_time
        assert selected.position==5
        assert selected.selected_start_seconds>0
        assert stamp.text()==selected.label
        assert win.wave_start.value()==pytest.approx(
            selected.selected_start_seconds,abs=1e-3)
        assert win._source_wave_readout["source_start_sample"]==(
            selected.selected_start_sample)
        assert win._source_wave_readout["rms_from_core"]>=0
        assert len(win.wave_plot.listDataItems())>0
        assert "СКЗ сигнала:" in win.wave_mean_primary.text()
        assert win._source_spectrum_readout is not None
        assert win._source_spectrum_readout["source_bin_sha256"]==(
            selected.bin_sha256)
        assert win._source_spectrum_readout["adc"]==1
        assert not win._source_spectrum_readout[
            "original_runtime_parity_verified"]
        win.original_root_tabs.setCurrentIndex(4)
        capture_synthetic_ui_if_requested(win,qt_app,"08_linked_spectrum")

        win.adc.setCurrentIndex(6)
        qt_app.processEvents()
        assert "АЦП7" in caption.text()
        assert win._source_wave_readout["adc"]==7
        assert win._source_spectrum_readout["adc"]==7
        assert win._source_view_time.adc==7
        assert win._source_wave_readout["source_bin_sha256"]==(
            win._source_spectrum_readout["source_bin_sha256"])
        win.tick.setValue(1)
        qt_app.processEvents()
        assert "VALUES 1/2" in caption.text()
        assert "АЦП7" in caption.text()
        assert win._pagestatus_snapshot["tick"]==0
        win.original_root_tabs.setCurrentIndex(2)
        capture_synthetic_ui_if_requested(win,qt_app,"09_linked_status")

        path,_,_=_make_pair(tmp_path,adc=4,n=8192)
        win.open_archive(path)
        qt_app.processEvents()
        assert isinstance(win.session,DirectBinSession)
        assert shell.view_panel.isVisible()
        assert slider.value()==0
        assert "АЦП4" in caption.text()
        assert "VALUES/AUX НЕТ" in caption.text()
        assert win._source_view_time.adc==4
        assert win._source_wave_readout["adc"]==4
        assert win._source_spectrum_readout["adc"]==4
        assert win._source_spectrum_readout[
            "physical_calibration_verified"] is False
        assert "расч" not in win.spec_core_triplet.text().lower() or (
            win._source_spectrum_readout["unit"]=="усл. ед. BIN")

        win._close_session()
        qt_app.processEvents()
        assert not shell.view_panel.isVisible()
        assert not slider.isEnabled()
        assert win._source_view_time is None
        assert win._source_wave_readout is None
        assert win._source_spectrum_readout is None
        assert "Нет подтверждённого" in win.spec_core_triplet.text()
    finally:
        win.close()
        qt_app.processEvents()


def test_original_view_time_is_only_source_model_and_bin_has_no_fake_dsp(
        qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    try:
        path,_,_=_make_pair(tmp_path,adc=4,n=8192)
        win.open_archive(path)
        qt_app.processEvents()
        shell=win.original_shell
        assert shell.view_slider.isEnabled()
        assert win._source_view_time.position==shell.view_slider.value()
        assert shell.view_slider.maximum()>0
        shell.view_slider.setValue(2)
        qt_app.processEvents()
        flow=win._current_offline_flow()
        assert "VALUES/AUX НЕТ" in shell.view_context.text()
        assert win._pagestatus_snapshot is None
        assert shell.file_spec.count()==1  # not invented 43 bands
        assert shell.file_values.count()==1  # not invented 24 DSP rows
        assert win._source_wave_readout["source_bin_sha256"]==(
            flow.source_record()["source_bin_sha256"])
        assert win._source_spectrum_readout is not None
        assert win._source_spectrum_readout["physical_calibration_verified"] is False
        # No hardware action was enabled by the time slider.
        for name in ("bConfigSave","bConfigUpload","bConfigReset",
                     "bConfigDownload"):
            assert not shell.config_page.findChild(
                type(win.wave_filter_button),name).isEnabled()
    finally:
        win.close()
        qt_app.processEvents()
