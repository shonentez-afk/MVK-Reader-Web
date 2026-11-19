"""True Qt regression: selected FIR must never display unfiltered LIVE FFT.

The private original IDP/coefficients are not bundled or used in CI.
Inject a synthetic profile ONLY to exercise the GUI safety gate; this
does not constitute a substitute filter or original FIR numeric proof.
"""
from __future__ import annotations
import numpy as np
import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z31db_qt_live_view_gate import _pair
from mvk_compatible.core.envelope_idr_candidate import EnvelopeProfile


def test_live_source_fir_code_does_not_render_plain_getsignal_or_getspectrum(
        qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        status,preview=_pair(tmp_path)
        win._receive_native_live_status(status)
        win._receive_live_preview(preview)
        assert win.wave_plot.listDataItems()
        assert win.spec_plot.listDataItems()

        # The operator could have independently selected a verified
        # private IDP. A synthetic profile only simulates its availability.
        # Source-matched FIR history/FFT is NOT a result of loading it.
        win.set_envelope_profile(EnvelopeProfile(
            np.zeros((10,512),dtype="<f4"),provenance="QT_TEST_ONLY"))
        idx=win.wave_envelope_code.findData(20)
        assert idx>=0
        win.wave_envelope_code.setCurrentIndex(idx)
        qt_app.processEvents()
        assert not win.wave_plot.listDataItems()
        assert "Огибающая Code20" in win.wave_hint.text()
        assert "Обычный сигнал не подменяет" in win.wave_hint.text()
        assert win.spec_envelope_code.currentData()==20

        # With the corresponding spectrum filter explicitly active,
        # the ordinary Go bSpecLines FFT must be blanked, NOT relabelled
        # as the filtered spectral envelope.
        win.spec_envelope_button.setChecked(True)
        win._render_live_spectrum()
        qt_app.processEvents()
        assert not win.spec_plot.listDataItems()
        assert "Огибающая Code20" in win.spec_hint.text()
        assert "не подменяет огибающую" in win.spec_hint.text()
        # This synthetic Qt profile must not masquerade as the
        # SHA-verified original IDP that can authorize a local candidate.
        assert "LOCAL_ORIGINAL_FIR_PROFILE_REQUIRED" in win.spec_hint.text()
        assert win._full_spectrum is None
        assert win._spectrum_summary is None
        assert not win.spec_copy_button.isEnabled()
        assert not win.spec_save_button.isEnabled()

        # Returning to Tag0 restores the prior honest unfiltered
        # candidate, but never turns an excluded Freeze packet into a
        # source-proven ring or an unverified filtered result.
        win.spec_envelope_button.setChecked(False)
        win.wave_envelope_code.setCurrentIndex(
            win.wave_envelope_code.findData(0))
        win._render_live_spectrum()
        assert win.spec_plot.listDataItems()
        assert "FFT локальный" in win.spec_mean.text()
        assert not win.spec_envelope_button.isChecked()
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_live_filter_selection_without_profile_cannot_be_silent(
        qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        status,preview=_pair(tmp_path)
        win._receive_native_live_status(status)
        win._receive_live_preview(preview)
        assert win.spec_plot.listDataItems()
        assert win.envelope_profile is None
        # Existing explicit operator selector cannot silently enable FIR
        # without loading a local original IDP; unfiltered mode remains.
        win._toggle_spec_envelope(True)
        assert not win.spec_envelope_button.isChecked()
        assert win.spec_plot.listDataItems()
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
