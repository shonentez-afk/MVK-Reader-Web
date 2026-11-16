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
# _Unit128 from original IDR mvkview.idp: bTaskConnectClick 00848E78
# sets Mode2. 00846D24..00846D5C calls SetTabVisible, 00846D79..
# 00846D84 makes pnMeasure visible, all BEFORE 00846DCC creates
# TMVKThread. Device connection success is *not* required for 5 tabs.
ORIGINAL_LIVE_VISIBLE=(
    "PageStart","PageStatus","PageAdc","PageSpectrum","PageFile")
_SOURCE_ROUTE_PAGES=frozenset(PAGES)


def original_runtime_visible_pages(
        *, has_measurement:bool, technical:bool=False,
        current_page:str="PageStart",live:bool=False,
        measurement_requested:bool=False) -> tuple[str,...]:
    if (type(has_measurement) is not bool
            or type(technical) is not bool or type(live) is not bool
            or type(measurement_requested) is not bool):
        raise ValueError("Runtime tab visibility needs strict booleans")
    if not isinstance(current_page,str) or current_page not in PAGES:
        raise ValueError("Current original DFM page is required")
    if technical:
        return PAGES
    # live means the read-only Go process was launched, *not* actual
    # device connection. Selected Mode2 must already show these pages.
    mode2=live or measurement_requested
    visible=set(ORIGINAL_LIVE_VISIBLE if mode2 else (
        ORIGINAL_ARCHIVE_VISIBLE if has_measurement
        else ORIGINAL_IDLE_VISIBLE))
    # An EXPLICIT source PageStart operation can enter e.g. Config or
    # PageFile without making unrelated internal TTabSheets visible.
    # This is compatible navigation, not a native runtime claim.
    if current_page not in visible:
        visible.add(current_page)
    return tuple(page for page in PAGES if page in visible)


def original_runtime_tab_contract(
        *,has_measurement:bool,technical:bool=False,
        current_page:str="PageStart",live:bool=False,
        measurement_requested:bool=False)->dict:
    visible=original_runtime_visible_pages(
        has_measurement=has_measurement,technical=technical,
        current_page=current_page,live=live,
        measurement_requested=measurement_requested)
    mode2=live or measurement_requested
    return {
        "source":SOURCE,"all_form_pages":PAGES,
        "visible":visible,"visible_count":len(visible),
        "startup_only_one_tab":not has_measurement and not mode2
            and not technical and current_page=="PageStart",
        "archive_only_three_default":has_measurement and not mode2
            and not technical and current_page in ORIGINAL_ARCHIVE_VISIBLE,
        # Historical key kept for existing tests; it means selected Mode2.
        "connected_original_five_tabs":mode2 and not technical
            and current_page in ORIGINAL_LIVE_VISIBLE,
        "mode2_selected_before_connection":measurement_requested,
        "native_recorder_started":live,
        "measurement_toolbar_visible_from_source_mode2":mode2,
        "device_connection_verified_by_tabs":False,
        "live_source_connected_verified_by_preview":False,
        "technical_mode_is_source_original":False,
        "all_seven_handlers_remain_mounted":True,
        "original_runtime_reachability_parity_verified":False,
        "instrument_command_sent":False,
    }
