"""Stage111Z31BE readonly constructor semantics; fake local data only."""
from dataclasses import dataclass
import pytest
from mvk_compatible.core.original_config_semantics import (
    NETWORK_FIELDS,CALIBRATION_FIELDS,CHANNEL_FIELDS,
    MODBUS_ENDIAN,HF_MODE,AdvancedCell,AdvancedValue,section_fields,
    source_section_rows,source_sections_report,UNKNOWN)
@dataclass(frozen=True)
class Cell:
    formatted:str
class Local:
    def __init__(self,values=None):self.values=values or {}
    def value(self,addr):return self.values.get(addr)
def test_original_layout():
    assert len(NETWORK_FIELDS)==15 and len(CALIBRATION_FIELDS)==10
    assert len(CHANNEL_FIELDS)==11
    assert [x.offset for x in NETWORK_FIELDS]==[
        4,6,8,10,12,20,64,66,68,70,72,74,76,80,96]
    assert [x.offset for x in CALIBRATION_FIELDS]==[
        32,34,36,38,40,42,44,46,18,16]
    assert [x.offset for x in CHANNEL_FIELDS]==[
        2,4,16,32,62,64,66,68,70,82,80]
    assert section_fields("adc",adc=8)[1]==0x800
    for section,adc in (("bad",None),("ip",1),("calib",1),("adc",None),
                        ("adc",True),("adc",0),("adc",9)):
        with pytest.raises(ValueError):section_fields(section,adc=adc)
def test_source_raw_and_secret_fail_closed():
    doc=Local({4:Cell("D:16909060"),0x4a:Cell("D:502"),
               0x60:Cell("S:do-not-display"),
               0x20:Cell("F:0.42"),0x802:Cell("F:1.5")})
    ip=source_section_rows(doc,"ip")
    assert ip[0]["raw_value"]=="D:16909060"
    assert ip[1]["raw_value"]==UNKNOWN
    assert ip[3]["source_min"]=="1" and ip[3]["source_max"]=="65535"
    assert ip[11]["raw_value"]=="D:502"
    assert ip[-1]["sensitive_value_masked"] is True
    assert "do-not-display" not in repr(ip)
    assert all(not x["writable"] and not x["live_device_verified"] for x in ip)
    assert source_section_rows(doc,"calib")[0]["raw_value"]=="F:0.42"
    assert source_section_rows(doc,"calib")[8]["address"]=="0x0012"
    assert source_section_rows(doc,"adc",adc=8)[0]["raw_value"]=="F:1.5"
    report=source_sections_report(doc)
    assert tuple(report[k] for k in (
        "network_fields","calibration_fields","adc_fields",
        "local_fields_present"))==(15,10,88,5)
    assert not report["original_runtime_parity_verified"]
    assert not report["device_writes_allowed"]
def test_advanced_exact_composite_id_link():
    assert [x.id for x in MODBUS_ENDIAN.values]==[0,0x99999999,0x66666666]
    assert MODBUS_ENDIAN.get_index_by_id(0x66666666)==2
    assert MODBUS_ENDIAN.get_index_by_id(0xffffffff)==-1
    assert MODBUS_ENDIAN.get_title_by_id(0xffffffff)=="(0xFFFFFFFF)"
    assert HF_MODE.get_title_by_id(1)=="6.4 кГц"
    exact=AdvancedCell((AdvancedValue(1,"first","link"),
                        AdvancedValue(1,"second","other")))
    assert exact.get_index_by_id(1)==0
    assert exact.get_link_by_id(1)=="link"
    composite=AdvancedCell((AdvancedValue(1,"A"),AdvancedValue(3,"AB"),
                             AdvancedValue(2,"B")),composite=True)
    assert composite.get_title_by_id(3)=="A; AB; B"
    assert composite.get_title_by_id(4)=="---"
    with pytest.raises(IndexError):exact.get_id(2)
    for bad in (-1,2**32,True,"3"):
        with pytest.raises(ValueError):exact.get_index_by_id(bad)
