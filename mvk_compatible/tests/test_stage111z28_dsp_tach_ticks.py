"""Stage111Z28A deterministic offline QA: two TACH raw banks, DSP and ADC flags.

SYNTHETIC local bundles only; never label fake samples as captured hardware.
"""
from __future__ import annotations

import hashlib
import json
import zipfile

import pytest

from mvk_compatible.core.offline_export import OfflineSession
from .test_offline_core import fixture_zip

SCHEMA = "MVK_NATIVE_R6_DSP_TACH_TICK_V1"
SOURCE = "READ_ONLY_REGISTER_IMAGE_AT_VALUES_76B_TICK"
TIME = "HOST_RECEIVE_CLOCK_NOT_DSP_SYNCHRONIZED"


def _records():
    def mk(i, status):
        return {
            "update": i + 1,
            "aux_frame": 50 + i * 20,
            "tick_frame": 55 + i * 20,
            "tick_received_utc": f"2026-10-29T06:32:{i:02d}Z",
            "dsp_tach_schema": SCHEMA,
            "dsp_status_register_word": "0x1020",
            "dsp_status_raw": status,
            "dsp_status_hex": f"0x{status:08X}",
            "tach_channels": [
                {"tach": 1, "register_base_word": "0x3000",
                 "raw_float32_words_0_2": [13.25+i, 22.5],
                 "raw_uint32_words_4_6_8": [0xDEADBEEF, 42, 0x80000400]},
                {"tach": 2, "register_base_word": "0x3100",
                 "raw_float32_words_0_2": [9.75, 2.125],
                 "raw_uint32_words_4_6_8": [0x01020304, 7, 77]},
            ],
            "source": SOURCE,
            "time_kind": TIME,
            "tach_units_and_rpm_verified": False,
        }
    return [mk(0,0x00000104),mk(1,0)]


def _fixture(tmp_path, mutate=None, *, recompute_sha=True, with_raw_status=True):
    initial=fixture_zip(tmp_path)
    with zipfile.ZipFile(initial) as z:
        files={n:z.read(n) for n in z.namelist()}
    initial.unlink()
    rows=_records()
    if mutate is not None:
        mutate(rows)
    payload=json.dumps(rows, ensure_ascii=False).encode("utf-8")
    files["TIMELINE.json"]=payload
    audit=json.loads(files["EXPORT_AUDIT.json"])
    audit["values_ticks_3100"]=2
    audit["aux4700_updates"]=2
    if recompute_sha:
        audit["output_file_sha256"]["TIMELINE.json"]=hashlib.sha256(payload).hexdigest()
    files["EXPORT_AUDIT.json"]=json.dumps(audit).encode("utf-8")
    if with_raw_status:
        aux=[json.loads(line) for line in files["aux4700.jsonl"].splitlines()]
        for record in aux:
            raw=0x400 if record["adc"] >= 7 else 0
            record["status_raw"]=raw
            record["not_ready"]={"fs16":False,"fs64":False,"fs512":False}
        content=("\n".join(json.dumps(record) for record in aux)+"\n").encode()
        files["aux4700.jsonl"]=content
        proven=json.loads(files["AUX_PROVENANCE.json"])
        proven["aux4700_sha256"]=hashlib.sha256(content).hexdigest()
        files["AUX_PROVENANCE.json"]=json.dumps(proven).encode()
    path=tmp_path/"synthetic_dsp_tach.zip"
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in files.items():
            z.writestr(name, raw)
    return path


def test_full_source_backed_dsp_tach_per_tick(tmp_path):
    session=OfflineSession.open(_fixture(tmp_path))
    assert session.updates==2
    a=session.calculations(0)
    b=session.calculations(1)
    t=a["dsp_tach"]
    assert t["available"] and t["source"]==SOURCE
    assert t["global_dsp_status_raw"]==0x104
    assert t["global_dsp_status_hex"]=="0x00000104"
    assert t["tick_frame"]==55 and t["aux_frame"]==50
    assert t["host_clock_only"]
    assert not t["rpm_verified"]
    assert not t["tach_frequency_hz_verified"]
    assert t["tachometers"][0]["raw_float32_words_0_2"]==[13.25,22.5]
    assert t["tachometers"][0]["raw_uint32_words_4_6_8"]==[
        0xDEADBEEF,42,0x80000400]
    assert t["tachometers"][1]["register_base_word"]=="0x3100"
    assert t["tachometers"][0]["rpm"] is None
    assert t["tachometers"][1]["frequency_hz"] is None
    assert b["dsp_tach"]["global_dsp_status_hex"]=="0x00000000"
    assert b["dsp_tach"]["tachometers"][0]["raw_float32_words_0_2"][0]==14.25
    assert a["channels"][6]["sensor_status"]=="0x00000400"
    bits=a["channels"][6]["sensor_status_details"]
    assert bits["raw_hex"]=="0x00000400" and bits["warning_bits_0xC00"]=="0x00000400"
    assert bits["state"]=="RAW_STATUS_NONZERO_CAUSE_UNVERIFIED"
    assert a["channels"][6]["health"]=="ALERT"
    assert a["channels"][0]["parameters_peak_24"] is not None
    assert len(a["channels"][0]["third_octave"])==43
    assert len(a["channels"][0]["parameters_peak_peak_24"])==24


