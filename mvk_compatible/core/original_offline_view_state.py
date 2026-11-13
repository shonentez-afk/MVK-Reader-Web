"""Stage111Z31BB: source-derived, offline-only MVKView view/menu state.

The original Delphi _Unit128.pas establishes ten horizontal 25600..50 Hz
scale items, FMax=25600-1 with a page sized by the selected menu item,
mode-dependent vertical pages, six FFT sizes, and seven main DFM pages.
A source TQGrapher SERIES END is NOT the full original horizontal menu
AXIS END. In the operator Code20/LOG0 reference, these differ by 2x.

No original executable, IDP/PAS/DFM bytes, device commands, or private
arrays embedded. This is a validated transition contract, not proof of
original runtime state parity or completeness of hardware operation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import numbers

from .mvk_original_scale_tables_idr_candidate import (
    FFT_WINDOW_SAMPLES, HORIZONTAL_HZ, original_v_scale_options,
)
from .mvk_spectrum_menu_runtime_idr_candidate import (
    source_default_vertical_tag, source_vertical_selection,
)
from .tqgrapher_display_idr_candidate import spectrum_display_contract
from .tqgrapher_spectrum_scroll_idr_candidate import (
    NativeScrollContract, rescale_scroll,
)
from .original_ui_form_contract import ORIGINAL_ROOT_PAGES
from .original_pagestatus_source import MODE_NAMES

SOURCE="SOURCE_DERIVED_ORIGINAL_MVKVIEW_OFFLINE_VIEW_STATE_STAGE111Z31BB"
PAGES=tuple(p.object_name for p in ORIGINAL_ROOT_PAGES)
DEFAULT_HZ=HORIZONTAL_HZ[0]
SAFE_TRANSITIONS=frozenset((
    "select_page","select_channel","select_status_tab",
    "select_spectrum_mode","select_spectrum_hscale",
    "scroll_spectrum_horizontal","select_spectrum_vscale",
    "scroll_spectrum_vertical","select_spectrum_fft_lines",
    "select_config_tab","select_file_action_tab",
    "select_calibration_result_tab",
))
UNSAFE_OR_UNVERIFIED=frozenset((
    "device_connect","device_config_download","device_config_upload",
    "device_config_reset","device_calibration_start",
    "device_calibration_save","device_calibration_generate",
    "device_firmware_write","device_register_write",
    "device_rate_change","device_command_send",
))


def _bounded_int(name,value,minimum,maximum):
    if (isinstance(value,bool) or not isinstance(value,numbers.Integral)
            or not minimum<=int(value)<=maximum):
        raise ValueError(name+" must be an original bounded integer")
    return int(value)


def original_reference_axis_contract(n_fft:int,fs_out_hz:int)->dict:
    """Source original menu full 25600 vs separate displayed DataSize.

    _Unit128:0084B536 (10 source H menu values) and 0084C3CD..C43C
    (full extent and invisible full-range scrollbar), while
    _Unit128:00848292..2CE separately truncates the TQGrapher series.
    """
    if (isinstance(fs_out_hz,bool)
            or not isinstance(fs_out_hz,numbers.Integral)
            or int(fs_out_hz)<=0):
        raise ValueError("Original output sample rate must be integer Hz")
    sample=spectrum_display_contract(n_fft,float(fs_out_hz))
    cutoff=sample["grapher_axis_end_frequency_hz"]
    visible=min(DEFAULT_HZ,cutoff)
    return {
        "source":SOURCE,
        "full_horizontal_menu_axis_end_hz":DEFAULT_HZ,
        "hscale_menu_tag":0,
        "delphi_scrollbar_visible":False,
        "tqgrapher_raw_power_bins":sample["full_fft_power_bins"],
        "tqgrapher_display_series_bins":sample["grapher_series_bins"],
        "tqgrapher_display_series_end_hz":cutoff,
        "visible_source_series_end_hz":visible,
        "empty_right_frequency_span_hz":max(0.,float(DEFAULT_HZ)-cutoff),
        "axis_end_is_not_derived_from_series_end":True,
        "fft_samples_or_bins_modified":False,
        "original_runtime_display_mode_verified":False,
    }


@dataclass(frozen=True)
class OriginalOfflineView:
    """Portable state for safe original controls; Qt is an independent client."""
    page: str = "PageStart"
    channel: int = 1
    status_tab: int = 0
    spectrum_mode: int = 0
    hscale_tag: int = 0
    hscroll_position: int = 0
    vscale_tag: int = 0
    vscroll_position: int = 0
    fft_lines_tag: int = 0
    config_tab: int = 0
    file_action_tab: int = 0
    calibration_result_tab: int = 0

    def __post_init__(self):
        if self.page not in PAGES:
            raise ValueError("Not an original DFM root page")
        _bounded_int("channel",self.channel,1,8)
        _bounded_int("status_tab",self.status_tab,0,len(MODE_NAMES)-1)
        _bounded_int("spectrum_mode",self.spectrum_mode,0,3)
        _bounded_int("hscale_tag",self.hscale_tag,0,len(HORIZONTAL_HZ)-1)
        _bounded_int("vscale_tag",self.vscale_tag,0,5)
        _bounded_int("fft_lines_tag",self.fft_lines_tag,0,len(FFT_WINDOW_SAMPLES)-1)
        _bounded_int("tcConfig",self.config_tab,0,1)
        _bounded_int("tcFileActions",self.file_action_tab,0,1)
        _bounded_int("tcCalibResult",self.calibration_result_tab,0,1)
        native=NativeScrollContract(
            "horizontal",DEFAULT_HZ,HORIZONTAL_HZ[self.hscale_tag],
            _bounded_int("hscroll_position",self.hscroll_position,0,DEFAULT_HZ),
            source_menu_preset_verified=True)
        y=source_vertical_selection(
            self.spectrum_mode,self.vscale_tag,
            old_position=0 if self.vscroll_position==0 else self.vscroll_position,
            old_tag=self.vscale_tag)
        if not 0 <= self.vscroll_position <= y["qt_maximum"]:
            raise ValueError("Original V scrollbar position outside scale page")
        if self.spectrum_mode==0 and self.vscale_tag not in range(6):
            raise ValueError("Invalid source dB menu tag")
        if native.position>native.full_size-native.page_size:
            raise ValueError("Original horizontal scrollbar position outside page")

    @classmethod
    def initial(cls):
        return cls()

    def transition(self,action:str,selection)->"OriginalOfflineView":
        """A strict allowlist. Never reinterpret device commands as UI actions."""
        if not isinstance(action,str) or action not in SAFE_TRANSITIONS:
            raise PermissionError(
                "Unsupported or unsafe original view action: "+str(action))
        if action=="select_page":
            if not isinstance(selection,str) or selection not in PAGES:
                raise ValueError("Unknown source form page")
            return replace(self,page=selection)
        if action=="select_channel":
            return replace(self,channel=_bounded_int("channel",selection,1,8))
        if action=="select_status_tab":
            return replace(self,status_tab=_bounded_int(
                "status_tab",selection,0,len(MODE_NAMES)-1))
        if action=="select_spectrum_mode":
            mode=_bounded_int("mode",selection,0,3)
            return replace(self,spectrum_mode=mode,
                           vscale_tag=source_default_vertical_tag(mode),
                           vscroll_position=0)
        if action=="select_spectrum_hscale":
            tag=_bounded_int("H menu tag",selection,0,len(HORIZONTAL_HZ)-1)
            old=NativeScrollContract(
                "horizontal",DEFAULT_HZ,HORIZONTAL_HZ[self.hscale_tag],
                self.hscroll_position,source_menu_preset_verified=True)
            new=rescale_scroll(old,selected_page=HORIZONTAL_HZ[tag])
            return replace(self,hscale_tag=tag,hscroll_position=new.position)
        if action=="scroll_spectrum_horizontal":
            page=HORIZONTAL_HZ[self.hscale_tag]
            pos=_bounded_int("H scrollbar position",selection,0,DEFAULT_HZ-page)
            return replace(self,hscroll_position=pos)
        if action=="select_spectrum_vscale":
            tag=_bounded_int("V menu tag",selection,0,5)
            y=source_vertical_selection(
                self.spectrum_mode,tag,old_tag=self.vscale_tag,
                old_position=self.vscroll_position)
            return replace(self,vscale_tag=tag,
                           vscroll_position=y["delphi_position"])
        if action=="scroll_spectrum_vertical":
            bounds=source_vertical_selection(
                self.spectrum_mode,self.vscale_tag,
                old_tag=self.vscale_tag,old_position=self.vscroll_position)
            pos=_bounded_int(
                "V scrollbar position",selection,0,bounds["qt_maximum"])
            return replace(self,vscroll_position=pos)
        if action=="select_spectrum_fft_lines":
            tag=_bounded_int("FFT menu tag",selection,0,len(FFT_WINDOW_SAMPLES)-1)
            # Source control selects an FFT length; it does NOT itself prove
            # sufficient real archive history, DSP readiness or device state.
            return replace(self,fft_lines_tag=tag)
        if action=="select_config_tab":
            return replace(self,config_tab=_bounded_int(
                "tcConfig",selection,0,1))
        if action=="select_file_action_tab":
            return replace(self,file_action_tab=_bounded_int(
                "tcFileActions",selection,0,1))
        if action=="select_calibration_result_tab":
            return replace(self,calibration_result_tab=_bounded_int(
                "tcCalibResult",selection,0,1))
        raise AssertionError("Exhaustive source action dispatch")

    def snapshot(self,*,n_fft:int|None=None,fs_out_hz:int|None=None)->dict:
        h=NativeScrollContract(
            "horizontal",DEFAULT_HZ,HORIZONTAL_HZ[self.hscale_tag],
            self.hscroll_position,source_menu_preset_verified=True).view()
        v=source_vertical_selection(
            self.spectrum_mode,self.vscale_tag,
            old_tag=self.vscale_tag,old_position=self.vscroll_position)
        result={
            "source":SOURCE,
            "page":self.page,"channel":self.channel,
            "status_tab":self.status_tab,"spectrum_mode":self.spectrum_mode,
            "hscale_tag":self.hscale_tag,
            "hscale_hz":HORIZONTAL_HZ[self.hscale_tag],
            "hscroll_left_hz":self.hscroll_position,
            "hscroll_visible":h["delphi_visible"],
            "vscale_tag":self.vscale_tag,
            "vscroll_position":self.vscroll_position,
            "vscale_menu":original_v_scale_options(self.spectrum_mode)[
                self.vscale_tag]["caption"],
            "fft_lines_tag":self.fft_lines_tag,
            "config_tab":self.config_tab,
            "file_action_tab":self.file_action_tab,
            "calibration_result_tab":self.calibration_result_tab,
            "source_other_tab_changes_are_offline_view_only":True,
            "n_fft_requested":FFT_WINDOW_SAMPLES[self.fft_lines_tag],
            "hscroll":h,"vscroll":v,
            "only_offline_safe_view_transitions":True,
            "original_live_runtime_parity_verified":False,
            "device_command_issued":False,
            "real_archive_fft_history_verified":False,
        }
        if (n_fft is None)!=(fs_out_hz is None):
            raise ValueError("Both source FFT parameters must be supplied together")
        if n_fft is not None:
            result["reference"]=original_reference_axis_contract(n_fft,fs_out_hz)
        return result
