"""Mode2 channel selectors preserve the eight-channel offline contract."""
import pytest
pytest.importorskip("PySide6")
from .test_desktop_qt import qt_app
from ..desktop.main_window import MainWindow

def test_live_10_channel_tabs_and_byte_only_controls(qt_app):
    w=MainWindow()
    w.show();qt_app.processEvents()
    try:
        assert w.adc.count()==8
        w._begin_live_capture()
        assert w.adc.count()==w.wave_channel_tabs.count()==w.spec_channel_tabs.count()==10
        w.wave_channel_tabs.setCurrentIndex(8)
        qt_app.processEvents()
        assert w._ch()==9 and w.spec_channel_tabs.currentIndex()==8
        assert w.wave_mode.currentIndex()==1
        assert not w.wave_type_button.isEnabled()
        assert not w.wave_filter_button.isEnabled()
        assert not w.spec_envelope_button.isEnabled()
        assert not w.spec_envelope_button.isChecked()
        w.spec_channel_tabs.setCurrentIndex(9)
        qt_app.processEvents()
        assert w._ch()==10 and w.wave_channel_tabs.currentIndex()==9
        w.wave_channel_tabs.setCurrentIndex(0)
        qt_app.processEvents()
        assert w._ch()==1 and w.wave_type_button.isEnabled()
        assert w.wave_filter_button.isEnabled()
        w._end_live_capture(False)
        assert w.adc.count()==w.wave_channel_tabs.count()==w.spec_channel_tabs.count()==8
    finally:
        if w._live_active: w._end_live_capture(False)
        w.close();qt_app.processEvents()
