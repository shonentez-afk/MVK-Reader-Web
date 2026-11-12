"""Stage111Z31BQ: restore local Tmvkform PageConfig Load/Edit/Save.

Original IDR: Unit115 007CFD44 LoadValuesFromFile, 007CF624 InputValue,
007D01E8 SaveValuesToFile; Unit128 00849970/0084A0F8 button handlers.
Safe offline source-format cycle, NOT a live device configuration writer.
No Qt, device/network access, or user-private file in repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from .original_config_readonly import (
    LocalConfigInspection,RawConfigCell,alarm_config_register,
    inspect_original_local_config,MAX_BYTES)
from .original_config_semantics import section_fields
from .original_config_input_draft import (
    SourceInputRejected,encode_source_text,source_type_for_raw_format)
from .original_config_idp_tables import source_type_description

SOURCE="IDR_TMvkCELL_LIST_LOCAL_CONFIG_ROUNDTRIP_STAGE111Z31BQ"
SAFE_VALUE=re.compile(r"[^;\r\n]{1,160}\Z")
EXTENSIONS=frozenset((".txt",".cfg",".conf"))


@dataclass(frozen=True)
class LocalEdit:
    address:int
    key:str
    format_char:str
    payload_sha256:str

    def report(self):
        return dict(register=f"0x{self.address:04X}",source_key=self.key,
                    format_char=self.format_char,
                    payload_sha256=self.payload_sha256,
                    original_live_register_written=False)


@dataclass(frozen=True)
class OriginalLocalConfigWorkspace:
    """Immutable source + candidate; original file always read-only."""
    original:LocalConfigInspection
    current:LocalConfigInspection
    input_file:Path
    edits:tuple[LocalEdit,...]=()

    @classmethod
    def load(cls,path):
        source=Path(path).absolute()
        checked=inspect_original_local_config(source)
        return cls(checked,checked,source)

    @property
    def changed(self):
        return bool(self.edits)

    @property
    def changed_count(self):
        return len(self.edits)

    def discard_changes(self):
        return OriginalLocalConfigWorkspace(
            self.original,self.original,self.input_file)

    def _patch(self,address,type_id,text,key,bounds=None):
        if type(address) is not int or not 0<=address<=0xfffe or address%2:
            raise SourceInputRejected("ctInvalidAddress")
        if not isinstance(text,str) or SAFE_VALUE.fullmatch(text) is None:
            raise SourceInputRejected("ctInvalidFormat")
        if key=="ConfigWifiPassword":
            raise SourceInputRejected("ctProtectedValue")
        info=source_type_description(type_id)
        payload=encode_source_text(type_id,text,bounds=bounds)
        byte_start,byte_end=address*2,address*2+len(payload)
        # Never edit credential material, including overlapping SSID strings.
        if max(byte_start,0x60*2)<min(byte_end,0x80*2):
            raise SourceInputRejected("ctProtectedValue")
        previous=self.current.value(address)
        if previous is not None and previous.format_char!=info["format_char"]:
            raise SourceInputRejected("ctInvalidCellType")
        for item in self.edits:
            if item.address!=address:
                other=self.current.value(item.address)
                other_type=source_type_for_raw_format(other.format_char)
                other_size=source_type_description(other_type)["source_storage_bytes"]
                if max(byte_start,other.address*2)<min(
                        byte_end,other.address*2+other_size):
                    raise SourceInputRejected("ctInvalidAddress")
        new=RawConfigCell(address,info["format_char"],text,
                          "<local-candidate>",0)
        cells={c.address:c for c in self.current.cells}
        cells[address]=new
        doc=LocalConfigInspection(
            tuple(cells[k] for k in sorted(cells)),
            self.original.file_digests,self.original.source)
        edits=tuple(x for x in self.edits if x.address!=address)
        original=self.original.value(address)
        if original is None or original.formatted!=new.formatted:
            edits+=(LocalEdit(
                address,key,info["format_char"],
                sha256(payload).hexdigest()),)
        return OriginalLocalConfigWorkspace(
            self.original,doc,self.input_file,edits)

    def edit_field(self,section,row,text,*,adc=None):
        """Typed and bounded source fields on IP, Calib and ADC pages."""
        fields,base=section_fields(section,adc=adc)
        if type(row) is not int or not 0<=row<len(fields):
            raise SourceInputRejected("ctIndexOutOfBounds")
        f=fields[row]
        return self._patch(
            base+f.offset,f.cell_type,text,f.key,f.bounds)

    def edit_alarm(self,adc,slot,field,text):
        """Edit only existing alarm fields with original FmtChar evidence.

        Missing alarm type or vendor bounds are never fabricated.
        """
        address=alarm_config_register(adc,slot,field)
        old=self.current.value(address)
        if old is None:
            raise SourceInputRejected("ctNoEntrySupported")
        return self._patch(
            address,source_type_for_raw_format(old.format_char),
            text,"Alarm."+field)

    def source_text(self):
        """Original loader-compatible FLATTENED address:format file.

        Original TMvkCellList SaveValuesToFile writes +offset then each
        address / GetValueWithFmt; titles are optional after ';'. Native
        binary equality/codepage parity is not asserted.
        """
        if not self.original.file_digests:
            raise ValueError("Load an explicit original text config first")
        if len(self.current.cells)>8192:
            raise ValueError("Too many source cells")
        lines=["; Local MVK source config; NO device connected","+0x0000"]
        for c in self.current.cells:
            if (type(c.address) is not int or
                    not 0<=c.address<=0xfffe or c.address%2 or
                    not isinstance(c.format_char,str) or
                    len(c.format_char)!=1 or
                    not isinstance(c.literal,str) or
                    SAFE_VALUE.fullmatch(c.literal) is None):
                raise ValueError("Source cell cannot be serialized")
            lines.append(f"0x{c.address:04X} {c.format_char}:{c.literal}")
        result="\n".join(lines)+"\n"
        if len(result.encode("utf-8"))>MAX_BYTES:
            raise ValueError("Original config file size exceeded")
        return result

    def _ensure_input_unchanged(self):
        refreshed=inspect_original_local_config(self.input_file)
        if (refreshed.file_digests!=self.original.file_digests or
                tuple((x.address,x.formatted) for x in refreshed.cells)!=
                tuple((x.address,x.formatted) for x in self.original.cells)):
            raise ValueError("Source config/includes changed since opening")

    def save_as(self,filename):
        """Explicitly create a NEW file, read it back, never write original."""
        self._ensure_input_unchanged()
        target=Path(filename).absolute()
        if (target.suffix.lower() not in EXTENSIONS or target.is_symlink()
                or target.exists() or not target.parent.is_dir()
                or target.parent.is_symlink()
                or target.resolve()==self.input_file.resolve()):
            raise ValueError(
                "Choose a NEW local .txt/.cfg/.conf; never overwrite original")
        try:
            raw=self.source_text().encode("cp1251","strict")
        except UnicodeEncodeError as exc:
            raise ValueError("Cannot safely represent original CP1251 text") from exc
        if not 0<len(raw)<=MAX_BYTES:
            raise ValueError("Source file size limit exceeded")
        created=False
        try:
            with target.open("xb") as fp:
                created=True
                fp.write(raw)
            readback=inspect_original_local_config(target)
            if tuple((x.address,x.formatted) for x in readback.cells)!=tuple(
                    (x.address,x.formatted) for x in self.current.cells):
                raise ValueError("Saved source parser roundtrip did not match")
            return {
                "source":SOURCE,
                "local_source_file_created":True,
                "source_loader_roundtrip_verified":True,
                "saved_cells":len(readback.cells),
                "edited_cells":len(self.edits),
                "saved_sha256":sha256(raw).hexdigest(),
                "original_live_device_config_verified":False,
                "original_delphi_bytes_and_codepage_verified":False,
                "original_source_modified":False,
                "device_commands_or_calibration_executed":False,
                "private_paths_values_or_secrets_in_report":False,
            }
        except Exception:
            if created:
                target.unlink(missing_ok=True)
            raise

    def describe(self):
        return {
            "source":SOURCE,
            "original_file_digests":len(self.original.file_digests),
            "original_cells":len(self.original.cells),
            "candidate_cells":len(self.current.cells),
            "unsaved_edits":len(self.edits),
            "edits":[x.report() for x in self.edits],
            "hardware_write_enabled":False,
            "local_original_changed":False,
            "original_win32_runtime_compatibility_verified":False,
        }
