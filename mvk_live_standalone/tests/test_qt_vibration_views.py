"""Full synthetic verified-stream Qt roundtrip, never touches industrial TCP."""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    inst=QApplication.instance() or QApplication([])
    inst.setQuitOnLastWindowClosed(False)
    return inst


def fake_preview(x,fs=8192,n=1,end=None):
    from mvk_live_standalone.live_ipc import IPCPreview,IPCChannel,DOMAIN
    samples=np.asarray(x,dtype="<f4")
    if end is None:end=len(samples)
    channel=IPCChannel(n,fs,samples,end%(1<<32),end,
                       hashlib.sha256(samples.tobytes()).hexdigest())
    return IPCPreview("TEST_SINE_SESSION",DOMAIN,True,
                      datetime.now(timezone.utc),{n:channel})


def _complete(window,app):
    for _ in range(20):
        if window._future is not None:
            window._future.result(timeout=6)
            window._collect_analysis()
        app.processEvents()
        if window._spectrum is not None and window._future is None:
            break


def test_all_derived_views_and_waterfall_with_real_synthetic_samples(app):
    from mvk_live_standalone.app import LiveWindow
    fs=8192
    t=np.arange(65536)/fs
    x=np.sqrt(2)*2*np.sin(2*np.pi*128*t)
    widget=LiveWindow()
    try:
        p=fake_preview(x)
        assert widget._gui_ring.ingest_preview(p)=={1}
        widget._preview=p
        widget.nfft.setCurrentIndex(0)  # n=8192
        widget._request_update()
        _complete(widget,app)
        assert widget._spectrum is not None
        assert widget._spectrum.mode=="fft"
        assert widget._spectrum.peak[0]==pytest.approx(128,abs=0.1)
        assert len(widget._waterfall_rows)>=1

        widget.analysis.setCurrentIndex(1)
        _complete(widget,app)
        assert widget._spectrum is not None
        assert widget._spectrum.mode=="welch"
        assert "Гц" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()

        widget.analysis.setCurrentIndex(widget.analysis.findData("third_octave"))
        _complete(widget,app)
        assert widget._spectrum is not None
        assert widget._spectrum.mode=="third_octave"
        assert "октавы" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()

        widget.yscale.setCurrentIndex(1)
        assert "дБ" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()
        widget.kind.setCurrentIndex(1)
        _complete(widget,app)
        assert widget._spectrum.kind=="velocity"
        assert "мм/с" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()

        widget.rpm.setValue(1800)
        assert widget._marker_lines
        widget.rpm.setValue(0)
        assert not widget._marker_lines
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


def test_no_unsupported_envelope_in_velocity_mode_and_manual_source_label(app):
    from mvk_live_standalone.app import LiveWindow
    fs=8192
    t=np.arange(65536)/fs
    x=(1+0.5*np.sin(2*np.pi*50*t))*np.sin(2*np.pi*2048*t)
    widget=LiveWindow()
    try:
        preview=fake_preview(x)
        widget._gui_ring.ingest_preview(preview)
        widget._preview=preview
        widget.nfft.setCurrentIndex(0)
        widget.analysis.setCurrentIndex(widget.analysis.findData("envelope"))
        _complete(widget,app)
        assert widget._spectrum is not None and widget._spectrum.mode=="envelope"
        assert widget._spectrum.peak[0]==pytest.approx(50,abs=1)
        # An unsupported programmatic choice must revert to acceleration;
        # the real envelope already computed remains a valid VU result.
        assert not widget.kind.isEnabled()
        widget.kind.setCurrentIndex(widget.kind.findData("velocity"))
        assert widget.kind.currentData()=="acceleration"
        assert widget._spectrum is not None
        assert widget._spectrum.kind=="acceleration"
        assert widget._spectrum.mode=="envelope"
        assert widget._spectrum.peak[0]==pytest.approx(50,abs=1)
        widget.analysis.setCurrentIndex(widget.analysis.findData("fft"))
        assert widget.kind.isEnabled()
        widget.rpm.setValue(1500)
        assert widget._marker_lines
    finally:
        widget.close()
