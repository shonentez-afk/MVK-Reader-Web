"""BR: original PageFile 10/43/(24+43+6) and REAL local selected export.

No original private data, instrument, recording thread or invented TACH RAW.
"""
from datetime import datetime,timezone
from hashlib import sha256
import csv
import json
import zipfile

import pytest

from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from ..core.offline_export import OfflineSession
from ..core.direct_bin_session import DirectBinSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_pagefile_recording import (
    OriginalPageFileSelection,OriginalFileNameOptions,
    export_selected_original_pagefile,
    CHANNEL_COUNT,SPEC_COUNT,VALUE_COUNT,
    ORIGINAL_DFM_FILE_ACTION_TABS,ORIGINAL_DFM_FILE_ADC_HEIGHT,
    ORIGINAL_DFM_LEFT_WIDTH,ORIGINAL_DFM_SPEC_WIDTH,ORIGINAL_DFM_VALUES_WIDTH,
    ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE,SOURCE,
)

WHEN=datetime(2026,11,12,16,25,9,tzinfo=timezone.utc)


def test_original_private_dfm_constants_exact_and_validated_selection(tmp_path):
    assert (CHANNEL_COUNT,SPEC_COUNT,VALUE_COUNT)==(10,43,73)
    assert ORIGINAL_DFM_FILE_ACTION_TABS==2
    assert ORIGINAL_DFM_FILE_ADC_HEIGHT==207
    assert ORIGINAL_DFM_LEFT_WIDTH==369
    assert ORIGINAL_DFM_SPEC_WIDTH==256
    assert ORIGINAL_DFM_VALUES_WIDTH==343
    assert ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE=='"RunUp"dd-mm-yyyy hh-nn-ss'
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=4096))
    flow=OfflineMeasurementFlow.bind(session,channel=2)
    s=OriginalPageFileSelection.for_flow(flow)
    assert len(s.checked("channels"))==8
    assert len(s.checked("spec"))==43
    assert len(s.checked("values"))==67
    assert s.channels[-2:]==(False,False)
    assert s.values[-6:]==(False,)*6
    with pytest.raises(ValueError,match="TACH"):
        s.set_checked("channels",8,True,flow=flow)
    with pytest.raises(ValueError,match="TACH"):
        s.set_checked("values",68,True,flow=flow)
    next_s=s.set_checked("channels",1,False,flow=flow)
    assert next_s.checked("channels")==(0,2,3,4,5,6,7)
    assert s.checked("channels")==tuple(range(8))
    other=next_s.set_checked("spec",42,False,flow=flow)
    assert 42 not in other.checked("spec")
    assert 42 in s.checked("spec")
    with pytest.raises(ValueError):
        s.set_checked("channels",10,True,flow=flow)
    with pytest.raises(ValueError):
        OriginalPageFileSelection((True,)*9,(True,)*43,(True,)*73)


def test_native_zip_real_selected_raw_and_dsp_are_exported_and_sha_checked(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=4096))
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    flags=OriginalPageFileSelection.for_flow(flow)
    for adc in range(2,9):
        flags=flags.set_checked("channels",adc-1,False,flow=flow)
    for i in range(43):
        if i!=5:
            flags=flags.set_checked("spec",i,False,flow=flow)
    for i in range(67):
        if i not in (0,25):
            flags=flags.set_checked("values",i,False,flow=flow)
    options=OriginalFileNameOptions(
        write_tsxml=True,use_folder_prefix=True,use_custom_name=True,
        folder_prefix=ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE,
        custom_name="Bench_MVK")
    report=export_selected_original_pagefile(
        flow,flags,options,tmp_path,when=WHEN)
    assert report["source"]==SOURCE
    assert report["selected_channels"]==[1]
    assert report["selected_result_rows"]==3
    assert report["files_written"]==4
    assert report["source_files_copied_without_resampling"]
    assert not report["device_io_executed"]
    target=tmp_path/f"RunUp12-11-2026 16-25-09_Bench_MVK_{flow.source_record()['source_bin_sha256'][:12]}"
    assert target==report["output_folder"] or str(target)==report["output_folder"]
    with zipfile.ZipFile(session.path) as z:
        bin_name=next(n for n in z.namelist()
                      if n.startswith(session.serial+"-ADC1-") and n.endswith(".bin"))
        for file_name in (bin_name,bin_name+".tsxml"):
            assert (target/file_name).read_bytes()==z.read(file_name)
    with (target/"PAGEFILE_SELECTED_VALUES.csv").open(
            encoding="utf-8",newline="") as fp:
        rows=list(csv.reader(fp))
    assert len(rows)==4
    assert [r[1] for r in rows[1:]]==[
        "SPEC","VALUES","VALUES third-octave"]
    manifest=json.loads((target/"PAGEFILE_SELECTION.json").read_text(
        encoding="utf-8"))
    assert manifest["source_pagefile_checklists"][
        "original_channel_flag_count"]==10
    assert manifest["selection_rows"]==3
    assert not manifest["original_mvkview_tmkvthread_write_data_executed"]
    assert not manifest["device_io_executed"]
    assert not manifest["original_file_format_pixel_runtime_parity_verified"]
    for item in manifest["files"]:
        assert sha256((target/item["name"]).read_bytes()).hexdigest()==item["sha256"]
    assert str(session.path) not in repr(manifest)
    with pytest.raises(ValueError,match="already exists"):
        export_selected_original_pagefile(
            flow,flags,options,tmp_path,when=WHEN)


