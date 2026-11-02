"""Stage111Z.28B2A: synthetic-only fresh original RAW control word contracts."""
from __future__ import annotations

import copy
import pytest

from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.original_pagestatus_source import source_pagestatus_table
from mvk_compatible.core.control_status_source import SCHEMA,SOURCE
from .test_stage111z28_dsp_tach_ticks import _fixture


def _evidence(*,adc=3,slot=2,frame=52,status=0xA5A50004,value=13.25):
    base=0x2000+(adc-1)*0x200+0x130+(slot-1)*8
    return {
        "adc":adc,"slot":slot,"status_base_word":f"0x{base:04X}",
        "source_frame_index":frame,"raw_value_float32":value,
        "raw_status_u32":status,"raw_status_hex":f"0x{status:08X}",
        "raw_last_transition_float32":1.25,
        "raw_reserved_u32":0xBADC0FFE,
    }


def _control(slots):
    return {
        "schema":SCHEMA,"source":SOURCE,
        "status_frame_fresh_for_tick":True,
        "zone_and_alert_text_verified":False,
        "config_parameter_selection_verified":False,
        "no_initial_snapshot_as_live_status":True,
        "raw_slots":slots,
    }


def _bundle(tmp_path,change=None):
    def mutate(rows):
        rows[0]["control_status"]=_control([_evidence()])
        rows[1]["control_status"]=_control([])  # one capture interval, no carryover
        if change is not None:
            change(rows)
    return _fixture(tmp_path,mutate=mutate)


def test_only_real_dedicated_same_tick_source_may_supply_raw_word(tmp_path):
    session=OfflineSession.open(_bundle(tmp_path))
    first=session.calculations(0)
    c=first["control_status"]
    assert c["available"] and len(c["raw_slots"])==1
    assert c["raw_slots"][0]["adc"]==3
    assert c["raw_slots"][0]["slot"]==2
    assert c["raw_slots"][0]["status_base_word"]=="0x2538"
    assert c["raw_slots"][0]["source_frame_index"]==52
    assert c["zone_and_alert_text_verified"] is False
    assert c["config_parameter_selection_verified"] is False
    table=source_pagestatus_table(1,first)
    assert len(table.rows)==24 and len(table.headers)==9
    assert table.rows[3][3]=="13.25" # slot 2, ADC 3, RAW
    assert table.rows[4][3]=="0xA5A50004 (RAW)" # AlarmState source WORD
    assert table.rows[5][3]=="0xA5A50004 (RAW)" # AlarmAlert SAME WORD
    assert table.rows[4][1]=="—"
    assert "НЕ декодированы" in table.note
    assert source_pagestatus_table(1,None).rows[4][3]=="—"
    second=session.calculations(1)
    assert not second["control_status"]["available"]
    assert second["control_status"]["raw_slots"]==[]
    assert source_pagestatus_table(1,second).rows[4][3]=="—"


@pytest.mark.parametrize("modify",[
    lambda r:r[0]["control_status"].update(schema="V2_UNATTESTED"),
    lambda r:r[0]["control_status"].update(source="INITIAL_FULL_SNAPSHOT_ONLY"),
    lambda r:r[0]["control_status"].update(zone_and_alert_text_verified=True),
    lambda r:r[0]["control_status"].update(config_parameter_selection_verified=True),
    lambda r:r[0]["control_status"].update(no_initial_snapshot_as_live_status=False),
    lambda r:r[0]["control_status"]["raw_slots"][0].update(source_frame_index=0),
    lambda r:r[0]["control_status"]["raw_slots"][0].update(source_frame_index=55),
    lambda r:r[0]["control_status"]["raw_slots"][0].update(status_base_word="0x2130"),
    lambda r:r[0]["control_status"]["raw_slots"][0].update(raw_status_u32=5),
    lambda r:r[0]["control_status"]["raw_slots"][0].update(raw_value_float32=1.1),
    lambda r:r[0]["control_status"]["raw_slots"][0].update(raw_last_transition_float32=float("nan")),
    lambda r:r[0]["control_status"]["raw_slots"][0].update(slot=0),
    lambda r:r[0]["control_status"]["raw_slots"].append(
        copy.deepcopy(r[0]["control_status"]["raw_slots"][0])),
    lambda r:r[1]["control_status"]["raw_slots"].append(_evidence(frame=52)),
])
def test_corrupt_forged_or_stale_control_provenance_rejected(tmp_path,modify):
    session=OfflineSession.open(_bundle(tmp_path,modify))
    with pytest.raises(ValueError,match="CONTROL_STATUS"):
        session.calculations(0)


def test_old_export_does_not_auto_diagnose_fictitious_normals(tmp_path):
    session=OfflineSession.open(_fixture(tmp_path))
    d=session.calculations(0)
    assert not d["control_status"]["available"]
    assert d["control_status"]["raw_slots"]==[]
    table=source_pagestatus_table(1,d)
    assert all(value=="—" for row in table.rows for value in row[1:])
