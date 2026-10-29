"""Pure offline model of original TMVKThread Task=2 retry arithmetic.

Source IDR _Unit125.pas: 0x00807CD6 reset PauseValue=25; after disconnect
0x008089C2..0x00808B15 uses compare with 26, round(PauseValue)+1
sleeps of 10 ms, then multiplies by sqrt(2) while PauseValue<801.
Not connected to sockets, not used to auto-transmit commands.
"""
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class RetryStep:
    delay_ms: int
    preview_rate_request_queued: bool
    pause_before: float
    pause_after: float

def preview_retry(pause_value):
    if not math.isfinite(pause_value) or pause_value<0:
        raise ValueError('invalid pause value')
    return RetryStep(
        delay_ms=(round(pause_value)+1)*10,
        preview_rate_request_queued=pause_value<26,
        pause_before=pause_value,
        pause_after=pause_value*math.sqrt(2) if pause_value<801 else pause_value,
    )

def successful_connect_reset():return 25.0
