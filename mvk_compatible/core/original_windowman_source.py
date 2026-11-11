"""Stage111Z31BG: original third form WindowMan, source-only message state.

Private IDR: WindowManForm.dfm (client 436x186; Lbl/img/4 buttons),
_Unit115:007C8B50 bOkClick, 007C8B7C SetupButtons,
007C8C90 SetupTitle, 007C8E1C SpawnError, 007C8EE4 SpawnMsg,
007C8FB8 UserQuery, 007C90E0 ShowWait, 007C91C0 HideWait.

No original image resources/DFM or original strings embedded. A source
modal result is UI-only and cannot authorize a device command.
"""
from __future__ import annotations
from dataclasses import dataclass

SOURCE = "IDR_TWindowManForm_SOURCE_STAGE111Z31BG"
ORIGINAL_CLIENT_SIZE = (436,186)
SOURCE_ICON_INDEX = {"error":0, "information":2, "query":3, "wait":1}
BUTTONS = (
    ("bYes","Yes",6,(16,127,129,41)),
    ("bNo","No",7,(151,127,129,41)),
    ("bCancel","Cancel",2,(286,127,129,41)),
    ("bOk","Ok",1,(151,127,129,41)),
)
ICON_RECT = (16,16,80,80)
LABEL_RECT = (111,24,304,65)


@dataclass(frozen=True)
class SourceWindowMessage:
    mode: str
    message: str
    title_key: str
    title: str | None
    button_names: tuple[str,...]
    icon_index: int
    original_dpi96_geometry_verified: bool = True
    original_resource_icons_available: bool = False
    original_runtime_localization_verified: bool = False
    device_action_allowed: bool = False


def source_window_message(
    mode: str, message: str, *,
    title: str | None = None,
    yes: bool = True, no: bool = True, cancel: bool = True,
) -> SourceWindowMessage:
    if mode not in SOURCE_ICON_INDEX:
        raise ValueError("Unknown original WindowMan mode")
    if not isinstance(message,str) or len(message)>8192:
        raise ValueError("Source WindowMan message must be bounded text")
    if title is not None and (not isinstance(title,str) or len(title)>256):
        raise ValueError("Source WindowMan title must be bounded")
    for flag in (yes,no,cancel):
        if type(flag) is not bool:
            raise ValueError("Original query buttons are Boolean")
    if mode == "error":
        title_key, active = "Error", ("bOk",)
    elif mode == "information":
        title_key, active = "Information", ("bOk",)
    elif mode == "wait":
        title_key, active = "Wait", ()
    else:
        title_key = ""
        active = tuple(n for n,enabled in (
            ("bYes",yes),("bNo",no),("bCancel",cancel)) if enabled)
    return SourceWindowMessage(
        mode=mode, message=message, title_key=title_key,
        title=title,button_names=active,icon_index=SOURCE_ICON_INDEX[mode])
