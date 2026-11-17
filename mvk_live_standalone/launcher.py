"""Standalone PyInstaller entrypoint; no MVK hardware contact until consent."""
from mvk_live_standalone.app import main

if __name__ == "__main__":
    raise SystemExit(main())
