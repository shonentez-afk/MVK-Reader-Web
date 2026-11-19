"""Background LIVE FIR GetSignal worker: Qt never blocks on long HTag DSP.

Only immutable authenticated local Go ring bytes and a locally supplied FIR
profile enter this worker. It has NO TCP/RAW/Flash/SetRate/Windows API access.
A SourceLiveFIRWorker is one-shot; interruption discards partial results.
"""
from __future__ import annotations

from PySide6.QtCore import QThread,Signal
from ..core.original_live_getsignal_fir_processing import (
    source_live_filtered_getsignal,source_live_fir_job_key,
    source_live_fir_configuration_key,
)


class SourceLiveFIRWorker(QThread):
    ready=Signal(object)
    failed=Signal(object)

    def __init__(self,window,profile,tag,code,mode=0,parent=None):
        super().__init__(parent)
        self.window=window
        self.profile=profile
        self.tag=tag
        self.code=code
        self.mode=mode
        self.job_key=source_live_fir_job_key(window,tag,code,mode)
        self.configuration_key=source_live_fir_configuration_key(
            window,tag,code)

    def run(self):
        try:
            result=source_live_filtered_getsignal(
                self.window,self.profile,tag=self.tag,code=self.code,
                mode=self.mode,cancelled=self.isInterruptionRequested)
        except InterruptedError:
            return
        except (ValueError,KeyError,TypeError,OSError,RuntimeError,
                OverflowError,MemoryError) as exc:
            if not self.isInterruptionRequested():
                self.failed.emit((self.job_key,str(exc)))
        else:
            if not self.isInterruptionRequested():
                self.ready.emit(result)
