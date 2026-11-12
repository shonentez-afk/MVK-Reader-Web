"""BT PageCalib Core: 49 original flags, 77x11 CSV, gain candidate.

Synthetic records, original source PAS/DFM constants only. No device writes.
"""
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from ..core.original_calibration_workbench import (
    OriginalCalibrationWorkspace,GRID_COLS,GRID_ROWS,STEP_GROUPS,
    GROUP_ROW_HEADERS,GAIN_REGISTERS,DFM_UNIT_BUTTONS,DFM_SAVE_BUTTONS,
    DFM_START,DFM_PORT,CALIB_SOURCE_TABS,
    SOURCE_RATIO_DENOMINATOR_ADJUSTMENT,
)
from ..core.original_config_local_workflow import OriginalLocalConfigWorkspace


def _result_csv(tmp_path,values=None):
    workspace=OriginalCalibrationWorkspace.initial()
    matrix=[list(row) for row in workspace.grid]
    matrix[8][2]="1,0"  # Original StrToFloat locale source
    for adc in range(8):
        matrix[8][3+adc]=(values or ["1.0"]*8)[adc]
    worksheet=replace(workspace,grid=tuple(tuple(row) for row in matrix))
    path=tmp_path/"CALIB-original-synthetic.csv"
    result=worksheet.export_csv(path)
    assert result["original_shape"]==[77,11]
    return path


def _config(tmp_path):
    config=tmp_path/"source_calib_config.txt"
    config.write_text(
        "; synthetic original TMvkCellList (NOT physical device config)\n"
        "+0x0000\n"+
        "".join(f"0x{0x20+2*i:04X} f:{1+i*.1:.2f}\n"
                for i in range(8)),
        encoding="utf-8")
    return config


def test_real_source_geometry_steps_and_group_toggle_exact_offsets():
    assert len(STEP_GROUPS)==5
    assert tuple(x[2] for x in STEP_GROUPS)==(11,14,14,1,9)
    assert sum(x[2] for x in STEP_GROUPS)==49
    assert GROUP_ROW_HEADERS==(0,14,25,36,47)
    assert GRID_COLS==11 and GRID_ROWS==77
    assert len(GAIN_REGISTERS)==8
    assert DFM_START==(6,8,107,41)
    assert DFM_PORT==(216,16,129,24)
    assert DFM_SAVE_BUTTONS==(
        ("bCalibSave",6,8,155,41),
        ("bCalibClear",174,8,155,41),
        ("bCalibGenerate",342,8,155,41))
    assert tuple(x[1] for x in DFM_UNIT_BUTTONS)==(1,2,3,4,5)
    assert CALIB_SOURCE_TABS==2

    w=OriginalCalibrationWorkspace.initial()
    assert len(w.steps)==49 and all(w.steps)
    assert len(w.grid)==77 and all(len(r)==11 for r in w.grid)
    assert "Ускорение" in w.grid[0][0]
    assert w.grid[1][3]=="АЦП 1"
    assert w.grid[1][10]=="АЦП 8"
    starts=(0,11,25,39,40)
    for tag,(start,group) in enumerate(zip(starts,STEP_GROUPS),1):
        a=w.toggle_group(tag)
        assert not any(a.steps[start:start+group[2]])
        assert all(a.steps[:start]) and all(a.steps[start+group[2]:])
        assert a.toggle_group(tag)==w
    assert w.select_step(7,False).checked_steps==48
    assert w.checked_steps==49
    for bad_tag in (0,6,True):
        with pytest.raises(ValueError):
            w.toggle_group(bad_tag)
    with pytest.raises(ValueError):
        w.select_step(49,True)


def test_original_csv_matrix_save_load_reopen_and_clear_keeps_log(tmp_path):
    src=_result_csv(tmp_path)
    raw=src.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbfsep=|\n")
    assert len(src.read_text(encoding="utf-8-sig").splitlines())==78
    w=OriginalCalibrationWorkspace.load_csv(src)
    assert w.source_grid_loaded
    assert w.grid[8][2]=="1,0"
    assert w.grid[8][3:11]==("1.0",)*8
    assert w.source_sha256==sha256(raw).hexdigest()
    assert w.steps==(True,)*49
    log=tmp_path/"calib-original.log"
    log.write_text("исходный лог — только тест\nСтрока 2\n",encoding="utf-8")
    w=w.open_log(log)
    assert len(w.log_lines)==2
    out=tmp_path/"CALIB-exported.csv"
    result=w.export_csv(out)
    assert result["local_file_created"]
    assert result["independent_source_csv_readback_passed"]
    assert result["saved_csv_sha256"]==sha256(out.read_bytes()).hexdigest()
    assert src.read_bytes()==raw
    reopened=OriginalCalibrationWorkspace.load_csv(out)
    assert reopened.grid==w.grid
    assert reopened.steps==(True,)*49
    with pytest.raises(ValueError,match="NEW"):
        w.export_csv(out)
    after=w.clear_grid()
    assert not after.source_grid_loaded
    assert after.log_lines==w.log_lines
    assert after.grid[8][2]==""
    assert len(after.grid)==77
    assert src.read_bytes()==raw


