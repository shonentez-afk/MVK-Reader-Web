"""Actual PageStatus QTableWidget fed by the same passive Go evidence."""
from __future__ import annotations
import struct
import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from .test_desktop_qt import qt_app
from .test_stage111z31di_qt_live_source_status_cells import inbound
from .test_stage111z31dl_source_15_status_core import visible_field_rows
from ..core.original_system_register_fields import SOURCE_FIELD_KEY

def test_qt_page_status_15_real_registers_without_fake_dsp(qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        snapshot=inbound(value=0)
        snapshot[SOURCE_FIELD_KEY]=visible_field_rows({
            0:struct.pack("<I",0xAABBCCDD),
            2:struct.pack("<I",0),
            3:struct.pack("<I",3661),
            11:struct.pack("<I",72),
        })
        win._receive_native_live_status(snapshot)
        qt_app.processEvents()
        grid=win.original_shell.status_table
        assert grid.rowCount()==15
        assert grid.item(0,1).text()=="0xAABBCCDD"
        assert grid.item(2,1).text()=="0"
        assert grid.item(3,1).text()=="01:01:01"
        assert grid.item(11,1).text()=="72"
        assert grid.item(12,1).text()=="—"
        assert "4/15" in win.original_shell.status_note.text()
        assert win.original_shell.status_page.property("sourceOriginalSystemRowsVerified")==4
        assert win._source_mode2_runtime.receipt()["hardware_commands_sent"]==0
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
