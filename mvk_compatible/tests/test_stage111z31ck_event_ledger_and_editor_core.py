"""Stage111Z31CK core QA: 95 DFM bindings and real editor arithmetic.

Original operator PAS/DFM/IDP are NOT in this public test.
No Windows original EXE, device, network, user files or software installation.
"""
from collections import Counter
import math
import struct

import pytest

from ..core.original_event_fidelity import (
    SOURCE,original_detailed_event_bindings,original_event_coverage_report,
)
from ..core.original_event_access_control import (
    guard_original_callback_dispatch, classify_handler,
)
from ..core.original_offline_view_state import OriginalOfflineView
from ..core.original_value_recalc import (
    SOURCE as RECALC_SOURCE,
    SOURCE_FACTOR_DECIMAL,source_recalc_millivolt_g,
)


def _f32(value):
    return struct.unpack("<f",struct.pack("<f",float(value)))[0]


def test_every_original_dfm_event_is_accounted_by_all_seven_pages_three_forms():
    events=original_detailed_event_bindings()
    report=original_event_coverage_report()
    assert len(events)==95
    assert report["source"]==SOURCE
    assert report["form_count"]==3
    assert report["page_count"]==7
    assert report["binding_count"]==95
    assert report["unique_handler_count"]==53
    assert report["form_binding_counts"]=={
        "mvkform.dfm":89,"mvkeditform.dfm":5,"WindowManForm.dfm":1}
    assert report["main_form_page_counts"]=={
        "FORM":19,"Pages":1,
        "PageStart":7,"PageConfig":15,"PageStatus":7,
        "PageAdc":7,"PageSpectrum":12,"PageFile":7,"PageCalib":14}
    assert not report["all_native_handlers_automatically_dispatchable"]
    assert not report["all_95_original_behavior_verified"]
    assert not report["original_device_write_authorized"]
    assert report["requires_original_win32_runtime_comparison"]
    assert len({x.source_key for x in events})==len(events)
    assert len(report["bindings"])==95
    assert all(x["device_action_allowed"] is False for x in report["bindings"])
    assert all(x["implemented_1_to_1_verified"] is False
               for x in report["bindings"])
    assert any(x.object_name=="bRecalc" and x.handler=="bRecalcClick"
               for x in events)
    assert any(x.object_name=="sbSpecVScroll"
               and x.handler=="sbSpecVScrollChange" for x in events)
    assert any(x.object_name=="sbSpecHScroll"
               and x.handler=="sbSpecVScrollChange" for x in events)


def test_every_original_handler_is_still_default_deny_even_when_documented():
    seen=set()
    for x in original_detailed_event_bindings():
        key=x.form,x.handler
        if key in seen:
            continue
        seen.add(key)
        with pytest.raises(PermissionError):
            guard_original_callback_dispatch(*key)
        status=classify_handler(*key)
        assert not status["standalone_device_action_allowed"]
        assert not status["safe_automatic_runtime_dispatch"]
    assert len({x.handler for x in original_detailed_event_bindings()})==53


@pytest.mark.parametrize("action,field",[
    ("select_config_tab","config_tab"),
    ("select_file_action_tab","file_action_tab"),
    ("select_calibration_result_tab","calibration_result_tab"),
])
def test_new_source_tab_events_share_one_autonomous_core_without_device(
        action,field):
    state=OriginalOfflineView.initial()
    assert getattr(state,field)==0
    next_state=state.transition(action,1)
    assert getattr(next_state,field)==1
    assert getattr(state,field)==0
    assert next_state.snapshot()[field]==1
    assert not next_state.snapshot()["device_command_issued"]
    restored=next_state.transition(action,0)
    assert getattr(restored,field)==0
    for bad in (-1,2,True,None,"1"):
        with pytest.raises(ValueError):
            state.transition(action,bad)


@pytest.mark.parametrize("text",["1","1,0","2.5","2,5","-3.25","0","1e2","1e-3"])
def test_source_mvkeditform_recalc_single_extended_single_boundary(text):
    report=source_recalc_millivolt_g(text)
    assert report.source==RECALC_SOURCE
    assert report.source_factor==str(SOURCE_FACTOR_DECIMAL)
    assert report.original_single==_f32(float(text.replace(",",".")))
    assert report.converted_single==_f32(
        report.original_single*float(SOURCE_FACTOR_DECIMAL))
    assert not report.original_x87_extended_parity_verified
    assert not report.original_delphi_float_to_str_parity_verified
    assert not report.configuration_mutated
    assert not report.instrument_write_sent
    assert report.formatted_candidate
    if "," in text:
        assert "," in report.formatted_candidate or report.converted_single==0


@pytest.mark.parametrize("invalid",[
    "", " ", "x", "1,2.3","1,2,3","nan","NaN","inf",
    "1 + 2", "1;2","100000000000000000000000e200",
    "9"*81, None, True, 3.5,
])
def test_editor_recalc_rejects_non_original_or_unsafe_text(invalid):
    with pytest.raises(ValueError):
        source_recalc_millivolt_g(invalid)
