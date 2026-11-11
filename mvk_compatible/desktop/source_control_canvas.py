"""Source-positioned Delphi controls on a responsive Qt page.

This module maps ONLY verified DFM logical pixel rectangles to Qt child
widgets.  It does not reproduce private bitmap resources, Delphi font
rasterisation, or device behaviour. Research models remain separate.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


def source_control_canvas(
    parent: QWidget,
    control_spec: Sequence[tuple[str, str, int, int, int, int]],
    bindings: Mapping[str, QWidget],
    *,
    name: str,
    panel_width: int = 177,
) -> QWidget:
    """Lay out original controls with exact *logical* DFM coordinates.

    Original Delphi controls may overlap (e.g. spectrum lbSpecMean y327
    height145 and copy button y464).  A QVBoxLayout cannot represent this.
    This canvas puts widgets at source coordinates while the rest of the
    functioning Qt pages and callbacks stay intact.
    """
    actual = {entry[0] for entry in control_spec}
    if set(bindings) != actual:
        raise ValueError(
            f"Source controls mismatch for {name}: "
            f"missing={sorted(actual-set(bindings))}, "
            f"extra={sorted(set(bindings)-actual)}")
    height = max(top + h for _, _, _, top, _, h in control_spec) + 4
    canvas = QWidget(parent)
    canvas.setObjectName(name)
    canvas.setFixedSize(panel_width, height)
    for source_name, _, left, top, width, h in control_spec:
        control = bindings[source_name]
        control.setParent(canvas)
        control.setGeometry(left, top, width, h)
        control.setFixedSize(width, h)
        control.setProperty("originalDfmControlName", source_name)
        control.setProperty("originalDfmLogicalRect",
                            (left, top, width, h))
        if isinstance(control, QLabel):
            control.setAlignment(Qt.AlignCenter)
            control.setWordWrap(True)
        # Reparenting a hidden legacy model is not an implicit activation.
        # All widgets listed here are genuine source-visible controls.
        control.show()
    return canvas
