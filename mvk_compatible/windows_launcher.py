"""Windows one-file entry point with an optional verified offline FIR resource."""
import sys


def main():
    from mvk_compatible.core.bundled_offline_fir import load_frozen_offline_fir

    profile = load_frozen_offline_fir()
    if sys.argv[1:] == ["--verify-offline-fir"]:
        return 0 if profile is not None else 2

    if profile is None:
        from mvk_compatible.desktop.main_window import run
        return run()

    from PySide6.QtWidgets import QApplication
    from mvk_compatible.desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ТПО МВК")
    win = MainWindow()
    win.set_envelope_profile(profile)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
