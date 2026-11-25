import pytest

pytest.importorskip("PySide6")
from .test_desktop_qt import qt_app
from mvk_compatible.core.original_pagefile_settings import (
    DEFAULT_PAGEFILE_SETTINGS,load_pagefile_settings,pagefile_settings_path)


def test_recording_options_restored_in_separate_profile(tmp_path,monkeypatch,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow

    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path/"profile"))
    library=tmp_path/"measurements"
    library.mkdir()
    filename=pagefile_settings_path()
    assert load_pagefile_settings()==DEFAULT_PAGEFILE_SETTINGS
    w=MainWindow()
    try:
        shell=w.original_shell
        shell._install_pagefile_settings()  # production portable startup hook
        w.original_start_controller.set_library(library)
        assert shell._file_names_option_state().write_tsxml
        shell.file_record_flags["cbFileWriteXml"].setChecked(False)
        shell.file_record_flags["cbFileFolderPrefix"].setChecked(True)
        shell.file_record_flags["cbFileMvkName"].setChecked(True)
        for name,text in (("edFolderPrefix","Серия"),("edFileMvkName","МВК4")):
            field=shell.file_record_names[name]
            field.setText(text)
            field.editingFinished.emit()
        assert filename.exists()
        assert not filename.with_name("device.xml").exists()
    finally:
        w.close()
    w=MainWindow()
    try:
        w.original_shell._install_pagefile_settings()
        restored=w.original_shell._file_names_option_state()
        assert not restored.write_tsxml
        assert restored.use_folder_prefix and restored.use_custom_name
        assert restored.folder_prefix=="Серия" and restored.custom_name=="МВК4"
        assert w.original_start_controller.workspace.library_path==library
        assert w.original_start_controller.library_files.count()==0
    finally:
        w.close()
