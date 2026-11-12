"""Stage111T: actual source VCL spectrum Y page and source FFT archive guard.

Private _Unit128 0084C5AC..0084C748: db full=0x96 (150), physical
full=0x186A0 (100000), physical page=100000/divisor. Mode-change
0084C560..0084C595 selects tag0 for dB, tag3 for physical.
No original Pascal/DFM/IDP, real measurement, or instrument is included.
"""
from __future__ import annotations
from dataclasses import dataclass
import numbers

from .mvk_original_scale_tables_idr_candidate import (
    DB_Y_RANGES, PHYSICAL_Y_DIVISORS, FFT_WINDOW_SAMPLES,
    original_v_scale_options, validate_source_v_scale)
from .tqgrapher_spectrum_scroll_idr_candidate import (
    NativeScrollContract, rescale_scroll)

SOURCE='APP_DERIVED_SOURCE_SPECTRUM_MENU_RUNTIME_IDR_CANDIDATE'
DB_FULL=150
PHYSICAL_FULL=100000
RESEARCH_FFT_SIZES=(1024,4096)


def source_default_vertical_tag(mode:int)->int:
    """Original mSpecType1Click chooses first dB or fourth physical item."""
    original_v_scale_options(mode)
    return 0 if int(mode)==0 else 3


def source_vertical_page(mode:int,tag:int)->dict:
    """Original V maximum is not the same for dB and physical spectrum."""
    entry=validate_source_v_scale(mode,tag)
    db=int(mode)==0
    full=DB_FULL if db else PHYSICAL_FULL
    page=entry['db_range'] if db else full//entry['physical_divisor']
    if not 1<=page<=full:
        raise ValueError('Original source vertical PageSize is invalid')
    return dict(entry,source_runtime=SOURCE,full=full,page=page,
                vertical_scrollbar_source_units_verified=True,
                source_original_graph_default_vscale_verified=False,
                original_qt_y_registration_verified=False)


def source_vertical_selection(mode:int,tag:int,*,
                              old_tag:int|None=None,
                              old_position:int=0)->dict:
    """Source V menu preserves bottom anchored region across menu steps.

    If mode changed, caller must omit old_tag. The original Delphi
    mSpecType1Click itself resets tag to 0(dB)/3(physical).
    """
    chosen=source_vertical_page(mode,tag)
    if old_tag is None:
        contract=NativeScrollContract('vertical',chosen['full'],
                                       chosen['page'],0)
    else:
        old=source_vertical_page(mode,old_tag)
        old_contract=NativeScrollContract('vertical',old['full'],
                                        old['page'],old_position)
        contract=rescale_scroll(old_contract,
                                selected_page=chosen['page'],vertical=True)
    return dict(chosen,**contract.view(),
                source_menu_tag=tag,
                original_canvas_runtime_parity_verified=False)



def source_vertical_mode_transition(mode:int, *,
                                    former_tag:int=0,
                                    former_position:int=0)->dict:
    """Rebuild VCL Y scrollbar during original mSpecType1Click mode switch.

    Original _Unit128 0084C514..C597 replaces the V menu for the new mode,
    then invokes mSpecVScale1Click with default Tag 0 for dB or Tag 3 for
    physical spectra. The *old* bSpecVScale Tag/scroll Position are captured,
    but the old Tag is looked up in the NEW mode's DB/physical table.
    _Unit128 0084C71A..C73A anchors the bottom:
        min(full-newPage, oldPosition+oldPage-newPage).
    On 0 dB/Tag0 -> physical/Tag3 this is 99900, NOT 0. At position=0
    the original graph would show the very top of the physical axis.
    Missing old Tag on first initialization is DFM default Tag=0, Pos=0.
    """
    selected_tag=source_default_vertical_tag(mode)
    if (isinstance(former_tag,bool) or not isinstance(former_tag,numbers.Integral)
            or isinstance(former_position,bool)
            or not isinstance(former_position,numbers.Integral)
            or not 0<=int(former_position)<=PHYSICAL_FULL):
        raise ValueError('Original previous V Tag/Position must be bounded integers')
    old=source_vertical_page(mode,int(former_tag))
    chosen=source_vertical_page(mode,selected_tag)
    maxpos=chosen["full"]-chosen["page"]
    newpos=max(0,min(maxpos,
        int(former_position)+old["page"]-chosen["page"]))
    scroll=NativeScrollContract(
        "vertical",chosen["full"],chosen["page"],newpos)
    return dict(chosen,**scroll.view(),
                source_menu_tag=selected_tag,
                source_previous_menu_tag=int(former_tag),
                source_previous_scroll_position=int(former_position),
                source_mode_transition_bottom_anchored=True,
                original_canvas_runtime_parity_verified=False)

def fft_source_archive_gate(n_fft:int,total_samples:int,*,
                            end_sample:int|None=None,
                            required_input_samples:int|None=None)->dict:
    """Refuse missing real BIN history before any FFT or UI state mutation.

    end_sample is an *absolute* source sample index, not a padded buffer.
    For envelope, required_input_samples must come from the validated
    original FIR history planner; it can exceed n_fft.
    """
    if (isinstance(n_fft,bool) or not isinstance(n_fft,numbers.Integral)
            or int(n_fft) not in FFT_WINDOW_SAMPLES+RESEARCH_FFT_SIZES):
        raise ValueError('Unsupported FFT size: use source or explicit research size')
    if (isinstance(total_samples,bool) or not isinstance(total_samples,numbers.Integral)
            or not 0<=int(total_samples)<=100_000_000):
        raise ValueError('Invalid archive sample count')
    end=total_samples if end_sample is None else end_sample
    if (isinstance(end,bool) or not isinstance(end,numbers.Integral)
            or not 0<=int(end)<=int(total_samples)):
        raise ValueError('Invalid source archive endpoint')
    required=n_fft if required_input_samples is None else required_input_samples
    if (isinstance(required,bool) or not isinstance(required,numbers.Integral)
            or not n_fft<=int(required)<=100_000_000):
        raise ValueError('Invalid source FIR history requirement')
    permitted=int(end)>=int(required)
    return {
        'source':SOURCE,
        'n_fft':int(n_fft),
        'original_fft_menu_preset':int(n_fft) in FFT_WINDOW_SAMPLES,
        'research_fft_preset':int(n_fft) in RESEARCH_FFT_SIZES,
        'available_real_samples':int(total_samples),
        'archive_end_sample':int(end),
        'required_real_history_samples':int(required),
        'can_compute_without_padding':permitted,
        'reason':None if permitted else 'INSUFFICIENT_REAL_BIN_HISTORY',
        'original_archive_time_parity_verified':False,
        'original_fft_numeric_parity_verified':False,
    }
