"""Stage111Z31BC Qt E2E File -> Signal -> Spectrum -> Status source flow.

Only temporary synthetic Native R6.1 ZIP and BIN/TSXML; no hardware,
original MVKView or x32dbg. Exercises actual MainWindow callbacks.
"""
import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from mvk_compatible.core.offline_measurement_flow import (
    OfflineMeasurementFlow, SOURCE_ZIP, SOURCE_BIN,
)
from mvk_compatible.core.direct_bin_session import DirectBinSession


def test_four_original_pages_share_same_zip_session_channel_and_values(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    w.open_archive(fixture_zip(tmp_path,sample_count=4096))
    qt_app.processEvents()
    try:
        assert w.session is not None
        flow=w._offline_flow
        assert isinstance(flow,OfflineMeasurementFlow)
        assert flow.session is w.session
        assert flow.channel==1
        assert flow.tick_index==w.tick.value()-1
        assert flow.source_record()["measurement_kind"]==SOURCE_ZIP
        assert w.original_shell.file_channels.count()==8
        assert "VALUES tick" in w.original_shell.file_source_evidence.text()
        assert w._pagestatus_snapshot is not None
        assert w._pagestatus_snapshot["tick"]==flow.tick_index
        assert w._full_spectrum["channel"]==1
        assert w.original_shell.file_values.count()==1
        assert "VALUES" in w.original_shell.file_values.item(0).text()
        assert w.original_shell.status_table.rowCount()>0

        # A single UI channel selection updates File/Signal/FFT/Status;
        # it cannot silently return old ADC1 or a different ZIP.
        w.adc.setCurrentIndex(6)
        qt_app.processEvents()
        current=w._current_offline_flow()
        assert current.session is w.session
        assert current.channel==7
        assert "АЦП7" in w.original_shell.file_source_evidence.text()
        assert w._full_spectrum["channel"]==7
        assert w._pagestatus_snapshot["channels"][6]["channel"]==7
        assert w.original_shell.file_channels.currentItem().data(
            Qt.UserRole)==7

        # A status tick is not an FFT re-computation or a change of BIN.
        before=np.asarray(w._full_spectrum["amplitude"],
                          dtype="<f4").view("<u4").copy()
        w.tick.setValue(1)
        qt_app.processEvents()
        selected=w._current_offline_flow()
        assert selected.tick_index==0
        assert w._pagestatus_snapshot["tick"]==0
        assert w._pagestatus_snapshot["serial"]==w.session.serial
        np.testing.assert_array_equal(
            np.asarray(w._full_spectrum["amplitude"],
                       dtype="<f4").view("<u4"),before)
        assert w.original_shell.status_table.rowCount()>0
    finally:
        w.close()
        qt_app.processEvents()


def test_direct_bin_switch_clears_all_old_zip_status_without_fake_dsp(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    zip_path=fixture_zip(tmp_path,sample_count=4096)
    p,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    w=MainWindow()
    w.show()
    w.open_archive(zip_path)
    qt_app.processEvents()
    assert w._pagestatus_snapshot is not None
    assert w.original_shell.file_channels.count()==8
    w.open_archive(p)
    qt_app.processEvents()
    try:
        assert isinstance(w.session,DirectBinSession)
        assert w._current_offline_flow().direct_bin
        assert w._current_offline_flow().channel==4
        assert w._current_offline_flow().available_channels==(4,)
        assert w.adc.currentIndex()==3
        assert w.wave_channel_tabs.currentIndex()==3
        assert w.spec_channel_tabs.currentIndex()==3
        for tab in (w.wave_channel_tabs,w.spec_channel_tabs):
            assert tab.isTabEnabled(3)
            assert sum(tab.isTabEnabled(i) for i in range(tab.count()))==1
        assert w._current_offline_flow().session is w.session
        assert w._pagestatus_snapshot is None
        assert w.original_shell.file_channels.count()==1
        assert w.original_shell.file_channels.currentItem().data(
            Qt.UserRole)==4
        assert "DSP НЕТ" in w.original_shell.file_source_evidence.text()
        assert "VALUES/AUX" in w.calc_source.text()
        assert w.original_shell.status_table.rowCount()>0
        assert not w.original_shell.status_plot.isVisible()
        assert w._full_spectrum["channel"]==4
        assert w._full_spectrum["physical_units_verified"] is False
        assert w._offline_flow.status_snapshot() is None

        w._close_session()
        qt_app.processEvents()
        assert w.session is None and w._offline_flow is None
        assert w.original_shell.file_channels.count()==0
        assert "не выбрано" in w.original_shell.file_source_evidence.text()
        assert w._pagestatus_snapshot is None
    finally:
        w.close()
        qt_app.processEvents()


def test_rejected_new_values_tick_never_leaves_old_source_bands_visible(
        tmp_path,qt_app,monkeypatch):
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.offline_export import OfflineSession
    w=MainWindow()
    w.show()
    w.open_archive(fixture_zip(tmp_path,sample_count=4096))
    qt_app.processEvents()
    assert w._pagestatus_snapshot is not None
    assert w.original_shell.status_table.rowCount()>1
    errors=[]
    monkeypatch.setattr(w,"_error",lambda e:errors.append(str(e)))

    # A real ZIP's require_members/VALUES read has strict SHA checks.
    # Simulate that rejection on the subsequent tick with zero private data.
    def rejected(self,tick=-1):
        raise ValueError("Source VALUES changed since the previous tick")
    monkeypatch.setattr(OfflineSession,"calculations",rejected)
    w.tick.setValue(1)
    w.refresh_calc()
    qt_app.processEvents()
    try:
        assert errors
        assert w._pagestatus_snapshot is None
        assert "отклонён" in w.calc_source.text()
        assert "недоступен" in w.calc_status.text()
        assert "не принят" in w.dsp_tach_status.text()
        assert "нет проверенного текущего DSP" in next(
            iter(w.status_fields.values()))[1].text()
        assert w.original_shell.status_table.rowCount()==1
        assert not w.original_shell.status_plot.isVisible()
    finally:
        w.close()
        qt_app.processEvents()
