"""Original one-shot bWriteTable source layout, real local writing.

Synthetic single-receiver PARAM fixture; no device, no private recordings,
no 1:1 Win32 CSV claim. Header/pipe/time shape is checked against
_Unit128:0084E020, while original GetValueText remains explicitly open.
"""
from __future__ import annotations

from datetime import datetime
import re
from types import SimpleNamespace

import pytest

from ..core.native_r6_live_status import validate_live_status
from ..core.original_live_table_snapshot import (
    TABLE_SOURCE, MAX_TABLE_ROWS, live_table_snapshot_ready,
    build_live_table_rows,export_live_table_snapshot,
)
from .test_stage111z26_native_live_status import now
from .test_mode2_original_page_status_param_banks import live_state


def status_with_real_source_banks():
    raw=live_state()
    result=validate_live_status(raw,expected_run=raw["session_id"],now=now())
    assert result["source_live_page_status_banks_verified"]
    return result


def _name(tmp_path, suffix=""):
    return tmp_path/("TABLE-2026-11-19--16-02-15"+suffix+".csv")


def test_one_shot_live_table_uses_only_selected_valid_param_and_pipe_layout(
    tmp_path
):
    status=status_with_real_source_banks()
    assert live_table_snapshot_ready(status)
    selected=(True,)+(False,)*7+(True,False)
    rows=build_live_table_rows(status,selected)
    assert len(rows)==MAX_TABLE_ROWS+3==39
    assert rows[0]==("Параметр (RAW)","АЦП 1","")
    assert rows[31]==()
    assert rows[32]==("Параметр (RAW)","Тахометр 1","")
    assert rows[1][1]=="0x00000051 (RAW)"
    assert rows[1][2]==""    # original Advanced GetUnits is empty
    assert rows[7][1]=="1.5 (RAW)"
    assert rows[7][2]=="м/с2"
    assert rows[-6][1]=="50.5 (RAW)"
    assert rows[-6][2]=="Гц"  # exact original TACH GetUnits
    assert rows[-1][1]=="—"  # no stale +FE TACH pseudo-impulse

    filename=_name(tmp_path)
    receipt=export_live_table_snapshot(
        status,selected,filename,expected_session_id=status["session_id"])
    assert receipt["source"]==TABLE_SOURCE
    assert receipt["source_table_selected_channels"]==[1,9]
    assert receipt["source_table_row_count"]==36
    assert receipt["source_table_section_count"]==2
    assert receipt["source_adc_data_rows"]==30
    assert receipt["source_tach_data_rows"]==6
    assert receipt["source_param_frames"]==3
    assert receipt["source_tcp_connection_count"]==1
    assert receipt["readback_all_rows_verified"]
    assert not receipt["original_delphi_table_byte_parity_verified"]
    assert not receipt["original_get_value_text_parity_verified"]
    assert not receipt["instrument_commands_sent"]
    assert not receipt["original_tmvkthread_write_table_executed"]
    assert not receipt["contains_operator_file_path"]
    import hashlib
    payload=filename.read_bytes()
    assert payload.startswith(b"\xef\xbb\xbfsep=|\r\n")
    assert payload.count(b"\r\n")==40  # sep + 2 headers + separator + 36 data
    assert receipt["csv_sha256"]==hashlib.sha256(payload).hexdigest()
    assert "1.5 (RAW)" in payload.decode("utf-8-sig")
    assert "GetValueText" not in payload.decode("utf-8-sig")
    with pytest.raises(ValueError,match="NEW"):
        export_live_table_snapshot(
            status,selected,filename,expected_session_id=status["session_id"])
    assert filename.read_bytes()==payload


def test_unselected_adcs_and_invalid_source_do_not_mint_live_table(tmp_path):
    status=status_with_real_source_banks()
    # Default selected ADC1 contains values; ADC2 has NO received PARAM.
    second=(False,True)+(False,)*8
    with pytest.raises(ValueError,match="selected channels"):
        export_live_table_snapshot(status,second,_name(tmp_path))
    assert not _name(tmp_path).exists()
    all_off=(False,)*10
    with pytest.raises(ValueError,match="no selected"):
        build_live_table_rows(status,all_off)
    with pytest.raises(ValueError,match="ten original channel flags"):
        build_live_table_rows(status,(True,)*8)
    with pytest.raises(ValueError,match="ten original channel flags"):
        build_live_table_rows(status,(True,)*9+(1,))
    with pytest.raises(ValueError,match="foreign run"):
        export_live_table_snapshot(status,(True,)*10,_name(tmp_path),
                                   expected_session_id="TEST_someone_else")


