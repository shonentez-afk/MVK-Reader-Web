"""Stage111Z31AR: Original mvkeditform / OriginalValueEditDialog.

Provides a safe offline value-edit dialog that mirrors the Delphi
``TForm`` ``mvkeditform`` contract without sending device commands
or modifying live instrument parameters.

When no safe offline editing scenario is confirmed by the current
source code, the dialog is marked ``UNWIRED_SAFE_BY_DESIGN`` and
shows a descriptive message instead of attempting to edit
unverified instrument parameters.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QMessageBox,
)


# Safe offline editing status constants
UNWIRED_SAFE_BY_DESIGN = 'UNWIRED_SAFE_BY_DESIGN'
SAFE_OFFLINE_EDITING = 'SAFE_OFFLINE_EDITING'
DEVICE_COMMAND_PROHIBITED = 'DEVICE_COMMAND_PROHIBITED'


class OriginalValueEditDialog(QDialog):
    """Safe offline value-edit dialog (``mvkeditform``).

    Mirrors the original Delphi ``TForm`` layout but is wired only
    to safe offline editing scenarios.  When ``wiring_status`` is
    ``UNWIRED_SAFE_BY_DESIGN``, the dialog shows a message explaining
    that no safe offline editing is available and buttons are disabled.
    """

    def __init__(
        self,
        param_name: str = '',
        current_value: Any = None,
        unit: str = '',
        wiring_status: str = UNWIRED_SAFE_BY_DESIGN,
        parent: QDialog | None = None,
    ):
        super().__init__(parent)
        self.setObjectName('mvkeditform')
        self.setWindowTitle(f'Редактирование: {param_name or "---"}')
        self.setModal(True)
        self.setMinimumSize(480, 280)

        self._param_name = param_name
        self._current_value = current_value
        self._unit = unit
        self._wiring_status = wiring_status

        self._build_ui()
        self._apply_wiring_status()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        # Parameter info
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel('Параметр:'))
        self._label_param = QLabel(self._param_name or '—')
        info_layout.addWidget(self._label_param)
        info_layout.addStretch()
        lay.addLayout(info_layout)

        # Current value (read-only display)
        val_layout = QHBoxLayout()
        val_layout.addWidget(QLabel('Текущее значение:'))
        self._label_value = QLabel(
            str(self._current_value) if self._current_value is not None else '—')
        self._label_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        val_layout.addWidget(self._label_value)
        if self._unit:
            val_layout.addWidget(QLabel(self._unit))
        val_layout.addStretch()
        lay.addLayout(val_layout)

        # Edit field (only for safe offline scenarios)
        self._edit_value = QLineEdit()
        self._edit_value.setText(
            str(self._current_value) if self._current_value is not None else '')
        self._edit_value.setObjectName('editValue')
        edit_layout = QHBoxLayout()
        edit_layout.addWidget(QLabel('Новое значение:'))
        edit_layout.addWidget(self._edit_value)
        lay.addLayout(edit_layout)

        # Status group
        status_group = QGroupBox('Статус подключения')
        status_lay = QVBoxLayout(status_group)
        self._label_status = QLabel()
        self._label_status.setWordWrap(True)
        self._label_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        status_lay.addWidget(self._label_status)
        lay.addWidget(status_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self._btn_ok = QPushButton('Применить')
        self._btn_ok.setObjectName('btnApply')
        self._btn_ok.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._btn_ok)

        self._btn_cancel = QPushButton('Отмена')
        self._btn_cancel.setObjectName('btnCancel')
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)
        lay.addLayout(btn_layout)

    def _apply_wiring_status(self):
        """Apply wiring status: enable/disable edit controls."""
        if self._wiring_status == UNWIRED_SAFE_BY_DESIGN:
            self._btn_ok.setEnabled(False)
            self._edit_value.setEnabled(False)
            self._label_status.setText(
                'Редактирование параметра недоступно. '
                'Без подтверждённого сценария безопасного офлайн-редактирования '
                'этот диалог не отправляет команды прибору и не модифицирует '
                'реальные параметры. Статус: UNWIRED_SAFE_BY_DESIGN.')
            self.setWindowTitle(
                f'Редактирование: {self._param_name or "---"} (недоступно)')
        elif self._wiring_status == SAFE_OFFLINE_EDITING:
            self._btn_ok.setEnabled(True)
            self._edit_value.setEnabled(True)
            self._label_status.setText(
                'Офлайн-режим: изменения применяются локально '
                'без отправки команд прибору.')
        else:
            # DEVICE_COMMAND_PROHIBITED
            self._btn_ok.setEnabled(False)
            self._edit_value.setEnabled(False)
            self._label_status.setText(
                'Запрещено: редактирование требует команды прибору, '
                'которая не разрешена в офлайн-режиме.')

    def _on_apply(self):
        """Handle Apply button in safe offline editing mode."""
        if self._wiring_status != SAFE_OFFLINE_EDITING:
            QMessageBox.warning(
                self, 'Недоступно',
                'Изменение параметра невозможно: сценарий офлайн-редактирования '
                'не подтверждён текущими исходниками.')
            return
        new_val = self._edit_value.text()
        self.accept()

    def get_wiring_status(self) -> str:
        return self._wiring_status

    def get_new_value(self) -> str | None:
        if self.exec() == QDialog.Accepted:
            return self._edit_value.text() or None
        return None
