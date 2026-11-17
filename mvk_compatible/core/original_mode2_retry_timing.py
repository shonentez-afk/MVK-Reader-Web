"""Actual TMVKThread Task=2 reconnect BACKOFF, as an OFFLINE plan only.

Private source _Unit125.pas:
- 00807C24 ConnectTimeout = 0x3e8 = 1000 ms
- 00807C34 ReadTimeout = 0x1388 = 5000 ms
- 00807CD9 initial PauseValue Single = 25.0
- 008089B0..008089BF after failure Task==2 sets Stage=0
- 008089C5..008089F3 if PauseValue < 26, synchronizes
  00809364 (QueueCommand(1,0x0E,MvkSampleRate)) once
- 00808A45 PauseValue/100 formatted as waiting seconds
- 00808AAF..00808ADA (Round(PauseValue)+1) sleeps in 10 ms units
- 00808ADD..00808B0E if PauseValue < 801, multiplies by sqrt(2)
  and stores back in Win32 Single.

This pure Core model performs NO network I/O. Go can execute separately
approved Task2 TCP reconnect even without SetRate writes. Multiple socket
segments have independent SHA256 and cannot certify a merged source BIN.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct

SOURCE = "IDR_TMVKTHREAD_008089A3_00808B0E_TASK2_RETRY_OFFLINE"
SOURCE_CONNECT_TIMEOUT_MS = 1000
SOURCE_READ_TIMEOUT_MS = 5000
START_PAUSE_CENTISECONDS = 25.0
SOURCE_REQUEUE_THRESHOLD = 26.0
SOURCE_GROWTH_CEILING = 801.0
# Distinct Sleep(10) counts reached by the original Win32 Single field.
# 800 < 801, so the last sqrt(2) multiplication overshoots to ~1131.37.
SOURCE_BACKOFF_WAITS_MS = (
    260, 360, 510, 720, 1010, 1420,
    2010, 2840, 4010, 5670, 8010, 11320,
)


def _single(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


@dataclass(frozen=True)
class SourceRetryStep:
    ordinal: int
    pause_before_centiseconds: float
    local_wait_ms: int
    source_requeues_set_rate: bool
    pause_after_centiseconds: float

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "source_failed_attempt": self.ordinal,
            "source_pause_value_before": self.pause_before_centiseconds,
            "source_wait_ms": self.local_wait_ms,
            "source_code_requeues_setrate": self.source_requeues_set_rate,
            "source_pause_value_after": self.pause_after_centiseconds,
            "compatible_go_auto_reconnect_performed": False,
            "device_command_sent": False,
        }


class OriginalSourceRetryPlan:
    def __init__(self):
        self.pause_centiseconds=START_PAUSE_CENTISECONDS
        self.attempts=0
        self.last_step: SourceRetryStep | None=None

    def connected(self):
        # Source 00807CD9 resets PauseValue after each *actual* connect.
        self.pause_centiseconds=START_PAUSE_CENTISECONDS

    def after_failure(self) -> SourceRetryStep:
        self.attempts+=1
        before=self.pause_centiseconds
        ms=10*(round(before)+1)  # Delphi @ROUND, then 00808ABE INC
        after=_single(before*math.sqrt(2.0)) if before<SOURCE_GROWTH_CEILING else before
        self.pause_centiseconds=after
        self.last_step=SourceRetryStep(
            self.attempts,before,ms,before<SOURCE_REQUEUE_THRESHOLD,after)
        return self.last_step

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "original_connect_timeout_ms": SOURCE_CONNECT_TIMEOUT_MS,
            "original_read_timeout_ms": SOURCE_READ_TIMEOUT_MS,
            "source_pause_start_centiseconds": START_PAUSE_CENTISECONDS,
            "source_backoff_sqrt2_until_801": True,
            "source_last_pause_overshoots_to_single_1131": True,
            "source_stable_max_wait_ms": 11320,
            "source_task2_attempts_modeled": self.attempts,
            "source_pause_current_centiseconds": self.pause_centiseconds,
            "last_step": self.last_step.receipt() if self.last_step else None,
            "automated_hardware_retry_enabled": False,
            "device_command_sent": False,
        }
