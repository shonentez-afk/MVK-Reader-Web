"""Source-verified 15 visible system fields, distinct from 14 internal StatusCells.

_Unit125:008026B0 creates a TMvkCellList, AddrOffset=0x1000.
Source pairs State/Alert share two register words but have distinct source
advanced-cell dictionaries. Unverified formatters render RAW hex only.
No I/O, simulated device values, device commands or private sources.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import struct

SYSTEM_SOURCE_FIELDS=(
 ("serial",0x1000,2),("firmware",0x1004,2),("errors",0x1006,2),
 ("uptime",0x1008,2),("memory_kib",0x100A,2),("dsp_md5",0x100C,8),
 ("control_group1",0x1014,2),("unack_group1",0x1014,2),
 ("control_group2",0x1016,2),("unack_group2",0x1016,2),
 ("calc_counter",0x1024,2),("modbus_queries",0x1036,2),
 ("modbus_last_address",0x103A,2),("modbus_last_count",0x103C,2),
 ("modbus_clients",0x103E,2),
)
SOURCE_FIELD_KEY="source_page_status_fields_15"
assert len(SYSTEM_SOURCE_FIELDS)==15
_HEX=re.compile(r"[0-9a-f]+\Z")

@dataclass(frozen=True)
class SourceSystemRegister:
 index:int
 key:str
 address:int
 words:int
 valid:bool
 raw:bytes|None
 def value(self)->str:
  if not self.valid or self.raw is None:return "—"
  if self.key=="dsp_md5":return self.raw.hex().upper()
  n=struct.unpack("<I",self.raw)[0]
  if self.key=="uptime":return f"{n//3600:02d}:{(n//60)%60:02d}:{n%60:02d}"
  if self.key in ("errors","memory_kib","calc_counter","modbus_queries","modbus_clients"):
   return str(n)
  return f"0x{n:08X}"

def parse_source_system_registers(status:dict)->tuple[SourceSystemRegister,...]|None:
 if not isinstance(status,dict):raise ValueError("PageStatus source JSON object required")
 if SOURCE_FIELD_KEY not in status:return None
 entries=status[SOURCE_FIELD_KEY]
 if not isinstance(entries,list) or len(entries)!=15:
  raise ValueError("PageStatus requires 15 original source fields")
 out=[]
 for i,(entry,(key,addr,words)) in enumerate(zip(entries,SYSTEM_SOURCE_FIELDS)):
  if not isinstance(entry,dict) or (type(entry.get("index")) is not int or entry["index"]!=i or
    entry.get("key")!=key or type(entry.get("register_address")) is not int or
    entry["register_address"]!=addr or type(entry.get("word_count")) is not int or
    entry["word_count"]!=words or type(entry.get("valid")) is not bool):
   raise ValueError("Wrong original PageStatus index, key, register or width")
  hex_le=entry.get("raw_hex_le")
  if entry["valid"]:
   if not isinstance(hex_le,str) or len(hex_le)!=words*4 or not _HEX.fullmatch(hex_le):
    raise ValueError("Partial/invalid PageStatus source bytes")
   raw=bytes.fromhex(hex_le)
  else:
   if hex_le is not None:raise ValueError("Unknown PageStatus field is not null")
   raw=None
  out.append(SourceSystemRegister(i,key,addr,words,entry["valid"],raw))
 for a,b in ((6,7),(8,9)):
  if out[a].valid!=out[b].valid or (out[a].valid and out[a].raw!=out[b].raw):
   raise ValueError("Shared source State/Alert register mismatch")
 return tuple(out)

def verify_source_error_overlap(payload:dict)->None:
 from .original_mode2_status_cells import parse_source_cells
 fields=parse_source_system_registers(payload)
 cells=parse_source_cells(payload)
 if fields is None or cells is None:return
 row,c=fields[2],cells[0]
 if row.valid!=c.valid or (row.valid and struct.unpack("<I",row.raw)[0]!=c.value):
  raise ValueError("Visible 0x1006 system error does not match StatusCells[0]")
