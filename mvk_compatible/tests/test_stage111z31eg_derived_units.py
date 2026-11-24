"""GetDerivedUnits source dispatch and snapshot-local units."""
import pytest
from ..core.mvk_original_scale_tables_idr_candidate import (
    source_derived_units,source_spectrum_unit_contract,original_physical_y_caption)
from ..core.original_source_ring_receipt import source_live_units_text,source_status_channel_units
from .test_stage111z31ef_config_frange import state

@pytest.mark.parametrize("units,expected",[
 ("м/с2",("м/с2","м/с2","мм/с","мкм")),
 ("V",("V","V","~V","~~V")),
 ("m/s2",("m/s2","m/s2","~m/s2","~~m/s2")),
 ("М/с2",("М/с2","М/с2","~М/с2","~~М/с2")),
 ("",("","","~","~~")),
 (None,(None,None,None,None))])
def test_source_derived_units_exact_dispatch(units,expected):
    assert tuple(source_derived_units(i,units) for i in range(4))==expected

def test_db_y_and_linear_summary_are_distinct():
    r=source_spectrum_unit_contract(0,"V",source_bound=True)
    assert r["unit"]=="дБ" and r["source_summary_unit"]=="V"
    assert r["source_derived_units"]=="V"
    assert source_spectrum_unit_contract(2,"V",source_bound=True)["unit"]=="~V"
    assert original_physical_y_caption(3,10,units="~~V")=="10 ~~V"
    assert not source_spectrum_unit_contract(1,None,source_bound=True)["source_unit_text_known"]
    assert source_spectrum_unit_contract(1,None,source_bound=True)["unit"]!="м/с²"

def test_chart_units_use_status_adc_and_validated_range():
    a=state(channel=1);b=state(channel=2)
    a["units_raw_le"]=b"V".ljust(32,b"\x00").hex()
    b["units_raw_le"]=b"g".ljust(32,b"\x00").hex()
    rows=[dict(source_range_state=a),dict(source_range_state=b)]+[{}]*8
    snapshot=dict(source_original_storage_verified=True,source_original_storage={"channels":rows})
    assert source_status_channel_units(snapshot,1)=="V"
    assert source_status_channel_units(snapshot,2)=="g"
    rows[1]["source_range_state"]=a
    assert source_status_channel_units(snapshot,2) is None
    assert source_status_channel_units({},1) is None

def test_explicit_codepage_never_guess_russian():
    s=state()
    s["units_raw_le"]="м/с2".encode("cp1251").ljust(32,b"\x00").hex()
    assert source_live_units_text(s) is None
    assert source_live_units_text(s,windows_ansi_code_page="cp1251")=="м/с2"
    assert source_derived_units(3,source_live_units_text(s,windows_ansi_code_page="cp1251"))=="мкм"
