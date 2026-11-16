"""Fourteen real StatusCells from the original TMVKThread, RX-only evidence.

Verified against *private* _Unit125.pas and mvkview.idp:
- 008D3068: 14 DWORD register addresses, exact copied values.
- 008061DB: source initializes its own StatusCells to FF (UNKNOWN).
- 00805D08: for each received valid block, reads UInt32 from the
  shared register-image byte buffer at address*2, tracks differences.
- 0080872D: source compares StatusCells[0] > 0 as UNSIGNED DWORD
  before setting Stage=3 / thrSystemError.

The original unsigned comparison would regard its own initial
0xFFFFFFFF sentinel as >0. The compatible read-only UI MUST NOT call
an unseen Go register a measured system error. Our source condition
is reported only after Go's RegisterImage.Valid has proved BOTH 16-bit
words at 0x1006. Actual Delphi TMVKThread.Stage is never asserted.

These 14 internal StatusCells are NOT the 15 PageStatus table fields.
No socket, instrument command, Go read, writer, or synthetic data.
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE = "STAGE111Z31DI_SOURCE_STATUSCELLS_IDP_008D3068_RX_VALID_14"
SOURCE_INDEX_ADDR = (
    0x1006,0x1038,0x1030,0x1032,
    0x2120,0x2320,0x2520,0x2720,
    0x2920,0x2b20,0x2d20,0x2f20,
    0x3004,0x3104,
)
SOURCE_INDEX_LABEL = (
    "Система","Загрузка","*SPORT","*SPI",
    "xChannel0","xChannel1","xChannel2","xChannel3",
    "xChannel4","xChannel5","xChannel6","xChannel7",
    "xChannel8","xChannel9",
)
SOURCE_ORIGINAL_UNKNOWN = 0xffffffff
SOURCE_STATUS_FIELD = "source_status_cells_14"
MAX_UINT32 = 0xffffffff
MAX_UINT64 = 0xffffffffffffffff


@dataclass(frozen=True)
class SourceStatusCell:
    index: int
    address: int
    valid: bool
    value: int | None

    @property
    def name(self) -> str:
        return SOURCE_INDEX_LABEL[self.index]

    def receipt(self) -> dict:
        return {
            "index": self.index,
            "register_address": self.address,
            "original_status_name": self.name,
            "valid": self.valid,
            "value_uint32": self.value,
            "value_hex": (f"0x{self.value:08X}" if self.valid else None),
        }


def parse_source_cells(status: dict) -> tuple[SourceStatusCell,...] | None:
    """Only exactly matching Go source addresses and VALID data.

    Absence of entire field = older capture without Source StatusCells.
    Null/false means *unseen*, not 0 and not an original system fault.
    A real on-wire 0xFFFFFFFF is allowed IF both 16-bit words were read.
    """
    if not isinstance(status,dict):
        raise ValueError("Source status cells require a Native status dictionary")
    if SOURCE_STATUS_FIELD not in status:
        return None
    if status.get("read_only_no_app_payload_sent") is not True:
        raise ValueError("Source StatusCells require read-only Native proof")
    values=status[SOURCE_STATUS_FIELD]
    if not isinstance(values,list) or len(values)!=len(SOURCE_INDEX_ADDR):
        raise ValueError("Source StatusCells require exactly 14 records")
    if not all(k in status for k in (
            "source_rx_nonempty_parameter_frames",
            "source_rx_ack_observed_no_command_issued",
            "source_rx_denied_responses")):
        raise ValueError("StatusCells require complete source RX counter group")
    count=status["source_rx_nonempty_parameter_frames"]
    if type(count) is not int or not 0<=count<=MAX_UINT64:
        raise ValueError("StatusCells require validated nonempty PARAM counter")
    result=[]
    for i,(addr,entry) in enumerate(zip(SOURCE_INDEX_ADDR,values)):
        if (not isinstance(entry,dict) or
                entry.get("index")!=i or type(entry.get("index")) is not int or
                entry.get("register_address")!=addr or
                type(entry.get("register_address")) is not int):
            raise ValueError("Source StatusCells original address/index mismatch")
        known=entry.get("valid")
        v=entry.get("value_uint32")
        if type(known) is not bool:
            raise ValueError("Source StatusCells missing Go Valid flag")
        if known:
            if type(v) is not int or not 0<=v<=MAX_UINT32 or count==0:
                raise ValueError("Source StatusCells value has no valid PARAM proof")
        elif v is not None:
            raise ValueError("Unseen register must be null, never assumed 0")
        result.append(SourceStatusCell(i,addr,known,v))
    return tuple(result)


def source_status_cell0_error(status:dict|None) -> bool:
    """True only for observed UInt32 >0 at 0x1006, not FF sentinel."""
    if status is None:
        return False
    cells=parse_source_cells(status)
    return bool(cells and cells[0].valid and cells[0].value>0)


class OriginalStatusCellsEvidence:
    """One active Native run. Go's RegisterImage.Valid never rolls back."""

    def __init__(self):
        self.available=False
        self.cells:tuple[SourceStatusCell,...] = ()
        self.source_param_count=0
        self.status_changes=0
        self.new_system_error=False
        self.system_error_latched=False

    def observe_native(self,status:dict)->dict:
        found=parse_source_cells(status)
        if found is None:
            if self.available:
                raise ValueError("Source StatusCells evidence disappeared mid-run")
            return self.receipt()
        if self.available:
            old=self.cells
            if any(before.valid and not after.valid
                   for before,after in zip(old,found)):
                raise ValueError("Source StatusCells Go Valid bit rolled back")
            count=status["source_rx_nonempty_parameter_frames"]
            if count<self.source_param_count:
                raise ValueError("Source StatusCells register frame count rolled back")
            if (count==self.source_param_count and any(
                    before!=after for before,after in zip(old,found))):
                raise ValueError("Source StatusCells changed without any new PARAM")
            self.status_changes+=sum(
                int(before!=after and after.valid)
                for before,after in zip(old,found))
        elif any(x.valid for x in found):
            self.status_changes+=sum(int(x.valid) for x in found)
        self.available=True
        self.cells=found
        self.source_param_count=status["source_rx_nonempty_parameter_frames"]
        self.new_system_error=bool(
            found[0].valid and found[0].value>0 and
            not self.system_error_latched)
        if self.new_system_error:
            # Source 0080871B skips further Stage3 handling once set;
            # a later zero raw code does not by itself reset that Stage.
            self.system_error_latched=True
        return self.receipt()

    def receipt(self)->dict:
        zero=bool(self.available and self.cells[0].valid)
        val=self.cells[0].value if zero else None
        fault=bool(zero and val>0)
        return {
            "source":SOURCE,
            "original_source_addresses_hex":tuple(
                f"{addr:04X}" for addr in SOURCE_INDEX_ADDR),
            "source_status_cells_received_from_go":self.available,
            "source_status_cells_valid_count":(
                sum(cell.valid for cell in self.cells) if self.available else 0),
            "source_status_cells":(
                tuple(cell.receipt() for cell in self.cells) if self.available
                else tuple(SourceStatusCell(i,addr,False,None).receipt()
                           for i,addr in enumerate(SOURCE_INDEX_ADDR))),
            "original_source_initial_unobserved_sentinel_hex":"0xFFFFFFFF",
            "source_statuscells0_register_valid":zero,
            "source_statuscells0_uint32":val,
            "source_statuscells0_nonzero_observed":fault,
            "new_source_system_error_from_go_register":self.new_system_error,
            "source_stage3_condition_from_observed_register":fault,
            "source_system_error_latched_until_new_capture":self.system_error_latched,
            "source_original_stage3_uses_unsigned_comparison":True,
            "original_tmkvthread_stage3_actually_observed":False,
            "original_15_pagestatus_fields_equal_these_14":False,
            "actual_instrument_register_query_sent":False,
            "device_commands_sent":0,
        }