def test_historical_r6_archives_without_new_fields_are_not_fabricated(tmp_path):
    old=OfflineSession.open(fixture_zip(tmp_path))
    d=old.calculations(0)
    assert not d["dsp_tach"]["available"]
    assert d["dsp_tach"]["tachometers"]==[]
    assert d["channels"][6]["sensor_status_details"]["raw_u32"] is None


def test_hash_mismatch_of_timeline_refuses_data(tmp_path):
    path=_fixture(tmp_path,lambda rows: rows[0].update(dsp_status_raw=12),
                  recompute_sha=False)
    with pytest.raises(ValueError,match="SHA256"):
        OfflineSession.open(path).calculations(0)


@pytest.mark.parametrize("alter",[
    lambda r: r[0].update(dsp_status_hex="0x00000000"),
    lambda r: r[0].update(dsp_tach_schema="UNSAFE_DSP_FREQUENCY_INFERRED"),
    lambda r: r[0].update(tach_units_and_rpm_verified=True),
    lambda r: r[0]["tach_channels"][1].update(register_base_word="0x3000"),
    lambda r: r[0]["tach_channels"].pop(),
    lambda r: r[0]["tach_channels"][0]["raw_float32_words_0_2"].__setitem__(0,1.1),
    lambda r: r[0]["tach_channels"][0]["raw_uint32_words_4_6_8"].__setitem__(1,-1),
    lambda r: r[0].update(tick_frame=49),
    lambda r: r[1].update(update=1),
    lambda r: r[1].update(tick_received_utc="2020-01-01T00:00:00Z"),
    lambda r: r[0].update(source="HOST_INFERRED_RPM"),
])
def test_unknown_tach_dsp_instrument_state_fails_closed(tmp_path,alter):
    s=OfflineSession.open(_fixture(tmp_path,alter))
    with pytest.raises(ValueError,match="TIMELINE"):
        s.calculations(0)


def test_old_schema_timeline_is_explicitly_unavailable(tmp_path):
    def strip(rows):
        for row in rows:
            for k in ("dsp_tach_schema","dsp_status_register_word",
                      "dsp_status_raw","dsp_status_hex","tach_channels",
                      "source","time_kind","tach_units_and_rpm_verified"):
                row.pop(k)
    result=OfflineSession.open(_fixture(tmp_path,strip))
    record=result.calculations(0)["dsp_tach"]
    assert not record["available"]
    assert record["reason"]=="OLD_TIMELINE_NO_REGISTER_WORDS"


def test_incomplete_aux_without_peak_data_cannot_fake_original_source(tmp_path):
    path=_fixture(tmp_path)
    with zipfile.ZipFile(path) as z:
        files={n:z.read(n) for n in z.namelist()}
    aux=[json.loads(line) for line in files["aux4700.jsonl"].splitlines()]
    aux[0]["band_peak_equiv"][0]=None
    raw=("\n".join(json.dumps(e) for e in aux)+"\n").encode()
    files["aux4700.jsonl"]=raw
    prov=json.loads(files["AUX_PROVENANCE.json"])
    prov["aux4700_sha256"]=hashlib.sha256(raw).hexdigest()
    files["AUX_PROVENANCE.json"]=json.dumps(prov).encode()
    path.unlink()
    with zipfile.ZipFile(path,"w") as z:
        for n,blob in files.items():
            z.writestr(n,blob)
    with pytest.raises(ValueError,match="AUX4700"):
        OfflineSession.open(path).calculations(0)
