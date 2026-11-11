"""Stage111Z31BD: native Qt read-only original Config grids with source provenance.

Source DFM has two tcConfig tabs (Channels, Alarms) and a sibling
tabConfigBasic grid in non-channel Mode. We preserve exactly that.
bConfigLoad is the ONLY enabled config toolbar button and reads a
user-selected bounded original text *locally*, never downloading to/from
instrument. No arbitrary memory images, saved source configurations or
live device semantics are inferred from a passive text file.
"""
from __future__ import annotations

import hashlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QMenu, QInputDialog, QLineEdit

from ..core.original_config_readonly import (
    FIELDS, UNKNOWN, empty_original_config_inspection,
    inspect_original_local_config, alarm_config_register,
)
from ..core.original_language_source import source_localize
from ..core.original_config_semantics import source_section_rows, section_fields
from ..core.original_config_input_draft import (
    SourceInputRejected, encode_source_text,
)
from .original_value_edit_dialog import OriginalValueEditDialog


class OriginalConfigReadOnlyPanel:
    def __init__(self,page):
        self.page=page
        self.channel_table=page.findChild(QTableWidget,"tabConfigChannels")
        self.alarm_table=page.findChild(QTableWidget,"tabConfigAlarms")
        self.basic_table=page.findChild(QTableWidget,"tabConfigBasic")
        self.source_note=page.findChild(QLabel,"sourceConfigEvidence")
        self.load_button=page.findChild(QPushButton,"bConfigLoad")
        self.page_tabs=page.findChild(QTabWidget,"tcConfig")
        self.source_mode=6
        self.document=empty_original_config_inspection()
        if any(x is None for x in (self.channel_table,self.alarm_table,
                                   self.basic_table,self.source_note,
                                   self.load_button,self.page_tabs)):
            raise ValueError("Missing source PageConfig DFM control")
        self.load_button.setEnabled(True)
        self.load_button.setToolTip(
            "Открыть ТОЛЬКО локальный исходный текстовый конфигурационный "
            "файл для чтения. Не загружает в прибор и не редактирует регистры.")
        self.load_button.clicked.connect(self.choose_file)
        self.alarm_table.cellDoubleClicked.connect(self.show_alarm_details)
        self.basic_table.cellDoubleClicked.connect(self.show_basic_details)
        # Extra source-audit action is a context menu, not an invented
        # original DFM button. It validates an ephemeral candidate only.
        self.basic_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.basic_table.customContextMenuRequested.connect(
            self._source_validation_context_menu)
        self.refresh()

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
        c.setRowCount(len(channel_rows))
        for r,channel in enumerate(channel_rows):
            for i,value in enumerate((
                f"ADC{channel['adc']}",channel["source_config_base"],
                channel["known_alarm_cells_in_file"],
                channel["expected_alarm_cells"],"НЕ подтверждено",
            )):
                self._cell(c,r,i,value)

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
        self._set_mode_visibility()
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
        self.source_note.setText(
            f"Локально прочитано {total} RAW значений. {summary} "
            "Текущая конфигурация прибора НЕ подтверждена. "
            "Save/Reset/Download/Upload/Calib отключены.")

    def _set_mode_visibility(self):
        basic=self.source_mode in (4,5)
        self.page_tabs.setVisible(not basic)
        self.basic_table.setVisible(basic)

    def _refresh_basic(self):
        table=self.basic_table
        if self.source_mode not in (4,5):
            table.setRowCount(0)
            return
        rows=source_section_rows(
            self.document,"ip" if self.source_mode==4 else "calib")
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ("Исходное поле","Адрес","IDR тип","Локальный RAW",
             "Исходные пределы / список"))
        table.setRowCount(len(rows))
        for index,info in enumerate(rows):
            name=source_localize(info["source_key"]).display+info["source_suffix"]
            bounds=(f'{info["source_min"]}..{info["source_max"]}'
                    if info["source_min"] is not None else "")
            values=(name,info["address"],
                    f'{info["cell_type_code"]} ({info["source_format_char"]}, '
                    f'{info["source_storage_bytes"]} байт)',
                    info["raw_value"],bounds or info["advanced_kind"] or UNKNOWN)
            detail={"source_translation_key":info["source_key"],
                    "address":info["address"]}
            for col,value in enumerate(values):
                self._cell(table,index,col,value,
                           detail=detail if col==3 else None)

    def set_source_mode(self,mode):
        if type(mode) is not int or mode not in (4,5,6):
            raise ValueError("Only source Config Mode4/5/6 supported")
        self.source_mode=mode
        self.refresh()

    def basic_detail_dialog(self,row,column):
        if (self.source_mode not in (4,5) or
                type(row) is not int or type(column) is not int or
                not 0<=row<self.basic_table.rowCount() or column!=3):
            raise ValueError("Only local raw source field may be viewed")
        info=source_section_rows(
            self.document,"ip" if self.source_mode==4 else "calib")[row]
        hint=source_localize(info["source_key"])
        return OriginalValueEditDialog(
            prompt=f'{hint.display}{info["source_suffix"]} ({hint.key})',
            value=info["raw_value"],units=info["address"],
            parent=self.page,read_only=True)

    def show_basic_details(self,row,column):
        if column==3:
            self.basic_detail_dialog(row,column).exec()

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
        self.document=empty_original_config_inspection()
        self.refresh()
        doc=inspect_original_local_config(path)
        self.document=doc
        self.refresh()
        return doc.report()

    def choose_file(self):
        file,_=QFileDialog.getOpenFileName(
            self.page,"Оригинальная конфигурация MVK — только чтение",
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
        if column<3:
            return
        dialog=self.alarm_detail_dialog(row,column)
        dialog.exec()
