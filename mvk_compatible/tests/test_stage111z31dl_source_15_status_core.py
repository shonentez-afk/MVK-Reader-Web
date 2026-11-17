"""Full 15 visible source-cell availability, original widths and strict overlap."""
from __future__ import annotations
import struct
import pytest

from ..core.original_system_register_fields import (
    SYSTEM_SOURCE_FIELDS,SOURCE_FIELD_KEY,parse_source_system_registers,
    verify_source_error_overlap,
)
from ..core.original_mode2_status_cells import SOURCE_INDEX_ADDR,SOURCE_STATUS_FIELD
from ..core.original_connected_status import connected_system_status
from .test_stage111z31cz_source_write_stages_core import source_status,RUN


def visible_field_rows(values=None):
    values=values or {}
    rows=[]
    for i,(key,addr,words) in enumerate(SYSTEM_SOURCE_FIELDS):
        raw=values.get(i)
        assert raw is None or len(raw)==words*2
        rows.append(dict(index=i,key=key,register_address=addr,word_count=words,
                         valid=raw is not None,raw_hex_le=raw.hex() if raw is not None else None))
    return rows


def test_original_system_15_offsets_and_unknowns():
    expected=[0x1000,0x1004,0x1006,0x1008,0x100A,0x100C,
              0x1014,0x1014,0x1016,0x1016,0x1024,0x1036,
              0x103A,0x103C,0x103E]
    assert [addr for _,addr,_ in SYSTEM_SOURCE_FIELDS]==expected
    p={SOURCE_FIELD_KEY:visible_field_rows()}
    rows=parse_source_system_registers(p)
    assert len(rows)==15
    assert all(not f.valid and f.value()=="—" for f in rows)


def test_actual_register_bytes_render_and_do_not_invent_delphi_enums():
    values={0:struct.pack("<I",0x12345678),2:struct.pack("<I",0),
            3:struct.pack("<I",3661),4:struct.pack("<I",4096),
            5:bytes.fromhex("00112233445566778899aabbccddeeff"),
            6:struct.pack("<I",3),7:struct.pack("<I",3),
            11:struct.pack("<I",51)}
    snapshot=source_status(session=RUN,adc_samples=512,aux=2,frames=90,raw=53000)
    snapshot[SOURCE_FIELD_KEY]=visible_field_rows(values)
    result=connected_system_status(snapshot)
    assert result.rows[0][1]=="0x12345678"
    assert result.rows[1][1]=="—"
    assert result.rows[2][1]=="0"
    assert result.rows[3][1]=="01:01:01"
    assert result.rows[4][1]=="4096"
    assert result.rows[5][1]=="00112233445566778899AABBCCDDEEFF"
    assert result.rows[6][1]==result.rows[7][1]=="0x00000003"
    assert result.rows[11][1]=="51"
    assert result.source_fields_proven==8
    assert result.receipt()["original_device_system_fields_proven"]==8


def test_page_system_error_is_same_register_as_source_statuscells0():
    payload={"read_only_no_app_payload_sent":True,
             SOURCE_FIELD_KEY:visible_field_rows({2:struct.pack("<I",0x1234)}),
             SOURCE_STATUS_FIELD:[
                dict(index=i,register_address=addr,valid=i==0,
                     value_uint32=0x1234 if i==0 else None)
                for i,addr in enumerate(SOURCE_INDEX_ADDR)]}
    verify_source_error_overlap(payload)
    payload[SOURCE_STATUS_FIELD][0]["value_uint32"]=0
    with pytest.raises(ValueError,match="0x1006"):
        verify_source_error_overlap(payload)


def test_incomplete_misordered_and_false_shared_evidence_rejected():
    base=visible_field_rows()
    for altered in (
        base[:-1],
        [dict(e) for e in base],
    ):
        if len(altered)==15:
            altered[7]["valid"]=True
            altered[7]["raw_hex_le"]="00000000"
        with pytest.raises(ValueError):
            parse_source_system_registers({SOURCE_FIELD_KEY:altered})
    broken=visible_field_rows()
    broken[5]["valid"]=True
    broken[5]["raw_hex_le"]="00"*14
    with pytest.raises(ValueError,match="incomplete|invalid|Partial"):
        parse_source_system_registers({SOURCE_FIELD_KEY:broken})
