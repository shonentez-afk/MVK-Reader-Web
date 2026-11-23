"""Real-source-shaped 4-file pair; deliberately synthetic data only.

Predeclared broad-band column + split validation tests that cross-file
coincidence is never misrepresented as raw same-session authentication.
No user's private BIN/TSXML/CSV bytes or device serial are embedded.
"""
from __future__ import annotations

from datetime import datetime,timedelta
import math
import json
import struct

import numpy as np
import pytest

from ..core.original_mode2_bin_tsxml_values_alignment_qa import (
    SOURCE,compare_original_bin_tsxml_values_table,main,
)
from ..core.original_ru_csv_layout import (
    source_ru_values_header,source_ru_encode_csv,source_ru_table_rows,
    source_ru_cell_title,
)


def fixture(tmp_path, *, flat_bin=False, tsxml_day=28):
    rate=4096
    samples=rate*33
    generator=np.random.default_rng(314159)
    chunks=[]
    for block in range(66):
        amplitude=4.5+(block*13%19)/17.0+0.3*math.sin(block*.27)
        chunks.append(np.asarray(
            -35+amplitude*generator.standard_normal(rate//2),dtype="<f4"))
    raw=np.concatenate(chunks).astype("<f4")
    if flat_bin:
        raw[:]=np.float32(-35)
    assert len(raw)==samples
    # (3) is a download-copy suffix, NOT source device filename identity.
    bp=tmp_path/"MVK00000043-ADC1-2026-10-28--10-11-32(3).bin"
    bp.write_bytes(raw.tobytes())
    xml=(
        '<?xml version="1.0" encoding="windows-1251"?>\r\n'
        '<MainRoot>\r\n'
        f'<DateTime>10/{tsxml_day}/2026 10:12:05 AM</DateTime>\r\n'
        '<Culture>en-US</Culture><From Units="ms">0</From>'
        '<To Units="ms">33000</To>\r\n'
        '<ChannelsQuantity>1</ChannelsQuantity>'
        '<FrequencyPerChannel>4096</FrequencyPerChannel>'
        '<DataFileName>.\\MVK00000043-ADC1-2026-10-28--10-11-32.bin</DataFileName>'
        '<Channels><Channel Index="0">'
        '<ChannelName>MVK00000043-ADC1</ChannelName>'
        '<ChannelNumber>1</ChannelNumber>'
        '<ChannelFrequency>4096</ChannelFrequency>'
        '<Units>м/с2</Units><RealDataType>Single</RealDataType>'
        f'<DataLength>{samples*4}</DataLength><DataOffset>0</DataOffset>'
        '<InternalChannelGain>510.6</InternalChannelGain>'
        '</Channel></Channels></MainRoot>\r\n')
    xp=tmp_path/"MVK00000043-ADC1-2026-10-28--10-11-32.bin(3).tsxml"
    xp.write_bytes(xml.encode("cp1251"))
    selected=[{"channel":1,"source_list_group":group,"source_cell_index":i}
              for group,n in (("SPEC",43),("RESULT",6),("BAND",24))
              for i in range(n)]
    header=source_ru_values_header(selected)
    lines=[]
    row_values=[]
    start=datetime(2026,10,28,10,11,32)
    for tick in range(63):
        t=1+tick*.5
        e=round((t-.475)*rate)
        s=e-rate//2
        # test constructs expected ADC broadband RMS from a different
        # code path than the module's cumsum detector.
        amp=float(np.std(raw[s:e].astype(np.float64)))
        tag=(start+timedelta(seconds=t)).strftime("%H:%M:%S.%f")[:-3]
        values=["0"]*43+["ОК","ОК","ОК",f"{10+tick/100:.2f}".replace(".",","),"0","0"]
        band=["0"]*24
        band[21]=f"{amp:.5f}".replace(".",",")
        row_values.append(values+band)
        lines.append((tag+"|"+"|".join(values+band)+"\r\n").encode("cp1251"))
    vp=tmp_path/"VALUES-2026-10-28--10-11-33.csv"
    vp.write_bytes(header+b"".join(lines))
    tp=tmp_path/"TABLE-2026-10-28--10-12-02.csv"
    selected_index=58 # 10:12:02
    tp.write_bytes(source_ru_encode_csv(source_ru_table_rows(
        [1],[],[row_values[selected_index][43:]],[])))
    return bp,xp,vp,tp


def test_synthetic_matching_source_shapes_strong_holdout_not_same_raw(tmp_path):
    files=fixture(tmp_path)
    report=compare_original_bin_tsxml_values_table(*files)
    assert report["schema"]==SOURCE
    assert report["bin_tsxml_exact_channel_bytes_rate_duration_verified"]
    assert report["values_table_same_original_snapshot_verified"]
    assert report["values_table_matched_cells"]==30
    assert report["values_table_unique_matching_tick"]=="10:12:02.000"
    assert report["bin_values_time_window_plausible"]
    assert report["values_ticks_compared"]==63
    assert report["train_pearson"]>.9
    assert report["holdout_pearson"]>.9
    assert report["all_tick_pearson"]>.9
    assert report["selected_lag_ms"]==-475
    assert report["classification"]=="time_series_aligned_not_byte_authenticated"
    assert report["strong_statistical_evidence_only"]
    assert report["holdout_circular_shift_pvalue"]<=.05
    assert report["lag_fitted_without_holdout_peeking"]
    assert not report["same_physical_capture_authenticated"]
    assert not report["same_original_raw_tcp_payload_authenticated"]
    assert not report["original_delphi_numeric_parity_verified"]
    assert not report["original_getsignal_fft_parity_verified"]
    assert not report["original_writevalues_to_signal_byte_parity_verified"]
    assert not report["hardware_commands_sent"]
    receipt=json.dumps(report,ensure_ascii=False)
    assert str(tmp_path) not in receipt
    assert files[0].name not in receipt
    assert "МВК00000043" not in receipt
    assert "MVK00000043" not in receipt


def test_same_day_unrelated_flat_signal_does_not_authenticate_capture(tmp_path):
    files=fixture(tmp_path,flat_bin=True)
    report=compare_original_bin_tsxml_values_table(*files)
    assert report["bin_tsxml_exact_channel_bytes_rate_duration_verified"]
    assert report["values_table_same_original_snapshot_verified"]
    assert report["classification"]=="separate_or_not_proven"
    assert report["same_physical_capture_authenticated"] is False


def test_different_day_even_with_same_waveform_refuses_pair(tmp_path):
    files=fixture(tmp_path,tsxml_day=29)
    report=compare_original_bin_tsxml_values_table(*files)
    assert not report["bin_values_time_window_plausible"]
    assert report["classification"]=="separate_or_not_proven"


def test_unrelated_table_snapshot_not_mislabeled_as_same_capture(tmp_path):
    bp,xp,vp,tp=fixture(tmp_path)
    wrong=tp.read_bytes().replace(b"10,58",b"77,58")
    assert wrong!=tp.read_bytes()
    tp.write_bytes(wrong)
    report=compare_original_bin_tsxml_values_table(bp,xp,vp,tp)
    assert not report["values_table_same_original_snapshot_verified"]
    assert report["classification"]=="separate_or_not_proven"


@pytest.mark.parametrize("mode",["wrong_rate","wrong_length","xml_entity",
                                 "missing_xml","missing_bin","nonfinite"])
def test_corrupt_or_foreign_instrument_reference_rejected(tmp_path,mode):
    bp,xp,vp,tp=fixture(tmp_path)
    if mode=="wrong_rate":
        xp.write_bytes(xp.read_bytes().replace(
            b"<FrequencyPerChannel>4096</FrequencyPerChannel>",
            b"<FrequencyPerChannel>8192</FrequencyPerChannel>"))
    elif mode=="wrong_length":
        xp.write_bytes(xp.read_bytes().replace(
            b"<DataLength>540672</DataLength>",
            b"<DataLength>540668</DataLength>"))
    elif mode=="xml_entity":
        xp.write_bytes(xp.read_bytes().replace(
            b"<MainRoot>",b"<!DOCTYPE dangerous><MainRoot>"))
    elif mode=="missing_xml":
        xp.unlink()
    elif mode=="missing_bin":
        bp.unlink()
    elif mode=="nonfinite":
        blob=bytearray(bp.read_bytes())
        blob[:4]=struct.pack("<I",0x7f800000)
        bp.write_bytes(blob)
    with pytest.raises(ValueError):
        compare_original_bin_tsxml_values_table(bp,xp,vp,tp)


def test_wrong_field_and_linked_bin_rejected_before_result(tmp_path):
    bp,xp,vp,tp=fixture(tmp_path)
    with pytest.raises(ValueError,match="predeclared"):
        compare_original_bin_tsxml_values_table(
            bp,xp,vp,tp,source_field="Виброускорение, 10..3000 Гц")
    link=tmp_path/"other.bin"
    try:link.symlink_to(bp)
    except OSError:pytest.skip("Symlink unavailable")
    with pytest.raises(ValueError,match="regular local"):
        compare_original_bin_tsxml_values_table(link,xp,vp,tp)


def test_cli_only_discloses_aggregate_and_sha_not_measurement_values(tmp_path,capsys):
    bp,xp,vp,tp=fixture(tmp_path)
    assert main([str(bp),str(xp),str(vp),str(tp)])==0
    report=json.loads(capsys.readouterr().out)
    assert report["classification"]=="time_series_aligned_not_byte_authenticated"
    assert "private_signal_and_csv_cells_in_report" in report
    assert str(bp) not in json.dumps(report)
