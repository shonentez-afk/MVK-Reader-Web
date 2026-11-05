"""Synthetic-only local screenshot PNG diff CLI regression (Stage111Z31M)."""
import json
import numpy as np
import pytest

PySide6=pytest.importorskip("PySide6")
from PySide6.QtGui import QImage

from mvk_compatible.desktop.spectrum_screen_diff_cli import main


def test_png_diff_cli_with_independently_placed_crops_no_file_names(
        tmp_path,capsys):
    h,w=120,220
    pixels=np.full((h,w,4),255,dtype=np.uint8)
    pixels[25:27,20:200,:3]=0
    pixels[15:95,100:102,:3]=192
    src=tmp_path/"original_nonpublic_mvkview.png"
    cand=tmp_path/"candidate_nonpublic_mvkgdi.png"
    for path in (src,cand):
        image=QImage(
            pixels.copy().data,w,h,w*4,QImage.Format_RGBA8888).copy()
        assert image.save(str(path))
    assert main(["--original",str(src),"--candidate",str(cand),
                 "--original-crop","0,0,220,120",
                 "--candidate-crop","0,0,220,120"])==0
    out=capsys.readouterr().out
    obj=json.loads(out)
    assert obj["best_match"]["candidate_to_original_offset_px"]==[0,0]
    assert obj["best_match"][
        "rgb_channel_mean_absolute_error_on_foreground"]==0.
    assert obj["complete_mvkview_spectrum_parity_verified"] is False
    assert str(tmp_path) not in out
    assert src.name not in out and cand.name not in out


def test_png_cli_rejects_inconsistent_crops_without_raw_output(
        tmp_path,capsys):
    pixels=np.full((90,150,4),255,dtype=np.uint8)
    path=tmp_path/"plot.png"
    image=QImage(
        pixels.data,150,90,150*4,QImage.Format_RGBA8888).copy()
    assert image.save(str(path))
    with pytest.raises(SystemExit) as exc:
        main(["--original",str(path),"--candidate",str(path),
              "--original-crop","0,0,120,80",
              "--candidate-crop","0,0,90,80"])
    assert exc.value.code==2
    out=capsys.readouterr()
    assert "Image comparison unavailable" in out.err
    assert str(path) not in out.err