def test_real_calib_generate_row8_adc_gain_source_ratio_candidate(tmp_path):
    csv_file=_result_csv(tmp_path)
    config_file=_config(tmp_path)
    csv_sha=sha256(csv_file.read_bytes()).hexdigest()
    config_sha=sha256(config_file.read_bytes()).hexdigest()
    w=OriginalCalibrationWorkspace.load_csv(csv_file)
    config=OriginalLocalConfigWorkspace.load(config_file)
    proposal=w.candidate(config.original)
    assert len(proposal.entries)==8
    report=proposal.report()
    assert not report["physical_calibration_verified"]
    assert not report["device_commands_sent"]
    assert not report["uploadable_original_calib_txt_created"]
    assert report["source_ratio_limits"]==[.8,1.2]
    assert report["source_row"]==8
    assert report["source_reference_column"]==2
    assert report["source_measured_columns"]==[3,4,5,6,7,8,9,10]
    for i,row in enumerate(proposal.entries):
        assert row.adc==i+1
        assert row.register==0x20+2*i
        assert abs(row.original_ratio_candidate-
                   SOURCE_RATIO_DENOMINATOR_ADJUSTMENT)<1e-12
        assert abs(row.new_gain_float32_candidate-
                   row.old_gain/SOURCE_RATIO_DENOMINATOR_ADJUSTMENT)<1e-6
    dest=tmp_path/"CALIB-offline-review.json"
    result=OriginalCalibrationWorkspace.save_candidate_json(proposal,dest)
    assert result["local_json_created"]
    assert result["adc_gain_candidates"]==8
    assert result["not_a_device_upload_file"]
    assert sha256(dest.read_bytes()).hexdigest()==result["sha256"]
    loaded=json.loads(dest.read_text(encoding="utf-8"))
    assert loaded==report
    assert csv_sha==sha256(csv_file.read_bytes()).hexdigest()
    assert config_sha==sha256(config_file.read_bytes()).hexdigest()
    assert not (tmp_path/"CALIB-MVK.txt").exists()


def test_candidate_rejects_malformed_missing_source_and_out_of_range(tmp_path):
    config=OriginalLocalConfigWorkspace.load(_config(tmp_path))
    with pytest.raises(ValueError,match="Original CALIB CSV"):
        OriginalCalibrationWorkspace.initial().candidate(config.original)
    out_of_range=_result_csv(tmp_path,values=["10.0"]+["1.0"]*7)
    loaded=OriginalCalibrationWorkspace.load_csv(out_of_range)
    with pytest.raises(ValueError,match="deviation"):
        loaded.candidate(config.original)
    out_of_range.write_bytes(out_of_range.read_bytes()[:-10])
    with pytest.raises(ValueError,match="changed"):
        loaded.candidate(config.original)


def test_bad_csv_format_formula_and_stale_source_are_denied(tmp_path):
    src=_result_csv(tmp_path)
    w=OriginalCalibrationWorkspace.load_csv(src)
    wrong=tmp_path/"bad.csv"
    wrong.write_text("sep=|\n1|2|3|\n",encoding="utf-8")
    with pytest.raises(ValueError,match="77 rows"):
        OriginalCalibrationWorkspace.load_csv(wrong)
    lines=[list(r) for r in w.grid]
    lines[8][4]="=HYPERLINK(1)"
    unsafe=replace(w,grid=tuple(tuple(r) for r in lines))
    target=tmp_path/"unsafe.csv"
    with pytest.raises(ValueError,match="formula"):
        unsafe.export_csv(target)
    assert not target.exists()
    original=src.read_bytes()
    src.write_bytes(original[:-4])
    with pytest.raises(ValueError,match="changed"):
        w.export_csv(tmp_path/"stale.csv")
    assert not (tmp_path/"stale.csv").exists()
