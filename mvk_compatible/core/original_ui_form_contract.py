"""Original MVKView 1.0.47 Delphi form hierarchy recovered from user-owned IDR.

Evidence: user-provided Projects.7z (sha256:
3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363)
and mvkform.dfm (sha256:
192c0ebaf1bf722292a9b64497493a1de6af52a4bf8ffbe2ea28d0fe0b68c2d4),
which in turn was recovered from the original IDP (sha256:
77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438).

Delphi caption '$' is a runtime translation placeholder, NOT a literal UI
caption. Russian labels below are semantic navigation fallbacks, not claimed
bitwise original strings. Bitmap resources and the private DFM/IDP are NOT
embedded or checked in.

_Unit128.pas 0084709E..008470F8: at initial form setup the original selects
PageStart and hides the other six tabs; subsequent Page visibility depends
on original Mode/configuration. We retain seven discoverable OFFLINE pages in
Qt while preventing any unimplemented device/config/calibration action.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OriginalPage:
    object_name: str
    image_name: str
    fallback_title_ru: str


ORIGINAL_FORM_CLASS = "Tmvkform"
ORIGINAL_FORM_CAPTION = "ТПО МВК"  # DFM #1058#1055#1054' '#1052#1042#1050
ORIGINAL_CLIENT_SIZE = (1008, 929)
ORIGINAL_MIN_WINDOW_SIZE = (1024, 704)
ORIGINAL_FONT = ("Tahoma", -13)  # Delphi logical pixels at design DPI 96
ORIGINAL_ROOT_PAGECONTROL = "Pages"
ORIGINAL_ROOT_TAB_HEIGHT = 44
ORIGINAL_CHANNEL_TAB_HEIGHT = 36

ORIGINAL_ROOT_PAGES = (
    OriginalPage("PageStart", "BWHand", "Задачи"),
    OriginalPage("PageConfig", "BWGear", "Настройка"),
    OriginalPage("PageStatus", "BWTable", "Состояние"),
    OriginalPage("PageAdc", "BWOsc", "Сигнал"),
    OriginalPage("PageSpectrum", "BWSpec", "Спектр"),
    OriginalPage("PageFile", "BWEdit", "Файлы"),
    OriginalPage("PageCalib", "BWBinary", "Калибровка"),
)

# DFM values in *Delphi logical pixels*, not already multiplied by Windows
# scaling. Reusing them as Qt logical coordinates is a first source-based pass;
# final Win32 font metrics/scaling/color/bitmap parity needs separate work.
ORIGINAL_PANEL_LAYOUT = {
    "pnMain": (0, 0, 1008, 828),
    "Pages": (4, 4, 1000, 820),
    "tcAdc": (0, 0, 992, 766),
    "pnAdcTools": (4, 6, 177, 756),
    "pnAdcGraph": (181, 6, 807, 756),
    "pbAdc": (8, 8, 791, 740),
    "tcSpectrum": (0, 0, 992, 766),
    "pnSpecTools": (4, 6, 177, 756),
    "pnSpecGraph": (181, 6, 807, 756),
    "pbSpectrum": (8, 32, 767, 716),
    "pnSpecGraphTop": (8, 8, 791, 24),
    "pnSpecGraphRight": (775, 32, 24, 716),
    "sbSpecHScroll": (24, 0, 553, 24),
    "sbSpecVScroll": (0, 0, 24, 400),
    "tcConfig": (0, 60, 992, 706),
    "pnConfig": (0, 0, 992, 60),
    "tcStatus": (0, 0, 992, 766),
    "tcFileChannels": (0, 0, 369, 766),
    "tcFileActions": (377, 0, 615, 766),
    "splFile": (369, 0, 8, 766),
    "tcCalibParam": (0, 0, 369, 766),
    "tcCalibResult": (377, 0, 615, 766),
    "splCalib": (369, 0, 8, 766),
    "pnMeasure": (0, 828, 1008, 53),
    "pnView": (0, 881, 1008, 48),
}

# Primary buttons and labels of the ORIGINAL PageSpectrum/pnSpecTools.
# The order below is *geometric*, not conventional Qt layout order.
ORIGINAL_SPECTRUM_CONTROLS = (
    ("bSpecEnvelopeType", "TButton", 9, 9, 162, 41),
    ("bSpecType", "TButton", 9, 56, 162, 41),
    ("bSpecLines", "TButton", 9, 103, 162, 41),
    ("bSpecHScale", "TButton", 9, 150, 162, 41),
    ("bSpecVScale", "TButton", 9, 197, 162, 41),
    ("lbSpecHint", "TLabel", 9, 257, 162, 64),
    ("lbSpecMean", "TLabel", 9, 327, 162, 145),
    ("bSpecCopyValue", "TButton", 9, 464, 162, 41),
    ("bSpecSaveValue", "TButton", 9, 511, 162, 41),
)
ORIGINAL_WAVE_CONTROLS = (
    ("bAdcEnvelopeType", "TButton", 9, 9, 162, 41),
    ("bAdcType", "TButton", 9, 56, 162, 41),
    ("bAdcHScale", "TButton", 9, 103, 162, 41),
    ("bAdcVScale", "TButton", 9, 150, 162, 41),
    ("lbAdcHint", "TLabel", 9, 207, 162, 64),
    ("lbMean", "TLabel", 9, 277, 162, 164),
)

# SOURCE-DFM: five 48x48 IMAGE-ONLY pnConfigButtons; labels come from
# translated runtime tooltips, not from the original control text.
# Fallback Qt icons must NOT be mistaken for the original bitmaps.
ORIGINAL_CONFIG_TOOLBAR = (
    ("bConfigLoad", 6, 6, 48, 48, "Open"),
    ("bConfigSave", 60, 6, 48, 48, "Save"),
    ("bConfigReset", 122, 6, 48, 48, "Zap"),
    ("bConfigDownload", 184, 6, 48, 48, "DevUpload"),
    ("bConfigUpload", 238, 6, 48, 48, "DevDownload"),
)
ORIGINAL_CONFIG_TABS_DESIGN_TIME = 2
ORIGINAL_STATUS_CHART = (4, 42, 400, 720)
ORIGINAL_STATUS_SPLITTER = (404, 42, 8, 720)

ORIGINAL_TASK_BUTTONS = (
    ("bTaskConnect", 29, 19, 301, 86, "Gears"),
    ("bTaskConfigCh", 370, 19, 458, 86, "EditGear"),
    ("bTaskView", 29, 105, 301, 86, "Open"),
    ("bTaskConfigIP", 370, 105, 458, 86, "EditNet"),
    ("bTaskConfigCalib", 370, 193, 458, 86, "EditCalib"),
)

# Delphi _Unit128:0084ECF0 PagesChange refreshes ADC & Spectrum by page.
ORIGINAL_PAGE_EVENTS = {
    "Pages": "PagesChange",
    "tcConfig": "tcAnyChange",
    "tcStatus": "tcAnyChange",
    "tcAdc": "tcAnyChange",
    "tcSpectrum": "tcAnyChange",
    "tcFileChannels": "tcAnyChange",
    "tcFileActions": "tcAnyChange",
    "tcCalibParam": "tcAnyChange",
    "tcCalibResult": "tcAnyChange",
    "bSpecEnvelopeType": "bAnyDropDownClick",
    "bSpecCopyValue": "bSpecCopyValueClick",
    "bSpecSaveValue": "bSpecSaveValueClick",
    "bTaskView": "bTaskViewClick",
}

ORIGINAL_FILE_SPLITTER_LEFT = 369
ORIGINAL_CALIB_SPLITTER_LEFT = 369


def source_layout_inventory() -> dict:
    """Return a serializable *derived* contract; no user-owned resource bytes."""
    return {
        "form": ORIGINAL_FORM_CLASS,
        "caption": ORIGINAL_FORM_CAPTION,
        "client_size_logical": list(ORIGINAL_CLIENT_SIZE),
        "min_window_logical": list(ORIGINAL_MIN_WINDOW_SIZE),
        "font": [ORIGINAL_FONT[0], ORIGINAL_FONT[1]],
        "root_pagecontrol": ORIGINAL_ROOT_PAGECONTROL,
        "root_tab_height": ORIGINAL_ROOT_TAB_HEIGHT,
        "channel_tab_height": ORIGINAL_CHANNEL_TAB_HEIGHT,
        "pages": [
            {"name": p.object_name, "image": p.image_name,
             "fallback_ru": p.fallback_title_ru} for p in ORIGINAL_ROOT_PAGES
        ],
        "panel_rectangles": {k: list(v) for k, v in ORIGINAL_PANEL_LAYOUT.items()},
        "spectrum_controls": [list(x) for x in ORIGINAL_SPECTRUM_CONTROLS],
        "wave_controls": [list(x) for x in ORIGINAL_WAVE_CONTROLS],
        "task_buttons": [list(x) for x in ORIGINAL_TASK_BUTTONS],
        "config_image_buttons": [list(x) for x in ORIGINAL_CONFIG_TOOLBAR],
        "config_tabs_design_time": ORIGINAL_CONFIG_TABS_DESIGN_TIME,
        "status_chart_rect": list(ORIGINAL_STATUS_CHART),
        "status_splitter_rect": list(ORIGINAL_STATUS_SPLITTER),
        "event_names": dict(ORIGINAL_PAGE_EVENTS),
        "caption_provenance": "DFM_CAPTION_DOLLAR_RUNTIME_TRANSLATION_NOT_YET_RECOVERED",
        "safety": "NO_PRIVATE_DFM_IMAGES_IDP_OR_ORIGINAL_EXECUTABLE_EMBEDDED",
    }
