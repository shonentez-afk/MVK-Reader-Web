"""Modern main-window, axes and filter QA without hardware TCP.

Synthetic test signals are never injected into the production receiver:
only the isolated verified Float32 test ring is exercised here.
"""
from __future__ import annotations
import hashlib
import math
import os
from datetime import datetime, timezone

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def widget():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    from mvk_live_standalone.app import LiveWindow
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = LiveWindow()
    yield window, app
    window.close()
    window.deleteLater()
    app.processEvents()


def _feed(w, fs=8192, n=32768):
    from mvk_live_standalone.live_ipc import IPCPreview, IPCChannel, DOMAIN
    t = np.arange(n, dtype=np.float64)/fs
    x = np.asarray(np.sqrt(2)*np.sin(2*np.pi*100*t), dtype="<f4")
    ch = IPCChannel(1, fs, x, n % (1 << 32), n,
                    hashlib.sha256(x.tobytes()).hexdigest())
    preview = IPCPreview("TEST_MODERN", DOMAIN, True,
                         datetime.now(timezone.utc), {1: ch})
    w._gui_ring.ingest_preview(preview)
    w._preview = preview
    return x


def test_main_has_one_global_adc_four_tabs_and_eight_working_menus(widget):
    w,_ = widget
    assert w._modern_installed
    assert [w.views.tabText(i) for i in range(w.views.count())] == [
        "Обзор", "Спектр", "Временной сигнал", "Расчётные данные"]
    assert w.views.currentWidget() == w.overview_page
    assert w.adc.count() == 8
    assert w.dsp_adc.isHidden() and w.extra_adc.isHidden()
    assert [a.text() for a in w.menuBar().actions()] == [
            "Файл", "Измерение", "Анализ", "Диагностика",
            "Архив", "Вид", "Настройки", "Справка"]
    assert w._native.state() == w._native.ProcessState.NotRunning
    assert w._capture_root is None


def test_operator_labels_describe_real_quantities_not_x_y(widget):
    """Ordinary measurement controls must name physical quantities, not axes."""
    import re
    from PySide6 import QtWidgets
    w, _ = widget
    inspector_labels = [item.text() for item in
                        w._modern_inspector.findChildren(QtWidgets.QLabel)]
    for required in (
        "Амплитуда · линейно / дБ",
        "Частота · линейно / логарифмически",
        "Частотный диапазон до, Гц", "Развёртка времени",
        "Масштаб виброускорения", "Тип фильтра",
    ):
        assert required in inspector_labels
    assert not any(re.search(r"(?<![A-Za-zА-Яа-я])[XY](?![A-Za-zА-Яа-я])", label)
                   for label in inspector_labels)
    assert [w.xscale.itemText(i) for i in range(w.xscale.count())] == [
        "Линейная", "Логарифмическая"]
    assert [w.yscale.itemText(i) for i in range(w.yscale.count())] == [
        "Линейная", "В децибелах (дБ)"]
    assert "время в мс/с" in w.wave_info.text()
    assert "X" not in w.operator_info.text()


def test_spectrum_and_overview_render_the_same_real_source(widget):
    w,_ = widget
    from mvk_live_standalone.vibration import analyze_vibration
    data = _feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.kind.setCurrentIndex(w.kind.findData("acceleration"))
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    w._spectrum = analyze_vibration(data, 8192,
                  kind="acceleration",mode="fft",nfft=8192)
    w._render_spectrum()
    sx,sy = w.spec_curve.getData()
    ox,oy = w.overview_spec_curve.getData()
    np.testing.assert_allclose(sx,ox)
    np.testing.assert_allclose(sy,oy)
    assert len(ox)>20
    assert w._spectrum.peak[0] == pytest.approx(100, abs=1)
    w._render_wave()
    tx,ty = w.wave_curve.getData()
    ux,uy = w.overview_wave_curve.getData()
    np.testing.assert_allclose(tx,ux)
    np.testing.assert_allclose(ty,uy)


def test_manual_axes_survive_another_verified_fft_frame(widget):
    w,_ = widget
    from mvk_live_standalone.vibration import analyze_vibration
    data = _feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    w._spectrum = analyze_vibration(
        data,8192,mode="fft",nfft=8192)
    w._render_spectrum()
    w._manual_spec_axes=(10.0,200.0,0.0,3.0)
    w._render_spectrum()
    assert w.spec.viewRange()[0] == pytest.approx([10,200],abs=1e-4)
    assert w.overview_spec.viewRange()[0] == pytest.approx([10,200],abs=1e-4)
    w._spectrum = analyze_vibration(
        data*0.5,8192,mode="fft",nfft=8192)
    w._render_spectrum()
    assert w.spec.viewRange()[0] == pytest.approx([10,200],abs=1e-4)
    assert w.spec.viewRange()[1] == pytest.approx([0,3],abs=1e-4)
    w._reset_spectrum_axis()
    assert w._manual_spec_axes is None
    assert w.spec.viewRange()[0][0] == pytest.approx(0,abs=1e-4)


def test_logarithmic_frequency_axis_has_no_zero_and_physical_cursor(widget):
    w,_=widget
    from mvk_live_standalone.vibration import analyze_vibration
    data = _feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    w._spectrum = analyze_vibration(data,8192,mode="fft",nfft=8192)
    w.xscale.setCurrentIndex(w.xscale.findData("log"))
    w._render_spectrum()
    low,high = w.spec.viewRange()[0]
    assert math.isfinite(low) and math.isfinite(high)
    assert low == pytest.approx(0,abs=1e-3)  # log10(8192/8192)=0
    assert high == pytest.approx(3,abs=1e-3)  # log10(1000 Hz)=3
    w.cursor.setValue(math.log10(100))
    w._cursor_text()
    assert "100" in w._professional_cursors.spec_readout.text()
    # This dB mode is a numeric Y ordinate; a second log Y is invalid.
    w.yscale.setCurrentIndex(w.yscale.findData("db"))
    assert "дБ" in w.spec.getPlotItem().getAxis("left").label.toPlainText()


