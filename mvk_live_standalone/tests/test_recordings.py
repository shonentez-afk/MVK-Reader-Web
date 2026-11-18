"""Local-only save/open; SHA and bounds, no remote or instrument reference."""
import csv
import json
import zipfile

import numpy as np
import pytest

from mvk_live_standalone.recordings import save_snapshot, load_snapshot, save_spectrum_csv


def test_snapshot_roundtrip_and_no_private_network_metadata(tmp_path):
    x=np.arange(2048,dtype="<f4")/8
    file=tmp_path/"verified_operator_snapshot.npz"
    save_snapshot(file,x,adc=2,rate_hz=8192,
                  session_id="RUN_LOCAL_NOIP",capture_end=4096)
    loaded=load_snapshot(file)
    assert loaded.adc==2 and loaded.rate_hz==8192
    assert loaded.capture_end==4096
    assert loaded.saved_utc is not None and loaded.saved_utc.endswith("+00:00")
    np.testing.assert_array_equal(loaded.acceleration_m_s2,x)
    assert loaded.source.startswith("OFFLINE_")
    with zipfile.ZipFile(file) as z:
        assert len(z.namelist())==2
        metadata=z.read("metadata_utf8.npy")
        assert b"192.168" not in metadata and b"token" not in metadata.lower()
    with pytest.raises(FileExistsError):
        save_snapshot(file,x,adc=2,rate_hz=8192,
                      session_id="RUN_LOCAL_NOIP",capture_end=4096)


def test_snapshot_refuses_tampering_or_unsafe_metadata(tmp_path):
    x=np.ones(512,dtype="<f4")
    path=tmp_path/"captured.npz"
    save_snapshot(path,x,adc=1,rate_hz=2048,
                  session_id="RUN",capture_end=512)
    with zipfile.ZipFile(path,"r") as zin:
        meta=np.load(zin.open("metadata_utf8.npy"),allow_pickle=False)
        data=np.load(zin.open("acceleration_m_s2.npy"),allow_pickle=False)
    details=json.loads(bytes(meta).decode("utf8"))
    details["sha256"]="0"*64
    bad=tmp_path/"bad.npz"
    np.savez_compressed(bad,acceleration_m_s2=data,
          metadata_utf8=np.frombuffer(json.dumps(details).encode(),dtype=np.uint8))
    with pytest.raises(ValueError,match="SHA256"):
        load_snapshot(bad)
    with pytest.raises(ValueError):
        save_snapshot(tmp_path/"x.npz",np.zeros(512),adc=9,rate_hz=2048,
                      session_id="RUN",capture_end=512)
    plain=tmp_path/"not_npz.npz"
    plain.write_bytes(b"no")
    with pytest.raises((ValueError,zipfile.BadZipFile)):
        load_snapshot(plain)


def test_spectrum_export_contains_units_and_exact_nan_semantics(tmp_path):
    path=tmp_path/"spectrum.csv"
    f=np.array([0,10,20,30],dtype=float)
    y=np.array([0,1,np.nan,2],dtype=float)
    z=np.array([-180,10,np.nan,20],dtype=float)
    save_spectrum_csv(path,f,y,z,mode="fft",unit="мм/с СКЗ",
                      scale="db",reference="1e-6 mm/s",
                      adc=4,session_id="ONE_RUN")
    with path.open(encoding="utf-8-sig",newline="") as source:
        rows=list(csv.reader(source,delimiter=";"))
    assert rows[1][1]=="fft"
    assert rows[1][3]=="мм/с СКЗ"
    assert rows[3]==["frequency_hz","linear_value","display_value"]
    assert rows[6]==["20","",""]
    with pytest.raises(FileExistsError):
        save_spectrum_csv(path,f,y,z,mode="fft",unit="мм/с СКЗ",
                          scale="db",reference="1e-6 mm/s",
                          adc=4,session_id="ONE_RUN")



def test_snapshot_legacy_without_saved_utc_is_accepted_and_never_invents_device_time(tmp_path):
    from datetime import datetime,timezone
    source=tmp_path/"recent.npz"
    save_snapshot(source,np.ones(512,dtype="<f4"),
                  adc=1,rate_hz=2048,session_id="TEST_LOCAL",
                  capture_end=512)
    with zipfile.ZipFile(source,"r") as z:
        meta=np.load(z.open("metadata_utf8.npy"),allow_pickle=False)
        samples=np.load(z.open("acceleration_m_s2.npy"),allow_pickle=False)
    details=json.loads(bytes(meta).decode("utf8"))
    assert datetime.fromisoformat(details["saved_utc"]).tzinfo is not None
    del details["saved_utc"]
    legacy=tmp_path/"legacy.npz"
    np.savez_compressed(
        legacy,acceleration_m_s2=samples,
        metadata_utf8=np.frombuffer(
            json.dumps(details).encode("utf-8"),dtype=np.uint8))
    opened=load_snapshot(legacy)
    assert opened.saved_utc is None  # no imaginary acquisition timestamp
    assert opened.source.startswith("OFFLINE_")
