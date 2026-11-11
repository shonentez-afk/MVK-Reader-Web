"""Stage111Z31BD: source-derived, strict, read-only original config text.

Private user _Unit115.pas:007CFD44 LoadValuesFromFile:
  comments ';', '+0xNNNN' sets per-file offset, '@relative.txt' include
  with inherited offset, and <hex-address> <format-char>:<literal>.
  007B28F8 emits original saved words as 0xNNNN. 007CFB50 feeds
  original InputValueRaw; this parser NEVER calls it or encodes device
  registers. Text configuration is not an authenticated live snapshot.

_Unit125:00803FB4 and manufacturer config map: ADC N base 0100+N*0100,
8 alarm slots +0060+j*0010, 8 fields +0,+2,..,+E (16-bit register
addresses, each cell may be larger than one word). Native status records
are separate at 0x2000+N*0x0200+0x0130+j*8. No status code/threshold or
selected parameter is guessed without actual source data.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

SOURCE="IDR_ORIGINAL_TMVKCELL_LIST_TEXT_OFFLINE_INSPECTION_STAGE111Z31BD"
UNKNOWN="—"
MAX_BYTES=1024*1024
MAX_LINES=10000
MAX_INCLUDES=16
MAX_DEPTH=4
ADDR_RE=re.compile(r"(?:0[xX])?([0-9A-Fa-f]{1,8})\Z")
FMT_RE=re.compile(r"([!-~]):([^;\r\n]{1,160})\Z")
INCLUDE_RE=re.compile(r"[A-Za-z0-9_\-. ]+\.(?:txt|cfg|conf)\Z",re.I)
FIELDS=(
    ("parameter_id","AlarmBand",0x0),
    ("yellow_threshold","AlarmYellowThr",0x2),
    ("red_threshold","AlarmRedThr",0x4),
    ("up_delay","AlarmUpDelay",0x6),
    ("down_delay","AlarmDownDelay",0x8),
    ("yellow_hysteresis","AlarmYellowHys",0xA),
    ("red_hysteresis","AlarmRedHys",0xC),
    ("display_scale_max","AlarmMax",0xE),
)


def _hex_word(s,*,name):
    m=ADDR_RE.fullmatch(s.strip())
    if not m:
        raise ValueError(name+": expected original hexadecimal address")
    number=int(m.group(1),16)
    if number<0 or number>=0x10000 or number%2:
        raise ValueError(name+": original address must be even and <0x10000")
    return number


def alarm_config_register(adc:int,slot:int,field:str)->int:
    if type(adc) is not int or not 1<=adc<=8:
        raise ValueError("Original alarm ADC must be 1..8")
    if type(slot) is not int or not 1<=slot<=8:
        raise ValueError("Original alarm slot must be 1..8")
    choice=next((offset for key,_,offset in FIELDS if key==field),None)
    if choice is None:
        raise ValueError("Unsupported original alarm configuration field")
    return 0x100+(adc-1)*0x100+0x60+(slot-1)*0x10+choice


def alarm_live_status_register(adc:int,slot:int)->int:
    if type(adc) is not int or not 1<=adc<=8:
        raise ValueError("Original alarm ADC must be 1..8")
    if type(slot) is not int or not 1<=slot<=8:
        raise ValueError("Original alarm slot must be 1..8")
    return 0x2000+(adc-1)*0x200+0x130+(slot-1)*8


@dataclass(frozen=True)
class RawConfigCell:
    address:int
    format_char:str
    literal:str
    source_basename:str
    source_line:int

    @property
    def formatted(self):
        return self.format_char+":"+self.literal


@dataclass(frozen=True)
class LocalConfigInspection:
    cells:tuple[RawConfigCell,...]
    file_digests:tuple[tuple[str,str],...]
    source: str=SOURCE

    def value(self,address:int)->RawConfigCell|None:
        if type(address) is not int or not 0<=address<0x10000 or address%2:
            raise ValueError("Address must be a source register")
        return next((c for c in self.cells if c.address==address),None)

    def alarm_rows(self):
        rows=[]
        for adc in range(1,9):
            for slot in range(1,9):
                fields={}
                for key,translation,delta in FIELDS:
                    address=alarm_config_register(adc,slot,key)
                    cell=self.value(address)
                    fields[key]={
                        "source_translation_key":translation,
                        "address":f"0x{address:04X}",
                        "raw_value":cell.formatted if cell is not None else UNKNOWN,
                        "observed_in_local_file":cell is not None,
                    }
                rows.append({
                    "adc":adc,"slot":slot,
                    "raw_source_status_address":
                        f"0x{alarm_live_status_register(adc,slot):04X}",
                    "fields":fields,
                    "live_device_configuration_verified":False,
                    "alarm_threshold_interpretation_verified":False,
                })
        return tuple(rows)

    def channel_rows(self):
        return tuple({
            "adc":adc,
            "source_config_base":f"0x{0x100+(adc-1)*0x100:04X}",
            "known_alarm_cells_in_file":sum(
                cell is not None
                for slot in range(1,9)
                for key,_,_ in FIELDS
                for cell in (self.value(alarm_config_register(adc,slot,key)),)
            ),
            "expected_alarm_cells":64,
            "device_config_verified":False,
        } for adc in range(1,9))

    def other_raw_rows(self):
        known={alarm_config_register(adc,slot,key)
               for adc in range(1,9) for slot in range(1,9)
               for key,_,_ in FIELDS}
        return tuple(c for c in self.cells if c.address not in known)

    def report(self):
        return {
            "source":self.source,
            "original_source_text_structure_verified":True,
            "read_only":True,
            "device_actions_allowed":False,
            "original_live_device_config_verified":False,
            "original_config_write_roundtrip_verified":False,
            "raw_value_decoding_verified":False,
            "file_digests":[{"filename":n,"sha256":d}
                            for n,d in self.file_digests],
            "parsed_cells":len(self.cells),
            "alarm_registers_present":sum(
                f["observed_in_local_file"]
                for r in self.alarm_rows() for f in r["fields"].values()),
            "alarm_registers_expected":512,
            "channels":8,
            "slots_per_channel":8,
        }


def inspect_original_local_config(path:str|Path)->LocalConfigInspection:
    """No CLI, device, writes or recursive arbitrary-file access.

    Follow ONLY short same-directory @filename.txt includes, with strict
    global count/size/line/depth/cycle and no symlinks or parent traversal.
    Source plaintext is decoded UTF-8 BOM, UTF-16LE BOM or CP1251; this
    is a reader, not a claim that all vendor encodings were accepted.
    """
    root=Path(path).absolute()
    if root.is_symlink() or not root.is_file():
        raise ValueError("Select a real local original config file")
    base=root.parent.resolve(strict=True)
    cells={}
    files={}
    seen=set()
    lines_total=0
    bytes_total=0

    def scan(file:Path,offset:int,depth:int,stack:frozenset):
        nonlocal lines_total,bytes_total
        if depth>MAX_DEPTH:
            raise ValueError("Config @include nesting is too deep")
        if file.is_symlink() or not file.is_file():
            raise ValueError("Config includes require ordinary local files")
        real=file.resolve(strict=True)
        if real.parent!=base:
            raise ValueError("Original @include cannot escape source folder")
        if real in stack:
            raise ValueError("Cyclic original config @include")
        if real not in seen:
            seen.add(real)
            if len(seen)>MAX_INCLUDES:
                raise ValueError("Too many original config includes")
        size=real.stat().st_size
        if not 1<=size<=MAX_BYTES or bytes_total+size>MAX_BYTES:
            raise ValueError("Original config exceeds local size budget")
        raw=real.read_bytes()
        if len(raw)!=size or real.stat().st_size!=size:
            raise ValueError("Source config changed during read")
        bytes_total+=size
        digest=hashlib.sha256(raw).hexdigest()
        existing=files.get(real.name)
        if existing is not None and existing!=digest:
            raise ValueError("Included config changed between reads")
        files[real.name]=digest
        if raw.startswith(b"\xff\xfe"):
            text=raw[2:].decode("utf-16le")
        elif raw.startswith(b"\xef\xbb\xbf"):
            text=raw[3:].decode("utf-8")
        else:
            try:text=raw.decode("utf-8")
            except UnicodeDecodeError:text=raw.decode("cp1251")
        if "\x00" in text:
            raise ValueError("Unexpected NUL in local config")
        current_offset=offset
        for lineno,rawline in enumerate(text.splitlines(),1):
            lines_total+=1
            if lines_total>MAX_LINES:
                raise ValueError("Too many original config text lines")
            line=rawline.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("+"):
                # From original IDR: +0xNNNN overrides LOCAL AddrOffset.
                current_offset=_hex_word(line[1:],name="AddrOffset")
                continue
            if line.startswith("@"):
                token=line[1:].strip()
                if not INCLUDE_RE.fullmatch(token):
                    raise ValueError("Unsafe or unsupported original @include")
                scan(base/token,current_offset,depth+1,stack|{real})
                continue
            parts=line.split(None,1)
            if len(parts)!=2:
                raise ValueError(f"{real.name}:{lineno} missing formatted value")
            addr=_hex_word(parts[0],name="Config address")
            actual=addr+current_offset
            if actual>0xFFFE:
                raise ValueError("Config address + base outside source 16-bit range")
            datum=parts[1].split(";",1)[0].strip()
            m=FMT_RE.fullmatch(datum)
            if not m:
                raise ValueError(f"{real.name}:{lineno}: unsupported source ValueWithFmt")
            new=RawConfigCell(actual,m.group(1),m.group(2),real.name,lineno)
            if actual in cells:
                raise ValueError("Duplicate source config register address")
            cells[actual]=new

    scan(root,0,0,frozenset())
    return LocalConfigInspection(
        tuple(cells[k] for k in sorted(cells)),
        tuple(sorted(files.items()))
    )


def empty_original_config_inspection()->LocalConfigInspection:
    """Display source address topology even when NO config file was loaded."""
    return LocalConfigInspection((),())
