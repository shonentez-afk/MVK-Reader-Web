"""Original mvkeditform.dfm geometry, deliberately offline-only.

The DFM has overlapping edVal and cbVal controls: original runtime chooses
text editing vs list selection. This reimplementation keeps them mutually
exclusive. The "recalculate" control is hidden in the original DFM as well.
No network/device write, no original bitmap data.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QListWidget, QPushButton,
)

ORIGINAL_DIALOG_CLIENT_SIZE = (357, 445)
ORIGINAL_DIALOG_CAPTION = "Редактирование"


class OriginalValueEditDialog(QDialog):
    """Safe, local replacement for IDR Tmvkeditform."""

    def __init__(self, *, prompt: str = "", value: str = "",
                 units: str = "", choices: list[str] | None = None,
                 parent=None, read_only: bool = False):
        super().__init__(parent)
        self.setObjectName("mvkeditform")
        self.setWindowTitle(ORIGINAL_DIALOG_CAPTION)
        self.setFixedSize(*ORIGINAL_DIALOG_CLIENT_SIZE)
        self.setModal(True)
        self._source_inspection_only = bool(read_only)

        label = QLabel(prompt or "Значение", self)
        label.setObjectName("lbVal")
        label.setGeometry(16, 10, 321, 47)
        label.setWordWrap(True)

        self.edVal = QLineEdit(value, self)
        self.edVal.setObjectName("edVal")
        self.edVal.setGeometry(16, 63, 245, 21)

        lbl_unit = QLabel(units, self)
        lbl_unit.setObjectName("lbUnits")
        lbl_unit.setGeometry(284, 66, 65, 31)
        lbl_unit.setWordWrap(True)

        self.cbVal = QListWidget(self)
        self.cbVal.setObjectName("cbVal")
        self.cbVal.setGeometry(16, 49, 321, 229)
        self.cbVal.itemDoubleClicked.connect(self._accept_selected)
        for item in choices or ():
            self.cbVal.addItem(item)
        # DFM declares both edit/list because the source toggles at runtime.
        self.cbVal.setVisible(choices is not None)
        self.edVal.setVisible(choices is None)

        self.bOk = QPushButton("ОК", self)
        self.bOk.setObjectName("bOk")
        self.bOk.setGeometry(16, 300, 113, 37)
        self.bOk.setDefault(True)
        self.bOk.clicked.connect(self._accept_selected)
        self.bCancel = QPushButton("Отмена", self)
        self.bCancel.setObjectName("bCancel")
        self.bCancel.setGeometry(147, 300, 114, 37)
        self.bCancel.clicked.connect(self.reject)

        self.bRecalc = QPushButton("Пересчитать мВ/g → В/(м/с²)", self)
        self.bRecalc.setObjectName("bRecalc")
        self.bRecalc.setGeometry(16, 104, 245, 33)
        self.bRecalc.setVisible(False)  # explicitly original DFM Visible=False
        if self._source_inspection_only:
            # Only the original dialog's DFM structure is reused here.
            # Source TMvkCellList.InputValue commits a LOCAL register image,
            # but there is no validated writable current config or upload.
            self.edVal.setReadOnly(True)
            self.cbVal.setEnabled(False)
            self.bOk.setEnabled(False)
            self.bCancel.setText("Закрыть")
            self.setWindowTitle("Исходное поле · просмотр без изменения")

    def selected_value(self) -> str:
        """Return edited value without applying it to any instrument."""
        if self.cbVal.isVisible():
            selected = self.cbVal.currentItem()
            return selected.text() if selected is not None else ""
        return self.edVal.text()

    def _accept_selected(self, *_):
        if self._source_inspection_only:
            return  # No local commit, no device/call-site action
        if self.cbVal.isVisible() and self.cbVal.currentItem() is None:
            return
        self.accept()
