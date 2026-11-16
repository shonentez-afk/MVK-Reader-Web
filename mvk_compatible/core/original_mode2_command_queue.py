"""Source-derived TMVKThread command FIFO, STRICTLY OFFLINE AND NON-TRANSMITTING.

Private local references: _Unit125.pas 008060B0/0080618E (initial 309),
00809330 (12-byte Cmd/Addr/Data TList.Add), 00809288 (Get(0), Delete(0)),
00809364 (QueueCommand(1, 0x0e, MvkSampleRate)), 00809400 (only if
changed), Execute 00807E8F..00807F67 (take only at Stage==1). The
actual wire writer 0080937C and TCP are NOT in this module.

A 12-byte TMVKThreadCommand memory record is NOT a 12-byte network
packet. Never feed its packed bytes to the Native recorder.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

SOURCE = "IDR_TMVKTHREAD_00809330_00809288_00809364_00809400_OFFLINE"
DEFAULT_RATE_CODE = 309
RATE_COMMAND = 1
RATE_ADDRESS = 0x0e
COMMAND_STRUCT_BYTES = 12
MAX_SIMULATED_COMMANDS = 256
SOURCE_EXCEPTION_ROUTES = {
    "closed": ("EIdConnClosedGracefully", "008088A2", "errDisconnected"),
    "read_timeout": ("EIdReadTimeout", "008088CE", "errNotResponding"),
    "connect_timeout": ("EIdConnectTimeout", "008088FA", "errCannotConnect"),
    "network": ("EIdException", "00808923", "errTransferError"),
    "other": ("Exception", "0080896D", "exception_message"),
}
# The following are source STATUS / parser errors, not the Delphi exception
# classes above, and not equivalent to a Native Go JSON error.
SOURCE_INTERNAL_ERROR_ROUTES = {
    "invalid_packet": "errInvalidPacket",
    "operation_denied": "errOperationDenied",
    "system_status": "thrSystemError",
}


def _u32(value: int, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError("Source 32-bit command field invalid: " + field)
    return value


def _i32(value: int) -> int:
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Original Cmd must be signed Delphi Integer")
    return value


@dataclass(frozen=True)
class OriginalCommandRecord:
    cmd: int
    addr: int
    data: int
    ordinal: int

    def __post_init__(self):
        _i32(self.cmd)
        _u32(self.addr, "Addr")
        _u32(self.data, "Data")
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise ValueError("Source command ordinal must be positive")

    def memory_record(self) -> bytes:
        """Delphi in-memory TList entry, NEVER the source wire frame."""
        return struct.pack("<iII", self.cmd, self.addr, self.data)

    def receipt(self) -> dict:
        return {
            "ordinal": self.ordinal,
            "Cmd": self.cmd,
            "Addr": self.addr,
            "Data": self.data,
            "delphi_in_memory_record_bytes": COMMAND_STRUCT_BYTES,
            "source_network_packet_reconstructed": False,
            "simulated_only": True,
        }


class OriginalMode2CommandQueue:
    """Autonomous original memory-queue semantics; no network/device API.

    The actual operator Qt instance never calls enqueue/set_rate: those
    require recovered five exact source tags and separately approved
    device-write transport. A synthetic test may exercise ALL queue
    transitions without a socket or any physical instrument.
    """

    def __init__(self):
        self._pending: list[OriginalCommandRecord] = []
        self._taken: list[OriginalCommandRecord] = []
        self._next_ordinal = 1
        self._rate_code = DEFAULT_RATE_CODE
        self._closed = False

    @property
    def source_rate_code(self) -> int:
        return self._rate_code

    @property
    def pending(self) -> tuple[OriginalCommandRecord, ...]:
        return tuple(self._pending)

    @property
    def taken(self) -> tuple[OriginalCommandRecord, ...]:
        return tuple(self._taken)

    def queue_command(self, cmd: int, addr: int, data: int) -> OriginalCommandRecord:
        if self._closed:
            raise ValueError("Original simulated command list is closed")
        _i32(cmd)
        _u32(addr, "Addr")
        _u32(data, "Data")
        if self._next_ordinal > MAX_SIMULATED_COMMANDS:
            raise ValueError("Bounded offline command model exhausted")
        record = OriginalCommandRecord(cmd, addr, data, self._next_ordinal)
        self._next_ordinal += 1
        self._pending.append(record)
        return record

    def set_rate(self, source_rate_code: int) -> OriginalCommandRecord | None:
        """Exact SetRate code-change gate. NOT a frequency in Hz.

        The five original UI Tag codes from gvar_008D2F7C are currently
        not independently attested. A caller's supplied code is ONLY
        used for offline simulation and must not be sent over TCP.
        """
        _u32(source_rate_code, "MvkSampleRate")
        if self._closed:
            raise ValueError("Cannot model SetRate after source shutdown")
        if source_rate_code == self._rate_code:
            return None
        self._rate_code = source_rate_code
        return self.queue_command(RATE_COMMAND, RATE_ADDRESS, source_rate_code)

    def take_one(self, source_stage: int) -> OriginalCommandRecord | None:
        """Source 00807E8F processes 1 FIFO item at Stage==1 per loop."""
        if type(source_stage) is not int or source_stage not in (0, 1, 2):
            raise ValueError("Unverified source thread Stage")
        if self._closed or source_stage != 1 or not self._pending:
            return None
        record = self._pending.pop(0)
        self._taken.append(record)
        return record

    def shutdown(self) -> dict:
        """Source Destroy frees remaining TList records; never rearm."""
        discarded = len(self._pending)
        self._pending.clear()
        self._closed = True
        return {"source": SOURCE, "pending_discarded": discarded,
                "device_commands_sent": 0}

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "default_internal_rate_code": DEFAULT_RATE_CODE,
            "current_internal_rate_code": self._rate_code,
            "five_original_rate_tags_independently_verified": False,
            "pending_count": len(self._pending),
            "taken_count": len(self._taken),
            "queue_closed": self._closed,
            "records_12_bytes_in_memory_only": True,
            "original_wire_serialization_verified": False,
            "original_device_write_enabled": False,
            "device_commands_sent": 0,
            "read_only_native_unchanged": True,
        }


class OriginalMode2FaultRoutes:
    """Exception-class ledger: do not map Native faults to Delphi by guess."""

    def __init__(self):
        self._events: list[dict] = []
        self._closed = False

    def record_source_exception(self, kind: str) -> dict:
        if self._closed or kind not in SOURCE_EXCEPTION_ROUTES:
            raise ValueError("Unknown/closed source exception route")
        cls, address, localization = SOURCE_EXCEPTION_ROUTES[kind]
        record = {
            "kind": kind, "delphi_exception_class": cls,
            "source_handler_address": address, "localization_key": localization,
            "native_error_equivalence_proven": False,
        }
        self._events.append(record)
        return dict(record)

    def record_source_internal_error(self, kind: str) -> dict:
        if self._closed or kind not in SOURCE_INTERNAL_ERROR_ROUTES:
            raise ValueError("Unknown/closed source parser/status error")
        record = {
            "kind": kind,
            "localization_key": SOURCE_INTERNAL_ERROR_ROUTES[kind],
            "source_internal_not_delphi_exception": True,
            "native_error_equivalence_proven": False,
        }
        self._events.append(record)
        return dict(record)

    def record_native_fault(self, kind: str) -> dict:
        """Native outcomes have a different provenance from Delphi."""
        if self._closed or kind not in (
            "STATUS_REJECTED", "NO_PACKET", "REFUSED",
            "STREAM_ERRORS", "PROCESS_FAILED", "PACK_FAILED",
            "STOPPED_WITHOUT_ARCHIVE"):
            raise ValueError("Unknown/closed Native quality/failure kind")
        record = {
            "kind": kind, "source": "MVK_R6_NATIVE_READ_ONLY",
            "matched_to_delphi_exception": False,
        }
        self._events.append(record)
        return dict(record)

    def finish(self):
        self._closed = True

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "source_exception_routes_verified": len(SOURCE_EXCEPTION_ROUTES),
            "source_internal_routes_verified": len(SOURCE_INTERNAL_ERROR_ROUTES),
            "event_count": len(self._events),
            "events": tuple(dict(x) for x in self._events),
            "closed": self._closed,
            "native_error_equivalence_proven": False,
            "device_commands_sent": 0,
        }
