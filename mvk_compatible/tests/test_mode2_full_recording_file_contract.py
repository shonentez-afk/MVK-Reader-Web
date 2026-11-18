"""Integrated Mode2 PageFile provenance, filename and TSXML source schema.

Synthetic-only. The test exercises original disassembled TSXML tags,
Delphi filename sanitization, byte lengths and live verified source data.
"""
from __future__ import annotations

from datetime import datetime,timezone,timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from ..core.original_mode2_source_files import (
    delphi_file_part,source_data_filename,source_values_filename,
    build_original_tsxml_compatible,write_verified_source_tsxml_sidecars,
)


def stamp():
    return datetime(2026,11,18,15,4,6,tzinfo=timezone(timedelta(hours=3)))


def test_exact_delphi_filename_character_whitelist_and_timestamp():
    # Source _Unit114:007B1FA4 replaces unsupported UTF16 chars with '_'.
    assert delphi_file_part("MVK 01/a_ё(А)-Z.3")=="MVK 01_a__(А)-Z_3"
    assert source_data_filename(
        device="MVK01",channel_label="ADC-1",
        when=stamp(),user_prefix="Узел 1-") == (
        "Узел 1-MVK01-ADC-1-2026-11-18--15-04-06.bin")
    assert source_values_filename(
        prefix="МВК-",when=stamp())=="МВК-VALUES-2026-11-18--15-04-06.csv"
    with pytest.raises(ValueError):
        source_data_filename(device="",channel_label="ADC1",when=stamp())


def test_adc_exact_tsxml_field_order_cp1251_byte_length_and_elapsed_ms():
    document,receipt=build_original_tsxml_compatible(
        channel=1,binary_basename="SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin",
        size_bytes=8192,rate_hz=4096 if False else 8192,
        local_time=stamp(),device_label="МВК 01",
        channel_label="АЦП 1",adc_units="мм/с",adc_gain=510.56503)
    assert document.startswith(
        b'<?xml version="1.0" encoding="windows-1251"?>\r\n')
    assert b"\r\n" in document and b"\xc3\x88" not in document
    assert document.decode("cp1251").count("<MainRoot>")==1
    root=ET.fromstring(document)
    assert root.findtext("DateTime")=="11/18/2026 03:04:06 PM"
    assert root.findtext("Culture")=="en-US"
    assert root.findtext("From")=="0"
    assert root.findtext("To")=="250.00"
    assert root.findtext("FrequencyPerChannel")=="8192"
    assert root.findtext("DataFileName")==r".\SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"
    assert root.findtext("Channels/Channel/ChannelName")=="МВК 01-АЦП 1"
    assert root.findtext("Channels/Channel/ChannelNumber")=="1"
    assert root.findtext("Channels/Channel/RealDataType")=="Single"
    assert root.findtext("Channels/Channel/DataLength")=="8192"
    assert root.findtext("Channels/Channel/DataOffset")=="0"
    assert root.findtext("Channels/Channel/Units")=="мм/с"
    assert float(root.findtext("Channels/Channel/InternalChannelGain"))>500
    assert receipt["gain_from_original_frange_verified"]
    assert receipt["units_from_original_cell_text_verified"]
    assert not receipt["original_delphi_tsxml_byte_parity_verified"]
    assert receipt["sha256"]==sha256(document).hexdigest()


def test_tach_original_byte_count_and_count_units():
    document,receipt=build_original_tsxml_compatible(
        channel=9,binary_basename="SOURCE_W01_TACH1_LIVE_RX_UNSCALED.bin",
        size_bytes=65536,rate_hz=8192,local_time=stamp(),
        device_label="MVK",channel_label="TACH1")
    root=ET.fromstring(document)
    assert root.findtext("To")=="8000.00"
    assert root.findtext("Channels/Channel/RealDataType")=="Byte"
    assert root.findtext("Channels/Channel/DataLength")=="65536"
    assert root.findtext("Channels/Channel/Units")=="Count"
    assert float(root.findtext("Channels/Channel/InternalChannelGain"))==1.0
    assert receipt["source_xml_structure_and_byte_length_verified"]
    assert not receipt["original_runtime_clock_verified"]


@pytest.mark.parametrize("invalid",[
    {"channel":11},{"channel":0},{"rate_hz":777},
    {"binary_basename":"../a.bin"},{"binary_basename":"x.xml"},
    {"size_bytes":3},{"local_time":datetime(2026,11,18)},
    {"device_label":"mvk<unsafe>"},{"adc_gain":float("nan")},
])
def test_original_txml_rejects_unproven_data(invalid):
    values={
        "channel":1,"binary_basename":"a.bin","size_bytes":4,
        "rate_hz":8192,"local_time":stamp(),"device_label":"MVK",
        "channel_label":"ADC1",
    }
    values.update(invalid)
    with pytest.raises((ValueError,UnicodeEncodeError)):
        build_original_tsxml_compatible(**values)


def test_source_sidecars_skip_mixed_fs_and_preserve_single_fs(tmp_path):
    original=tmp_path/"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"
    original.write_bytes(b"\x01\x00\x00\x00"*4)
    mixed=tmp_path/"SOURCE_W01_ADC2_LIVE_RX_UNSCALED.bin"
    mixed.write_bytes(b"\x02\x00\x00\x00"*4)
    proof={
        "source_raw_sha256":"1"*64,
        "verified_channel_files":[{
            "name":original.name,"channel":1,"bytes":16,
            "sha256":sha256(original.read_bytes()).hexdigest(),
            "verified_packet_rates_hz":[8192],
        },{
            "name":mixed.name,"channel":2,"bytes":16,
            "sha256":sha256(mixed.read_bytes()).hexdigest(),
            "verified_packet_rates_hz":[8192,32768],
        }]
    }
    rows=write_verified_source_tsxml_sidecars(
        tmp_path,live_proof=proof,
        source_run_end_utc="2026-11-18T12:17:00Z")
    assert rows[0]["sidecar_created"] and not rows[1]["sidecar_created"]
    assert rows[1]["reason"]=="MULTIPLE_OR_UNKNOWN_SOURCE_FS"
    candidate=(tmp_path/(original.name+".tsxml"))
    assert candidate.exists() and ET.parse(candidate).getroot().tag=="MainRoot"
    assert not (tmp_path/(mixed.name+".tsxml")).exists()
    assert not rows[0]["original_delphi_tsxml_byte_parity_verified"]
    original.write_bytes(original.read_bytes()[:-1]+b"Q")
    with pytest.raises(ValueError,match="changed"):
        write_verified_source_tsxml_sidecars(
            tmp_path,live_proof=proof,
            source_run_end_utc="2026-11-18T12:17:00Z")
