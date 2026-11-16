"""Synthetic Native TACH1/2 original TCP 64xFloat32 -> SHA ZIP -> Core.

All samples are invented synthetic test input; NO original operator data,
no device access, no instrument write commands or physical RPM claims.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import struct
import zipfile

import pytest

from .test_offline_core import fixture_zip
from ..core.native_r6_tach_evidence import (
    DOMAIN,FILENAME,SCHEMA,read_tach_evidence,
)
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_pagefile_recording import (
    OriginalPageFileSelection,OriginalFileNameOptions,
    export_selected_original_pagefile,
)


def synthetic_tach_native_zip(folder:Path,*,present=(True,True),
                              gap_on_tach1=False):
    """Add evidence to a REAL SHA-checked synthetic 8xADC Native ZIP.

    TACH is 64 Float32 per original type 0xFF8001AC frame, exactly
    128 values in two frames per present channel. No ADC calibration.
    """
    source=fixture_zip(folder)
    with zipfile.ZipFile(source) as z:
        members={name:z.read(name) for name in z.namelist()}
    export=json.loads(members["EXPORT_AUDIT.json"])
    channels=[]
    for n in (1,2):
        active=present[n-1]
        row={
            "channel":n+8,"present":active,
            "frames":2 if active else 0,
            "samples":128 if active else 0,
            "bytes":512 if active else 0,
            "first_sample_index":0,
            "last_frame_first_sample_index":(
                (128 if n==1 and gap_on_tach1 else 64) if active else 0),
            "first_sample_rate_hz":32768 if active else 0,
            "sequence_discontinuities":(
                1 if n==1 and gap_on_tach1 and active else 0),
            "sample_rate_changes":0,
            "contiguous_constant_rate":(
                active and not (n==1 and gap_on_tach1)),
            "physical_calibration_verified":False,
        }
        if active:
            name=f"TACH{n}_NATIVE_UNCALIBRATED.f32"
            raw=struct.pack("<128f",*(n+i/256 for i in range(128)))
            digest=sha256(raw).hexdigest()
            members[name]=raw
            export["output_file_sha256"][name]=digest
            row.update({"filename":name,"sha256":digest})
        channels.append(row)
    audit={
        "schema":SCHEMA,
        "source_raw_sha256":export["source_raw_sha256"],
        "input_domain":DOMAIN,
        "device_commands_sent":False,
        "original_tach_bin_parity_verified":False,
        "channels":channels,
    }
    audit_bytes=json.dumps(audit,ensure_ascii=False,indent=2).encode()+b"\n"
    members[FILENAME]=audit_bytes
    export["output_file_sha256"][FILENAME]=sha256(audit_bytes).hexdigest()
    members["EXPORT_AUDIT.json"]=json.dumps(
        export,ensure_ascii=False).encode()
    out=folder/"synthetic_native_tach.zip"
    with zipfile.ZipFile(out,"w",zipfile.ZIP_STORED) as z:
        for name,payload in members.items():
            z.writestr(name,payload)
    return out


def test_native_tach_8adc_2tach_verified_and_core_selection(tmp_path):
    archive=synthetic_tach_native_zip(tmp_path)
    session=OfflineSession.open(archive)
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    evidence=read_tach_evidence(archive)
    assert evidence is not None
    assert evidence.safe_native_channels==(9,10)
    assert evidence.receipt()["device_commands_sent"] is False
    assert evidence.receipt()["source_tach_bin_tsxml_created"] is False
    assert evidence.channels[0].samples==128
    assert evidence.channels[0].sample_rate_hz==32768
    assert evidence.channels[0].digest is not None
    selected=OriginalPageFileSelection.for_flow(flow)
    assert selected.channels==((True,)*10)
    assert selected.report()["selected_tachs"]==[1,2]
    assert selected.report()["original_tach_bin_tsxml_equivalence_verified"] is False


def test_local_pagefile_exports_original_tach_bytes_without_calibration(
        tmp_path):
    archive=synthetic_tach_native_zip(tmp_path)
    session=OfflineSession.open(archive)
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    selection=OriginalPageFileSelection.for_flow(flow)
    # Real independent source checklists: only original TACH2 selected.
    for i in range(8):
        selection=selection.set_checked("channels",i,False,flow=flow)
    selection=selection.set_checked("channels",8,False,flow=flow)
    assert selection.report()["selected_tachs"]==[2]
    # No source ADC selection means SPEC/VALUES have no channel rows;
    # operator still receives exactly the raw TACH2 bytes + source audit.
    opts=OriginalFileNameOptions(
        use_folder_prefix=False,use_custom_name=True,custom_name="NativeTach")
    target=tmp_path/"output"
    target.mkdir()
    result=export_selected_original_pagefile(
        flow,selection,opts,target)
    out=Path(result["output_folder"])
    assert result["selected_native_tach_channels"]==[2]
    data=(out/"TACH2_NATIVE_UNCALIBRATED.f32").read_bytes()
    with zipfile.ZipFile(archive) as z:
        assert data==z.read("TACH2_NATIVE_UNCALIBRATED.f32")
    assert len(data)==512
    assert not (out/"TACH1_NATIVE_UNCALIBRATED.f32").exists()
    assert not (out/"TACH2_NATIVE_UNCALIBRATED.f32.tsxml").exists()
    assert (out/FILENAME).exists()
    manifest=json.loads((out/"PAGEFILE_SELECTION.json").read_text())
    assert manifest["selected_native_tach_channels"]==[2]
    assert manifest["original_tach_tsxml_generated"] is False
    assert manifest["device_io_executed"] is False


def test_absent_or_discontinuous_tach_fails_closed_for_local_selection(
        tmp_path):
    archive=synthetic_tach_native_zip(tmp_path,present=(False,True))
    s=OfflineSession.open(archive)
    flow=OfflineMeasurementFlow.bind(s,channel=1)
    sel=OriginalPageFileSelection.for_flow(flow)
    assert sel.channels[8:] == (False,True)
    with pytest.raises(ValueError):
        sel.set_checked("channels",8,True,flow=flow)
    tmp=tmp_path/"different"
    tmp.mkdir()
    gap=synthetic_tach_native_zip(tmp,gap_on_tach1=True)
    evidence=read_tach_evidence(gap)
    assert evidence.channels[0].present
    assert not evidence.channels[0].safe_local_raw_export
    assert evidence.channels[0].discontinuities==1
    s2=OfflineSession.open(gap)
    plan=OriginalPageFileSelection.for_flow(
        OfflineMeasurementFlow.bind(s2,channel=1))
    assert plan.channels[8:] == (False,True)


def _tamper_zip(tmp_path,archive,member_name,new_content):
    with zipfile.ZipFile(archive) as z:
        files={name:z.read(name) for name in z.namelist()}
    files[member_name]=new_content
    out=tmp_path/"tampered.zip"
    with zipfile.ZipFile(out,"w") as z:
        for name,data in files.items():z.writestr(name,data)
    return out


@pytest.mark.parametrize("tamper",(
    "tach_bytes","sidecar","source_sha","calibration",
))
def test_native_tach_provenance_or_bytes_tamper_rejected(tmp_path,tamper):
    archive=synthetic_tach_native_zip(tmp_path)
    if tamper=="tach_bytes":
        with zipfile.ZipFile(archive) as z:
            data=z.read("TACH1_NATIVE_UNCALIBRATED.f32")
        bad=_tamper_zip(
            tmp_path,archive,"TACH1_NATIVE_UNCALIBRATED.f32",
            data[:-4]+b"\x00\x00\x00\x00")
    else:
        with zipfile.ZipFile(archive) as z:
            blob=json.loads(z.read(FILENAME))
        if tamper=="sidecar":
            blob["channels"][0]["frames"]=999
        elif tamper=="source_sha":
            blob["source_raw_sha256"]="f"*64
        else:
            blob["channels"][0]["physical_calibration_verified"]=True
        bad=_tamper_zip(
            tmp_path,archive,FILENAME,json.dumps(blob).encode())
    with pytest.raises((ValueError,KeyError)):
        OfflineSession.open(bad)


def test_legacy_native_zip_with_no_tach_sidecar_remains_accepted(tmp_path):
    archive=fixture_zip(tmp_path)
    session=OfflineSession.open(archive)
    assert read_tach_evidence(archive) is None
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    assert OriginalPageFileSelection.for_flow(flow).channels[8:]==(
        False,False)
