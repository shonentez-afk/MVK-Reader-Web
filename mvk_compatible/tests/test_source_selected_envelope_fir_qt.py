"""Real Windows Qt path for original PRE-FIR bSpecLines -> post-IQ FFT.

The synthetic data and fake IDP availability are TEST DOUBLES ONLY.
Real Qt production availability requires a user-selected SHA-verified
private mvkview.idp and the Go-validated SHA source ring; no coefficient
or private source is published here. Original Delphi numerical 1:1 false.
"""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import numpy as np
import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z31db_qt_live_view_gate import _pair
from mvk_compatible.core.envelope_idr_candidate import EnvelopeProfile
from mvk_compatible.core.native_r6_live_preview import (
    LivePreview,PreviewADC,
)
from mvk_compatible.core.original_source_long_window import (
    SourceWindowRequest,SourceLongWindow,
)


def _qa_idp_double():
    banks=np.zeros((10,512),dtype="<f4")
    banks[4,0]=1.
    banks[4,1]=0.4
    # This is a deliberately labeled TEST DOUBLE for the already tested
    # IDP filename/hash loader. It never constitutes real FIR provenance.
    return EnvelopeProfile(
        banks,provenance="USER_SUPPLIED_LOCAL_IDP_SHA256_VERIFIED")


def test_qt_live_fir_iq_from_exact_2m_source_ring_not_plain_fft(qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        status,normal=_pair(tmp_path)
        win._receive_native_live_status(status)
        win._receive_live_preview(normal)
        assert win.spec_plot.listDataItems()
        win.set_envelope_profile(_qa_idp_double())
        selected=win.spec_n.findData(4096)
        assert selected>=0
        win.spec_n.setCurrentIndex(selected)
        for combo in (win.wave_envelope_code,win.spec_envelope_code):
            index=combo.findData(20)
            assert index>=0
            signals=combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(signals)
        win.spec_envelope_button.setChecked(True)
        # Source ring/accepted ADC proof is normally checked in
        # native_r6_live_status. This synthetic widget test injects
        # the already authenticated state without a network socket.
        ring_count=65536
        ring=({**status,
            "source_original_storage_verified":True,
            "source_original_storage":{"channels":[
                {"last_sample_rate_hz":65536,
                 "available_elements":ring_count} for _ in range(10)]},
        })
        win._native_live_status=ring
        win._live_fft_window=None
        win._render_live_spectrum()
        assert not win.spec_plot.listDataItems()
        assert "Ожидание" in win.spec_hint.text()
        n=4147
        data=np.asarray(
            0.5*np.sin(np.arange(n)*2*np.pi*300/65536)
            +0.1*np.cos(np.arange(n)*2*np.pi*1500/65536),
            dtype="<f4")
        raw=data.tobytes()
        ch=PreviewADC(1,65536,(ring_count-n)&0xffffffff,
                      ring_count,data,hashlib.sha256(raw).hexdigest(),
                      ring_count)
        selected_window=LivePreview(
            status["session_id"],datetime.now(timezone.utc),
            status["raw_bytes"],status["frames_decoded"],
            {1:ch},source_ring_provenance_verified=True)
        req=SourceWindowRequest(
            status["session_id"],"f0"*16,1,-2,n,ring_count,65536,
            ring_count,20,4096)
        win._live_fft_window=SourceLongWindow(req,selected_window)
        win._render_live_spectrum()
        assert win.spec_plot.listDataItems()
        assert "FIR Code20" in win.spec_mean.text()
        assert "FFT 2048" in win.spec_mean.text()
        assert "16" in win.spec_mean.text()
        assert "локальный FIR/IQ" in win.spec_mean_primary.text()
        assert "FRange=1" in win.spec_hint.text()
        assert win._full_spectrum is None
        assert not win.spec_copy_button.isEnabled()
        assert not win.spec_save_button.isEnabled()
        # A stale response tagged for the wrong filter can NOT be
        # re-used after menu switch, even with an intact source SHA.
        win.spec_envelope_code.setCurrentIndex(
            win.spec_envelope_code.findData(26))
        win._render_live_spectrum()
        assert not win.spec_plot.listDataItems()
        assert "Ожидание" in win.spec_hint.text() or (
            "недоступен" in win.spec_hint.text())
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
