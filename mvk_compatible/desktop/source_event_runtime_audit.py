"""Stage111Z31CK: observational Qt audit of ALL source DFM event identities.

Every event has an original source ledger row, but an objectName match
does NOT prove a signal is connected, a handler works or that numeric
results match a running original MVKView. Unknown original events stay
default-denied by Core; this module NEVER invokes a native callback.

Can inspect optional editor and WindowManForm without opening device,
modal dialogs, network connections or changing external files.
"""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QPushButton

from ..core.original_event_fidelity import (
    SOURCE,original_detailed_event_bindings,
)
from ..core.original_ui_form_contract import ORIGINAL_ROOT_PAGES

DANGEROUS_CONFIG_BUTTONS=(
    "bConfigDownload","bConfigUpload","bConfigReset")
DANGEROUS_CALIB_BUTTONS=("bCalibStart",)


def audit_live_source_event_controls(window,*,editor=None,windowman=None):
    """Find actual widgets for every 95-source-DMF event identity.

    The individual results are "found" or "missing"; only specifically
    audited routes can have an explicit "safe_offline" assertion in QA.
    A native Delphi TTimer, TStringGrid paint handler or menu-action
    need not correspond to a same-name Qt QObject in a faithful app.
    """
    root=window.original_root_tabs
    names=tuple(p.object_name for p in ORIGINAL_ROOT_PAGES)
    if root.count()!=7 or tuple(root.tabData(i) for i in range(7))!=names:
        raise ValueError("Original source seven-page Qt navigation drift")
    lookup={
        "mvkform.dfm":window,
        "mvkeditform.dfm":editor,
        "WindowManForm.dfm":windowman,
    }
    events=[]
    for entry in original_detailed_event_bindings():
        form=lookup[entry.form]
        if form is None:
            available=False
        elif entry.object_name in ("mvkform","mvkeditform",
                                    "WindowManForm"):
            available=True
        elif entry.object_name=="Pages":
            available=root.objectName()=="Pages"
        else:
            available=bool(form.findChildren(QObject,entry.object_name))
        events.append({
            "form":entry.form,"page":entry.page,
            "control":entry.object_name,"event":entry.event_property,
            "handler":entry.handler,"qt_object_present":available,
            "native_delphi_signal_invocable":False,
            "original_handler_behavior_verified":False,
        })
    missing=[e for e in events if not e["qt_object_present"]]
    unsafe_buttons={}
    for name in DANGEROUS_CONFIG_BUTTONS:
        control=window.original_config_panel.page.findChild(QPushButton,name)
        if control is None:
            raise ValueError("Source hardware config control missing: "+name)
        unsafe_buttons[name]=not control.isEnabled()
        if control.isEnabled():
            raise PermissionError("Hardware config action must stay disabled")
    for name in DANGEROUS_CALIB_BUTTONS:
        control=window.original_calib_panel.page.findChild(QPushButton,name)
        if control is None:
            raise ValueError("Source hardware CALIB control missing: "+name)
        unsafe_buttons[name]=not control.isEnabled()
        if control.isEnabled():
            raise PermissionError("Unverified physical calibration enabled")
    start=window.original_start_controller
    if start.buttons["bTaskConfigCalib"].isEnabled():
        raise PermissionError("Unverified original calibration route unlocked")
    # The source bTaskConnect opens a SEPARATE consent-gated dialog,
    # not the original hardware connection. Never activate it here.
    routes={
        "root_seven_pages":root.count()==7,
        "config_tabs":window.original_config_panel.page_tabs.count()==2,
        "file_actions":window.original_shell.file_action_tabs.count()==2,
        "calibration_result_tabs":window.original_calib_panel.tabs.count()==2,
        "status_modes":window.original_shell.status_tabs.count()==15,
        "calibration_steps":window.original_calib_panel.steps.count()==49,
        "no_device_command_issued":window.source_view_state.snapshot()[
            "device_command_issued"] is False,
        "unsafe_buttons_disabled":all(unsafe_buttons.values()),
    }
    return {
        "source":SOURCE,"schema":"MVKVIEW_SOURCE_DFM_QT_OBSERVATION_V1",
        "total_bindings":len(events),
        "qt_control_present_count":len(events)-len(missing),
        "qt_control_missing_count":len(missing),
        "missing_source_objects":tuple(sorted(set(
            (e["form"],e["control"]) for e in missing))),
        "per_form_present":dict(Counter(
            e["form"] for e in events if e["qt_object_present"])),
        "per_form_missing":dict(Counter(
            e["form"] for e in missing)),
        "observed_routes":routes,
        "hardware_guards":unsafe_buttons,
        "original_running_process_invoked":False,
        "original_95_behavior_verified":False,
        "source_events":[*events],
    }