def test_filter_preview_is_two_pass_and_has_no_device_side_effects():
    from mvk_live_standalone.graph_policies import (
        filter_magnitude_response, spectrum_x_limits)
    hz, response=filter_magnitude_response(8192,band_hz=(150,400))
    assert len(hz)==512 and len(response)==512
    assert float(np.interp(250,hz,response))> -7
    assert float(np.interp(25,hz,response))< -30
    z,a=filter_magnitude_response(8192)
    assert np.array_equal(z,hz)
    assert np.all(a==0.0)
    with pytest.raises(ValueError):
        filter_magnitude_response(512,band_hz=(100,300))
    with pytest.raises(ValueError):
        spectrum_x_limits(512,8192,0.0,log_x=True)


def test_detached_method_windows_are_not_extra_main_tabs(widget):
    w,_=widget
    from mvk_live_standalone.modern_shell import open_advanced_window
    stft=open_advanced_window(w,"stft")
    again=open_advanced_window(w,"stft")
    kurt=open_advanced_window(w,"kurtogram")
    assert stft is again
    assert stft is not kurt
    assert stft.centralWidget() is w.extra_method_pages["stft"]
    assert kurt.centralWidget() is w.kurtogram_page
    assert len(w._modern_windows)==2
    assert w.views.count()==4
    assert w._native.state()==w._native.ProcessState.NotRunning


def test_original_four_views_are_presets_not_forced_x_or_psd_modes(widget):
    w,_=widget
    w.analysis.setCurrentIndex(w.analysis.findData("welch"))
    w.xscale.setCurrentIndex(w.xscale.findData("log"))
    w.spectrum_view.setCurrentIndex(w.spectrum_view.findData("linear_vs"))
    assert w.kind.currentData()=="velocity"
    assert w.yscale.currentData()=="linear"
    assert w.xscale.currentData()=="log"
    assert w.analysis.currentData()=="welch"
    assert "мм/с" in w.y_height_choice.itemText(1)
    assert not w.y_height_choice.isEnabled()  # PSD has power density units
    w.analysis.setCurrentIndex(w.analysis.findData("fft"))
    assert w.y_height_choice.isEnabled()


def test_standalone_stft_is_pinned_and_survives_main_adc_switch(widget):
    w,_=widget
    from mvk_live_standalone.modern_shell import open_advanced_window
    _feed(w)
    child=open_advanced_window(w,"stft")
    pin=w._modern_method_pins["stft"]
    assert pin["adc"]==1 and pin["fs"]==8192
    assert not pin["samples"].flags.writeable
    assert len(pin["samples"])==8192
    w.adc.setCurrentIndex(1)  # ADC 2 has no samples
    assert pin["adc"]==1
    w._start_extra_mode("stft")
    assert w._extra_future is not None
    w._extra_future.result(timeout=40)
    w._poll_extra()
    assert w._extra_future is None
    assert w._modern_windows["stft"] is child
    assert "APP_DERIVED" in w.extra_method_infos["stft"].text()
    assert "старый результат отброшен" not in w.extra_method_infos["stft"].text()


def test_inspector_is_compact_vertical_without_horizontally_clipped_fields(widget):
    w,app=widget
    from PySide6 import QtCore,QtWidgets
    w.resize(1600,900)
    w.show()
    app.processEvents()
    scroll=w._modern_inspector_dock.widget()
    assert isinstance(scroll,QtWidgets.QScrollArea)
    assert scroll.horizontalScrollBarPolicy()==QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    # The right inspector uses stacked labels/controls instead of the old
    # two-column QFormLayout that needed a horizontal scrollbar at 1600 px.
    assert len(w._modern_inspector.findChildren(QtWidgets.QFormLayout))==0
    assert len(w._modern_metric_values)==4
    assert all(v.text()=="—" for v in w._modern_metric_values.values())
    spectrum_pane=w._modern_inspector.widget(0)
    toggles=spectrum_pane.findChildren(QtWidgets.QToolButton)
    assert toggles and not toggles[0].isChecked()
    assert w._modern_inspector_dock.width()>=246
    assert scroll.widget().width()<=scroll.viewport().width()+2
    assert w.views.count()==4


def test_overview_curve_is_cleared_after_switch_to_unavailable_adc(widget):
    w,_=widget
    from mvk_live_standalone.vibration import analyze_vibration
    data=_feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w._spectrum=analyze_vibration(data,8192,nfft=8192)
    w._render_spectrum()
    w._render_wave()
    assert len(w.overview_spec_curve.getData()[0])>0
    assert len(w.overview_wave_curve.getData()[0])>0
    w.adc.setCurrentIndex(1)
    w._render_wave()
    sx,_=w.overview_spec_curve.getData()
    tx,_=w.overview_wave_curve.getData()
    assert sx is None or len(sx)==0
    assert tx is None or len(tx)==0
    assert "нет подтверждённых" in w.overview_wave.getPlotItem().titleLabel.text.lower()


def test_bearing_window_pins_source_and_never_reconfigures_live_fft(widget):
    """Independent bearing operation must not change main FFT settings."""
    w,_=widget
    from mvk_live_standalone.modern_shell import open_advanced_window
    _feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.kind.setCurrentIndex(w.kind.findData("velocity"))
    w.analysis.setCurrentIndex(w.analysis.findData("welch"))
    w.bearing_fft.setCurrentIndex(w.bearing_fft.findData(8192))
    before=(w.kind.currentData(),w.analysis.currentData(),
            w.nfft.currentData(),w.envelope_band.currentData())
    child=open_advanced_window(w,"bearing")
    assert child.centralWidget() is w.diagnostics_page
    pin=w._modern_method_pins["bearing"]
    assert pin["adc"]==1 and pin["fs"]==8192
    assert len(pin["samples"])==8192
    assert not pin["samples"].flags.writeable
    w._run_bearing_page()
    view=w._bearing_spectrum
    assert view is not None and view.mode=="envelope"
    assert "АЦП 1" in w.bearing_plot.getPlotItem().titleLabel.text
    assert (w.kind.currentData(),w.analysis.currentData(),
            w.nfft.currentData(),w.envelope_band.currentData())==before
    w.adc.setCurrentIndex(w.adc.findData(2))
    assert w._bearing_spectrum is view
    assert w._modern_method_pins["bearing"] is pin
    assert w._professional_cursors.bearing_line.isVisible()
    np.testing.assert_allclose(w.bearing_curve.getData()[0],view.hz)
    w._clear("LIVE источник закрыт")
    assert w._bearing_spectrum is view  # unrelated session reset
    assert w._native.state()==w._native.ProcessState.NotRunning
    assert open_advanced_window(w,"bearing") is child


