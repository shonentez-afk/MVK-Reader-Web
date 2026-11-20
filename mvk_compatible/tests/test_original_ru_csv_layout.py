"""No operator files in tests: source 28 Oct original column/header fingerprints.

Only original header SHA256 is retained (5554 bytes, no measurements).
The source user VALUES/TABLE data is never committed to the repository.
"""
from __future__ import annotations
import hashlib
import pytest

from ..core.original_ru_csv_layout import (
    PROFILE,source_ru_cell_title,source_ru_encode_csv,
    source_ru_values_header,source_ru_advanced_title,
    source_ru_typed_text,source_ru_table_rows,
)
from ..core.original_get_value_text_30 import live_get_units


def selected_three_original_adc():
    return [
        {"channel":channel,"source_list_group":group,"source_cell_index":i}
        for channel in (1,3,6)
        for group,n in (("SPEC",43),("RESULT",6),("BAND",24))
        for i in range(n)
    ]


def test_original_20261028_header_5554_bytes_and_sha_only():
    fields=selected_three_original_adc()
    b=source_ru_values_header(fields)
    assert len(fields)==219
    assert len(b)==5554
    assert hashlib.sha256(b).hexdigest()==(
        "faf529700f0a597d44e112cdd9459634748f56119f0469adc882e189603ef467")
    assert b.startswith(b"sep=|\r\n")
    assert not b.startswith(b"\xef\xbb\xbf")
    assert b.count(b"\r\n")==3
    assert b.count(b"\x00")==0
    text=b.decode("cp1251")
    assert "АЦП 1" in text and "АЦП 6" in text
    assert "Полоса 0.63 Гц" in text
    assert "Полоса 10000 Гц" in text
    assert "Виброперемещение, Польз. 2" in text
    assert "Параметр (RAW)" not in text
    assert PROFILE.startswith("MVK_ORIGINAL_RU_")


def test_ru_advanced_and_source_numeric_types():
    assert source_ru_advanced_title(0,0x51)=="Перегрузка"
    assert source_ru_advanced_title(1,0x51)=="(0x00000005)"
    assert source_ru_advanced_title(2,0x51)=="ОК"
    assert source_ru_advanced_title(1,0x70)=="Идет заполнение (1, 4, 32 с)"
    assert source_ru_advanced_title(2,0x800)=="КЗ линии"
    assert source_ru_typed_text("RESULT",0,"51000000")=="Перегрузка"
    assert source_ru_typed_text("RESULT",1,"51000000")=="(0x00000005)"
    assert source_ru_typed_text("RESULT",2,"51000000")=="ОК"
    assert source_ru_typed_text("BAND",0,"0000c03f")=="1,5"
    assert source_ru_typed_text("SPEC",0,"cdcccc3d")=="0,1"
    assert source_ru_typed_text("TACH",2,"ffffffff")=="4294967295"
    assert source_ru_typed_text("TACH",5,None)=="UNKNOWN"
    assert source_ru_typed_text("SPEC",4,None)=="UNKNOWN"


def test_source_ru_tach_header_and_table_selection():
    choices=[
        {"channel":1,"source_list_group":"RESULT","source_cell_index":0},
        {"channel":9,"source_list_group":"TACH","source_cell_index":0},
        {"channel":9,"source_list_group":"TACH","source_cell_index":2},
    ]
    b=source_ru_values_header(choices)
    assert b.decode("cp1251").splitlines()[1]==(
        "|АЦП 1|Тахометр 1|Тахометр 1")
    assert b.decode("cp1251").splitlines()[2]==(
        "Время|Индикатор перегрузки|Частота вращения|Ошибка датчика оборотов")
    adcs=[["ОК"]*30,["ОК"]*30]
    tachs=[["0"]*6]
    rows=source_ru_table_rows([1,3],[1],adcs,tachs)
    assert len(rows)==39
    assert rows[0]==("Наименование параметра","АЦП 1","АЦП 3","")
    assert rows[1]==("Индикатор перегрузки","ОК","ОК","")
    assert rows[31]==()
    assert rows[32]==("Наименование параметра","Тахометр 1","")
    assert rows[-6]==("Частота вращения","0","Гц")
    assert rows[-1]==("Наличие импульсов на входе","0","")
    assert len(source_ru_encode_csv(rows).split(b"\r\n"))==41


def test_source_ru_reject_invalid_or_corrupt_input():
    data=selected_three_original_adc()
    with pytest.raises(ValueError,match="order"):
        source_ru_values_header(data[::-1])
    with pytest.raises(ValueError,match="group"):
        source_ru_cell_title("OTHER",0)
    with pytest.raises(ValueError):
        source_ru_typed_text("SPEC",1,"NOT_DWORD")
    with pytest.raises(ValueError):
        source_ru_encode_csv([("a|b",)])
    with pytest.raises(UnicodeEncodeError):
        source_ru_encode_csv([("💾",)])
    with pytest.raises(ValueError,match="order"):
        source_ru_table_rows([3,1],[],[["0"]*30]*2,[])
    with pytest.raises(ValueError,match="DWORD"):
        source_ru_advanced_title(0,1<<33)
