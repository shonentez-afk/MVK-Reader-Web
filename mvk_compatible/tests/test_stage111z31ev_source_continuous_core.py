"""Triple-source Stage111Z31EV: original TMVKThread Task2 has no time cap.

No industrial socket or command is used in these tests.
"""
from __future__ import annotations

import pytest
from ..core.native_r6_bridge import CaptureSpec
from .test_stage111z26_native_live_status import fixture_state, now
from ..core.native_r6_live_status import validate_live_status


def _spec(tmp_path,seconds):
    return CaptureSpec("10.13.42.84","10.13.42.22",seconds,128,tmp_path)


def test_original_mode2_operator_stop_has_real_local_sentinel(tmp_path):
    spec=_spec(tmp_path,0)
    spec.validate()
    assert spec.source_until_stop
    assert "Отключить" in spec.duration_description()
    args=spec.native_args(spec.create_root())
    assert args[args.index("-seconds")+1]=="0"
    assert "-stop-file" in args
    assert "-max-mb" in args and args[args.index("-max-mb")+1]=="128"
    assert "-source-setrate-tx=true" not in args
    assert "-source-task2-reconnect=true" not in args


@pytest.mark.parametrize("duration",[-1,301,True,1.5,"0"])
def test_unbounded_mode_rejects_ambiguous_or_out_of_range_lengths(tmp_path,duration):
    with pytest.raises(ValueError,match="Время записи"):
        _spec(tmp_path,duration).validate()


def test_explicit_duration_keeps_old_native_argv_and_status(tmp_path):
    spec=_spec(tmp_path,30)
    assert not spec.source_until_stop
    assert "на 30 секунд" in spec.duration_description()
    assert spec.native_args(spec.create_root())[5:7]==["-seconds","30"]


def test_unbounded_producer_status_is_accepted_without_fake_success():
    snapshot=fixture_state()
    snapshot["target_seconds"]=0
    checked=validate_live_status(
        snapshot,expected_run=snapshot["session_id"],now=now())
    assert checked["target_seconds"]==0
    assert checked["phase"]=="RECORDING"
    assert checked["read_only_no_app_payload_sent"] is True
    for invalid in (-1,301,True):
        snapshot["target_seconds"]=invalid
        with pytest.raises(ValueError):
            validate_live_status(
                snapshot,expected_run=snapshot["session_id"],now=now())