def test_bearing_source_must_be_explicit_and_large_fft_needs_new_capture(widget):
    w,_=widget
    from mvk_live_standalone.modern_shell import (
        open_advanced_window, _pin_method_source)
    child=open_advanced_window(w,"bearing")
    assert "bearing" not in w._modern_method_pins
    w._run_bearing_page()
    assert w._bearing_spectrum is None
    assert "Источник не закреплён" in w.bearing_diagnostics.text()
    _feed(w)
    w.bearing_fft.setCurrentIndex(w.bearing_fft.findData(8192))
    assert _pin_method_source(w,"bearing",child)
    w._run_bearing_page()
    assert w._bearing_spectrum is not None
    old_pin=w._modern_method_pins["bearing"]
    w.bearing_fft.setCurrentIndex(w.bearing_fft.findData(16384))
    w._run_bearing_page()
    assert w._bearing_spectrum is None
    assert "больше закреплённой выборки" in w.bearing_diagnostics.text()
    assert w._modern_method_pins["bearing"] is old_pin
    w.adc.setCurrentIndex(w.adc.findData(2))
    assert not _pin_method_source(w,"bearing",child)
    assert w._modern_method_pins["bearing"] is old_pin



def test_overview_has_only_quick_settings_and_tab_owns_inspector(widget):
    w,_=widget
    assert w.views.currentWidget() is w.overview_page
    assert w._modern_inspector.currentIndex()==2
    assert "Обзор" in w._modern_inspector_dock.windowTitle()
    assert w._overview_spectrum_view.currentData()=="log_vu"
    assert w._overview_frequency_limit.currentData()==w.x_limit_choice.currentData()
    assert w._overview_y_height.currentData()==w.y_height_choice.currentData()
    assert w._overview_timebase.currentData()==w.timebase.currentData()
    assert w._overview_time_y_width.currentData()==w.time_y_width.currentData()
    # Legacy one-click graph interaction never opens the detailed inspector.
    from mvk_live_standalone.modern_shell import _chart_focus, _focus_inspector
    _chart_focus(w,"spectrum")
    assert w.views.currentWidget() is w.overview_page
    assert w._modern_inspector.currentIndex()==2
    _focus_inspector(w,"spectrum")
    assert w.views.currentWidget() is w.spectrum_page
    assert w._modern_inspector.currentIndex()==0
    assert "Спектр" in w._modern_inspector_dock.windowTitle()
    w.views.setCurrentWidget(w.wave_page)
    assert w._modern_inspector.currentIndex()==1
    assert "Временной сигнал" in w._modern_inspector_dock.windowTitle()
    w.views.setCurrentWidget(w.calculated_page)
    assert w._modern_inspector_dock.isHidden()
    w.views.setCurrentWidget(w.overview_page)
    assert w._modern_inspector.currentIndex()==2
    assert not w._modern_inspector_dock.isHidden()


def test_overview_quick_controls_reuse_exact_main_processing_values(widget):
    w,_=widget
    assert w.adc.count()==8 and w.dsp_adc.isHidden()
    before_filter=(w.filter_choice.currentData(),
                   w.time_filter_choice.currentData())
    modes={
        "log_vu": ("acceleration","db","дБ"),
        "linear_vu": ("acceleration","linear","м/с²"),
        "linear_vs": ("velocity","linear","мм/с"),
        "linear_vp": ("displacement","linear","мкм"),
    }
    assert w._overview_spectrum_view.count()==4
    for key,(kind,scale,unit) in modes.items():
        w._overview_spectrum_view.setCurrentIndex(
            w._overview_spectrum_view.findData(key))
        assert w.kind.currentData()==kind
        assert w.yscale.currentData()==scale
        # The Y scale selection must be fully rebuilt with new units.
        assert w._overview_y_height.count()==w.y_height_choice.count()
        assert unit in w._overview_y_height.itemText(1)
        assert unit in w._overview_y_height.itemText(
            w._overview_y_height.count()-1)
        assert w._overview_y_height.currentData() is None
        last=w._overview_y_height.count()-1
        chosen=w._overview_y_height.itemData(last)
        w._overview_y_height.setCurrentIndex(last)
        assert w.y_height_choice.currentData()==chosen
        low,high=w.spec.viewRange()[1]
        assert high-low==pytest.approx(chosen,rel=1e-4)
        if scale=="linear":
            assert low==pytest.approx(0.,abs=1e-5)
    w._overview_frequency_limit.setCurrentIndex(
        w._overview_frequency_limit.findData(4000))
    assert w.x_limit_choice.currentData()==4000
    w._overview_timebase.setCurrentIndex(
        w._overview_timebase.findData(.5))
    assert w.timebase.currentData()==.5
    w._overview_time_y_width.setCurrentIndex(
        w._overview_time_y_width.findData(10.))
    assert w.time_y_width.currentData()==10.
    assert (w.filter_choice.currentData(),
            w.time_filter_choice.currentData())==before_filter


def test_filters_are_grouped_and_spectrum_and_time_have_independent_scopes(widget):
    from PySide6 import QtWidgets
    w,_=widget
    assert w.filter_choice.itemText(
        w.filter_choice.findData("original_preset")
    ).startswith("Меню MVKView")
    assert w.filter_choice.itemText(
        w.filter_choice.findData("third_octave")
    ).startswith("1/3 октавы")
    assert w.filter_choice.itemText(0)=="Без фильтра"
    assert w.time_filter_choice.itemText(0)=="Без фильтра"
    spectrum_pane=w._modern_inspector.widget(0)
    assert w.spectrum_view not in spectrum_pane.findChildren(QtWidgets.QComboBox)
    overview=w._modern_inspector.widget(2)
    assert [c.currentData() for c in
            overview.findChildren(QtWidgets.QComboBox)] == [
        w.spectrum_view.currentData(),w.x_limit_choice.currentData(),
        w.y_height_choice.currentData(),w.timebase.currentData(),
        w.time_y_width.currentData()]
    assert not overview.findChildren(QtWidgets.QPushButton)
    assert "Фильтр" not in " ".join(
        label.text() for label in overview.findChildren(QtWidgets.QLabel))
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("highpass"))
    assert w.time_filter_choice.currentData()=="none"
    w.time_filter_choice.setCurrentIndex(
        w.time_filter_choice.findData("third_octave"))
    assert w.filter_choice.currentData()=="highpass"
    assert w.time_filter_center.count()==43
    assert w._modern_inspector.widget(0).findChild(
        QtWidgets.QToolButton) is not None


