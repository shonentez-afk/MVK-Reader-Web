"""Stage111Z31BR: source-checked PageFile selections and LOCAL data export.

_PRIVATE ORIGINAL_: mvkform.dfm PageFile has tcFileChannels 1 tab,
cbFileChannels 10 checked entries, tcFileActions 2 tabs (index0:
cbFileSpec/cbFileValues, index1: pnFileAdc 207px). _Unit128:
0084E914 bWriteAdcClick copies ten flags into TMVKThread.WriteData;
0084E988 bWriteValuesClick copies dynamic SPEC/Values/Band/Tacho flags.
0084C95C/0084C980 enable the folder/custom-name text only when checked.
Real TMVKThread live writer is NOT implemented by this offline module.

The module makes those selections useful for a CHECKED existing Native
R6.1 ZIP or direct BIN/TSXML: it copies source RAW/TSXML byte-for-byte
and optionally emits selection-filtered verified DSP rows. It does NOT
claim the resulting folder/CSV is original MVKView recorder output.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import csv
import io
import json
import re
import shutil
import zipfile

from .offline_export import BIN_NAME_RE,require_members
from .offline_measurement_flow import OfflineMeasurementFlow
from .original_file_workbench import source_file_workbench

SOURCE="IDR_PAGEFILE_10_CHANNEL_2_TAB_OFFLINE_FUNCTIONAL_STAGE111Z31BR"
CHANNEL_COUNT=10
SPEC_COUNT=43
ADC_VALUE_COUNT=24
BAND_VALUE_COUNT=43
TACH_RESULT_COUNT=6
VALUE_COUNT=ADC_VALUE_COUNT+BAND_VALUE_COUNT+TACH_RESULT_COUNT
ORIGINAL_DFM_FILE_ACTION_TABS=2
ORIGINAL_DFM_FILE_ADC_HEIGHT=207
ORIGINAL_DFM_LEFT_WIDTH=369
ORIGINAL_DFM_SPEC_WIDTH=256
ORIGINAL_DFM_VALUES_WIDTH=343
ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE='"RunUp"dd-mm-yyyy hh-nn-ss'
_SAFE_TOKEN=re.compile(r"[A-Za-z0-9_\-. ]{1,70}\Z")
_MAX_EXPORT_FILES=27
_CHUNK=1024*1024


def _bool_tuple(values,count,name):
    values=tuple(values)
    if len(values)!=count or any(type(x) is not bool for x in values):
        raise ValueError(f"{name}: requires {count} original boolean flags")
    return values


@dataclass(frozen=True)
class OriginalPageFileSelection:
    """Immutable original 10 + 43 + 24/43/6 checkbox contract.

    Original live acquisition flags have not been sent to Go Native R6.1.
    Native recorder remains its independent, already validated mode.
    """
    channels:tuple[bool,...]
    spec:tuple[bool,...]
    values:tuple[bool,...]

    def __post_init__(self):
        _bool_tuple(self.channels,CHANNEL_COUNT,"channels")
        _bool_tuple(self.spec,SPEC_COUNT,"spec")
        _bool_tuple(self.values,VALUE_COUNT,"values")

    @classmethod
    def for_flow(cls,flow:OfflineMeasurementFlow):
        if not isinstance(flow,OfflineMeasurementFlow):
            raise ValueError("Source-bound measurement required")
        flow.source_record()
        channels=tuple(i+1 in flow.available_channels if i<8 else False
                       for i in range(CHANNEL_COUNT))
        native=not flow.direct_bin
        return cls(channels,
                   (True,)*SPEC_COUNT if native else (False,)*SPEC_COUNT,
                   ((True,)*(ADC_VALUE_COUNT+BAND_VALUE_COUNT)
                    +(False,)*TACH_RESULT_COUNT) if native
                   else (False,)*VALUE_COUNT)

    def checked(self,group):
        if group not in ("channels","spec","values"):
            raise ValueError("Original source group missing")
        return tuple(i for i,x in enumerate(getattr(self,group)) if x)

    def set_checked(self,group,index,checked,*,flow:OfflineMeasurementFlow):
        if type(index) is not int or type(checked) is not bool:
            raise ValueError("Source selection index/flag invalid")
        self.validate(flow)
        if group not in ("channels","spec","values"):
            raise ValueError("Source selection group invalid")
        original=getattr(self,group)
        if not 0<=index<len(original):
            raise ValueError("Original PageFile list index outside source")
        if checked:
            if (group=="channels" and
                    (index>=8 or index+1 not in flow.available_channels)):
                raise ValueError("No verified ADC/TACH raw stream for this flag")
            if group=="spec" and flow.direct_bin:
                raise ValueError("Original SPEC cannot be inferred from BIN")
            if group=="values" and (
                    flow.direct_bin or index>=ADC_VALUE_COUNT+BAND_VALUE_COUNT)):
                raise ValueError("Missing verified VALUES or original TACH export")
        updated=list(original)
        updated[index]=checked
        result=replace(self,**{group:tuple(updated)})
        result.validate(flow)
        return result

    def validate(self,flow:OfflineMeasurementFlow):
        if not isinstance(flow,OfflineMeasurementFlow):
            raise ValueError("Selected file no longer has trusted Core source")
        flow.source_record()  # verifies ADC, SHA, source BIN and session
        if any(self.channels[i] for i in range(8)
               if i+1 not in flow.available_channels):
            raise ValueError("A selected ADC was absent from the source")
        if self.channels[8] or self.channels[9]:
            raise ValueError("Original TACH1/2 do not have native RAW stream")
        if flow.direct_bin and (any(self.spec) or any(self.values)):
            raise ValueError("BIN source does not contain authenticated DSP")
        if any(self.values[ADC_VALUE_COUNT+BAND_VALUE_COUNT:]):
            raise ValueError("TACH file writes not yet authenticated")
        return self

    def report(self):
        return {
            "source":SOURCE,
            "original_channel_flag_count":CHANNEL_COUNT,
            "original_spec_flag_count":SPEC_COUNT,
            "original_value_flag_count":VALUE_COUNT,
            "selected_adcs":[i+1 for i in self.checked("channels") if i<8],
            "selected_spec_indices":list(self.checked("spec")),
            "selected_value_indices":list(self.checked("values")),
            "original_live_thread_writer_restored":False,
            "native_r6_recorder_filter_applied":False,
            "physical_calibration_verified":False,
        }


@dataclass(frozen=True)
class OriginalFileNameOptions:
    write_tsxml:bool=True
    use_folder_prefix:bool=True
    use_custom_name:bool=True
    folder_prefix:str=ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE
    custom_name:str=""

    def __post_init__(self):
        if any(type(x) is not bool for x in (
                self.write_tsxml,self.use_folder_prefix,self.use_custom_name)):
            raise ValueError("Original DFM PageFile flags are Boolean")

    @staticmethod
    def _token(value):
        if not isinstance(value,str) or not _SAFE_TOKEN.fullmatch(value):
            raise ValueError("File prefix/name must be a safe single filename token")
        if value.strip() in ("",".","..") or value.endswith(" "):
            raise ValueError("Blank or special folder name")
        return value.strip()

    def export_folder_name(self,flow:OfflineMeasurementFlow,when:datetime):
        if not isinstance(when,datetime) or when.tzinfo is None:
            raise ValueError("Timestamp must be explicitly timezone-aware")
        flow.source_record()
        if self.use_folder_prefix:
            if self.folder_prefix==ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE:
                # Only this recovered format string is mapped here.
                # Timestamp = export action time, NOT instrument sample time.
                prefix="RunUp"+when.strftime("%d-%m-%Y %H-%M-%S")
            else:
                prefix=self._token(self.folder_prefix)
        else:
            prefix="MVK_Local"
        if self.use_custom_name:
            device=self._token(self.custom_name)
        else:
            device=self._token(flow.session.serial)
        fingerprint=flow.source_record()["source_bin_sha256"][:12]
        return f"{prefix}_{device}_{fingerprint}"


def _copy_stream(reader,output_file,expected_sha):
    digest=sha256()
    length=0
    with output_file.open("xb") as out:
        while True:
            part=reader.read(_CHUNK)
            if not part:
                break
            length+=len(part)
            if length>42_000_000:
                # Direct Single BIN <=40M plus verified original BIN header; TSXML <=64k.
                raise ValueError("Unexpectedly large source file")
            digest.update(part)
            out.write(part)
    actual=digest.hexdigest()
    if actual.lower()!=expected_sha.lower():
        raise ValueError("Selected source file SHA changed")
    return {"name":output_file.name,"byte_count":length,"sha256":actual}


def _write_checked_csv(path,rows):
    with path.open("x",encoding="utf-8",newline="") as fp:
        w=csv.writer(fp)
        w.writerow(("АЦП","Группа","Исходный индекс","Проверенное значение"))
        w.writerows(rows)
    return {"name":path.name,"sha256":sha256(path.read_bytes()).hexdigest(),
            "count":len(rows)}


def export_selected_original_pagefile(
        flow:OfflineMeasurementFlow,selection:OriginalPageFileSelection,
        options:OriginalFileNameOptions,parent_folder:str|Path,
        *,when:datetime|None=None) -> dict:
    """Real local export of verified source, NEVER original live recorder.

    Only an explicit selected *new* folder; preexisting paths never written.
    Input ZIP/TSXML and hashes are independently verified before copying.
    On failure remove ONLY the newly-created output, never original inputs.
    """
    if not isinstance(options,OriginalFileNameOptions):
        raise ValueError("Original PageFile option model required")
    if not isinstance(selection,OriginalPageFileSelection):
        raise ValueError("Original PageFile selection model required")
    selection.validate(flow)
    selected=[i+1 for i in selection.checked("channels") if i<8]
    if not selected:
        raise ValueError("At least one actual verified ADC must be selected")
    folder=Path(parent_folder).absolute()
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Output parent must be a real existing local folder")
    time=when if when is not None else datetime.now(timezone.utc)
    name=options.export_folder_name(flow,time)
    target=folder/name
    if target.exists() or target.is_symlink():
        raise ValueError("A local export with this name already exists")
    source=flow.session
    manifest_items=[]
    raw_rows=[]
    created=False
    try:
        target.mkdir(exist_ok=False)
        created=True
        if flow.direct_bin:
            for adc in selected:
                ch=next((c for c in source.channel_files if c.adc==adc),None)
                if ch is None:
                    raise ValueError("Selected original channel absent from BIN")
                flow.select(channel=adc).source_record()
                for path,digest in ((ch.bin_path,ch.bin_sha256),
                                    *((((ch.tsxml_path,ch.tsxml_sha256),))
                                      if options.write_tsxml else ())):
                    if path.is_symlink() or not path.is_file():
                        raise ValueError("Original selected file is no longer available")
                    with path.open("rb") as fp:
                        manifest_items.append(
                            _copy_stream(fp,target/path.name,digest))
        else:
            with zipfile.ZipFile(source.path) as z:
                members,audit=require_members(z)
                expected=audit["output_file_sha256"]
                for adc in selected:
                    flow.select(channel=adc).source_record()
                    original_name=members[adc-1]
                    names=(original_name,original_name+".tsxml") if (
                        options.write_tsxml) else (original_name,)
                    for filename in names:
                        if not BIN_NAME_RE.fullmatch(original_name):
                            raise ValueError("Unsafe original native BIN filename")
                        digest=expected.get(filename)
                        if not isinstance(digest,str) or len(digest)!=64:
                            raise ValueError("Source manifest SHA is missing")
                        with z.open(filename) as fp:
                            manifest_items.append(
                                _copy_stream(fp,target/filename,digest))
            if any(selection.spec) or any(selection.values):
                status=flow.status_snapshot()
                if status is None:
                    raise ValueError("Verified source DSP snapshot is absent")
                for adc in selected:
                    model=source_file_workbench(
                        flow.select(channel=adc),verified_status=status)
                    if not model.dsp_verified_for_selection:
                        raise ValueError("Cannot export unverified result values")
                    if len(model.value_rows)!=ADC_VALUE_COUNT or (
                            len(model.spectrum_rows)!=SPEC_COUNT):
                        raise ValueError("Source result counts do not match original")
                    for index in selection.checked("spec"):
                        raw_rows.append((adc,"SPEC",index,
                                         model.spectrum_rows[index]))
                    for index in selection.checked("values"):
                        if index<ADC_VALUE_COUNT:
                            raw_rows.append((adc,"VALUES",index,
                                             model.value_rows[index]))
                        elif index<ADC_VALUE_COUNT+BAND_VALUE_COUNT:
                            raw_rows.append((
                                adc,"VALUES third-octave",index,
                                model.spectrum_rows[index-ADC_VALUE_COUNT]))
                if raw_rows:
                    manifest_items.append(
                        _write_checked_csv(target/"PAGEFILE_SELECTED_VALUES.csv",
                                           raw_rows))
        manifest={
            "schema":SOURCE,
            "recording_vs_offline":"OFFLINE_VERIFIED_SOURCE_EXPORT_ONLY",
            "original_mvkview_tmkvthread_write_data_executed":False,
            "original_mvkview_tmkvthread_write_values_executed":False,
            "device_io_executed":False,
            "source_kind":"BIN_TSXML" if flow.direct_bin else "NATIVE_R6_ZIP",
            "source_bin_sha256":flow.source_record()["source_bin_sha256"],
            "selected_channels":selected,
            "source_pagefile_checklists":selection.report(),
            "source_pagefile_settings":{
                "cbFileWriteXml":options.write_tsxml,
                "cbFileFolderPrefix":options.use_folder_prefix,
                "cbFileMvkName":options.use_custom_name,
            },
            "selection_rows":len(raw_rows),
            "files":manifest_items,
            "original_file_format_pixel_runtime_parity_verified":False,
            "timestamp_semantics":"EXPORT_ACTION_UTC_NOT_INSTRUMENT_TIME",
        }
        (target/"PAGEFILE_SELECTION.json").write_text(
            json.dumps(manifest,ensure_ascii=False,indent=2),
            encoding="utf-8")
        return {
            "source":SOURCE,"output_folder":str(target),
            "files_written":len(manifest_items)+1,
            "selected_channels":selected,
            "selected_result_rows":len(raw_rows),
            "source_files_copied_without_resampling":True,
            "device_io_executed":False,
            "native_r6_capture_selection_actuated":False,
            "original_writer_byte_parity_verified":False,
        }
    except Exception:
        if created:
            shutil.rmtree(target)
        raise
