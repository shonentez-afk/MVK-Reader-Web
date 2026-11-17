from __future__ import annotations
import pytest
from ..core.original_mode2_source_rate_input import (
 source_setrate_stdin_line,SOURCE_RATES,
)

def test_qprocess_to_native_go_rate_line_is_real_lf_not_backslash_n():
    for rate in SOURCE_RATES:
        command=source_setrate_stdin_line(rate)
        assert command==f"RATE {rate}\n".encode("ascii")
        assert command.endswith(b"\n") and command.count(b"\n")==1
        assert b"\\n" not in command
        assert not any(byte>127 for byte in command)

@pytest.mark.parametrize("rate",[0,309,777,12345,65537,"65536",True,65536.0])
def test_reject_all_unverified_rates(rate):
    with pytest.raises(ValueError):
        source_setrate_stdin_line(rate)
