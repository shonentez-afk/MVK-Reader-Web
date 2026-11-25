"""Stage111Z31BQ: source PageConfig with actual local Load/Edit/Save flow.

Source DFM has two tcConfig tabs (Channels, Alarms) and a sibling
tabConfigBasic grid in non-channel Mode. We preserve exactly that.
bConfigLoad and bConfigSave operate on a selected local original text file;
Tmvkeditform edits validated source fields in an immutable draft. Hardware
Download requires explicit consent; Upload stays unavailable. Reset loads only local defaults.
"""
from __future__ import annotations

import hashlib

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import (QFileDialog,QLabel,QPushButton,QTableWidget,QTableWidgetItem,
    QTabWidget,QMenu,QInputDialog,QLineEdit,QDialog)

from ..core.original_config_readonly import (
    FIELDS, UNKNOWN, empty_original_config_inspection,
    inspect_original_local_config, alarm_config_register,
)
from ..core.original_language_source import source_localize
from ..core.original_config_semantics import (
    source_section_rows,section_fields,SOURCE_ADVANCED_OPTIONS,
    SOURCE_CONFIG_ALARM_OPTIONS,
)
from ..core.original_config_idp_tables import source_type_description
from ..core.original_config_input_draft import (
    SourceInputRejected, encode_source_text,
)
from ..core.original_config_local_workflow import OriginalLocalConfigWorkspace
from ..core.original_task0_config_live import (
    original_task0_field_text,source_original_default_config_path,
)
from .original_value_edit_dialog import OriginalValueEditDialog


