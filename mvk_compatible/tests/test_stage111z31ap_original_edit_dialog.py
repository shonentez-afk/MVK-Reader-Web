"""Original Tmvkeditform DFM geometry/behaviour (no device or network)."""
from __future__ import annotations
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from mvk_compatible.desktop.original_value_edit_dialog import OriginalValueEditDialog


@pytest.fixture
def app():
    result = QApplication.instance()
    if result is None:
        result = QApplication([])
    return result


def test_original_dialog_text_mode(app):
    box = OriginalValueEditDialog(prompt="Значение", value="10", units="мВ/g")
    try:
        assert box.objectName() == "mvkeditform"
        assert box.size().width() == 357
        assert box.size().height() == 445
        assert box.edVal.objectName() == "edVal"
        assert not box.cbVal.isVisible()
        assert box.selected_value() == "10"
        assert not box.bRecalc.isVisible()
        box.edVal.setText("11")
        assert box.selected_value() == "11"
    finally:
        box.close()


def test_original_dialog_list_mode(app):
    box = OriginalValueEditDialog(choices=["Первый", "Второй"])
    try:
        assert not box.edVal.isVisible()
        assert box.cbVal.count() == 2
        box.cbVal.setCurrentRow(1)
        # Before the dialog is shown isVisible() is False for all children,
        # selected_value() works after display.
        box.show()
        assert box.selected_value() == "Второй"
    finally:
        box.close()
