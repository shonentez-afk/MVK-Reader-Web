"""Independent Go RAW JSONL + RAW layout + text-candidate three-file checks."""
from __future__ import annotations

from hashlib import sha256
import json
import pytest

from ..core.original_source_values_text_candidate_acceptance import (
    SOURCE_TEXT_FORMATTER_VERSION, expected_source_text_candidate_row,
    verify_source_values_text_candidate_files,
)
from .test_original_source_values_tick_acceptance import synthetic_tick


def candidate():
    event,raw=synthetic_tick()
    cells=event["source_ordered_raw_tick"]["original_selected_cell_order"]
    for cell in cells:
        if cell["source_list_group"]=="RESULT":
            cell["source_cell_type"]=10
            cell["source_advanced_selected_id"]=1
        elif cell["type_candidate"]=="F32_CANDIDATE":
            cell["source_cell_type"]=0
        else:
            cell["source_cell_type"]=2
    text="16:24:12.123|1.5|UNRESOLVED_ADVANCED_ID_1|UNKNOWN\r\n".encode()
    proof=event["source_ordered_raw_tick"]
    proof["source_text_candidate_formatter_version"]=SOURCE_TEXT_FORMATTER_VERSION
    proof["source_text_candidate_line_sha256"]=sha256(text).hexdigest()
    return event,raw,text


def test_python_source_candidate_matches_independent_go_text_types():
    event,_,row=candidate()
    assert expected_source_text_candidate_row(event)==row
    assert b"RAW_" not in row
    assert event["source_ordered_raw_tick"]["original_selected_cell_order"][1][
        "source_advanced_selected_id"]==1


def test_three_actual_files_are_stream_verified(tmp_path):
    e=tmp_path/"incoming.jsonl"
    r=tmp_path/"source_layout.csv"
    t=tmp_path/"source_text.csv"
    ev,raw,text=candidate()
    e.write_text(json.dumps(ev,ensure_ascii=False)+"\n")
    r.write_bytes(raw)
    t.write_bytes(text)
    receipt=verify_source_values_text_candidate_files(e,r,t)
    assert receipt["source_three_files_verified"]
    assert receipt["actual_param_3100_ticks"]==1
    assert receipt["candidate_csv_sha256"]==sha256(text).hexdigest()
    assert not receipt["original_delphi_text_parity_verified"]
    assert not receipt["original_win32_ansi_csv_byte_parity_verified"]
    assert not receipt["physical_mvk01_e2e_verified"]
    assert "tmp_path" not in json.dumps(receipt)
    t.write_bytes(text.replace(b"1.5",b"1.6"))
    with pytest.raises(ValueError,match="text"):
        verify_source_values_text_candidate_files(e,r,t)


@pytest.mark.parametrize("mutate",[
    lambda e:e["source_ordered_raw_tick"].update(
        source_text_candidate_line_sha256="0"*64),
    lambda e:e["source_ordered_raw_tick"].update(
        source_text_candidate_formatter_version="WRONG_V2"),
    lambda e:e["source_ordered_raw_tick"]["original_selected_cell_order"][1].update(
        source_advanced_selected_id=2),
    lambda e:e["source_ordered_raw_tick"]["original_selected_cell_order"][0].update(
        source_cell_type=2),
    lambda e:e["source_ordered_raw_tick"]["original_selected_cell_order"][0].update(
        source_advanced_selected_id=1),
    lambda e:e["source_ordered_raw_tick"]["original_selected_cell_order"][2].update(
        source_cell_type=0),
])
def test_reject_forged_vendor_formatter_proof(mutate):
    ev,_,_=candidate()
    mutate(ev)
    with pytest.raises(ValueError):
        expected_source_text_candidate_row(ev)


def test_missing_selected_words_remain_unknown_without_pseudo_advanced_id():
    ev,_,row=candidate()
    ev["source_ordered_raw_tick"]["original_selected_cell_order"][1][
        "raw_dword_le_hex"]=None
    ev["source_ordered_raw_tick"]["original_selected_cell_order"][1][
        "source_two_words_valid"]=False
    del ev["source_ordered_raw_tick"]["original_selected_cell_order"][1][
        "source_advanced_selected_id"]
    proof=ev["source_ordered_raw_tick"]
    proof["source_known_full_register_dwords"]-=1
    proof["unknown_or_unmapped_selected_cells"]+=1
    newraw=b"16:24:12.123|RAW_F32_CANDIDATE:0000c03f|UNKNOWN|UNKNOWN\r\n"
    proof["source_raw_layout_line_sha256"]=sha256(newraw).hexdigest()
    newtext=b"16:24:12.123|1.5|UNKNOWN|UNKNOWN\r\n"
    proof["source_text_candidate_line_sha256"]=sha256(newtext).hexdigest()
    assert expected_source_text_candidate_row(ev)==newtext
