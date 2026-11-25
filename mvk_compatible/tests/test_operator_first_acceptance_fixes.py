import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from .test_desktop_qt import qt_app
from .test_mode1_saved_adc_spectrum_export_qt import _adc
from ..desktop.main_window import MainWindow
from ..core.original_adc_spectrum_actions import append_source_spec_freq_csv, spectrum_source_ru_header

@pytest.mark.parametrize('close_mode', ['close', 'escape'])
def test_dismiss_pending_measurement_returns_to_archive(tmp_path, qt_app, close_mode):
    path, _ = _adc(tmp_path, 1, 'м/с2', 8)
    w = MainWindow()
    w.show()
    try:
        w.open_archive(path)
        w.original_root_tabs.setCurrentIndex(0)
        start = w.original_start_controller
        assert start.open_capture_dialog()
        dlg = w._native_dialog
        assert dlg.isVisible() and w._measurement_mode_selected and not w._live_active
        qt_app.processEvents()
        if close_mode == 'escape':
            QTest.keyClick(dlg, Qt.Key_Escape)
        else:
            assert dlg.close()
        qt_app.processEvents()
        assert not dlg.isVisible() and not w._measurement_mode_selected
        assert w.session and w.session.path == path
        assert w.wave_advanced_button.isHidden() and w.spec_advanced_button.isHidden()
        assert start.open_config_mode(6) == 6
    finally:
        w.close()

def test_invalid_ip_has_visible_warning_and_never_arms_tcp(qt_app, monkeypatch):
    w = MainWindow()
    w.show()
    messages = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: messages.append(args[-1]))
    try:
        start = w.original_start_controller
        w.activateWindow()
        qt_app.processEvents()
        start.ip_edit.setText('bad-ip')
        assert not start.open_capture_dialog()
        qt_app.processEvents()
        assert start.ip_edit.hasFocus()
        assert messages and 'IPv4' in messages[-1]
        assert not w._measurement_mode_selected and not w._live_active
    finally:
        w.close()

def test_stale_copy_visibly_leaves_clipboard_unchanged(tmp_path, qt_app, monkeypatch):
    path, _ = _adc(tmp_path, 1, 'м/с2', 8)
    w = MainWindow()
    w.show()
    messages = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: messages.append(args[-1]))
    try:
        w.open_archive(path)
        assert w.spec_copy_button.isEnabled()
        QApplication.clipboard().setText('earlier channel data')
        path.write_bytes(path.read_bytes() + b'\x00')
        w.spec_copy_button.click()
        assert messages and 'Буфер обмена не изменён' in messages[-1]
        assert QApplication.clipboard().text() == 'earlier channel data'
    finally:
        w.close()

@pytest.mark.parametrize('tail', [b'', b'1|2|', b'1|2|\r\n', b'1.2|2|3\r\n'])
def test_daily_spectrum_header_only_recovers_but_bad_rows_are_refused(tmp_path, qt_app, tail):
    path, _ = _adc(tmp_path, 1, 'м/с2', 8)
    w = MainWindow()
    w.show()
    try:
        w.open_archive(path)
        flow, action = w._current_original_spectrum_action()
        dest = tmp_path / 'SPEC-FREQ-2026-11-25.csv'
        header = ('sep=|\r\n' + spectrum_source_ru_header(action.spectrum_mode, action.source_units) + '\r\n').encode('cp1251')
        dest.write_bytes(header + tail)
        if not tail:
            append_source_spec_freq_csv(action, flow, dest, spectrum=w._full_spectrum)
            assert dest.read_bytes().startswith(header)
            assert dest.read_bytes().count(b'\r\n') == 3
        else:
            with pytest.raises(ValueError):
                append_source_spec_freq_csv(action, flow, dest, spectrum=w._full_spectrum)
            assert dest.read_bytes() == header + tail
    finally:
        w.close()