def test_direct_single_bin_copies_only_real_source_and_reopens(tmp_path):
    original,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    session=DirectBinSession.open(original)
    flow=OfflineMeasurementFlow.bind(session,channel=4)
    flags=OriginalPageFileSelection.for_flow(flow)
    assert flags.checked("channels")==(3,)
    assert not flags.checked("values")
    assert not flags.checked("spec")
    with pytest.raises(ValueError,match="SPEC"):
        flags.set_checked("spec",0,True,flow=flow)
    options=OriginalFileNameOptions(
        write_tsxml=True,use_folder_prefix=True,use_custom_name=True,
        folder_prefix="MyFileSource",custom_name="Device04")
    out=tmp_path/"export"
    out.mkdir()
    report=export_selected_original_pagefile(
        flow,flags,options,out,when=WHEN)
    assert report["files_written"]==3  # exact BIN + TSXML + manifest
    target=next(out.iterdir())
    exported=target/original.name
    assert exported.read_bytes()==original.read_bytes()
    assert (target/sidecar.name).read_bytes()==sidecar.read_bytes()
    # This selected original BIN remains usable in the same Qt Core parser.
    again=DirectBinSession.open(exported)
    assert again.available_channels==(4,)
    assert again.channel_files[0].bin_sha256==session.channel_files[0].bin_sha256
    assert report["selected_result_rows"]==0


def test_no_fake_dsp_tach_no_overwrite_no_path_traversal(tmp_path):
    path,_,_=_make_pair(tmp_path,adc=4,n=8192)
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(path),channel=4)
    s=OriginalPageFileSelection.for_flow(flow)
    before=sha256(path.read_bytes()).hexdigest()
    none=s.set_checked("channels",3,False,flow=flow)
    safe=OriginalFileNameOptions(
        write_tsxml=False,use_folder_prefix=False,
        use_custom_name=True,custom_name="Bench_MVK")
    with pytest.raises(ValueError,match="At least one"):
        export_selected_original_pagefile(flow,none,safe,tmp_path,when=WHEN)
    with pytest.raises(ValueError):
        OriginalFileNameOptions(
            use_folder_prefix=True,folder_prefix="../escape",
            use_custom_name=True,custom_name="Bench"
        ).export_folder_name(flow,WHEN)
    with pytest.raises(ValueError):
        OriginalFileNameOptions(
            use_custom_name=True,custom_name="../escape"
        ).export_folder_name(flow,WHEN)
    assert sha256(path.read_bytes()).hexdigest()==before
    assert all(not x.is_dir() or x.name not in ("escape","Bench")
               for x in tmp_path.iterdir())


def test_source_zip_tampering_refused_before_copy(tmp_path):
    source,_,_=_make_pair(tmp_path,adc=4,n=8192)
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(source),channel=4)
    selection=OriginalPageFileSelection.for_flow(flow)
    source.write_bytes(source.read_bytes()[:-4]+b"\x00\x00\x00\x00")
    with pytest.raises(ValueError):
        export_selected_original_pagefile(
            flow,selection,
            OriginalFileNameOptions(use_custom_name=True,
                                    custom_name="MVK04"),
            tmp_path,when=WHEN)
