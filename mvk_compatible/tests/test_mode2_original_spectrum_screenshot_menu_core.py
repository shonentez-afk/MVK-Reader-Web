
"""Screenshot-grounded source menu contracts, synthetic, no original pixels."""
import pytest
from mvk_compatible.core.mvk_original_scale_tables_idr_candidate import (
    FFT_WINDOW_SAMPLES,HORIZONTAL_HZ,PHYSICAL_Y_DIVISORS,
    original_fft_resolution_caption,original_physical_y_caption)
from mvk_compatible.core.original_envelope_shared_menu import source_original_envelope_menu


def test_screenshot_20261021_six_fft_resolution_rows():
    assert FFT_WINDOW_SAMPLES==(262144,131072,65536,32768,16384,8192)
    assert tuple(original_fft_resolution_caption(n,65536) for n in FFT_WINDOW_SAMPLES)==(
        "1/4 Гц/лин","1/2 Гц/лин","1 Гц/лин","2 Гц/лин","4 Гц/лин","8 Гц/лин")
    for n in (1024,4096):
        with pytest.raises(ValueError):
            original_fft_resolution_caption(n,65536)


def test_screenshot_ten_x_ranges_and_six_velocity_units():
    assert HORIZONTAL_HZ==(25600,12800,6400,3200,1600,800,400,200,100,50)
    assert PHYSICAL_Y_DIVISORS==(1,10,100,1000,10000,100000)
    assert tuple(original_physical_y_caption(2,10000/d) for d in PHYSICAL_Y_DIVISORS)==(
        "10000 мм/с","1000 мм/с","100 мм/с","10 мм/с","1 мм/с","0,1 мм/с")
    assert original_physical_y_caption(1,.125)=="0,125 м/с²"
    assert original_physical_y_caption(3,100)=="100 мкм"
    with pytest.raises(ValueError):original_physical_y_caption(0,10)


def test_screenshot_filter_two_column_menu_tag_and_captions():
    items=source_original_envelope_menu(
        selected_tag=0,sample_rate_hz=65536,local_profile_available=False)
    assert len(items)==32
    assert [x["source_menu_column"] for x in items]==[0]*20+[1]*12
    assert [x["source_menu_row"] for x in items]==list(range(20))+list(range(12))
    assert items[0]["caption"]=="Без фильтра"
    assert items[1]["caption"]=="1/3окт 25 кГц"
    assert items[20]["caption"]=="1окт 16 кГц"
    assert items[26]["caption"]=="2окт 13 кГц"
