"""Mode2 paired acceptance now includes BOTH original VALUES and TABLE CSV.

Entirely synthetic; never adds original operator numeric values or private
instrument files to CI. Matching files alone NEVER prove original RX input.
"""
from __future__ import annotations

from hashlib import sha256
import pytest

from ..core.original_mode2_paired_acceptance import (
    KINDS,compare_original_mode2_pair,
)
from ..core.original_ru_csv_layout import (
    source_ru_values_header,source_ru_table_rows,source_ru_encode_csv,
)


def _pair(tmp_path):
    original=tmp_path/"original"
    candidate=tmp_path/"candidate"
    original.mkdir();candidate.mkdir()
    fields=[
        {"channel":1,"source_list_group":group,"source_cell_index":i}
        for group,n in (("SPEC",43),("RESULT",6),("BAND",24))
        for i in range(n)
    ]
    values=["0"]*43+["ОК","ОК","ОК","10,62","0","0"]+["1,5"]*24
    stream=source_ru_values_header(fields)+(
        "10:12:02.623|"+"|".join(values)+"\r\n").encode("cp1251")
    table=source_ru_encode_csv(source_ru_table_rows(
        [1],[],[values[43:]],[]))
    names={"VALUES_CSV":"VALUES-2026-10-28--10-11-33.csv",
           "TABLE_CSV":"TABLE-2026-10-28--10-12-02.csv"}
    for kind,content in (("VALUES_CSV",stream),("TABLE_CSV",table)):
        for folder in (original,candidate):
            (folder/names[kind]).write_bytes(content)
    pairs=[{"kind":k,"reference_name":v,"candidate_name":v}
           for k,v in names.items()]
    return original,candidate,pairs,table


def test_original_table_and_values_can_both_be_compared_byte_for_byte(tmp_path):
    assert "TABLE_CSV" in KINDS and "VALUES_CSV" in KINDS
    a,b,pairs,table=_pair(tmp_path)
    report=compare_original_mode2_pair(
        a,b,files=pairs,session_id="test-source-run-1")
    assert report["file_pairs_compared"]==2
    assert report["all_pairs_byte_identical"]
    assert not report["same_input_tcp_raw_verified"]
    assert not report["original_delphi_compatibility_verified"]
    assert not report["original_hardware_parity_verified"]
    assert not report["original_1_to_1_release_gate_passed"]
    assert {r["kind"] for r in report["pairs"]}=={"VALUES_CSV","TABLE_CSV"}
    row=next(r for r in report["pairs"] if r["kind"]=="TABLE_CSV")
    assert row["byte_identical"]
    assert row["reference_file_sha256"]==sha256(table).hexdigest()
    assert row["first_different_byte"] is None
    assert str(a) not in str(report)
    assert "1,5" not in str(report)


def test_table_one_byte_change_fails_without_claiming_different_rx(tmp_path):
    a,b,pairs,table=_pair(tmp_path)
    name=pairs[-1]["candidate_name"]
    edited=table.replace("м/с2".encode("cp1251"),
                         "м/с3".encode("cp1251"),1)
    assert edited!=table
    (b/name).write_bytes(edited)
    report=compare_original_mode2_pair(
        a,b,files=pairs,session_id="test-source-run-1")
    assert not report["all_pairs_byte_identical"]
    assert report["file_pairs_compared"]==2
    table_row=next(x for x in report["pairs"] if x["kind"]=="TABLE_CSV")
    assert not table_row["byte_identical"]
    assert table_row["first_different_byte"] is not None
    assert not report["same_input_tcp_raw_verified"]


def test_paired_kind_rejects_unknown_and_repeated_table(tmp_path):
    a,b,pairs,_=_pair(tmp_path)
    with pytest.raises(ValueError,match="unsupported"):
        compare_original_mode2_pair(
            a,b,files=[dict(pairs[0],kind="TSXML_UNKNOWN")],
            session_id="test-source-run-1")
    with pytest.raises(ValueError,match="duplicate"):
        compare_original_mode2_pair(
            a,b,files=[pairs[-1],pairs[-1]],session_id="test-source-run-1")
