"""Single trust gate for read-only or explicitly authorized original Task2 TX.

The Go producer is the only TCP socket owner. When TX=0 old read-only
snapshots stay valid. Once any outgoing bytes are physically written the
consumer MUST NOT continue to label the session passive. An opt-in may
send only the exact 36-byte source SetRate on port 10230, never Flash.
No sockets, device commands, filesystem IO, or automatic approval here.
"""
from __future__ import annotations

FIELD="source_mode2_tx_evidence"
EXT=(
 "source_tx_explicitly_approved","source_tx_sent_commands",
 "source_tx_last_rate_hz","source_tx_ack_observed_after_send",
 "source_tx_denied_observed_after_send","source_tx_write_fault",
)
RATES=frozenset((65536,32768,8192,2048,512))


def verify_source_native_tx_origin(status:dict)->bool:
    """Return True only for PROVEN actual outgoing SetRate bytes."""
    if not isinstance(status,dict):
        raise ValueError("Native Task2 requires a JSON object")
    is_read_only=status.get("read_only_no_app_payload_sent")
    if type(is_read_only) is not bool:
        raise ValueError("Native source TX proof requires a read-only flag")
    evidence=status.get(FIELD)
    if evidence is None:
        if not is_read_only:
            raise ValueError("Unattributed outgoing device bytes")
        return False
    if not isinstance(evidence,dict):
        raise ValueError("Invalid Task2 TX proof")
    has=[k in evidence for k in EXT]
    if any(has) and not all(has):
        raise ValueError("Partial original SetRate evidence")
    bytes_sent=evidence.get("source_go_device_app_bytes_sent")
    if type(bytes_sent) is not int or not 0<=bytes_sent<=36*100000:
        raise ValueError("Invalid original device TX byte count")
    if not all(has):
        if bytes_sent or not is_read_only:
            raise ValueError("Unproven active device TX from legacy producer")
        return False
    approval,count,rate,acks,denials,fault=(evidence[k] for k in EXT)
    if (type(approval) is not bool or type(count) is not int
            or not 0<=count<=100000 or type(rate) is not int
            or type(acks) is not int or not 0<=acks<=100000
            or type(denials) is not int or not 0<=denials<=100000
            or not isinstance(fault,str) or len(fault)>1024):
        raise ValueError("Invalid original device TX envelope")
    if not approval and (count or bytes_sent or acks or denials or fault):
        raise ValueError("Unapproved original device TX provenance")
    if count and rate not in RATES or not count and rate!=0:
        raise ValueError("Original SetRate after-TX frequency unsupported")
    if bytes_sent != count*36 and not (
            fault and count*36 < bytes_sent < (count+1)*36):
        raise ValueError("Task2 source TX byte count does not match 36-byte commands")
    if is_read_only != (bytes_sent==0):
        raise ValueError("Go source read-only flag contradicts transmitted bytes")
    if count and not approval:
        raise ValueError("Unapproved TX command count")
    if bytes_sent and evidence.get("original_source_command_physically_verified") is not False:
        # Real client writes do NOT mean Delphi peer-level equivalence was verified.
        raise ValueError("Fabricated Delphi command parity")
    return bytes_sent>0
