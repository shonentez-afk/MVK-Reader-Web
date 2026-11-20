"""Source-shaped synthetic VALUES/TABLE pair; no private original rows."""
from __future__ import annotations

import pytest

from ..core.original_values_table_pair_qa import compare_original_values_table


def fixture(tmp_path, *, different=False, ambiguous=False, different_date=False,
            utf8=False):
    channels=["АЦП 1","АЦП 3"]
    cols=[f"Полоса {i} Гц" for i in range(43)]+[
        "Индикатор перегрузки","Индикатор заполнения буферов",
        "Состояние датчика","Напряжение на датчике",
        "Виброускорение, Х..25 кГц","Пик-фактор виброуск., Х..25 кГц",
    ]+[f"Измерение {i}" for i in range(24)]
    one=["ОК","ОК","ОК","10,62","0","0"]+[str(i+1) for i in range(24)]
    three=["ОК","ОК","ОК","10,84","0","0"]+[str(i+31) for i in range(24)]
    complete=["0"]*43+one+["0"]*43+three
    prior=complete.copy()
    prior[-1]="999"
    if ambiguous:
        prior=complete.copy()
    v=[["sep=",""],
       [""]+[ch for ch in channels for _ in range(73)],
       ["Время"]+cols*2,
       ["10:12:02.123"]+prior,
       ["10:12:02.623"]+complete]
    t=[["sep=",""],["Наименование параметра",*channels,""]]
    for i,(a,b) in enumerate(zip(one,three)):
        t.append([cols[43+i],a,("888" if different and i==29 else b),""])
    t.extend([[],["Наименование параметра",""]])
    t.extend([[f"Тахометр {i}",""] for i in range(6)])
    assert len(t)==40
    vp=tmp_path/"VALUES-2026-10-28--10-11-33.csv"
    tp=tmp_path/("TABLE-2026-10-29--10-12-02.csv" if different_date else
                 "TABLE-2026-10-28--10-12-02.csv")
    for file,rows in ((vp,v),(tp,t)):
        data="".join("|".join(line)+"\r\n" for line in rows)
        file.write_bytes(data.encode("utf-8" if utf8 else "cp1251"))
    return vp,tp


def test_exact_snapshot_requires_unique_match_all_60_cells(tmp_path):
    v,t=fixture(tmp_path)
    receipt=compare_original_values_table(v,t)
    assert receipt["classification"]=="verified_same_snapshot"
    assert receipt["cells_compared_per_row"]==60
    assert receipt["best_same_row_exact_cell_matches"]==60
    assert receipt["second_best_same_row_matches"]==59
    assert receipt["unique_matching_tick"]=="10:12:02.623"
    assert receipt["matching_tick_minus_table_filename_seconds"]==0.623
    assert receipt["source_columns_per_adc"]==73
    assert receipt["values_columns_including_time"]==147
    assert receipt["original_encoding"]=="cp1251"
    assert not receipt["bin_tsxml_same_run_verified"]
    assert not receipt["includes_private_original_values"]


def test_mismatch_does_not_assert_same_run(tmp_path):
    v,t=fixture(tmp_path,different=True)
    got=compare_original_values_table(v,t)
    assert got["classification"]=="separate_or_not_proven"
    assert got["best_same_row_exact_cell_matches"]<60


def test_duplicated_constant_rows_not_unique(tmp_path):
    v,t=fixture(tmp_path,ambiguous=True)
    got=compare_original_values_table(v,t)
    assert got["number_of_perfect_matching_ticks"]==2
    assert got["classification"]=="separate_or_not_proven"


def test_wrong_calendar_date_cannot_validate_pair(tmp_path):
    v,t=fixture(tmp_path,different_date=True)
    got=compare_original_values_table(v,t)
    assert got["best_same_row_exact_cell_matches"]==60
    assert not got["filename_date_agrees"]
    assert got["classification"]=="separate_or_not_proven"


def test_corrupt_line_endings_utf8_and_symlinks_rejected(tmp_path):
    v,t=fixture(tmp_path)
    t.write_bytes(t.read_bytes().replace(b"\r\n",b"\n"))
    with pytest.raises(ValueError,match="CRLF"):
        compare_original_values_table(v,t)
    v,t=fixture(tmp_path,utf8=True)
    with pytest.raises(ValueError):
        compare_original_values_table(v,t)
    v,t=fixture(tmp_path)
    alias=tmp_path/"alias.csv"
    try:
        alias.symlink_to(v)
    except OSError:
        pytest.skip("symlinks not available")
    with pytest.raises(ValueError,match="non-symlink"):
        compare_original_values_table(alias,t)
