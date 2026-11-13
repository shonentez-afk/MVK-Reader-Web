"""Stage111Z31CL original runtime TTabSheet visibility: NOT all seven tabs.

Operator's original Win32 screenshot with an open measurement (13.11.2026)
shows ONLY Tasks, Time signal, Spectrum. The original Delphi source
_Unit128:0084709E..008470F8 initially hides six pages. Other four DFM
TTabSheets still exist and are reachable through source task mode.
No original device/registry or other side effects; this is a pure model.

The Qt compatible "technical" mode is explicitly NOT original and
reveals all seven to retain local Calib/Status/Config/File workbenches.
"""
from __future__ import annotations

from .original_ui_form_contract import ORIGINAL_ROOT_PAGES

SOURCE="SOURCE_DERIVED_ORIGINAL_TABS_INITIAL_AND_ARCHIVE_STAGE111Z31CL"
PAGES=tuple(p.object_name for p in ORIGINAL_ROOT_PAGES)
ORIGINAL_IDLE_VISIBLE=("PageStart",)
ORIGINAL_ARCHIVE_VISIBLE=("PageStart","PageAdc","PageSpectrum")
_SOURCE_ROUTE_PAGES=frozenset(PAGES)


def original_runtime_visible_pages(
        *, has_measurement:bool, technical:bool=False,
        current_page:str="PageStart") -> tuple[str,...]:
    if type(has_measurement) is not bool or type(technical) is not bool:
        raise ValueError("Runtime tab visibility needs strict booleans")
    if not isinstance(current_page,str) or current_page not in PAGES:
        raise ValueError("Current original DFM page is required")
    if technical:
        return PAGES
    visible=set(ORIGINAL_ARCHIVE_VISIBLE if has_measurement
                else ORIGINAL_IDLE_VISIBLE)
    # An EXPLICIT source PageStart operation can enter e.g. Config or
    # PageFile without making unrelated internal TTabSheets visible.
    # This is compatible navigation, not a native runtime claim.
    if current_page not in visible:
        visible.add(current_page)
    return tuple(page for page in PAGES if page in visible)


def original_runtime_tab_contract(
        *,has_measurement:bool,technical:bool=False,
        current_page:str="PageStart")->dict:
    visible=original_runtime_visible_pages(
        has_measurement=has_measurement,technical=technical,
        current_page=current_page)
    return {
        "source":SOURCE,"all_form_pages":PAGES,
        "visible":visible,"visible_count":len(visible),
        "startup_only_one_tab":not has_measurement and not technical
            and current_page=="PageStart",
        "archive_only_three_default":has_measurement and not technical
            and current_page in ORIGINAL_ARCHIVE_VISIBLE,
        "technical_mode_is_source_original":False,
        "all_seven_handlers_remain_mounted":True,
        "original_runtime_reachability_parity_verified":False,
        "instrument_command_sent":False,
    }
