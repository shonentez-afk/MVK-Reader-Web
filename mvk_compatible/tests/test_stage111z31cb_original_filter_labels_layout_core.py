"""CB: full exact 31 original static filter labels and VCL 20+12 geometry.

String-only UI data confirmed from private operator image; no original
IDP bytes/FIR coefficients in repository or in fixtures.
"""
from __future__ import annotations
import pytest

from ..core.original_envelope_shared_menu import (
    SOURCE_ORIGINAL_FILTER_CAPTIONS,source_original_envelope_caption,
    source_original_envelope_menu,source_original_envelope_selection,
    ORIGINAL_MENU_COLUMN_COUNT,ORIGINAL_MENU_FIRST_COLUMN_ROWS,
)


def test_original_idp_utf16_static_labels_are_preserved_at_all_32_source_tags():
    expected=(
        'Без фильтра',
        '1/3окт 25 кГц','1/3окт 20 кГц','1/3окт 16 кГц',
        '1/3окт 13 кГц','1/3окт 10 кГц','1/3окт 8000 Гц',
        '1/3окт 6300 Гц','1/3окт 5000 Гц','1/3окт 4000 Гц',
        '1/3окт 3150 Гц','1/3окт 2500 Гц','1/3окт 2000 Гц',
        '1/3окт 1600 Гц','1/3окт 1250 Гц','1/3окт 1000 Гц',
        '1/3окт 800 Гц','1/3окт 630 Гц','1/3окт 500 Гц',
        '1/3окт 400 Гц',
        '1окт 16 кГц','1окт 8000 Гц','1окт 4000 Гц',
        '1окт 2000 Гц','1окт 1000 Гц','1окт 500 Гц',
        '2окт 13 кГц','2окт 6400 Гц','2окт 3200 Гц',
        '2окт 1600 Гц','2окт 800 Гц','2окт 400 Гц',
    )
    assert SOURCE_ORIGINAL_FILTER_CAPTIONS==expected
    assert len(expected)==32
    for tag,name in enumerate(expected):
        assert source_original_envelope_caption(tag)==name
    for invalid in (-1,32,3.0,'2',True):
        with pytest.raises(ValueError,match="Tag"):
            source_original_envelope_caption(invalid)
    # Tag0 is not an IDP string: original Delphi localizes xNoEnvelope
    # at run time. A reasonable fallback may not claim literal Win32 text.
    entries=source_original_envelope_menu(
        selected_tag=20,sample_rate_hz=65536,local_profile_available=True)
    assert not entries[0]['original_static_caption_verified']
    assert not entries[0]['original_translation_caption_verified']
    assert all(x['original_static_caption_verified'] for x in entries[1:])
    assert not any(x['original_translation_caption_verified'] for x in entries)


def test_original_vcl_two_columns_tag0_to_19_and_tag20_to_31_full_radio_table():
    entries=source_original_envelope_menu(
        selected_tag=20,sample_rate_hz=65536,local_profile_available=True)
    assert ORIGINAL_MENU_COLUMN_COUNT==2
    assert ORIGINAL_MENU_FIRST_COLUMN_ROWS==20
    assert [x['source_menu_column'] for x in entries]==[0]*20+[1]*12
    assert [x['source_menu_row'] for x in entries]==list(range(20))+list(range(12))
    assert [x['tag'] for x in entries if x['source_column_break_before']]==[20]
    assert [x['tag'] for x in entries if x['checked']]==[20]
    assert [x['source_menu_column_size'] for x in entries]==[20]*20+[12]*12
    assert all(x['source_menu_columns']==2 for x in entries)
    assert [x['caption'] for x in entries]==list(SOURCE_ORIGINAL_FILTER_CAPTIONS)
    assert entries[20]['caption']=='1окт 16 кГц'
    # 16k is a frequency BAND LABEL, not the 65536 Hz downsampled
    # output.  A mislabeled output would deceive operators.
    assert entries[20]['source_target_rate_hz']==65536
    assert entries[31]['caption']=='2окт 400 Гц'
    assert entries[31]['source_target_rate_hz']==2048
    for x in entries:
        assert x['source_menu_column'] in (0,1)
        assert x['source_menu_row'] in range(20)
        assert x['original_shared_popup_name']=='popEnvelopeType'
    selected=source_original_envelope_selection(
        selected_tag=0,new_tag=20,sample_rate_hz=65536,
        local_profile_available=True)
    assert selected['source_filter_caption']=='1окт 16 кГц'
    assert selected['source_filter_menu_column']==1
    assert selected['source_filter_menu_row']==0
    assert selected['source_filter_static_caption_verified']


def test_original_band_caption_does_not_bypass_real_fir_rate_or_idp_gate():
    without=source_original_envelope_menu(
        selected_tag=0,sample_rate_hz=65536,local_profile_available=False)
    assert without[20]['caption']=='1окт 16 кГц'
    assert not without[20]['qt_selectable_without_fabricated_fir']
    with_idp=source_original_envelope_menu(
        selected_tag=0,sample_rate_hz=8192,local_profile_available=True)
    assert not with_idp[20]['qt_selectable_without_fabricated_fir']
    assert with_idp[11]['caption']=='1/3окт 2500 Гц'
    assert with_idp[11]['qt_selectable_without_fabricated_fir']