def test_overview_mode_follows_advanced_spectrum_without_stale_preset(widget):
    w,_=widget
    # Returning from a detailed view must reflect its actual physical mode.
    w.kind.setCurrentIndex(w.kind.findData("velocity"))
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    assert w._overview_spectrum_view.currentData()=="linear_vs"
    assert "мм/с" in w._overview_y_height.itemText(1)
    # A valid advanced combination outside the 4 presets must not claim to
    # be 'logarithmic acceleration' while actually showing velocity in dB.
    w.yscale.setCurrentIndex(w.yscale.findData("db"))
    assert w._overview_spectrum_view.currentIndex()==-1
    assert "дБ" in w._overview_y_height.itemText(1)
    w._overview_spectrum_view.setCurrentIndex(
        w._overview_spectrum_view.findData("log_vu"))
    assert w.kind.currentData()=="acceleration"
    assert w.yscale.currentData()=="db"
    assert w._overview_spectrum_view.currentData()=="log_vu"
    assert "дБ" in w._overview_y_height.itemText(1)


def test_overview_scale_mirror_is_rebuilt_after_mode_and_fft_changes(widget):
    w,_=widget
    select=w._overview_spectrum_view
    select.setCurrentIndex(select.findData("linear_vp"))
    assert w._overview_y_height.itemText(1).endswith("мкм")
    assert not any("дБ" in w._overview_y_height.itemText(i)
                   for i in range(w._overview_y_height.count()))
    w.analysis.setCurrentIndex(w.analysis.findData("welch"))
    assert not w.y_height_choice.isEnabled()
    assert not w._overview_y_height.isEnabled()
    w.analysis.setCurrentIndex(w.analysis.findData("fft"))
    assert w._overview_y_height.isEnabled()
    w.y_height_choice.setCurrentIndex(w.y_height_choice.count()-1)
    assert w._overview_y_height.currentData()==w.y_height_choice.currentData()
    w._overview_y_height.setCurrentIndex(
        w._overview_y_height.findData(5.))
    assert w.y_height_choice.currentData()==5.
    # Time's vertical limit stays an independently signed VU scale.
    w._overview_time_y_width.setCurrentIndex(
        w._overview_time_y_width.findData(2.))
    assert w.time_y_width.currentData()==2.
    w.time_y_width.setCurrentIndex(w.time_y_width.findData(20.))
    assert w._overview_time_y_width.currentData()==20.


def test_inspector_titlebar_close_can_be_restored_by_toolbar_menu_and_popup(widget):
    """The titlebar X must not permanently strand operator controls."""
    from PySide6 import QtWidgets
    w,app=widget
    w.show()
    app.processEvents()
    dock=w._modern_inspector_dock
    button=w._modern_inspector_button
    toggle=w._modern_actions["inspector_toggle"]
    floating=w._modern_actions["inspector_float"]
    assert dock.isVisible() and button.isChecked() and toggle.isChecked()
    assert button.menu() is not None
    assert len(button.menu().actions())==2

    # The actual QDockWidget titlebar close behaves like a user close.
    dock.close()
    app.processEvents()
    assert dock.isHidden()
    assert not button.isChecked() and not toggle.isChecked()
    w.views.setCurrentWidget(w.wave_page)
    assert dock.isHidden()  # tab changes do NOT undo the user's close
    w.views.setCurrentWidget(w.overview_page)
    assert dock.isHidden()

    # Persistent top-bar affordance opens current context, no stale page.
    button.click()
    app.processEvents()
    assert dock.isVisible() and button.isChecked() and toggle.isChecked()
    assert w._modern_inspector.currentIndex()==2
    toggle.trigger()
    app.processEvents()
    assert dock.isHidden() and not button.isChecked()
    toggle.trigger()
    app.processEvents()
    assert dock.isVisible() and toggle.isChecked()

    # Floating, nonmodal is optional, closing it must remain recoverable.
    w._modern_inspector_popup_action.trigger()
    app.processEvents()
    assert dock.isFloating() and dock.isVisible()
    assert floating.isChecked()
    dock.close()
    app.processEvents()
    assert not button.isChecked()
    w._modern_inspector_dock_action.trigger()
    app.processEvents()
    assert not dock.isFloating()
    assert dock.isVisible()
    assert not floating.isChecked()
    w.views.setCurrentWidget(w.calculated_page)
    assert dock.isHidden()
    button.click()  # from a plot-free tab, go back to Overview
    app.processEvents()
    assert w.views.currentWidget() is w.overview_page
    assert dock.isVisible()
    w.hide()


def test_overview_blank_adc_rescales_both_time_axes_without_inventing_data(widget):
    w,_=widget
    assert w._gui_ring.channel(1) is None
    assert w.overview_wave.viewRange()[1]==pytest.approx([-1.,1.],abs=1e-5)
    assert w.wave.viewRange()[1]==pytest.approx([-1.,1.],abs=1e-5)
    w._overview_timebase.setCurrentIndex(
        w._overview_timebase.findData(.05))
    w._overview_time_y_width.setCurrentIndex(
        w._overview_time_y_width.findData(5.))
    for plot in (w.wave,w.overview_wave):
        assert plot.viewRange()[0]==pytest.approx([-.05,0.],abs=1e-5)
        assert plot.viewRange()[1]==pytest.approx([-5.,5.],abs=1e-5)
    for curve in (w.overview_wave_curve,w.wave_curve):
        # pyqtgraph returns None, not an empty ndarray, for a curve
        # which has never received even a test sample.
        values=curve.getData()[0]
        assert values is None or len(values)==0
    assert w._native.state()==w._native.ProcessState.NotRunning


