"""Stage111Z31CK: exhaustive SANITIZED 7-page / 3-form DFM event ledger.

Counts cross-checked locally with the operator-owned Projects.7z:
  Tmvkform 89 DFM bindings, Tmvkeditform 5, TWindowManForm 1;
  95 bindings, 53 unique handler names. Only control/event identities
  and names are retained; no proprietary DFM/PAS/image/IDP bytes or
  executing Delphi code are stored or distributed.

VERY IMPORTANT: "listed in source" != "implemented 1:1" and != "allowed
to dispatch". Every native handler is still default-denied by
original_event_access_control. This is an evidence/QA contract only.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from .original_event_access_control import classify_handler
from .original_ui_form_contract import ORIGINAL_ROOT_PAGES

SOURCE="SOURCE_DERIVED_ORIGINAL_95_EVENT_LEDGER_STAGE111Z31CK"

# Format: <owner> <Delphi event property> <native method name>. These
# contain only structural identifiers, not source procedure bodies.
_MAIN_EVENTS={
"FORM":"""mvkform OnCreate FormCreate
mvkform OnDestroy FormDestroy
mvkform OnResize FormResize
bFreezeUpdate OnClick bFreezeUpdateClick
bWriteTable OnClick bWriteTableClick
bWriteAdc OnClick bWriteAdcClick
bSampleRate OnClick bAnyDropDownClick
bWriteValues OnClick bWriteValuesClick
tbViewTime OnChange tbViewTimeChange
stFormStorage OnSavePlacement stFormStorageSavePlacement
stFormStorage OnRestorePlacement stFormStorageRestorePlacement
tmInterfaceUpdate OnTimer tmInterfaceUpdateTimer
tmConfigResult OnTimer tmConfigResultTimer
mAdcType1 OnClick mAdcType1Click
mAdcType2 OnClick mAdcType1Click
mSpecType1 OnClick mSpecType1Click
mSpecType2 OnClick mSpecType1Click
mSpecType3 OnClick mSpecType1Click
mSpecType4 OnClick mSpecType1Click""",
"Pages":"""Pages OnChange PagesChange""",
"PageStart":"""imLogo OnMouseDown imLogoMouseDown
edLibraryPath OnAfterDialog edLibraryPathAfterDialog
bTaskConnect OnClick bTaskConnectClick
bTaskConfigIP OnClick bTaskConfigIPClick
bTaskConfigCalib OnClick bTaskConfigCalibClick
bTaskConfigCh OnClick bTaskConfigChClick
bTaskView OnClick bTaskViewClick""",
"PageConfig":"""bConfigLoad OnClick bConfigLoadClick
bConfigSave OnClick bConfigSaveClick
bConfigDownload OnClick bConfigDownloadClick
bConfigUpload OnClick bConfigUploadClick
bConfigReset OnClick bConfigResetClick
tcConfig OnChange tcAnyChange
tabConfigChannels OnDblClick tabConfigChannelsDblClick
tabConfigChannels OnDrawCell tabDrawCell
tabConfigChannels OnKeyPress tabKeyPress
tabConfigAlarms OnDblClick tabConfigAlarmsDblClick
tabConfigAlarms OnDrawCell tabDrawCell
tabConfigAlarms OnKeyPress tabKeyPress
tabConfigBasic OnDblClick tabConfigBasicDblClick
tabConfigBasic OnDrawCell tabDrawCell
tabConfigBasic OnKeyPress tabKeyPress""",
"PageStatus":"""tcStatus OnChange tcAnyChange
splResult OnMoved FormResize
tabStatus OnDrawCell tabDrawCell
tabResult OnDrawCell tabDrawCell
tabAllResult OnDrawCell tabDrawCell
chResult OnMouseMove chResultMouseMove
tabAlarmResult OnDrawCell tabDrawCell""",
"PageAdc":"""tcAdc OnChange tcAnyChange
bAdcHScale OnClick bAnyDropDownClick
bAdcVScale OnClick bAnyDropDownClick
bAdcType OnClick bAnyDropDownClick
bAdcEnvelopeType OnClick bAnyDropDownClick
pbAdc OnMouseMove pbAdcMouseMove
pbAdc OnPaint pbAdcPaint""",
"PageSpectrum":"""tcSpectrum OnChange tcAnyChange
bSpecHScale OnClick bAnyDropDownClick
bSpecVScale OnClick bAnyDropDownClick
bSpecLines OnClick bAnyDropDownClick
bSpecType OnClick bAnyDropDownClick
bSpecCopyValue OnClick bSpecCopyValueClick
bSpecSaveValue OnClick bSpecSaveValueClick
bSpecEnvelopeType OnClick bAnyDropDownClick
pbSpectrum OnMouseMove pbSpectrumMouseMove
pbSpectrum OnPaint pbSpectrumPaint
sbSpecHScroll OnChange sbSpecVScrollChange
sbSpecVScroll OnChange sbSpecVScrollChange""",
"PageFile":"""splFile OnMoved FormResize
tcFileChannels OnChange tcAnyChange
cbFileChannels OnClick cbFileChannelsClick
tcFileActions OnChange tcAnyChange
splFileValues OnMoved FormResize
cbFileFolderPrefix OnClick cbFileFolderPrefixClick
cbFileMvkName OnClick cbFileMvkNameClick""",
"PageCalib":"""splCalib OnMoved FormResize
tcCalibResult OnChange tcAnyChange
bCalibSave OnClick bCalibSaveClick
bCalibClear OnClick bCalibClearClick
bCalibGenerate OnClick bCalibGenerateClick
tabCalibResult OnDrawCell tabDrawCell
tcCalibParam OnChange tcAnyChange
cbCalibSteps OnClick cbFileChannelsClick
bCalibStart OnClick bCalibStartClick
bCalibA OnClick bCalibAClick
bCalibV OnClick bCalibAClick
bCalibD OnClick bCalibAClick
bCalibDR OnClick bCalibAClick
bCalibT OnClick bCalibAClick""",
}
_EDITOR_EVENTS="""mvkeditform OnCreate FormCreate
mvkeditform OnShow FormShow
bOk OnClick bOkClick
cbVal OnDblClick bOkClick
bRecalc OnClick bRecalcClick"""
_WINDOWMAN_EVENTS="""bOk OnClick bOkClick"""


@dataclass(frozen=True)
class SourceFormEvent:
    form: str
    page: str
    object_name: str
    event_property: str
    handler: str

    @property
    def source_key(self):
        return (self.form,self.page,self.object_name,
                self.event_property,self.handler)


def _parse(form,page,source):
    rows=[]
    for text in source.strip().splitlines():
        fields=text.split()
        if len(fields)!=3:
            raise ValueError("Sanitized original event ledger malformed")
        name,event,handler=fields
        if (not event.startswith("On") or
                not all(part.isidentifier() for part in fields)):
            raise ValueError("Original source event contains invalid name")
        rows.append(SourceFormEvent(form,page,name,event,handler))
    return tuple(rows)


def original_detailed_event_bindings() -> tuple[SourceFormEvent,...]:
    """Immutable source identities; NEVER dispatch the named callbacks."""
    rows=[]
    for page,description in _MAIN_EVENTS.items():
        rows.extend(_parse("mvkform.dfm",page,description))
    rows.extend(_parse("mvkeditform.dfm","FORM",_EDITOR_EVENTS))
    rows.extend(_parse("WindowManForm.dfm","FORM",_WINDOWMAN_EVENTS))
    if len(rows)!=95:
        raise ValueError("Original DFM event binding total drift")
    forms=Counter(x.form for x in rows)
    if forms!={"mvkform.dfm":89,"mvkeditform.dfm":5,"WindowManForm.dfm":1}:
        raise ValueError("Original three-form event total drift")
    if len({x.handler for x in rows})!=53:
        raise ValueError("Original 53 unique handler names drift")
    pages={x.page for x in rows if x.form=="mvkform.dfm"}
    allowed={"FORM","Pages"}|{x.object_name for x in ORIGINAL_ROOT_PAGES}
    if pages!=allowed:
        raise ValueError("Original seven-page event ownership drift")
    if len({x.source_key for x in rows})!=len(rows):
        raise ValueError("Duplicate original source event binding")
    return tuple(rows)


def original_event_coverage_report():
    """Coverage ledger with explicit confidence, not a self-certified replica."""
    items=original_detailed_event_bindings()
    form_counts=Counter(x.form for x in items)
    page_counts=Counter(x.page for x in items if x.form=="mvkform.dfm")
    categories=Counter(
        classify_handler(x.form,x.handler)["category"] for x in items)
    return {
        "source":SOURCE,"schema":"MVKVIEW_SOURCE_DFM_95_EVENTS_V1",
        "form_count":3,"page_count":7,
        "binding_count":len(items),
        "unique_handler_count":len({e.handler for e in items}),
        "form_binding_counts":dict(form_counts),
        "main_form_page_counts":dict(page_counts),
        "classification_counts":dict(categories),
        "all_native_handlers_automatically_dispatchable":False,
        "all_95_original_behavior_verified":False,
        "original_device_write_authorized":False,
        "requires_original_win32_runtime_comparison":True,
        "bindings":[{
            "form":x.form,"page":x.page,"control":x.object_name,
            "event":x.event_property,"handler":x.handler,
            "permission_category":classify_handler(x.form,x.handler)[
                "category"],
            "implemented_1_to_1_verified":False,
            "device_action_allowed":False,
        } for x in items],
    }
