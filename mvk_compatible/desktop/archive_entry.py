"""Explicit open-from-shell and drag/drop for the operator desktop."""
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .main_window import MainWindow


_KINDS=frozenset(('.bin','.tsxml','.zip'))
_FILTER=(
    'Двоичные файлы временного сигнала (*.bin *.BIN);;'
    'Файлы измерений MVK (*.bin *.BIN *.tsxml *.TSXML *.zip *.ZIP);;'
    'Экспорт Native R6.1 (*.zip *.ZIP);;'
    'Все файлы (*)')


def _valid_name(path):
    return bool(path and '://' not in path and
                Path(path).suffix.lower() in _KINDS)


class ArchiveEntryWindow(MainWindow):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def open_operator_path(self,path):
        if self._live_active:
            self.statusBar().showMessage(
                'Сначала завершите активную запись; открытый сеанс не изменён.')
            return False
        if not _valid_name(path):
            QMessageBox.warning(self,'Открытие записи',
                'Выберите один локальный файл BIN, TSXML или ZIP Native.')
            return False
        previous=self.session
        self.open_archive(path)
        accepted=self.session is not None and self.session is not previous
        if accepted:
            self.original_visual_skin.reveal_page(3)
        return accepted

    def choose_archive(self):
        if self._live_active:
            self.statusBar().showMessage(
                'Сначала завершите активную запись; открытый сеанс не изменён.')
            return
        home=self.original_start_controller.workspace.library_path
        path,_=QFileDialog.getOpenFileName(
            self,'Открытие',str(home) if home is not None else '',_FILTER)
        if path:
            self.open_operator_path(path)

    @staticmethod
    def _dropped_path(event):
        data=event.mimeData()
        urls=data.urls() if data.hasUrls() else []
        if len(urls)==1 and urls[0].isLocalFile() and not urls[0].host():
            name=urls[0].toLocalFile()
            if _valid_name(name):
                return name
        return None

    def dragEnterEvent(self,event):
        if not self._live_active and self._dropped_path(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self,event):
        path=self._dropped_path(event)
        if path and not self._live_active:
            event.acceptProposedAction()
            self.open_operator_path(path)
        else:
            event.ignore()


def run_archive_desktop(paths=(),*,profile=None):
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('ТПО МВК')
    win=ArchiveEntryWindow()
    if profile is not None:
        win.set_envelope_profile(profile)
    win.show()
    if len(paths)==1:
        QTimer.singleShot(0,lambda: win.open_operator_path(paths[0]))
    elif paths:
        QTimer.singleShot(0,lambda: QMessageBox.warning(
            win,'Открытие записи','Передайте только один файл записи.'))
    return app.exec()
