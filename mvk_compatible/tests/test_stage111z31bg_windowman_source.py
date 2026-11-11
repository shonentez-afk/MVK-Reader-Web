"""Stage111Z31BG: original third form's source-only state.

These tests use no original program, images, instrument or dialog.
"""
import pytest

from mvk_compatible.core.original_windowman_source import (
    SOURCE, BUTTONS, ORIGINAL_CLIENT_SIZE, ICON_RECT, LABEL_RECT,
    source_window_message,
)


def test_source_third_form_has_original_dfm_geometry_and_button_results():
    assert SOURCE.endswith("STAGE111Z31BG")
    assert ORIGINAL_CLIENT_SIZE==(436,186)
    assert LABEL_RECT==(111,24,304,65)
    assert ICON_RECT==(16,16,80,80)
    assert {n:result for n,key,result,_ in BUTTONS}=={
        "bYes":6,"bNo":7,"bCancel":2,"bOk":1}


def test_source_controller_modes_and_local_only_contract():
    for mode,code,active,title in (
        ("error",0,("bOk",),"Error"),
        ("information",2,("bOk",),"Information"),
        ("query",3,("bYes","bNo","bCancel"),""),
        ("wait",1,(),"Wait"),
    ):
        msg=source_window_message(mode,"synthetic")
        assert msg.mode==mode and msg.icon_index==code
        assert msg.button_names==active and msg.title_key==title
        assert msg.original_dpi96_geometry_verified
        assert not msg.original_resource_icons_available
        assert not msg.original_runtime_localization_verified
        assert not msg.device_action_allowed


def test_custom_query_only_enables_requested_original_buttons():
    item=source_window_message(
        "query","message",title="Query",yes=True,no=False,cancel=True)
    assert item.button_names==("bYes","bCancel")
    assert item.title=="Query"
    assert source_window_message(
        "query","",yes=False,no=False,cancel=False).button_names==()


@pytest.mark.parametrize("kwargs",[
    {"mode":"invalid","message":"x"},
    {"mode":"error","message":1},
    {"mode":"wait","message":"x"*8193},
    {"mode":"query","message":"x","title":"a"*257},
    {"mode":"query","message":"x","yes":1},
    {"mode":"query","message":"x","no":None},
    {"mode":"query","message":"x","cancel":"False"},
])
def test_invalid_source_window_state_fails_closed(kwargs):
    with pytest.raises(ValueError):
        source_window_message(**kwargs)
