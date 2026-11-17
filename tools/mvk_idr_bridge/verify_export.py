#!/usr/bin/env python3
"""Validate a private Ghidra research bundle locally, without uploading or networking."""
import csv
import json
import pathlib
import sys


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: py verify_export.py <MVK_Ghidra_Research_directory>")
    root = pathlib.Path(sys.argv[1])
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "mvk-ghidra-idr-export-v1", "Unexpected format"
    assert manifest["image_base"] == "00400000", "Wrong Ghidra image base"
    assert "mvkview" in manifest["program"].lower(), "Wrong binary"
    with (root / "functions.csv").open(encoding="utf-8", newline="") as f:
        functions = list(csv.DictReader(f))
    assert len(functions) == manifest["resolved_functions_exported"], "Function count mismatch"
    for f in functions:
        for key in ("Disassembly", "Decompilation", "Variables"):
            path = (root / f[key]).resolve()
            assert path.is_relative_to(root.resolve()), "Invalid file path"
            assert path.is_file(), f"Missing {path}"
    for name in ("probes.csv", "outgoing_references.csv", "incoming_calls.csv", "referenced_strings.csv", "structures.csv"):
        with (root / name).open(encoding="utf-8", newline="") as f:
            list(csv.reader(f))
    count = len(functions)
    print("OK: schema", manifest["schema"], "functions", count,
          "decompiled", manifest["decompiled_functions"],
          "errors", manifest["decompilation_failures"],
          "missing seeds", manifest["missing_or_undefined_seed_addresses"])
    if count == 0:
        raise SystemExit("Warning: no functions exported. Run Auto Analyze and check imported binary.")
    if manifest["canceled"]:
        print("WARNING: Ghidra script was canceled, partial results only")


if __name__ == "__main__":
    main()