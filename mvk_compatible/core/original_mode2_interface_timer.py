"""Source _Unit128:0084F7C8 -> 00847248, 20 ms active-page timer.

Unlike a broadcast to every page, the original dispatcher calls exactly
ONE branch for the active TPageControl tab and THEN 008486F4 if pnMeasure
is visible. It begins disabled per private mvkform.dfm and is enabled in
Mode2 only after TMVKThread construction.

This module is an autonomous, bounded dispatch RECEIPT. It cannot poll a
device, synthesize ADC/DSP samples, or claim 20ms sensor acquisition.
"""
from __future__ import annotations

from dataclasses import dataclass

from .original_runtime_tabs import PAGES

SOURCE = "SOURCE_IDR_0084F7C8_00847248_ACTIVE_PAGE_PLUS_PNMEASURE"
DFM_TIMER_OBJECT = "tmInterfaceUpdate"
DFM_INTERVAL_MS = 20
DFM_TIMER_INITIALLY_ENABLED = False
DFM_HANDLER_ADDRESS = "0084F7C8"
SOURCE_DISPATCHER_ADDRESS = "00847248"
SOURCE_TOOLBAR_UPDATE_HANDLER = "008486F4"
SOURCE_ACTIVE_PAGE_HANDLERS = {
    "PageConfig": "008472D0",
    "PageStatus": "008475BC",
    "PageAdc": "00847EAC",
    "PageSpectrum": "00848148",
    "PageFile": "0084845C",
    "PageCalib": "00848688",
    # The original PageStart has no per-page branch in 00847248.
    "PageStart": None,
}
assert set(SOURCE_ACTIVE_PAGE_HANDLERS) == set(PAGES)


def source_active_page_refresh_allowed(page_name: str, *, freeze_update: bool) -> bool:
    """Original 008475BC skips PageStatus body painting on FreezeUpdate.

    Original 00847248 still dispatches the active page and 008486F4
    still refreshes pnMeasure. Other page handlers retain their own
    independent source semantics. No network or device writes.
    """
    if type(page_name) is not str or page_name not in SOURCE_ACTIVE_PAGE_HANDLERS:
        raise ValueError("Original active TTabSheet required")
    if type(freeze_update) is not bool:
        raise ValueError("Original TMVKThread.FreezeUpdate is Boolean")
    return not (page_name == "PageStatus" and freeze_update)

@dataclass(frozen=True)
class SourceInterfaceTimerTick:
    number: int
    page_name: str
    active_page_handler: str | None
    measurement_panel_handler: str | None

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "source_dfm_timer": DFM_TIMER_OBJECT,
            "source_original_interval_ms": DFM_INTERVAL_MS,
            "source_delphi_handler": DFM_HANDLER_ADDRESS,
            "source_dispatcher": SOURCE_DISPATCHER_ADDRESS,
            "tick_sequence": self.number,
            "active_page_name": self.page_name,
            "active_page_handler_address": self.active_page_handler,
            "active_page_handler_count": (
                1 if self.active_page_handler is not None else 0),
            "pnmeasure_source_handler_address": self.measurement_panel_handler,
            "active_page_only": True,
            "simultaneous_page_recalculation": False,
            "native_frames_decoded_by_this_timer": 0,
            "original_full_dsp_page_parity_verified": False,
            "device_commands_sent": 0,
        }


class OriginalMode2InterfaceTimer:
    """Stateful source dispatcher with no platform or network dependency."""

    def __init__(self):
        self.running = DFM_TIMER_INITIALLY_ENABLED
        self.tick_count = 0
        self.last_tick: SourceInterfaceTimerTick | None = None

    def start(self):
        if self.running:
            return self.receipt()
        self.running = True
        return self.receipt()

    def stop(self):
        self.running = False
        return self.receipt()

    def tick(self, active_page: str, pnmeasure_visible: bool):
        if not self.running:
            return None
        if (type(active_page) is not str
                or active_page not in SOURCE_ACTIVE_PAGE_HANDLERS):
            raise ValueError("Source timer needs a real original TTabSheet")
        if type(pnmeasure_visible) is not bool:
            raise ValueError("Source timer needs source pnMeasure visibility")
        self.tick_count += 1
        self.last_tick = SourceInterfaceTimerTick(
            self.tick_count, active_page,
            SOURCE_ACTIVE_PAGE_HANDLERS[active_page],
            SOURCE_TOOLBAR_UPDATE_HANDLER if pnmeasure_visible else None,
        )
        return self.last_tick

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "source_dfm_interval_ms": DFM_INTERVAL_MS,
            "source_dfm_initially_disabled": True,
            "active": self.running,
            "ticks_total": self.tick_count,
            "last_tick": self.last_tick.receipt() if self.last_tick else None,
            "independent_native_go_status_poll_ms": 900,
            "source_20ms_is_not_900ms_tcp_sample_refresh": True,
            "device_commands_sent": 0,
        }
