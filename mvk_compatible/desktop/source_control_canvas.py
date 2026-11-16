"""Original Delphi DFM control rectangles with safe Qt narrow-window fallback.

Coordinates are source-verified *logical* pixels. At full 177px pnSpecTools
width the paint geometry is exact. If a native Qt vertical scrollbar takes
space in a short window, only the X coordinates are proportionally reduced:
the original DFM rectangles stay available as immutable widget metadata.
This avoids silently clipping the right part of 162px buttons.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget, QScrollArea


class SourceControlCanvas(QWidget):
    """A fixed-height DFM canvas with width-responsive source controls."""

    def __init__(
        self,
        parent: QWidget,
        control_spec: Sequence[tuple[str, str, int, int, int, int]],
        bindings: Mapping[str, QWidget],
        name: str,
        tab_order: Sequence[str] | None = None,
    ) -> None:
        super().__init__(parent)
        source_names = {entry[0] for entry in control_spec}
        if set(bindings) != source_names:
            raise ValueError(
                f"Source controls mismatch for {name}: "
                f"missing={sorted(source_names-set(bindings))}, "
                f"extra={sorted(set(bindings)-source_names)}")
        self.setObjectName(name)
        self._focus_controls=set(bindings.values())
        focus_names={key for key,value in bindings.items()
                     if not isinstance(value,QLabel)}
        if tab_order is not None and (len(set(tab_order))!=len(tab_order)
                or set(tab_order)!=focus_names):
            raise ValueError("DFM TabOrder must list each button exactly once")
        self._source_tab_order=tuple(tab_order or ())
        self.setProperty("originalDfmTabOrder",self._source_tab_order)
        self._source_controls = tuple(
            (left, top, width, height, bindings[source_name])
            for source_name, _, left, top, width, height in control_spec)
        self._source_extent = max(left + width
                                  for left, _, width, _, _ in self._source_controls)
        height = max(top + h for _, top, _, h, _ in self._source_controls) + 4
        self.setFixedHeight(height)
        self.setMinimumWidth(0)
        self.setMaximumWidth(self._source_extent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for name_in_source, _, left, top, width, h in control_spec:
            widget = bindings[name_in_source]
            widget.setParent(self)
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(width)
            widget.setFixedHeight(h)
            widget.setGeometry(left, top, width, h)
            widget.setProperty("originalDfmControlName", name_in_source)
            widget.setProperty("originalDfmLogicalRect",
                               (left, top, width, h))
            if isinstance(widget, QLabel):
                widget.setAlignment(Qt.AlignCenter)
                widget.setWordWrap(True)
            widget.installEventFilter(self)
            widget.show()
        if self._source_tab_order:
            for order,source_name in enumerate(self._source_tab_order):
                bindings[source_name].setProperty("originalDfmTabOrder",order)
            for current,following in zip(
                    self._source_tab_order,self._source_tab_order[1:]):
                QWidget.setTabOrder(bindings[current],bindings[following])

    def eventFilter(self, watched, event):
        # When the native source panel is clipped at 150% DPI, moving
        # focus via *original* TabOrder must reveal the real control in
        # the scroll viewport, not just activate an invisible widget.
        if event.type()==QEvent.FocusIn and watched in self._focus_controls:
            ancestor=self.parentWidget()
            while ancestor is not None and not isinstance(ancestor,QScrollArea):
                ancestor=ancestor.parentWidget()
            if ancestor is not None:
                ancestor.ensureWidgetVisible(watched,0,6)
                self.setProperty("sourceDfmFocusRevealedInViewport",True)
        return super().eventFilter(watched,event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Source rightmost extent is x=171, while original surrounding panel
        # is 177px. A Windows style scrollbar can reduce the viewport below
        # 171 in a minimum-height window; never generate horizontal clipping.
        factor = min(1.0, max(1, self.width()) / self._source_extent)
        for x, y, width, height, widget in self._source_controls:
            scaled_x = int(round(x * factor))
            scaled_width = min(width, max(1, int(round(width * factor))))
            scaled_width = min(scaled_width, max(1, self.width() - scaled_x))
            if widget.geometry().getRect() != (
                    scaled_x, y, scaled_width, height):
                widget.setGeometry(scaled_x, y, scaled_width, height)


def source_control_canvas(
    parent: QWidget,
    control_spec: Sequence[tuple[str, str, int, int, int, int]],
    bindings: Mapping[str, QWidget],
    *,
    name: str,
    panel_width: int = 177,
    tab_order: Sequence[str] | None = None,
) -> SourceControlCanvas:
    """Place source controls; panel_width is surrounding DFM pn*Tools width."""
    if panel_width < max(x + w for _, _, x, _, w, _ in control_spec):
        raise ValueError("Source panel is narrower than its DFM controls")
    return SourceControlCanvas(parent, control_spec, bindings, name,
                               tab_order=tab_order)
