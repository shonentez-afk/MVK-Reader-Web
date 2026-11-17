import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")


def test_qt_modes_scale_update_labels_and_no_network_on_open():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    from mvk_live_standalone.app import LiveWindow
    app=QApplication.instance() or QApplication([])
    widget=LiveWindow()
    try:
        assert widget._native.state()==QtCore.QProcess.ProcessState.NotRunning
        assert widget._capture_root is None
        assert "м/с²" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()
        widget.kind.setCurrentIndex(1)
        assert "мм/с" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()
        widget.yscale.setCurrentIndex(1)
        assert "мм/с" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()
        widget.kind.setCurrentIndex(2)
        assert "мкм" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()
        widget.yscale.setCurrentIndex(2)
        assert "дБ" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()
        assert "мкм" in widget.spec.getPlotItem().getAxis("left").label.toPlainText()
    finally:
        widget.close()
