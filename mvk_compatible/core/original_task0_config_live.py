"""Original bConfigDownloadClick/Task0 read-only register snapshot.

Private 3-way provenance: mvkview.idp 008495A8/0084964C/00807A98,
_Unit125.pas and _Unit128.pas from Projects.7z, and mvk_idr(1).sqlite.
Only independently verified incoming RAW is shown; never writes an MVK
register, never enables original Task3/4/5 Flash/reboot configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import tempfile

from .native_r6_bridge import STOP_REQUEST,validate_ipv4
from .original_config_semantics import section_fields
from .original_config_idp_tables import source_type_description

SCHEMA = "MVK_SOURCE_TASK0_CONFIG_IP_READ_V1"
FILENAME = "SOURCE_TASK0_CONFIG_IP_READ.json"
SOURCE_TASK = 0
SOURCE_MODE = "LIVE_SOURCE_TASK0_CONFIG_READ_ONLY"
END_REASON = "SOURCE_TASK0_CONFIG_READ_COMPLETE"
_RUN_NAME = re.compile(r"TEST_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.\d{3}(?:_\d+)?\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_TASK0_RAW_BYTES = 32 * 1024 * 1024
_SENSITIVE = frozenset(("ConfigWifiSSID","ConfigWifiPassword"))
_SOURCE_WIRE_TYPES = frozenset((
    0x00000001,0xFF800ADC,0xFF8001AC,0xFF800C0D,0x00010FF0,0x00010FFF,
))


@dataclass(frozen=True)
class SourceTask0DownloadSpec:
    """Only the approved, finite passive Task0 TCP connection."""
    device_ipv4: str
    local_ipv4: str
    output_parent: Path
    seconds: int = 20
    max_mb: int = 16

    def validate(self) -> None:
        validate_ipv4(self.device_ipv4,field="IP прибора")
        validate_ipv4(self.local_ipv4,field="IP Ethernet")
        if type(self.seconds) is not int or not 1<=self.seconds<=60:
            raise ValueError("Task0 допускает только 1..60 секунд")
        if type(self.max_mb) is not int or not 1<=self.max_mb<=32:
            raise ValueError("Task0 ограничен 1..32 МиБ RAW")
        directory=Path(self.output_parent)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("Выберите существующий локальный каталог")
        if not directory.resolve().is_dir():
            raise ValueError("Недоступен локальный каталог Task0")

    def create_root(self) -> Path:
        self.validate()
        return Path(tempfile.mkdtemp(prefix="mvk_task0_",dir=self.output_parent))

    def native_args(self,root:Path) -> list[str]:
        self.validate()
        root=Path(root)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Нет каталога оригинального Task0")
        if not root.resolve().is_relative_to(Path(self.output_parent).resolve()):
            raise ValueError("Task0 запрещён за пределами каталога пользователя")
        stop=root/STOP_REQUEST
        if stop.is_symlink() or stop.exists():
            raise ValueError("Старый Task0 stop-маркер")
        # This is a distinct source *read* task. TX, Flash, reset,
        # frame-mark, auto-reconnect, ADC export are always disabled.
        return [
            "-ip",self.device_ipv4,"-local-ip",self.local_ipv4,
            "-seconds",str(self.seconds),"-max-mb",str(self.max_mb),
            "-out",str(root),"-approve=true","-live-status=true",
            "-export=false","-source-task0-config-read=true",
            "-stop-file",str(stop.resolve()),
        ]


def _read_json(path:Path,limit:int)->dict:
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=limit:
        raise ValueError("Task0 local evidence missing or unsafe")
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise ValueError("Task0 local evidence JSON invalid") from exc
    if not isinstance(value,dict):
        raise ValueError("Task0 local evidence object required")
    return value


def _safe_specs():
    fields,_=section_fields("ip")
    return tuple(
        (field.key,field.offset,
         source_type_description(field.cell_type)["source_register_words"])
        for field in fields if field.key not in _SENSITIVE
    )


def _replay_original_param(raw:bytes) -> tuple[bytes,tuple[bool,...],int,int]:
    """Decode ONLY source-validated inbound PARAM register blocks.

    The Go snapshot is rejected if it disagrees with independently
    replayed original RAW. The frame reassembler tolerates a terminal
    incomplete packet only when Go reports its exact tail length.
    """
    memory=bytearray(0x4000*2)
    valid=[False]*0x4000
    cursor=0
    param_count=0
    while len(raw)-cursor>=8:
        kind,length=struct.unpack_from("<II",raw,cursor)
        if kind not in _SOURCE_WIRE_TYPES or length<8 or length>0x20000 or length%4:
            raise ValueError("Task0 RAW contains invalid original frame")
        if length>len(raw)-cursor:break
        frame=raw[cursor:cursor+length]
        if kind==0xFF800C0D:
            if length<32:
                raise ValueError("Task0 PARAM too short")
            count=struct.unpack_from("<I",frame,24)[0]
            if count>4096:
                raise ValueError("Task0 PARAM has too many records")
            pos=28
            for _ in range(count):
                if pos+4>length:
                    raise ValueError("Task0 PARAM descriptor truncated")
                descriptor=struct.unpack_from("<I",frame,pos)[0]
                pos+=4
                address=descriptor&0xFFFF
                words=descriptor>>16
                if (words==0 or words%2 or
                        address+words>0x4000 or pos+words*2>length):
                    raise ValueError("Task0 PARAM register block invalid")
                start=address*2
                memory[start:start+words*2]=frame[pos:pos+words*2]
                valid[address:address+words]=[True]*words
                pos+=words*2
            if pos!=length:
                raise ValueError("Task0 PARAM trailing bytes")
            if count: param_count+=1
        cursor+=length
    return bytes(memory),tuple(valid),param_count,len(raw)-cursor


def load_source_task0_config(root:Path|str,*,expected_ip:str)->dict:
    """Verify source Task0, SHA-bound incoming RAW and every displayed cell."""
    expected_ip=validate_ipv4(expected_ip,field="IP прибора")
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Неверный каталог Task0")
    runs=[p for p in root.iterdir()
          if p.is_dir() and not p.is_symlink() and
          _RUN_NAME.fullmatch(p.name) and (p/FILENAME).is_file()]
    if len(runs)!=1:
        raise ValueError("Task0 ожидает ровно один результат соединения")
    run=runs[0]
    summary=_read_json(run/"summary.json",256_000)
    snapshot=_read_json(run/FILENAME,128_000)
    raw_path=run/"incoming.raw"
    if raw_path.is_symlink() or not raw_path.is_file():
        raise ValueError("Исходные байты Task0 отсутствуют")
    raw_bytes=raw_path.stat().st_size
    if not 0<raw_bytes<=MAX_TASK0_RAW_BYTES:
        raise ValueError("Недопустимая длина Task0 RAW")
    raw=raw_path.read_bytes()
    digest=sha256(raw).hexdigest()
    if (summary.get("mode")!=SOURCE_MODE or
            summary.get("end_reason")!=END_REASON or
            summary.get("read_only_no_app_payload_sent") is not True or
            summary.get("source_setrate_sent_bytes",0)!=0 or
            summary.get("capture_only_after_parser_error") is not False or
            summary.get("target_ipv4")!=expected_ip or
            type(summary.get("raw_bytes")) is not int or
            summary["raw_bytes"]!=len(raw) or
            summary.get("raw_sha256")!=digest or
            not _SHA.fullmatch(digest)):
        raise ValueError("Task0 RAW or passive session does not match Go evidence")
    image,valid,param_count,tail=_replay_original_param(raw)
    if (param_count==0 or
            summary.get("source_rx_nonempty_parameter_frames")!=param_count or
            summary.get("incomplete_final_frame_bytes")!=tail):
        raise ValueError("Task0 registered PARAM count or frame tail disagrees")
    if (snapshot.get("schema")!=SCHEMA or
            snapshot.get("original_task")!=0 or
            snapshot.get("session_id")!=run.name or
            snapshot.get("instrument_ipv4")!=expected_ip or
            snapshot.get("source_raw_sha256")!=digest or
            snapshot.get("raw_bytes")!=len(raw) or
            snapshot.get("device_commands_not_sent") is not True or
            snapshot.get("source_nonempty_param_received") is not True or
            snapshot.get("original_delphi_byte_parity_verified") is not False):
        raise ValueError("Task0 snapshot is not bound to original RAW")
    entries=snapshot.get("fields")
    specs=_safe_specs()
    if not isinstance(entries,list) or len(entries)!=len(specs):
        raise ValueError("Task0 field list cannot be trusted")
    values={}
    count=0
    for field,(key,address,words) in zip(entries,specs):
        if (not isinstance(field,dict) or field.get("key")!=key or
                field.get("register_address")!=address or
                field.get("word_count")!=words or
                type(field.get("valid")) is not bool):
            raise ValueError("Task0 source field metadata differs from IDP")
        is_valid=all(valid[address:address+words])
        raw_hex=image[address*2:(address+words)*2].hex() if is_valid else None
        if field["valid"] is not is_valid or field.get("raw_hex_le")!=raw_hex:
            raise ValueError("Task0 register differs from independently replayed RAW")
        if is_valid:count+=1
        values[key]={"address":f"0x{address:04X}",
                     "valid":is_valid,"raw_hex_le":raw_hex}
    if type(snapshot.get("config_fields_confirmed")) is not int or (
            snapshot["config_fields_confirmed"]!=count):
        raise ValueError("Task0 confirmed-field count invalid")
    return {
        "schema":SCHEMA,
        "source_original_task":0,
        "source":"source_go_task0_verified_incoming_raw",
        "device_ipv4":expected_ip,
        "source_raw_sha256":digest,
        "confirmed_fields":count,
        "fields":values,
        "read_only":True,
        "device_commands_sent":False,
        "original_delphi_byte_parity_verified":False,
    }
