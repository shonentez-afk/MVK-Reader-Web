"""Stage111Z31BB full source DFM event coverage, default-deny hardware.

Tests target sanitized structural metadata, never private PAS/DFM/IDP.
"""
import json
from pathlib import Path

import pytest

from mvk_compatible.core.original_offline_view_state import OriginalOfflineView
from mvk_compatible.core.original_event_access_control import (
    build_original_event_coverage, classify_handler,
    guard_original_callback_dispatch, dispatch_offline_view_action,
    SOURCE,
)

ROOT=Path(__file__).resolve().parents[2]
SOURCE_META=ROOT/"docs/research/STAGE111Z31BA_FULL_IDR_STRUCTURE_METADATA.json"


def test_all_original_55_dfm_plus_seven_dynamic_methods_accounted_for():
    inventory=json.loads(SOURCE_META.read_text(encoding="utf-8"))
    contract=build_original_event_coverage(inventory)
    assert set(contract)=={
        "mvkform.dfm","mvkeditform.dfm","WindowManForm.dfm"}
    assert len(contract["mvkform.dfm"])==57
    assert len(contract["mvkeditform.dfm"])==4
    assert len(contract["WindowManForm.dfm"])==1
    assert sum(len(form) for form in contract.values())==62
    assert sum(e["dfm_direct_event_handler"] for form in contract.values()
               for e in form.values())==55
    assert sum(not e["dfm_direct_event_handler"] for form in contract.values()
               for e in form.values())==7
    assert all(not e["implemented_original_behavior_verified"]
               for form in contract.values() for e in form.values())
    assert all(not e["standalone_device_action_allowed"]
               for form in contract.values() for e in form.values())


@pytest.mark.parametrize("form,handler",[
    ("mvkform.dfm","bConfigUploadClick"),
    ("mvkform.dfm","bConfigDownloadClick"),
    ("mvkform.dfm","bConfigResetClick"),
    ("mvkform.dfm","bCalibStartClick"),
    ("mvkform.dfm","mRate1Click"),
    ("mvkform.dfm","tmInterfaceUpdateTimer"),
    ("mvkeditform.dfm","bOkClick"),
    ("WindowManForm.dfm","bOkClick"),
])
def test_original_sensitive_callbacks_remain_default_denied(form,handler):
    info=classify_handler(form,handler)
    assert info["source"]==SOURCE
    assert not info["safe_automatic_runtime_dispatch"]
    with pytest.raises(PermissionError):
        guard_original_callback_dispatch(form,handler)


def test_all_seven_safe_page_transitions_use_portable_core_not_dfm_cb():
    state=OriginalOfflineView.initial()
    for page in ("PageStart","PageConfig","PageStatus","PageAdc",
                 "PageSpectrum","PageFile","PageCalib"):
        state=dispatch_offline_view_action(state,"select_page",page)
        assert state.page==page
    with pytest.raises(PermissionError):
        dispatch_offline_view_action(state,"device_calibration_start",True)
    with pytest.raises(PermissionError):
        dispatch_offline_view_action(state,"bConfigResetClick",True)
    with pytest.raises(ValueError):
        dispatch_offline_view_action(object(),"select_page","PageStart")


def test_coverage_fails_closed_without_original_source_metadata():
    with pytest.raises(ValueError):
        build_original_event_coverage({"forms":{}})
    m=json.loads(SOURCE_META.read_text(encoding="utf-8"))
    m["forms"]["mvkform.dfm"]["bound_handler_addresses"][
        "bTaskViewClick"]="BAD"
    with pytest.raises(ValueError):
        build_original_event_coverage(m)
    m["forms"]["mvkform.dfm"]["bound_handler_addresses"][
        "bTaskViewClick"]="00848E84"
    m["forms"]["mvkform.dfm"]["dynamic_menu_handlers_source_derived"][
        "PagesChange"]={"method_va":"00840000"}
    with pytest.raises(ValueError):
        build_original_event_coverage(m)
