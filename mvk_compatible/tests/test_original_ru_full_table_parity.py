"""Source-shaped synthetic full TABLE reconstruction; no instrument CSV rows."""
from __future__ import annotations

from hashlib import sha256
import pytest

from ..core.original_ru_csv_layout import (
    source_ru_cell_title,source_ru_values_header,source_ru_table_rows,
    source_ru_encode_csv,
)
from ..core.original_values_table_pair_qa import verify_full_table_byte_rebuild


def files(tmp_path, *,repeat=False,other_date=False):
    adc=[1,3,6]
    selected=[{"channel":ch,"source_list_group":group,"source_cell_index":i}
              for ch in adc
              for group,n in (("SPEC",43),("RESULT",6),("BAND",24))
              for i in range(n)]
    header=source_ru_values_header(selected)
    # Mock values, not copied from any real device.
    values=[["0"]*43+["ОК","ОК","ОК","11,2","0","0"]+["1,5"]*24
            for _ in adc]
    other=[v.copy() for v in values]
    other[0][-1]="9,1"
    def stream_line(at,matrix):
        return (at+"|"+"|".join(x for row in matrix for x in row)+"\r\n").encode("cp1251")
    original=header+stream_line("10:12:01.623",other)+stream_line("10:12:02.623",values)
    if repeat: original+=stream_line("10:12:03.123",values)
    vp=tmp_path/"VALUES-2026-10-28--10-11-33.csv"
    tp=tmp_path/("TABLE-2026-10-29--10-12-02.csv" if other_date else
                 "TABLE-2026-10-28--10-12-02.csv")
    vp.write_bytes(original)
    table=source_ru_encode_csv(source_ru_table_rows(adc,[],[
        row[43:] for row in values],[]))
    tp.write_bytes(table)
    return vp,tp,table


def test_snapshot_build_matches_all_table_bytes_not_just_90_numeric_cells(tmp_path):
    values,table,actual=files(tmp_path)
    proof=verify_full_table_byte_rebuild(values,table)
    assert proof["original_values_table_unique_snapshot_verified"]
    assert proof["full_table_bytes_equal"]
    assert proof["full_table_length"]==len(actual)
    assert proof["full_table_sha256"]==sha256(actual).hexdigest()
    assert not proof["original_delphi_formatfloat_all_inputs_verified"]
    assert not proof["original_delphi_input_register_parity_verified"]
    assert not proof["private_original_values_embedded"]


def test_unit_and_final_crlf_difference_not_silently_accepted(tmp_path):
    values,table,actual=files(tmp_path)
    table.write_bytes(actual.replace(
        "м/с2".encode("cp1251"),"M/S2".encode("cp1251"),1))
    proof=verify_full_table_byte_rebuild(values,table)
    assert proof["original_values_table_unique_snapshot_verified"]
    assert not proof["full_table_bytes_equal"]
    assert proof["full_table_length"]==len(actual)


@pytest.mark.parametrize("repeat,other_date",[(True,False),(False,True)])
def test_ambiguous_or_different_day_is_not_forged_same_capture(
        tmp_path,repeat,other_date):
    values,table,_=files(tmp_path,repeat=repeat,other_date=other_date)
    proof=verify_full_table_byte_rebuild(values,table)
    assert not proof["original_values_table_unique_snapshot_verified"]
    assert not proof["full_table_bytes_equal"]
