"""Operator workflows with synthetic calibrated acceleration, no TACH/network."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")


@pytest.fixture
def gui():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    from mvk_live_standalone.app import LiveWindow
    app=QApplication.instance() or QApplication([])
    w=LiveWindow()
    yield w,app
    w.close()
    w.deleteLater()
    app.processEvents()


def feed(window, samples, *, fs=8192, end=None):
    from mvk_live_standalone.live_ipc import IPCPreview,IPCChannel,DOMAIN
    x=np.asarray(samples,dtype="<f4")
    if end is None:end=len(x)
    c=IPCChannel(1,fs,x,end%(1<<32),end,
                 hashlib.sha256(x.tobytes()).hexdigest())
    view=IPCPreview("SYNTHETIC_OFFLINE_TEST",DOMAIN,True,
                    datetime.now(timezone.utc),{1:c})
    window._gui_ring.ingest_preview(view)
    window._preview=view
    return view


def _wait(view,app):
    for _ in range(10):
        future=view._future
        if future is not None:
            try:future.result(timeout=20)
            except ValueError:pass
        view._collect_analysis()
        app.processEvents()
        if view._future is None:return


def test_manual_or_velocity_1x_requires_operator_acceptance(gui):
    w,app=gui
    fs=8192
    t=np.arange(32768)/fs
    vel=(.002*np.sin(2*np.pi*25*t)+.004*np.sin(2*np.pi*50*t))
    feed(w,np.gradient(vel,1/fs))
    assert w.rpm.value()==0
    w._propose_rotation()
    assert w._speed_future is not None
    w._speed_future.result(timeout=10)
    w._poll_extra()
    assert w.rpm.value()==0
    assert w._speed_candidate is not None
    assert w.rpm_accept.isEnabled()
    w._accept_rotation()
    assert w.rpm.value()==pytest.approx(1500,abs=12)
    assert "ВС" in w.rotation_info.text()
    assert w._rpm_source=="VELOCITY_FFT_OPERATOR_ACCEPTED"
    assert w._marker_lines
    w.rpm.setValue(1800)
    assert w._rpm_source=="MANUAL"
    assert not w.rpm_accept.isEnabled()


def test_freeze_retains_old_data_as_native_receiver_continues(gui):
    w,app=gui
    initial=np.arange(65536,dtype="<f4")
    feed(w,initial)
    w.freeze.setChecked(True)
    w._toggle_freeze(True)
    before,rate,stamp=w._current_window(8192)
    assert rate==8192 and stamp[0]=="FROZEN"
    assert before[-1]==65535
    w.history.setValue(1.0)
    earlier,rate,stamp=w._current_window(8192)
    assert earlier[-1]==65535-8192
    feed(w,np.arange(8192,73728,dtype="<f4"),end=73728)
    retained,_,_=w._current_window(8192)
    np.testing.assert_array_equal(retained,earlier)
    assert w._gui_ring.channel(1).end==73728
    w.freeze.setChecked(False)
    w._toggle_freeze(False)
    current,rate,stamp=w._current_window(8192)
    assert current[-1]==73727
    assert stamp[0]=="SYNTHETIC_OFFLINE_TEST"
    w.timebase.setCurrentIndex(0)
    w._render_wave()
    xs,ys=w.wave_curve.getData()
    assert len(xs)>0 and xs[0]>=-.11


def test_save_reopen_npz_and_export_vibration_csv(gui,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    w,app=gui
    t=np.arange(32768)/8192
    feed(w,np.sqrt(2)*np.sin(2*np.pi*128*t))
    npz=tmp_path/"record.npz"
    monkeypatch.setattr(QFileDialog,"getSaveFileName",
                        lambda *args,**kwargs:(str(npz),"MVK Live (*.npz)"))
    w._save_snapshot()
    assert npz.is_file()
    monkeypatch.setattr(QFileDialog,"getOpenFileName",
                        lambda *args,**kwargs:(str(npz),"MVK Live (*.npz)"))
    w._open_snapshot()
    assert w._gui_ring.session_id.startswith("OFFLINE_")
    assert w._capture_root is None
    assert "OFFLINE" in w.status.text()
    w._request_update()
    _wait(w,app)
    assert w._spectrum is not None
    csv_path=tmp_path/"measurement.csv"
    monkeypatch.setattr(QFileDialog,"getSaveFileName",
                        lambda *args,**kwargs:(str(csv_path),"CSV (*.csv)"))
    w._export_csv()
    assert csv_path.is_file()
    assert "APP_DERIVED" in csv_path.read_text("utf-8-sig")
    assert "дБ" not in w.status.text() or "CSV" in w.status.text()


def test_stft_view_from_selected_real_buffer(gui):
    w,app=gui
    t=np.arange(8192)/8192
    feed(w,np.sin(2*np.pi*500*t))
    w._calculate_extra()
    assert w._extra_future is not None
    w._extra_future.result(timeout=15)
    w._poll_extra()
    assert w._extra_future is None
    assert w.extra_button.isEnabled()
    assert w.views.currentWidget()==w.extra_panel
    assert w.extra_pages.currentWidget()==w.extra_plot
    assert "STFT" in w.extra_plot.getPlotItem().titleLabel.text



def test_small_fft_ipc_starts_without_waiting_65536_samples(gui):
    from mvk_live_standalone.live_ipc import IPCNotReady
    w,app=gui
    seen=[]
    class FakeIPC:
        session_id="SYNTHETIC_OFFLINE_TEST"
        def read_channel(self,adc,count):
            seen.append((adc,count))
            raise IPCNotReady("only expected sample window")
    w._ipc_client=FakeIPC()
    w._last_status={"phase":"RECORDING","source_tcp_multi_socket":False}
    w.nfft.setCurrentIndex(0)  # 8192
    w._poll_ipc()
    assert w._ipc_future is not None
    with pytest.raises(IPCNotReady):
        w._ipc_future.result(timeout=10)
    assert seen==[(1,8192)]
