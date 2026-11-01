"""Stage111Z.16 Windows Qt: real filename type gating and readable sidebar.

Only synthetic on-disk samples. No instrument, original private sources,
web session, or production measurement archive is used by CI.
"""
from __future__ import annotations

import pytest


def test_qt_imports_direct_bin_tsxml_and_displays_no_fabricated_dsp(
    tmp_path, qt_app,
):
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.direct_bin_session import DirectBinSession
    from .test_stage111z16_direct_bin_tsxml import _make_pair

    source, sidecar, original = _make_pair(tmp_path, adc=4, n=8192)
    win=MainWindow()
    win.open_archive(source)
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()

    assert isinstance(win.session,DirectBinSession)
    assert win.adc.currentText()=="АЦП 4"
    assert win.adc.currentIndex()==3
    assert win.tick.value()==1 and win.tick.maximum()==1
    assert win.tabs.isEnabled()
    assert win.adc.model().item(3).isEnabled()
    assert all(
        not win.adc.model().item(i).isEnabled()
        for i in range(8) if i!=3
    )
    assert "BIN/TSXML" in win.title.text()
    assert "DSP" in win.calc_source.text()
    assert "недоступны" not in win.calc_source.text() or "отсутствуют" in win.calc_source.text()
    assert "не подтверждена" in win.note.text()
    assert win.metrics.item(0,1).text()=="—"
    assert win.oct_table.item(0,1).text()=="—"
    assert win._full_spectrum is not None
    assert len(win._full_spectrum["amplitude"])==4096
    assert win._full_spectrum["physical_units_verified"] is False
    assert len(win.wave_plot.listDataItems())==1
    assert "BIN/TSXML" in win.statusBar().currentMessage()

    assert win.spec_tools.width()==244
    from PySide6.QtCore import Qt
    assert win.spec_tools.horizontalScrollBarPolicy()==Qt.ScrollBarAlwaysOff
    assert win.spec_copy_button.text()=="Копировать"
    assert win.spec_save_button.text()=="Сохранить CSV"
    # Source button captions must fit within the sidebar available width.
    available=win.spec_tools.viewport().width()
    assert available >= 200
    for widget in (
        win.spec_envelope_button,win.spec_mode,win.spec_n,
        win.spec_copy_button,win.spec_save_button,win.spec_hscale_button,
        win.spec_vscale_button,win.spec_original_copy_compare,
    ):
        assert widget.minimumWidth()==0
        assert widget.width() <= available
    win.close()
    qt_app.processEvents()


def test_qt_can_switch_direct_session_to_existing_native_zip_without_fake_dsp(
    tmp_path, qt_app,
):
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.direct_bin_session import DirectBinSession
    from mvk_compatible.core.offline_export import OfflineSession
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    from .test_offline_core import fixture_zip

    source,sidecar,_=_make_pair(tmp_path,adc=4)
    win=MainWindow()
    win.open_archive(sidecar)
    assert isinstance(win.session,DirectBinSession)
    assert "DSP" in win.calc_source.text()
    assert win.adc.currentIndex()==3

    native=fixture_zip(tmp_path)
    win.open_archive(native)
    assert isinstance(win.session,OfflineSession)
    assert not isinstance(win.session,DirectBinSession)
    assert win.adc.currentIndex()==0
    assert all(win.adc.model().item(i).isEnabled() for i in range(8))
    assert win.tick.maximum()==2 and win.tick.value()==2
    assert win.metrics.item(0,1).text()!="—"
    assert win.oct_table.item(0,1).text()!="—"
    assert "Приборный DSP" in win.calc_source.text()
    assert win._full_spectrum is not None
    win.close()
    qt_app.processEvents()


def test_invalid_or_unpaired_direct_bin_does_not_replace_loaded_zip(
    tmp_path,qt_app,monkeypatch,
):
    from PySide6.QtWidgets import QMessageBox
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip

    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    existing=win.session
    invalid=tmp_path/"unpaired.bin"
    invalid.write_bytes(b"\0"*4096)
    messages=[]
    monkeypatch.setattr(QMessageBox,"critical",
                        lambda *args:messages.append(args[2]))
    win.open_archive(invalid)
    assert win.session is existing
    assert messages and "TSXML" in messages[0]
    assert win.adc.currentIndex()==0
    assert win.metrics.item(0,1).text()!="—"
    win.close()
    qt_app.processEvents()
