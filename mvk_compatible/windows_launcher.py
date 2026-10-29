"""Windows packaging entry point for PyInstaller; no HTTP server or device access."""
from mvk_compatible.desktop.main_window import run

if __name__ == '__main__':
    raise SystemExit(run())