@pytest.mark.parametrize("change",[
    lambda s:s.update(snapshot_stale=True),
    lambda s:s.update(phase="CONNECTING"),
    lambda s:s.update(phase="COMPLETED"),
    lambda s:s.update(capture_only=True),
    lambda s:s.update(source_tcp_multi_socket=True,source_tcp_connection_count=2),
    lambda s:s.update(source_rate_transition_during_live=True),
    lambda s:s.update(source_system_error_observed=True),
    lambda s:s.update(seconds_since_last_packet=12.0),
    lambda s:s.update(source_live_page_status_banks_verified=False),
    lambda s:s["source_live_page_status_banks"].update(accepted_param_frames=0),
])
def test_live_table_rejects_stale_denied_frozen_or_unverified_evidence(change):
    status=status_with_real_source_banks()
    status=dict(status)
    status["source_live_page_status_banks"]=dict(
        status["source_live_page_status_banks"])
    change(status)
    assert not live_table_snapshot_ready(status)
    with pytest.raises(ValueError,match="no fresh"):
        build_live_table_rows(status,(True,)*10)


@pytest.mark.parametrize("bad",[
    "notes.csv","TABLE-overwrite.csv",
    "TABLE-2026-11-19--16-02-15.csv.bak",
    ".TABLE-2026-11-19--16-02-15.csv",
    "../escape.csv"
])
def test_live_table_requires_original_safe_filename_and_existing_dir(
    tmp_path,bad
):
    status=status_with_real_source_banks()
    dest=tmp_path/bad
    with pytest.raises(ValueError,match="NEW|filename"):
        export_live_table_snapshot(status,(True,)*10,dest)
    assert not dest.exists()


def test_live_table_refuses_symlink_and_nonexistent_folder(tmp_path):
    status=status_with_real_source_banks()
    target=_name(tmp_path)
    target.write_bytes(b"EXISTING_DATA")
    alias=_name(tmp_path,"-1")
    alias.symlink_to(target)
    with pytest.raises(ValueError,match="NEW"):
        export_live_table_snapshot(status,(True,)*10,alias)
    with pytest.raises(ValueError,match="NEW"):
        export_live_table_snapshot(
            status,(True,)*10,tmp_path/"missing"/target.name)
    assert target.read_bytes()==b"EXISTING_DATA"



def test_source_ru_table_uses_original_name_units_and_cp1251_with_no_false_parity(tmp_path):
    from ..core.original_live_table_snapshot import (
        RU_TABLE_CANDIDATE_SOURCE,build_live_ru_table_candidate_rows,
        export_live_ru_table_candidate,
    )
    status=status_with_real_source_banks()
    selected=(True,)+(False,)*7+(True,False)
    rows=build_live_ru_table_candidate_rows(status,selected)
    assert len(rows)==39
    assert rows[0]==("Наименование параметра","АЦП 1","")
    assert rows[1][0]=="Индикатор перегрузки"
    assert rows[1][1]=="Перегрузка" # original +0x120=0x51, Bits 0
    assert rows[2][1]=="(0x00000005)" # not in source Buffers list
    assert rows[3][1]=="ОК"        # SensorState bits10..11==0
    assert rows[7][0]=="Виброускорение, 10..3000 Гц"
    assert rows[7][1]=="1,5"
    assert rows[7][2]=="м/с2"
    assert rows[31]==()
    assert rows[32]==("Наименование параметра","Тахометр 1","")
    assert rows[33][1]=="50,5"
    assert rows[33][2]=="Гц"
    assert rows[-1][1]=="UNKNOWN" # stale +0xFE is not valid live evidence
    p=tmp_path/"TABLE-2026-11-19--16-02-15.csv"
    out=export_live_ru_table_candidate(
        status,selected,p,expected_session_id=status["session_id"])
    payload=p.read_bytes()
    assert out["source"]==RU_TABLE_CANDIDATE_SOURCE
    assert out["csv_encoding_kind"]=="CP1251_CRLF_PIPE_ORIGINAL_LAYOUT_CANDIDATE"
    assert payload.startswith(b"sep=|\r\n")
    assert not payload.startswith(b"\xef\xbb\xbf")
    assert payload.count(b"\r\n")==40
    assert "Перегрузка" in payload.decode("cp1251")
    assert "UNKNOWN" in payload.decode("cp1251")
    assert out["source_table_row_count"]==36
    assert out["readback_all_rows_verified"]
    assert not out["original_delphi_table_byte_parity_verified"]
    assert not out["instrument_commands_sent"]
    import hashlib
    assert out["csv_sha256"]==hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError,match="NEW"):
        export_live_ru_table_candidate(status,selected,p)


def test_source_ru_table_rejects_selected_unreceived_adc(tmp_path):
    from ..core.original_live_table_snapshot import export_live_ru_table_candidate
    status=status_with_real_source_banks()
    # In fixture only ADC 1 has accepted complete result words.
    selected=(False,True)+(False,)*8
    p=tmp_path/"TABLE-2026-11-19--16-02-15.csv"
    with pytest.raises(ValueError,match="no received DWORDs"):
        export_live_ru_table_candidate(status,selected,p)
    assert not p.exists()
