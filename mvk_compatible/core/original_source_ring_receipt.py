"""Source-backed ten-channel receive ring receipt, no device commands.

Private original evidence jointly verified: mvkview.idp; Projects.7z
_Unit115.pas, _Unit125.pas, _Unit128.pas; mvk_idr(1).sqlite.
All 10 original TMvkChannelStorage buffers have 2**21 elements:
eight Float32 (4 bytes), two TACH bytes (1 byte).
"""
from __future__ import annotations
import math
import struct
import re

SCHEMA="MVK_SOURCE_CHANNEL_STORAGE_V1"
BUFFER_ELEMENTS=1<<21
# Exact original LIVE FRange source; never mix with Native exporter gain.
SOURCE_LIVE_ADC_DOMAIN="ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32"
SOURCE_CONFIG_ADC_DOMAIN="ORIGINAL_LIVE_ADC_CONFIG_FRANGE_FLOAT32"
SOURCE_LIVE_ADC_DOMAINS=frozenset((SOURCE_LIVE_ADC_DOMAIN,SOURCE_CONFIG_ADC_DOMAIN))
ADC_DOMAIN=frozenset((
    SOURCE_LIVE_ADC_DOMAIN,SOURCE_CONFIG_ADC_DOMAIN,
    "RAW_DEVICE_FLOAT32_NOT_YET_CALIBRATED",
    "CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32",
))
TACH_DOMAIN="TACH_EXACT_DEVICE_PAYLOAD_BYTES"
U32_MAX=(1<<32)-1
U64_MAX=(1<<64)-1


def _bounded_int(obj:dict,key:str,max_value:int=U64_MAX)->int:
    value=obj.get(key)
    if type(value) is not int or not 0<=value<=max_value:
        raise ValueError(f"Original storage: invalid {key}")
    return value


def validate_source_epoch(epoch, *, rx: int, valid: int, width: int,
                          socket_count: int = 0):
    """An admitted, contiguous range, not a certificate for the whole run."""
    if epoch is None:
        return None
    if (not isinstance(epoch, dict) or
            set(epoch) != {"socket_attempt", "continuity_generation",
                           "start_pos_64"}):
        raise ValueError("Original storage: malformed source epoch")
    attempt = _bounded_int(epoch, "socket_attempt", 128)
    generation = _bounded_int(epoch, "continuity_generation")
    start = _bounded_int(epoch, "start_pos_64", rx)
    if (attempt == 0 or generation == 0 or start < valid or start >= rx
            or (socket_count and attempt != socket_count)
            or (width == 1 and start % 4)):
        raise ValueError("Original storage: invalid source epoch bounds/socket")
    return dict(epoch)


def source_epoch_recovery_pending(status: dict) -> bool:
    """The legacy, mixed-history preview must never replace an epoch window."""
    return (status.get("source_tcp_multi_socket") is True or
            status.get("source_rate_transition_during_live") is True)


def source_epoch_recovery_possible(status: dict) -> bool:
    """Only the local graph path can resume; leave writer/transport alarms intact."""
    return (source_epoch_recovery_pending(status) and
            status.get("phase") == "RECORDING" and
            status.get("capture_only") is False and
            status.get("snapshot_stale") is False and
            status.get("invalid_frames") == 0 and
            status.get("source_rx_denied_responses", 0) == 0 and
            status.get("source_system_error_observed", False) is False and
            type(status.get("source_tcp_connection_count")) is int and
            status["source_tcp_connection_count"] > 0 and
            status.get("source_original_receive_gate_verified") is True and
            status.get("source_original_storage_verified") is True)


def source_channel_epoch(status: dict, row: dict):
    epoch = row.get("source_epoch")
    if epoch is None:
        return None
    return validate_source_epoch(
        epoch, rx=row["rx_pos_64"],
        valid=row["valid_pos_64"], width=row["sample_width_bytes"],
        socket_count=status.get("source_tcp_connection_count", 0))


