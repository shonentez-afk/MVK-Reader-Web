"""Stage111Z31BB: default-deny DFM/IDR action-safety coverage for 3 forms.

Source mapping uses only the previous published SANITIZED structural
inventory. An original DFM handler with an address is NOT automatically
an implemented function. Unsafe, unknown and hardware-oriented actions
are not dispatched even when a similarly named Qt control is present.
"""
from __future__ import annotations

from collections.abc import Mapping

from .original_offline_view_state import OriginalOfflineView,SAFE_TRANSITIONS

SOURCE="SOURCE_DERIVED_ORIGINAL_DFM_EVENT_DEFAULT_DENY_STAGE111Z31BB"

# Exact event name and attached form; no heuristic "contains Config" may
# silently authorize an original device command.
READONLY_UI_EVENTS=frozenset((
    ("mvkform.dfm","PagesChange"),
    ("mvkform.dfm","tcAnyChange"),
    ("mvkform.dfm","cbFileChannelsClick"),
    ("mvkform.dfm","mSpecType1Click"),
    ("mvkform.dfm","mSpecHScale1Click"),
    ("mvkform.dfm","mSpecVScale1Click"),
    ("mvkform.dfm","mSpecLines1Click"),
    ("mvkform.dfm","mAdcHScale1Click"),
    ("mvkform.dfm","mAdcVScale1Click"),
    ("mvkform.dfm","pbAdcPaint"),
    ("mvkform.dfm","pbSpectrumPaint"),
    ("mvkform.dfm","pbAdcMouseMove"),
    ("mvkform.dfm","pbSpectrumMouseMove"),
    ("mvkform.dfm","chResultMouseMove"),
    ("mvkform.dfm","sbSpecVScrollChange"),
    ("mvkform.dfm","tbViewTimeChange"),
    ("mvkform.dfm","tabDrawCell"),
    ("mvkform.dfm","FormResize"),
    ("mvkform.dfm","bAnyDropDownClick"),
))
# Explicit local save/selection: needs user's file chooser; not automatic.
LOCAL_FILE_USER_ACTION_EVENTS=frozenset((
    ("mvkform.dfm","bTaskViewClick"),
    ("mvkform.dfm","bConfigLoadClick"),
    ("mvkform.dfm","bConfigSaveClick"),
    ("mvkform.dfm","bSpecCopyValueClick"),
    ("mvkform.dfm","bSpecSaveValueClick"),
    ("mvkform.dfm","bWriteAdcClick"),
    ("mvkform.dfm","bWriteTableClick"),
    ("mvkform.dfm","bWriteValuesClick"),
    ("mvkform.dfm","edLibraryPathAfterDialog"),
))
# Not authorized in autonomous offline reconstruction: original may
# communicate with hardware, change calibration or edit instrument state.
DEVICE_OR_CALIBRATION_GATED=frozenset((
    ("mvkform.dfm","bTaskConnectClick"),
    ("mvkform.dfm","bTaskConfigCalibClick"),
    ("mvkform.dfm","bTaskConfigIPClick"),
    ("mvkform.dfm","bConfigDownloadClick"),
    ("mvkform.dfm","bConfigUploadClick"),
    ("mvkform.dfm","bConfigResetClick"),
    ("mvkform.dfm","bCalibStartClick"),
    ("mvkform.dfm","bCalibSaveClick"),
    ("mvkform.dfm","bCalibClearClick"),
    ("mvkform.dfm","bCalibGenerateClick"),
    ("mvkform.dfm","bCalibAClick"),
    ("mvkform.dfm","mRate1Click"),
    ("mvkform.dfm","tmConfigResultTimer"),
    ("mvkform.dfm","tmInterfaceUpdateTimer"),
))
# Source field changes are NOT safe until all side effects in original
# call graph are established; runtime dispatch must be default-deny.
CONFIG_MUTATION_UNVERIFIED=frozenset((
    ("mvkform.dfm","bTaskConfigChClick"),
    ("mvkform.dfm","tabConfigAlarmsDblClick"),
    ("mvkform.dfm","tabConfigBasicDblClick"),
    ("mvkform.dfm","tabConfigChannelsDblClick"),
    ("mvkform.dfm","tabKeyPress"),
    ("mvkform.dfm","cbFileFolderPrefixClick"),
    ("mvkform.dfm","cbFileMvkNameClick"),
    ("mvkeditform.dfm","bOkClick"),
    ("mvkeditform.dfm","bRecalcClick"),
))
CLASSES=(
    ("READONLY_UI_SOURCE_EVIDENCE_ONLY",READONLY_UI_EVENTS),
    ("LOCAL_USER_CONFIRMATION_REQUIRED",LOCAL_FILE_USER_ACTION_EVENTS),
    ("DEVICE_OR_CALIBRATION_DEFAULT_DENY",DEVICE_OR_CALIBRATION_GATED),
    ("UNVERIFIED_CONFIGURATION_DEFAULT_DENY",CONFIG_MUTATION_UNVERIFIED),
)


