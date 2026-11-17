"""The only allowed Qt→Go local stdin command for original Task2 SetRate.

No instrument connection: the consumer is the already-running, separately
approved QProcess and the only actual Go TCP/10230 socket owner.
"""
from __future__ import annotations

SOURCE_RATES=(65536,32768,8192,2048,512)

def source_setrate_stdin_line(rate:int)->bytes:
    if type(rate) is not int or rate not in SOURCE_RATES:
        raise ValueError("Unknown original source sampling rate")
    return ("RATE "+str(rate)+"\n").encode("ascii")
