"""Source Task=2 receive-stage proof projected from ONE passive Native Go run.

Private source:
- _Unit125.pas 00807F74/84 reads Type/Length, 0080807B accepts ACK,
  008080AC raises on DENIED, 0080839E processes PARAM blocks,
  00808617 switches source Stage0->Stage1 on first valid nonempty block.
- The actual source Stage3 requires source StatusCells >0 and CANNOT be
  inferred from Native Framer packet counts.
- Native Go R6.1 sends zero application commands. An observed ACK is NOT
  proof of an accepted SetRate from this compatible application.

Only optional fields produced by the SAME Native Go monitor are accepted;
old status snapshots without these fields stay UNKNOWN, never "ready".
"""
from __future__ import annotations

SOURCE = "STAGE111Z31DG_SOURCE_RX_STAGE1_PASSIVE_NATIVE_PROOF"
FIELDS = (
    "source_rx_nonempty_parameter_frames",
    "source_rx_ack_observed_no_command_issued",
    "source_rx_denied_responses",
)
SOURCE_STAGE_START = 0
SOURCE_STAGE_READY = 1


def _counter(value, name: str) -> int:
    if type(value) is not int or not 0 <= value <= (1<<64)-1:
        raise ValueError("Invalid source inbound counter: " + name)
    return value


class OriginalMode2ReceiveEvidence:
    """Stable counters over one already-validated Native run; no I/O."""

    def __init__(self):
        self.available = False
        self.register_frames_with_blocks = 0
        self.ack_observed = 0
        self.denied_observed = 0
        self.snapshot_frame_count = 0
        self.new_denial_observed = False

    def observe_native(self, status: dict) -> dict:
        from .original_mode2_active_tx_provenance import verify_source_native_tx_origin
        verify_source_native_tx_origin(status)
        present=[key in status for key in FIELDS]
        if any(present) and not all(present):
            raise ValueError("Source RX evidence must be an atomic counter group")
        if not any(present):
            # Old synthetic/Go JSON has not established this evidence.
            # Never replace an already-bound new-schema run with a
            # lower-trust legacy snapshot missing its protocol counters.
            if self.available:
                raise ValueError("Source RX evidence disappeared mid-session")
            self.new_denial_observed=False
            return self.receipt()

        counters=tuple(_counter(status[key],key) for key in FIELDS)
        frames=_counter(status.get("frames_decoded"),"frames_decoded")
        if sum(counters)>frames:
            raise ValueError("Source RX reply/register counters exceed frames")
        if self.available and (
                counters[0]<self.register_frames_with_blocks or
                counters[1]<self.ack_observed or
                counters[2]<self.denied_observed or
                frames<self.snapshot_frame_count):
            raise ValueError("Source RX counters rolled back in current Native run")
        self.new_denial_observed=counters[2]>self.denied_observed
        (self.register_frames_with_blocks,self.ack_observed,
         self.denied_observed)=counters
        self.snapshot_frame_count=frames
        self.available=True
        return self.receipt()

    def receipt(self) -> dict:
        ready=self.available and self.register_frames_with_blocks>0
        return {
            "source": SOURCE,
            "native_protocol_evidence_available": self.available,
            "original_source_stage_0_until_nonempty_register": True,
            "original_source_stage_candidate_from_rx": (
                SOURCE_STAGE_READY if ready else
                SOURCE_STAGE_START if self.available else None),
            "native_receive_register_frames_with_blocks": (
                self.register_frames_with_blocks if self.available else None),
            "native_received_ack_unattributed": (
                self.ack_observed if self.available else None),
            "native_received_denied_unattributed": (
                self.denied_observed if self.available else None),
            "new_denial_observed_this_snapshot": self.new_denial_observed,
            "denial_seen": bool(self.available and self.denied_observed>0),
            "original_source_stage_3_statuscells_verified": False,
            "original_setrate_command_ack_verified": False,
            "original_source_stage_is_actually_running": False,
            "only_passive_go_frames_counted": True,
            "device_commands_sent": 0,
        }
