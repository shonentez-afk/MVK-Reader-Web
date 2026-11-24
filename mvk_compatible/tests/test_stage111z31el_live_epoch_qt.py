"""Actual Qt local IPC and LIVE Copy/Save actions, offline only."""
from types import SimpleNamespace

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z31el_live_epoch import epoch_state, validated
from .test_stage111z31fj_original_long_window import response_fixture
from ..core.live_spectrum_triplet import DISCLAIMER
from ..core.original_source_long_window import REQUEST_NAME


def test_qt_local_epoch_recovers_copy_save_and_rejects_modal_staleness(
        qt_app,tmp_path,monkeypatch):
    from ..desktop import main_window
    from ..desktop.native_capture_dialog import NativeCaptureDialog

    w=main_window.MainWindow()
    dlg=NativeCaptureDialog(w)
    try:
        w._begin_live_capture()
        tabs=w.original_root_tabs
        tabs.setCurrentIndex(next(i for i in range(tabs.count())
                                  if tabs.tabData(i)=="PageSpectrum"))
        w.spec_n.setCurrentIndex(w.spec_n.findData(1024))
        w.spec_mode.setCurrentIndex(0)
        dlg._mode="capture"
        dlg._capture_root=tmp_path
        dlg.sourceLongWindowReady.connect(w._receive_source_long_window)
        root,raw,stamp=epoch_state(tmp_path)
        status=validated(raw,stamp)
        w._receive_native_live_status(status)
        dlg._poll_source_long_window(status)
        # Actual UI writes ring IPC to the exact Go run child, not root.
        assert (root/REQUEST_NAME).is_file()
        assert not (tmp_path/REQUEST_NAME).exists()
        request=dlg._source_long_request
        response_fixture(root,status,request,override=lambda payload:payload.update(
            source_range_state=request.source_range_state,source_epoch=request.source_epoch))
        dlg._poll_source_long_window(status)
        assert w._full_spectrum["live_source_epoch"]==request.source_epoch
        assert len(w.spec_plot.listDataItems())==1
        assert w.spec_copy_button.isEnabled() and w.spec_save_button.isEnabled()
        w.spec_copy_button.click()
        assert qt_app.clipboard().text().splitlines()[0]==DISCLAIMER
        assert len(qt_app.clipboard().text().splitlines()[1].split("\t"))==3
        destination=tmp_path/"MVK-COMPATIBLE-LIVE-ADC1.csv"
        monkeypatch.setattr(main_window,"QFileDialog",SimpleNamespace(
            getSaveFileName=lambda *_:(str(destination),"CSV (*.csv)")))
        w.spec_save_button.click()
        assert DISCLAIMER in destination.read_text(encoding="utf-8")

        # A rate/continuity generation change while the file picker runs
        # invalidates precisely the linked SHA window and never writes.
        _,new_raw,stamp=epoch_state(tmp_path,generation=4,create=False)
        renewed=validated(new_raw,stamp)
        stale_dest=tmp_path/"MVK-COMPATIBLE-LIVE-stale.csv"
        def on_choose(*_):
            w._receive_native_live_status(renewed)
            return str(stale_dest),"CSV (*.csv)"
        monkeypatch.setattr(main_window,"QFileDialog",SimpleNamespace(
            getSaveFileName=on_choose))
        w.spec_save_button.click()
        assert not stale_dest.exists()
        assert not w.spec_save_button.isEnabled()
        assert not w.spec_copy_button.isEnabled()
        assert not w.spec_plot.listDataItems()
        # The pending old request is superseded immediately, even at
        # the same ADC, Fs and device index.
        dlg._poll_source_long_window(renewed)
        current=dlg._source_long_request
        assert current.request_id!=request.request_id
        assert current.source_epoch!=request.source_epoch
        response_fixture(root,renewed,current,override=lambda payload:payload.update(
            source_range_state=current.source_range_state,source_epoch=current.source_epoch))
        dlg._poll_source_long_window(renewed)
        assert w.spec_save_button.isEnabled()
        assert not w._source_live_writer.receipt()["write_values_requested"]

        # A user-approved selection must suppress export/plot before
        # Go publishes the next receipt; we simulate only local queueing.
        from PySide6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox,"question",lambda *_:QMessageBox.Yes)
        w._native_dialog=SimpleNamespace(
            source_rate_tx_active=lambda:True, send_source_rate=lambda _:True)
        assert w.source_rate_selected(32768)
        assert w._source_graph_wait_rate==(32768,2)
        assert not w.spec_save_button.isEnabled()
        assert not w.spec_plot.listDataItems()
        w._receive_native_live_status(renewed)
        assert w._source_graph_wait_rate is not None
        assert not w.spec_save_button.isEnabled()
        _,selected_raw,stamp=epoch_state(tmp_path,generation=5,rate=32768,
                                        create=False)
        selected_raw["source_original_receive_gate"]["selection_changes"]=3
        selected=validated(selected_raw,stamp)
        w._receive_native_live_status(selected)
        assert w._source_graph_wait_rate is None
        assert not w.spec_save_button.isEnabled()  # needs full new ring window
        assert not w.spec_plot.listDataItems()
    finally:
        w._native_dialog=None
        dlg._mode=None
        dlg.close()
        if w._live_active:
            w._end_live_capture(False)
        w.close()
        qt_app.processEvents()
