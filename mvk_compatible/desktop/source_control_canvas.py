"""Original Delphi DFM control rectangles with safe Qt narrow-window fallback.

Coordinates are source-verified *logical* pixels. At full 177px pnSpecTools
width the paint geometry is exact. If a native Qt vertical scrollbar takes
space in a short window, only the X coordinates are proportionally reduced:
the original DFM rectangles stay available as immutable widget metadata.
This avoids silently clipping the right part of 162px buttons.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class SourceControlCanvas(QWidget):
    """A fixed-height DFM canvas with width-responsive source controls."""

    def __init__(
        self,
        parent: QWidget,
        control_spec: Sequence[tuple[str, str, int, int, int, int]],
        bindings: Mapping[str, QWidget],
        name: str,
    ) -> None:
        super().__init__(parent)
        source_names = {entry[0] for entry in control_spec}
        if set(bindings) != source_names:
            raise ValueError(
                f"Source controls mismatch for {name}: "
                f"missing={sorted(source_names-set(bindings))}, "
                f"extra={sorted(set(bindings)-source_names)}")
        self.setObjectName(name)
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
            widget.show()

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
) -> SourceControlCanvas:
    """Place source controls; panel_width is surrounding DFM pn*Tools width."""
    if panel_width < max(x + w for _, _, x, _, w, _ in control_spec):
        raise ValueError("Source panel is narrower than its DFM controls")
    return SourceControlCanvas(parent, control_spec, bindings, name)