def test_overview_all_controls_update_real_verified_graphs_and_physical_units(widget):
    """Integration: real test-ring Float32, signal reanalysis, scaling, redraw."""
    from mvk_live_standalone.vibration import vibration_plot_values
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    def wait_for_fft(kind):
        # A pending, superseded worker can finish before its replacement.
        for _ in range(6):
            if w._future is None:
                w._last_fft_submit=0.0
                w._schedule_fft()
            assert w._future is not None
            w._future.result(timeout=25)
            w._collect_analysis()
            if w._spectrum is not None and w._spectrum.kind==kind:
                return w._spectrum
        pytest.fail(f"No verified app-derived FFT for {kind}")

    modes={
        "linear_vu": ("acceleration","м/с²"),
        "linear_vs": ("velocity","мм/с"),
        "linear_vp": ("displacement","мкм"),
        "log_vu": ("acceleration","дБ"),
    }
    results={}
    for key,(kind,unit) in modes.items():
        quick=w._overview_spectrum_view
        quick.setCurrentIndex(quick.findData(key))
        view=wait_for_fft(kind)
        results[key]=float(view.rms[
            np.argmin(abs(view.hz-100.))])
        assert view.kind==kind and view.mode=="fft"
        ox,oy=w.overview_spec_curve.getData()
        sx,sy=w.spec_curve.getData()
        np.testing.assert_allclose(ox,sx)
        np.testing.assert_allclose(oy,sy)
        assert len(ox)>10
        assert unit in w.overview_spec.getPlotItem().getAxis(
            "left").label.toPlainText()
        assert unit in w._overview_y_height.itemText(1)

    # Independent physical transformations: acceleration->velocity (×1/ω),
    # acceleration->displacement (×1/ω²), not just a renamed y-axis.
    ratio_velocity=1000/(2*math.pi*100)
    ratio_displacement=1e6/(2*math.pi*100)**2
    assert results["linear_vs"]==pytest.approx(
        results["linear_vu"]*ratio_velocity,rel=.06)
    assert results["linear_vp"]==pytest.approx(
        results["linear_vu"]*ratio_displacement,rel=.06)

    w._overview_frequency_limit.setCurrentIndex(
        w._overview_frequency_limit.findData(200))
    assert w.spec.viewRange()[0]==pytest.approx([0,200],abs=1e-4)
    assert w.overview_spec.viewRange()[0]==pytest.approx([0,200],abs=1e-4)
    w._overview_y_height.setCurrentIndex(
        w._overview_y_height.findData(40.))
    assert w.spec.viewRange()[1][1]-w.spec.viewRange()[1][0]==pytest.approx(40.)
    assert w.overview_spec.viewRange()[1]==pytest.approx(
        w.spec.viewRange()[1],abs=1e-4)
    assert "дБ" in w._overview_y_height.currentText()

    w._overview_timebase.setCurrentIndex(
        w._overview_timebase.findData(.02))
    wx,wy=w.overview_wave_curve.getData()
    tx,ty=w.wave_curve.getData()
    np.testing.assert_allclose(wx,tx)
    np.testing.assert_allclose(wy,ty)
    assert len(wx)>2
    assert float(wx[0])>=-.03
    w._overview_time_y_width.setCurrentIndex(
        w._overview_time_y_width.findData(2.))
    assert w.wave.viewRange()[1]==pytest.approx([-2,2],abs=1e-5)
    assert w.overview_wave.viewRange()[1]==pytest.approx([-2,2],abs=1e-5)
    assert w._native.state()==w._native.ProcessState.NotRunning



def test_overview_db_to_linear_vu_redraws_immediately_without_new_fft(widget):
    """A physical FFT can be replotted in dB or m/s² without a device."""
    from mvk_live_standalone.vibration import (
        analyze_vibration, vibration_plot_values)
    w,_=widget
    fs=8192
    n=8192
    t=np.arange(n,dtype=np.float64)/fs
    samples=np.sqrt(2.)*np.sin(2*math.pi*100.*t)
    assert w._preview is None
    w.nfft.setCurrentIndex(w.nfft.findData(n))
    w._spectrum=analyze_vibration(
        samples,fs,kind="acceleration",mode="fft",nfft=n)
    w._render_spectrum()
    assert w.yscale.currentData()=="db"
    x,y_db=w.overview_spec_curve.getData()
    assert len(x)>10
    assert np.all(np.isfinite(y_db))
    w._overview_spectrum_view.setCurrentIndex(
        w._overview_spectrum_view.findData("linear_vu"))
    assert w._spectrum is not None
    assert w.kind.currentData()=="acceleration"
    assert w.yscale.currentData()=="linear"
    _,y_linear=w.overview_spec_curve.getData()
    np.testing.assert_allclose(
        y_linear, vibration_plot_values(w._spectrum,"linear"),
        rtol=1e-12)
    assert not np.array_equal(y_db,y_linear)
    w._overview_spectrum_view.setCurrentIndex(
        w._overview_spectrum_view.findData("log_vu"))
    assert w.yscale.currentData()=="db"
    _,y_back=w.overview_spec_curve.getData()
    np.testing.assert_allclose(y_back,y_db,rtol=1e-12,atol=1e-10)
    assert w._native.state()==w._native.ProcessState.NotRunning



def test_spectrum_panel_physical_modes_and_controls_are_honest(widget):
    """Professional spectrum setup: quantity/method/N/axes/filter are distinct."""
    from PySide6 import QtWidgets
    w,_=widget
    panel=w._modern_inspector.widget(0)
    assert all(panel.isAncestorOf(control) for control in (
        w.kind,w.analysis,w.nfft,w.yscale,w.db_ref,w.xscale,
        w.x_limit_choice,w.y_height_choice,w.filter_choice,
        w.filter_center,w.envelope_band,w.smooth))
    assert w._modern_spectrum_setup_info.text()
    assert "Fs неизвестна" in w._modern_spectrum_setup_info.text()
    assert "отсчётов" in w.nfft.currentText()
    assert "Fs/" not in w.nfft.currentText()
    assert len(w.nfft.currentText())<25
    assert "Хэнна" in w._modern_spectrum_setup_info.text()
    assert "Отсчётов в FFT" in " ".join(
        a.text() for a in panel.findChildren(QtWidgets.QLabel))
    assert w._modern_spectrum_envelope_row.isHidden()
    w.analysis.setCurrentIndex(w.analysis.findData("welch"))
    assert "50%" in w._modern_spectrum_setup_info.text()
    assert w._modern_spectrum_smoothing_row.isHidden()
    assert not w.smooth.isEnabled()
    assert not w.y_height_choice.isEnabled()
    assert "автомасштаб" in " ".join(
        a.text().lower() for a in panel.findChildren(QtWidgets.QLabel))
    w.analysis.setCurrentIndex(w.analysis.findData("asd"))
    assert "ASD Welch" in w._modern_spectrum_setup_info.text()
    w.analysis.setCurrentIndex(w.analysis.findData("fft"))
    assert w.smooth.isEnabled()
    assert "Хэнна" in w._modern_spectrum_setup_info.text()
    assert w.y_height_choice.isEnabled()
    w.analysis.setCurrentIndex(w.analysis.findData("envelope"))
    assert w.kind.currentData()=="acceleration"
    assert not w.kind.isEnabled()
    assert not w._modern_spectrum_envelope_row.isHidden()
    assert w._modern_spectrum_smoothing_row.isHidden()
    w.kind.setCurrentIndex(w.kind.findData("velocity"))
    assert w.kind.currentData()=="acceleration"


