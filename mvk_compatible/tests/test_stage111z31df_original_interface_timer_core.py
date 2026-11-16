"""Source 0084F7C8/00847248 active-page-only 20ms timer; no device.

Source records directly inspected in the private _Unit128.pas and DFM.
"""
from __future__ import annotations

import pytest

from ..core.original_mode2_interface_timer import (
    OriginalMode2InterfaceTimer,
    SOURCE_ACTIVE_PAGE_HANDLERS,
    SOURCE_TOOLBAR_UPDATE_HANDLER, DFM_INTERVAL_MS,
)
from ..core.original_runtime_tabs import PAGES


def test_original_20ms_timer_starts_disabled_and_dispatches_one_page():
    clock=OriginalMode2InterfaceTimer()
    assert DFM_INTERVAL_MS==20
    assert not clock.running
    assert clock.tick("PageStatus", True) is None
    assert clock.receipt()["ticks_total"]==0
    clock.start()
    for page in PAGES:
        tick=clock.tick(page,True)
        receipt=tick.receipt()
        assert receipt["active_page_name"]==page
        assert receipt["active_page_handler_address"]==(
            SOURCE_ACTIVE_PAGE_HANDLERS[page])
        assert receipt["active_page_handler_count"]==(
            0 if page=="PageStart" else 1)
        assert receipt["pnmeasure_source_handler_address"]==(
            SOURCE_TOOLBAR_UPDATE_HANDLER)
        assert receipt["active_page_only"]
        assert not receipt["simultaneous_page_recalculation"]
        assert receipt["native_frames_decoded_by_this_timer"]==0
        assert receipt["device_commands_sent"]==0
    assert clock.receipt()["ticks_total"]==len(PAGES)
    assert clock.receipt()["independent_native_go_status_poll_ms"]==900
    clock.stop()
    assert clock.tick("PageAdc",True) is None
    assert clock.receipt()["ticks_total"]==len(PAGES)


def test_dispatcher_exact_source_order_and_toolbar_visibility_gate():
    assert list(SOURCE_ACTIVE_PAGE_HANDLERS.items())==[
        ("PageConfig","008472D0"),("PageStatus","008475BC"),
        ("PageAdc","00847EAC"),("PageSpectrum","00848148"),
        ("PageFile","0084845C"),("PageCalib","00848688"),
        ("PageStart",None),
    ] or {
        "PageStart":None,"PageConfig":"008472D0",
        "PageStatus":"008475BC","PageAdc":"00847EAC",
        "PageSpectrum":"00848148","PageFile":"0084845C",
        "PageCalib":"00848688",
    }==SOURCE_ACTIVE_PAGE_HANDLERS
    clock=OriginalMode2InterfaceTimer()
    clock.start()
    without=clock.tick("PageSpectrum",False).receipt()
    assert without["active_page_handler_count"]==1
    assert without["pnmeasure_source_handler_address"] is None
    with_panel=clock.tick("PageSpectrum",True).receipt()
    assert with_panel["active_page_handler_count"]==1
    assert with_panel["pnmeasure_source_handler_address"]=="008486F4"


@pytest.mark.parametrize("bad,visible",[
    (None,True),("PageUnknown",True),("PageStatus",1),
    ("PageAdc","yes"),(1,False)])
def test_source_timer_refuses_unknown_pages_and_unproven_visibility(
        bad,visible):
    clock=OriginalMode2InterfaceTimer()
    clock.start()
    with pytest.raises(ValueError):
        clock.tick(bad,visible)
    assert clock.receipt()["ticks_total"]==0
