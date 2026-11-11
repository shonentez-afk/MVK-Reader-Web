"""Stage111Z31AW: source-only validation of original UI logical rectangles.

The original DFM/IDP was examined privately.  The public test uses ONLY a
derived, small data contract and never redistributes Delphi resources.
"""
from mvk_compatible.core.original_ui_form_contract import (
    ORIGINAL_SPECTRUM_CONTROLS, ORIGINAL_WAVE_CONTROLS,
    ORIGINAL_CONFIG_TOOLBAR, ORIGINAL_CONFIG_TABS_DESIGN_TIME,
    ORIGINAL_STATUS_CHART, ORIGINAL_STATUS_SPLITTER,
    source_layout_inventory,
)


def test_original_spec_nine_controls_and_source_overlap():
    assert [name for name, *_ in ORIGINAL_SPECTRUM_CONTROLS] == [
        "bSpecEnvelopeType", "bSpecType", "bSpecLines",
        "bSpecHScale", "bSpecVScale", "lbSpecHint", "lbSpecMean",
        "bSpecCopyValue", "bSpecSaveValue",
    ]
    by_name={name: (x,y,w,h)
             for name, _, x,y,w,h in ORIGINAL_SPECTRUM_CONTROLS}
    assert all(w == 162 for _,_,w,_ in by_name.values())
    assert by_name["bSpecLines"] == (9,103,162,41)
    assert by_name["lbSpecMean"] == (9,327,162,145)
    assert by_name["bSpecCopyValue"] == (9,464,162,41)
    assert (327+145)-464 == 8  # overlapping Delphi VCL controls


def test_original_wave_six_controls_and_status_splitter():
    assert len(ORIGINAL_WAVE_CONTROLS) == 6
    assert ORIGINAL_WAVE_CONTROLS[-1] == (
        "lbMean", "TLabel", 9,277,162,164)
    assert ORIGINAL_STATUS_CHART == (4,42,400,720)
    assert ORIGINAL_STATUS_SPLITTER == (404,42,8,720)


def test_original_config_icon_only_five_buttons_two_runtime_modes():
    expected=[
        ("bConfigLoad",6,6,48,48,"Open"),
        ("bConfigSave",60,6,48,48,"Save"),
        ("bConfigReset",122,6,48,48,"Zap"),
        ("bConfigDownload",184,6,48,48,"DevUpload"),
        ("bConfigUpload",238,6,48,48,"DevDownload"),
    ]
    assert list(ORIGINAL_CONFIG_TOOLBAR) == expected
    assert ORIGINAL_CONFIG_TABS_DESIGN_TIME == 2
    inv=source_layout_inventory()
    assert inv["config_image_buttons"] == [list(x) for x in expected]
    assert inv["config_tabs_design_time"] == 2
    assert inv["status_chart_rect"] == [4,42,400,720]
    assert inv["status_splitter_rect"] == [404,42,8,720]
    assert inv["caption_provenance"].startswith("DFM_CAPTION_DOLLAR")
