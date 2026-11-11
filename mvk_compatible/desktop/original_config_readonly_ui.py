"""Stage111Z31BD: native Qt read-only original Config grids with source provenance.

Source DFM has two tcConfig tabs (Channels, Alarms) and a sibling
tabConfigBasic grid in non-channel Mode. We preserve exactly that.
bConfigLoad is the ONLY enabled config toolbar button and reads a
user-selected bounded original text *locally*, never downloading to/from
instrument. No arbitrary memory images, saved source configurations or
live device semantics are inferred from a passive text file.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem

from ..core.original_config_readonly import (
    FIELDS, UNKNOWN, empty_original_config_inspection,
    inspect_original_local_config, alarm_config_register,
)
from ..core.original_language_source import source_localize
from .original_value_edit_dialog import OriginalValueEditDialog


class OriginalConfigReadOnlyPanel:
    def __init__(self,page):
        self.page=page
        self.channel_table=page.findChild(QTableWidget,"tabConfigChannels")
        self.alarm_table=page.findChild(QTableWidget,"tabConfigAlarms")
        self.basic_table=page.findChild(QTableWidget,"tabConfigBasic")
        self.source_note=page.findChild(QLabel,"sourceConfigEvidence")
        self.load_button=page.findChild(QPushButton,"bConfigLoad")
        self.document=empty_original_config_inspection()
        if any(x is None for x in (self.channel_table,self.alarm_table,
                                   self.basic_table,self.source_note,
                                   self.load_button)):
            raise ValueError("Missing source PageConfig DFM control")
        self.load_button.setEnabled(True)
        self.load_button.setToolTip(
            "Открыть ТОЛЬКО локальный исходный текстовый конфигурационный "
            "файл для чтения. Не загружает в прибор и не редактирует регистры.")
        self.load_button.clicked.connect(self.choose_file)
        self.alarm_table.cellDoubleClicked.connect(self.show_alarm_details)
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

        # Source sibling tabConfigBasic is only active in Delphi Mode4/5;
        # keep it hidden here. Do not add a third, invented tcConfig tab.
        self.basic_table.hide()
        total=report["parsed_cells"]
        count=report["alarm_registers_present"]
        self.source_note.setText(
            "Исходный IDR: 8 АЦП × 8 контрольных слотов × 8 полей "
            f"(0x0100..0x08FF). Локально прочитано {total} значений, "
            f"из них {count}/512 совпали с адресами контрольных зон. "
            "Текущая конфигурация прибора НЕ подтверждена. "
            "Статус, пороги и единицы не расшифрованы автоматически; "
            "сохранение, Upload, Reset и калибровка отключены.")

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
            QMessageBox.warning(self.page,"Локальная конфигурация отклонена",
                                str(exc))

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