class OriginalConfigReadOnlyPanel(QObject):
    def __init__(self,page):
        super().__init__(page)
        self.page=page
        self.channel_table=page.findChild(QTableWidget,"tabConfigChannels")
        self.alarm_table=page.findChild(QTableWidget,"tabConfigAlarms")
        self.basic_table=page.findChild(QTableWidget,"tabConfigBasic")
        self.source_note=page.findChild(QLabel,"sourceConfigEvidence")
        self.load_button=page.findChild(QPushButton,"bConfigLoad")
        self.save_button=page.findChild(QPushButton,"bConfigSave")
        self.download_button=page.findChild(QPushButton,"bConfigDownload")
        self.upload_button=page.findChild(QPushButton,"bConfigUpload")
        self.reset_button=page.findChild(QPushButton,"bConfigReset")
        self._task0_receipt=None
        self._task0_dialog=None
        self._task0_ip_epoch=0
        self.workspace=None
        self.selected_adc=1
        self.page_tabs=page.findChild(QTabWidget,"tcConfig")
        self.source_mode=6
        self.document=empty_original_config_inspection()
        if any(x is None for x in (self.channel_table,self.alarm_table,
                                   self.basic_table,self.source_note,
                                   self.load_button,self.save_button,
                                   self.download_button,self.page_tabs)):
            raise ValueError("Missing source PageConfig DFM control")
        self.load_button.setEnabled(True)
        self.load_button.setToolTip(
            "Открыть ТОЛЬКО локальный исходный текстовый конфигурационный "
            "файл для чтения. Не загружает в прибор и не редактирует регистры.")
        self.load_button.clicked.connect(self.choose_file)
        self.save_button.setEnabled(False)
        self.save_button.setToolTip(
            "Сохранить НОВУЮ локальную текстовую конфигурацию по исходному "
            "TMvkCellList.SaveValuesToFile. Без команды прибору.")
        self.save_button.clicked.connect(self.choose_save_file)
        self.download_button.setToolTip(
            "Исходный Task0: чтение конфигурации с прибора по разрешённому TCP; "
            "никаких Flash, Reset, SetRate или Upload.")
        self.download_button.clicked.connect(self.download_device_config)
        if self.upload_button is not None:
            self.upload_button.setEnabled(False)
            self.upload_button.setToolTip(
                "Запись конфигурации в прибор отключена.")
        if self.reset_button is not None:
            self.reset_button.setEnabled(True)
            self.reset_button.setToolTip(
                "Восстановить локальные значения из DefaultConfig.txt. "
                "Прибор не опрашивается и не перезагружается.")
            self.reset_button.clicked.connect(self.confirm_local_defaults)
        self.channel_table.cellClicked.connect(self._select_channel)
        self.channel_table.cellDoubleClicked.connect(self._focus_channel_details)
        self.channel_fields=QTableWidget(0,4,page)
        self.channel_fields.setObjectName("sourceConfigSelectedAdcFields")
        self.channel_fields.setEditTriggers(QTableWidget.NoEditTriggers)
        self.channel_fields.setHorizontalHeaderLabels(
            ("Поле выбранного канала","Адрес","Тип","Локальное значение"))
        self.channel_fields.cellDoubleClicked.connect(self.show_channel_details)
        self.channel_fields.setMinimumHeight(125)
        self.channel_fields.setMaximumHeight(240)
        # Extra inspector lives OUTSIDE original 2-tab tcConfig; the actual
        # source DFM tabConfigChannels remains the authoritative 8-row grid.
        page.layout().insertWidget(2,self.channel_fields,1)
        self.channel_fields_caption=QLabel(
            "ADC1 · исходные поля. Двойной щелчок — локальный mvkeditform.",page)
        self.channel_fields_caption.setObjectName("sourceConfigSelectedAdcHint")
        page.layout().insertWidget(2,self.channel_fields_caption)
        self.page_tabs.currentChanged.connect(self._set_mode_visibility)
        self.discard_button=QPushButton("Отменить изменения локального файла",page)
        self.discard_button.setObjectName("discardLocalOriginalConfigDraft")
        self.discard_button.setToolTip(
            "Отменить ТОЛЬКО локальные несохранённые поля. "
            "Не сбрасывает конфигурацию прибора.")
        self.discard_button.clicked.connect(self.discard_local_changes)
        self.discard_button.setEnabled(False)
        page.layout().addWidget(self.discard_button)
        self.alarm_table.cellDoubleClicked.connect(self.show_alarm_details)
        self.basic_table.cellDoubleClicked.connect(self.show_basic_details)
        # Delphi's shared tabKeyPress converts Enter to OnDblClick.
        for table in (self.channel_table,self.channel_fields,
                      self.alarm_table,self.basic_table):
            table.installEventFilter(self)
            table.viewport().installEventFilter(self)
        # Extra source-audit action is a context menu, not an invented
        # original DFM button. It validates an ephemeral candidate only.
        self.basic_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.basic_table.customContextMenuRequested.connect(
            self._source_validation_context_menu)
        self.refresh()

    def eventFilter(self,watched,event):
        if (event.type()==QEvent.Type.KeyPress and
                event.key() in (Qt.Key_Return,Qt.Key_Enter)):
            for table,handler in (
                (self.channel_table,self._focus_channel_details),
                (self.channel_fields,self.show_channel_details),
                (self.alarm_table,self.show_alarm_details),
                (self.basic_table,self.show_basic_details),
            ):
                if watched in (table,table.viewport()):
                    if table.currentRow()>=0 and table.currentColumn()>=0:
                        handler(table.currentRow(),table.currentColumn())
                    return True
        return super().eventFilter(watched,event)

    def _focus_channel_details(self,row,column):
        self._select_channel(row,column)
        if self.channel_fields.rowCount():
            self.channel_fields.setCurrentCell(0,3)
            self.channel_fields.setFocus()

    def _task0_reading(self):
        return getattr(self._task0_dialog,"_mode",None)=="read"

    def _require_local_change_allowed(self):
        if self._task0_reading():
            raise ValueError("Сначала завершите чтение Task0.")

    def confirm_local_defaults(self):
        """00849CE0: confirmed, local DefaultConfig.txt only; no network."""
        window=self.page.window()
        if self._task0_reading():
            window.original_window_man.spawn_error("Сначала завершите чтение Task0.")
            return False
        box=window.original_window_man.create_query(
            "Восстановить локальные значения из DefaultConfig.txt? "
            "Несохранённые локальные изменения будут заменены. "
            "Записи в прибор и перезагрузки не будет.",
            "Сбросить настройки",yes=True,no=True,cancel=False)
        if box.exec()!=6:
            return False
        try:
            # Load and verify before changing the existing local workspace.
            # Keep the current draft if defaults cannot be read.
            workspace=OriginalLocalConfigWorkspace.load(
                source_original_default_config_path())
        except (ValueError,OSError,UnicodeError) as exc:
            window.original_window_man.spawn_error(
                "Не удалось загрузить локальный DefaultConfig.txt: "+str(exc))
            return False
        self.workspace=workspace
        self.document=workspace.current
        self._task0_receipt=None
        self.refresh()
        self.source_note.setText(
            "Восстановлены локальные параметры из DefaultConfig.txt. "
            "Прибор не опрашивался и не перезагружался.")
        return True

    @staticmethod
    def _cell(table,row,col,value,detail=None):
        item=QTableWidgetItem(str(value))
        item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
        if detail is not None:
            item.setData(Qt.UserRole,detail)
            item.setToolTip(
                "Исходный адрес "+detail["address"]+
                "; ключ "+detail["source_translation_key"]+
                ". Значения взяты только из локального файла; "
                "живой конфигурацией прибора не считаются.")
        table.setItem(row,col,item)

    def refresh(self):
        doc=self.document
        report=doc.report()
        channel_rows=doc.channel_rows()
        c=self.channel_table
        c.setColumnCount(5)
        c.setHorizontalHeaderLabels((
            source_localize("ConfigADC").display,
            "IDR регистр", "Локальные поля", "Ожидаемые поля",
            "Подтверждение прибора",
        ))
        c.setRowCount(len(channel_rows)+2)
        for r,channel in enumerate(channel_rows):
            for i,value in enumerate((
                f"ADC{channel['adc']}",channel["source_config_base"],
                channel["known_alarm_cells_in_file"],
                channel["expected_alarm_cells"],"НЕ подтверждено",
            )):
                self._cell(c,r,i,value)
        for i in range(1,3):
            fields,base=section_fields("tach",adc=i)
            present=sum(doc.value(base+f.offset) is not None for f in fields)
            for j,val in enumerate((f"TACH{i}",f"0x{base:04X}",present,
                                    len(fields),"НЕ подтверждено")):
                self._cell(c,7+i,j,val)

        a=self.alarm_table
        columns=("АЦП","Слот","Status RAW",*[
            source_localize(key).display for _,key,_ in FIELDS])
        a.setColumnCount(len(columns))
        a.setHorizontalHeaderLabels(columns)
        alarm_rows=doc.alarm_rows()
        a.setRowCount(len(alarm_rows))
        for r,entry in enumerate(alarm_rows):
            self._cell(a,r,0,f"ADC{entry['adc']}")
            self._cell(a,r,1,entry["slot"])
            self._cell(a,r,2,entry["raw_source_status_address"])
            for col,(key,language_key,_) in enumerate(FIELDS,3):
                info=entry["fields"][key]
                self._cell(a,r,col,info["raw_value"],detail=info)

        self._refresh_basic()
        self._refresh_channel_details()
        self._set_mode_visibility()
        self.load_button.setEnabled(not self._task0_reading())
        self.save_button.setEnabled(
            self.workspace is not None and not self._task0_reading())
        self.discard_button.setEnabled(bool(
            self.workspace and self.workspace.changed and not self._task0_reading()))
        total=report["parsed_cells"]
        count=report["alarm_registers_present"]
        if self.source_mode==6:
            summary=f"Из них {count}/512 в полях контроля."
        else:
            rows=source_section_rows(
                doc,"ip" if self.source_mode==4 else "calib")
            known=sum(r["observed_in_local_file"] for r in rows)
            summary=(f"Исходный Mode{self.source_mode}: "
                     f"{known}/{len(rows)} полей локального источника.")
        pending=(self.workspace.changed_count if self.workspace else 0)
        if self.source_mode==4 and self._task0_receipt is not None:
            checked=self._task0_receipt
            self.source_note.setText(
                f"Task0: {checked['confirmed_fields']} полей получены "
                "и независимо сверены с RAW и SHA256. "
                "Остальные поля остаются неизвестными; пароли скрыты. "
                "Advanced-поля показывают исходный ID и ключ локализации; "
                "оригинальный перевод Delphi не подтверждён. "
                "Flash, Reset и Upload не выполнялись.")
        else:
            self.source_note.setText(
                f"Локально прочитано {total} RAW значений. {summary} "
                f"Изменено в памяти: {pending}. "
                "Текущая конфигурация прибора НЕ подтверждена. "
                "Локальное сохранение доступно после загрузки; "
                "запись в прибор и физическая поверка отключены.")


    def _set_mode_visibility(self,*_):
        basic=self.source_mode in (4,5)
        self.page_tabs.setVisible(not basic)
        self.basic_table.setVisible(basic)
        # Task0 is the ONLY restored hardware configuration action.
        self.download_button.setEnabled(self.source_mode==4)
        if self.upload_button is not None:self.upload_button.setEnabled(False)
        show_channel=(not basic and self.page_tabs.currentIndex()==0)
        self.channel_fields_caption.setVisible(show_channel)
        self.channel_fields.setVisible(show_channel)

    def _select_channel(self,row,column=0):
        if type(row) is not int or not 0<=row<10:return
        self.selected_adc=row+1
        self._refresh_channel_details()

    def _selected_channel(self):
        return (("adc",self.selected_adc) if self.selected_adc<=8
                else ("tach",self.selected_adc-8))

    def _refresh_channel_details(self):
        section,channel=self._selected_channel()
        rows=source_section_rows(self.document,section,adc=channel)
        t=self.channel_fields
        t.setRowCount(len(rows))
        self.channel_fields_caption.setText(
            f"{section.upper()}{channel}: {len(rows)} полей исходного "
            "TMvkCellList. Двойной щелчок — редактор локального проекта.")
        for i,info in enumerate(rows):
            display=source_localize(info["source_key"]).display+info["source_suffix"]
            for col,value in enumerate((
                display,info["address"],
                str(info["cell_type_code"]),info["raw_value"])):
                self._cell(t,i,col,value)

    def _refresh_basic(self):
        table=self.basic_table
        if self.source_mode not in (4,5):
            table.setRowCount(0)
            return
        rows=source_section_rows(
            self.document,"ip" if self.source_mode==4 else "calib")
        table.setColumnCount(5)
        task0=(self._task0_receipt if self.source_mode==4 else None)
        table.setHorizontalHeaderLabels(
            ("Исходное поле","Адрес","IDR тип",
             "Получено / исходный ID" if task0 else "Локальный RAW",
             "Исходные пределы / список"))
        table.setRowCount(len(rows))
        for index,info in enumerate(rows):
            name=source_localize(info["source_key"]).display+info["source_suffix"]
            bounds=(f'{info["source_min"]}..{info["source_max"]}'
                    if info["source_min"] is not None else "")
            value=info["raw_value"]
            if task0 is not None:
                entry=task0["fields"].get(info["source_key"])
                if entry is not None:
                    value=original_task0_field_text(
                        info["source_key"],entry)
                elif info["source_key"]=="ConfigWifiPassword":
                    value="•••••••• (скрыто)"
            values=(name,info["address"],
                    f'{info["cell_type_code"]} ({info["source_format_char"]}, '
                    f'{info["source_storage_bytes"]} байт)',
                    value,bounds or info["advanced_kind"] or UNKNOWN)
            detail={"source_translation_key":info["source_key"],
                    "address":info["address"]}
            for col,value in enumerate(values):
                self._cell(table,index,col,value,
                           detail=detail if col==3 else None)

    def download_device_config(self):
        """Original bConfigDownloadClick: separate, consented Task0 read."""
        if self.source_mode!=4:return False
        window=self.page.window()
        if (getattr(window,"_measurement_mode_selected",False) or
                getattr(window,"_live_active",False)):
            window.original_window_man.spawn_error(
                "Сначала завершите измерение: Task0 требует отдельного TCP.")
            return False
        controller=window.original_start_controller
        if not controller.commit_ip():return False
        from .original_task0_download_dialog import OriginalTask0DownloadDialog
        if self._task0_dialog is not None and (
                getattr(self._task0_dialog,"_mode",None)=="read" or
                self._task0_dialog.isVisible()):
            self._task0_dialog.raise_()
            self._task0_dialog.activateWindow()
            return True
        if self.workspace is not None and self.workspace.changed:
            window.original_window_man.spawn_error(
                "Сохраните локальную конфигурацию или отмените её изменения.")
            return False
        dialog=OriginalTask0DownloadDialog(
            controller.workspace.device_ipv4,window)
        device_ip=controller.workspace.device_ipv4
        epoch=self._task0_ip_epoch
        def forward(callback):
            def on_signal(*args):
                # An asynchronous response cannot restore the previous IP.
                if (self._task0_dialog is dialog and
                        controller.workspace.device_ipv4==device_ip and
                        self._task0_ip_epoch==epoch):
                    callback(*args)
                elif self._task0_dialog is dialog and not self._task0_reading():
                    self.refresh()
            return on_signal
        dialog.readCompleted.connect(forward(self.apply_device_task0_read))
        dialog.readStarted.connect(forward(self.source_task0_read_started))
        dialog.readFailed.connect(forward(self.source_task0_read_failed))
        self._task0_dialog=dialog
        dialog.show()
        return True

    def source_task0_read_started(self):
        """Do not leave old device fields visible during a new TCP attempt."""
        self._task0_receipt=None
        self.workspace=None
        self.document=empty_original_config_inspection()
        self.refresh()
        self.source_note.setText(
            "Считывание Task0: старые значения прибора очищены. "
            "Нет подтверждённых данных нового TCP-сеанса.")

    def source_task0_read_failed(self,reason):
        """00849687..00849765: LOCAL DefaultConfig.txt fallback, never device."""
        if not isinstance(reason,str):
            reason="исходный Task0 не подтвердил конфигурацию"
        reason=reason[:220]
        self._task0_receipt=None
        self.workspace=None
        self.document=empty_original_config_inspection()
        self.refresh()
        fallback=source_original_default_config_path()
        if (fallback.is_file() and not fallback.is_symlink()):
            try:
                self.load_local_file(fallback)
            except (ValueError,OSError,UnicodeError):
                # Fail closed: do not display invalid or stale device fields.
                self.workspace=None
                self.document=empty_original_config_inspection()
                self.refresh()
                self.source_note.setText(
                    "Ошибка чтения Task0: "+reason+
                    ". Локальный DefaultConfig.txt повреждён; "
                    "конфигурация прибора НЕ известна.")
            else:
                self.source_note.setText(
                    "Ошибка чтения Task0: "+reason+
                    ". Загружен ТОЛЬКО локальный DefaultConfig.txt "
                    "из каталога приложения, как в оригинале. "
                    "ЭТО НЕ КОНФИГУРАЦИЯ ПОДКЛЮЧЁННОГО ПРИБОРА.")
        else:
            self.source_note.setText(
                "Ошибка чтения Task0: "+reason+
                ". Локальный DefaultConfig.txt отсутствует. "
                "Конфигурация прибора НЕ известна.")

    def apply_device_task0_read(self,proof):
        """Bind only independently RAW/SHA-verified Task0 register cells."""
        if (not isinstance(proof,dict) or
                proof.get("schema")!="MVK_SOURCE_TASK0_CONFIG_IP_READ_V1" or
                proof.get("source_original_task")!=0 or
                proof.get("read_only") is not True or
                proof.get("device_commands_sent") is not False or
                proof.get("original_delphi_byte_parity_verified") is not False or
                not isinstance(proof.get("fields"),dict)):
            raise ValueError("Task0: неверное подтверждение конфигурации")
        controller=self.page.window().original_start_controller
        if proof.get("device_ipv4")!=controller.workspace.device_ipv4:
            raise ValueError("Task0: текущий IP прибора отличается от ответа")
        if self.workspace is not None and self.workspace.changed:
            raise ValueError(
                "Сохраните или отмените локальные изменения перед Task0")
        self.workspace=None
        self.document=empty_original_config_inspection()
        self._task0_receipt=proof
        self.source_mode=4
        self.refresh()
        return self.basic_table.rowCount()

    def invalidate_task0_ip(self):
        """Called at the committed IP boundary, not only on reopening Mode4."""
        self._task0_ip_epoch+=1
        invalidate=getattr(self._task0_dialog,"invalidate_device_ip",None)
        if callable(invalidate):invalidate()
        had_proof=self._task0_receipt is not None
        self._task0_receipt=None
        if had_proof:
            self.refresh()
            self.source_note.setText(
                "IP изменён. Ответ Task0 от предыдущего прибора скрыт; "
                "текущая конфигурация не подтверждена.")

    def set_source_mode(self,mode):
        if type(mode) is not int or mode not in (4,5,6):
            raise ValueError("Only source Config Mode4/5/6 supported")
        if mode==4 and self._task0_receipt is not None:
            # An old TCP response can never be shown under a new edIpAddr.
            controller=getattr(self.page.window(),"original_start_controller",None)
            if (controller is None or
                    controller.workspace.device_ipv4!=
                    self._task0_receipt.get("device_ipv4")):
                self._task0_receipt=None
        self.source_mode=mode
        window=self.page.window()
        nav=getattr(window,"original_root_tabs",None)
        if nav is not None:
            for index in range(nav.count()):
                if nav.tabData(index)=="PageConfig":
                    # Actual Russian captions observed in original 1.0.47.
                    nav.setTabText(index,{
                        4:"Системные параметры",5:"Калибровочные значения",
                        6:"Параметры измерительных каналов",
                    }[mode])
                    break
        self.refresh()

    def basic_detail_dialog(self,row,column):
        if (self.source_mode not in (4,5) or
                type(row) is not int or type(column) is not int or
                not 0<=row<self.basic_table.rowCount() or column!=3):
            raise ValueError("Only local raw source field may be viewed")
        info=source_section_rows(
            self.document,"ip" if self.source_mode==4 else "calib")[row]
        hint=source_localize(info["source_key"])
        value=info["raw_value"]
        if self.source_mode==4 and self._task0_receipt is not None:
            entry=self._task0_receipt["fields"].get(info["source_key"])
            if entry is not None:
                value=original_task0_field_text(
                    info["source_key"],entry)
            elif info["source_key"]=="ConfigWifiPassword":
                value="•••••••• (скрыто)"
        return OriginalValueEditDialog(
            prompt=f'{hint.display}{info["source_suffix"]} ({hint.key})',
            value=value,units=info["address"],
            parent=self.page,read_only=True)

    def show_basic_details(self,row,column):
        if column!=3:return
        if self.workspace is None:
            self.basic_detail_dialog(row,column).exec()
            return
        section="ip" if self.source_mode==4 else "calib"
        fields,base=section_fields(section)
        if type(row) is not int or not 0<=row<len(fields):return
        f=fields[row]
        if f.key=="ConfigWifiPassword":
            self.page.window().original_window_man.spawn_error(
                "Пароль исходного прибора нельзя редактировать локально.")
            return
        self._prompt_edit_source_field(section,row,f,base+f.offset)

    @staticmethod
    def _choice_setup(advanced,value):
        if advanced is None:
            return {},value
        labels=[]
        raw_values=[]
        for option in advanced.values:
            try:
                label=source_localize(option.title).display
            except KeyError:
                label=option.title
            labels.append(f"{label} · 0x{option.id:08X}")
            raw_values.append(f"0x{option.id:08X}")
        try:
            value=f"0x{int(value,16):08X}"
        except (TypeError,ValueError):
            pass # An unknown ID is not selected or silently coerced.
        return {"choices":labels,"choice_values":raw_values},value

    def _prompt_edit_source_field(self,section,row,field,address,*,adc=None):
        if self.workspace is None:
            return
        current=self.document.value(address)
        text=current.literal if current is not None else ""
        options,text=self._choice_setup(
            SOURCE_ADVANCED_OPTIONS.get(field.advanced),text)
        box=OriginalValueEditDialog(
            prompt=source_localize(field.key).display+
                   " · локальное изменение (не прибор)",
            value=text,units=f"0x{address:04X}",
            parent=self.page,read_only=False,
            sensitivity_conversion=(section=="adc" and row==0),
            **options)
        if box.exec()==QDialog.Accepted:
            try:
                self.edit_local_field(section,row,box.selected_value(),adc=adc)
            except (SourceInputRejected,ValueError) as exc:
                self.page.window().original_window_man.spawn_error(
                    "Локальное поле не принято: "+str(exc))

    def show_channel_details(self,row,column):
        if column!=3 or self.workspace is None:return
        section,channel=self._selected_channel()
        fields,base=section_fields(section,adc=channel)
        if type(row) is not int or not 0<=row<len(fields):return
        f=fields[row]
        self._prompt_edit_source_field(
            section,row,f,base+f.offset,adc=channel)

    def edit_local_field(self,section,row,text,*,adc=None):
        self._require_local_change_allowed()
        if self.workspace is None:
            raise ValueError("Open a local original config before editing")
        self.workspace=self.workspace.edit_field(section,row,text,adc=adc)
        self.document=self.workspace.current
        self.refresh()
        return self.workspace.describe()

    def edit_local_alarm(self,adc,slot,field,text):
        self._require_local_change_allowed()
        if self.workspace is None:
            raise ValueError("Open a local original config before editing")
        self.workspace=self.workspace.edit_alarm(adc,slot,field,text)
        self.document=self.workspace.current
        self.refresh()
        return self.workspace.describe()

    def discard_local_changes(self):
        if self._task0_reading() or self.workspace is None:return
        self.workspace=self.workspace.discard_changes()
        self.document=self.workspace.current
        self.refresh()

    def save_local_file(self,path):
        self._require_local_change_allowed()
        if self.workspace is None:
            raise ValueError("Open a local source file before saving")
        result=self.workspace.save_as(path,mode=self.source_mode)
        self.workspace=self.workspace.mark_mode_saved(self.source_mode)
        self.document=self.workspace.current
        self.refresh()
        self.source_note.setText(
            self.source_note.text()+" Локальный файл сохранён: "+
            str(result["saved_cells"])+" ячеек; запись в прибор НЕ выполнялась.")
        return result

    def choose_save_file(self):
        if self.workspace is None:return
        name,_=QFileDialog.getSaveFileName(
            self.page,"СОХРАНИТЬ новую локальную MVK конфигурацию","",
            "Исходный текстовый формат (*.txt *.cfg *.conf)")
        if not name:return
        try:
            self.save_local_file(name)
        except (OSError,ValueError,UnicodeError) as exc:
            self.page.window().original_window_man.spawn_error(
                "Сохранение локальной конфигурации отклонено: "+str(exc))

    def preview_local_value_input(self,row:int,text:str)->dict:
        """Non-mutating original InputValue *syntax* preview for Mode4/5.

        This deliberately does not claim that the currently connected
        instrument has no protection flags, correct locale settings,
        or the supplied local file actually contains live config.
        """
        if self.source_mode not in (4,5) or type(row) is not int:
            raise ValueError("Source Mode4/5 local validation only")
        section="ip" if self.source_mode==4 else "calib"
        fields,_=section_fields(section)
        if not 0<=row<len(fields):
            raise ValueError("Source row outside the original list")
        f=fields[row]
        info={
            "source_field":f.key,
            "source_type":f.cell_type,
            "source_mode":self.source_mode,
            "local_text_file_mutated":False,
            "original_runtime_acceptance_verified":False,
            "device_config_write_allowed":False,
            "source_protection_state_known":False,
        }
        try:
            payload=encode_source_text(
                f.cell_type,text,bounds=f.bounds,
                sensitive=f.key=="ConfigWifiPassword")
            info["source_subset_syntax_valid"]=True
            info["payload_bytes"]=len(payload)
            info["payload_sha256"]=hashlib.sha256(payload).hexdigest()
        except SourceInputRejected as err:
            info["source_subset_syntax_valid"]=False
            info["reason_source_key"]=err.source_key
        return info

    def _source_validation_context_menu(self,at):
        selected=self.basic_table.indexAt(at)
        if not selected.isValid() or selected.column()!=3:
            return
        menu=QMenu(self.basic_table)
        command=menu.addAction(
            "Проверить значение локально (без изменения)")
        chosen=menu.exec(self.basic_table.viewport().mapToGlobal(at))
        if chosen is command:
            self._prompt_source_validation(selected.row())

    def _prompt_source_validation(self,row):
        section="ip" if self.source_mode==4 else "calib"
        fields,_=section_fields(section)
        if not 0<=row<len(fields):
            return
        if fields[row].key=="ConfigWifiPassword":
            self.page.window().original_window_man.spawn_error(
                "Пароль запрещено вводить в диагностический просмотр.")
            return
        text,ok=QInputDialog.getText(
            self.page,"Локальный анализ исходного InputValue",
            "Ввод для проверки формата (не сохраняется):",
            QLineEdit.Normal,"")
        if not ok:
            return
        report=self.preview_local_value_input(row,text)
        note=("Проверка исходного формата прошла; запись не выполняется."
              if report["source_subset_syntax_valid"]
              else "Исходная проверка отклонила ввод: "
                   + report["reason_source_key"])
        if report["source_subset_syntax_valid"]:
            self.page.window().original_window_man.spawn_information(note)
        else:
            self.page.window().original_window_man.spawn_error(note)

    def load_local_file(self,path):
        """Fail-closed: a bad/new file never preserves old config evidence."""
        self._require_local_change_allowed()
        self.workspace=None
        self._task0_receipt=None
        self.document=empty_original_config_inspection()
        self.refresh()
        self.workspace=OriginalLocalConfigWorkspace.load(path)
        self.document=self.workspace.current
        self.refresh()
        return self.document.report()

    def choose_file(self):
        file,_=QFileDialog.getOpenFileName(
            self.page,"Оригинальная конфигурация MVK — локальный редактор",
            "","Текстовая конфигурация (*.txt *.cfg *.conf)")
        if not file:return
        try:
            self.load_local_file(file)
        except (OSError,ValueError,UnicodeError) as exc:
            # The original TWindowMan.SpawnError shows its own nonmodal
            # third form. This local validation error does not operate a device.
            self.page.window().original_window_man.spawn_error(
                "Локальная конфигурация отклонена: "+str(exc))

    def alarm_detail_dialog(self,row:int,column:int):
        if (type(row) is not int or type(column) is not int
                or not 0<=row<self.alarm_table.rowCount()
                or not 3<=column<self.alarm_table.columnCount()):
            raise ValueError("Only valid source Alarm field may be inspected")
        item=self.alarm_table.item(row,column)
        if item is None:
            raise ValueError("No source alarm cell")
        info=item.data(Qt.UserRole)
        if not isinstance(info,dict):
            raise ValueError("Missing original config register mapping")
        key=info["source_translation_key"]
        hint=source_localize(key)
        return OriginalValueEditDialog(
            prompt=f"{hint.display} ({hint.key}; перевод не принят как оригинал)",
            value=info["raw_value"],units=info["address"],
            parent=self.page,read_only=True,
        )

    def show_alarm_details(self,row:int,column:int):
        if not (0<=row<self.alarm_table.rowCount() and
                3<=column<self.alarm_table.columnCount()):return
        if self.workspace is None:
            self.alarm_detail_dialog(row,column).exec()
            return
        adc=row//8+1
        slot=row%8+1
        field=FIELDS[column-3][0]
        address=alarm_config_register(adc,slot,field)
        cell=self.document.value(address)
        if cell is None:
            # No original FmtChar/type evidence; do not invent one.
            self.alarm_detail_dialog(row,column).exec()
            return
        options,value=self._choice_setup(
            SOURCE_CONFIG_ALARM_OPTIONS
            if field=="parameter_id" and
               cell.format_char==source_type_description(10)["format_char"]
            else None,cell.literal)
        box=OriginalValueEditDialog(
            prompt=source_localize(FIELDS[column-3][1]).display+
                   " · только локальный файл",
            value=value,units=f"0x{address:04X}",
            parent=self.page,read_only=False,**options)
        if box.exec()==QDialog.Accepted:
            try:self.edit_local_alarm(adc,slot,field,box.selected_value())
            except (SourceInputRejected,ValueError) as exc:
                self.page.window().original_window_man.spawn_error(
                    "Локальный Alarm-параметр не принят: "+str(exc))
