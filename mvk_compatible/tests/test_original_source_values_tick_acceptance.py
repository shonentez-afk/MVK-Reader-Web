"""Independent Go WriteValues JSONL+source RAW-layout acceptance tests."""
from __future__ import annotations

from hashlib import sha256
import json
import struct

import pytest

from ..core.original_source_values_tick_acceptance import (
    parse_source_values_3100_event,verify_source_values_tick_files,
)


def synthetic_tick(*,frame=2,tick=0):
    word=struct.pack("<f",1.5).hex()
    cells=[
        dict(channel=1,source_list_group="SPEC",source_cell_index=0,
             source_word_address=0x2002,
             raw_dword_le_hex=word,type_candidate="F32_CANDIDATE",
             source_two_words_valid=True),
        dict(channel=1,source_list_group="RESULT",source_cell_index=0,
             source_word_address=0x2120,
             raw_dword_le_hex="51000000",type_candidate="U32_ADVANCED_UNFORMATTED",
             source_two_words_valid=True),
        dict(channel=9,source_list_group="TACH",source_cell_index=5,
             source_word_address=0x30FE,
             raw_dword_le_hex=None,type_candidate="U32_CANDIDATE",
             source_two_words_valid=False),
    ]
    line=("16:24:12.123|RAW_F32_CANDIDATE:"+word+
          "|RAW_U32_ADVANCED_UNFORMATTED:51000000|UNKNOWN\r\n")
    payload=bytes.fromhex("cafebabe")
    return {
        "frame_index":frame,"source_values_tick_index":tick,
        "received_utc":"2026-11-19T13:24:12.123Z",
        "param_address":"0x3100","register_words":2,
        "param_payload_le_hex":payload.hex(),
        "param_payload_sha256":sha256(payload).hexdigest(),
        "source_ordered_raw_tick":{
            "schema":"MVK_SOURCE_VALUES_3100_ORDERED_RAW_TICK_V1",
            "local_source_capture_hh_nn_ss_zzz":"16:24:12.123",
            "original_selected_cell_order":cells,
            "source_known_full_register_dwords":2,
            "unknown_or_unmapped_selected_cells":1,
            "source_raw_layout_line_sha256":sha256(line.encode()).hexdigest(),
            "original_get_value_text_parity_verified":False,
            "original_delphi_local_time_parity_verified":False,
            "original_delphi_values_csv_byte_parity_verified":False,
        },
    },line.encode()


def test_source_3100_record_exact_tick_group_and_original_f32_hex():
    event,row=synthetic_tick()
    result=parse_source_values_3100_event(event)
    assert result["raw_line_bytes"]==row
    assert result["source_ordered_cells"]==3
    assert result["source_valid_raw_dwords"]==2
    assert result["unmapped_or_missing_cells"]==1
    assert not result["original_get_value_text_parity_verified"]


def test_independent_files_sha_per_tick_and_no_raw_paths_in_report(tmp_path):
    events=tmp_path/"source_received.jsonl"
    layout=tmp_path/"source_layout.csv"
    rows=[synthetic_tick(frame=2,tick=0),synthetic_tick(frame=4,tick=1)]
    events.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x,_ in rows))
    layout.write_bytes(b"".join(y for _,y in rows))
    receipt=verify_source_values_tick_files(events,layout)
    assert receipt["accepted_actual_param_3100_ticks"]==2
    assert receipt["source_valid_raw_dwords"]==4
    assert receipt["unmapped_or_missing_cells"]==2
    assert receipt["paired_csv_sha256"]==sha256(layout.read_bytes()).hexdigest()
    assert not receipt["original_delphi_get_value_text_parity_verified"]
    assert "tmp_path" not in json.dumps(receipt)
    mutated=bytearray(layout.read_bytes());mutated[16]^=1
    layout.write_bytes(mutated)
    with pytest.raises(ValueError,match="CSV differs"):
        verify_source_values_tick_files(events,layout)


@pytest.mark.parametrize("edit",[
    lambda x:x.update(param_address="0x2000"),
    lambda x:x.update(param_payload_sha256="0"*64),
    lambda x:x["source_ordered_raw_tick"].update(
        original_delphi_csv_byte_parity_verified=True),
    lambda x:x["source_ordered_raw_tick"]["original_selected_cell_order"][1].
        update(source_word_address=0x3002),
    lambda x:x["source_ordered_raw_tick"]["original_selected_cell_order"][0].
        update(source_word_address=0x3002),
    lambda x:x["source_ordered_raw_tick"]["original_selected_cell_order"][1].
        update(source_two_words_valid=False),
    lambda x:x["source_ordered_raw_tick"]["original_selected_cell_order"].reverse(),
    lambda x:x["source_ordered_raw_tick"].update(
        local_source_capture_hh_nn_ss_zzz="25:01:01.000"),
])
def test_source_tick_validator_rejects_corrupt_reordered_or_false_vendor_parity(edit):
    event,_=synthetic_tick()
    edit(event)
    with pytest.raises(ValueError):
        parse_source_values_3100_event(event)


def test_source_no_false_tick_coverage_and_symlink_block(tmp_path):
    e=tmp_path/"data.jsonl";r=tmp_path/"rows.csv"
    row,line=synthetic_tick()
    e.write_text(json.dumps(row)+"\n"+json.dumps(row)+"\n")
    r.write_bytes(line+line)
    with pytest.raises(ValueError,match="reordered"):
        verify_source_values_tick_files(e,r)
    e.write_text(json.dumps(row)+"\n")
    alias=tmp_path/"alias.csv"
    alias.symlink_to(r)
    with pytest.raises(ValueError,match="symlink"):
        verify_source_values_tick_files(e,alias)