def test_open_selected_archive_reveals_clickable_tabs_without_resize(tmp_path, qt_app, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path, _ = _adc(tmp_path, 1, 'м/с2', 8)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    qt_app.processEvents()
    root = w.original_root_tabs
    size = w.size()
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), 'BIN'))
        w.choose_archive()
        qt_app.processEvents()
        assert w.size() == size
        assert root.currentIndex() == 3
        for page in (3, 4, 3):
            rect = root.tabRect(page)
            assert rect.isValid() and root.tabAt(rect.center()) == page
            QTest.mouseClick(root, Qt.LeftButton, pos=rect.center())
            assert root.currentIndex() == page
    finally:
        w.close()

def test_archived_early_fft_is_marked_preview_and_never_exportable(tmp_path, qt_app):
    import numpy as np
    from ..core.offline_export import spectrum_for_zip
    from ..core.storage_f_range_idr_candidate import DOMAIN_ORIGINAL_STORAGE
    path, _ = _adc(tmp_path, 1, 'м/с2', 8, n=16384)
    w = MainWindow()
    w.show()
    try:
        w.open_archive(path)
        w.original_shell.view_slider.setValue(50)
        w.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        d=w._full_spectrum
        assert d['preview_left_padding_samples']==12288
        assert d['end_s']==0.5
        assert 'только просмотр' in w.spec_mean_primary.text()
        assert 'условн.' not in w.spec_mean_primary.text()
        assert not w.spec_copy_button.isEnabled() and not w.spec_save_button.isEnabled()
        with pytest.raises(ValueError,match='только для просмотра'):
            w._current_original_spectrum_action()
        samples,fs,audit,filename=w.session.samples(1)
        expected=spectrum_for_zip(path,1,16384,w.spec_mode.currentIndex(),
            max_hz=1e9,max_points=8192,f_range=8,input_domain=DOMAIN_ORIGINAL_STORAGE,
            sample_provider=lambda _:(np.pad(samples[:4096],(12288,0)),fs,audit,filename))
        assert np.asarray(d['amplitude'],dtype='<f4').tobytes()==np.asarray(expected['amplitude'],dtype='<f4').tobytes()
        assert w.spec_plot.getViewBox().viewRange()[0][1]<=4096
        assert not next(a for a in w._spec_hscale_actions if a.data()==6400).isEnabled()
        w.original_shell.view_slider.setValue(w.original_shell.view_slider.maximum())
        assert w._full_spectrum['preview_left_padding_samples']==0
        assert w.spec_copy_button.isEnabled() and w.spec_save_button.isEnabled()
    finally:
        w.close()


def test_saved_tach_at_same_time_and_n_does_not_depend_on_opening_route(tmp_path, qt_app):
    import numpy as np
    from .test_stage111z31en_saved_tach_qt import _write_bin
    adc,_=_adc(tmp_path, 1, 'м/с2', 8, n=16384)
    raw=(127+91*np.sin(np.arange(9121)*0.32)).astype('u1')
    tach,_=_write_bin(tmp_path, 'TACH2', 10, raw.tobytes())
    w=MainWindow()
    w.show()
    try:
        w.open_archive(tach)
        end=w.original_shell.view_slider.maximum()
        w.original_shell.view_slider.setValue(end)
        w.spec_n.setCurrentText('8192')
        w.refresh_spec()
        direct=w._full_spectrum['amplitude']
        w.open_archive(adc)
        w.spec_channel_tabs.setCurrentIndex(9)
        w.original_shell.view_slider.setValue(end)
        w.spec_n.setCurrentText('8192')
        w.refresh_spec()
        assert w._full_spectrum['amplitude']==direct
        assert w.original_shell.view_slider.value()==end
    finally:
        w.close()

def test_timeline_reads_one_verified_source_snapshot_but_export_rechecks(tmp_path, qt_app, monkeypatch):
    from ..core.direct_bin_session import DirectBinSession
    path,_=_adc(tmp_path,1,'м/с2',8,n=16384)
    w=MainWindow()
    w.show()
    try:
        w.open_archive(path)
        reads=[]
        orig=DirectBinSession.read_current_samples
        def logged(self,ch):
            reads.append(ch)
            return orig(self,ch)
        monkeypatch.setattr(DirectBinSession,'read_current_samples',logged)
        slider=w.original_shell.view_slider
        slider.setValue(150)
        assert reads==[1]
        slider.setValue(slider.maximum())
        assert reads==[1,1]
        assert w.spec_copy_button.isEnabled()
        # Change only our fixture and force an export check while inside
        # a nested render transaction; stale content must still fail.
        with w.session.sample_render_transaction():
            w.session.samples(1)
            path.write_bytes(path.read_bytes()+b'\0')
            with pytest.raises(ValueError,match='изменён после открытия'):
                w._current_original_spectrum_action()
    finally:
        w.close()

