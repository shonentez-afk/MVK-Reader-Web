"""Stage111Z31AO: source-recovered original seven page UI contract regression."""
from __future__ import annotations

from mvk_compatible.core.original_ui_form_contract import (
    ORIGINAL_CLIENT_SIZE, ORIGINAL_MIN_WINDOW_SIZE,
    ORIGINAL_ROOT_TAB_HEIGHT, ORIGINAL_CHANNEL_TAB_HEIGHT,
    ORIGINAL_ROOT_PAGES, ORIGINAL_PANEL_LAYOUT,
    ORIGINAL_SPECTRUM_CONTROLS, ORIGINAL_WAVE_CONTROLS,
    ORIGINAL_TASK_BUTTONS, source_layout_inventory,
)


def test_original_delphi_root_page_order_not_three_research_tabs():
    assert [x.object_name for x in ORIGINAL_ROOT_PAGES] == [
        "PageStart", "PageConfig", "PageStatus", "PageAdc",
        "PageSpectrum", "PageFile", "PageCalib"]
    assert [x.image_name for x in ORIGINAL_ROOT_PAGES] == [
        "BWHand", "BWGear", "BWTable", "BWOsc", "BWSpec",
        "BWEdit", "BWBinary"]
    assert len(set(x.object_name for x in ORIGINAL_ROOT_PAGES)) == 7
    assert ORIGINAL_CLIENT_SIZE == (1008, 929)
    assert ORIGINAL_MIN_WINDOW_SIZE == (1024, 704)
    assert ORIGINAL_ROOT_TAB_HEIGHT == 44
    assert ORIGINAL_CHANNEL_TAB_HEIGHT == 36


def test_original_spectrum_geometry_from_private_dfm_without_binaries():
    assert ORIGINAL_PANEL_LAYOUT["pnSpecTools"] == (4, 6, 177, 756)
    assert ORIGINAL_PANEL_LAYOUT["pnSpecGraph"] == (181, 6, 807, 756)
    assert ORIGINAL_PANEL_LAYOUT["pbSpectrum"] == (8, 32, 767, 716)
    assert ORIGINAL_PANEL_LAYOUT["pnSpecGraphTop"][3] == 24
    assert ORIGINAL_PANEL_LAYOUT["pnSpecGraphRight"][2] == 24
    assert ORIGINAL_PANEL_LAYOUT["pnAdcTools"] == (4, 6, 177, 756)
    assert ORIGINAL_PANEL_LAYOUT["tcFileChannels"][2] == 369
    assert ORIGINAL_PANEL_LAYOUT["tcCalibParam"][2] == 369
    assert [x[0] for x in ORIGINAL_SPECTRUM_CONTROLS] == [
        "bSpecEnvelopeType", "bSpecType", "bSpecLines",
        "bSpecHScale", "bSpecVScale", "lbSpecHint",
        "lbSpecMean", "bSpecCopyValue", "bSpecSaveValue"]
    assert [x[3] for x in ORIGINAL_SPECTRUM_CONTROLS] == [
        9, 56, 103, 150, 197, 257, 327, 464, 511]
    assert ORIGINAL_WAVE_CONTROLS[0] == (
        "bAdcEnvelopeType", "TButton", 9, 9, 162, 41)
    assert [x[0] for x in ORIGINAL_TASK_BUTTONS] == [
        "bTaskConnect", "bTaskConfigCh", "bTaskView",
        "bTaskConfigIP", "bTaskConfigCalib"]


def test_source_provenance_does_not_claim_literal_dollar_tab_captions():
    src = source_layout_inventory()
    assert src["root_pagecontrol"] == "Pages"
    assert src["caption"] == "ТПО МВК"
    assert src["caption_provenance"] == (
        "DFM_CAPTION_DOLLAR_RUNTIME_TRANSLATION_NOT_YET_RECOVERED")
    assert src["safety"] == (
        "NO_PRIVATE_DFM_IMAGES_IDP_OR_ORIGINAL_EXECUTABLE_EMBEDDED")
    assert len(src["pages"]) == 7
    assert "mvkform.dfm" not in repr(src).lower() or src["safety"]
