"""Source-recovered naming, PageStatus scale and factory visibility (offline)."""
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest

from ..core.original_mode2_source_files import (
    delphi_file_part,source_values_filename,source_device_label,
    source_writer_name_candidates,SOURCE_WRITER_CHANNEL_NAMES,SOURCE_FOLDER_TEMPLATE,
    source_serial_cell0_text,
)
from ..core.original_pagefile_recording import OriginalFileNameOptions
from ..core.original_status_workbench import source_octave_y_max,source_octave_chart_text
from ..core.original_runtime_tabs import original_runtime_visible_pages,ORIGINAL_LIVE_VISIBLE

STAMP=datetime(2026,11,24,9,5,6,tzinfo=timezone.utc)


def test_source_names_utf16_empty_prefix_and_distinct_paths():
    assert delphi_file_part("А/ё😀# $()-Z.9")=="А____# $()-Z_9"
    assert SOURCE_WRITER_CHANNEL_NAMES==tuple(f"ADC{i}" for i in range(1,9))+("TACH1","TACH2")
    assert source_values_filename(prefix="",when=STAMP)=="VALUES-2026-11-24--09-05-06.csv"
    assert source_device_label(use_custom_name=False,custom_name="ignored",status_serial_text="0012")=="MVK0012"
    assert source_device_label(use_custom_name=False,custom_name="ignored") is None
    window=SimpleNamespace(kind="data",operator_begin_utc=STAMP.isoformat(),
        channels=(True,)+(False,)*7+(True,False),
        file_options=OriginalFileNameOptions(use_custom_name=True,custom_name="МВК/1",
            file_prefix="Узел-",folder_prefix=SOURCE_FOLDER_TEMPLATE))
    result=source_writer_name_candidates(window)
    assert result["folder"]=="RunUp24-11-2026 09-05-06"
    assert result["files"]==["Узел-МВК_1-ADC1-2026-11-24--09-05-06.bin",
                            "Узел-МВК_1-TACH1-2026-11-24--09-05-06.bin"]
    assert not result["original_file_open_time_verified"]
    assert result["actual_go_filenames_unchanged"]
    window.kind="values"
    assert source_writer_name_candidates(window)["files"]==["Узел-VALUES-2026-11-24--09-05-06.csv"]
    assert source_writer_name_candidates(window)["folder"]==""
    window.kind="data"
    window.file_options=OriginalFileNameOptions(use_custom_name=False)
    assert source_writer_name_candidates(window)["reason"]=="ORIGINAL_SERIAL_CELL_TEXT_UNKNOWN"


@pytest.mark.parametrize("v,limit",[(0,0.001),(0.002,0.01),(0.02,0.1),(0.2,1),(2,10),(20,100)])
def test_source_scale_is_original_power_rule_not_auto_range(v,limit):
    values=[0.0]*43
    values[21]=v
    assert source_octave_y_max(values)==pytest.approx(limit)


def test_source_chart_cursor_and_reject_nonfinite():
    assert source_octave_chart_text(0.63)=="0,63"
    assert source_octave_chart_text(10.75)=="10,8"
    with pytest.raises(ValueError):
        source_octave_y_max([float("nan")]+[0]*42)
    with pytest.raises(ValueError):
        source_octave_y_max([0]*42)


def test_factory_page_only_on_confirmed_factory_mode():
    assert original_runtime_visible_pages(has_measurement=False,
        measurement_requested=True)==ORIGINAL_LIVE_VISIBLE
    assert original_runtime_visible_pages(has_measurement=False,
        measurement_requested=True,factory_mode=True)==ORIGINAL_LIVE_VISIBLE+("PageCalib",)
    assert original_runtime_visible_pages(has_measurement=False,factory_mode=True)==("PageStart",)


def test_serial_name_uses_source_type11_ascii_not_ip_or_raw_hex():
    from ..core.original_system_register_fields import SYSTEM_SOURCE_FIELDS,SOURCE_FIELD_KEY
    fields=[dict(index=i,key=key,register_address=addr,word_count=words,
                 valid=False,raw_hex_le=None)
            for i,(key,addr,words) in enumerate(SYSTEM_SOURCE_FIELDS)]
    status={SOURCE_FIELD_KEY:fields}
    assert source_serial_cell0_text(status) is None
    fields[0].update(valid=True,raw_hex_le=b"0123".hex())
    assert source_serial_cell0_text(status)=="0123"
    fields[0]["raw_hex_le"]=b"01\xff\x00".hex()
    assert source_serial_cell0_text(status) is None