def test_regular_save_as_does_not_switch_to_research_csv(tmp_path, qt_app, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path,_=_adc(tmp_path,1,'м/с2',8)
    w=MainWindow()
    w.show()
    errors=[]
    try:
        w.open_archive(path)
        monkeypatch.setattr(w.original_window_man,'spawn_error',errors.append)
        dest=tmp_path/'operator-name.csv'
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**kw:(str(dest),'CSV'))
        w.spec_save_button.click()
        assert not dest.exists()
        assert errors and 'оставьте имя SPEC-FREQ' in errors[-1]
    finally:
        w.close()

def test_saved_adc_never_appends_other_physical_units_under_existing_header(tmp_path, qt_app):
    path,_=_adc(tmp_path,1,'м/с2',8)
    w=MainWindow()
    w.show()
    try:
        w.open_archive(path)
        dest=tmp_path/'SPEC-FREQ-2026-11-25.csv'
        flow,action=w._current_original_spectrum_action()
        append_source_spec_freq_csv(action,flow,dest,spectrum=w._full_spectrum)
        before=dest.read_bytes()
        w.spec_mode.setCurrentIndex(2)
        flow,action=w._current_original_spectrum_action()
        with pytest.raises(ValueError,match='единицами'):
            append_source_spec_freq_csv(action,flow,dest,spectrum=w._full_spectrum)
        assert dest.read_bytes()==before
    finally:
        w.close()


