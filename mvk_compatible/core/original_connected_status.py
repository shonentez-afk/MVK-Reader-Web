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
    provenance:str=SOURCE

    @property
    def headers(self):
        return SYSTEM_STATUS_HEADERS

    def receipt(self):
        return {
            "source":SOURCE,"row_count":len(self.rows),
            "original_device_system_fields_proven":0,
            "connected_readonly_transport_verified":self.connection_verified,
            "transport_phase":self.transport_phase,
            "transport_frames":self.frame_count,
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
        connected=phase=="RECORDING" and count>0 and not stale
    # Never fill serial, firmware, errors, DSP MD5 or Modbus counters
    # using Go capture elapsed_seconds/frames_decoded/raw_bytes.
    rows=tuple((caption,UNKNOWN) for _,caption in SYSTEM_STATUS_KEYS)
    return ConnectedSystemStatus(rows,connected,phase,frame_count)


assert len(SYSTEM_STATUS_KEYS)==15
