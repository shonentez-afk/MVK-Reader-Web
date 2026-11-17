"""Local MVK Live snapshots: save/reopen offline without TACH or hardware.

NPZ is a convenience archive, not proof of device origin or a metrological
reference. SHA protects accidental changes to the samples in the archive.
Session metadata is retained, but reopening is distinctly tagged OFFLINE.
No IP, authentication token, MAC address or source register image is stored.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np

MAX_SAMPLES = 262144
MAX_ARCHIVE_BYTES = 6 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 3 * 1024 * 1024
SCHEMA = "MVK_LIVE_CALIBRATED_SNAPSHOT_V1"


@dataclass(frozen=True)
class OfflineSnapshot:
    acceleration_m_s2: np.ndarray
    adc: int
    rate_hz: int
    source_session: str
    capture_end: int
    sha256: str
    source: str = "OFFLINE_REOPENED_LOCAL_SNAPSHOT_NOT_DEVICE_PROOF"


def _checked(acceleration_m_s2: np.ndarray, adc: int, rate_hz: int) -> np.ndarray:
    x=np.asarray(acceleration_m_s2,dtype="<f4")
    if (type(adc) is not int or not 1<=adc<=8
        or type(rate_hz) is not int or rate_hz not in (512,2048,8192,32768,65536)
        or x.ndim!=1 or not 256<=x.size<=MAX_SAMPLES
        or not np.all(np.isfinite(x))):
        raise ValueError("Only a bounded real calibrated ADC channel may be saved")
    return np.ascontiguousarray(x)


def save_snapshot(
    path: str | Path, samples: np.ndarray, *, adc: int, rate_hz: int,
    session_id: str, capture_end: int,
) -> Path:
    x=_checked(samples,adc,rate_hz)
    if (not isinstance(session_id,str) or not 1<=len(session_id)<=160
        or type(capture_end) is not int or not x.size<=capture_end<2**64):
        raise ValueError("Incomplete Native provenance")
    digest=hashlib.sha256(x.tobytes()).hexdigest()
    meta={
        "schema":SCHEMA,"adc":adc,"rate_hz":rate_hz,
        "source_session":session_id,"capture_end":capture_end,
        "sample_count":len(x),"sha256":digest,
        "unit":"m/s^2","source":"MVK_NATIVE_VERIFIED_APP_DERIVED_EXPORT",
        "not_hardware_reference":True,
    }
    output=Path(path)
    if output.suffix.lower()!=".npz":
        raise ValueError("Use .npz snapshot format")
    if output.exists():
        raise FileExistsError("Do not silently overwrite a prior measurement")
    data=io.BytesIO()
    np.savez_compressed(
        data,acceleration_m_s2=x,
        metadata_utf8=np.frombuffer(
            json.dumps(meta,ensure_ascii=False,sort_keys=True).encode("utf-8"),
            dtype=np.uint8))
    if data.tell()>MAX_ARCHIVE_BYTES:
        raise ValueError("Snapshot archive is too large")
    # Exclusive creation: no overwrite of operator's saved evidence.
    with output.open("xb") as f:
        f.write(data.getvalue())
    return output


def load_snapshot(path: str | Path) -> OfflineSnapshot:
    source=Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size>MAX_ARCHIVE_BYTES:
        raise ValueError("Unsafe or oversized offline snapshot")
    with zipfile.ZipFile(source,"r") as archive:
        members=archive.infolist()
        if len(members)!=2 or {x.filename for x in members}!={
                "acceleration_m_s2.npy","metadata_utf8.npy"}:
            raise ValueError("Unexpected offline snapshot members")
        if sum(x.file_size for x in members)>MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Offline snapshot decompression quota exceeded")
        if any(x.file_size<0 or x.compress_type not in (
                zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) for x in members):
            raise ValueError("Unsafe offline compression")
    with np.load(source,allow_pickle=False) as z:
        samples=z["acceleration_m_s2"]
        metadata=z["metadata_utf8"]
    if metadata.dtype!=np.uint8 or metadata.ndim!=1 or metadata.size>4096:
        raise ValueError("Invalid snapshot metadata encoding")
    try:
        meta=json.loads(bytes(metadata).decode("utf-8"))
    except (UnicodeError,ValueError,TypeError) as exc:
        raise ValueError("Damaged snapshot metadata") from exc
    if not isinstance(meta,dict) or meta.get("schema")!=SCHEMA or (
            meta.get("unit")!="m/s^2") or meta.get("not_hardware_reference") is not True:
        raise ValueError("Unknown snapshot provenance or units")
    x=_checked(samples,meta.get("adc"),meta.get("rate_hz"))
    expected=hashlib.sha256(x.tobytes()).hexdigest()
    if (meta.get("sha256")!=expected or meta.get("sample_count")!=len(x)
        or not isinstance(meta.get("source_session"),str)
        or not 1<=len(meta["source_session"])<=160
        or type(meta.get("capture_end")) is not int
        or not x.size<=meta["capture_end"]<2**64):
        raise ValueError("Snapshot data or provenance does not match SHA256")
    return OfflineSnapshot(x,meta["adc"],meta["rate_hz"],
                           meta["source_session"],meta["capture_end"],expected)


def save_spectrum_csv(
    path: str | Path, frequencies: np.ndarray, linear_values: np.ndarray,
    displayed_values: np.ndarray, *, mode: str, unit: str,
    scale: str, reference: str, adc: int, session_id: str,
) -> Path:
    f=np.asarray(frequencies,dtype=np.float64)
    raw=np.asarray(linear_values,dtype=np.float64)
    plotted=np.asarray(displayed_values,dtype=np.float64)
    if (f.ndim!=1 or f.size<2 or raw.shape!=f.shape or plotted.shape!=f.shape
        or not np.isfinite(f).all() or
        not np.all(np.isfinite(raw)|np.isnan(raw))
        or not np.all(np.isfinite(plotted)|np.isnan(plotted))
        or type(adc) is not int or not 1<=adc<=8):
        raise ValueError("Invalid spectrum table")
    output=Path(path)
    if output.suffix.lower()!=".csv":
        raise ValueError("Use .csv for spectrum")
    with output.open("x",newline="",encoding="utf-8-sig") as file:
        writer=csv.writer(file,delimiter=";")
        writer.writerow(["# MVK Live APP_DERIVED, not AUX4700 / not reference"])
        writer.writerow(["# Mode",mode,"Unit",unit,"Y scale",scale,"dB ref",reference])
        writer.writerow(["# ADC",adc,"Source session",session_id])
        writer.writerow(["frequency_hz","linear_value","display_value"])
        for x,y,z in zip(f,raw,plotted):
            writer.writerow([format(float(x),".11g"),
                             "" if np.isnan(y) else format(float(y),".11g"),
                             "" if np.isnan(z) else format(float(z),".11g")])
    return output