def test_spec_save_as_appends_without_asking_for_overwrite(tmp_path, qt_app, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path,_=_adc(tmp_path,1,'м/с2',8)
    w=MainWindow()
    w.show()
    prompts=[]
    try:
        w.open_archive(path)
        dest=tmp_path/'SPEC-FREQ-2026-11-25.csv'
        def save_dialog(*args, **kwargs):
            prompts.append((args, kwargs))
            return str(dest),'SPEC-FREQ CSV'
        monkeypatch.setattr(QFileDialog,'getSaveFileName',save_dialog)
        assert w._save_spec_summary()['appended_existing_candidate'] is False
        before=dest.read_bytes()
        assert w._save_spec_summary()['appended_existing_candidate'] is True
        assert len(prompts)==2
        assert all(args[5] & QFileDialog.Option.DontConfirmOverwrite
                   for args,_ in prompts)
        assert all('добавление строки' in args[1] for args,_ in prompts)
        after=dest.read_bytes()
        assert after.startswith(before)
        assert after.count(b'\r\n')==before.count(b'\r\n')+1
    finally:
        w.close()


def test_archive_opens_verified_pair_and_names_unusable_sibling(tmp_path, qt_app, monkeypatch):
    adc1,_=_adc(tmp_path,1,'м/с2',8)
    adc2,sidecar2=_adc(tmp_path,2,'м/с2',8)
    sidecar2.unlink()
    w=MainWindow()
    w.show()
    messages=[]
    monkeypatch.setattr(QMessageBox,'critical',lambda *args:messages.append(args[-1]))
    try:
        w.open_archive(adc1)
        assert w.session.available_channels==(1,)
        assert 'Не открыто соседних каналов: 1' in w.statusBar().currentMessage()
        assert adc2.name in w.task_session_summary.text()
        assert 'Не открыты каналы' in w.task_session_summary.text()
        original=w.session
        w.open_archive(adc2)
        assert w.session is original
        assert messages and adc2.name in messages[-1]
        assert 'Предыдущая запись осталась открытой' in messages[-1]
    finally:
        w.close()

def test_saved_count_cannot_append_under_physical_header(tmp_path, qt_app):
    import numpy as np
    from .test_stage111z31en_saved_tach_qt import _write_bin
    adc, _ = _adc(tmp_path, 1, 'м/с2', 8, n=8192)
    tach, _ = _write_bin(tmp_path, 'TACH2', 10,
        (127+90*np.sin(np.arange(8192)*.32)).astype('u1').tobytes())
    dest = tmp_path/'SPEC-FREQ-2026-11-25.csv'
    w = MainWindow()
    w.show()
    try:
        w.open_archive(adc)
        flow, action = w._current_original_spectrum_action()
        append_source_spec_freq_csv(action, flow, dest, spectrum=w._full_spectrum)
        before = dest.read_bytes()
        w.open_archive(tach)
        flow, action = w._current_original_spectrum_action()
        assert action.source_units == ""
        with pytest.raises(ValueError, match='единицами'):
            append_source_spec_freq_csv(action, flow, dest, spectrum=w._full_spectrum)
        assert dest.read_bytes() == before
    finally:
        w.close()


def test_mode2_native_consent_is_inline_and_cancel_disarms(tmp_path, qt_app, monkeypatch):
    import mvk_compatible.desktop.native_capture_dialog as native_ui
    monkeypatch.setattr(native_ui,'native_executable',lambda:tmp_path/'mock-receiver.exe')
    path,_=_adc(tmp_path,1,'м/с2',8)
    win=MainWindow()
    win.show()
    try:
        win.open_archive(path)
        start=win.original_start_controller
        win.original_root_tabs.setCurrentIndex(0)
        start.ip_edit.setText('192.0.2.10')
        assert start.open_capture_dialog()
        qt_app.processEvents()
        panel=win._native_dialog
        host=win._native_capture_host
        assert not panel.isWindow() and panel.window() is win
        assert panel not in QApplication.topLevelWidgets()
        assert host.parentWidget() is win.original_shell.status_page
        assert panel.isVisible() and host.isVisible()
        assert panel._original_mode2_authorized() and not panel.confirm.isChecked()
        assert not panel.start_button.isEnabled() and not panel.is_busy()
        panel.confirm.setChecked(True)
        assert not panel.start_button.isEnabled()  # no selected Ethernet interface
        panel.cancel_inline.click()
        qt_app.processEvents()
        assert not host.isVisible() and not panel._original_mode2_authorized()
        assert not panel.confirm.isChecked() and not win._measurement_mode_selected
        assert win.session.path==path
        assert start.open_capture_dialog()
        qt_app.processEvents()
        assert win._native_dialog is not panel
        assert not win._native_dialog.confirm.isChecked()
        assert not win._native_dialog.isWindow()
        assert not win._native_dialog.is_busy()
    finally:
        win.close()


def test_inline_measurement_stop_reaches_same_receiver_once(tmp_path,qt_app,monkeypatch):
    from PySide6.QtTest import QSignalSpy
    from ..core.native_r6_bridge import STOP_REQUEST
    import mvk_compatible.desktop.native_capture_dialog as native_ui
    monkeypatch.setattr(native_ui,'native_executable',lambda:tmp_path/'mock-receiver.exe')
    win=MainWindow()
    win.show()
    panel=None
    try:
        start=win.original_start_controller
        start.ip_edit.setText('192.0.2.10')
        assert start.open_capture_dialog()
        panel=win._native_dialog
        win.original_visual_skin.reveal_page(3)
        win.open_native_capture()
        assert win._native_dialog is panel
        assert not panel.isWindow()
        panel._mode='capture'
        panel._capture_root=tmp_path
        panel.captureStarted.emit()
        finalizing=QSignalSpy(panel.captureFinalizing)
        assert win.request_measurement_stop()
        assert (tmp_path/STOP_REQUEST).read_bytes()==b'STOP\n'
        assert win._live_active and win._measurement_exit_requested
        assert not win.request_measurement_stop()
        assert finalizing.count()==1
        assert win._source_mode2_runtime.receipt()['hardware_commands_sent']==0
        panel._mode=None
        panel.captureEnded.emit(False)
        assert not win._live_active and not win._measurement_mode_selected
        assert win._native_capture_host.isHidden()
    finally:
        if panel is not None:
            panel._mode=None
        if win._live_active:
            win._end_live_capture(False)
        win.close()
