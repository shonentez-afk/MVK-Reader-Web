"""Actual Qt source Mode2 panel + PageStatus 10-channel quality + DFM DPI."""
import pytest
pytest.importorskip("PySide6")

from .test_desktop_qt import qt_app
from .test_stage111z31cr_connected_core import source_test_transport
from .test_stage111z31cs_qt_measurement_mode import _capture_source_mode2
from ..core.original_connected_status import UNKNOWN
from ..core.original_mode2_live_health import SOURCE_CHANNEL_KINDS


def _ten_channels():
    return [
        {"channel":number,"type":kind,"sequence_discontinuities":0,
         "nonfinite_samples":0}
        for number,kind in enumerate(SOURCE_CHANNEL_KINDS,1)]


def test_source_96dpi_panel_live_status_silence_and_ten_channels(qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        assert win.enter_measurement_mode()
        qt_app.processEvents()
        panel=win.original_measure_controls
        geom=panel.panel.property("sourceOriginalDfmDpiReceipt")
        assert geom["dfm_pixels_per_inch"]==96
        assert geom["panel_logical_height"]==53
        assert panel.panel.height()==53
        assert geom["qt_layout_must_not_apply_second_scale"]
        assert geom["button_logical_rects"][0]=={
            "name":"bFreezeUpdate","rect":[6,0,160,41]}
        assert geom["qt_device_pixel_ratio"]==pytest.approx(
            panel.panel.devicePixelRatioF())
        win._begin_live_capture()
        good=source_test_transport(frames=200)
        good.update({"seconds_since_last_packet":0.1,
                     "invalid_frames":0,"channels":_ten_channels()})
        win._receive_native_live_status(good)
        qt_app.processEvents()
        assert panel.status.text()=="Подключен к прибору"
        assert panel.indicator.isVisible()
        assert not panel.bad_indicator.isVisible()
        assert win.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        receipt=win.original_shell.status_page.property(
            "sourceNativeLiveQualityReceipt")
        assert receipt["native_channels_observed"]==10
        assert receipt["original_device_system_fields_proven"]==0
        assert win.original_shell.status_table.item(0,1).text()==UNKNOWN
        win.original_visual_skin.reveal_page(2)
        qt_app.processEvents()
        _capture_source_mode2(win,"15_cv_native_8adc_2tach_readonly_healthy")
        # Healthy JSON timestamp does not make an old packet live.
        silent=good|{"seconds_since_last_packet":5.1}
        win._receive_native_live_status(silent)
        qt_app.processEvents()
        assert panel.status.text()=="Нет новых данных прибора"
        assert panel.bad_indicator.isVisible()
        assert not panel.indicator.isVisible()
        assert not win.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        _capture_source_mode2(win,"16_cv_no_new_instrument_packets_red")
        # Source 15-mode tab change must keep same 8+2 evidence and no
        # recycled DSP fields from the previous good/offline session.
        win.original_status_mode.setCurrentIndex(5)
        qt_app.processEvents()
        receipt=win.original_shell.status_page.property(
            "sourceNativeLiveQualityReceipt")
        assert receipt["native_stream_silent"]
        assert receipt["native_channels_observed"]==10
        win._receive_native_live_status(good|{
            "seconds_since_last_packet":0.2,
            "invalid_frames":3})
        qt_app.processEvents()
        assert panel.status.text()=="Ошибки входного потока"
        assert panel.bad_indicator.isVisible()
        assert win.measurement_connection_display().phase=="STREAM_ERRORS"
        # This status was pushed WHILE source mode 5, without revisiting
        # the first PageStatus tab. Its receipt must update on the spot.
        updated=win.original_shell.status_page.property(
            "sourceNativeLiveQualityReceipt")
        assert updated["native_invalid_frames"]==3
        assert updated["native_data_integrity_alert"]
        _capture_source_mode2(win,"17_cv_invalid_frames_red")
        win._invalidate_native_live_status("Native status source rejected")
        qt_app.processEvents()
        cleared=win.original_shell.status_page.property(
            "sourceNativeLiveQualityReceipt")
        assert cleared["native_channels_observed"]==0
        assert cleared["original_device_system_fields_proven"]==0
        win._end_live_capture(False)
        qt_app.processEvents()
        assert win._measurement_mode_selected
        assert not win._live_active
        assert panel.bad_indicator.isVisible()
    finally:
        win.close()
        qt_app.processEvents()
