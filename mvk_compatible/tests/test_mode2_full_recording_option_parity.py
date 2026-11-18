"""Source original PageFile capture options: Start->stop->Go RAW->Core->XML.

This tests ONE measurement pipeline, not extra research UI options.
"""
from __future__ import annotations

from dataclasses import replace
import json
from xml.etree import ElementTree as ET

from .test_stage111z31fs_original_live_writer_e2e import with_live_writer
from .test_stage111z31cz_source_write_stages_core import source_status
from ..core.original_live_pagefile import OriginalLiveFilePlan
from ..core.original_live_write_stages import OriginalLiveWriteLedger,EXPORT_SUBDIR
from ..core.original_pagefile_recording import OriginalFileNameOptions
from ..core.original_live_write_stages import export_source_write_windows


def test_original_xml_checkbox_captured_at_data_begin_not_export(tmp_path):
    ledger=OriginalLiveWriteLedger()
    before=source_status(adc_samples=0,aux=0,frames=1,raw=1024)
    after=source_status(adc_samples=512,aux=1,frames=21,raw=54000)
    ledger.observe(before)
    plan=OriginalLiveFilePlan().bind_status(before)
    off=OriginalFileNameOptions(write_tsxml=False)
    on=OriginalFileNameOptions(write_tsxml=True)
    ledger.toggle("data",plan,file_options=off)
    ledger.observe(after)
    ledger.toggle("data",plan,file_options=on)
    assert len(ledger.windows)==1
    window=ledger.windows[0]
    assert window.file_options is off
    assert window.receipt()["source_pagefile_write_tsxml_requested"] is False
    assert window.receipt()["source_pagefile_options_snapshot_present"]


def test_unchecked_original_tsxml_flag_does_not_create_xml_after_capture(tmp_path):
    run,flow,ledger=with_live_writer(tmp_path)
    ledger.windows=[replace(w,file_options=OriginalFileNameOptions(
        write_tsxml=False)) if w.kind=="data" else w for w in ledger.windows]
    report=export_source_write_windows(ledger,flow,run)
    assert report["source_live_source_gate_verified"] is True
    assert report["source_live_original_writer_files"]==8
    assert report["source_original_tsxml_structural_sidecars"]==0
    assert report["source_original_tsxml_skipped_by_operator"]==8
    assert report["source_original_tsxml_settings_snapshot_verified"] is True
    output=run/EXPORT_SUBDIR
    assert not list(output.glob("*.tsxml"))
    assert (output/"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin").is_file()
    evidence=json.loads((output/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text())
    skipped=[s for s in evidence["missing_source_channels"]
             if s.get("reason")=="ORIGINAL_XML_CHECKBOX_OFF"]
    assert len(skipped)==8


def test_original_operator_device_name_used_only_when_supplied(tmp_path):
    run,flow,ledger=with_live_writer(tmp_path)
    ledger.windows=[replace(w,file_options=OriginalFileNameOptions(
        write_tsxml=True,use_custom_name=True,custom_name="МВК01")) 
        if w.kind=="data" else w for w in ledger.windows]
    report=export_source_write_windows(ledger,flow,run)
    assert report["source_original_tsxml_structural_sidecars"]==8
    assert report["source_original_tsxml_skipped_by_operator"]==0
    output=run/EXPORT_SUBDIR
    xml=ET.parse(output/"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin.tsxml")
    assert xml.findtext("Channels/Channel/ChannelName")=="МВК01-ADC1"
    rec=json.loads((output/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text())
    sidecars=[p for p in rec["files"] if p.get("kind")=="source_original_tsxml_structure"]
    assert len(sidecars)==8
    assert all(p["device_name_source"]=="OPERATOR_CBFILEMVKNAME"
               for p in sidecars)
    assert all(p["original_delphi_tsxml_byte_parity_verified"] is False
               for p in sidecars)
