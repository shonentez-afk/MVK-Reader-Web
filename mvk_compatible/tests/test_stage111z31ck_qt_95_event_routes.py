"""Stage111Z31CK: live seven-page + three-form event coverage.

Use only generated synthetic local archive/config and ephemeral dialogs.
The original Win32 executable and real MVK device/remote commands are
NOT launched. Report missing Qt object names honestly, never equate
object presence to 1:1 original handler behavior.
"""
import hashlib
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QPushButton,QDialog,QLineEdit,QCheckBox)

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from ..desktop.source_event_runtime_audit import (
    audit_live_source_event_controls,
)
from ..desktop.original_value_edit_dialog import OriginalValueEditDialog
from ..core.original_offline_view_state import PAGES


def test_all_seven_live_pages_all_three_forms_dmf95_and_true_safe_routes(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    source=fixture_zip(tmp_path,sample_count=8192)
    before_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    win=MainWindow();win.show();qt_app.processEvents()
    editor=OriginalValueEditDialog(
        parent=win,prompt="Проверка исходного поля",value="1")
    message=win.original_window_man.build(
        "information","Только локальная проверка")
    editor.show()
    message.show()
    qt_app.processEvents()
    try:
        coverage=audit_live_source_event_controls(
            win,editor=editor,windowman=message)
        assert coverage["total_bindings"]==95
        assert coverage["observed_routes"]["root_seven_pages"]
        assert coverage["observed_routes"]["config_tabs"]
        assert coverage["observed_routes"]["file_actions"]
        assert coverage["observed_routes"]["calibration_result_tabs"]
        assert coverage["observed_routes"]["status_modes"]
        assert coverage["observed_routes"]["calibration_steps"]
        assert coverage["observed_routes"]["unsafe_buttons_disabled"]
        assert coverage["observed_routes"]["no_device_command_issued"]
        assert coverage["qt_control_present_count"]>=35
        assert coverage["qt_control_present_count"]+coverage[
            "qt_control_missing_count"]==95
        assert len(coverage["source_events"])==95
        assert not coverage["original_running_process_invoked"]
        assert not coverage["original_95_behavior_verified"]

        win.open_archive(source)
        qt_app.processEvents()
        for idx,page in enumerate(PAGES):
            assert win.original_root_tabs.isTabEnabled(idx)
            win.original_root_tabs.setCurrentIndex(idx)
            qt_app.processEvents()
            assert win.source_view_state.page==page
            assert not win.source_view_state.snapshot()["device_command_issued"]
        # DFM tcAnyChange previously had no independent Core route
        # on these three visible tab-owners.
        panel=win.original_config_panel
        panel.page_tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert win.source_view_state.config_tab==1
        panel.page_tabs.setCurrentIndex(0)
        qt_app.processEvents()
        assert win.source_view_state.config_tab==0
        file_tabs=win.original_shell.file_action_tabs
        file_tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert win.source_view_state.file_action_tab==1
        assert file_tabs.property("sourceCurrentFileActionMode")==1
        assert win.original_shell.file_capture_panel.property(
            "sourceLocalCaptureOptionsVisible") is True
        file_tabs.setCurrentIndex(0)
        qt_app.processEvents()
        assert win.source_view_state.file_action_tab==0
        assert win.original_shell.file_capture_panel.property(
            "sourceLocalCaptureOptionsVisible") is False
        calibration=win.original_calib_panel
        calibration.tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert win.source_view_state.calibration_result_tab==1
        calibration.tabs.setCurrentIndex(0)
        qt_app.processEvents()
        assert win.source_view_state.calibration_result_tab==0

        win.original_root_tabs.setCurrentIndex(2)
        win.original_shell.status_tabs.setCurrentIndex(12)
        qt_app.processEvents()
        assert win.source_view_state.status_tab==12

        # Source cbFileFolderPrefixClick / cbFileMvkNameClick only
        # enable matching local name fields; no device file operation.
        win.original_root_tabs.setCurrentIndex(5)
        for flag_name,field_name in (
            ("cbFileFolderPrefix","edFolderPrefix"),
            ("cbFileMvkName","edFileMvkName")):
            flag=win.original_shell.file_record_flags[flag_name]
            value=win.original_shell.file_record_names[field_name]
            flag.setChecked(False)
            qt_app.processEvents()
            assert not value.isEnabled()
            flag.setChecked(True)
            qt_app.processEvents()
            assert value.isEnabled()
        assert not win._live_active
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before_hash

        # bCalibAClick is a verified LOCAL selection only; physical
        # bCalibStart remains disabled even with an open archive.
        win.original_root_tabs.setCurrentIndex(6)
        calibration.groups[min(calibration.groups)].click()
        qt_app.processEvents()
        assert calibration.workspace.checked_steps>=0
        assert calibration.steps.count()==49
        assert not calibration.buttons["bCalibStart"].isEnabled()
        assert not win.original_config_panel.page.findChild(
            QPushButton,"bConfigUpload").isEnabled()
        assert not win.original_config_panel.page.findChild(
            QPushButton,"bConfigDownload").isEnabled()
        assert not win.original_config_panel.page.findChild(
            QPushButton,"bConfigReset").isEnabled()
    finally:
        editor.close()
        message.close()
        win.close()
        qt_app.processEvents()


def test_third_form_brecalc_actual_edited_source_single_without_device(
        qt_app):
    # Native Tmvkeditform.bRecalcClick 008404E8, previously missing.
    form=OriginalValueEditDialog(
        prompt="Чувствительность",value="2,5",
        sensitivity_conversion=True)
    form.show();qt_app.processEvents()
    try:
        assert form.objectName()=="mvkeditform"
        assert form.bRecalc.isVisible()
        assert form.edVal.isVisible()
        assert not form.cbVal.isVisible()
        form.bRecalc.click()
        qt_app.processEvents()
        recalc=form.source_recalc_receipt
        assert recalc is not None
        assert recalc.source_factor=="0.00010194"
        assert recalc.converted_single>0
        assert not recalc.instrument_write_sent
        assert not recalc.configuration_mutated
        assert not recalc.original_delphi_float_to_str_parity_verified
        assert form.edVal.text()==recalc.formatted_candidate
        assert "," in form.edVal.text()
        form.edVal.setText("не число")
        form.bRecalc.click()
        qt_app.processEvents()
        assert form.source_recalc_receipt is None
        assert "Недопустимое" in form.lbVal.text()
        assert form.edVal.text()=="не число" # never commit invalid edit
        form.edVal.setText("1")
        form.bRecalc.click()
        assert form.source_recalc_receipt is not None
        form.bOk.click()
        assert form.result()==QDialog.Accepted
    finally:
        form.close()
        qt_app.processEvents()


def test_editor_source_hidden_default_readonly_and_list_doubleclick(qt_app):
    default=OriginalValueEditDialog(value="1")
    readonly=OriginalValueEditDialog(
        value="2",read_only=True,sensitivity_conversion=True)
    choices=OriginalValueEditDialog(
        choices=["A","B"],sensitivity_conversion=True)
    for dlg in (default,readonly,choices):
        dlg.show()
    qt_app.processEvents()
    try:
        assert not default.bRecalc.isVisible()
        assert not readonly.bRecalc.isVisible()
        assert not choices.bRecalc.isVisible()
        assert readonly.edVal.isReadOnly()
        assert not readonly.bOk.isEnabled()
        assert choices.cbVal.isVisible()
        item=choices.cbVal.item(1)
        choices.cbVal.setCurrentItem(item)
        choices.cbVal.itemDoubleClicked.emit(item)
        assert choices.result()==QDialog.Accepted
        assert choices.selected_value()=="B"
    finally:
        for dlg in (default,readonly,choices):
            dlg.close()
        qt_app.processEvents()


def test_third_windowman_bok_returns_source_modal_result_without_mutations(
        qt_app):
    from ..desktop.original_windowman_form import OriginalWindowManForm
    from ..core.original_windowman_source import source_window_message
    dialog=OriginalWindowManForm()
    dialog.setup_source(source_window_message(
        "information","Проверка без прибора"))
    dialog.show();qt_app.processEvents()
    try:
        assert dialog.objectName()=="WindowManForm"
        assert dialog.bOk.isVisible()
        assert dialog.property("deviceCommandAllowed") is False
        dialog.bOk.click()
        assert dialog.result()==1
    finally:
        dialog.close()
        qt_app.processEvents()
