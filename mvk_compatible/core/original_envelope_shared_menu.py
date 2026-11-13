"""Original MVKView shared ADC/Spectrum 32-item envelope popup contract.

Source PRIVATE (operator owned; not distributed):
  mvkform.dfm bAdcEnvelopeType / bSpecEnvelopeType both point at
  popEnvelopeType with Style=bsSplitButton, OnClick=bAnyDropDownClick.
  _Unit128:0084587D..0084594B builds 32 RadioItem Tag=0..31, with
  an item-column break at original Tag 20.
  _Unit128:0084B274 sets both TButton.Tags AND both Captions together.
  _Unit128:0084B2C8 invalidates both graph series and repaints.
  _Unit128:0084BAF9..0084BB2C enables codes only if their source
  target-rate table <= active channel sample rate.
  _Unit128:0084EAF4 pops up FDropDownMenu on main button click.

No Pascal, DFM, IDP FIR coefficients, private samples or device calls
are embedded. A validated local operator IDP is required to compute FIR.
"""
from __future__ import annotations

from .envelope_idr_candidate import ENVELOPE_RATES

SOURCE = "MVKVIEW_ORIGINAL_SHARED_ENVELOPE_MENU_STAGE111Z31CB"
COUNT = 32
ORIGINAL_COLUMN_BREAK_TAG = 20
ORIGINAL_MENU_COLUMN_COUNT = 2
ORIGINAL_MENU_FIRST_COLUMN_ROWS = 20
# Source strings (NOT FIR coefficients): verified from the exact UTF-16
# application-image strings referenced by the 31 pointers of the user's
# local mvkview.idp at 0x008CD900. Original Pascal _Unit128:008458C4
# uses these direct strings for Tag1..31. Tag0 invokes a TLanguage key
# 'xNoEnvelope'; the local translation dictionary is not verified.
# Do not commit/source-share the IDP image or any memory offsets/banks.
SOURCE_ORIGINAL_FILTER_CAPTIONS = (
    "Без фильтра",  # Tag0: honest localized fallback only
    "1/3окт 25 кГц", "1/3окт 20 кГц", "1/3окт 16 кГц",
    "1/3окт 13 кГц", "1/3окт 10 кГц", "1/3окт 8000 Гц",
    "1/3окт 6300 Гц", "1/3окт 5000 Гц", "1/3окт 4000 Гц",
    "1/3окт 3150 Гц", "1/3окт 2500 Гц", "1/3окт 2000 Гц",
    "1/3окт 1600 Гц", "1/3окт 1250 Гц", "1/3окт 1000 Гц",
    "1/3окт 800 Гц", "1/3окт 630 Гц", "1/3окт 500 Гц",
    "1/3окт 400 Гц",
    "1окт 16 кГц", "1окт 8000 Гц", "1окт 4000 Гц",
    "1окт 2000 Гц", "1окт 1000 Гц", "1окт 500 Гц",
    "2окт 13 кГц", "2окт 6400 Гц", "2окт 3200 Гц",
    "2окт 1600 Гц", "2окт 800 Гц", "2окт 400 Гц",
)


def source_original_envelope_caption(tag:int) -> str:
    """31 source-exact menu captions; Tag0 uses untranslated fallback."""
    _tag(tag)
    if len(SOURCE_ORIGINAL_FILTER_CAPTIONS) != COUNT:
        raise ValueError("Source original 32-caption filter table is corrupted")
    return SOURCE_ORIGINAL_FILTER_CAPTIONS[tag]


def _tag(value: int) -> int:
    if type(value) is not int or not 0 <= value < COUNT:
        raise ValueError("Original popEnvelopeType Tag must be 0..31")
    return value


def _rate(value: int | float | None) -> int | None:
    if value is None:
        return None
    if (type(value) not in (float,int) or not 1 <= value <= 10_000_000
            or int(value) != value):
        raise ValueError("Original envelope source sample rate must be integer Hz")
    return int(value)