def classify_handler(form:str,handler:str)->dict:
    """Source-derived classification, NOT runtime implementation coverage."""
    if not isinstance(form,str) or not isinstance(handler,str):
        raise ValueError("Original form/handler must be string names")
    matches=[category for category,group in CLASSES if (form,handler) in group]
    if len(matches)>1:
        raise ValueError("Ambiguous source event classification")
    if not matches:
        category="NOT_TRACED_OR_RESTORED_DEFAULT_DENY"
    else:
        category=matches[0]
    return {
        "source":SOURCE,"form":form,"handler":handler,
        "category":category,
        "implemented_original_behavior_verified":False,
        "standalone_device_action_allowed":False,
        "safe_automatic_runtime_dispatch":False,
        "needs_explicit_local_user_action":(
            category=="LOCAL_USER_CONFIRMATION_REQUIRED"),
    }


def build_original_event_coverage(inventory:Mapping)->dict:
    """Enumerate every DFM event and every proven dynamic FOnClick."""
    if (not isinstance(inventory,Mapping)
            or inventory.get("schema")!="MVKVIEW_ORIGINAL_STRUCTURAL_INVENTORY_V1"):
        raise ValueError("Use only the source-derived, sanitized BA metadata")
    forms=inventory.get("forms")
    if not isinstance(forms,Mapping) or len(forms)!=3:
        raise ValueError("Expected exactly the three original DFM forms")
    result={}
    for form,details in sorted(forms.items()):
        if not isinstance(details,Mapping):
            raise ValueError("Invalid source form metadata")
        handlers=details.get("bound_handler_addresses")
        if not isinstance(handlers,Mapping):
            raise ValueError("No original source handler address map")
        dynamic=details.get("dynamic_menu_handlers_source_derived",{})
        if not isinstance(dynamic,Mapping):
            raise ValueError("Invalid dynamic menu mapping")
        per_form={}
        for handler,va in handlers.items():
            if (not isinstance(handler,str) or not isinstance(va,str)
                    or len(va)!=8 or not all(c in "0123456789ABCDEFabcdef" for c in va)):
                raise ValueError("Missing source handler/VA")
            per_form[handler]={**classify_handler(form,handler),
                               "original_idr_method_va":va,
                               "dfm_direct_event_handler":True}
        for handler,evidence in dynamic.items():
            if handler in per_form:
                raise ValueError("Dynamic menu handler duplicated in DFM")
            va=evidence.get("method_va")
            if not isinstance(va,str) or len(va)!=8:
                raise ValueError("Unrecognized dynamic menu original address")
            per_form[handler]={**classify_handler(form,handler),
                               "original_idr_method_va":va,
                               "dfm_direct_event_handler":False,
                               "source_dynamic_fonclick_evidence":True}
        result[form]=per_form
    return result


def guard_original_callback_dispatch(form:str,handler:str)->None:
    """All original callbacks are gated; explicit safe views use Core API."""
    c=classify_handler(form,handler)
    raise PermissionError(
        "Original callback cannot execute without a proven route: "+
        c["category"]+" "+form+"."+handler)


def dispatch_offline_view_action(
        state:OriginalOfflineView,action:str,value)->OriginalOfflineView:
    """Explicit source safe-transition API, NOT a generic DFM callback."""
    if not isinstance(state,OriginalOfflineView):
        raise ValueError("Autonomous view state is required")
    if action not in SAFE_TRANSITIONS:
        raise PermissionError("Not an authorized source view action")
    return state.transition(action,value)