def test_spectrum_real_fft_resolution_and_stale_filter_are_not_misleading(widget):
    from mvk_live_standalone.vibration import vibration_plot_values
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    def calculate():
        for _ in range(5):
            if w._future is None:
                w._last_fft_submit=0.0
                w._schedule_fft()
            assert w._future is not None
            w._future.result(timeout=20)
            w._collect_analysis()
            if (w._spectrum is not None and
                    w._last_completed_spectrum_settings == w._read_settings()):
                return w._spectrum
        pytest.fail("No current verified FFT")
    raw=calculate()
    assert raw.resolution_hz==pytest.approx(1.0)
    assert "Δf 1 Гц" in w._modern_spectrum_setup_info.text()
    assert "длительность окна 1 с" in w._modern_spectrum_setup_info.text()
    peak=float(raw.rms[np.argmin(abs(raw.hz-100))])
    assert peak>0.9
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("highpass"))
    w.custom_low.setValue(200.)
    assert w._spectrum is None
    assert w._last_completed_spectrum_settings is None
    stale=w.overview_spec_curve.getData()[0]
    assert stale is None or len(stale)==0
    assert "Пересчёт" in w.metrics.text()
    filtered=calculate()
    attenuation=filtered.rms[np.argmin(abs(filtered.hz-100))]
    assert attenuation < .1 * peak
    assert "ФВЧ" in w._modern_spectrum_filter_note.text()
    w.nfft.setCurrentIndex(w.nfft.findData(16384))
    assert w._spectrum is None
    longer=calculate()
    assert longer.nfft==16384
    assert longer.resolution_hz==pytest.approx(.5)
    assert "Δf 0.5 Гц" in w._modern_spectrum_setup_info.text()
    assert "длительность окна 2 с" in w._modern_spectrum_setup_info.text()


def test_spectrum_welch_density_and_asd_square_root_with_real_source(widget):
    from mvk_live_standalone.vibration import vibration_plot_values
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.analysis.setCurrentIndex(w.analysis.findData("welch"))
    def calculate(kind):
        for _ in range(5):
            if w._future is None:
                w._last_fft_submit=0.0
                w._schedule_fft()
            assert w._future is not None
            w._future.result(timeout=20)
            w._collect_analysis()
            if (w._spectrum is not None and
                    w._spectrum.mode==kind and
                    w._last_completed_spectrum_settings==w._read_settings()):
                return w._spectrum
        pytest.fail(kind)
    power=calculate("welch")
    i=int(np.argmin(abs(power.hz-100)))
    p=float(power.rms[i])
    assert p>0
    # The default dB display is a valid PSD representation:
    # 10*log10(power/reference^2), not linear power in physical units.
    assert "дБ" in w.spec.getPlotItem().getAxis("left").label.toPlainText()
    assert not w.smooth.isEnabled()
    assert "50%" in w._modern_spectrum_setup_info.text()
    assert "сегм." in w._modern_spectrum_setup_info.text()
    assert vibration_plot_values(power,"db")[i] == pytest.approx(
        10*math.log10(p/(1e-6**2)),abs=1e-5)
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    assert "(м/с²)²/Гц" in w.spec.getPlotItem().getAxis("left").label.toPlainText()
    w.analysis.setCurrentIndex(w.analysis.findData("asd"))
    assert w._spectrum is None
    amplitude=calculate("asd")
    assert amplitude.rms[i]**2==pytest.approx(p,rel=1e-7)
    assert vibration_plot_values(amplitude,"db")[i] == pytest.approx(
        20*math.log10(float(amplitude.rms[i])/1e-6),abs=1e-5)
    assert "м/с²/√Гц" in w.spec.getPlotItem().getAxis("left").label.toPlainText()
    assert not w.y_height_choice.isEnabled()


def test_spectrum_out_of_nyquist_filter_never_uses_stale_curve(widget):
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.filter_choice.setCurrentIndex(
        w.filter_choice.findData("third_octave"))
    assert w.filter_center.findData(8000.)>=0
    w.filter_center.setCurrentIndex(
        w.filter_center.findData(8000.))
    assert "НЕДОПУСТИМО" in w._modern_spectrum_filter_note.text()
    # Earlier option changes can leave an old, still-running FFT worker.
    # Drain it first; only the NEW job with this exact filter must fail.
    # A previous unfiltered result is not evidence for a rejected band.
    rejected=False
    for _ in range(6):
        if w._future is None:
            w._last_fft_submit=0.
            w._schedule_fft()
        assert w._future is not None
        try:
            w._future.result(timeout=20)
        except ValueError as exc:
            assert "Nyquist" in str(exc)
            rejected=True
        w._last_fft_submit=0.
        w._collect_analysis()
        if rejected:
            break
    assert rejected
    assert w._spectrum is None
    assert "спектр недоступен" in w.metrics.text()
    empty=w.overview_spec_curve.getData()[0]
    assert empty is None or len(empty)==0
    assert w._native.state()==w._native.ProcessState.NotRunning



def test_fft_worker_survives_normal_new_rx_preview_generation(widget):
    """A new authenticated RX frame must not discard a valid in-flight FFT."""
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    assert w._future is not None
    revision=w._processing_revision
    generation=w._generation
    w._request_update()   # same processing settings, newer RX
    assert w._processing_revision==revision
    assert w._generation==generation+1
    w._future.result(timeout=20)
    w._collect_analysis()
    assert w._spectrum is not None
    assert w._spectrum.kind=="acceleration"
    assert w._last_completed_spectrum_settings==w._read_settings()


