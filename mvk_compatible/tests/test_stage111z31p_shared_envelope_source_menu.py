"""Stage111Z31P: explicit original spectrum-envelope menu provenance.

Private IDR _Unit128:0084587D..0084594B creates exactly 32 menu tags
0..31. _Unit128:0084B274 applies a selected tag to BOTH ADC and
Spectrum; 00846AB4 invalidates both old series and 00847248 updates
the active page. These tests use synthetic offline data only.

Original Win32 full envelope numeric output is NOT asserted or faked.
"""
import pytest

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile


def test_original_shared_menu_tag_from_either_pane_without_recursion(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    try:
        win.set_envelope_profile(fake_profile())
        # Source Tag0 is preserved on IDP load; explicit selection from
        # either independent research combo mirrors the other Tag.
        assert win.wave_envelope_code.currentData()==0
        assert win.spec_envelope_code.currentData()==0
        for selected in (1, 7, 20, 31, 0):
            win.wave_envelope_code.setCurrentIndex(selected)
            assert win.wave_envelope_code.currentData()==selected
            assert win.spec_envelope_code.currentData()==selected
        for selected in (31, 20, 8, 0):
            win.spec_envelope_code.setCurrentIndex(selected)
            assert win.spec_envelope_code.currentData()==selected
            assert win.wave_envelope_code.currentData()==selected
        assert not win.spec_envelope_button.isChecked()
        assert win.session is None
    finally:
        win.close()
        qt_app.processEvents()


def test_spec_menu_tag_zero_returns_to_plain_fft_without_stale_fir(
        tmp_path, qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    try:
        win.open_archive(fixture_zip(tmp_path))
        win.show()
        win.tabs.setCurrentIndex(2)
        qt_app.processEvents()
        win.set_envelope_profile(fake_profile())
        assert win.spec_envelope_code.currentData()==0
        win.spec_envelope_code.setCurrentIndex(20)
        win.spec_envelope_button.setChecked(True)
        qt_app.processEvents()
        assert win.spec_envelope_button.isChecked()
        assert win._full_spectrum['source']==(
            'APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE')
        assert win.spec_copy_button.isEnabled()
        win.spec_envelope_code.setCurrentIndex(0)
        qt_app.processEvents()
        assert win.wave_envelope_code.currentData()==0
        assert not win.spec_envelope_button.isChecked()
        assert win._full_spectrum['source']==(
            'APP_DERIVED_FFT_MVKVIEW_CANDIDATE')
        assert len(win.spec_plot.listDataItems())==1
        assert win._spectrum_summary is not None
        assert win._archive_raw_line is not None
        assert win.spec_copy_button.isEnabled()
    finally:
        win.close()
        qt_app.processEvents()


def test_insufficient_original_fir_history_rejects_and_shows_plain_fft(
        tmp_path, qt_app, monkeypatch):
    from mvk_compatible.desktop import main_window
    from mvk_compatible.desktop.main_window import MainWindow
    original=main_window.required_original_history

    def fail_only_new_code(n_fft, fs, code):
        if code==31:
            return {'input_samples':10**12}
        return original(n_fft,fs,code)

    win=MainWindow()
    try:
        win.open_archive(fixture_zip(tmp_path))
        win.show()
        win.tabs.setCurrentIndex(2)
        qt_app.processEvents()
        win.set_envelope_profile(fake_profile())
        win.spec_envelope_code.setCurrentIndex(20)
        win.spec_envelope_button.setChecked(True)
        assert win._full_spectrum['source']==(
            'APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE')
        monkeypatch.setattr(main_window,'required_original_history',fail_only_new_code)
        win.spec_envelope_code.setCurrentIndex(31)
        qt_app.processEvents()
        assert win.wave_envelope_code.currentData()==31
        assert not win.spec_envelope_button.isChecked()
        assert win._full_spectrum is not None
        assert win._full_spectrum['source']==(
            'APP_DERIVED_FFT_MVKVIEW_CANDIDATE')
        assert win._spectrum_summary is not None
        assert len(win.spec_plot.listDataItems())==1
        assert 'недостаточно исходной истории' in win.statusBar().currentMessage()
    finally:
        win.close()
        qt_app.processEvents()
