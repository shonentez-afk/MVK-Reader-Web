"""Stage111Z31BS visible original pnMeasure / pnMeasureControls.

Geometry, five original objectNames and handlers follow private
Projects/mvkform.dfm and _Unit128.pas. Current Native R6.1 is NOT a
writable TMVKThread replacement: source FreezeUpdate now gates the actual
Go 2M ring via local QProcess stdin; RAW acquisition continues without
hardware commands. SetRate stays opt-in, table is a verified local
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
    TABLE_PREFIX,export_verified_table_csv,
)
from ..core.original_measurement_mode import source_connection_display
from ..core.original_mode2_rate_menu_source import (
    SOURCE_DEFAULT_MENU_TAG, original_rate_menu_items,
    source_initial_rate_provenance,
)
from ..core.original_measurement_pipeline import measurement_operator_policy
from ..core.original_mode2_live_health import original_dpi_geometry
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
            "bFreezeUpdate":"Пауза приема",
            "bSampleRate":"ЧД —",
            "bWriteTable":"Запись таблицы",
            "bWriteAdc":"Запись сигнала",
            "bWriteValues":"Запись значений",
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
            "Оригинал _Unit128:0084DEA4 переключает FreezeUpdate. "
            "TCP и сохранение RAW продолжаются; TMVKThread не обновляет "
            "кольца ADC/TACH, регистры PARAM, AUX и WriteValues 0x3100 "
            "до снятия паузы (_Unit125:0080850C). Локальная FREEZE "
            "передаётся тому же Go-приёмнику без команды прибору.")
        self.freeze.clicked.connect(self._toggle_freeze)
        self.rate=self.buttons["bSampleRate"]
        self.rate_menu=QMenu(self.rate)
        self.rate_menu.setObjectName("popSampleRate")
        self.rate.setMenu(self.rate_menu)
        self.rate.setToolTip(
            "Оригинальные 5 частот 65536/32768/8192/2048/512 Гц "
            "точно прочитаны из IDP; исходный SetRate пока разрешён "
            "только в автономной модели. На кнопке показывается только "
            "реально наблюдаемая Fs Native/архива; изменения прибору нет.")
        self.buttons["bWriteTable"].clicked.connect(
            lambda:self._save_verified_table(filtered=False))
        self.buttons["bWriteTable"].setToolTip(
            "Исходный _Unit128:0084E020: TABLE-yyyy-mm-dd--hh-nn-ss.csv. "
            "Записать проверенный офлайн VALUES текущего тика, не "
            "заменяя аппаратную TABLE и не вычисляя вымышленные DSP.")
        self.buttons["bWriteAdc"].clicked.connect(
            self._export_checked_adcs)
        self.buttons["bWriteAdc"].setToolTip(
            "Оригинал: _Unit128:0084E914 -> WriteData -> 10 флагов. "
            "При LIVE эта кнопка фиксирует границы подтверждённых "
            "отсчётов Go; после успешной проверки архива записываются "
            "выбранные локальные Float32, не исходные Delphi файлы. "
            "RAW сохраняется полностью, команды прибору не отправляются.")
        self.buttons["bWriteValues"].clicked.connect(
            lambda:self._save_verified_table(filtered=True))
        self.buttons["bWriteValues"].setToolTip(
            "Оригинал: _Unit128:0084E988 -> WriteValues -> 43/24/43/6 "
            "маски. При LIVE эта кнопка фиксирует границы реально "
            "подтверждённых AUX-тиков; после принятия Native ZIP создаётся "
            "локальный проверенный CSV, а не исходный Delphi WriteValues.")
        self.status=QLabel("Без подтверждённого источника",self.panel)
        self.status.setObjectName("lbStatus")
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.status.setMinimumWidth(72)
        lay.addWidget(self.status,1)
        # Two independent source images: green when validated; red on
        # an actual error. The missing connection never gets a green icon.
        self.status_icons=QWidget(self.panel)
        self.status_icons.setObjectName("pnSourceStatusIcons")
        self.status_icons.setFixedSize(33,41)
        self.indicator=QLabel("○",self.status_icons)
        self.indicator.setObjectName("imStatusGood")
        self.indicator.setGeometry(0,0,33,41)
        self.indicator.setAlignment(Qt.AlignCenter)
        self.bad_indicator=QLabel("●",self.status_icons)
        self.bad_indicator.setObjectName("imStatusBad")
        self.bad_indicator.setGeometry(0,0,33,41)
        self.bad_indicator.setAlignment(Qt.AlignCenter)
        self.bad_indicator.hide()
        lay.addWidget(self.status_icons,0)
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
        # Original _Unit128:0084DEA4 toggles TMVKThread.FreezeUpdate.
        # Go receives an in-memory gate change over EXISTING QProcess
        # stdin (not instrument TCP) and confirms it in the next status.
        # Without an active Native process, this remains render-only.
        dlg=getattr(self.window,"_native_dialog",None)
        active=bool(dlg is not None and
            getattr(dlg,"source_freeze_control_active",lambda:False)())
        if active:
            try:
                dlg.send_source_freeze(self.state.frozen)
            except (ValueError,RuntimeError,OSError) as exc:
                # Never claim that the operator's source storage freeze
                # occurred when local Go failed to accept the command.
                self.state=self.state.toggle_freeze()
                self.window._source_live_view_frozen=self.state.frozen
                self.window.statusBar().showMessage(
                    "FreezeUpdate не принят приёмником: "+str(exc))
                self.render()
                return
        trace=getattr(self.window,"_source_mode2_runtime",None)
        if trace is not None and trace.capture_started and not trace.finished:
            trace.set_source_preview_freeze(self.state.frozen)
            self.window._sync_source_mode2_runtime()
        self.render()
        if not self.state.frozen and self.window._live_active:
            # Render the NEWEST verified ring after thaw; never replay
            # stale source pointer or reset live recorder.
            self.window._render_live_wave()
            self.window._render_live_spectrum()

    def _export_checked_adcs(self):
        if self.state.mode=="live" and self.window._live_active:
            return self._toggle_live_write("data")
        if (self.state.mode!="offline" or
                self.window.session is None or
                self.window._live_active):
            return
        # This is the EXISTING verified PageFile local Save action;
        # NEVER try to toggle TMVKThread.WriteData.
        return self.window.original_shell._export_selected_file_source()

    def _toggle_live_write(self,kind):
        """One REAL source button action, no extra research controls."""
        try:
            receipt=self.window.source_write_toggle(kind)
        except (ValueError,KeyError,RuntimeError,TypeError) as exc:
            # No modal dialog can implicitly approve device commands.
            self.window.statusBar().showMessage(
                "Исходная запись отклонена: "+str(exc))
            self.render()
            return None
        self.render()
        if receipt is not None:
            self.panel.setProperty("sourceOriginalWriteStageReceipt",receipt)
        return receipt

    def _save_verified_table(self,*,filtered):
        if filtered and self.state.mode=="live" and self.window._live_active:
            return self._toggle_live_write("values")
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
        live=(mode=="live")
        requested=bool(self.window._measurement_mode_selected)
        offline=(mode=="offline" and not requested)
        # Original pnMeasure design-time Visible=False and the accepted
        # operator PageSpectrum archive screenshot shows ONLY pnView time,
        # not the 53px five-button device toolbar. In a connected Native
        # LIVE preview, source pnMeasure is available; in OFFLINE archive
        # it is available only when F12 enables compatible technical UI.
        skin=getattr(self.window,"original_visual_skin",None)
        technical=bool(skin is None or skin.technical)
        flow=getattr(self.window,"_offline_flow",None)
        selection=getattr(
            getattr(self.window,"original_shell",None),
            "file_record_selection",None)
        has_channels=bool(selection and selection.checked("channels"))
        has_values=bool(selection and (
            selection.checked("spec") or selection.checked("values")))
        policy=measurement_operator_policy(
            ui_mode=mode,mode2_selected=requested,
            capture_active=bool(self.window._live_active),
            technical_ui=technical,
            native_archive_available=bool(
                flow is not None and not flow.direct_bin),
            has_channels=has_channels,has_values=has_values,
            stop_requested=bool(self.window._measurement_exit_requested))
        self.panel.setVisible(policy.panel_visible)
        self.panel.setProperty(
            "sourceRuntimeMeasurePanelVisible",policy.panel_visible)
        self.panel.setProperty(
            "sourceOriginalMeasureCorePolicy",policy.receipt())
        # Source mvkform.dfm uses PixelsPerInch=96. Qt owns the actual
        # scaling; do not resize the DFM logical button rectangles at
        # Windows 150 percent (144 physical DPI).
        self.panel.setProperty(
            "sourceOriginalDfmDpiReceipt",
            original_dpi_geometry(self.panel.devicePixelRatioF()))
        self.panel.setProperty(
            "sourceOfflineMeasureCommandsRemainLocalOnly",True)
        self.freeze.setEnabled(policy.freeze_preview_enabled)
        self.freeze.blockSignals(True)
        try:
            self.freeze.setChecked(live and state.frozen)
        finally:
            self.freeze.blockSignals(False)
        self.freeze.setText("Продолжить приём" if state.frozen
                            else "Пауза приема")
        dlg=getattr(self.window,"_native_dialog",None)
        tx_enabled=bool(live and dlg is not None and
                        getattr(dlg,"source_rate_tx_active",lambda:False)()
                        and not self.window._measurement_exit_requested)
        self.rate.setEnabled(policy.rate_inspection_enabled)
        self.rate.setToolTip(
            "Изменить ЧД прибора через исходную SetRate: отдельное разрешение получено; "
            "будет отправлено 36 байт по существующему соединению."
            if tx_enabled else
            "Исходные значения частот восстановлены. Реальная SetRate отключена; "
            "включить её можно только при отдельном разрешении подключения.")
        self.rate_menu.clear()
        hz=state.observed_sample_rate_hz if (live or offline) else None
        self.rate.setText("ЧД "+str(hz)+" Гц" if hz else "ЧД —")
        # Reproduce the FIVE real TMenuItem captions/Tag values in exact
        # Source Insert(0) order. The independent original thread code
        # was 0x309; mRate1Click initially selects Items[0] = 65536.
        # Disabled actions are intentional: Go is passive/read-only and
        # changing a Qt menu must NOT pretend to configure the instrument.
        trace=getattr(self.window,"_source_mode2_runtime",None)
        selected=(
            trace.command_model.source_rate_code
            if trace is not None and trace.source_initial_rate_queued_offline
            else SOURCE_DEFAULT_MENU_TAG)
        source_tx=(getattr(self.window,"_source_mode2_runtime",None))
        proof=getattr(source_tx,"source_tx_observed",None) if source_tx is not None else None
        if proof is not None and proof.get("source_tx_last_rate_hz"):
            selected=proof["source_tx_last_rate_hz"]
        for option in original_rate_menu_items():
            action=self.rate_menu.addAction(option.caption)
            action.setCheckable(True)
            action.setChecked(option.tag==selected)
            action.setProperty("sourceOriginalRateTag",option.tag)
            action.setProperty("sourceOriginalRateMenuIndex",option.position)
            action.setProperty("sourceRateChangesDisabledForNative",not tx_enabled)
            action.setEnabled(tx_enabled)
            if tx_enabled:
                action.triggered.connect(
                    lambda checked=False,rate=option.tag:
                    self.window.source_rate_selected(rate))
        self.rate_menu.setProperty(
            "sourceOriginalRateMenuProvenance",source_initial_rate_provenance())
        self.rate_menu.setProperty("sourceObservedNativeHz",hz)
        self.rate_menu.setProperty("sourceSelectedOriginalRateTag",selected)
        self.buttons["bWriteTable"].setEnabled(
            policy.local_table_enabled)
        # Original Delphi start/stop buttons are now linked to the
        # actual read-only Native session's verified counters. In a
        # synthetic preview without trusted transport, keep DISABLED
        # as before. This does not enable TMVKThread device writes.
        writer=getattr(self.window,"_source_live_writer",None)
        source_ready=bool(live and writer is not None
                          and writer.trustworthy
                          and not self.window._measurement_exit_requested
                          and not (trace is not None and
                                   trace.status_cells.system_error_latched))
        source_plan=getattr(
            getattr(self.window,"original_shell",None),
            "live_file_plan",None)
        source_has_data=bool(
            source_plan is not None and any(source_plan.channels))
        source_has_values=bool(
            source_has_data and source_plan is not None and
            (any(source_plan.spec) or any(source_plan.values)))
        data_requested=bool(
            writer is not None and writer.receipt()["write_data_requested"])
        values_requested=bool(
            writer is not None and writer.receipt()["write_values_requested"])
        self.buttons["bWriteAdc"].setEnabled(
            policy.local_adc_enabled or
            (source_ready and (source_has_data or data_requested)))
        self.buttons["bWriteValues"].setEnabled(
            policy.local_values_enabled or
            (source_ready and (source_has_values or values_requested)))
        self.buttons["bWriteAdc"].setText(
            "Завершить запись сигнала" if live and data_requested
            else "Запись сигнала")
        self.buttons["bWriteValues"].setText(
            "Завершить запись значений" if live and values_requested
            else "Запись значений")
        self.panel.setProperty(
            "sourceOriginalWriteStageReceipt",
            writer.receipt() if writer is not None else None)
        if requested or live:
            state_view=self.window.measurement_connection_display()
            # Native Go is passive: an incoming DENIED is a real instrument
            # reply, but never an ACK/error for a command sent by this app.
            trace=getattr(self.window,"_source_mode2_runtime",None)
            read_proof=(
                trace.receive_evidence.receipt() if trace is not None
                else {})
            denied=bool(
                read_proof.get("denial_seen") and
                not self.window._measurement_exit_requested and
                not self.window._measurement_connection_error)
            source_cells=trace.status_cells.receipt() if trace is not None else {}
            system_error=bool(
                source_cells.get("source_system_error_latched_until_new_capture"))
            code=source_cells.get("source_statuscells0_uint32")
            error_text=(
                f"Системная ошибка прибора (0x{code:08X})"
                if system_error and isinstance(code,int) and code>0
                else "Системная ошибка прибора (ранее подтверждена)")
            tx_bytes=(trace.source_tx_observed.get("source_go_bytes_actually_sent",0)
                      if trace is not None and trace.source_tx_observed is not None
                      else 0)
            self.status.setText(
                error_text if system_error
                else ("Прибор: отказ операции после отправки SetRate (ACK без ID)"
                      if tx_bytes else
                      "Прибор: отказ операции (наш клиент команд не отправлял)")
                if denied else state_view.text)
            bad=(state_view.indicator=="bad" or denied or system_error)
            self.bad_indicator.setStyleSheet("color:#cc3636")
            self.bad_indicator.setVisible(bad)
            self.indicator.setVisible(not bad)
            self.indicator.setText(
                "●" if state_view.transport_verified else "○")
            self.indicator.setStyleSheet(
                "color:#459a4c" if state_view.transport_verified
                else "color:#888888")
            tx=trace.source_tx_observed if trace is not None else None
            self.status.setToolTip(
                (f"Исходная SetRate: реально отправлено {tx['source_go_bytes_actually_sent']} байт; "
                 f"команд {tx['source_tx_sent_commands']}; "
                 "входящие ACK не имеют ID и не подтверждают конкретную SetRate. "
                 if tx is not None and tx["source_go_bytes_actually_sent"]>0
                 else "Исходная SetRate (36 байт): условие Stage1 подтверждено; "
                 "Go физически отправил 0 байт. "
                 if tx is not None and tx["source_setrate_dispatch_candidate"]
                 else "")+
                ("Native R6.1: исходная SetRate физически отправлялась; "
                 if tx_bytes else "Пассивный Native R6.1: исходящих команд нет. ")+
                "Транспортный статус не является приборным регистром StatusIsError. "
                "ACK/отказ входящего протокола не имеют transaction ID: "
                "нельзя приписывать их конкретной SetRate без проверки. "
                "Системная ошибка StatusCells[0] выводится только при "
                "полученных из Go двух валидных 16-битных регистрах.")
        else:
            self.status.setText(
                "Просмотр сохранённого измерения" if offline
                else "Нет подключения к прибору")
            self.indicator.setText("○")
            self.indicator.setStyleSheet("color:#888888")
            self.bad_indicator.hide()
            self.indicator.show()