def test_fft_smoothing_enforces_odd_width_even_when_typed_directly(widget):
    w,_=widget
    w.smooth.setValue(4)
    assert w.smooth.value()==5
    assert w.analysis.currentData()=="fft"
    w.analysis.setCurrentIndex(w.analysis.findData("welch"))
    assert not w.smooth.isEnabled()
    assert w._modern_spectrum_smoothing_row.isHidden()



def test_spectrum_db_reference_changes_actual_curve_by_120_db_not_just_label(widget):
    from mvk_live_standalone.vibration import (
        analyze_vibration, vibration_plot_values)
    w,_=widget
    fs,n=8192,8192
    source=np.sqrt(2)*np.sin(
        2*math.pi*100*np.arange(n,dtype=np.float64)/fs)
    w.nfft.setCurrentIndex(w.nfft.findData(n))
    w._spectrum=analyze_vibration(
        source,fs,kind="acceleration",mode="fft",nfft=n)
    w._render_spectrum()
    assert w.yscale.currentData()=="db"
    _,before=w.overview_spec_curve.getData()
    assert np.isfinite(before).all()
    w.db_ref.setCurrentIndex(w.db_ref.findData("unit"))
    _,after=w.overview_spec_curve.getData()
    # Only measured NON-CENSORED lines have a physically meaningful
    # 120 dB reference shift; silence is clipped at the display floor.
    ix=int(np.argmin(abs(w._spectrum.hz-100)))
    assert after[ix]-before[ix]==pytest.approx(-120.,abs=1e-8)
    np.testing.assert_allclose(
        after,vibration_plot_values(w._spectrum,"db",reference="unit"))
    assert "1 м/с²" in w.overview_spec.getPlotItem().getAxis(
        "left").label.toPlainText()
    assert w._spectrum.kind=="acceleration"
    assert w._native.state()==w._native.ProcessState.NotRunning


def test_spectrum_manual_axis_dialog_immediately_updates_overview(widget,monkeypatch):
    from PySide6 import QtWidgets
    w,_=widget
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    def submit(dialog):
        boxes=dialog.findChildren(QtWidgets.QDoubleSpinBox)
        assert len(boxes)==4
        for box,value in zip(boxes,[20.,200.,0.,3.]):
            box.setValue(value)
        return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(QtWidgets.QDialog,"exec",submit)
    w._edit_axes()
    for plot in (w.spec,w.overview_spec):
        assert plot.viewRange()[0]==pytest.approx([20.,200.],abs=1e-5)
        assert plot.viewRange()[1]==pytest.approx([0.,3.],abs=1e-5)
    assert w._manual_spec_axes==(20.,200.,0.,3.)
    w._reset_spectrum_axis()
    assert w._manual_spec_axes is None
    assert w.spec.viewRange()[0]==w.overview_spec.viewRange()[0]



def test_spectrum_envelope_does_not_silently_use_fft_only_filter(widget):
    w,_=widget
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("highpass"))
    w.custom_low.setValue(200.)
    assert w._read_settings()[3]==(200.,None)
    assert w.filter_choice.isEnabled()
    w.analysis.setCurrentIndex(w.analysis.findData("envelope"))
    assert w.analysis.currentData()=="envelope"
    assert w.kind.currentData()=="acceleration"
    assert w._read_settings()[3]==(0.,None)
    assert w._read_settings()[-1] is None
    assert not w.filter_choice.isEnabled()
    assert not w.filter_button.isEnabled()
    assert not w._modern_spectrum_envelope_row.isHidden()
    assert "НЕ участвует" in w._modern_spectrum_filter_note.text()
    w.analysis.setCurrentIndex(w.analysis.findData("fft"))
    assert w.filter_choice.isEnabled()
    assert w.filter_button.isEnabled()
    assert w._read_settings()[3]==(200.,None)
    assert w._modern_spectrum_envelope_row.isHidden()



def test_time_scope_settings_show_real_fs_samples_duration_and_full_measurements(widget):
    w,_=widget
    panel=w._modern_inspector.widget(1)
    assert "Fs и реальные отсчёты не подтверждены" in w._modern_time_setup_info.text()
    assert "развёртка 1 с" in w._modern_time_setup_info.text()
    _feed(w,fs=8192,n=16384)
    w._render_wave()
    assert "Fs 8192 Гц" in w._modern_time_setup_info.text()
    assert "8192 подтверждённых отсчётов" in w._modern_time_setup_info.text()
    assert "шаг 0.12207 мс" in w._modern_time_setup_info.text()
    assert "показано 1 с" in w._modern_time_setup_info.text()
    assert "СКЗ AC (DC вычтено)" in w.wave_stats.text()
    assert "СКЗ полный" in w.wave_stats.text()
    assert "Среднее/DC" in w.wave_stats.text()
    assert "Макс" in w.wave_stats.text() and "Мин" in w.wave_stats.text()
    assert "Crest AC" in w.wave_stats.text()
    assert "Пик-пик" in w.wave_stats.text()
    assert "подтверждённых отсчётов" in w._modern_time_setup_info.text()
    w.timebase.setCurrentIndex(w.timebase.findData(5.))
    assert "ограничение доступной истории" in w._modern_time_setup_info.text()
    assert "показано 2 с" in w._modern_time_setup_info.text()
    assert "доступно только 2 с из запрошенных 5 с" in w.wave_info.text()
    a=w._cursor_time_samples
    assert len(a)==16384
    assert w._native.state()==w._native.ProcessState.NotRunning


def test_time_scope_minmax_plot_has_genuine_impulse_order_and_cursor_source(widget):
    from mvk_live_standalone.live_ipc import IPCPreview, IPCChannel, DOMAIN
    w,_=widget
    fs,n=8192,32768
    samples=np.zeros(n,dtype="<f4")
    samples[16000]=3.5
    samples[16001]=-2.25
    channel=IPCChannel(1,fs,samples,n%(1<<32),n,
                       hashlib.sha256(samples.tobytes()).hexdigest())
    preview=IPCPreview("TEST_TIME_EXTREMA",DOMAIN,True,
                       datetime.now(timezone.utc),{1:channel})
    w._gui_ring.ingest_preview(preview)
    w._preview=preview
    w.timebase.setCurrentIndex(w.timebase.findData(5.))
    w._render_wave()
    xx,yy=w.wave_curve.getData()
    indices=np.rint(xx*fs+n).astype(int)
    assert np.all(np.diff(xx)>0)
    np.testing.assert_array_equal(yy,w._cursor_time_samples[indices])
    assert np.where(indices==16000)[0].size==1
    assert np.where(indices==16001)[0].size==1
    assert np.where(indices==16000)[0][0]<np.where(indices==16001)[0][0]
    assert np.max(yy)==3.5 and np.min(yy)==-2.25
    assert "Пик-пик 5.75" in w.wave_stats.text()
    ox,oy=w.overview_wave_curve.getData()
    np.testing.assert_array_equal(ox,xx)
    np.testing.assert_array_equal(oy,yy)


