"""Saved TACH/ADC BIN Mode1, through a genuine MainWindow source open."""
from datetime import datetime, timezone

import numpy as np
import pytest

from .test_desktop_qt import qt_app
from ..core.original_mode2_source_files import build_original_tsxml_compatible


def _write_bin(root, label, channel, payload):
    name=f"MVK00000043-{label}-2026-11-24--10-00-00.bin"
    path=root/name
    path.write_bytes(payload)
    xml, _=build_original_tsxml_compatible(
        channel=channel,binary_basename=name,size_bytes=len(payload),rate_hz=8192,
        local_time=datetime(2026,11,24,10,0,1,tzinfo=timezone.utc),
        device_label="MVK00000043",channel_label=label)
    sidecar=path.with_name(name+".tsxml")
    sidecar.write_bytes(xml)
    return path,sidecar


def test_mode1_opens_selected_tach_and_safely_reopens_adc(tmp_path,qt_app,monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from ..desktop.main_window import MainWindow

    wave=(127+115*np.sin(2*np.pi*np.arange(1024)*32/1024)).astype('u1')
    _, tach1_xml=_write_bin(tmp_path,"TACH1",9,bytes(1024))
    tach2,tach2_xml=_write_bin(tmp_path,"TACH2",10,wave.tobytes())
    adc,_=_write_bin(tmp_path,"ADC4",4,
                     (np.arange(1024)%41).astype("<f4").tobytes())
    messages=[]
    for handler in ("critical","warning"):
        monkeypatch.setattr(QMessageBox,handler,lambda *args: messages.append(args[-1]))
    win=MainWindow()
    try:
        win.show()
        qt_app.processEvents()
        win.spec_f_range.setValue(3.0)
        win.open_archive(tach2_xml)
        qt_app.processEvents()
        assert not messages
        assert win.session.available_channels==(4,9,10)
        assert win._ch()==10 and win.adc.currentIndex()==9
        assert win.wave_channel_tabs.currentIndex()==win.spec_channel_tabs.currentIndex()==9
        assert win.wave_channel_tabs.isTabEnabled(8) and win.spec_channel_tabs.isTabEnabled(9)
        assert not win.wave_channel_tabs.isTabEnabled(0)
        flags=win.original_shell.file_channels
        assert flags.item(9).data(Qt.UserRole)==10
        assert flags.item(9).flags() & Qt.ItemIsEnabled
        assert "TACH2:" in flags.item(9).text() and "Byte" in flags.item(9).text()
        assert "TACH2" in win.original_shell.file_source_evidence.text()
        assert not win.tick.isEnabled() and "DSP/VALUES/AUX" in win.calc_source.text()
        assert not win.wave_filter_button.isEnabled()
        assert not win.spec_envelope_button.isEnabled()
        assert not win.spec_f_range.isEnabled() and not win.spec_input_domain.isEnabled()
        assert win.wave_mode.currentIndex()==1

        trace=win._source_wave_trace
        assert trace["channel"]==10 and trace["mode"]=="acdc"
        assert trace["source_tach_byte_normalization_divisor"]==255
        assert trace["sample_rate_hz"]==8192 and trace["removed_mean_m_s2"]==0
        assert trace["peak_m_s2"]==pytest.approx(float(wave.max())/255)
        assert "Byte/255" in win.wave_plot.getAxis('left').labelText
        assert not win.wave_vscale_button.isEnabled()
        assert win.wave_vscale_button.text()=="1"
        assert win.wave_plot.getViewBox().viewRange()[1]==pytest.approx([-.5,1.5])
        win._select_original_wave_vscale(4)
        assert win.wave_plot.getViewBox().viewRange()[1]==pytest.approx([-.5,1.5])
        assert "м/с" not in win.wave_mean_primary.text()
        assert win._full_spectrum["f_range_used"]==1.
        for index, unit in enumerate(("дБ","","~","~~")):
            win.spec_mode.setCurrentIndex(index)
            assert win._full_spectrum["unit"]==unit
            assert win.spec_plot.getAxis("left").labelText==unit
            if index:
                assert all("м/с" not in action.text() and "мкм" not in action.text()
                           for action in win._spec_vscale_actions)
            assert win._full_spectrum["spectrum_summary"]["output_peak_frequency_hz"]==pytest.approx(256,abs=1.0)
        assert win.spec_copy_button.isEnabled() and win.spec_save_button.isEnabled()
        assert "м/с" not in win.spec_mean_primary.text()
        assert "не обороты" in win.spec_mean_primary.text()

        assert win.source_view_state.channel==10
        assert win.source_view_state.saved_byte_channel

        monkeypatch.setattr(QMessageBox,"question",lambda *args: QMessageBox.Yes)
        win._copy_spec_summary()
        assert "НЕ КАЛИБРОВАНО" in QApplication.clipboard().text()
        assert len(QApplication.clipboard().text().splitlines()[-1].split("\t"))==3
        local_csv=tmp_path/"local_tach.csv"
        monkeypatch.setattr(QFileDialog,"getSaveFileName",
                            lambda *args: (str(local_csv),"CSV"))
        win._save_spec_summary()
        assert "НЕ КАЛИБРОВАНО" in local_csv.read_text(encoding="utf-8")

        stale_csv=tmp_path/"must_not_be_created.csv"
        errors=[]
        monkeypatch.setattr(win.original_window_man,"spawn_error",
                            lambda message: errors.append(message))
        def replace_source_during_save(*args):
            win.open_archive(adc)
            return str(stale_csv),"CSV"
        monkeypatch.setattr(QFileDialog,"getSaveFileName",replace_source_during_save)
        win._save_spec_summary()
        assert not stale_csv.exists()
        assert errors and "Источник сменился" in errors[-1]
        assert not messages
        assert win._ch()==4 and win._full_spectrum["channel"]==4
        assert win.source_view_state.channel==4
        assert not win.source_view_state.saved_byte_channel
        assert win._source_wave_trace["channel"]==4
        assert win._full_spectrum["f_range_used"]==3.
        assert win.spec_f_range.isEnabled() and win.wave_type_button.isEnabled()
        assert "Byte/255" not in win.wave_plot.getAxis('left').labelText

        win.open_archive(tach1_xml)
        assert win._ch()==9 and win._full_spectrum["channel"]==9
        assert win._source_wave_trace["peak_m_s2"]==0.
        assert win._full_spectrum["file"]!=tach2.name

        # Changed Byte BIN has its own retained SHA, even at the same size.
        selected=win.session.path
        selected.write_bytes(bytes((255,))+bytes(1023))
        win.refresh_wave(quiet=True)
        win.refresh_spec()
        assert messages and "изменён" in messages[-1]
        assert win._source_wave_trace is None and win._full_spectrum is None
        assert not win.spec_copy_button.isEnabled() and not win.spec_save_button.isEnabled()
        assert win.original_shell.view_panel.isHidden()
    finally:
        win.close()
        qt_app.processEvents()


def test_mode1_short_saved_tach_keeps_wave_time_and_no_stale_fft(tmp_path,qt_app,monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ..desktop.main_window import MainWindow

    long_dir=tmp_path/"long"
    short_dir=tmp_path/"short"
    long_dir.mkdir()
    short_dir.mkdir()
    long,_=_write_bin(long_dir,"TACH1",9,bytes((0,255))*512)
    short,_=_write_bin(short_dir,"TACH2",10,bytes(range(1,49)))
    messages=[]
    for handler in ("critical","warning"):
        monkeypatch.setattr(QMessageBox,handler,lambda *args: messages.append(args[-1]))
    win=MainWindow()
    try:
        win.open_archive(long)
        assert win._full_spectrum["channel"]==9
        win.open_archive(short)
        assert not messages
        assert win._ch()==10 and win.session.path==short
        assert win._source_wave_trace["window_samples"]==48
        assert win._source_view_time is not None and win._source_view_time.adc==10
        assert win._full_spectrum is None
        assert not win.spec_copy_button.isEnabled() and not win.spec_save_button.isEnabled()
        assert "доступно 48" in win.spec_hint.text()
        assert not win.spec_n.model().item(0).isEnabled()
    finally:
        win.close()
        qt_app.processEvents()
