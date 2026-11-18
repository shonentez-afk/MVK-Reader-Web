"""Stage111Z.26B Qt: original three tabs show provisional from local ZIP only."""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app


def _preview(tmp_path):
    from .test_stage111z26b_live_preview import make_preview,now
    from mvk_compatible.core.native_r6_live_preview import load_live_preview
    root,status,_=make_preview(tmp_path)
    return status,load_live_preview(root,status,now=now())


def test_live_preview_uses_same_existing_wave_spectrum_tabs_without_archive(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    window=MainWindow()
    assert not window._live_active
    assert window.session is None
    assert window.tabs.count()==3
    assert not window.tabs.isTabEnabled(1)
    window._begin_live_capture()
    assert window._live_active
    assert window.tabs.count()==3
    assert window.tabs.isTabEnabled(1)
    assert window.tabs.isTabEnabled(2)
    assert not window.tick.isEnabled()
    assert not window.task_metrics_button.isEnabled()
    assert "LIVE" in window.note.text()
    status,preview=_preview(tmp_path)
    window._receive_native_live_status(status)
    window._receive_live_preview(preview)
    assert len(window.wave_plot.listDataItems())==1
    assert len(window.spec_plot.listDataItems())==1
    # bSpecLines default N=65536 must be the ACTUAL candidate FFT N,
    # not the old silent downshift to N=8192 at Fs=65536Hz.
    assert int(window.spec_n.currentData())==65536
    assert "FFT N=65536" in window.spec_mean.text()
    assert "1 Гц/лин" in window.spec_lines_button.text()
    assert "LIVE PREVIEW" in window.wave_hint.text()
    assert "FRange повторно НЕ применялся" in window.spec_hint.text()
    assert not window.spec_copy_button.isEnabled()
    assert not window.spec_save_button.isEnabled()
    assert window._spectrum_summary is None
    assert window._full_spectrum is None
    assert window.wave_line is None
    assert window.session is None
    window.adc.setCurrentIndex(6)
    qt_app.processEvents()
    assert "АЦП7" in window.wave_mean_primary.text()
    window.spec_mode.setCurrentIndex(1)
    qt_app.processEvents()
    assert len(window.spec_plot.listDataItems())==1
    # Source menu may select a smaller, *explicit* FFT N; it must
    # recompute from the SAME SHA-verified incoming Float32 bytes.
    window.spec_n.setCurrentText("32768")
    qt_app.processEvents()
    assert "FFT N=32768" in window.spec_mean.text()
    assert "2 Гц/лин" in window.spec_lines_button.text()
    assert len(window.spec_plot.listDataItems())==1
    # This synthetic source window has only 65536 real samples.
    # Blank the prior spectrum until the larger selected N arrives.
    window.spec_n.setCurrentText("131072")
    qt_app.processEvents()
    assert "ожидание реальных данных" in window.spec_mean.text()
    assert "FFT N=131072" in window.spec_hint.text()
    assert not window.spec_plot.listDataItems()
    window.spec_n.setCurrentText("65536")
    qt_app.processEvents()
    assert "FFT N=65536" in window.spec_mean.text()
    assert len(window.spec_plot.listDataItems())==1
    window._invalidate_live_preview("некорректный SHA")
    assert not window.wave_plot.listDataItems()
    assert not window.spec_plot.listDataItems()
    window._end_live_capture(False)
    assert not window._live_active
    assert not window.tabs.isTabEnabled(1)
    assert window.session is None
    window.close()
    qt_app.processEvents()


def test_original_archive_restored_on_failed_capture(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    window=MainWindow()
    path=fixture_zip(tmp_path)
    window.open_archive(path)
    assert window.session is not None
    serial=window.session.serial
    window._begin_live_capture()
    assert window.session is None
    window.open_archive(path)  # forbidden during live, no replacement
    assert window.session is None
    window._end_live_capture(False)
    assert window.session is not None and window.session.serial==serial
    assert len(window.wave_plot.listDataItems())==1
    window.close()
    qt_app.processEvents()


def test_live_completion_disables_preview_until_verified_archive(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    window=MainWindow()
    window._begin_live_capture()
    status,preview=_preview(tmp_path)
    window._receive_native_live_status(status)
    window._receive_live_preview(preview)
    window._end_live_capture(True)
    assert window.session is None
    assert not window._live_active
    assert not window.wave_plot.listDataItems()
    verified=fixture_zip(tmp_path)
    window.open_archive(verified)
    assert window.session is not None
    assert not window._live_active
    assert len(window.wave_plot.listDataItems())==1
    window.close()
    qt_app.processEvents()


def test_qt_live_wave_and_fft_survive_late_attach_absolute_source_index(
        tmp_path,qt_app):
    from .test_stage111z26b_live_preview import make_preview,now
    from mvk_compatible.core.native_r6_live_preview import (
        MAX_SAMPLES,load_live_preview,
    )
    from mvk_compatible.desktop.main_window import MainWindow
    offset=1_000_000
    def large_cursor(meta):
        for channel in meta["channels"]:
            channel["first_sample_index"]+=offset
            channel["next_sample_index"]+=offset
    # This short original late-attach fixture keeps only 65536 real
    # samples; MAX_SAMPLES now denotes the *capacity* 262144, not the
    # contents of every individual validated preview.
    root,status,_=make_preview(tmp_path,modify=large_cursor)
    actual_fixture_samples=65536
    for ch in status["channels"][:8]:
        ch["next_sample_index"]=offset+4096+actual_fixture_samples
    preview=load_live_preview(root,status,now=now())
    assert preview.channels[1].next_index==offset+4096+actual_fixture_samples
    win=MainWindow()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(status)
        win._receive_live_preview(preview)
        assert len(win.wave_plot.listDataItems())==1
        assert len(win.spec_plot.listDataItems())==1
        assert "FFT N=65536" in win.spec_mean.text()
        # Absolute device time is never mistaken for capture-local 0.
        assert "Индекс отсчёта" in win.wave_plot.getAxis("bottom").labelText
    finally:
        if win._live_active:win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_live_original_131072_and_262144_bSpecLines_on_real_qt_widgets(
        tmp_path,qt_app):
    from .test_stage111z26b_live_preview import make_preview,now
    from mvk_compatible.core.native_r6_live_preview import (
        MAX_SAMPLES,load_live_preview,
    )
    from mvk_compatible.desktop.main_window import MainWindow
    root,status,_=make_preview(tmp_path,count=MAX_SAMPLES)
    source=load_live_preview(root,status,now=now())
    win=MainWindow()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(status)
        win._receive_live_preview(source)
        assert "FFT N=65536" in win.spec_mean.text()
        for n,step in ((131072,"0.5"),(262144,"0.25")):
            # Live bSpecLines is now bound to all six ORIGINAL values.
            win.spec_n.setCurrentText(str(n))
            qt_app.processEvents()
            assert f"FFT N={n}" in win.spec_mean.text()
            assert f"шаг {step} Гц" in win.spec_mean.text()
            assert len(win.spec_plot.listDataItems())==1
            line=win.spec_plot.listDataItems()[0]
            assert len(line.xData)<=5000  # display-only peak-preserving reduction
            assert not win.spec_copy_button.isEnabled()
            assert not win.spec_save_button.isEnabled()
        # Changing N back must restore the correct 65536 window, not
        # a cached 262144 plot or the old 8192-point downshift.
        win.spec_n.setCurrentText("65536")
        qt_app.processEvents()
        assert "FFT N=65536" in win.spec_mean.text()
        assert len(win.spec_plot.listDataItems())==1
        assert "1 Гц/лин" in win.spec_lines_button.text()
    finally:
        if win._live_active: win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_real_qt_original_page_adc_hscale_live_signal_length_and_cursor(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    status,preview=_preview(tmp_path)  # Fs=65536, actual 65536 real samples
    win=MainWindow()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(status)
        win._receive_live_preview(preview)
        assert win._wave_hscale_tag==4
        assert "bAdcHScale=1000 мс" in win.wave_hint.text()
        assert "65536 реальных Float32" in win.wave_hint.text()
        assert len(win.wave_plot.listDataItems())==1
        key=(preview.session_id,win._ch(),4,
             win.wave_mode.currentIndex(),preview.channels[win._ch()].rate_hz)
        rx=status["channels"][win._ch()-1]["samples"]
        assert win._source_getsignal_last_processed[key]==rx
        assert win._source_getsignal_last_preview_end[key]==(
            preview.channels[win._ch()].next_index)
        # Even if the verified native transport counter advances,
        # unchanged source preview bytes cannot be marked NEW data.
        native_ch=win._native_live_status["channels"][win._ch()-1]
        native_ch["samples"]+=65536
        win._render_live_wave()
        assert "ожидание следующего окна" in win.wave_hint.text()
        assert len(win.wave_plot.listDataItems())==1
        native_ch["samples"]-=65536
        # A stable Mode2 1-second GetSignal cannot be repainted as
        # NEW data before another full 65536 ADC samples have arrived.
        old_x=win.wave_plot.listDataItems()[0].xData.copy()
        win._render_live_wave()
        assert "ожидание следующего окна" in win.wave_hint.text()
        assert len(win.wave_plot.listDataItems())==1
        assert (win.wave_plot.listDataItems()[0].xData==old_x).all()
        # The original 500ms Tag5 must request exactly 32768 fresh
        # captured samples; a menu selection clears only the local
        # last-processed cursor and recomputes from SAME verified ZIP.
        win._select_original_wave_hscale(5)
        qt_app.processEvents()
        assert "bAdcHScale=500 мс" in win.wave_hint.text()
        assert "32768 реальных Float32" in win.wave_hint.text()
        assert len(win.wave_plot.listDataItems())==1
        assert win._source_getsignal_last_processed[
            (preview.session_id,win._ch(),5,win.wave_mode.currentIndex(),
             preview.channels[win._ch()].rate_hz)]==rx
        # 20s asks 1,310,720 samples at Fs=65536; 262144 native preview
        # cannot provide it. Never show the stale 500ms waveform.
        win._select_original_wave_hscale(0)
        qt_app.processEvents()
        assert not win.wave_plot.listDataItems()
        assert "Ожидание исходного длинного GetSignal" in win.wave_hint.text()
        assert "1310720" in win.wave_hint.text()
        assert win._live_long_window is None  # no invented 20s from 1s preview
        assert "ожидание реальных отсчётов" in win.wave_mean_primary.text()
        # Restore source Tag4 without reopening TCP or applying gain twice.
        win._select_original_wave_hscale(4)
        qt_app.processEvents()
        assert "bAdcHScale=1000 мс" in win.wave_hint.text()
        assert len(win.wave_plot.listDataItems())==1
        # FreezeUpdate suppresses new render even for a Tag change.
        win._source_live_view_frozen=True
        win._select_original_wave_hscale(5)
        assert "bAdcHScale=1000 мс" in win.wave_hint.text()
        win._source_live_view_frozen=False
        win._render_live_wave()
        assert "bAdcHScale=500 мс" in win.wave_hint.text()
    finally:
        if win._live_active:win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_original_measure_mode2_operator_controls_before_and_during_live(qt_app):
    """Real source tool buttons remain clickable without a real TCP socket.

    _Unit128.pas 00846D24: tab reveal precedes TMVKThread creation.
    00847F0D/0084819A: bAdcHScale and bSpecLines stay usable in Mode2.
    The additional research FFT sizes are not original operator choices.
    """
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.mvk_spectrum_menu_runtime_idr_candidate import (
        RESEARCH_FFT_SIZES,
    )
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.spec_n.setCurrentText("1024")
        assert int(win.spec_n.currentData())==1024
        assert win.enter_measurement_mode()
        assert win._measurement_mode_selected and not win._live_active
        assert win.wave_advanced_button.isHidden()
        assert win.spec_advanced_button.isHidden()
        assert int(win.spec_n.currentData())==65536
        assert all(
            not action.isVisible()
            for action in win._spec_lines_actions
            if int(action.data()) in RESEARCH_FFT_SIZES
        )
        # This is the same UI transition used for the authorized Native run.
        # The test does NOT create a socket or transmit instrument commands.
        win._begin_live_capture()
        assert win._live_active
        assert win.wave_hscale_button.isEnabled()
        assert win.wave_filter_button.isEnabled()
        assert win.spec_lines_button.isEnabled()
        hscale=next(
            action for action in win.wave_hscale_menu.actions()
            if int(action.data())==5
        )
        assert hscale.isEnabled()
        hscale.trigger()  # Actual Qt menu action, not a direct Python callback
        assert win._wave_hscale_tag==5
        assert win.wave_seconds.value()==0.5
        fft=next(
            action for action in win._spec_lines_actions
            if int(action.data())==32768
        )
        assert fft.isVisible() and fft.isEnabled()
        fft.trigger()
        assert int(win.spec_n.currentData())==32768
        win._end_live_capture(False)
        # A failed Native run retains Mode2 tabs and source operator-only UI.
        assert win._measurement_mode_selected
        assert win.wave_advanced_button.isHidden()
        assert win.leave_measurement_mode()
        assert not win.wave_advanced_button.isHidden()
        assert not win.spec_advanced_button.isHidden()
        assert all(
            action.isVisible() for action in win._spec_lines_actions
        )
    finally:
        if win._live_active:
            win._end_live_capture(False)
        if win._measurement_mode_selected:
            win.leave_measurement_mode()
        win.close()
        qt_app.processEvents()


def test_qt_getsignal_new_window_survives_source_uint32_rollover(
        tmp_path,qt_app):
    from copy import deepcopy
    from dataclasses import replace
    from mvk_compatible.desktop.main_window import MainWindow
    status,preview=_preview(tmp_path)
    mask=(1<<32)-1
    ch=preview.channels[1]
    n=len(ch.samples)
    before=0xFFFFF000
    after=(before+n)&mask
    s1=deepcopy(status)
    s1["channels"][0]["next_sample_index"]=before
    p1=replace(preview,channels={
        **preview.channels,1:replace(ch,
            first_index=(before-n)&mask,next_index=before,
            captured_samples=s1["channels"][0]["samples"])})
    win=MainWindow()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(s1)
        win._receive_live_preview(p1)
        assert "bAdcHScale=1000 мс" in win.wave_hint.text()
        assert len(win.wave_plot.listDataItems())==1
        s2=deepcopy(s1)
        s2["channels"][0]["samples"]+=n
        s2["channels"][0]["next_sample_index"]=after
        p2=replace(p1,channels={
            **p1.channels,1:replace(p1.channels[1],
                first_index=(after-n)&mask,next_index=after,
                captured_samples=s2["channels"][0]["samples"])})
        win._receive_native_live_status(s2)
        win._receive_live_preview(p2)
        assert "bAdcHScale=1000 мс" in win.wave_hint.text()
        assert "ожидание следующего окна" not in win.wave_hint.text()
        assert len(win.wave_plot.listDataItems())==1
        assert win._source_getsignal_last_preview_end[
            (p2.session_id,1,4,win.wave_mode.currentIndex(),
             p2.channels[1].rate_hz)]==after
        win._render_live_wave()
        assert "ожидание следующего окна" in win.wave_hint.text()
    finally:
        if win._live_active:win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_original_source_2m_storage_is_attached_only_to_verified_live_qt(
        tmp_path,qt_app):
    from .test_stage111z26b_live_preview import make_preview,now
    from mvk_compatible.core.native_r6_live_status import validate_live_status
    from mvk_compatible.core.original_source_ring_receipt import (
        SCHEMA,BUFFER_ELEMENTS,TACH_DOMAIN,
    )
    from mvk_compatible.desktop.main_window import MainWindow
    root,status,_=make_preview(tmp_path)
    # The mock Go Status and original 10-channel ring share one immutable
    # instrument/device cursor and a separate received-local count.
    rows=[]
    for i,ch in enumerate(status["channels"]):
        adc=i<8
        count=ch["samples"] if adc else ch["samples"]*4
        next_index=(100000+ch["samples"])&0xFFFFFFFF
        ch["next_sample_index"]=next_index
        rows.append(dict(channel=i+1,sample_width_bytes=4 if adc else 1,
            rx_pos_64=count,valid_pos_64=0,first_readable_pos_64=0,
            available_elements=count,last_sample_rate_hz=ch["sample_rates_hz"][0],
            next_device_sample_index=next_index,
            input_domain=("CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32" if adc
                          else TACH_DOMAIN),
            sequence_gaps=0,rate_changes=0,rejected_nonfinite_frames=0))
    status["source_original_storage"]=dict(
        schema=SCHEMA,buffer_elements_per_channel=BUFFER_ELEMENTS,
        channels=rows)
    validated=validate_live_status(
        status,expected_run=status["session_id"],now=now())
    assert validated["source_original_storage_verified"]
    win=MainWindow()
    try:
        win._begin_live_capture()
        assert win.original_shell.status_page.property(
            "sourceOriginalTenChannelStorageProof") is None
        win._receive_native_live_status(validated)
        proof=win.original_shell.status_page.property(
            "sourceOriginalTenChannelStorageProof")
        assert proof is not None and len(proof["channels"])==10
        assert proof["channels"][8]["sample_width_bytes"]==1
        # A rejected/stopped capture may not retain any old 2M proof.
        win._invalidate_native_live_status("Live status source rejected")
        assert win.original_shell.status_page.property(
            "sourceOriginalTenChannelStorageProof") is None
    finally:
        if win._live_active:win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_original_long_20s_getsignal_renders_full_source_ring_in_real_qt(
        tmp_path,qt_app):
    """Actual PageAdc widget accepts 1,310,720 real samples, no 262144 N cut."""
    from datetime import datetime,timezone
    from hashlib import sha256
    import numpy as np
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.original_source_long_window import (
        SourceLongWindow,SourceWindowRequest,
    )
    from mvk_compatible.core.native_r6_live_preview import (
        LivePreview,PreviewADC,
    )
    status,_=_preview(tmp_path)
    n=65536*20
    status["channels"][0]["samples"]=n
    status["channels"][0]["frames"]=n//256
    status["channels"][0]["next_sample_index"]=4096
    status["frames_decoded"]=max(status["frames_decoded"],n//256*8)
    status["raw_bytes"]=max(status["raw_bytes"],n*4*8)
    values=np.zeros(n,dtype="<f4")
    req=SourceWindowRequest(status["session_id"],
        "0123456789abcdef0123456789abcdef",1,0,n,n,65536,4096)
    payload=values.tobytes()
    preview=LivePreview(
        status["session_id"],datetime.now(timezone.utc),
        status["raw_bytes"],status["frames_decoded"],
        {1:PreviewADC(1,65536,(4096-n)&0xffffffff,4096,values,
                      sha256(payload).hexdigest(),n)})
    window=MainWindow()
    try:
        window._begin_live_capture()
        window._receive_native_live_status(status)
        window._select_original_wave_hscale(0)
        assert not window.wave_plot.listDataItems()
        window._receive_source_long_window(SourceLongWindow(req,preview))
        assert len(window.wave_plot.listDataItems())==1
        assert "LIVE SOURCE 2M КОЛЬЦО" in window.wave_hint.text()
        assert str(n) in window.wave_hint.text()
        assert window._source_getsignal_last_processed
        key=window._live_long_rendered_key
        window._render_live_wave()  # no 1.3M repeated processing at 50Hz
        assert window._live_long_rendered_key==key
        window._invalidate_native_live_status("Live status source rejected")
        assert window._live_long_window is None
        assert not window.wave_plot.listDataItems()
    finally:
        if window._live_active:window._end_live_capture(False)
        window.close()
        qt_app.processEvents()


def test_original_qt_long_window_request_only_for_selected_page_and_tag(
        tmp_path,qt_app):
    """Qt local IPC never starts a second network stream or changes Fs."""
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.desktop.native_capture_dialog import NativeCaptureDialog
    from .test_stage111z31fj_original_long_window import long_source_status
    from mvk_compatible.core.original_source_long_window import REQUEST_NAME
    root,status=long_source_status(tmp_path)
    window=MainWindow()
    dialog=NativeCaptureDialog(window)
    try:
        window._begin_live_capture()
        dialog._mode="capture"   # simulate already-authorized local Go run
        dialog._capture_root=root
        dialog._poll_source_long_window(status)
        assert not (root/REQUEST_NAME).exists() # initial PageStatus
        tabs=window.original_root_tabs
        adc_page=next(i for i in range(tabs.count())
                      if tabs.tabData(i)=="PageAdc")
        tabs.setCurrentIndex(adc_page)
        window._select_original_wave_hscale(0)
        dialog._poll_source_long_window(status)
        assert (root/REQUEST_NAME).exists()
        request=(root/REQUEST_NAME).read_bytes()
        assert b'"source_h_tag":0' in request
        assert b'"samples":1310720' in request
        before=dialog._source_long_request
        dialog._poll_source_long_window(status)
        assert dialog._source_long_request is before
        # Even after the time throttle expires, an unchanged confirmed
        # source FRxPos cannot cause an expensive 5MiB ZIP retry.
        dialog._source_long_last_capture_end=status[
            "source_original_storage"]["channels"][0]["rx_pos_64"]
        dialog._source_long_last_sent_at=0.0
        dialog._poll_source_long_window(status)
        assert dialog._source_long_request is before
        assert (root/REQUEST_NAME).read_bytes()==request
        # Freeze does not ask the device for new samples.
        window._source_live_view_frozen=True
        dialog._poll_source_long_window(status)
        assert (root/REQUEST_NAME).read_bytes()==request
        window._measurement_exit_requested=True
        dialog._poll_source_long_window(status)
        assert (root/REQUEST_NAME).read_bytes()==request
    finally:
        if window._live_active:window._end_live_capture(False)
        # This test sets _mode="capture" WITHOUT starting any QProcess.
        # Close only the synthetic dialog state; never disable the actual
        # application's operator Stop/confirm modal policy.
        dialog._mode=None
        dialog.close()
        window.close()
        qt_app.processEvents()


def test_original_qt_freeze_sends_local_go_gate_without_device_tx(
        tmp_path,qt_app):
    """Original bFreezeUpdate toggles source storage, not instrument writes."""
    from PySide6.QtCore import QProcess
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.desktop.native_capture_dialog import NativeCaptureDialog

    class LocalProcess:
        writes=[]
        def state(self):return QProcess.Running
        def write(self,data):
            self.writes.append(bytes(data))
            return len(data)

    win=MainWindow()
    dlg=NativeCaptureDialog(win)
    original_process=dlg._process
    mock=LocalProcess()
    try:
        win._begin_live_capture()
        win._native_dialog=dlg
        dlg._mode="capture"
        dlg._capture_root=tmp_path
        dlg._process=mock
        assert dlg.source_freeze_control_active()
        assert not dlg.source_rate_tx_active()
        controls=win.original_shell.measure_controls
        controls.freeze.click()
        assert win._source_live_view_frozen
        assert mock.writes[-1].splitlines()==[b"FREEZE 1"] and mock.writes[-1].endswith(bytes((10,)))
        assert not dlg.source_rate_tx_active()
        controls.freeze.click()
        assert not win._source_live_view_frozen
        assert mock.writes[-1].splitlines()==[b"FREEZE 0"] and mock.writes[-1].endswith(bytes((10,)))
        assert len(mock.writes)==2
    finally:
        dlg._mode=None
        dlg._process=original_process
        win._native_dialog=None
        if win._live_active:win._end_live_capture(False)
        dlg.close()
        win.close()
        qt_app.processEvents()
