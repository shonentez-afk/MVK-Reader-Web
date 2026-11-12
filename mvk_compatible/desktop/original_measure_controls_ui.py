"""Stage111Z31BS visible original pnMeasure / pnMeasureControls.

Geometry, five original objectNames and handlers follow private
Projects/mvkform.dfm and _Unit128.pas. Current Native R6.1 is NOT a
writable TMVKThread replacement: Freeze is for preview RENDER only,
sample rate is observed (SetRate not sent), table is a verified local
CSV and channel/VALUES original device toggles are OFF during LIVE.
Offline source-only actions are labelled explicitly, not represented
as original native recorder behavior.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,QHBoxLayout,QPushButton,QLabel,QMenu,QFileDialog,QSizePolicy,
)

from ..core.original_measure_controls import (
    OriginalMeasureState,DFM_BUTTONS,DFM_MEASURE_HEIGHT,
    ORIGINAL_RATE_RADIO_ITEMS,TABLE_PREFIX,export_verified_table_csv,
)
from ..core.original_pagefile_recording import OriginalPageFileSelection


class OriginalMeasureControls:
    """One real Qt owner for the original bottom measurement controls."""

    def __init__(self,window):
        self.window=window
        self.state=OriginalMeasureState()
        self.panel=QWidget(window)
        self.panel.setObjectName("pnMeasure")
        self.panel.setFixedHeight(DFM_MEASURE_HEIGHT)
        lay=QHBoxLayout(self.panel)
        lay.setContentsMargins(6,6,6,6)
        lay.setSpacing(6)
        self.controls=QWidget(self.panel)
        self.controls.setObjectName("pnMeasureControls")
        self.controls.setFixedSize(843,41)
        lay.addWidget(self.controls,0)
        self.buttons={}
        names={
            "bFreezeUpdate":"Пауза",
            "bSampleRate":"Частота",
            "bWriteTable":"Таблица CSV",
            "bWriteAdc":"АЦП · локально",
            "bWriteValues":"VALUES · CSV",
        }
        for name,x,y,w,h,tag,order in DFM_BUTTONS:
            btn=QPushButton(names[name],self.controls)
            btn.setObjectName(name)
            btn.setGeometry(x,y,w,h)
            btn.setProperty("SourceDFMTag",tag)
            btn.setProperty("SourceDFMTabOrder",order)
            self.buttons[name]=btn
        self.freeze=self.buttons["bFreezeUpdate"]
        self.freeze.setCheckable(True)
        self.freeze.setToolTip(
            "Оригинал _Unit128:0084DEA4 переключает "
            "TMVKThread.FreezeUpdate. Здесь пауза ТОЛЬКО экрана Native "
            "LIVE PREVIEW: RAW запись и получение данных продолжаются.")
        self.freeze.clicked.connect(self._toggle_freeze)
        self.rate=self.buttons["bSampleRate"]
        self.rate_menu=QMenu(self.rate)
        self.rate_menu.setObjectName("popSampleRate")
        self.rate.setMenu(self.rate_menu)
        self.rate.setToolTip(
            "Оригинал конструирует 5 пунктов из gvar_008D2F7C и вызывает "
            "TMVKThread.SetRate. Их значения из IDP/runtime ещё не "
            "подтверждены. Здесь показывается только проверенная Fs "
            "открытого файла или Native LIVE, без установки прибору.")
        self.buttons["bWriteTable"].clicked.connect(
            lambda:self._save_verified_table(filtered=False))
        self.buttons["bWriteTable"].setToolTip(
            "Исходный _Unit128:0084E020: TABLE-yyyy-mm-dd--hh-nn-ss.csv. "
            "Записать проверенный офлайн VALUES текущего тика, не "
            "заменяя аппаратную TABLE и не вычисляя вымышленные DSP.")
        self.buttons["bWriteAdc"].clicked.connect(
            self._export_checked_adcs)
        self.buttons["bWriteAdc"].setToolTip(
            "Исходный _Unit128:0084E914 переключает TMVKThread.WriteData. "
            "Здесь — безопасное сохранение выбранных исходных "
            "BIN/TSXML из готового файла, без аппаратных команд.")
        self.buttons["bWriteValues"].clicked.connect(
            lambda:self._save_verified_table(filtered=True))
        self.buttons["bWriteValues"].setToolTip(
            "Исходный _Unit128:0084E988 переключает "
            "TMVKThread.WriteValues. Здесь — только локальный CSV "
            "из выбранных подтверждённых VALUES/SPEC и тика.")
        self.status=QLabel("Без подтверждённого источника",self.panel)
        self.status.setObjectName("lbStatus")
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.status.setMinimumWidth(72)
        lay.addWidget(self.status,1)
        self.indicator=QLabel("●",self.panel)
        self.indicator.setObjectName("imStatusGood")
        self.indicator.setFixedSize(33,41)
        self.indicator.setAlignment(Qt.AlignCenter)
        self.indicator.setToolTip(
            "Круг не означает доказанное подключение исходной TMVKThread.")
        lay.addWidget(self.indicator,0)
        self.render()

    def sync_source(self):
        """Only one flow owns the offline toolbar; live is separate."""
        if self.window._live_active:
            return
        flow=getattr(self.window,"_offline_flow",None)
        if flow is None or self.window.session is None:
            self.state=OriginalMeasureState()
        else:
            flow.require_session(self.window.session)
            self.state=OriginalMeasureState().open_offline(flow)
        self.render()

    def begin_live(self):
        self.state=self.state.begin_live()
        self.window._source_live_view_frozen=False
        self.render()

    def observe_preview(self,preview):
        self.state=self.state.accept_preview(preview)
        self.render()

    def invalidate_preview(self):
        self.state=self.state.invalidate_preview()
        self.render()

    def end_live(self):
        self.state=self.state.finish()
        self.window._source_live_view_frozen=False
        self.render()

    def _toggle_freeze(self):
        try:
            self.state=self.state.toggle_freeze()
        except ValueError:
            self.render()
            return
        self.window._source_live_view_frozen=self.state.frozen
        self.render()
        if not self.state.frozen and self.window._live_active:
            # Render the NEWEST verified ring after thaw; never replay
            # stale source pointer or reset live recorder.
            self.window._render_live_wave()
            self.window._render_live_spectrum()

    def _export_checked_adcs(self):
        if (self.state.mode!="offline" or
                self.window.session is None or
                self.window._live_active):
            return
        # This is the EXISTING verified PageFile local Save action;
        # NEVER try to toggle TMVKThread.WriteData.
        return self.window.original_shell._export_selected_file_source()

    def _save_verified_table(self,*,filtered):
        if (self.state.mode!="offline" or
                self.window.session is None or self.window._live_active):
            return
        flow=self.window._current_offline_flow()
        if flow.direct_bin:
            return
        selection=None
        if filtered:
            selection=self.window.original_shell.file_record_selection
            if not isinstance(selection,OriginalPageFileSelection):
                return
        proposed=TABLE_PREFIX+datetime.now().strftime(
            "%Y-%m-%d--%H-%M-%S")+".csv"
        dest,_=QFileDialog.getSaveFileName(
            self.panel,"Новая локальная таблица проверенных VALUES",
            proposed,"CSV (*.csv)")
        if not dest:return
        try:
            report=export_verified_table_csv(
                flow,dest,selection=selection)
        except (OSError,ValueError,UnicodeError,KeyError) as exc:
            self.window.original_window_man.spawn_error(
                "Таблица не сохранена: "+str(exc))
            return
        self.status.setText(
            f"Локально сохранено: {report['rows']} исходных строк "
            f"· {len(report['channels'])} АЦП · не TMVKThread")
        self.window.statusBar().showMessage(
            "PageFile TABLE: проверенный локальный CSV, прибор не менялся")
        return report

    def render(self):
        state=self.state
        mode=state.mode
        self.panel.setVisible(mode!="idle")
        live=(mode=="live")
        offline=(mode=="offline")
        self.freeze.setEnabled(live)
        self.freeze.blockSignals(True)
        try:
            self.freeze.setChecked(live and state.frozen)
        finally:
            self.freeze.blockSignals(False)
        self.freeze.setText("Возобновить" if state.frozen else "Пауза")
        self.rate.setEnabled(mode!="idle")
        self.rate_menu.clear()
        hz=state.observed_sample_rate_hz
        self.rate.setText("Fs: "+str(hz)+" Гц" if hz else "Частота: —")
        seen=self.rate_menu.addAction(
            f"Подтверждённая Fs: {hz} Гц" if hz else
            "Fs: нет проверенного источника")
        seen.setEnabled(False)
        missing=self.rate_menu.addAction(
            f"Исходное меню: {ORIGINAL_RATE_RADIO_ITEMS} "
            "Tag из gvar_008D2F7C (не исследованы)")
        missing.setEnabled(False)
        self.rate_menu.addAction(
            "Управление TMVKThread.SetRate недоступно").setEnabled(False)
        flow=getattr(self.window,"_offline_flow",None)
        is_native=bool(offline and flow is not None
                       and not flow.direct_bin)
        selection=getattr(
            getattr(self.window,"original_shell",None),
            "file_record_selection",None)
        has_channels=bool(selection and selection.checked("channels"))
        has_values=bool(selection and (
            selection.checked("spec") or selection.checked("values")))
        self.buttons["bWriteTable"].setEnabled(is_native)
        self.buttons["bWriteAdc"].setEnabled(
            offline and has_channels)
        self.buttons["bWriteValues"].setEnabled(
            is_native and has_channels and has_values)
        if live:
            self.status.setText(
                "LIVE R6.1 · только просмотр" +
                (" · пауза экрана" if state.frozen else
                 " · приёмник продолжает запись"))
        elif offline:
            self.status.setText(
                "ОФЛАЙН · таблицы/файлы" +
                (" · DSP нет" if not is_native else
                 " · VALUES проверены"))
        else:
            self.status.setText("Без подключённого прибора/файла")
        self.indicator.setText(
            "●" if live else "○")
        self.indicator.setStyleSheet(
            "color:#b38a17" if live else "color:#777777")
