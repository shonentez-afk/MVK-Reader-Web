"""Stage111Z31BU: true source PageStart + four-grid PageStatus Core tests.

Only synthetic Native R6.1 ZIP / direct Single BIN/TSXML. No device I/O.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import csv
from zipfile import BadZipFile
from pathlib import Path
import pytest

from .test_offline_core import fixture_zip
from .test_stage111z28_dsp_tach_ticks import _fixture
from .test_stage111z16_direct_bin_tsxml import _make_pair
from ..core.offline_export import OfflineSession
from ..core.direct_bin_session import DirectBinSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_config_idp_tables import source_octave_frequencies_float32
from ..core.original_start_workbench import (
    OriginalStartWorkspace,SourceLibraryItem,START_BUTTONS,
    START_IP_DEFAULT,START_IP_RECT,START_LIBRARY_RECT,MAX_LIBRARY_FILES,
    validate_source_ipv4,
)
from ..core.original_status_workbench import (
    SOURCE as STATUS_SOURCE,MODE_GRID,ORIGINAL_STATUS_GRIDS,
    ORIGINAL_STATUS_TABS_DESIGN_TIME,ORIGINAL_STATUS_TABS_RUNTIME,
    ORIGINAL_STATUS_CHART_RECT,ORIGINAL_STATUS_SPLITTER_RECT,
    source_status_projection,export_verified_status_csv,
)


def test_original_start_dfm_controls_and_real_pas_mode_routes():
    assert START_IP_DEFAULT=="192.168.0.30"
    assert START_IP_RECT==(157,208,173,24)
    assert START_LIBRARY_RECT==(29,276,301,24)
    assert tuple((row[0],row[1:5],row[6],row[7])
                 for row in START_BUTTONS)==(
        ("bTaskConnect",(29,19,301,86),0,2),
        ("bTaskConfigCh",(370,19,458,86),1,6),
        ("bTaskView",(29,105,301,86),6,1),
        ("bTaskConfigIP",(370,105,458,86),2,4),
        ("bTaskConfigCalib",(370,193,458,86),3,5),
    )
    workspace=OriginalStartWorkspace()
    assert workspace.report()["device_io_performed"] is False
    assert workspace.report()["network_scan_performed"] is False
    for row in START_BUTTONS:
        action=workspace.source_route(row[0])
        assert action["original_mode"]==row[7]
        assert not action["device_command_issued"]
    with pytest.raises(ValueError):
        workspace.source_route("bTaskFake")


@pytest.mark.parametrize("bad",[
    "", "localhost","192.168.0.256","192.168.00.30","127.0.0.1",
    "0.0.0.0","255.255.255.255","224.1.2.3",
    "192.168.0.30 ","-1.2.3.4","1.2.3.4:10230",
])
def test_edipaddr_source_never_silently_accepts_invalid_ip(bad):
    with pytest.raises(ValueError):
        validate_source_ipv4(bad)
    assert OriginalStartWorkspace().device_ipv4==START_IP_DEFAULT


def test_real_local_source_library_list_selection_path_guard(tmp_path):
    folder=tmp_path/"recordings"
    folder.mkdir()
    archive=fixture_zip(folder,sample_count=4096)
    raw=archive.read_bytes()
    other,sidecar,_=_make_pair(folder,adc=4,n=8192)
    (folder/"ignore.exe").write_bytes(b"x")
    w=OriginalStartWorkspace()
    with pytest.raises(ValueError,match="explicitly"):
        w.list_recordings()
    w=w.with_library(folder)
    files=w.list_recordings()
    filenames={x.basename for x in files}
    assert archive.name in filenames
    assert other.name in filenames
    assert sidecar.name in filenames
    assert "ignore.exe" not in filenames
    assert all(isinstance(x,SourceLibraryItem) for x in files)
    assert w.selected_file(archive.name)==archive
    assert sha256(w.selected_file(archive.name).read_bytes()).hexdigest()==sha256(raw).hexdigest()
    with pytest.raises(ValueError):
        w.selected_file("../ignore.exe")
    with pytest.raises(ValueError):
        w.selected_file("ignore.exe")
    with pytest.raises(ValueError):
        w.selected_file("..\\escape.zip")
    with pytest.raises(ValueError):
        w.selected_file("not-existing.zip")
    folder2=tmp_path/"other"
    folder2.mkdir()
    linked=folder/"sneak.zip"
    try:
        linked.symlink_to(archive)
    except (OSError,NotImplementedError):
        pass
    else:
        assert linked.name not in {x.basename for x in w.list_recordings()}
        with pytest.raises(ValueError):
            w.selected_file(linked.name)
    with pytest.raises(ValueError):
        w.with_library(folder/"missing")
    assert w.report()["library_explicit"]
    assert str(folder) not in str(w.report())
    assert sha256(archive.read_bytes()).hexdigest()==sha256(raw).hexdigest()


def test_original_page_status_four_physical_table_modes_and_43_band_cursor(tmp_path):
    assert ORIGINAL_STATUS_TABS_DESIGN_TIME==2
    assert ORIGINAL_STATUS_TABS_RUNTIME==15
    assert ORIGINAL_STATUS_GRIDS==(
        "tabStatus","tabAlarmResult","tabAllResult","tabResult")
    assert MODE_GRID==(
        "tabStatus","tabAlarmResult",
        "tabAllResult","tabAllResult","tabAllResult",
        *(("tabResult",)*10))
    assert ORIGINAL_STATUS_CHART_RECT==(4,42,400,720)
    assert ORIGINAL_STATUS_SPLITTER_RECT==(404,42,8,720)
    native=OfflineSession.open(_fixture(tmp_path))
    flow=OfflineMeasurementFlow.bind(native,channel=1,tick_index=0)
    for mode in range(15):
        result=source_status_projection(mode,flow)
        assert result.mode==mode
        assert result.table_name==MODE_GRID[mode]
        assert result.model.index==mode
        assert len(result.model.rows)>0
        assert result.source_digest is not None
        assert result.receipt()["device_io_performed"] is False
        if 5<=mode<=12:
            assert result.chart_visible
            cursor=result.cursor(0)
            assert cursor["band_index"]==0
            assert cursor["adc"]==mode-4
            assert cursor["nominal_hz_float32"]==source_octave_frequencies_float32()[0]
            assert cursor["original_canvas_mouse_pixel_parity_verified"] is False
            with pytest.raises(ValueError):
                result.cursor(43)
        else:
            assert not result.chart_visible
            with pytest.raises(ValueError):
                result.cursor(0)
    absent=source_status_projection(0,None)
    assert absent.source_digest is None and absent.model.rows[0][1]=="—"


def test_real_page_status_mode5_csv_excludes_false_alarm_or_peak_values(tmp_path):
    source=fixture_zip(tmp_path,sample_count=4096)
    oldsha=sha256(source.read_bytes()).hexdigest()
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(source),channel=4)
    current=source_status_projection(5,flow)
    assert current.model.rows[0][0]
    assert current.model.bands_for_plot is not None
    file=tmp_path/"source-mode05.csv"
    report=export_verified_status_csv(flow,5,file)
    assert report["source"]==STATUS_SOURCE
    assert report["original_grid_name"]=="tabResult"
    assert report["saved_rows"]==43
    assert report["saved_columns"]==2
    assert report["all_written_rows_reopened_and_verified"] is True
    assert report["device_io_performed"] is False
    with file.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.reader(f,delimiter=";"))
    assert len(rows)==44
    assert rows[1][0]==current.model.rows[0][0]
    assert report["sha256"]==sha256(file.read_bytes()).hexdigest()
    assert sha256(source.read_bytes()).hexdigest()==oldsha
    with pytest.raises(ValueError,match="NEW"):
        export_verified_status_csv(flow,5,file)
    assert sha256(source.read_bytes()).hexdigest()==oldsha


def test_source_status_no_native_aux_bin_never_fabricates_values(tmp_path):
    binfile,_,_=_make_pair(tmp_path,adc=4,n=8192)
    direct=OfflineMeasurementFlow.bind(
        DirectBinSession.open(binfile),channel=4)
    for mode in (0,1,2,5,13,14):
        view=source_status_projection(mode,direct)
        assert not view.chart_visible
        assert view.model.bands_for_plot is None
        assert view.source_digest is not None
        assert view.model.rows
        assert view.model.rows[0][0] in ("Источник","Контроль 1 · AlarmValue (отн. 0x130)")
    with pytest.raises(ValueError,match="VALUES"):
        export_verified_status_csv(direct,5,tmp_path/"fake-VALUES.csv")
    assert not (tmp_path/"fake-VALUES.csv").exists()


def test_source_status_stale_zip_refused_before_export(tmp_path):
    source=fixture_zip(tmp_path,sample_count=4096)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(source))
    before=sha256(source.read_bytes()).hexdigest()
    source.write_bytes(source.read_bytes()[:-20])
    with pytest.raises((ValueError,OSError,KeyError,RuntimeError,BadZipFile)):
        export_verified_status_csv(flow,3,tmp_path/"out.csv")
    assert not (tmp_path/"out.csv").exists()
    assert sha256(source.read_bytes()).hexdigest()!=before
