"""End-to-end verified Go mark, RAW and Native ZIP -> original wire bytes.

Synthetic only. Original Delphi FileStream rate/freeze timing is NOT proven.
"""
from __future__ import annotations

from hashlib import sha256
import json
import struct
import zipfile

import pytest

from .test_stage111z31da_frame_mark_core import synthetic_marked_run
from .test_stage111z31fr_original_wire_replay import sample
from .test_stage111z31fq_original_values_3100_timeline import aux_frame
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_live_write_stages import (
    EXPORT_SUBDIR,export_source_write_windows,
)
from ..core.source_frame_mark_protocol import AUDIT
from ..core.original_write_data_wire_replay import TYPE_ADC


def _marked_wire_run(tmp_path):
    run,archive,_oldflow,ledger=synthetic_marked_run(tmp_path)
    records=[struct.pack("<II",1,8)]
    for ch in range(8):
        bits=struct.unpack("<I",struct.pack("<f",float(ch+1)))[0]
        records.append(sample(TYPE_ADC,ch,65536,[bits]*256,0))
    records.append(aux_frame()) # end of the first 10 application frames
    for ch in range(8):
        bits=struct.unpack("<I",struct.pack("<f",float(ch+11)))[0]
        records.append(sample(TYPE_ADC,ch,65536,[bits]*256,256))
    records.append(aux_frame())
    records.append(struct.pack("<IIII",0xDEADBEEF,16,0,0))
    assert len(records)==20
    raw=b"".join(records)
    sha=sha256(raw).hexdigest()
    (run/"incoming.raw").write_bytes(raw)
    with zipfile.ZipFile(archive) as z:
        contents={name:z.read(name) for name in z.namelist()}
    audit=json.loads(contents["EXPORT_AUDIT.json"])
    audit["source_raw_sha256"]=sha
    contents["EXPORT_AUDIT.json"]=json.dumps(audit).encode()
    aux=json.loads(contents["AUX_PROVENANCE.json"])
    aux["source_raw_sha256"]=sha
    contents["AUX_PROVENANCE.json"]=json.dumps(aux).encode()
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        for name,data in contents.items():
            z.writestr(name,data)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(archive),channel=1)
    doc=json.loads((run/AUDIT).read_text(encoding="utf-8"))
    doc["source_raw_sha256"]=sha
    doc["end_frames_decoded"]=20
    doc["end_channel_samples"]=[512]*8+[0,0]
    doc["requests"][1]["frames_decoded"]=19
    doc["requests"][1]["channel_samples"]=[512]*8+[0,0]
    data=(json.dumps(doc,indent=2,ensure_ascii=False)+"\n").encode()
    (run/AUDIT).write_bytes(data)
    summary=json.loads((run/"summary.json").read_text())
    summary.update(
        raw_sha256=sha,raw_bytes=len(raw),frames_decoded=20,
        incomplete_final_frame_bytes=0,aux4700_updates=2,
        channels=[{"samples":n} for n in [512]*8+[0,0]],
        source_frame_marks_sha256=sha256(data).hexdigest(),
    )
    (run/"summary.json").write_text(json.dumps(summary))
    return run,flow,ledger


def test_original_wire_data_and_gain_calibrated_files_remain_separate(tmp_path):
    run,flow,ledger=_marked_wire_run(tmp_path)
    result=export_source_write_windows(ledger,flow,run)
    assert result["verified_frame_boundaries"]
    assert result["source_write_data_wire_payload_files"]==8
    assert result["source_write_data_wire_payload_byte_exact"] is True
    assert result["source_write_data_delphi_rate_freeze_parity_verified"] is False
    raw=(run/EXPORT_SUBDIR/"DATA01_ADC1_WIRE_RX_UNSCALED.bin").read_bytes()
    assert raw==struct.pack("<f",11.0)*256
    calibrated=(run/EXPORT_SUBDIR/
                "DATA01_ADC1_NATIVE_CALIBRATED.f32").read_bytes()
    assert len(calibrated)==len(raw)
    assert calibrated!=raw
    audit=json.loads(
        (run/EXPORT_SUBDIR/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text())
    assert audit["source_write_data_wire_payload_files"]==8
    assert audit["original_tmkvthread_byte_exact_recording"] is False
    wires=[f for f in audit["files"]
           if f.get("kind")=="source_raw_wire_payload"]
    assert len(wires)==8
    for item in wires:
        assert item["source_raw_sha256"]==audit["source_raw_sha256"]
        assert item["original_delphi_bin_parity_verified"] is False
        assert item["sha256"]==sha256(
            (run/EXPORT_SUBDIR/item["name"]).read_bytes()).hexdigest()


def test_modified_source_wire_data_prevents_any_export(tmp_path):
    run,flow,ledger=_marked_wire_run(tmp_path)
    raw=bytearray((run/"incoming.raw").read_bytes())
    raw[-1]^=1
    (run/"incoming.raw").write_bytes(raw)
    with pytest.raises(ValueError,match="SHA|source|mismatch"):
        export_source_write_windows(ledger,flow,run)
    assert not (run/EXPORT_SUBDIR).exists()
