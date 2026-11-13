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
from ..core.original_value_recalc import source_recalc_millivolt_g

ORIGINAL_DIALOG_CLIENT_SIZE = (357, 445)
ORIGINAL_DIALOG_CAPTION = "Редактирование"


class OriginalValueEditDialog(QDialog):
    """Safe, local replacement for IDR Tmvkeditform."""

    def __init__(self, *, prompt: str = "", value: str = "",
                 units: str = "", choices: list[str] | None = None,
                 parent=None, read_only: bool = False,
                 sensitivity_conversion: bool = False):
        super().__init__(parent)
        self.setObjectName("mvkeditform")
        self.setWindowTitle(ORIGINAL_DIALOG_CAPTION)
        self.setFixedSize(*ORIGINAL_DIALOG_CLIENT_SIZE)
        self.setModal(True)
        self._source_inspection_only = bool(read_only)
        self._initial_prompt = prompt or "Значение"
        self._recalc_receipt = None
        self._sensitivity_conversion_enabled = bool(
            sensitivity_conversion and choices is None and not read_only)

        label = QLabel(prompt or "Значение", self)
        label.setObjectName("lbVal")
        self.lbVal = label
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
        # Source DFM Visible=False. The original FormShow keeps that
        # default unless the caller explicitly enables the sensitivity
        # editor mode. No automatic guess from an arbitrary config field.
        self.bRecalc.setVisible(self._sensitivity_conversion_enabled)
        self.bRecalc.setEnabled(self._sensitivity_conversion_enabled)
        self.bRecalc.clicked.connect(self._recalc_clicked)
        self.bRecalc.setToolTip(
            "Исходный bRecalcClick 008404E8: Float32 мВ/g × "
            "Extended 0,00010194 → Float32 В/(м/с²). "
            "Только локальное текстовое поле, НЕ прибор.")
        if self._source_inspection_only:
            # Only the original dialog's DFM structure is reused here.
            # Source TMvkCellList.InputValue commits a LOCAL register image,
            # but there is no validated writable current config or upload.
            self.edVal.setReadOnly(True)
            self.cbVal.setEnabled(False)
            self.bOk.setEnabled(False)
            self.bCancel.setText("Закрыть")
            self.setWindowTitle("Исходное поле · просмотр без изменения")

    @property
    def source_recalc_receipt(self):
        return self._recalc_receipt

    def _recalc_clicked(self):
        """Execute original bRecalcClick arithmetic on edVal only."""
        if (not self._sensitivity_conversion_enabled
                or self._source_inspection_only or self.cbVal.isVisible()):
            return False
        try:
            receipt=source_recalc_millivolt_g(self.edVal.text())
        except (ValueError,OverflowError) as exc:
            self._recalc_receipt=None
            self.lbVal.setText(
                "Недопустимое значение чувствительности (мВ/g): "+str(exc))
            return False
        self._recalc_receipt=receipt
        self.edVal.setText(receipt.formatted_candidate)
        self.lbVal.setText(self._initial_prompt)
        return True

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
