"""Working two-column Qt presenter for original Delphi popEnvelopeType.

Original _Unit128:008458FC..00845913 creates 32 radio items and starts
the second column at Tag20. In Qt, the 32 enabled/checked source actions
are independent QAction models, and one QWidgetAction presents a 20+12
QRadioButton grid. Both original PageAdc/PageSpectrum buttons reference
the SAME QMenu instance. The menu contains no hidden native duplicates.

The menu host widget MUST be assigned with setDefaultWidget() BEFORE
QMenu.addAction(widget_host): Qt requests widgets when an action is
registered and will not instantiate a late-assigned defaultWidget.
No source FIR coefficients, source BIN bytes or device calls live here.
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
    """QMenu with 32 source QAction models and one native radio-grid host.

    Qt disables an added QAction when setVisible(False), which would
    silently disable the real original source filters. Instead, 32
    independent actions are owned by this menu but not registered as
    native rows; QRadioButton pixels delegate to those same actions.

    actions(): original 32 source Tag items for existing Core/Qt contracts.
    native_actions(): one registered QWidgetAction hosting visible rows.
    """

    def __init__(self,parent=None):
        super().__init__(parent)
        self._source_actions=None
        self.source_palette=None
        self.widget_host_action=None

    def actions(self):
        if self._source_actions is None:
            return super().actions()
        return list(self._source_actions)

    def native_actions(self):
        return tuple(super().actions())

    def set_source_actions(self,entries):
        if self._source_actions is not None:
            raise ValueError("Source menu actions already registered")
        if (len(entries)!=COUNT or self.widget_host_action is None
                or self.native_actions()!=(self.widget_host_action,)):
            raise ValueError("Original source menu action registry is malformed")
        self._source_actions=tuple(entries)


def build_source_envelope_popup(parent, *, on_select):
    """Return (real QMenu, 32 source QAction, 32 radio widgets, palette)."""
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

    def triggered_by_radio(action):
        # Exit the popup's nested event loop BEFORE expensive real
        # GetSignal/FIR/GetSpectrum calculations can resize the pages.
        if action.isEnabled():
            menu.hide()
            action.trigger()

    for item in entries:
        tag=item["tag"]
        # The logical Source Tag is always an independently enabled model
        # action, not a native row marked invisible (which Qt disables).
        action=QAction(item["caption"],menu)
        action.setData(tag)
        action.setCheckable(True)
        action.triggered.connect(
            lambda checked=False,value=tag:on_select(value))
        radio=QRadioButton(item["caption"],palette)
        radio.setObjectName(f"sourceEnvelopeMenuTag{tag:02d}")
        radio.setMinimumWidth(150)
        radio.setMinimumHeight(22)
        radio.setAutoExclusive(True)
        radio.clicked.connect(
            lambda checked=False,source_action=action:
                triggered_by_radio(source_action))
        grid.addWidget(
            radio,item["source_menu_row"],item["source_menu_column"])
        actions.append(action)
        radios.append(radio)

    if len(actions)!=COUNT or len(radios)!=COUNT:
        raise ValueError("Original 32 filter radio items not fully constructed")
    # Critical sequence for QWidgetAction in a QMenu: setDefaultWidget
    # BEFORE adding the action to its action container.
    host=QWidgetAction(menu)
    host.setDefaultWidget(palette)
    menu.addAction(host)
    menu.source_palette=palette
    menu.widget_host_action=host
    menu.set_source_actions(actions)
    return menu,tuple(actions),tuple(radios),palette


def sync_source_envelope_popup(*, entries, actions, radios):
    """Mirror source checked/enabled/caption to both logical and UI rows."""
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
