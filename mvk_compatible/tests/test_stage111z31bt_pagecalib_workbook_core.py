"""BT PageCalib Core: 55 original flags, 77x11 CSV, gain candidate.

Synthetic records, original source PAS/DFM constants only. No device writes.
"""
from dataclasses import replace
from hashlib import sha256
from datetime import datetime
import struct
import json

import pytest

from ..core.original_calibration_workbench import (
    OriginalCalibrationWorkspace,GRID_COLS,GRID_ROWS,STEP_GROUPS,
    GROUP_ROW_HEADERS,GAIN_REGISTERS,DFM_UNIT_BUTTONS,DFM_SAVE_BUTTONS,
    DFM_START,DFM_PORT,CALIB_SOURCE_TABS,
    SOURCE_RATIO_DENOMINATOR_ADJUSTMENT,CALIBRATION_STEPS,
    source_calib_csv_filename,
)
from ..core.original_config_local_workflow import OriginalLocalConfigWorkspace


def _result_csv(tmp_path,values=None):
    workspace=OriginalCalibrationWorkspace.initial()
    matrix=[list(row) for row in workspace.grid]
    matrix[8][0]="100"
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
    assert tuple(x[2] for x in STEP_GROUPS)==(17,14,14,1,9)
    assert sum(x[2] for x in STEP_GROUPS)==55
    assert GROUP_ROW_HEADERS==(0,20,37,54,65)
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
    assert len(w.steps)==55 and all(w.steps)
    assert len(w.grid)==77 and all(len(r)==11 for r in w.grid)
    assert w.grid[0][0]=="Виброускорение"
    assert w.grid[1][3]=="АЦП 1"
    assert w.grid[1][10]=="АЦП 8"
    starts=(0,17,31,45,46)
    for tag,(start,group) in enumerate(zip(starts,STEP_GROUPS),1):
        a=w.toggle_group(tag)
        assert not any(a.steps[start:start+group[2]])
        assert all(a.steps[:start]) and all(a.steps[start+group[2]:])
        assert a.toggle_group(tag)==w
    assert w.select_step(7,False).checked_steps==54
    assert w.checked_steps==55
    for bad_tag in (0,6,True):
        with pytest.raises(ValueError):
            w.toggle_group(bad_tag)
    with pytest.raises(ValueError):
        w.select_step(55,True)


def test_original_csv_matrix_save_load_reopen_and_clear_keeps_log(tmp_path):
    src=_result_csv(tmp_path)
    raw=src.read_bytes()
    assert raw.startswith(b"sep=|\r\n")
    lines=raw.decode("cp1251").split("\r\n")
    assert len(lines)==79 and lines[-1]==""
    assert all(s.count("|")==11 for s in lines[1:-1])
    w=OriginalCalibrationWorkspace.load_csv(src)
    assert w.source_grid_loaded
    assert w.grid[8][2]=="1,0"
    assert w.grid[8][3:11]==("1.0",)*8
    assert w.source_sha256==sha256(raw).hexdigest()
    assert w.steps==(True,)*55
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
    assert reopened.steps==(True,)*55
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
        rounded=struct.unpack("<f",struct.pack("<f",SOURCE_RATIO_DENOMINATOR_ADJUSTMENT))[0]
        assert row.original_ratio_candidate==rounded
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


def test_source_step_identifiers_and_frequency_table():
    steps=CALIBRATION_STEPS
    assert steps[0].caption(",")=="Виброускорение: 0,5 Гц, 3467 мВ"
    assert (steps[6].index,steps[6].frequency_hz,steps[6].result_rows)==(6,"100",(8,))
    assert steps[16].caption()=="Виброускорение: 160 Гц, 1.02 мВ"
    assert steps[17].caption()=="Виброскорость: 0.5 Гц, 22.1 мВ"
    assert steps[44].caption()=="Виброперемещение: 40 Гц, 0.6441 мВ"
    assert steps[45].result_rows==tuple(range(56,64))
    assert steps[54].caption()=="Частота вращения: 1000 Гц"
    assert steps[54].result_rows==(75,)
    assert source_calib_csv_filename(datetime(2026,11,24,22,46,59))=="CALIB-2026-11-24--22-46-59.csv"


def test_proposal_uses_float32_ratio_before_range_check(tmp_path):
    config=OriginalLocalConfigWorkspace.load(_config(tmp_path))
    # Original x87 constant equals approximately 1/0.999. Upper-limit
    # rounding to the Single immediately greater than 1.2 must reject.
    src=_result_csv(tmp_path,values=["1.1988"]*8)
    with pytest.raises(ValueError,match="deviation"):
        OriginalCalibrationWorkspace.load_csv(src).candidate(config.original)
    src.unlink()
    src=_result_csv(tmp_path,values=["0.7992"]*8)
    candidate=OriginalCalibrationWorkspace.load_csv(src).candidate(config.original)
    assert candidate.entries[0].original_ratio_candidate==struct.unpack("<f",struct.pack("<f",.8))[0]


def test_proposal_rejects_a_shifted_workbook_even_if_shape_matches(tmp_path):
    config=OriginalLocalConfigWorkspace.load(_config(tmp_path))
    source=_result_csv(tmp_path)
    raw=source.read_bytes()
    source.write_bytes(raw.replace(b"100|",b"101|",1))
    with pytest.raises(ValueError,match="100 Hz"):
        OriginalCalibrationWorkspace.load_csv(source).candidate(config.original)
