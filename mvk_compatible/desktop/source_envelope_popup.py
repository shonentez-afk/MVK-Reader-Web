"""Real two-column Qt presentation of original VCL popEnvelopeType.

The original _Unit128:00845900 divides 32 menu items after Tag19.
One QMenu is shared by bAdcEnvelopeType and bSpecEnvelopeType.

The host QMenu preserves the original public 32 QAction menu objects
(including each Tag, checked, enabled, triggered) for existing Core/Qt
integration, but visually displays a 20+12 QWidgetAction radio palette:
no disabled ghost-actions and no scroll-to-find the second octave column.
Nothing here computes FIR, calibrates a source or reads private files.
"""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMenu, QWidget, QWidgetAction, QGridLayout, QRadioButton,
)
from ..core.original_envelope_shared_menu import (
    COUNT, ORIGINAL_COLUMN_BREAK_TAG, ORIGINAL_MENU_COLUMN_COUNT,
    source_original_envelope_menu,
)


class OriginalSourceEnvelopeMenu(QMenu):
    """One native QWidgetAction, 32 independently enabled source Actions.

    Qt QAction becomes automatically disabled if setVisible(False).
    Therefore the source actions for Tag1..31 are NOT added as ghost
    native menu rows. They are ordinary live QAction models attached
    to this QObject, and the QWidgetAction radios are their visual
    counterparts. The public actions() exposes the original 32 source
    entries, as did the native VCL menu. native_actions() exposes the
    actual Qt base menu items to support nonvisual regression checks.
    """

    def __init__(self,parent=None):
        super().__init__(parent)
        self._source_actions=None
        self.source_palette=None

    def actions(self):
        if self._source_actions is None:
            return super().actions()
        return list(self._source_actions)

    def native_actions(self):
        return tuple(super().actions())

    def set_source_actions(self,entries):
        if self._source_actions is not None:
            raise ValueError("Source menu actions already registered")
        if len(entries)!=COUNT or entries[0] not in self.native_actions():
            raise ValueError("Original source menu action registry is malformed")
        self._source_actions=tuple(entries)


def build_source_envelope_popup(parent, *, on_select):
    """Return (same QMenu, 32 QAction, 32 visual radios, real two-col widget).

    Both original buttons should call QToolButton.setMenu(menu) with the
    returned SAME instance and QToolButton.InstantPopup.
    """
    if not callable(on_select):
        raise ValueError("Original shared filter requires a selection callback")
    menu=OriginalSourceEnvelopeMenu(parent)
    menu.setObjectName("popEnvelopeType")
    menu.setToolTipsVisible(True)
    palette=QWidget(menu)
    palette.setObjectName("sourceEnvelopeTwoColumnPalette")
    palette.setAutoFillBackground(True)
    grid=QGridLayout(palette)
    grid.setContentsMargins(8,5,8,5)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(0)
    entries=source_original_envelope_menu(
        selected_tag=0, sample_rate_hz=None,
        local_profile_available=False)
    if len(entries)!=COUNT or ORIGINAL_MENU_COLUMN_COUNT!=2:
        raise ValueError("Invalid original envelope popup layout contract")
    actions=[]
    radios=[]
    host_action=None

    def triggered_by_radio(action):
        # The click came from the widget inside the QMenu. Hide first to
        # exit the popup's nested event loop BEFORE a real GetSignal/FIR
        # and GetSpectrum computation changes the parent pages.
        if action.isEnabled():
            menu.hide()
            action.trigger()

    for item in entries:
        tag=item["tag"]
        if tag==0:
            action=QWidgetAction(menu)
            action.setText(item["caption"])
            menu.addAction(action)
            host_action=action
        else:
            # DO NOT call QMenu.addAction or setVisible(False) here:
            # Qt auto-disables invisible QAction even if setEnabled(True).
            # A nonregistered QAction remains fully operational and
            # is triggered by this item's REAL visible radio control.
            action=QAction(item["caption"],menu)
        action.setData(tag)
        action.setCheckable(True)
        action.triggered.connect(
            lambda checked=False, value=tag: on_select(value))
        radio=QRadioButton(item["caption"],palette)
        radio.setObjectName(f"sourceEnvelopeMenuTag{tag:02d}")
        radio.setMinimumWidth(150)
        radio.setMinimumHeight(22)
        radio.setAutoExclusive(True)
        radio.clicked.connect(
            lambda checked=False, source_action=action:
                triggered_by_radio(source_action))
        grid.addWidget(
            radio,item["source_menu_row"],item["source_menu_column"])
        actions.append(action)
        radios.append(radio)
    if host_action is None or len(actions)!=COUNT or len(radios)!=COUNT:
        raise ValueError("Original VCL 32 radio items not fully constructed")
    host_action.setDefaultWidget(palette)
    menu.source_palette=palette
    menu.set_source_actions(actions)
    # Just one QMenu native row: the actual two-column radio palette.
    if len(menu.native_actions())!=1:
        raise ValueError("Qt menu unexpectedly contains duplicate native entries")
    return menu,tuple(actions),tuple(radios),palette


def sync_source_envelope_popup(*, entries, actions, radios):
    """Mirror source checked/enabled/caption to both representations."""
    if len(entries)!=COUNT or len(actions)!=COUNT or len(radios)!=COUNT:
        raise ValueError("Original popup action count changed")
    checked=[]
    for item,action,radio in zip(entries,actions,radios):
        tag=item["tag"]
        if action.data()!=tag:
            raise ValueError("Source envelope popup Tag mismatch")
        caption=item["caption"]
        allowed=bool(item["qt_selectable_without_fabricated_fir"])
        action.setText(caption)
        action.setChecked(bool(item["checked"]))
        action.setEnabled(allowed)
        radio.setText(caption)
        radio.setEnabled(allowed)
        radio.setChecked(bool(item["checked"]))
        radio.setToolTip(action.toolTip())
        if item["checked"]:
            checked.append(tag)
    if len(checked)!=1:
        raise ValueError("Original shared envelope menu radio has no unique Tag")
    return checked[0]
