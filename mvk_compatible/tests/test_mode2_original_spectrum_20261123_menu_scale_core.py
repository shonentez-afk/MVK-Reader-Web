"""Original MVKView spectrum popups from EIGHT 2026-11-23 user screenshots.

Source data are derived tables only. All fixtures synthetic, no private
vendor source/IDP/BIN/TSXML or original screen pixels in GitHub.
"""
import pytest

from ..core.mvk_original_scale_tables_idr_candidate import (
    HORIZONTAL_HZ,FFT_WINDOW_SAMPLES,DB_Y_RANGES,PHYSICAL_Y_DIVISORS,
    original_physical_y_caption,original_fft_resolution_caption,
    source_spectrum_y_unit,research_spectrum_vscale_auto_basis,
    source_spectrum_h_available)
from ..core.original_envelope_shared_menu import (
    SOURCE_ORIGINAL_FILTER_CAPTIONS,ORIGINAL_COLUMN_BREAK_TAG,
    source_original_envelope_menu)


def test_20261123_all_original_filter_caption_tags_and_columns():
    names=SOURCE_ORIGINAL_FILTER_CAPTIONS
    assert len(names)==32
    assert names[0]=="Без фильтра"
    assert names[1:20]==(
        "1/3окт 25 кГц","1/3окт 20 кГц","1/3окт 16 кГц",
        "1/3окт 13 кГц","1/3окт 10 кГц","1/3окт 8000 Гц",
        "1/3окт 6300 Гц","1/3окт 5000 Гц","1/3окт 4000 Гц",
        "1/3окт 3150 Гц","1/3окт 2500 Гц","1/3окт 2000 Гц",
        "1/3окт 1600 Гц","1/3окт 1250 Гц","1/3окт 1000 Гц",
        "1/3окт 800 Гц","1/3окт 630 Гц","1/3окт 500 Гц",
        "1/3окт 400 Гц")
    assert names[20:26]==(
        "1окт 16 кГц","1окт 8000 Гц","1окт 4000 Гц",
        "1окт 2000 Гц","1окт 1000 Гц","1окт 500 Гц")
    assert names[26:]==(
        "2окт 13 кГц","2окт 6400 Гц","2окт 3200 Гц",
        "2окт 1600 Гц","2окт 800 Гц","2окт 400 Гц")
    items=source_original_envelope_menu(
        selected_tag=0,sample_rate_hz=65536,local_profile_available=False)
    assert ORIGINAL_COLUMN_BREAK_TAG==20
    assert [row["caption"] for row in items]==list(names)
    assert [row["source_menu_column"] for row in items]==[0]*20+[1]*12


def test_20261123_mode_units_exact_six_y_captions_with_original_frange_bases():
    assert [source_spectrum_y_unit(mode) for mode in range(4)]==[
        "дБ","м/с²","мм/с","мкм"]
    assert DB_Y_RANGES==(150,100,75,50,25,10)
    assert PHYSICAL_Y_DIVISORS==(1,10,100,1000,10000,100000)
    for mode,basis,labels in (
        (1,1000,("1000 м/с²","100 м/с²","10 м/с²","1 м/с²",
                 "0,1 м/с²","0,01 м/с²")),
        (2,10000,("10000 мм/с","1000 мм/с","100 мм/с","10 мм/с",
                  "1 мм/с","0,1 мм/с")),
        (3,100000,("100000 мкм","10000 мкм","1000 мкм","100 мкм",
                   "10 мкм","1 мкм")),
    ):
        assert tuple(original_physical_y_caption(mode,basis/divisor)
                     for divisor in PHYSICAL_Y_DIVISORS)==labels
    for mode in (-1,4,True,None,"1"):
        with pytest.raises(ValueError):
            source_spectrum_y_unit(mode)


def test_20261123_fft_and_horizontal_menu_exact_order_and_data_gate():
    assert FFT_WINDOW_SAMPLES==(262144,131072,65536,32768,16384,8192)
    assert tuple(original_fft_resolution_caption(n,65536)
                 for n in FFT_WINDOW_SAMPLES)==(
                    "1/4 Гц/лин","1/2 Гц/лин","1 Гц/лин",
                    "2 Гц/лин","4 Гц/лин","8 Гц/лин")
    assert HORIZONTAL_HZ==(25600,12800,6400,3200,1600,800,400,200,100,50)
    assert source_spectrum_h_available(25600)==(True,)*10
    assert source_spectrum_h_available(3200)==(
        False,False,False,True,True,True,True,True,True,True)
    assert source_spectrum_h_available(200)==(
        False,False,False,False,False,False,False,True,True,True)
    assert source_spectrum_h_available(40)==(False,)*10
    for bad in (0,-1,True,float('inf'),float('nan'),"3200"):
        with pytest.raises(ValueError):
            source_spectrum_h_available(bad)


def test_20261123_uncalibrated_Y_nice_local_peak_fit_and_strict_provenance():
    for peak,basis in ((.1,200.),(.001,2.),(1.,2000.)):
        got=research_spectrum_vscale_auto_basis(peak)
        assert got==basis
        assert got/1000>=peak*1.2-1e-12
    for bad in (-1,True,"5",float('inf'),float('nan')):
        with pytest.raises(ValueError):
            research_spectrum_vscale_auto_basis(bad)