def test_time_scope_filtering_is_not_recomputed_on_each_cropped_10ms_window(widget):
    from mvk_live_standalone.live_ipc import IPCPreview, IPCChannel, DOMAIN
    from mvk_live_standalone.time_controls import time_filter_waveform
    w,_=widget
    fs,n=8192,32768
    times=np.arange(n,dtype=np.float64)/fs
    raw=(np.sqrt(2)*np.sin(2*np.pi*100*times)
         +np.sqrt(2)*np.sin(2*np.pi*1000*times)).astype("<f4")
    channel=IPCChannel(1,fs,raw,n%(1<<32),n,
                       hashlib.sha256(raw.tobytes()).hexdigest())
    preview=IPCPreview("TEST_TIME_FULL_HISTORY",DOMAIN,True,
                       datetime.now(timezone.utc),{1:channel})
    w._gui_ring.ingest_preview(preview)
    w._preview=preview
    w.time_filter_choice.setCurrentIndex(
        w.time_filter_choice.findData("lowpass"))
    w.time_filter_high=200.
    w.timebase.setCurrentIndex(w.timebase.findData(.01))
    actual=w._cursor_time_samples.copy()
    assert len(actual)==int(round(.01*fs))
    expected=time_filter_waveform(
        raw,fs,mode="lowpass",high=200.)[-len(actual):]
    np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
    assert "ФНЧ ≤200 Гц" in w._modern_time_filter_note.text()
    assert "не влияет" not in w._modern_time_filter_note.text()
    assert "Fs 8192" in w._modern_time_setup_info.text()
    # Only the selected local time filter changes, never a spectrum setting.
    assert w.filter_choice.currentData()=="none"
    assert w._native.state()==w._native.ProcessState.NotRunning


def test_time_scope_invalid_nyquist_filter_clears_data_and_displays_constraint(widget):
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w._render_wave()
    assert len(w.wave_curve.getData()[0])>0
    w.time_filter_choice.setCurrentIndex(
        w.time_filter_choice.findData("third_octave"))
    assert w.time_filter_center.findData(8000.)>=0
    w.time_filter_center.setCurrentIndex(
        w.time_filter_center.findData(8000.))
    assert "НЕДОПУСТИМО" in w._modern_time_filter_note.text()
    assert "Nyquist" in w.wave_stats.text()
    assert w._cursor_time_samples is None
    empty=w.overview_wave_curve.getData()[0]
    assert empty is None or len(empty)==0
    w.time_filter_center.setCurrentIndex(
        w.time_filter_center.findData(1000.))
    assert len(w.wave_curve.getData()[0])>0
    assert "1000 Гц" in w._modern_time_filter_note.text()
    assert w._cursor_time_samples is not None


def test_time_scope_freeze_history_and_independent_y_axis(widget):
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w._render_wave()
    before=w._cursor_time_samples.copy()
    w.freeze.setChecked(True)
    w._toggle_freeze(True)
    assert w.freeze.isChecked()
    assert "Freeze" in w._modern_time_setup_info.text() or (
        w._modern_refresh_time_setup() is None and
        "Freeze" in w._modern_time_setup_info.text())
    w.time_y_width.setCurrentIndex(w.time_y_width.findData(10.))
    assert w.wave.viewRange()[1]==pytest.approx([-10.,10.])
    assert w.overview_wave.viewRange()[1]==pytest.approx([-10.,10.])
    w.history.setValue(.25)
    assert "Freeze" in w._modern_time_setup_info.text()
    assert not np.array_equal(w._cursor_time_samples,before)
    # Source is static; history changes the reviewed interval rather than
    # making measurements from the newest part of the same frozen buffer.
    assert w._cursor_time_samples.size==8192
    w.freeze.setChecked(False)
    w._toggle_freeze(False)
    assert "Live" in w._modern_time_setup_info.text()



def test_time_scope_manual_y_clipping_warns_but_never_clips_real_statistics(widget):
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w._render_wave()
    full=w._cursor_time_samples.copy()
    assert np.max(np.abs(full))>1.4
    w.time_y_width.setCurrentIndex(w.time_y_width.findData(.5))
    assert "ВНИМАНИЕ: масштаб ±0.5 м/с²" in w.wave_info.text()
    assert "данные и расчёты не обрезаны" in w.wave_info.text()
    np.testing.assert_array_equal(w._cursor_time_samples,full)
    assert w.wave.viewRange()[1]==pytest.approx([-.5,.5])
    assert w.overview_wave.viewRange()[1]==pytest.approx([-.5,.5])
    assert "Пик 1.4142" in w.wave_stats.text()
    w.time_y_width.setCurrentIndex(w.time_y_width.findData(None))
    assert "ВНИМАНИЕ" not in w.wave_info.text()
    assert w.wave.viewRange()[1][1]>1.4


def test_time_scope_selected_adc_without_data_clears_old_source_and_cursor(widget):
    w,_=widget
    _feed(w,fs=8192,n=32768)
    w._render_wave()
    assert "Fs=8192" in w.wave_info.text()
    assert "APP_DERIVED" in w.wave_stats.text()
    assert w._cursor_time_samples is not None
    w.adc.setCurrentIndex(w.adc.findData(2))
    w._render_wave()
    assert "АЦП 2" in w.wave_info.text()
    assert "нет отображаемой подтверждённой осциллограммы" in w.wave_info.text()
    assert "Fs=8192" not in w.wave_info.text()
    assert "ожидание подтверждённых АЦП" in w.wave_stats.text()
    assert w._cursor_time_samples is None
    for curve in (w.wave_curve,w.overview_wave_curve):
        xx=curve.getData()[0]
        assert xx is None or len(xx)==0
    assert "Fs и реальные отсчёты не подтверждены" in (
        w._modern_time_setup_info.text())
