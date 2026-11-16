"""Original Mode2 lifecycle receipts attached to REAL Native read-only Qt events.

Source: _Unit128.pas bTaskConnectClick 00848E78, 00846D24 (show pages
BEFORE thread create 00846DCC), tmInterfaceUpdate 0084F7C8 -> 00847248;
_Unit125.pas TMVKThread.Execute 00807A98, source 20ms timer, and source
exception handlers 008088A2/CE/FA/00808923. This is NOT a driver.

Composes the independently source-verified nontransmitting queue/fault
models; the initial SetRate is enqueued only into the OFFLINE simulator,
never into any real device/Go transport.
"""
from __future__ import annotations

from dataclasses import dataclass
from .original_connected_status import connected_system_status
from .original_mode2_rx_evidence import OriginalMode2ReceiveEvidence
from .original_mode2_command_queue import (
    OriginalMode2CommandQueue, OriginalMode2FaultRoutes,
)
from .original_mode2_rate_menu_source import (
    SOURCE_DEFAULT_MENU_TAG, SOURCE_THREAD_INITIAL_CODE,
    source_initial_rate_provenance,
)

SOURCE = "STAGE111Z31DC_MODE2_NATIVE_LIVE_LIFECYCLE_SOURCE_TRACE"
MAX_EVENTS = 64
NATIVE_PHASES = frozenset((
    "CONNECTING", "RECORDING", "VERIFYING", "COMPLETED", "REFUSED",
))


@dataclass(frozen=True)
class Mode2TraceEvent:
    ordinal: int
    name: str
    phase: str


