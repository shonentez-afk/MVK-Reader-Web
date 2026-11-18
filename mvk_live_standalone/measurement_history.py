"""Durable MVK01 history: true original AUX4700 frames + operator-saved ADC windows.

Native Go ALREADY writes every decoded AUX4700 for all eight channels to
<run>/aux4700.jsonl. Import complete lines incrementally with a durable byte
cursor, not one sampled GUI update per 900 ms. SQLite preserves 115 original
cells per ADC/update and their original timestamp; NULL stays unavailable.

Calibrated ADC NPZ windows have a separate provenance, unit and SHA check.
Local metrics and re-FFT from saved samples NEVER masquerade as vendor DSP or
a hardware reference. No networking, instrument configuration or TACH.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

import numpy as np

from .advanced import extended_time_features, broadband_rms
from .vibration import analyze_vibration
from .original_dsp import OriginalDSPBands, read_original_dsp_bands, _THIRD_HZ
from .recordings import load_snapshot, save_snapshot, OfflineSnapshot

MAX_JSONL_LINE=16384
MAX_IMPORT_ROWS=240
MAX_PLOT_ROWS=15000
MAX_OVERLAYS=8
VENDOR="MVK_DSP_ORIGINAL_AUX4700"
LOCAL="APP_DERIVED_FROM_SAVED_ADC"

_LOCAL_METRICS={
    "time_rms":("ВУ СКЗ временного окна","м/с²"),
    "time_peak":("ВУ пик временного окна","м/с²"),
    "time_pp":("ВУ пик-пик временного окна","м/с²"),
    "crest":("Крест-фактор","безразм."),
    "kurtosis":("Куртозис Pearson","безразм."),
    "skew":("Асимметрия","безразм."),
    "impulse":("Импульсный фактор","безразм."),
    "shape":("Фактор формы","безразм."),
    "clearance":("Фактор зазора","безразм."),
    "velocity_rms_10_1000":("ВС СКЗ 10–1000 Гц · из АЦП","мм/с"),
    "fft_acceleration_peak":("FFT ВУ · максимум линии","м/с²"),
    "fft_acceleration_peak_hz":("FFT ВУ · частота максимума","Гц"),
    "fft_velocity_peak":("FFT ВС · максимум линии","мм/с"),
    "fft_velocity_peak_hz":("FFT ВС · частота максимума","Гц"),
    "fft_displacement_peak":("FFT ВП · максимум линии","мкм"),
    "fft_displacement_peak_hz":("FFT ВП · частота максимума","Гц"),
}


@dataclass(frozen=True)
class HistoryEntry:
    key: str
    source: str
    adc: int
    time_utc: str
    session: str
    detail: str
    rate_hz: int | None = None

    @property
    def pretty(self)->str:
        return (f"{self.time_utc[:19].replace('T',' ')}Z · "
                f"АЦП {self.adc} · {self.detail}")


def _utc(value: str) -> str:
    if not isinstance(value,str) or len(value)>80:
        raise ValueError("Неизвестная временная метка сохранённого измерения")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("Некорректная дата в измерении") from exc
    if dt.tzinfo is None:
        raise ValueError("Нужно время измерения с часовым поясом")
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _num(v):
    return None if v is None or (type(v) in (int,float) and
                                 not math.isfinite(v)) else v


def metric_details(metric: str) -> tuple[str,str]:
    if metric in _LOCAL_METRICS:
        return _LOCAL_METRICS[metric]
    if metric.startswith("third_octave:"):
        i=int(metric.split(":")[1])
        if not 0<=i<43:raise ValueError("Index of third octave out of range")
        return (f"Прибор · 1/3 октавы {float(_THIRD_HZ[i]):g} Гц · СКЗ",
                "м/с²")
    prefix,index=metric.split(":")
    i=int(index)
    if prefix not in ("band_rms","band_peak_equiv","band_span_equiv") or not 0<=i<24:
        raise ValueError("Invalid original calculation index")
    label={"band_rms":"СКЗ","band_peak_equiv":"Пик",
           "band_span_equiv":"Размах"}[prefix]
    return (f"Прибор · {label} · расчётная позиция {i+1}",
            "единица прибора не подтверждена")


def _metric_value(row: dict,metric:str) -> float | None:
    if metric.startswith("third_octave:"):
        name="third_octave_acceleration_rms"; index=int(metric.split(":")[1])
    else:
        name,index=metric.split(":")
        index=int(index)
    array=row.get(name)
    if not isinstance(array,list) or index<0 or index>=len(array):
        return None
    v=array[index]
    return float(v) if type(v) in (int,float) and math.isfinite(v) else None


def _local_features(x:np.ndarray,fs:int)->dict[str,float]:
    f=extended_time_features(x)
    metrics={
        "time_rms":f.rms_m_s2,
        "time_peak":f.peak_m_s2,
        "time_pp":f.peak_to_peak_m_s2,
        "crest":f.crest_factor,
        "kurtosis":f.kurtosis_pearson,
        "skew":f.skewness,
        "impulse":f.impulse_factor,
        "shape":f.shape_factor,
        "clearance":f.clearance_factor,
    }
    # Three comparable spectral maxima derived from the SAME actual
    # 8192 ADC samples, with calibrated acceleration only once. Never
    # invent FFT if a stored window is shorter than 8192 samples.
    if x.size>=8192:
        for kind in ("acceleration","velocity","displacement"):
            spectrum=analyze_vibration(
                x,fs,kind=kind,mode="fft",nfft=8192,
                band_hz=(0.,None),smooth_bins=1)
            frequency,amplitude=spectrum.peak
            if math.isfinite(frequency) and math.isfinite(amplitude):
                metrics[f"fft_{kind}_peak"]=float(amplitude)
                metrics[f"fft_{kind}_peak_hz"]=float(frequency)
    # Only a truly sampled 10..1000 Hz band can be stated in these units.
    if fs>2250 and x.size>=8192:
        try:
            v=broadband_rms(x,fs,kind="velocity",
                            band_hz=(10.,1000.),nfft=8192)
            if v.valid and math.isfinite(v.rms):
                metrics["velocity_rms_10_1000"]=float(v.rms)
        except ValueError:
            pass
    return metrics


class MeasurementHistory:
    """One local-only SQLite index plus immutable, checked NPZ snapshots."""

    def __init__(self,root:Path|str):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.samples=self.root/"windows"
        self.samples.mkdir(exist_ok=True)
        self.db=self.root/"measurements.sqlite"
        with self._db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS vendor_frames(
                    id INTEGER PRIMARY KEY,
                    session TEXT NOT NULL,
                    adc INTEGER NOT NULL CHECK(adc BETWEEN 1 AND 8),
                    update_tick INTEGER NOT NULL,
                    measured_utc TEXT NOT NULL,
                    original_json TEXT NOT NULL,
                    UNIQUE(session,adc,update_tick)
                );
                CREATE INDEX IF NOT EXISTS vendor_time ON
                    vendor_frames(adc,measured_utc);
                CREATE TABLE IF NOT EXISTS saved_windows(
                    id INTEGER PRIMARY KEY,
                    session TEXT NOT NULL,
                    adc INTEGER NOT NULL CHECK(adc BETWEEN 1 AND 8),
                    saved_utc TEXT NOT NULL,
                    rate_hz INTEGER NOT NULL,
                    capture_end INTEGER NOT NULL,
                    filename TEXT NOT NULL UNIQUE,
                    sha256 TEXT NOT NULL,
                    UNIQUE(session,adc,capture_end,sha256)
                );
                CREATE INDEX IF NOT EXISTS saved_time ON
                    saved_windows(adc,saved_utc);
                CREATE TABLE IF NOT EXISTS local_values(
                    window_id INTEGER NOT NULL
                        REFERENCES saved_windows(id) ON DELETE CASCADE,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    PRIMARY KEY(window_id,metric)
                );
                CREATE TABLE IF NOT EXISTS import_offsets(
                    session TEXT PRIMARY KEY,
                    byte_offset INTEGER NOT NULL
                );
            """)

    @contextmanager
    def _db(self):
        conn=sqlite3.connect(self.db,timeout=4)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=4000")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _valid_session(session:str):
        if not isinstance(session,str) or not 1<=len(session)<=160 or (
                any(ord(c)<32 for c in session)):
            raise ValueError("Некорректная метка источника измерения")

    def _parse_vendor(self,session:str,row:dict)->tuple[OriginalDSPBands,str]:
        self._valid_session(session)
        if not isinstance(row,dict):
            raise ValueError("Ожидалась одна исходная строка AUX4700")
        adc=row.get("adc")
        tick=row.get("update")
        if type(adc) is not int or not 1<=adc<=8 or (
                type(tick) is not int or not 1<=tick<2**63):
            raise ValueError("АЦП/порядковый номер исходного AUX неверен")
        # Strict original decoder checks ALL 115 cells and nonfinite count.
        packet=read_original_dsp_bands(
            {"aux4700_updates":tick,
             "dsp_original_aux4700_channels":[row]},adc)
        if packet is None or not packet.has_extended:
            raise ValueError("Неполный исходный AUX4700 — 115 ячеек обязательны")
        return packet,_utc(packet.time_utc)

    def record_vendor_row(self,session:str,row:dict,
                          *, conn=None)->bool:
        packet,utc=self._parse_vendor(session,row)
        if conn is None:
            with self._db() as writable:
                return self.record_vendor_row(session,row,conn=writable)
        cur=conn.execute("""
            INSERT OR IGNORE INTO vendor_frames
            (session,adc,update_tick,measured_utc,original_json)
            VALUES (?,?,?,?,?)
        """,(session,packet.adc,packet.update,utc,
             json.dumps(row,ensure_ascii=False,separators=(",",":"),
                        allow_nan=False)))
        return cur.rowcount==1

    def record_vendor_status(self,status:dict)->int:
        """Live fallback captures last verified packets; log import is primary."""
        if (not isinstance(status,dict) or
                status.get("phase") not in ("RECORDING","VERIFYING","COMPLETED") or
                status.get("source_tcp_multi_socket")):
            return 0
        session=status.get("session_id")
        self._valid_session(session)
        if not isinstance(status.get("dsp_original_aux4700_channels"),list):
            return 0
        count=0
        with self._db() as con:
            for row in status["dsp_original_aux4700_channels"]:
                if self.record_vendor_row(session,row,conn=con):count+=1
        return count

    def sync_aux_jsonl(self,run_dir:Path|str,session:str,
                       *,batch:int=MAX_IMPORT_ROWS)->int:
        """Append complete JSONL lines only; resume from durable byte cursor.

        Reads Native's already-created, append-only aux4700.jsonl, never RAW
        and never a device socket. A partially buffered/truncated line waits.
        """
        self._valid_session(session)
        base=Path(run_dir)
        source=base/"aux4700.jsonl"
        if source.is_symlink() or not source.is_file():
            return 0
        if type(batch) is not int or not 1<=batch<=MAX_IMPORT_ROWS:
            raise ValueError("Importer batch quota exceeded")
        rows=0
        with self._db() as con:
            cur=con.execute("SELECT byte_offset FROM import_offsets WHERE session=?",
                            (session,))
            record=cur.fetchone()
            offset=record[0] if record else 0
            if source.stat().st_size<offset:
                raise ValueError("Журнал AUX4700 был обрезан после импорта")
            with source.open("rb") as reader:
                reader.seek(offset)
                while rows<batch:
                    line=reader.readline(MAX_JSONL_LINE+1)
                    if not line:break
                    if not line.endswith(b"\n"):
                        if len(line)>MAX_JSONL_LINE:
                            raise ValueError("Слишком длинная строка прибора AUX4700")
                        break  # tail may still be written; retry next poll
                    if len(line)>MAX_JSONL_LINE:
                        raise ValueError("Строка AUX4700 превышает лимит")
                    try:
                        row=json.loads(line.decode("utf-8"))
                    except (UnicodeError,ValueError) as exc:
                        raise ValueError("Повреждённая строка архива AUX4700") from exc
                    self.record_vendor_row(session,row,conn=con)
                    offset=reader.tell()
                    rows+=1
            con.execute("""
                INSERT INTO import_offsets(session,byte_offset) VALUES (?,?)
                ON CONFLICT(session) DO UPDATE SET byte_offset=excluded.byte_offset
            """,(session,offset))
        return rows

    def import_npz(self,path:Path|str,*, saved_utc:str|None=None)->int:
        """Copy and index a verified local NPZ once, by its real SHA samples.

        Timestamp is UTC of operator archiving, NOT an invented original
        acquisition instant. The source window is permanently local.
        """
        origin=Path(path)
        snap=load_snapshot(origin)
        timestamp=_utc(saved_utc or snap.saved_utc or
                       datetime.now(timezone.utc).isoformat())
        metrics=_local_features(snap.acceleration_m_s2,snap.rate_hz)
        with self._db() as con:
            existing=con.execute("""
              SELECT id FROM saved_windows
              WHERE session=? AND adc=? AND capture_end=? AND sha256=?
            """,(snap.source_session,snap.adc,snap.capture_end,snap.sha256)).fetchone()
            if existing:return existing[0]
        target=self.samples/f"w_{uuid4().hex}.npz"
        if origin.resolve()!=target.resolve():
            # Exclusive destination never overwrites another measurement.
            with origin.open("rb") as r, target.open("xb") as w:
                shutil.copyfileobj(r,w,length=131072)
            try:
                checked=load_snapshot(target)
                if checked.sha256!=snap.sha256:
                    raise ValueError("Копия окна изменила содержимое")
            except Exception:
                target.unlink(missing_ok=True)
                raise
        try:
            with self._db() as con:
                cur=con.execute("""
                  INSERT OR IGNORE INTO saved_windows
                  (session,adc,saved_utc,rate_hz,capture_end,filename,sha256)
                  VALUES (?,?,?,?,?,?,?)
                """,(snap.source_session,snap.adc,timestamp,snap.rate_hz,
                     snap.capture_end,target.name,snap.sha256))
                if cur.rowcount!=1:
                    target.unlink(missing_ok=True)
                    existing=con.execute("""
                      SELECT id FROM saved_windows
                      WHERE session=? AND adc=? AND capture_end=? AND sha256=?
                    """,(snap.source_session,snap.adc,snap.capture_end,
                         snap.sha256)).fetchone()
                    if existing:return existing[0]
                    raise ValueError("Существующая архивная запись конфликтует")
                idx=cur.lastrowid
                con.executemany("""
                  INSERT INTO local_values(window_id,metric,value) VALUES (?,?,?)
                """,[(idx,key,float(value)) for key,value in metrics.items()
                     if math.isfinite(value)])
                return idx
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def capture_npz(self,x:np.ndarray,*,adc:int,fs:int,session:str,
                    capture_end:int,saved_utc:str|None=None)->int:
        """One-click immutable measurement from the selected verified ring."""
        name=self.samples/f"w_{uuid4().hex}.npz"
        save_snapshot(name,x,adc=adc,rate_hz=fs,
                      session_id=session,capture_end=capture_end)
        # Reuse SHA-verified import semantics; if duplicate, remove this new
        # file as it wasn't indexed, instead of growing duplicate archives.
        try:
            snap=load_snapshot(name)
            timestamp=_utc(saved_utc or snap.saved_utc or
                       datetime.now(timezone.utc).isoformat())
            metrics=_local_features(snap.acceleration_m_s2,snap.rate_hz)
            with self._db() as con:
                cur=con.execute("""
                  INSERT OR IGNORE INTO saved_windows
                  (session,adc,saved_utc,rate_hz,capture_end,filename,sha256)
                  VALUES (?,?,?,?,?,?,?)
                """,(snap.source_session,snap.adc,timestamp,snap.rate_hz,
                     snap.capture_end,name.name,snap.sha256))
                if cur.rowcount==0:
                    old=con.execute("""
                      SELECT id FROM saved_windows
                      WHERE session=? AND adc=? AND capture_end=? AND sha256=?
                    """,(session,adc,capture_end,snap.sha256)).fetchone()
                    name.unlink(missing_ok=True)
                    if old:return old[0]
                    raise ValueError("Архивное измерение уже существует")
                idx=cur.lastrowid
                con.executemany("""
                  INSERT INTO local_values(window_id,metric,value)
                  VALUES (?,?,?)
                """,[(idx,k,float(v)) for k,v in metrics.items() if math.isfinite(v)])
                return idx
        except Exception:
            name.unlink(missing_ok=True)
            raise

    def entries(self,adc:int,kind:str="all",limit:int=300,*,
                after_utc:str|None=None,before_utc:str|None=None)->list[HistoryEntry]:
        """Bounded date-filtered historical table; all original data remains."""
        if type(adc) is not int or not 1<=adc<=8:
            raise ValueError("Неверный выбранный АЦП")
        if kind not in ("all","vendor","window") or not 1<=limit<=2000:
            raise ValueError("Неверный архивный фильтр")
        lo=_utc(after_utc) if after_utc else ""
        hi=_utc(before_utc) if before_utc else "9999"
        if lo>hi:raise ValueError("Начальная дата позже конечной")
        entries=[]
        with self._db() as con:
            if kind in ("vendor","all"):
                for idx,session,utc,tick in con.execute("""
                    SELECT id,session,measured_utc,update_tick
                    FROM vendor_frames WHERE adc=? AND measured_utc>=?
                    AND measured_utc<=?
                    ORDER BY measured_utc DESC LIMIT ?
                """,(adc,lo,hi,limit)).fetchall():
                    entries.append(HistoryEntry(
                        f"V:{idx}",VENDOR,adc,utc,session,
                        f"МВК01 AUX4700 · пакет {tick}"))
            if kind in ("window","all"):
                for idx,session,utc,fs in con.execute("""
                    SELECT id,session,saved_utc,rate_hz
                    FROM saved_windows WHERE adc=? AND saved_utc>=?
                    AND saved_utc<=?
                    ORDER BY saved_utc DESC LIMIT ?
                """,(adc,lo,hi,limit)).fetchall():
                    entries.append(HistoryEntry(
                        f"W:{idx}",LOCAL,adc,utc,session,
                        f"АЦП окно · сохранено в архив · Fs={fs} Гц",fs))
        return sorted(entries,key=lambda x:x.time_utc,reverse=True)[:limit]

    def exact_entry(self,adc:int,kind:str,utc:str)->HistoryEntry|None:
        """Trend click must navigate to EXACT same ADC/source/timestamp.

        Never silently choose the nearest unrelated measurement when many
        AUX4700 frames per day exceed the 500-row UI cap.
        """
        if kind not in ("vendor","window") or type(adc) is not int or not 1<=adc<=8:
            raise ValueError("Неизвестный АЦП или источник истории")
        timestamp=_utc(utc)
        with self._db() as con:
            if kind=="vendor":
                rows=con.execute("""
                  SELECT id,session,update_tick
                  FROM vendor_frames
                  WHERE adc=? AND measured_utc=? LIMIT 2
                """,(adc,timestamp)).fetchall()
            else:
                rows=con.execute("""
                  SELECT id,session,rate_hz
                  FROM saved_windows
                  WHERE adc=? AND saved_utc=? LIMIT 2
                """,(adc,timestamp)).fetchall()
        if not rows:return None
        if len(rows)>1:
            raise ValueError("Две записи одного АЦП имеют одинаковое время; нужен ручной выбор")
        idx,session,value=rows[0]
        return (HistoryEntry(f"V:{idx}",VENDOR,adc,timestamp,session,
                              f"МВК01 AUX4700 · пакет {value}")
                if kind=="vendor" else
                HistoryEntry(f"W:{idx}",LOCAL,adc,timestamp,session,
                              f"АЦП окно · сохранено в архив · Fs={value} Гц",value))

    def trend(self,adc:int,metric:str,days:int|None=None,
              limit:int=MAX_PLOT_ROWS)->tuple[list[tuple[datetime,float]],str,str,bool]:
        label,unit=metric_details(metric)
        if type(adc) is not int or not 1<=adc<=8:
            raise ValueError("Неверный выбранный АЦП")
        if days is not None and (type(days) is not int or not 1<=days<=3650):
            raise ValueError("Неверный период тренда")
        start=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat() if days else ""
        data=[]
        with self._db() as con:
            if metric in _LOCAL_METRICS:
                records=con.execute("""
                  SELECT w.saved_utc,v.value
                  FROM saved_windows w JOIN local_values v ON w.id=v.window_id
                  WHERE w.adc=? AND w.saved_utc>=? AND v.metric=?
                  ORDER BY w.saved_utc DESC LIMIT ?
                """,(adc,start,metric,limit+1)).fetchall()
                data=[(datetime.fromisoformat(ts),float(v)) for ts,v in records]
            else:
                records=con.execute("""
                  SELECT measured_utc,original_json
                  FROM vendor_frames WHERE adc=? AND measured_utc>=?
                  ORDER BY measured_utc DESC LIMIT ?
                """,(adc,start,limit+1)).fetchall()
                for ts,payload in records:
                    value=_metric_value(json.loads(payload),metric)
                    if value is not None:
                        data.append((datetime.fromisoformat(ts),value))
        truncated=len(records)>limit
        data.reverse()
        return data,label,unit,truncated

    def get_vendor(self,entry:HistoryEntry)->OriginalDSPBands:
        if entry.source!=VENDOR or not entry.key.startswith("V:"):
            raise ValueError("Выбранная запись не является приборным AUX4700")
        with self._db() as con:
            row=con.execute(
                "SELECT session,original_json FROM vendor_frames WHERE id=? AND adc=?",
                (int(entry.key[2:]),entry.adc)).fetchone()
        if row is None:raise ValueError("Нет сохранённого приборного пакета")
        return self._parse_vendor(row[0],json.loads(row[1]))[0]

    def get_window(self,entry:HistoryEntry)->OfflineSnapshot:
        if entry.source!=LOCAL or not entry.key.startswith("W:"):
            raise ValueError("Выбранная запись не содержит АЦП Float32")
        with self._db() as con:
            row=con.execute("""
              SELECT filename,sha256 FROM saved_windows WHERE id=? AND adc=?
            """,(int(entry.key[2:]),entry.adc)).fetchone()
        if row is None:raise ValueError("Нет сохранённой осциллограммы")
        filename,sha=row
        if (Path(filename).name!=filename or "/" in filename or
                "\\" in filename or not filename.endswith(".npz")):
            raise ValueError("Некорректный путь к архивному окну")
        snap=load_snapshot(self.samples/filename)
        if snap.sha256!=sha or snap.adc!=entry.adc:
            raise ValueError("SHA/АЦП файла не соответствует архивному индексу")
        return snap
