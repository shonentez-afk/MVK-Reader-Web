"""Stage111Z31BT: functional ORIGINAL PageCalib local worksheet.

Private Projects/mvkform.dfm, _Unit128.pas (provided by operator):
 * bCalibAClick at 0084C9A4 selects 11/14/14/1/9 original tests.
 * bCalibClearClick at 0084CA58 creates 11 cols x 77 rows.
 * bCalibSaveClick at 0084D9D0 creates CALIB-*.csv: sep=| then
   each source TStringGrid cell plus a trailing '|' (11 per row).
 * bCalibGenerateClick at 0084D474 evaluates row=8, columns 2,3..10:
   ratio = (observed * 1.001001001001...) / reference, .8..1.2,
   new_calibration_gain = ConfigCalibCellList.GetFloat(index)/ratio.
 * bCalibStartClick at 0084DD30 creates TMVKCalibThread and uses
   configured serial-generator port; this is NEVER invoked here.

We can inspect an operator-provided original CALIB CSV, preserve the
source matrix and derive a *local proposal*. No device, generator, serial,
calibration write, or live hardware trust. No assumed missing measurements.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from hashlib import sha256
from pathlib import Path
import json
import math
import re
import struct

from .original_config_readonly import LocalConfigInspection

SOURCE="ORIGINAL_IDR_PAGECALIB_LOCAL_WORKBENCH_STAGE111Z31BT"
GRID_ROWS=77
GRID_COLS=11
STEP_GROUPS=(("A","Ускорение",11),("V","Скорость",14),
             ("D","Перемещение",14),("DR","Динамический диапазон",1),
             ("T","Частота вращения",9))
GROUP_ROW_HEADERS=(0,14,25,36,47)
DFM_LEFT_WIDTH=369
DFM_SPLITTER_WIDTH=8
DFM_RIGHT_WIDTH=615
DFM_TAB_HEIGHT=36
DFM_CALIB_TOOLS_HEIGHT=63
DFM_CALIB_SELECT_HEIGHT=51
DFM_RESULT_TOOLS_HEIGHT=63
DFM_START=(6,8,107,41)
DFM_PORT=(216,16,129,24)
DFM_SAVE_BUTTONS=(("bCalibSave",6,8,155,41),
                  ("bCalibClear",174,8,155,41),
                  ("bCalibGenerate",342,8,155,41))
DFM_UNIT_BUTTONS=(("A",1,6,6,43,35),("V",2,55,6,43,35),
                  ("D",3,104,6,43,35),("DR",4,153,6,43,35),
                  ("T",5,202,6,43,35))
CALIB_SOURCE_TABS=2
GAIN_REGISTERS=tuple(0x20+2*i for i in range(8))
# Rounded source Extended multiplier literal at _Unit128:0084D5CE.
SOURCE_RATIO_DENOMINATOR_ADJUSTMENT=1.001001001001
SOURCE_RATIO_MIN=.8
SOURCE_RATIO_MAX=1.2
MAX_CSV_BYTES=512*1024
MAX_CELL_CHARS=140
MAX_LOG_BYTES=256*1024
_DECIMAL=re.compile(r"[+-]?(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def _source_number(value,kind):
    if not isinstance(value,str) or _DECIMAL.fullmatch(value.strip()) is None:
        raise ValueError(f"Original {kind}: finite numeric source field required")
    x=float(value.strip().replace(",","."))
    if not math.isfinite(x) or x<=0 or x>1e8:
        raise ValueError(f"Original {kind}: positive finite source required")
    return x


def _float32(x):
    try: result=struct.unpack("<f",struct.pack("<f",x))[0]
    except (OverflowError,struct.error) as exc:
        raise ValueError("Candidate gain out of original float32 range") from exc
    if not math.isfinite(result) or result<=0:
        raise ValueError("Candidate gain not a positive float32")
    return result


def blank_original_grid():
    """bCalibClear grid dimensions/header locations, no invented values."""
    rows=[[""]*GRID_COLS for _ in range(GRID_ROWS)]
    for index,(symbol,label,count) in enumerate(STEP_GROUPS):
        top=GROUP_ROW_HEADERS[index]
        rows[top][0]=label
        rows[top+1][0]="Частота, Гц"
        rows[top+1][1]="U, мВ СКЗ"
        rows[top+1][2]={
            "A":"Ускорение, м/с² СКЗ",
            "V":"Скорость, мм/с СКЗ",
            "D":"Перемещение, мкм СКЗ",
            "DR":"Динамический диапазон",
            "T":"Частота вращения",
        }[symbol]
        for adc in range(8):
            rows[top+1][3+adc]=f"АЦП {adc+1}"
    return tuple(tuple(r) for r in rows)


def _validate_grid(rows):
    data=tuple(tuple(row) for row in rows)
    if len(data)!=GRID_ROWS or any(len(row)!=GRID_COLS for row in data):
        raise ValueError("Source PageCalib grid must be EXACTLY 77x11")
    for row in data:
        for cell in row:
            if (not isinstance(cell,str) or len(cell)>MAX_CELL_CHARS or
                    any(ch in cell for ch in ("\x00","\r","\n","|"))):
                raise ValueError("Original CALIB cell invalid or oversized")
    return data


def _read_bounded(file,max_bytes,extensions):
    src=Path(file).absolute()
    if (src.suffix.lower() not in extensions or src.is_symlink()
            or not src.is_file() or src.stat().st_size>max_bytes
            or src.stat().st_size<1):
        raise ValueError("Choose a bounded ordinary local source file")
    raw=src.read_bytes()
    if len(raw)>max_bytes or len(raw)!=src.stat().st_size:
        raise ValueError("Source file changed or oversized")
    digest=sha256(raw).hexdigest()
    if raw.startswith(b"\xff\xfe"):
        decoded=raw[2:].decode("utf-16le")
    elif raw.startswith(b"\xef\xbb\xbf"):
        decoded=raw[3:].decode("utf-8")
    else:
        try:decoded=raw.decode("utf-8")
        except UnicodeDecodeError:decoded=raw.decode("cp1251")
    if "\x00" in decoded:
        raise ValueError("Source text contains unexpected NUL")
    return src,digest,decoded


def _parse_original_csv(text):
    lines=text.splitlines()
    if len(lines)!=GRID_ROWS+1 or lines[0].strip()!="sep=|":
        raise ValueError("Original CALIB CSV must have sep=| + 77 rows")
    rows=[]
    for text_row in lines[1:]:
        parts=text_row.split("|")
        if len(parts)!=GRID_COLS+1 or parts[-1]!="":
            raise ValueError("Original TStringGrid CSV requires 11 cells plus trailing |")
        rows.append(tuple(parts[:-1]))
    return _validate_grid(rows)


@dataclass(frozen=True)
class CandidateGain:
    adc:int
    register:int
    reference:float
    observed:float
    old_gain:float
    original_ratio_candidate:float
    new_gain_float32_candidate:float

    def as_dict(self):
        return {
            "adc":self.adc,
            "source_calib_register":f"0x{self.register:04X}",
            "source_row":8,
            "source_column":self.adc+2,
            "reference_column":2,
            "reference":self.reference,
            "observed":self.observed,
            "old_gain":self.old_gain,
            "original_ratio_candidate":self.original_ratio_candidate,
            "new_gain_float32_candidate":self.new_gain_float32_candidate,
            "original_runtime_x87_bit_parity_verified":False,
            "device_write_executed":False,
        }


@dataclass(frozen=True)
class CalibrationProposal:
    entries:tuple[CandidateGain,...]
    grid_sha256:str
    config_source_sha256:str
    source:str=SOURCE

    def report(self):
        return {
            "source":self.source,
            "interpretation":"OFFLINE_SOURCE_FORMULA_CANDIDATE_ONLY",
            "source_row":8,
            "source_reference_column":2,
            "source_measured_columns":[3,4,5,6,7,8,9,10],
            "source_ratio_limits":[SOURCE_RATIO_MIN,SOURCE_RATIO_MAX],
            "source_adjustment":SOURCE_RATIO_DENOMINATOR_ADJUSTMENT,
            "original_grid_sha256":self.grid_sha256,
            "original_config_cells_sha256":self.config_source_sha256,
            "entries":[entry.as_dict() for entry in self.entries],
            "original_live_calibthread_ran":False,
            "original_tmkvcelllist_inputvalue_called":False,
            "physical_calibration_verified":False,
            "uploadable_original_calib_txt_created":False,
            "source_formula_candidate_not_original_x87_parity":True,
            "device_commands_sent":False,
        }


@dataclass(frozen=True)
class OriginalCalibrationWorkspace:
    steps:tuple[bool,...]
    grid:tuple[tuple[str,...],...]
    log_lines:tuple[str,...]=()
    source_file:Path|None=None
    source_sha256:str|None=None
    log_source_sha256:str|None=None
    source:str=SOURCE

    def __post_init__(self):
        if (len(self.steps)!=sum(g[2] for g in STEP_GROUPS) or
                any(type(checked) is not bool for checked in self.steps)):
            raise ValueError("Source PageCalib requires 49 checked test flags")
        _validate_grid(self.grid)
        if len(self.log_lines)>4096 or any(
                not isinstance(line,str) or len(line)>300
                for line in self.log_lines):
            raise ValueError("Original calibration log exceeds bounded view")

    @classmethod
    def initial(cls):
        return cls((True,)*sum(x[2] for x in STEP_GROUPS),
                   blank_original_grid())

    @classmethod
    def load_csv(cls,path,*,steps=None):
        src,digest,text=_read_bounded(path,MAX_CSV_BYTES,{".csv"})
        grid=_parse_original_csv(text)
        selected=steps if steps is not None else cls.initial().steps
        return cls(tuple(selected),grid,source_file=src,
                   source_sha256=digest)

    def require_source_unchanged(self):
        if self.source_file is None or self.source_sha256 is None:
            return
        source=self.source_file
        if (source.is_symlink() or not source.is_file() or
                sha256(source.read_bytes()).hexdigest()!=self.source_sha256):
            raise ValueError("Original CALIB input changed since loading")

    @property
    def source_grid_loaded(self):
        return self.source_file is not None

    @property
    def checked_steps(self):
        return sum(self.steps)

    def select_step(self,index:int,checked:bool):
        if type(index) is not int or not 0<=index<len(self.steps):
            raise ValueError("Original calibration step index invalid")
        if type(checked) is not bool:
            raise ValueError("Calibration checkbox state must be Boolean")
        updated=list(self.steps)
        updated[index]=checked
        return replace(self,steps=tuple(updated))

    def toggle_group(self,tag:int):
        """_Unit128:0084C9A4: inverse of FIRST item, propagate within group."""
        if type(tag) is not int or not 1<=tag<=len(STEP_GROUPS):
            raise ValueError("Original bCalibAClick Tag must be 1..5")
        begin=sum(g[2] for g in STEP_GROUPS[:tag-1])
        count=STEP_GROUPS[tag-1][2]
        value=not self.steps[begin]
        updated=list(self.steps)
        updated[begin:begin+count]=[value]*count
        return replace(self,steps=tuple(updated))

    def clear_grid(self):
        """bCalibClear resets 11x77; original log is NOT cleared here."""
        return replace(self,grid=blank_original_grid(),source_file=None,
                       source_sha256=None)

    def open_log(self,path):
        src,digest,text=_read_bounded(path,MAX_LOG_BYTES,{".log",".txt"})
        lines=tuple(text.splitlines())
        if len(lines)>4096:
            raise ValueError("Original log exceeds 4096 lines")
        return replace(self,log_lines=lines,log_source_sha256=digest)

    def _csv_text(self):
        _validate_grid(self.grid)
        # Original Delphi writes every cell followed by '|'; it has no
        # formula escaping. To avoid spreadsheet formula execution in the
        # restored app, refuse unsafe source cells, NOT silently mutate them.
        for row in self.grid:
            for cell in row:
                if cell.lstrip().startswith(("=","@","+")):
                    try: _source_number(cell,"CSV numeric field")
                    except ValueError as exc:
                        raise ValueError("Potential spreadsheet formula in CALIB cell") from exc
        return "sep=|\n"+"\n".join("|".join(row)+"|" for row in self.grid)+"\n"

    def export_csv(self,destination):
        self.require_source_unchanged()
        target=Path(destination).absolute()
        if (target.suffix.lower()!=".csv" or target.is_symlink()
                or target.exists() or not target.parent.is_dir()
                or target.parent.is_symlink()):
            raise ValueError("Choose a NEW local CALIB CSV file")
        try: payload=self._csv_text().encode("utf-8-sig")
        except UnicodeError as exc:raise ValueError("CALIB text encoding error") from exc
        if len(payload)>MAX_CSV_BYTES:
            raise ValueError("Source calibration CSV exceeds size budget")
        created=False
        try:
            with target.open("xb") as fp:
                created=True
                fp.write(payload)
            check=OriginalCalibrationWorkspace.load_csv(target)
            if check.grid!=self.grid:
                raise ValueError("Original CALIB CSV readback mismatch")
            return {
                "source":SOURCE,
                "original_shape":[GRID_ROWS,GRID_COLS],
                "original_delimiter":"sep=|",
                "saved_csv_sha256":sha256(target.read_bytes()).hexdigest(),
                "independent_source_csv_readback_passed":True,
                "local_file_created":True,
                "original_live_calibthread_executed":False,
                "device_commands_sent":False,
                "original_delphi_codepage_byte_parity_verified":False,
            }
        except Exception:
            if created:target.unlink(missing_ok=True)
            raise

    def candidate(self,config:LocalConfigInspection):
        """IDR bCalibGenerate row8/cols2..10 with verified local config.

        The source routine saves a live CALIB-*.txt to be used with hardware.
        This version NEVER emits uploadable config. It exposes only a
        machine-readable OFFLINE candidate for human review.
        """
        self.require_source_unchanged()
        if not self.source_grid_loaded or not isinstance(config,LocalConfigInspection):
            raise ValueError("Original CALIB CSV and local config source required")
        reference=_source_number(self.grid[8][2],"reference row8, col2")
        entries=[]
        for index,address in enumerate(GAIN_REGISTERS):
            measured=_source_number(
                self.grid[8][3+index],f"ADC{index+1} row8")
            cell=config.value(address)
            if cell is None or cell.format_char!="f":
                raise ValueError(f"ADC{index+1}: original float config gain absent")
            old_gain=_float32(_source_number(cell.literal,f"ADC{index+1} gain"))
            # x87 _Unit128:0084D612-0084D617: FLD stored measured*mult
            # above reference, then FDIVRP ST(1),ST(0). Ratio is thus
            # (MEASURED*MULT)/REFERENCE, not the inverse. Subsequently
            # 0084D6B3 divides the original gain by that ratio.
            ratio=(measured*SOURCE_RATIO_DENOMINATOR_ADJUSTMENT)/reference
            if (not math.isfinite(ratio) or
                    not SOURCE_RATIO_MIN<=ratio<=SOURCE_RATIO_MAX):
                raise ValueError(f"ADC{index+1}: calibration deviation exceeds source 0.8..1.2")
            proposed=_float32(old_gain/ratio)
            entries.append(CandidateGain(index+1,address,reference,measured,
                                         old_gain,ratio,proposed))
        matrix_digest=sha256(self._csv_text().encode("utf-8")).hexdigest()
        gains_digest=sha256(
            (";".join(f"{entry.register:04X}:{entry.old_gain:.9g}"
                      for entry in entries)).encode("ascii")).hexdigest()
        return CalibrationProposal(tuple(entries),matrix_digest,gains_digest)

    @staticmethod
    def save_candidate_json(proposal:CalibrationProposal,destination):
        if not isinstance(proposal,CalibrationProposal):
            raise ValueError("Original local proposal absent")
        target=Path(destination).absolute()
        if (target.suffix.lower()!=".json" or target.is_symlink()
                or target.exists() or not target.parent.is_dir()
                or target.parent.is_symlink()):
            raise ValueError("Choose a NEW local candidate JSON")
        payload=(json.dumps(proposal.report(),ensure_ascii=False,indent=2)+"\n").encode("utf-8")
        if len(payload)>64*1024:raise ValueError("Candidate report too large")
        created=False
        try:
            with target.open("xb") as f:
                created=True
                f.write(payload)
            check=json.loads(target.read_text(encoding="utf-8"))
            if check!=proposal.report():raise ValueError("Candidate JSON verification failed")
            return {
                "source":SOURCE,
                "local_json_created":True,
                "adc_gain_candidates":len(proposal.entries),
                "sha256":sha256(payload).hexdigest(),
                "not_a_device_upload_file":True,
                "device_io_executed":False,
            }
        except Exception:
            if created:target.unlink(missing_ok=True)
            raise


assert sum(g[2] for g in STEP_GROUPS)==49
assert len(GROUP_ROW_HEADERS)==5 and len(GAIN_REGISTERS)==8
