"""Original MVKView connected PageStatus, without fake equipment values.

The operator's 2026-11-16 Win32 screenshot shows 15 visible system
parameter names and a two-column TStringGrid. Native R6.1 is a passive
read-only TCP/10230 recorder: its validated live JSON reports transport,
NOT the vendor's device serial, firmware MD5, device runtime or Modbus
counters. Those are intentionally UNKNOWN until the source protocol
actually supplies them. This module never starts a socket or mutates
device state.
"""
from __future__ import annotations

from dataclasses import dataclass
from .native_r6_live_status import SCHEMA
from .original_mode2_live_health import live_transport_health
from .original_system_register_fields import SYSTEM_SOURCE_FIELDS,parse_source_system_registers

SOURCE="ORIGINAL_CONNECTED_SYSTEM_STATUS_VISIBLE_SCREEN_20261116"
SYSTEM_STATUS_KEYS=(
 ("serial","Серийный номер устройства"),
 ("firmware","Версия внутреннего ПО"),
 ("errors","Системные ошибки"),
 ("uptime","Время работы"),
 ("memory_kib","Размер карты памяти в КБ"),
 ("dsp_md5","MD5 внутреннего ПО DSP"),
 ("control_group1","Состояние контроля по группе 1"),
 ("unack_group1","Неквитированные события по группе 1"),
 ("control_group2","Состояние контроля по группе 2"),
 ("unack_group2","Неквитированные события по группе 2"),
 ("calc_counter","Счетчик процедур расчета"),
 ("modbus_queries","Счетчик запросов Modbus"),
 ("modbus_last_address","Последний адрес Modbus"),
 ("modbus_last_count","Последнее число регистров Modbus"),
 ("modbus_clients","Число активных клиентов Modbus"),
)
SYSTEM_STATUS_HEADERS=("Наименование параметра","Значение")
UNKNOWN="—"


@dataclass(frozen=True)
class ConnectedSystemStatus:
    rows:tuple[tuple[str,str],...]
    connection_verified:bool
    transport_phase:str
    frame_count:int|None
    stream_silent:bool=False
    data_integrity_alert:bool=False
    native_channel_count:int=0
    native_invalid_frames:int=0
    native_sequence_gaps:int=0
    native_nonfinite_samples:int=0
    source_system_error_observed:bool=False
    source_fields_proven:int=0
    provenance:str=SOURCE

    @property
    def headers(self):
        return SYSTEM_STATUS_HEADERS

    def receipt(self):
        return {
            "source":SOURCE,"row_count":len(self.rows),
            "original_device_system_fields_proven":self.source_fields_proven,
            "connected_readonly_transport_verified":self.connection_verified,
            "transport_phase":self.transport_phase,
            "transport_frames":self.frame_count,
            "native_channels_observed":self.native_channel_count,
            "native_stream_silent":self.stream_silent,
            "native_data_integrity_alert":self.data_integrity_alert,
            "native_invalid_frames":self.native_invalid_frames,
            "native_sequence_gaps":self.native_sequence_gaps,
            "native_nonfinite_samples":self.native_nonfinite_samples,
            "source_statuscells0_real_system_error":self.source_system_error_observed,
            "source_system_error_from_14_not_15_table":True,
            "original_modbus_or_device_commands_issued":False,
        }


def connected_system_status(native_status:dict|None=None)->ConnectedSystemStatus:
    """Render exact source names. Native transport != original device STATUS.

    The producer must have been validated by validate_live_status()
    upstream. A wrongly tagged or stale recording is *not* a connection.
    """
    if native_status is None:
        phase="NO_NATIVE_EVIDENCE"
        connected=False
        frame_count=None
        health=live_transport_health(None)
    else:
        if (not isinstance(native_status,dict)
                or native_status.get("schema")!=SCHEMA
                or native_status.get("read_only_no_app_payload_sent") is not True
                or native_status.get("phase") not in (
                    "CONNECTING","RECORDING","VERIFYING",
                    "COMPLETED","REFUSED")):
            raise ValueError("Unverified Native read-only status")
        count=native_status.get("frames_decoded")
        if type(count) is not int or not 0<=count<=2**64-1:
            raise ValueError("Invalid Native decoded-frame counter")
        stale=native_status.get("snapshot_stale")
        if type(stale) is not bool:
            raise ValueError("Validated Native freshness bit missing")
        phase=native_status["phase"]
        frame_count=count
        health=live_transport_health(native_status)
        # A freshly-written JSON file is not proof that data are still
        # arriving. The Go transport can keep reporting old frame totals
        # after its last instrument packet. Keep the source lamp non-green
        # when packet silence crosses the Native watchdog threshold.
        connected=(
            phase=="RECORDING" and count>0
            and not stale and not health.stream_silent)
    # Never fill serial, firmware, errors, DSP MD5 or Modbus counters
    # using Go capture elapsed_seconds/frames_decoded/raw_bytes.
    fields=parse_source_system_registers(native_status) if native_status is not None else None
    rows=tuple((caption,fields[i].value() if fields is not None else UNKNOWN)
               for i,(_,caption) in enumerate(SYSTEM_STATUS_KEYS))
    proven=sum(int(f.valid) for f in fields) if fields is not None else 0
    return ConnectedSystemStatus(
        rows,connected,phase,frame_count,
        stream_silent=health.stream_silent,
        data_integrity_alert=health.data_integrity_alert,
        native_channel_count=health.channels_observed,
        native_invalid_frames=health.invalid_frames,
        native_sequence_gaps=health.sequence_gaps,
        native_nonfinite_samples=health.nonfinite_samples,
        source_system_error_observed=health.source_system_error_observed,
        source_fields_proven=proven)


assert len(SYSTEM_STATUS_KEYS)==15
assert tuple(k for k,_,_ in SYSTEM_SOURCE_FIELDS)==tuple(k for k,_ in SYSTEM_STATUS_KEYS)
