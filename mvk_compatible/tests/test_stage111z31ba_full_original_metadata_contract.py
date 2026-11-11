"""Stage111Z31BA independent source-derived 3-form/7-page IDR coverage gates.

Published file is ONLY sanitized component/event metadata, not original
decompiled PAS, raw DFM, program resources or private IDP.
A passing test is STRUCTURE coverage, never functional compatibility.
"""
from pathlib import Path
import json

from mvk_compatible.core.original_ui_form_contract import ORIGINAL_ROOT_PAGES


ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"docs/research/STAGE111Z31BA_FULL_IDR_STRUCTURE_METADATA.json"
EXPECTED_FORMS={
    "mvkform.dfm":(145,89,50),
    "mvkeditform.dfm":(8,5,4),
    "WindowManForm.dfm":(9,1,1),
}
EXPECTED_DYNAMIC_METHODS={
    "mAdcHScale1Click","mAdcVScale1Click","mEnvelopeType1Click",
    "mRate1Click","mSpecHScale1Click","mSpecLines1Click",
    "mSpecVScale1Click",
}


def test_exact_three_private_dfm_form_counts_are_indexed():
    meta=json.loads(SOURCE.read_text(encoding="utf-8"))
    assert meta["schema"]=="MVKVIEW_ORIGINAL_STRUCTURAL_INVENTORY_V1"
    assert meta["pas_files_count"]==129
    assert meta["idr_generated_unit_files_count"]==86
    assert meta["dfm_files_count"]==3
    assert meta["dpr_files_count"]==1
    assert set(meta["forms"])==set(EXPECTED_FORMS)
    for key,(controls,bindings,handlers) in EXPECTED_FORMS.items():
        form=meta["forms"][key]
        assert form["component_count"]==controls
        assert form["event_binding_count"]==bindings
        assert form["distinct_event_handlers"]==handlers
        assert len(form["bound_handler_addresses"])==handlers
        assert form["bound_handlers_missing_in_declared_class"]==[]
        assert all(len(addr)==8 and int(addr,16)>0
                   for addr in form["bound_handler_addresses"].values())
    assert not meta["original_live_runtime_verified"]
    assert not meta["executable_code_semantics_verified"]
    assert not meta["source_code_or_original_resources_embedded"]


def test_all_seven_original_page_names_crosswalk_to_current_shell_contract():
    meta=json.loads(SOURCE.read_text(encoding="utf-8"))
    main=meta["forms"]["mvkform.dfm"]
    original_page_names=set(main["page_component_counts"])
    current_source_page_names={p.object_name for p in ORIGINAL_ROOT_PAGES}
    assert current_source_page_names==original_page_names
    assert len(original_page_names)==7
    assert set(main["declared_methods_unbound_in_dfm"])==EXPECTED_DYNAMIC_METHODS
    for page,count in main["page_component_counts"].items():
        assert count>=8, "Unexpected loss in source hierarchy for "+page
    assert {c["name"] for c in main["controls"]
            if c["class"]=="TTabSheet"}==original_page_names


def test_no_program_binary_pascal_or_runtime_proof_in_sanitized_metadata():
    meta=json.loads(SOURCE.read_text(encoding="utf-8"))
    for form in meta["forms"].values():
        for control in form["controls"]:
            assert set(control).issubset({
                "name","class","parent","page","line","geometry","events"})
            assert not any(key in control for key in
                           ("source_code","binary_blob","picture_data"))
            assert all(type(s) is str for s in control["events"].values())
    assert meta["source_kind"].startswith("private_IDR_decompilation_")
    assert not meta["original_live_runtime_verified"]
