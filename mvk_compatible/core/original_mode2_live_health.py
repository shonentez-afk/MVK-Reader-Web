"""Source Mode2 measurement evidence and Win32 DFM 96-DPI geometry.

Source-only provenance: operator-supplied mvkview.idp; Projects.7z
_Unit125.pas, _Unit128.pas and mvkform.dfm. No source/private data
is bundled in this module. It never opens a socket or writes a command.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

SOURCE="ORIGINAL_IDP_00846D24_00807A98_DFM_96_DPI_MODE2_V1"
SOURCE_DFM_DPI=96
SOURCE_CLIENT_SIZE=(1008,929)
SOURCE_PANEL_HEIGHT=53
SOURCE_PN_MEASURE_CONTROLS_SIZE=(843,41)
SOURCE_PN_MEASURE_BUTTON_RECTS=(
    ("bFreezeUpdate",6,0,160,41),
    ("bSampleRate",172,0,160,41),
    ("bWriteTable",338,0,160,41),
    ("bWriteAdc",504,0,160,41),
    ("bWriteValues",670,0,160,41),
)
SOURCE_ROOT_TAB_HEIGHT=44
SOURCE_INTERNAL_TAB_HEIGHT=36
SOURCE_CHANNEL_KINDS=("ADC",)*8+("TACH",)*2
# Existing Native status schema reports silence as a quality warning
# after >4 seconds (not a claimed source Delphi TCP read timeout).
NATIVE_SILENCE_WARNING_S=4.0


@dataclass(frozen=True)
class LiveTransportHealth:
    """Validated passive recorder counters, distinct from MVK DSP status."""
    channels_observed:int
    invalid_frames:int
    sequence_gaps:int
    nonfinite_samples:int
    stream_silent:bool
    data_integrity_alert:bool
    packet_age_s:float|None
    received_operation_denied:bool=False

    def receipt(self):
        return {
            "source":SOURCE,
            "native_readonly_channels_observed":self.channels_observed,
            "original_storage_channels_source_count":10,
            "native_invalid_frames":self.invalid_frames,
            "native_sequence_gaps":self.sequence_gaps,
            "native_nonfinite_samples":self.nonfinite_samples,
            "native_packet_silence":self.stream_silent,
            "native_data_integrity_alert":self.data_integrity_alert,
            "native_operation_denied_received":self.received_operation_denied,
            "original_dsp_or_firmware_fields_inferred":False,
            "instrument_commands_issued":False,
        }


def live_transport_health(snapshot:dict|None)->LiveTransportHealth:
    """Project optional ten-channel metadata from a validated Native status.

    The caller validates schema, session identity and read-only transport.
    Older minimal synthetic transport receipts intentionally omit channels;
    missing counters are UNKNOWN, not evidence of all ten good channels.
    """
    if snapshot is None:
        return LiveTransportHealth(0,0,0,0,False,False,None)
    if not isinstance(snapshot,dict):
        raise ValueError("Native transport evidence must be a dictionary")
    raw_invalid=snapshot.get("invalid_frames",0)
    if type(raw_invalid) is not int or raw_invalid<0:
        raise ValueError("Invalid decoded-frame count")
    denied=snapshot.get("source_rx_denied_responses",0)
    if type(denied) is not int or denied<0:
        raise ValueError("Invalid passive source operation-denied counter")
    operation_denied=denied>0
    age=snapshot.get("seconds_since_last_packet")
    if age is not None and (
            type(age) not in (float,int) or
            not isfinite(age) or age<0):
        raise ValueError("Invalid packet-age evidence")
    silent=bool(
        snapshot.get("phase")=="RECORDING" and
        age is not None and age>NATIVE_SILENCE_WARNING_S)
    channels=snapshot.get("channels")
    if channels is None:
        return LiveTransportHealth(
            0,raw_invalid,0,0,silent,raw_invalid>0 or operation_denied,
            None if age is None else float(age),operation_denied)
    if not isinstance(channels,list) or len(channels)!=10:
        raise ValueError("Source Mode2 expects ten validated Native channels")
    gaps=0
    nonfinite=0
    for number,ch in enumerate(channels,1):
        if not isinstance(ch,dict) or (
                ch.get("channel")!=number or
                ch.get("type")!=SOURCE_CHANNEL_KINDS[number-1]):
            raise ValueError("Native channel order differs from source 8+2")
        for field in ("sequence_discontinuities","nonfinite_samples"):
            count=ch.get(field)
            if type(count) is not int or count<0:
                raise ValueError("Invalid channel stream counter")
        gaps+=ch["sequence_discontinuities"]
        nonfinite+=ch["nonfinite_samples"]
    return LiveTransportHealth(
        10,raw_invalid,gaps,nonfinite,silent,
        raw_invalid>0 or gaps>0 or nonfinite>0 or operation_denied,
        None if age is None else float(age),operation_denied)


def original_dpi_geometry(device_pixel_ratio:float)->dict:
    """DFM logical pixels are 96 DPI; Qt scales once into physical pixels.

    DPI=144 => scale 1.5. Never apply device ratio again to the
    QWidget fixed logical button rectangles. This is a geometry contract
    rather than a claim of Windows GDI glyph/pixel identity.
    """
    if (type(device_pixel_ratio) not in (float,int) or
            not isfinite(device_pixel_ratio) or
            not .75<=device_pixel_ratio<=4.0):
        raise ValueError("Qt devicePixelRatio must be finite and valid")
    ratio=float(device_pixel_ratio)
    px=lambda logical:int(logical*ratio+0.5)
    return {
        "source":SOURCE,
        "dfm_pixels_per_inch":SOURCE_DFM_DPI,
        "qt_device_pixel_ratio":ratio,
        "physical_dpi_candidate":int(SOURCE_DFM_DPI*ratio+0.5),
        "dfm_logical_client":SOURCE_CLIENT_SIZE,
        "qt_physical_client_reference":[px(x) for x in SOURCE_CLIENT_SIZE],
        "panel_logical_height":SOURCE_PANEL_HEIGHT,
        "panel_physical_height":px(SOURCE_PANEL_HEIGHT),
        "tab_logical_height":SOURCE_ROOT_TAB_HEIGHT,
        "tab_physical_height":px(SOURCE_ROOT_TAB_HEIGHT),
        "control_logical_size":SOURCE_PN_MEASURE_CONTROLS_SIZE,
        "button_logical_rects":[
            {"name":name,"rect":[x,y,w,h]}
            for name,x,y,w,h in SOURCE_PN_MEASURE_BUTTON_RECTS],
        "button_physical_rects":[
            {"name":name,"rect":[px(x),px(y),px(w),px(h)]}
            for name,x,y,w,h in SOURCE_PN_MEASURE_BUTTON_RECTS],
        "qt_layout_must_not_apply_second_scale":True,
        "original_gdi_font_raster_parity_verified":False,
    }
