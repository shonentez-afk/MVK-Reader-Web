"""Independent Go RX evidence that a source Delphi TX *could* occur.

Source Delphi _Unit125 00807E8F..00807F52 (Task2) writes the queued
SetRate BEFORE its next Read only after a meaningful PARAM enters Stage1.
The checked Go Native R6.1 is deliberately passive: NO device writes.

This validates producer receipts; it never creates a socket, performs IO,
or counts an unpaired ACK as proof that our own command succeeded.
"""
from __future__ import annotations

from dataclasses import dataclass
from .original_mode2_status_cells import parse_source_cells
from .original_mode2_active_tx_provenance import verify_source_native_tx_origin,EXT,RATES

FIELD = "source_mode2_tx_evidence"
FRAME_BYTES = 36
REQUIRED = (
    "source_original_writer_present",
    "source_stage1_nonempty_param_observed",
    "source_system_status0_valid_zero",
    "source_delphi_unobserved_status0_sentinel_stage3_risk",
    "source_setrate_candidate_after_param",
    "source_go_device_app_bytes_sent",
    "source_setrate_frame_size_bytes",
    "original_source_command_physically_verified",
)


@dataclass(frozen=True)
class OriginalTask2TransmitEvidence:
    stage1_observed: bool
    system0_known_zero: bool
    source_send_candidate: bool
    delphi_unobserved_ff_stage3_risk: bool
    producer_sent_bytes: int
    approved: bool=False
    sent_commands: int=0
    current_rate: int=0
    ack_after_sent: int=0
    denial_after_sent: int=0
    def receipt(self) -> dict:
        return {
            "source": "DELPHI_TASK2_SOURCE_WRITER_RECEIPT_PASSIVE_GO",
            "source_stage1_observed": self.stage1_observed,
            "source_system0_known_zero": self.system0_known_zero,
            "source_setrate_dispatch_candidate": self.source_send_candidate,
            "source_unobserved_status0_ff_source_stage3_risk": self.delphi_unobserved_ff_stage3_risk,
            "source_setrate_36_bytes_lab_recovered": True,
            "source_go_bytes_actually_sent": self.producer_sent_bytes,
            "source_tx_explicitly_approved":self.approved,
            "source_tx_sent_commands":self.sent_commands,
            "source_tx_last_rate_hz":self.current_rate,
            "source_tx_temporal_acks":self.ack_after_sent,
            "source_tx_temporal_denials":self.denial_after_sent,
            "original_delphi_command_physically_observed": False,
            "original_ack_attributed_to_setrate": False,
        }


def validate_original_task2_tx(status: dict) -> OriginalTask2TransmitEvidence | None:
    if not isinstance(status, dict):
        raise ValueError("Source Task2 TX evidence must be a Native object")
    if FIELD not in status:
        return None
    active=verify_source_native_tx_origin(status)
    data=status[FIELD]
    if (not isinstance(data, dict) or
            not set(REQUIRED)<=set(data) or
            set(data)-set(REQUIRED)-set(EXT)):
        raise ValueError("Incomplete source Task2 TX proof")
    for key in REQUIRED:
        if key not in ("source_go_device_app_bytes_sent","source_setrate_frame_size_bytes"):
            if type(data[key]) is not bool:
                raise ValueError("Non-boolean source Task2 TX provenance")
    if (data["source_original_writer_present"] is not True or
            data["original_source_command_physically_verified"] is not False or
            type(data["source_go_device_app_bytes_sent"]) is not int or
            data["source_go_device_app_bytes_sent"] < 0 or
            type(data["source_setrate_frame_size_bytes"]) is not int or
            data["source_setrate_frame_size_bytes"] != FRAME_BYTES):
        raise ValueError("Live source TX cannot claim a physical command")
    params=status.get("source_rx_nonempty_parameter_frames")
    if type(params) is not int or params<0:
        raise ValueError("Native RX PARAM proof missing for source TX")
    seen=params>0
    if seen!=data["source_stage1_nonempty_param_observed"]:
        raise ValueError("Source Stage1 TX proof disagrees with actual PARAM count")
    cells=parse_source_cells(status)
    if cells is None:
        raise ValueError("Original TX requires 14 source StatusCells proof")
    zero=bool(cells[0].valid and cells[0].value==0)
    if zero!=data["source_system_status0_valid_zero"]:
        raise ValueError("Source TX system0 zero does not match real registers")
    source_sentinel_risk=seen and not cells[0].valid
    if source_sentinel_risk!=data["source_delphi_unobserved_status0_sentinel_stage3_risk"]:
        raise ValueError("Source literal FF sentinel Stage3 risk not proven")
    candidate=seen and zero and status.get("capture_only") is False
    if candidate!=data["source_setrate_candidate_after_param"]:
        raise ValueError("Source outbound candidate contradicts receive-only evidence")
    approval=bool(data.get("source_tx_explicitly_approved",False))
    count=data.get("source_tx_sent_commands",0)
    rate=data.get("source_tx_last_rate_hz",0)
    acks=data.get("source_tx_ack_observed_after_send",0)
    denied=data.get("source_tx_denied_observed_after_send",0)
    if active and not (seen and approval and count>0):
        raise ValueError("Original source physical TX has no RX PARAM proof")
    if acks>status.get("source_rx_ack_observed_no_command_issued",0):
        raise ValueError("Temporal ACK count exceeds source RX ACK count")
    if denied>status.get("source_rx_denied_responses",0):
        raise ValueError("Temporal denial count exceeds source RX denied count")
    return OriginalTask2TransmitEvidence(
        seen,zero,candidate,source_sentinel_risk,
        data["source_go_device_app_bytes_sent"],approval,count,rate,acks,denied)
