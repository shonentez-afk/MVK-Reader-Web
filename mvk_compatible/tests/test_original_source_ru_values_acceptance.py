"""Fourth stream source RU+CP1251 acceptance with Go/Python independent paths."""
from __future__ import annotations

from hashlib import sha256
import json
import pytest

from ..core.original_ru_csv_layout import source_ru_values_header
from ..core.original_source_ru_values_acceptance import (
    RU_VERSION,original_source_ru_values_row,verify_original_source_ru_values_files,
)
from .test_original_source_values_text_candidate_acceptance import candidate


def four_file_fixture(tmp_path):
    event,raw,plain=candidate()
    proof=event["source_ordered_raw_tick"]
    cells=proof["original_selected_cell_order"]
    rurow="16:24:12.123|1,5|Перегрузка|UNKNOWN\r\n".encode("cp1251")
    proof["source_ru_profile_candidate_line_sha256"]=sha256(rurow).hexdigest()
    proof["source_ru_profile_candidate_formatter_version"]=RU_VERSION
    header=source_ru_values_header(cells)
    assert original_source_ru_values_row(event)==rurow
    e=tmp_path/"SOURCE_W01_VALUES_3100_RECEIVED.jsonl"
    r=tmp_path/"SOURCE_W01_VALUES_3100_RAW_LAYOUT.csv"
    t=tmp_path/"SOURCE_W01_VALUES_3100_TEXT_CANDIDATE.csv"
    p=tmp_path/"SOURCE_W01_VALUES_3100_RU_PROFILE_CANDIDATE.csv"
    e.write_bytes((json.dumps(event,ensure_ascii=False)+"\n").encode("utf-8"))
    r.write_bytes(raw)
    t.write_bytes(plain)
    p.write_bytes(header+rurow)
    return e,r,t,p,event,header,rurow


def test_real_source_four_files_byte_exact_and_manifest(tmp_path):
    e,r,t,p,event,header,rurow=four_file_fixture(tmp_path)
    audited={
        "windows":[{
            "source_ru_profile_candidate_name":p.name,
            "source_ru_profile_candidate_rows":1,
            "source_ru_profile_candidate_bytes":len(header+rurow),
            "source_ru_profile_candidate_sha256":sha256(header+rurow).hexdigest(),
            "original_ru_profile_csv_byte_parity_verified":False,
        }]
    }
    audit=tmp_path/"SOURCE_LIVE_VALUES_NATIVE_AUDIT.json"
    audit.write_text(json.dumps(audited))
    proof=verify_original_source_ru_values_files(e,r,t,p,audit_json=audit)
    assert proof["actual_param_3100_ticks"]==1
    assert proof["all_four_stream_files_same_run_verified"]
    assert proof["independently_rebuilt_ru_csv_bytes"]==len(header+rurow)
    assert proof["original_header_and_all_rows_sha256"]==sha256(header+rurow).hexdigest()
    assert proof["original_selected_source_fields"]==3
    assert proof["source_cp1251_crlf_pipe_verified"]
    assert not proof["original_delphi_get_value_text_30_byte_parity_verified"]
    assert not proof["physical_mvk01_live_1to1_parity_verified"]
    assert "tmp_path" not in json.dumps(proof)
    assert b"\xef\xbb\xbf" not in p.read_bytes()


@pytest.mark.parametrize("part",["header","text","digest","version","selected_id","manifest"])
def test_source_ru_rejects_header_values_hash_and_audit_mutation(tmp_path,part):
    e,r,t,p,event,header,rurow=four_file_fixture(tmp_path)
    if part=="header":
        p.write_bytes(p.read_bytes().replace(b"sep=|",b"sep=,"))
    elif part=="text":
        p.write_bytes(p.read_bytes().replace("Перегрузка".encode("cp1251"),
                                             "Перегруска".encode("cp1251")))
    else:
        proof=event["source_ordered_raw_tick"]
        if part=="digest":
            proof["source_ru_profile_candidate_line_sha256"]="0"*64
        elif part=="version":
            proof["source_ru_profile_candidate_formatter_version"]="UNKNOWN"
        elif part=="selected_id":
            proof["original_selected_cell_order"][1]["source_advanced_selected_id"]=3
        if part!="manifest":
            e.write_text(json.dumps(event,ensure_ascii=False)+"\n")
    if part=="manifest":
        audit=tmp_path/"SOURCE_LIVE_VALUES_NATIVE_AUDIT.json"
        audit.write_text(json.dumps({"windows":[{
            "source_ru_profile_candidate_name":p.name,
            "source_ru_profile_candidate_rows":4,
            "source_ru_profile_candidate_bytes":len(header+rurow),
            "source_ru_profile_candidate_sha256":sha256(header+rurow).hexdigest(),
            "original_ru_profile_csv_byte_parity_verified":False,
        }]}))
        with pytest.raises(ValueError):
            verify_original_source_ru_values_files(e,r,t,p,audit_json=audit)
    else:
        with pytest.raises(ValueError):
            verify_original_source_ru_values_files(e,r,t,p)


def test_source_ru_rejects_file_from_other_session_directory(tmp_path):
    e,r,t,p,_,_,_=four_file_fixture(tmp_path)
    other=tmp_path/"other";other.mkdir()
    different=other/p.name;different.write_bytes(p.read_bytes())
    with pytest.raises(ValueError,match="different directories"):
        verify_original_source_ru_values_files(e,r,t,different)
