"""Stage111Z31BT real original PageCalib Qt: DFM 49 test flags, 77x11 grid.

Original source from operator's Projects.7z mvkform.dfm and _Unit128.pas.
All calculator / import / save buttons are OFFLINE ONLY; bCalibStart
never creates a generator/serial thread, and bCalibGenerate shows only
a non-uploadable 8-channel gain candidate from an original local CSV and
original local PageConfig baseline.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,QFileDialog,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,
    QPlainTextEdit,QPushButton,QSplitter,QTabWidget,QTableWidget,
    QTableWidgetItem,QVBoxLayout,QWidget,
)

from ..core.original_calibration_workbench import (
    OriginalCalibrationWorkspace,STEP_GROUPS,GRID_ROWS,GRID_COLS,
    GROUP_ROW_HEADERS,DFM_LEFT_WIDTH,DFM_RIGHT_WIDTH,
    DFM_SPLITTER_WIDTH,DFM_CALIB_TOOLS_HEIGHT,DFM_CALIB_SELECT_HEIGHT,
    DFM_RESULT_TOOLS_HEIGHT,DFM_SAVE_BUTTONS,DFM_UNIT_BUTTONS,
    DFM_START,DFM_PORT,CALIB_SOURCE_TABS,
)


def _button(parent,name,caption,rect):
    control=QPushButton(caption,parent)
    control.setObjectName(name)
    control.setGeometry(*rect)
    return control


def build_original_calibration_page(parent):
    page=QWidget(parent)
    page.setObjectName("PageCalib")
    lay=QVBoxLayout(page)
    lay.setContentsMargins(4,4,4,4)
    lay.setSpacing(4)

    split=QSplitter(Qt.Horizontal,page)
    split.setObjectName("splCalib")
    split.setHandleWidth(DFM_SPLITTER_WIDTH)
    split.setChildrenCollapsible(False)
    left=QTabWidget(split)
    left.setObjectName("tcCalibParam")
    left.tabBar().setFixedHeight(36)
    param=QWidget(left)
    pl=QVBoxLayout(param)
    pl.setContentsMargins(4,4,4,4)
    pl.setSpacing(0)

    tools=QWidget(param)
    tools.setObjectName("pnCalibTools")
    tools.setFixedHeight(DFM_CALIB_TOOLS_HEIGHT)
    _button(tools,"bCalibStart","Пуск генератора",DFM_START).setEnabled(False)
    label=QLabel("Порт генератора:",tools)
    label.setObjectName("lbCalibGenPort")
    label.setGeometry(129,20,96,21)
    port=QComboBox(tools)
    port.setObjectName("cbCalibGenPort")
    port.setGeometry(*DFM_PORT)
    port.addItem("нет подтверждённого генератора")
    port.setEnabled(False)
    port.setToolTip("TMVKCalibThread и COM/serial генератор не подключаются")
    pl.addWidget(tools)

    check=QListWidget(param)
    check.setObjectName("cbCalibSteps")
    check.setUniformItemSizes(True)
    pl.addWidget(check,1)

    select=QWidget(param)
    select.setObjectName("pnCalibSelect")
    select.setFixedHeight(DFM_CALIB_SELECT_HEIGHT)
    caption={"A":"A","V":"V","D":"D","DR":"DR","T":"T"}
    for short,tag,x,y,w,h in DFM_UNIT_BUTTONS:
        btn=_button(select,"bCalib"+short,caption[short],(x,y,w,h))
        btn.setProperty("SourceDFMTag",tag)
        btn.setProperty("SourceDFMTabOrder",tag-1)
        btn.setToolTip(
            "Оригинальный bCalibAClick: инвертирует первый флаг и "
            "назначает его всей группе исходных шагов")
    pl.addWidget(select)
    left.addTab(param,"Параметры")

    right=QTabWidget(split)
    right.setObjectName("tcCalibResult")
    right.tabBar().setFixedHeight(36)
    result_log=QWidget(right)
    log_lay=QVBoxLayout(result_log)
    log_lay.setContentsMargins(4,67,4,4)
    log=QPlainTextEdit(result_log)
    log.setObjectName("logCalibResult")
    log.setReadOnly(True)
    log.setPlaceholderText(
        "Здесь будет только импортированный исходный лог калибровки. "
        "TMVKCalibThread не запущен.")
    log_lay.addWidget(log)
    right.addTab(result_log,"Журнал")

    result_table=QWidget(right)
    table_layout=QVBoxLayout(result_table)
    table_layout.setContentsMargins(4,67,4,4)
    grid=QTableWidget(result_table)
    grid.setObjectName("tabCalibResult")
    grid.setColumnCount(GRID_COLS)
    grid.setRowCount(GRID_ROWS)
    grid.setEditTriggers(QTableWidget.NoEditTriggers)
    grid.verticalHeader().setDefaultSectionSize(20)
    grid.horizontalHeader().setDefaultSectionSize(90)
    grid.setHorizontalHeaderLabels(
        ["Группа","Частота / U","Эталон"]+
        [f"АЦП {i}" for i in range(1,9)])
    grid.setColumnWidth(0,160)
    table_layout.addWidget(grid)
    right.addTab(result_table,"Таблица")
    assert right.count()==CALIB_SOURCE_TABS

    # DFM pnCalibResult is a sibling of both memo/grid; keep it visible
    # in both Qt tab modes as an OVERLAY immediately below the tab strip.
    toolbar=QWidget(right)
    toolbar.setObjectName("pnCalibResult")
    toolbar.setGeometry(4,42,607,DFM_RESULT_TOOLS_HEIGHT)
    captions={"bCalibSave":"Сохранить CSV",
              "bCalibClear":"Очистить таблицу",
              "bCalibGenerate":"Проект поправок"}
    for name,x,y,w,h in DFM_SAVE_BUTTONS:
        _button(toolbar,name,captions[name],(x,y,w,h))
    toolbar.raise_()

    split.addWidget(left)
    split.addWidget(right)
    split.setSizes([DFM_LEFT_WIDTH,DFM_RIGHT_WIDTH])
    lay.addWidget(split,1)

    # These are explicit safe compatible actions, not fabricated source
    # DFM controls. Keep original tcCalibParam=1 / tcCalibResult=2.
    extra=QWidget(page)
    extra.setObjectName("localCalibOfflineActions")
    extra_layout=QHBoxLayout(extra)
    extra_layout.setContentsMargins(0,0,0,0)
    load=QPushButton("Открыть исходный CALIB CSV…",extra)
    load.setObjectName("localCalibLoadCsv")
    extra_layout.addWidget(load)
    import_log=QPushButton("Открыть исходный журнал…",extra)
    import_log.setObjectName("localCalibLoadLog")
    extra_layout.addWidget(import_log)
    save_proposal=QPushButton("Сохранить проект .json…",extra)
    save_proposal.setObjectName("localCalibSaveProposal")
    save_proposal.setEnabled(False)
    extra_layout.addWidget(save_proposal)
    lay.addWidget(extra)

    candidate=QTableWidget(0,4,page)
    candidate.setObjectName("localCalibCandidatePreview")
    candidate.setEditTriggers(QTableWidget.NoEditTriggers)
    candidate.setHorizontalHeaderLabels(
        ("АЦП","Исходный коэффициент",
         "Измерение/эталон × 1.001","Локальный проект"))
    candidate.setMaximumHeight(230)
    candidate.setVisible(False)
    lay.addWidget(candidate)
    note=QLabel(
        "Исходный файл калибровки не открыт. Все значения результата — "
        "только локальные. Генератор и приборная калибровка отключены.",
        page)
    note.setObjectName("localCalibSourceEvidence")
    note.setWordWrap(True)
    note.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(note)
    return page


class OriginalCalibrationPanel:
    """Owns visible Qt controls and ONE immutable source-calibration model."""

    def __init__(self,page,window):
        self.page=page
        self.window=window
        self.workspace=OriginalCalibrationWorkspace.initial()
        self.proposal=None
        self.tabs=page.findChild(QTabWidget,"tcCalibResult")
        self.param_tabs=page.findChild(QTabWidget,"tcCalibParam")
        self.steps=page.findChild(QListWidget,"cbCalibSteps")
        self.grid=page.findChild(QTableWidget,"tabCalibResult")
        self.log=page.findChild(QPlainTextEdit,"logCalibResult")
        self.hint=page.findChild(QLabel,"localCalibSourceEvidence")
        self.preview=page.findChild(QTableWidget,"localCalibCandidatePreview")
        self.buttons={
            name:page.findChild(QPushButton,name)
            for name in ("bCalibStart","bCalibSave","bCalibClear",
                         "bCalibGenerate","localCalibLoadCsv",
                         "localCalibLoadLog","localCalibSaveProposal")
        }
        self.groups={
            tag:page.findChild(QPushButton,"bCalib"+short)
            for short,tag,*_ in DFM_UNIT_BUTTONS
        }
        if (any(v is None for v in self.buttons.values()) or
                any(v is None for v in self.groups.values()) or
                any(v is None for v in (
                    self.tabs,self.param_tabs,self.steps,
                    self.grid,self.log,self.hint,self.preview))):
            raise ValueError("Original PageCalib DFM controls are missing")
        assert self.tabs.count()==2 and self.param_tabs.count()==1
        self.buttons["bCalibStart"].setEnabled(False)
        self.buttons["bCalibStart"].setToolTip(
            "Исходный _Unit128:0084DD30 создаёт TMVKCalibThread. "
            "Без прибора/COM генератора физический запуск ЗАПРЕЩЁН.")
        self.buttons["bCalibGenerate"].setToolTip(
            "Исходный _Unit128:0084D474: 8 поправок, row8/col2..10. "
            "Только локальный проект; НЕТ CALIB-файла для прибора.")
        self.buttons["bCalibSave"].clicked.connect(self.choose_save_csv)
        self.buttons["bCalibClear"].clicked.connect(self.clear_grid)
        self.buttons["bCalibGenerate"].clicked.connect(self.make_proposal)
        self.buttons["localCalibLoadCsv"].clicked.connect(self.choose_csv)
        self.buttons["localCalibLoadLog"].clicked.connect(self.choose_log)
        self.buttons["localCalibSaveProposal"].clicked.connect(
            self.choose_save_proposal)
        for tag,btn in self.groups.items():
            btn.clicked.connect(
                lambda _checked=False,index=tag:self.toggle_group(index))
        self.steps.itemChanged.connect(self._step_changed)
        self.tabs.currentChanged.connect(
            lambda *_:page.findChild(QWidget,"pnCalibResult").raise_())
        self.refresh()

    def _config_workspace(self):
        panel=getattr(self.window,"original_config_panel",None)
        workspace=getattr(panel,"workspace",None) if panel else None
        if workspace is None:return None
        # Even if PageConfig has unsaved edits, original baseline, not draft,
        # is the physical source for source gain comparison.
        workspace._ensure_input_unchanged()
        return workspace

    def refresh_gate(self):
        allowed=False
        try:
            current=self._config_workspace()
            allowed=bool(current is not None and
                         self.workspace.source_grid_loaded)
        except (ValueError,OSError):
            allowed=False
        self.buttons["bCalibGenerate"].setEnabled(allowed)
        self.buttons["localCalibSaveProposal"].setEnabled(
            self.proposal is not None)

    def _render_steps(self):
        old=self.steps.blockSignals(True)
        try:
            self.steps.clear()
            counter=0
            for short,label,count in STEP_GROUPS:
                for k in range(count):
                    item=QListWidgetItem(
                        f"{label} · исходный шаг {k+1:02d}",self.steps)
                    item.setData(Qt.UserRole,counter)
                    item.setFlags(Qt.ItemIsSelectable|
                                  Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
                    item.setCheckState(
                        Qt.Checked if self.workspace.steps[counter] else
                        Qt.Unchecked)
                    counter+=1
            assert counter==49
        finally:
            self.steps.blockSignals(old)

    def _step_changed(self,item):
        index=item.data(Qt.UserRole)
        if type(index) is not int:return
        self.workspace=self.workspace.select_step(
            index,item.checkState()==Qt.Checked)
        self.hint.setText(
            f"Исходные bCalibAClick: отмечено "
            f"{self.workspace.checked_steps}/49. "
            "Команд генератору или прибору нет.")

    def toggle_group(self,tag):
        self.workspace=self.workspace.toggle_group(tag)
        self._render_steps()
        self.hint.setText(
            f"Группа {tag} переключена, выбрано "
            f"{self.workspace.checked_steps}/49 исходных шагов. "
            "TMVKCalibThread не запускался.")
        return self.workspace.steps

    def _render_grid(self):
        self.grid.setRowCount(GRID_ROWS)
        self.grid.setColumnCount(GRID_COLS)
        self.grid.clearContents()
        for row,values in enumerate(self.workspace.grid):
            for col,value in enumerate(values):
                if not value:continue
                item=QTableWidgetItem(value)
                item.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
                self.grid.setItem(row,col,item)

    def _clear_proposal(self):
        self.proposal=None
        self.preview.setRowCount(0)
        self.preview.setVisible(False)
        self.buttons["localCalibSaveProposal"].setEnabled(False)

    def refresh(self):
        self._render_steps()
        self._render_grid()
        self.log.setPlainText("\n".join(self.workspace.log_lines))
        self._clear_proposal()
        self.refresh_gate()
        if self.workspace.source_grid_loaded:
            self.hint.setText(
                f"Открыт исходный CALIB CSV: 77×11; SHA256 "
                f"{self.workspace.source_sha256[:16]}… "
                f"Выбрано {self.workspace.checked_steps}/49 шагов. "
                "Данные только локальные, COM/прибор не задействованы.")
        else:
            self.hint.setText(
                "Локальная исходная матрица 77×11; проверенных "
                "калибровочных измерений нет. "
                "Откройте оригинальный CALIB CSV для расчёта поправок.")

    def load_csv(self,path):
        self.workspace=OriginalCalibrationWorkspace.load_csv(
            path,steps=self.workspace.steps)
        self.refresh()
        self.tabs.setCurrentIndex(1)
        return self.workspace

    def choose_csv(self):
        path,_=QFileDialog.getOpenFileName(
            self.page,"Оригинальный CALIB-*.csv (только локально)","",
            "Исходный CSV (*.csv)")
        if not path:return
        try:self.load_csv(path)
        except (OSError,ValueError,UnicodeError) as exc:
            self.window.original_window_man.spawn_error(
                "Источник CALIB отклонён: "+str(exc))

    def load_log(self,path):
        self.workspace=self.workspace.open_log(path)
        self.log.setPlainText("\n".join(self.workspace.log_lines))
        self.tabs.setCurrentIndex(0)
        return self.workspace

    def choose_log(self):
        path,_=QFileDialog.getOpenFileName(
            self.page,"Локальный оригинальный журнал калибровки","",
            "Текст (*.txt *.log)")
        if not path:return
        try:self.load_log(path)
        except (OSError,ValueError,UnicodeError) as exc:
            self.window.original_window_man.spawn_error(
                "Журнал CALIB отклонён: "+str(exc))

    def clear_grid(self):
        self.workspace=self.workspace.clear_grid()
        self.refresh()
        return self.workspace

    def save_csv(self,path):
        return self.workspace.export_csv(path)

    def choose_save_csv(self):
        dest,_=QFileDialog.getSaveFileName(
            self.page,"Создать новый локальный CALIB CSV","CALIB-local.csv",
            "Исходный CALIB CSV (*.csv)")
        if not dest:return
        try:result=self.save_csv(dest)
        except (OSError,ValueError,UnicodeError) as exc:
            self.window.original_window_man.spawn_error(
                "CALIB CSV не сохранён: "+str(exc))
            return
        self.hint.setText(
            f"CALIB CSV 77×11 сохранён локально, SHA256 "
            f"{result['saved_csv_sha256'][:16]}…; прибор не изменён.")
        return result

    def make_proposal(self):
        try:
            source=self._config_workspace()
            if source is None:
                raise ValueError("Сначала откройте исходный файл на PageConfig")
            proposal=self.workspace.candidate(source.original)
        except (ValueError,OSError,UnicodeError) as exc:
            self._clear_proposal()
            self.window.original_window_man.spawn_error(
                "Проект поправок не сформирован: "+str(exc))
            return
        self.proposal=proposal
        self.preview.setRowCount(len(proposal.entries))
        for i,entry in enumerate(proposal.entries):
            for col,value in enumerate((
                    f"АЦП{entry.adc}",f"{entry.old_gain:.9g}",
                    f"{entry.original_ratio_candidate:.9g}",
                    f"{entry.new_gain_float32_candidate:.9g}")):
                cell=QTableWidgetItem(value)
                cell.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
                self.preview.setItem(i,col,cell)
        self.preview.setVisible(True)
        self.buttons["localCalibSaveProposal"].setEnabled(True)
        self.hint.setText(
            "Получены 8 локальных кандидатов поправок по строке 8 "
            "оригинала. Только проект JSON, физическая калибровка "
            "НЕ выполнялась. Проверьте значения перед экспортом.")
        self.tabs.setCurrentIndex(1)
        return proposal

    def save_proposal(self,path):
        if self.proposal is None:
            raise ValueError("Создайте локальный кандидат перед сохранением")
        self.workspace.require_source_unchanged()
        self._config_workspace()  # SHA-source revalidation
        return OriginalCalibrationWorkspace.save_candidate_json(
            self.proposal,path)

    def choose_save_proposal(self):
        if self.proposal is None:return
        dest,_=QFileDialog.getSaveFileName(
            self.page,"Проект коэффициентов (НЕ для загрузки в прибор)",
            "CALIB-candidate-review-only.json",
            "Проект JSON (*.json)")
        if not dest:return
        try:result=self.save_proposal(dest)
        except (OSError,ValueError,UnicodeError) as exc:
            self.window.original_window_man.spawn_error(
                "Проект поправок не сохранён: "+str(exc))
            return
        self.hint.setText(
            "Локальный проект 8 поправок сохранён и проверен SHA256 "
            f"{result['sha256'][:16]}…; "
            "файл нельзя загружать в МВК.")
        return result