class OriginalMode2RuntimeTrace:
    """One Mode2 lifetime, observed from the *existing* Qt/Go owner."""

    def __init__(self):
        self.command_model = OriginalMode2CommandQueue()
        self.fault_routes = OriginalMode2FaultRoutes()
        self.receive_evidence=OriginalMode2ReceiveEvidence()
        self.phase = "IDLE"
        self.capture_started = False
        self.stop_requested = False
        self.session_id: str | None = None
        self.frames_decoded = 0
        self._events: list[Mode2TraceEvent] = []
        self._event_total = 0
        self.finished = False
        self.source_initial_rate_queued_offline = False

    def _event(self, name: str):
        self._event_total += 1
        self._events.append(Mode2TraceEvent(self._event_total, name, self.phase))
        if len(self._events) > MAX_EVENTS:
            del self._events[:len(self._events) - MAX_EVENTS]

    def enter_mode2(self):
        if self.phase != "IDLE" or self.finished:
            raise ValueError("Original Mode2 cannot be entered twice")
        self.phase = "MODE2_BEFORE_TCP"
        self._event("MEASURE_CLICK")
        return self.receipt()

    def native_started(self):
        if self.phase != "MODE2_BEFORE_TCP" or self.finished:
            raise ValueError("Native may start only after source Mode2 entry")
        self.capture_started = True
        self.phase = "CONNECTING"
        self._event("NATIVE_START")
        # Original 00846DDF..00846DF7 calls mRate1Click(Items[0])
        # immediately after TMVKThread.Create. Items[0] is 65536
        # because five array elements are each inserted at index zero.
        # The private IDP memory proves a 0x309 (777) thread initial
        # code, so the initial SetRate enqueues (1,0x0E,65536).
        # THIS QUEUE IS DRY-RUN ONLY: Native R6.1 gets NO application bytes.
        source_command=self.command_model.set_rate(SOURCE_DEFAULT_MENU_TAG)
        if source_command is None:
            raise AssertionError("Source initial rate should differ from 0x309")
        self.source_initial_rate_queued_offline=True
        self._event("SOURCE_INITIAL_MRATE1CLICK_DRY_RUN")
        return self.receipt()

    def observe_native(self, status: dict):
        """Accepted Native JSON evidence, not original TMVKThread status."""
        if not self.capture_started or self.finished:
            raise ValueError("No active source Mode2 Native run")
        if not isinstance(status, dict) or status.get("phase") not in NATIVE_PHASES:
            raise ValueError("Only checked Native phases may be observed")
        # Existing production path validates JSON provenance before it
        # reaches this Core; use the same system-status proof as the GUI.
        proof = connected_system_status(status)
        sid = status.get("session_id")
        if sid is None and self.session_id is not None:
            raise ValueError("Bound Native run lost source session identity")
        if sid is not None:
            if not isinstance(sid, str) or not sid:
                raise ValueError("Native session identity invalid")
            if self.session_id is not None and sid != self.session_id:
                raise ValueError("Native run changed in original Mode2")
            self.session_id = sid
        frames = status["frames_decoded"]
        if frames < self.frames_decoded and self.session_id is not None:
            raise ValueError("Native decoded-frame count rolled back")
        # Sparse old synthetic UI receipts have no run identity; never
        # pretend their counters belong to one monotonic physical session.
        self.frames_decoded = max(self.frames_decoded, frames)
        # Actual Go receive counters are separate from the DRY-RUN
        # SetRate queue: ACK from the device cannot certify that we sent
        # a command, because the Native Go client sends none.
        source_rx=self.receive_evidence.observe_native(status)
        if source_rx["new_denial_observed_this_snapshot"]:
            self._event("PASSIVE_RX_OPERATION_DENIED")
        if self.stop_requested:
            self.phase = "STOPPING"
        elif status["phase"] == "REFUSED":
            self.phase = "REFUSED"
            self.fault_routes.record_native_fault("REFUSED")
        elif proof.stream_silent:
            self.phase = "SILENT"
            self.fault_routes.record_native_fault("NO_PACKET")
        elif proof.data_integrity_alert:
            self.phase = "STREAM_ERRORS"
            self.fault_routes.record_native_fault("STREAM_ERRORS")
        elif proof.connection_verified:
            self.phase = "RECORDING"
        else:
            self.phase = status["phase"]
        self._event("NATIVE_STATUS")
        return self.receipt()

    def awaiting_native_status(self):
        """No Go JSON yet is a WAIT, not a spurious Delphi TCP fault."""
        if not self.capture_started or self.finished:
            return self.receipt()
        if self.session_id is not None:
            # The source was previously bound to a real run: a missing
            # status is no longer initial connecting/waiting evidence.
            return self.status_rejected()
        if not self.stop_requested:
            self.phase = "CONNECTING"
        self._event("NATIVE_STATUS_PENDING")
        return self.receipt()

    def status_rejected(self):
        if not self.capture_started or self.finished:
            return self.receipt()
        if not self.stop_requested:
            self.phase = "STATUS_REJECTED"
        self.fault_routes.record_native_fault("STATUS_REJECTED")
        self._event("NATIVE_STATUS_INVALID")
        return self.receipt()

    def request_stop(self):
        if not self.capture_started or self.finished or self.stop_requested:
            raise ValueError("Native Stop is not available")
        self.stop_requested = True
        self.phase = "STOPPING"
        self._event("MEASURE_OFF_CLICK")
        return self.receipt()

    def complete(self, *, accepted: bool):
        if type(accepted) is not bool or not self.capture_started or self.finished:
            raise ValueError("Native completion requires a running Mode2")
        self.finished = True
        self.capture_started = False
        self.phase = "VERIFIED_ARCHIVE" if accepted else "STOPPED_WITHOUT_ARCHIVE"
        if not accepted:
            self.fault_routes.record_native_fault("STOPPED_WITHOUT_ARCHIVE")
        self.command_model.shutdown()
        self.fault_routes.finish()
        self._event("NATIVE_COMPLETE")
        return self.receipt()

    def exit_before_native(self):
        if self.phase != "MODE2_BEFORE_TCP" or self.capture_started or self.finished:
            raise ValueError("Only idle Mode2 may exit without Native")
        self.phase = "IDLE"
        self.finished = True
        self.command_model.shutdown()
        self.fault_routes.finish()
        self._event("MEASURE_OFF_BEFORE_TCP")
        return self.receipt()

    def leave_after_native(self):
        if not self.finished or self.capture_started or self.phase == "IDLE":
            raise ValueError("Source Mode2 can leave only after Native finishes")
        self.phase = "IDLE"
        self._event("MEASURE_OFF_AFTER_NATIVE")
        return self.receipt()

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "mode2_phase": self.phase,
            "mode2_selected": self.phase not in ("IDLE", "VERIFIED_ARCHIVE"),
            "source_ui_before_tcp": bool(
                self._events and self._events[0].name == "MEASURE_CLICK"),
            "native_capture_started": self.capture_started,
            "native_stop_requested": self.stop_requested,
            "native_run_bound": self.session_id is not None,
            "native_frames_decoded": self.frames_decoded,
            "recording_commands_allowed": False,
            "original_source_timer_ms": 20,
            "native_qt_status_poll_ms": 900,
            "original_timer_behavior_reproduced": False,
            "original_queue": self.command_model.receipt(),
            "original_receive_protocol": self.receive_evidence.receipt(),
            "source_initial_rate_queued_offline":
                self.source_initial_rate_queued_offline,
            "source_selected_sample_rate_code": (
                SOURCE_DEFAULT_MENU_TAG if self.source_initial_rate_queued_offline
                else None),
            "source_rate_menu_provenance": source_initial_rate_provenance(),
            "source_initial_device_setrate_sent": False,
            "original_faults": self.fault_routes.receipt(),
            "events_seen": self._event_total,
            "last_events": tuple(
                (event.ordinal, event.name, event.phase)
                for event in self._events[-12:]),
            "original_delphi_device_parity_verified": False,
            "hardware_commands_sent": 0,
        }
