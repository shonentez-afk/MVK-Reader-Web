"""Run with: py -3 -m capture_agent gui|mcp|probe|selftest"""
from __future__ import annotations
import argparse
import json
import sys
from .config import CaptureError
from .session import CaptureService


def main(argv=None):
    parser = argparse.ArgumentParser(description="MVKView Capture Agent - local, read-only")
    parser.add_argument("mode", choices=("gui", "mcp", "probe", "selftest"), nargs="?", default="gui")
    args = parser.parse_args(argv)
    if args.mode == "gui":
        from .gui import run_gui
        run_gui()
        return 0
    if args.mode == "mcp":
        from .mcp import serve
        serve()
        return 0
    if args.mode == "selftest":
        import unittest
        suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    try:
        targets = CaptureService().discover()
        print(json.dumps({"targets": targets, "note": "Read-only discovery, no process attached"},
                         ensure_ascii=False, indent=2))
        return 0
    except CaptureError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())