def source_original_envelope_menu(*, selected_tag: int,
                                  sample_rate_hz: int | float | None,
                                  local_profile_available: bool) -> tuple[dict,...]:
    """Source-checked radio Tag and sample-rate gates for BOTH original pages.

    The source's static target-rate gate and UI's local-IDP requirement
    are reported separately. None rate means selection for a future
    session can be prepared, not that the original rate gate is proven.
    """
    selected = _tag(selected_tag)
    rate = _rate(sample_rate_hz)
    if type(local_profile_available) is not bool:
        raise ValueError("Local private envelope profile gate must be boolean")
    if len(ENVELOPE_RATES)!=COUNT:
        raise ValueError("Original source envelope table lost Tag0..31")
    items = []
    for tag, fs in enumerate(ENVELOPE_RATES):
        if type(fs) is not int or not 1 <= fs <= 65536:
            raise ValueError("Original envelope target-rate table corrupted")
        native_allowed = tag == 0 or rate is None or fs <= rate
        usable = (tag == 0 or (local_profile_available and native_allowed))
        items.append({
            "source": SOURCE,
            "tag": tag,
            "original_shared_popup_name": "popEnvelopeType",
            "source_radio_item": True,
            "source_column_break_before": tag == ORIGINAL_COLUMN_BREAK_TAG,
            "source_menu_columns": ORIGINAL_MENU_COLUMN_COUNT,
            "source_menu_column": 0 if tag < ORIGINAL_COLUMN_BREAK_TAG else 1,
            "source_menu_row": tag if tag < ORIGINAL_COLUMN_BREAK_TAG else tag - ORIGINAL_COLUMN_BREAK_TAG,
            "source_menu_column_size": (ORIGINAL_MENU_FIRST_COLUMN_ROWS if tag < ORIGINAL_COLUMN_BREAK_TAG else COUNT-ORIGINAL_COLUMN_BREAK_TAG),
            "source_target_rate_hz": fs if tag else None,
            "original_sample_rate_gate_pass": native_allowed,
            "source_gate_deferred_without_selected_channel": rate is None,
            "local_private_fir_profile_present": local_profile_available,
            "qt_selectable_without_fabricated_fir": usable,
            "checked": tag == selected,
            # Pascal tag0 is a TLanguage lookup not available from the
            # original IDP; the other 31 strings ARE exact static strings
            # in the checked operator-supplied original image.
            "caption": source_original_envelope_caption(tag),
            "original_static_caption_verified": tag != 0,
            "original_translation_caption_verified": False,
            "source_ui_caption_from_original_idp_static": tag != 0,
            "original_win32_canvas_parity_verified": False,
        })
    return tuple(items)


def source_original_envelope_selection(*, selected_tag: int, new_tag: int,
                                       sample_rate_hz: int | float | None,
                                       local_profile_available: bool) -> dict:
    """An explicit popup action atomically targets both source TButtons.

    This intentionally does not carry/compute a waveform or spectrum:
    callers must recompute their existing independent Core pipelines,
    fail-closed on insufficient archive FIR history, and retain source
    BIN/FFT SHA evidence. Loading a profile is NOT a selection event.
    """
    selected = _tag(selected_tag)
    new = _tag(new_tag)
    choices = source_original_envelope_menu(
        selected_tag=selected,sample_rate_hz=sample_rate_hz,
        local_profile_available=local_profile_available)
    entry = choices[new]
    if not entry["qt_selectable_without_fabricated_fir"]:
        if new and not local_profile_available:
            raise ValueError("Нужен локальный исходный IDP для FIR")
        raise ValueError(
            f"EnvelopeCode{new} требует Fs не менее "
            f"{entry['source_target_rate_hz']} Гц")
    return {
        "source":SOURCE,
        "previous_tag":selected,
        "selected_tag":new,
        "adc_tag":new,
        "spectrum_tag":new,
        "source_radio_item_checked":True,
        "source_target_rate_hz":entry["source_target_rate_hz"],
        "source_filter_caption":entry["caption"],
        "source_filter_static_caption_verified":entry["original_static_caption_verified"],
        "source_filter_menu_column":entry["source_menu_column"],
        "source_filter_menu_row":entry["source_menu_row"],
        "original_filter_enabled":new>0,
        "requires_real_fir_coefficients":new>0,
        "source_both_screen_series_invalidated":True,
        "repaint_adc_and_spectrum_even_if_hidden":True,
        "source_zero_removes_fir_without_padding":new==0,
        "source_fft_values_should_not_be_mutated_by_menu":True,
        "source_f_range_not_inferred_from_menu":True,
        "original_win32_runtime_parity_verified":False,
    }


def source_original_envelope_rebind(*, selected_tag:int,
                                    sample_rate_hz:int|float|None,
                                    local_profile_available:bool)->dict:
    """The source falls back to Tag0 if current envelope rate is disabled.

    _Unit128:0084BAF9..0084BB43 compares the target-rate table with
    the currently selected channel Fs; when a selected radio entry
    becomes disabled it calls sub_0084B274(Tag0). This must be done
    BEFORE an unrelated channel or file's FFT is rendered.
    """
    old=_tag(selected_tag)
    items=source_original_envelope_menu(
        selected_tag=old,sample_rate_hz=sample_rate_hz,
        local_profile_available=local_profile_available)
    current=items[old]
    selected=old if current['qt_selectable_without_fabricated_fir'] else 0
    return {
        "source":SOURCE,
        "old_tag":old,
        "selected_tag":selected,
        "adc_tag":selected,
        "spectrum_tag":selected,
        "reset_to_zero":old!=selected,
        "original_sample_rate_disabled_selected_tag":(
            bool(old and not current['original_sample_rate_gate_pass'])),
        "qt_missing_private_idp_disabled_selected_tag":(
            bool(old and not current['local_private_fir_profile_present'])),
        "source_filter_must_be_recomputed":old!=selected,
        "source_both_screen_series_invalidated":old!=selected,
        "does_not_modify_any_source_samples_or_fft":True,
        "original_win32_runtime_parity_verified":False,
    }
