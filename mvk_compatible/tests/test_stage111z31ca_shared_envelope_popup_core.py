"""CA: full source-shared popEnvelopeType Core contract.

All original source references are derivative constants only; no original
DFM/PAS/IDP FIR bank, private BIN, or hardware connection is distributed.
"""
from __future__ import annotations

import pytest

from ..core.envelope_idr_candidate import ENVELOPE_RATES
from ..core.original_envelope_shared_menu import (
    source_original_envelope_menu,source_original_envelope_selection,
    source_original_envelope_rebind,
)


def test_source_32_radio_items_one_shared_popup_and_source_fs_gating():
    choices=source_original_envelope_menu(
        selected_tag=0,sample_rate_hz=8192,local_profile_available=True)
    assert len(choices)==32
    assert [x['tag'] for x in choices]==list(range(32))
    assert all(x['original_shared_popup_name']=='popEnvelopeType' for x in choices)
    assert all(x['source_radio_item'] for x in choices)
    assert [x['tag'] for x in choices if x['source_column_break_before']]==[20]
    assert [x['tag'] for x in choices if x['checked']]==[0]
    assert choices[0]['caption']=='Без фильтра'
    assert choices[0]['qt_selectable_without_fabricated_fir']
    assert choices[20]['source_target_rate_hz']==65536
    assert not choices[20]['original_sample_rate_gate_pass']
    assert not choices[20]['qt_selectable_without_fabricated_fir']
    assert choices[11]['source_target_rate_hz']==ENVELOPE_RATES[11]==8192
    assert choices[11]['original_sample_rate_gate_pass']
    assert choices[11]['qt_selectable_without_fabricated_fir']
    assert not choices[11]['original_translation_caption_verified']
    assert not choices[11]['original_win32_canvas_parity_verified']


def test_source_fir_requires_real_local_idp_and_never_fabricates():
    no_idp=source_original_envelope_menu(
        selected_tag=0,sample_rate_hz=65536,local_profile_available=False)
    assert no_idp[0]['qt_selectable_without_fabricated_fir']
    assert all(not x['qt_selectable_without_fabricated_fir'] for x in no_idp[1:])
    with pytest.raises(ValueError,match='IDP'):
        source_original_envelope_selection(
            selected_tag=0,new_tag=20,sample_rate_hz=65536,
            local_profile_available=False)
    with pytest.raises(ValueError,match='Fs'):
        source_original_envelope_selection(
            selected_tag=0,new_tag=20,sample_rate_hz=8192,
            local_profile_available=True)
    pending=source_original_envelope_menu(
        selected_tag=0,sample_rate_hz=None,local_profile_available=True)
    assert pending[20]['qt_selectable_without_fabricated_fir']
    assert pending[20]['source_gate_deferred_without_selected_channel']


def test_popup_is_atomic_two_page_tag_transition_not_numeric_fft_mutation():
    receipt=source_original_envelope_selection(
        selected_tag=0,new_tag=20,sample_rate_hz=65536,
        local_profile_available=True)
    assert receipt['adc_tag']==receipt['spectrum_tag']==20
    assert receipt['source_both_screen_series_invalidated']
    assert receipt['source_fft_values_should_not_be_mutated_by_menu']
    assert receipt['requires_real_fir_coefficients']
    assert not receipt['original_win32_runtime_parity_verified']
    zero=source_original_envelope_selection(
        selected_tag=20,new_tag=0,sample_rate_hz=65536,
        local_profile_available=True)
    assert zero['adc_tag']==zero['spectrum_tag']==0
    assert zero['source_zero_removes_fir_without_padding']
    assert not zero['original_filter_enabled']
    for bad in (-1,32,True,2.5,'20'):
        with pytest.raises(ValueError,match='Tag'):
            source_original_envelope_menu(
                selected_tag=bad,sample_rate_hz=65536,
                local_profile_available=True)
    for bad_rate in (False,0,-1,65536.5,float('nan'),float('inf')):
        with pytest.raises(ValueError,match='rate'):
            source_original_envelope_menu(
                selected_tag=0,sample_rate_hz=bad_rate,
                local_profile_available=True)


def test_original_source_fs_change_auto_resets_unsupported_selected_tag():
    allowed=source_original_envelope_rebind(
        selected_tag=20,sample_rate_hz=65536,local_profile_available=True)
    assert allowed['selected_tag']==20
    assert not allowed['reset_to_zero']
    # Original _Unit128:0084BB2E calls Tag0 when rate gate disables
    # the previously selected filter during a channel/file change.
    drop=source_original_envelope_rebind(
        selected_tag=20,sample_rate_hz=8192,local_profile_available=True)
    assert drop['old_tag']==20
    assert drop['selected_tag']==drop['adc_tag']==drop['spectrum_tag']==0
    assert drop['original_sample_rate_disabled_selected_tag']
    assert drop['reset_to_zero']
    assert drop['source_both_screen_series_invalidated']
    assert drop['does_not_modify_any_source_samples_or_fft']
    no_coefficients=source_original_envelope_rebind(
        selected_tag=20,sample_rate_hz=65536,local_profile_available=False)
    assert no_coefficients['reset_to_zero']
    assert no_coefficients['qt_missing_private_idp_disabled_selected_tag']
    zero=source_original_envelope_rebind(
        selected_tag=0,sample_rate_hz=8192,local_profile_available=False)
    assert zero['selected_tag']==0 and not zero['reset_to_zero']