def validate_source_range_state(state,channel):
    """Prove the reported Single against source config bytes, not UI gain."""
    if state is None:
        return None
    fields={"single","origin","register_word","register_raw_le","units_raw_le",
            "latched_frame","socket_attempt","usable"}
    if not isinstance(state,dict) or set(state)!=fields or not 1<=channel<=8:
        raise ValueError("Original live FRange: malformed state")
    if state["register_word"]!=0x100*channel+0x0e:
        raise ValueError("Original live FRange: wrong ADC register")
    _bounded_int(state,"latched_frame")
    if _bounded_int(state,"socket_attempt")==0:
        raise ValueError("Original live FRange: invalid socket attempt")
    raw=state["register_raw_le"]
    units=state["units_raw_le"]
    if (not isinstance(raw,str) or (raw!="" and not re.fullmatch("[0-9a-f]{8}",raw))
            or not isinstance(units,str) or
            (units!="" and not re.fullmatch("[0-9a-f]{64}",units))):
        raise ValueError("Original live FRange: malformed register bytes")
    value=state["single"]
    if type(value) not in (float,int) or not math.isfinite(value) or type(state["usable"]) is not bool:
        raise ValueError("Original live FRange: invalid Single")
    decoded=struct.unpack("<f",bytes.fromhex(raw))[0] if raw else None
    if decoded is None:
        expected,origin,usable=1.0,"UNOBSERVED_REGISTER_PROVISIONAL_ONE",True
    elif decoded==0:
        expected,origin,usable=1.0,"REGISTER_ZERO_FALLBACK_ONE",True
    elif math.isfinite(decoded) and decoded>0:
        expected,origin,usable=decoded,"REGISTER_FLOAT32",True
    else:
        expected,origin,usable=0.0,"INVALID_REGISTER_NO_CALCULATION",False
    try:
        match=struct.pack("<f",value)==struct.pack("<f",expected)
    except (OverflowError,struct.error):
        match=False
    if not match or state["origin"]!=origin or state["usable"]!=usable:
        raise ValueError("Original live FRange: Single does not match register")
    return dict(state)


def source_live_range_matches(row,domain,scale,state):
    if domain not in SOURCE_LIVE_ADC_DOMAINS or row.get("input_domain")!=domain:
        return False
    if row.get("source_range_state")!=state or row.get("original_live_f_range_single")!=scale:
        return False
    if type(scale) not in (float,int) or not math.isfinite(scale) or scale<=0:
        return False
    if state is None:
        return domain==SOURCE_LIVE_ADC_DOMAIN and scale==1.0
    return (state.get("usable") is True and state.get("single")==scale and
            ((scale==1.0)==(domain==SOURCE_LIVE_ADC_DOMAIN)))


