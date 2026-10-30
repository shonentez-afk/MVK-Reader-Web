"""Stage111S: source-derived Delphi spectrum scrollbar mechanics, offline.

Private original _Unit128:0084C3AC..0084C4BB horizontal range/page,
0084C5AC..0084C748 vertical range/page, 0084C770..0084C840
TQGrapher ScrLeft/Width/Bottom/Height. Original H full range starts at
gvar_008D3428=0x6400 (25600); complete H/V/FFT source DWORD tables
were recovered privately at Stage111S. Only explicit source menu choices
may be regarded as source-verified. Qt/runtime original parity is separate.
Qt scrollbar maximum is effective max position, unlike Delphi FMax=full-1
with PageSize reducing the scrollable end.
No instrument or original code is redistributed.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numbers
import numpy as np
from .mvk_original_scale_tables_idr_candidate import HORIZONTAL_HZ

SOURCE='APP_DERIVED_DELPHI_SPECTRUM_SCROLLBARS_IDR_CANDIDATE'
DELPHI_H_FIRST_MENU_SCALE_HZ=0x6400
MAX_NATIVE_RANGE=2_000_000


def _integer(name,value,*,low=0):
    if (not isinstance(value,numbers.Integral) or isinstance(value,bool)
            or not low<=int(value)<=MAX_NATIVE_RANGE):
        raise ValueError(name+' must be a bounded original integer')
    return int(value)


def _native_float(name,value):
    if (isinstance(value,bool) or not isinstance(value,numbers.Real)
            or not math.isfinite(float(value))):
        raise ValueError(name+' must be finite')
    v=float(np.float32(float(value)))
    if not math.isfinite(v):
        raise ValueError(name+' cannot overflow original Single')
    return v


@dataclass(frozen=True)
class NativeScrollContract:
    axis: str
    full_size: int
    page_size: int
    position: int
    source_menu_preset_verified: bool=False

    def __post_init__(self):
        if self.axis not in ('horizontal','vertical'):
            raise ValueError('Only original H/V scroll axes supported')
        full=_integer('full_size',self.full_size,low=1)
        page=_integer('page_size',self.page_size,low=1)
        pos=_integer('position',self.position)
        if page>full or pos>full-page:
            raise ValueError('Native position/page outside source range')
        if not isinstance(self.source_menu_preset_verified,bool):
            raise ValueError('Preset provenance flag must be boolean')
        if self.source_menu_preset_verified:
            if (self.axis!='horizontal'
                    or full!=DELPHI_H_FIRST_MENU_SCALE_HZ
                    or page not in HORIZONTAL_HZ):
                raise ValueError('Unknown original menu presets are not verified')

    def view(self)->dict:
        """Delphi FMax=full-1; Qt maximum=full-page."""
        visible=self.page_size<self.full_size
        return {
            'source':SOURCE,'axis':self.axis,
            'source_full_size':self.full_size,
            'delphi_max':self.full_size-1,
            'delphi_page_size':self.page_size,
            'delphi_position':self.position,
            'delphi_small_change':(max(1,self.page_size//10) if visible else 1),
            'delphi_large_change':self.page_size,
            'delphi_visible':visible,
            'qt_minimum':0,
            'qt_maximum':self.full_size-self.page_size,
            'qt_page_step':self.page_size,
            'qt_single_step':max(1,self.page_size//10),
            'source_menu_preset_verified':self.source_menu_preset_verified,
            'runtime_delphi_vcl_scrollbar_parity_verified':False,
        }


def rescale_scroll(old:NativeScrollContract,*,selected_page:int,
                   vertical:bool=False)->NativeScrollContract:
    """Source original menu scaling; H holds position, V bottom-aligns.

    H 0084C494..C4AD: min(oldpos, full-newpage).
    V 0084C71A..C73A: min(oldpos+oldpage-newpage, full-newpage).
    """
    if not isinstance(old,NativeScrollContract):
        raise ValueError('Old native scroll contract required')
    if vertical!=(old.axis=='vertical'):
        raise ValueError('Rescale direction does not match axis')
    page=_integer('selected_page',selected_page,low=1)
    if page>old.full_size:
        raise ValueError('Page size larger than full range')
    if page==old.full_size:
        pos=0
    elif vertical:
        pos=max(0,min(old.full_size-page,old.position+old.page_size-page))
    else:
        pos=min(old.full_size-page,old.position)
    return NativeScrollContract(old.axis,old.full_size,page,pos)


def source_spectrum_h_scr(position:int,page:int,full:int)->dict:
    """Source _Unit128:0084C811..C840, no 0..1000 normalization."""
    contract=NativeScrollContract('horizontal',full,page,position)
    width=_native_float('ScrWidth',page)
    left=_native_float('ScrLeft',(float(position)*width)/page)
    return {**contract.view(),
            'scr_width_single':width,'scr_left_single':left,
            'original_delphi_x87_parity_verified':False,
            'original_menu_scale_values_verified':False}


def source_spectrum_v_scr(position:int,page:int,full:int,*,
                          db_mode:bool,graph_default_v_scale:float,
                          scale_divisor:int=1)->dict:
    """Original dB/other unit vertical ScrollBottom branches.

    dB: ScrHeight=PageSize; ScrBottom=-Height-Pos*Height/Page.
    Other: ScrHeight=GraphDefaultVScale/divisor;
    ScrBottom=(GraphDefaultVScale-Height)-Pos*Height/Page.
    The Intel x87 FSUBRP ST(1),ST(0) subtracts the original ST(1)
    from the new ST(0), not the reverse. Vertical Position increases
    toward lower/negative Y in both original branches.
    Source vertical menu tables now recovered (Stage111S), but this
    low-level function accepts caller-supplied full/page and does NOT
    authenticate their provenance or the original GraphDefaultVScale.
    """
    if not isinstance(db_mode,bool):
        raise ValueError('dB mode must be explicit')
    contract=NativeScrollContract('vertical',full,page,position)
    default=_native_float('GraphDefaultVScale',graph_default_v_scale)
    if default<=0:raise ValueError('GraphDefaultVScale must be positive')
    divisor=_integer('scale_divisor',scale_divisor,low=1)
    height=_native_float('ScrHeight',page if db_mode else float(default)/divisor)
    position_term=float(position)*height/page
    bottom=_native_float('ScrBottom',
        (-height-position_term) if db_mode else ((default-height)-position_term))
    return {**contract.view(),'db_mode':db_mode,
            'scr_height_single':height,'scr_bottom_single':bottom,
            'original_vertical_menu_values_verified':False,
            'original_delphi_x87_parity_verified':False}
