"""Source-local TACH tests: synthetic Go RX -> actual VALUES -> Python proof."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import pytest
from ..core.original_local_tach_latch import TachLatch, SCHEMA, GATE_NAME
from ..core.original_param_gate_proof import SOURCE_PARAM_GATE_NAME
from ..core.original_values_3100_timeline import scan_original_values_3100
from ..core.original_live_values_proof import verify_original_live_values
from ..core.original_live_result_registers import parse_live_result_registers,source_live_status_projection
from .test_mode2_original_page_status_param_banks import live_state


def test_tach_byte_latch_preserves_last_and_partial_words():
    s=TachLatch()
    data=bytearray(0x8000)
    valid=bytearray(0x4000)
    s.sample(0,b"\x01\x00\x03\x03")
    assert s.projection(data,valid)[0]==(3,"01000000")
    s.tick()
    s.sample(0,b"\x03"*4)
    assert s.projection(data,valid)[0]==(3,"00000000")
    assert s.projection(data,valid)[1]==(3,"00000000")
    addr=0x30ff
    data[addr*2:addr*2+2]=b"\x78\x56"
    valid[addr]=1
    s.block(addr,2)
    assert s.projection(data,valid)[0]==(1,"00007856")
    s.sample(0,b"\x03\x01")
    assert s.projection(data,valid)[0]==(3,"01000000")


def test_pagestatus_reads_validated_local_projection_not_legacy_wire():
    raw=live_state()
    banks=raw["source_live_page_status_banks"]
    banks["source_local_tach_projection_schema"]=SCHEMA
    tach=banks["tach"][0]
    tach["source_local_tach_word_mask"]=3
    tach["source_field_0_2_4_6_8_fe_raw_le"][5]="01000000"
    checked=parse_live_result_registers(raw)
    assert checked["tach"][0]["source_field_0_2_4_6_8_fe_raw_le"][5]=="01000000"
    assert source_live_status_projection(13,checked).model.rows[5][2]=="0x00000001 (RAW)"
    tach["source_field_0_2_4_6_8_fe_raw_le"][5]="02000000"
    with pytest.raises(ValueError,match="local TACH DWORD"):
        parse_live_result_registers(raw)
    tach["source_local_tach_word_mask"]=0
    assert parse_live_result_registers(raw)["tach"][0]["source_field_0_2_4_6_8_fe_raw_le"][5] is None


@pytest.fixture
def actual_tach_run(tmp_path):
    root=os.getenv("MVK_PREFIX_FIXTURE_DIR")
    if not root:
        pytest.skip("Go-generated local TACH fixture available in cross-language CI")
    path=Path(root)/"tach"/"TEST_2026-11-24_05-00-00.000"
    assert path.is_dir()
    return Path(shutil.copytree(path,tmp_path/path.name))


def replay(run,summary):
    return scan_original_values_3100(run/"incoming.raw",
        expected_sha256=summary["raw_sha256"],
        expected_raw_bytes=summary["raw_bytes"],
        expected_frames=summary["frames_decoded"],
        expected_aux=summary["aux4700_updates"],
        expected_ticks=summary["values_ticks_address_3100"],
        expected_tail_bytes=summary["incomplete_final_frame_bytes"],
        ranges=[(1,0,2)],capture_register_prefix=True,
        param_gate_path=run/SOURCE_PARAM_GATE_NAME,
        expected_param_gate_sha256=summary["source_original_param_gate_sha256"],
        expected_param_gate_records=summary["source_original_param_gate_records"],
        expected_frozen_param_frames=summary.get("source_original_param_frames_skipped_frozen",0),
        expected_frozen_aux=summary.get("source_original_aux4700_skipped_frozen",0),
        expected_frozen_values=summary.get("source_original_values_3100_skipped_frozen",0),
        tach_gate_path=run/GATE_NAME,
        expected_tach_gate_sha256=summary["source_local_tach_gate_sha256"],
        expected_tach_gate_records=summary["source_local_tach_gate_records"])


def test_actual_go_tach_values_and_independent_python_replay(actual_tach_run):
    run=actual_tach_run
    summary=json.loads((run/"summary.json").read_text())
    events=replay(run,summary)
    assert [e["_register_prefix"].dword_hex(0x30fe,current=True) for e in events[1]]==["01000000","00000000"]
    assert [e["_register_prefix"].dword_hex(0x31fe,current=True) for e in events[1]]==["01000000","00000000"]
    qt=SimpleNamespace(channels=(False,)*8+(True,True),spec=(False,)*43,
        values=tuple(i==35 for i in range(73)),start_source_values_ticks=0,end_source_values_ticks=2)
    receipt=verify_original_live_values(run,summary=summary,
        source_sha=summary["raw_sha256"],qt_values_windows=[(1,qt)],replayed_events=events)
    assert receipt["verified_events"]==2
    assert receipt["source_trigger_prefix_registers_verified"]


def test_tach_gate_rehashed_wrong_rate_freeze_refused(actual_tach_run):
    run=actual_tach_run
    summary=json.loads((run/"summary.json").read_text())
    path=run/GATE_NAME
    lines=path.read_text().splitlines()
    row=json.loads(lines[0]);row["freeze_update"]=True
    lines[0]=json.dumps(row)
    content=("\n".join(lines)+"\n").encode()
    path.write_bytes(content)
    summary["source_local_tach_gate_sha256"]=sha256(content).hexdigest()
    with pytest.raises(ValueError,match="RAW/gate mismatch"):
        replay(run,summary)
