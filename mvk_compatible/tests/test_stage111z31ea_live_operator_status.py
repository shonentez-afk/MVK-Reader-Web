"""Source PageStatus operator layout + accepted snapshot lifecycle.

Synthetic register words only. No private source, device connection or
Win32 numerical equivalence is claimed.
"""
import pytest

from ..core.original_live_operator_status import (
    LivePageStatusBinding, source_live_operator_status_projection,
)
from ..core.original_live_result_registers import parse_live_result_registers
from ..core.native_r6_live_status import validate_live_status
from ..core.original_ru_csv_layout import source_ru_advanced_title
from .test_mode2_original_page_status_param_banks import live_state, w, d
from .test_stage111z26_native_live_status import now


def test_operator_source_lists_and_units_not_43_duplicate_table_rows():
    raw=live_state()
    a=raw["source_live_page_status_banks"]["adc"][0]
    a["result_adc_six_raw_dwords_le"]=[
        d(0x51),d(0x51),d(0x51),w(3.3),w(6.5),w(2.0)]
    parsed=parse_live_result_registers(raw)
    for mode,expected in ((2,"1,5"),(3,"2,5"),(4,"3,5")):
        model=source_live_operator_status_projection(mode,parsed).model
        assert len(model.headers)==12 and len(model.rows)==36
        assert all(len(row)==12 for row in model.rows)
        assert model.rows[0][1]==source_ru_advanced_title(0,0x51)
        assert model.rows[1][1]==source_ru_advanced_title(1,0x51)
        assert model.rows[2][1]==source_ru_advanced_title(2,0x51)
        assert model.rows[3][1]=="3,3" and model.rows[3][-1]=="В"
        assert model.rows[4][1]=="6,5" and model.rows[4][-1]=="м/с2"
        assert model.rows[6][1]==expected
        assert model.rows[6][2]=="—"
        assert model.rows[6][9:11]==("","")
        assert model.rows[30][1:9]==("",)*8
        assert model.rows[30][9:]==("50,5","—","Гц")
        assert model.rows[35][9]=="—"
    view=source_live_operator_status_projection(5,parsed)
    assert len(view.model.rows)==30 and len(view.model.headers)==5
    assert view.model.rows[3][1:]==("3,3","","","В")
    assert view.model.rows[6][1:]==("1,5","2,5","3,5","м/с2")
    assert view.model.rows[7][-1]=="мм/с"
    assert view.model.rows[8][-1]=="мкм"
    assert view.chart_visible and len(view.model.bands_for_plot)==43
    assert view.cursor(42)["verified_source_band_value"]==10.75
    assert view.cursor(42)["adc"]==1
    for mode in range(6,13):
        p=source_live_operator_status_projection(mode,parsed)
        assert not p.chart_visible
        assert p.model.rows[6][1:4]==("—",)*3
    t=source_live_operator_status_projection(13,parsed).model
    assert len(t.rows)==6 and len(t.headers)==5
    assert t.rows[0][1:]==("50,5","","","Гц")
    assert t.rows[5][1]=="—"


def test_pending_param_does_not_change_original_grid_shape():
    for mode,rows,cols in [(1,24,9),(2,36,12),(3,36,12),(4,36,12),
                           *((m,30,5) for m in range(5,13)),
                           (13,6,5),(14,6,5)]:
        p=source_live_operator_status_projection(mode,None)
        assert len(p.model.rows)==rows
        assert len(p.model.headers)==cols
        assert not p.chart_visible
        assert all(v in ("","—") for row in p.model.rows
                   for v in (row[1:-1] if mode!=1 else row[1:]))
        assert p.provenance=="SOURCE_LIVE_OPERATOR_UNAVAILABLE"


def test_missing_or_nonfinite_register_not_a_computed_replacement():
    raw=live_state(partial=True)
    a=raw["source_live_page_status_banks"]["adc"][0]
    a["peak_24_raw_f32_le"][0]=d(0x7fc00000)
    p=source_live_operator_status_projection(5,parse_live_result_registers(raw))
    assert not p.chart_visible
    assert p.model.rows[6][1:4]==("1,5","—","3,5")
    assert p.model.rows[3][1]=="—"


@pytest.mark.parametrize("six",[
    [None,d(0x51),None,None,None,None],
    [d(0x52)]*3+[None]*3,
    [None]*6,
])
def test_explicit_adc_advanced_aliases_must_match_one_valid_dword(six):
    raw=live_state()
    raw["source_live_page_status_banks"]["adc"][0]["result_adc_six_raw_dwords_le"]=six
    with pytest.raises(ValueError,match="Source PageStatus"):
        parse_live_result_registers(raw)


def _status(value=1.5,frames=3):
    raw=live_state()
    bank=raw["source_live_page_status_banks"]
    bank["accepted_param_frames"]=frames
    bank["adc"][0]["rms_24_raw_f32_le"][0]=w(value)
    return validate_live_status(raw,expected_run=raw["session_id"],now=now())


def _select(binding,status,**overrides):
    flags=dict(active=True,stop_requested=False,source_fault=False,
               freeze_requested=False)
    flags.update(overrides)
    return binding.select(status,**flags)


def test_one_live_snapshot_freeze_resume_and_clear_at_fault_stop():
    a=_status()
    b=_status(9.5,4)
    binding=LivePageStatusBinding()
    snap=_select(binding,a)
    assert snap is not None and snap is not a
    assert _select(binding,a) is snap
    assert _select(binding,b,freeze_requested=True) is snap
    assert binding.receipt()["accepted_param_frames"]==3
    assert binding.receipt()["display_frozen"]
    assert binding.banks["adc"][0]["rms_24_raw_f32_le"][0]==w(1.5)
    # Local thaw must await actual Go freeze acknowledgement if present.
    acknowledged={**b,"source_original_receive_gate_verified":True,
                  "source_original_receive_gate":{"freeze_update":True}}
    assert _select(binding,acknowledged) is snap
    newest=_select(binding,b)
    assert newest is not snap
    assert binding.banks["adc"][0]["rms_24_raw_f32_le"][0]==w(9.5)
    assert _select(binding,a) is None  # accepted PARAM count rolled back
    assert binding.banks is None
    assert _select(binding,b) is not None
    assert _select(binding,{**b,"seconds_since_last_packet":5.1},
                   freeze_requested=True) is None
    assert binding.receipt() is None
    assert _select(binding,b,freeze_requested=True) is None
    assert _select(binding,b) is not None
    assert _select(binding,b,source_fault=True) is None
    assert _select(binding,b,stop_requested=True) is None
    assert binding.receipt() is None
    assert _select(binding,b,active=False) is None
    assert binding.identity is None


def test_freeze_cannot_inherit_registers_from_foreign_session_or_tcp():
    b=_status()
    binding=LivePageStatusBinding()
    assert _select(binding,b) is not None
    foreign={**b,"session_id":"FOREIGN"}
    assert _select(binding,foreign,freeze_requested=True,
                   expected_session_id=b["session_id"]) is None
    assert binding.banks is None
    assert _select(binding,b) is not None
    another_socket={**b,"source_tcp_connection_count":2}
    assert _select(binding,another_socket,freeze_requested=True) is None
    assert binding.banks is None
