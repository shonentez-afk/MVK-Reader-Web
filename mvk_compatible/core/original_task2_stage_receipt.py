"""Source Task2 Stage0/1/3 and DENIED evidence, without physical Delphi claims.

Private triple-source recovery: _Unit125 TMVKThread.Execute at 00807A98
(Projects.7z) with IDP crosscheck and mvk_idr(1).sqlite.
Original Task2 does not use Stage2. The Go receipt is a compatibility
model driven by actually received frames, not a debugger trace.
"""
from __future__ import annotations
import re

SCHEMA="MVK_SOURCE_TASK2_STAGE_LIFECYCLE_V1"
_FIELDS=("source_socket_attempts","nonempty_param_since_connect",
         "observed_ack_frames","observed_denied_frames")
_REASON=re.compile(r"[A-Z0-9_]{1,100}\Z")


def validate_original_task2_stage(status: dict, cells: tuple|None) -> dict|None:
    if not isinstance(status,dict):
        raise ValueError("Source Task2 Stage: nonobject Native status")
    p=status.get("source_original_task2_stage")
    if p is None:
        return None  # older supported native receipts, NOT original proof
    if not isinstance(p,dict) or p.get("schema")!=SCHEMA or p.get("task")!=2:
        raise ValueError("Source Task2 Stage: invalid original schema or Task")
    stage=p.get("source_stage")
    last=p.get("last_live_stage")
    if type(stage) is not int or stage not in (0,1,3) or (
            type(last) is not int or last not in (0,1,3)):
        raise ValueError("Source Task2 Stage: Stage2 is not a Task2 measurement state")
    required=("socket_connected","source_system_status0_valid",
              "original_unobserved_ff_sentinel_risk",
              "system_error_latched","disconnected",
              "original_delphi_thread_parity_verified",
              "device_command_sent_by_lifecycle")
    if any(type(p.get(k)) is not bool for k in required):
        raise ValueError("Source Task2 Stage: invalid Boolean provenance")
    if p["original_delphi_thread_parity_verified"] or p["device_command_sent_by_lifecycle"]:
        raise ValueError("Source Task2 Stage: fabricated Delphi or instrument evidence")
    def u64(field):
        v=p.get(field)
        if type(v) is not int or not 0<=v<1<<64:
            raise ValueError("Source Task2 Stage: invalid "+field)
        return v
    values={k:u64(k) for k in _FIELDS}
    count=status.get("source_rx_nonempty_parameter_frames")
    ack=status.get("source_rx_ack_observed_no_command_issued")
    denied=status.get("source_rx_denied_responses")
    if (type(count) is not int or type(ack) is not int or
            type(denied) is not int or
            values["nonempty_param_since_connect"]>count or
            values["observed_ack_frames"]>ack or
            values["observed_denied_frames"]>denied):
        raise ValueError("Source Task2 Stage: real RX counts contradict receipt")
    known=p["source_system_status0_valid"]
    value=p.get("source_system_status0_uint32")
    if known:
        if (type(value) is not int or not 0<=value<1<<32 or
                cells is None or not cells[0].valid or
                cells[0].value!=value):
            raise ValueError("Source Task2 Stage: unverified StatusCells[0]")
    elif value is not None:
        raise ValueError("Source Task2 Stage: unobserved Status0 is not zero")
    connected=p["socket_connected"]
    params=values["nonempty_param_since_connect"]
    sentinel=connected and params>0 and not known
    if p["original_unobserved_ff_sentinel_risk"]!=sentinel:
        raise ValueError("Source Task2 Stage: unknown FF sentinel was hidden")
    fault=p["system_error_latched"]
    if ((stage!=0 and not connected) or
            (stage==0 and connected and params>0) or
            (stage==1 and (params==0 or fault)) or
            (stage==3 and (params==0 or not fault or not known)) or
            (fault and known is False) or
            (not connected and stage!=0) or
            (p["disconnected"] and connected) or
            (connected and values["source_socket_attempts"]==0) or
            (p["disconnected"] and values["source_socket_attempts"]==0)):
        raise ValueError("Source Task2 Stage: impossible original transition")
    reason=p.get("last_end_reason")
    if not isinstance(reason,str) or len(reason)>100 or (
            reason and not _REASON.fullmatch(reason)):
        raise ValueError("Source Task2 Stage: invalid end reason")
    if p["disconnected"] and not reason:
        raise ValueError("Source Task2 Stage: disconnected without reason")
    if (values["observed_denied_frames"]>0 and
            not p["disconnected"] and reason!="SOURCE_OPERATION_DENIED" and
            connected):
        raise ValueError("Source Task2 Stage: DENIED did not abort original operation")
    # This only validates provenance; original Delphi execution has not
    # been attached and actual hardware SetRate is not inferred.
    return {"schema":SCHEMA,"task":2,"source_stage":stage,
            "last_live_stage":last,
            "socket_connected":connected,
            "disconnected":p["disconnected"],
            "source_system_status0_valid":known,
            "source_system_status0_uint32":value,
            "system_error_latched":fault,
            "original_unobserved_ff_sentinel_risk":sentinel,
            "last_end_reason":reason,
            **values,"source_backed_not_actual_delphi":True,
            "device_commands_sent_by_lifecycle":False}
