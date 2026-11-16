"""Non-blocking, source-bounded post-Native local write extraction.

No TCP, device command, x32dbg or original vendor file is read from this
worker. It owns only an independently SHA-verified local Native ZIP and a
new subdirectory under that SAME accepted run.
"""
from __future__ import annotations

from PySide6.QtCore import QThread,Signal

from ..core.original_live_write_stages import export_source_write_windows


class SourceWriteWindowExportWorker(QThread):
    ready=Signal(object)
    failed=Signal(str)

    def __init__(self,ledger,flow,parent_folder,parent=None):
        super().__init__(parent)
        self._ledger=ledger
        self._flow=flow
        self._parent_folder=parent_folder

    def run(self):
        try:
            receipt=export_source_write_windows(
                self._ledger,self._flow,self._parent_folder)
        except (OSError,ValueError,KeyError,RuntimeError,
                UnicodeError,OverflowError) as exc:
            self.failed.emit(str(exc))
        else:
            self.ready.emit(receipt)