def validate_original_storage_receipt(
        receipt:dict|None,channels:list[dict],
        receive_gate:dict|None=None, *, socket_count:int=0)->dict|None:
    """Check Go ring accounting; never claim Delphi binary/runtime parity.

    The optional receipt preserves existing approved historical status files.
    A small preview ZIP alone does not prove original 2M storage.
    """
    if receipt is None:
        return None
    if (not isinstance(receipt,dict) or receipt.get("schema")!=SCHEMA or
            receipt.get("buffer_elements_per_channel")!=BUFFER_ELEMENTS or
            not isinstance(channels,list) or len(channels)!=10 or
            not isinstance(receipt.get("channels"),list) or
            len(receipt["channels"])!=10):
        raise ValueError("Original storage: invalid 10-channel 2M receipt")
    verified=[]
    for i,row in enumerate(receipt["channels"]):
        if not isinstance(row,dict) or not isinstance(channels[i],dict):
            raise ValueError("Original storage: invalid channel object")
        if row.get("channel")!=i+1 or channels[i].get("channel")!=i+1:
            raise ValueError("Original storage: channel order mismatch")
        width=4 if i<8 else 1
        if row.get("sample_width_bytes")!=width:
            raise ValueError("Original storage: ADC Float32 or TACH byte type mismatch")
        rx=_bounded_int(row,"rx_pos_64")
        valid=_bounded_int(row,"valid_pos_64")
        first=_bounded_int(row,"first_readable_pos_64")
        available=_bounded_int(row,"available_elements",BUFFER_ELEMENTS)
        sample_rate=_bounded_int(row,"last_sample_rate_hz",1_000_000)
        gap=_bounded_int(row,"sequence_gaps")
        rate_changes=_bounded_int(row,"rate_changes")
        dropped=_bounded_int(row,"rejected_nonfinite_frames")
        if (valid>rx or
                first!=max(valid,rx-BUFFER_ELEMENTS if rx>BUFFER_ELEMENTS else 0)
                or available!=rx-first or available>BUFFER_ELEMENTS):
            raise ValueError("Original storage: impossible ring cursor/history")
        epoch=validate_source_epoch(row.get("source_epoch"),
            rx=rx,valid=valid,width=width,socket_count=socket_count)
        source_samples=channels[i].get("samples")
        expected_upper=source_samples if i<8 else (
            source_samples*4 if type(source_samples) is int else -1)
        gate_row=(receive_gate["channels"][i]
                  if receive_gate is not None else None)
        skipped=(gate_row["rate_skipped_elements"]+
                 gate_row["freeze_skipped_elements"]
                 if gate_row is not None else 0)
        admitted=(gate_row["accepted_elements"]
                  if gate_row is not None else expected_upper)
        # Source FreezeUpdate and MvkSampleRate mismatch DO NOT advance
        # TMvkChannelStorage.FRxPos, while the TCP/raw counter continues.
        # A resume may introduce a source ring gap even if native TCP
        # SampleHeader.Index itself remained completely contiguous.
        gate_gaps=(gate_row["rate_skipped_frames"]+
                   gate_row["freeze_skipped_frames"]
                   if gate_row is not None else 0)
        if (type(source_samples) is not int or source_samples<0
                or rx>expected_upper or rx>admitted or
                rx+skipped>expected_upper or
                gap>channels[i].get("sequence_discontinuities",-1)+max(1,socket_count)+gate_gaps or
                dropped>channels[i].get("nonfinite_samples",-1)):
            raise ValueError("Original storage: source RX counters disagree")
        domain=row.get("input_domain")
        live_range=row.get("original_live_f_range_single")
        range_state=validate_source_range_state(row.get("source_range_state"),i+1)
        if domain in SOURCE_LIVE_ADC_DOMAINS:
            if not source_live_range_matches(row,domain,live_range,range_state):
                raise ValueError("Original live FRange: source ring must prove current Single")
        elif live_range is not None:
            raise ValueError(
                "Original live FRange: cannot attach factor to foreign domain")
        if i>=8 and dropped!=0:
            raise ValueError("Original storage: byte TACH cannot reject Float32 NaN")
        allowed=ADC_DOMAIN if i<8 else frozenset((TACH_DOMAIN,))
        if domain not in allowed and domain!="":
            raise ValueError("Original storage: unknown signal input domain")
        if rx>0 and domain not in allowed:
            raise ValueError("Original storage: real samples lack domain")
        if rx>0 and (sample_rate==0 or sample_rate not in
                     channels[i].get("sample_rates_hz",[])):
            raise ValueError("Original storage: sample-rate provenance mismatch")
        idx=row.get("next_device_sample_index")
        native_idx=channels[i].get("next_sample_index")
        if idx is not None and (type(idx) is not int or not 0<=idx<=U32_MAX):
            raise ValueError("Original storage: invalid uint32 device index")
        if (idx is not None and native_idx is not None and idx!=native_idx
                and (gate_row is None or skipped==0)):
            raise ValueError("Original storage: device index contradicts Go")
        # Different indices are allowed ONLY when the same validated
        # Go gate proves that real TCP samples were deliberately excluded
        # by original rate matching or FreezeUpdate.
        if rx>0 and idx is None:
            raise ValueError("Original storage: missing device index")
        verified.append({
            "channel":i+1,"kind":"ADC" if i<8 else "TACH",
            "sample_width_bytes":width,"rx_pos_64":rx,
            "valid_pos_64":valid,"first_readable_pos_64":first,
            "available_elements":available,"last_sample_rate_hz":sample_rate,
            "next_device_sample_index":idx,"input_domain":domain,
            "original_live_f_range_single":live_range,
            **({"source_range_state":range_state} if range_state is not None else {}),
            **({"source_epoch":epoch} if epoch is not None else {}),
            "sequence_gaps":gap,"rate_changes":rate_changes,
            "rejected_nonfinite_frames":dropped,
        })
    return {
        "schema":SCHEMA,"buffer_elements_per_channel":BUFFER_ELEMENTS,
        "channels":verified,
        "verified_only_source_go_accounting":True,
        "original_delphi_memory_parity_verified":False,
        "device_commands_issued":False,
    }


def source_live_units_text(state, *, windows_ansi_code_page=None):
    """ConfigUnits type 9 (32 bytes). Never infer Windows ANSI code page."""
    if not isinstance(state,dict) or not state.get("units_raw_le"):
        return None
    from .original_get_value_text_30 import get_value_text_30
    raw=state["units_raw_le"]
    if not isinstance(raw,str) or not re.fullmatch("[0-9a-f]{64}",raw):
        return None
    out=get_value_text_30(9,bytes.fromhex(raw),
        windows_ansi_code_page=windows_ansi_code_page)
    return out.text if out.available and not any(ord(c)<32 for c in out.text) else None

def source_status_channel_units(status,adc):
    """PageStatus uses its own accepted snapshot; tcAdc is independent."""
    if (not isinstance(status,dict) or status.get("source_original_storage_verified") is not True
            or type(adc) is not int or not 1<=adc<=10):
        return None
    bank=status.get("source_original_storage")
    rows=bank.get("channels") if isinstance(bank,dict) else None
    if not isinstance(rows,list) or len(rows)!=10 or not isinstance(rows[adc-1],dict):
        return None
    try:
        if adc>=9:
            return "" if rows[adc-1].get("input_domain")==TACH_DOMAIN else None
        state=validate_source_range_state(rows[adc-1].get("source_range_state"),adc)
        return source_live_units_text(state)
    except (ValueError,TypeError,KeyError,OverflowError):
        return None
