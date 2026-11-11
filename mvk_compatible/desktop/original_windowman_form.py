"""Stage111Z31BG: source TWindowManForm third Delphi form in Qt.

Reconstructs geometry, button names/visibility and modal-result codes;
does not reproduce private image bitmaps or vendor locale strings. All
functions are local UI. No device/config/calibration action is exposed.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton

from ..core.original_language_source import source_localize
from ..core.original_windowman_source import (
    BUTTONS, ICON_RECT, LABEL_RECT, ORIGINAL_CLIENT_SIZE,
    SourceWindowMessage, source_window_message,
)


class OriginalWindowManForm(QDialog):
    """Original TWindowManForm structure; no hardcoded design-time joke text."""

    def __init__(self, parent=None, language=None):
        super().__init__(parent)
        self.setObjectName("WindowManForm")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setModal(False)
        self.setFixedSize(*ORIGINAL_CLIENT_SIZE)
        self._language = language
        self._source_message = None

        self.Lbl = QLabel("", self)
        self.Lbl.setObjectName("Lbl")
        self.Lbl.setGeometry(*LABEL_RECT)
        self.Lbl.setWordWrap(True)

        self.img = QPushButton("", self)
        self.img.setObjectName("img")
        self.img.setGeometry(*ICON_RECT)
        self.img.setEnabled(False)
        self.img.setProperty("originalSourceImageUnavailable", True)

        self._buttons = {}
        for name, source_key, result, rect in BUTTONS:
            control = QPushButton("", self)
            control.setObjectName(name)
            control.setGeometry(*rect)
            control.setVisible(False)
            control.setAutoDefault(False)
            control.clicked.connect(
                lambda checked=False, modal_code=result: self.done(modal_code))
            self._buttons[name] = (control, source_key, result)
            setattr(self, name, control)

    def _localize(self, key: str) -> str:
        if self._language is not None:
            try:
                return self._language.display(key)
            except (ValueError, KeyError):
                pass
        return source_localize(key).display

    def setup_source(self, message: SourceWindowMessage) -> None:
        if not isinstance(message, SourceWindowMessage):
            raise ValueError("Original source message contract required")
        self._source_message = message
        title = message.title if message.title is not None else (
            self._localize(message.title_key) if message.title_key else "")
        self.setWindowTitle(title)
        self.Lbl.setText(message.message)
        self.img.setProperty("originalSourceImageIndex", message.icon_index)
        # Icons are source-dependent original embedded TImageCollection data;
        # we deliberately do NOT substitute an allegedly exact resource.
        self.img.setText(("!", "...", "i", "?")[message.icon_index])
        for name, (button, key, code) in self._buttons.items():
            enabled = name in message.button_names
            button.setText(self._localize(key) if enabled else "")
            button.setVisible(enabled)
            button.setDefault(enabled and name in ("bYes", "bOk"))
        self.setProperty("originalSourceMessageMode", message.mode)
        self.setProperty("deviceCommandAllowed", False)

    def original_button_result_map(self) -> dict[str, int]:
        return {name: result for name, (_, _, result) in self._buttons.items()}


class OriginalWindowMan:
    """Source TWindowMan controller, local-only. No original executable runs."""

    def __init__(self, parent, language=None):
        self.parent = parent
        self.language = language
        self._visible = []
        self._wait = None

    def build(self, kind: str, message: str, **kwargs) -> OriginalWindowManForm:
        dialog = OriginalWindowManForm(self.parent, language=self.language)
        dialog.setup_source(source_window_message(kind, message, **kwargs))
        return dialog

    def _show(self, dialog: OriginalWindowManForm) -> OriginalWindowManForm:
        self._visible.append(dialog)
        dialog.finished.connect(
            lambda _result, current=dialog: (
                self._visible.remove(current)
                if current in self._visible else None))
        dialog.show()
        return dialog

    def spawn_error(self, message: str) -> OriginalWindowManForm:
        self.hide_wait()
        return self._show(self.build("error", message))

    def spawn_information(self, message: str) -> OriginalWindowManForm:
        self.hide_wait()
        return self._show(self.build("information", message))

    def create_query(self, message: str, title: str, *,
                     yes: bool, no: bool, cancel: bool
                     ) -> OriginalWindowManForm:
        # Explicit caller may exec() later; merely constructing this form
        # NEVER authorizes any underlying action.
        return self.build("query", message, title=title,
                          yes=yes, no=no, cancel=cancel)

    def show_wait(self, message: str) -> OriginalWindowManForm:
        if self._wait is None:
            self._wait = self.build("wait", message)
        else:
            self._wait.setup_source(source_window_message("wait", message))
        self._wait.show()
        return self._wait

    def hide_wait(self) -> None:
        if self._wait is not None:
            self._wait.close()
            self._wait = None
