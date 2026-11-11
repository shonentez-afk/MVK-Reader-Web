#!/usr/bin/env python3
"""Offline-only source STRUCTURE index of user-owned IDR Projects export.

Input: locally extracted Projects/*.dfm, _Unit*.pas and mvkview.dpr,
optionally the user's own original mvkview.idp.
Output: derived component/event/method inventory, not original source code.
No original runtime/debugger, hardware, network, GUI or file mutation.
No original texts, images, DFM/PAS bytes or private IDP are ever published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

CONTROL = re.compile(
    r"^(\s*)(?:object|inherited)\s+([A-Za-z_]\w*)\s*:\s*([A-Za-z_][\w.]*)\s*$",
    flags=re.I)
EVENT = re.compile(
    r"^\s*(On\w+)\s*=\s*([A-Za-z_]\w*)\s*$", flags=re.I)
CLASS = re.compile(
    r"(?m)^\s{2}([A-Za-z_]\w*)\s*=\s*class\([^\r\n]+\)\s*\r?\n")
METHOD = re.compile(
    r"(?m)^\s*(?:procedure|function|constructor|destructor)\s+"
    r"([A-Za-z_][\w.]*)[^\r\n]*?;//([0-9A-F]{8})")
EXPLICIT_GEOMETRY = re.compile(
    r"^\s*(Left|Top|Width|Height|ClientWidth|ClientHeight|"
    r"BorderWidth|PixelsPerInch|Font.Height)\s*=\s*(-?\d+)\s*$")


def read_dfm_structure(path: Path) -> list[dict]:
    """DFM property nesting is non-Pascal; only extract own OBJECT levels."""
    tree, stack = [], []
    for line in path.read_text(encoding="latin-1").splitlines():
        m = CONTROL.match(line)
        if m:
            depth = len(m[1])
            while stack and stack[-1][0] >= depth:
                stack.pop()
            parent = stack[-1][1] if stack else None
            page = next((
                tree[index]["name"] for _, index in reversed(stack)
                if tree[index]["class"] == "TTabSheet"
                and tree[index]["name"].startswith("Page")), None)
            tree.append({
                "name": m[2], "class": m[3],
                "parent": tree[parent]["name"] if parent is not None else None,
                "page": page, "geometry": {}, "events": {}})
            stack.append((depth, len(tree) - 1))
            continue
        if line.strip() == "end":
            depth = len(line) - len(line.lstrip())
            if stack and stack[-1][0] == depth:
                stack.pop()
            continue
        if not stack:
            continue
        item = tree[stack[-1][1]]
        e = EVENT.match(line)
        if e:
            item["events"][e[1]] = e[2]
            continue
        p = EXPLICIT_GEOMETRY.match(line)
        if p:
            item["geometry"][p[1]] = int(p[2])
    if not tree or tree[0]["parent"] is not None:
        raise ValueError("Cannot read original Delphi form hierarchy")
    return tree


def read_class_method_addresses(unit: Path, class_name: str) -> dict[str, str]:
    """Match IDR class methods to original VAs; NOT complete method logic."""
    src = unit.read_text(encoding="latin-1")
    match = re.search(
        r"(?m)^\s{2}" + re.escape(class_name) +
        r"\s*=\s*class\([^\r\n]+\)\s*\r?\n", src)
    if not match:
        return {}
    end = src.find("\n  end;", match.end())
    if end < 0 or end - match.end() > 450_000:
        raise ValueError("Malformed IDR class declaration: " + class_name)
    return dict(METHOD.findall(src[match.end():end]))


def build_index(projects_dir: Path, idp: Path | None = None) -> dict:
    root = projects_dir.resolve()
    if not root.is_dir():
        raise ValueError("Extracted private Projects folder is required")
    dfms = sorted(root.glob("*.dfm"))
    units = sorted(root.glob("*.pas"))
    if not (root / "mvkview.dpr").is_file() or len(dfms) < 2 or len(units) < 10:
        raise ValueError("Incomplete original IDR project export")
    # Original IDP is only checked for type, never parsed for unknown offsets.
    if idp is not None:
        with idp.open("rb") as inp:
            if not inp.read(12).startswith(b"IDR proj v.3"):
                raise ValueError("Unexpected private IDP format")
    result = {
        "schema": "MVKVIEW_IDR_PRIVATE_SOURCE_STRUCTURE_V1",
        "archive_source": "Projects.7z (private, not uploaded)",
        "pas_file_count": len(units),
        "idr_generated_units": len(list(root.glob("_Unit*.pas"))),
        "dfm_file_count": len(dfms), "dpr_file_count": 1,
        "idp_header_checked": idp is not None,
        "forms": {}, "original_executable_behavior_verified": False,
        "delphi_project_recompilable": False,
        "private_source_or_resource_bytes_included": False,
    }
    for form in dfms:
        components = read_dfm_structure(form)
        cls = components[0]["class"]
        # IDR gathers the original application's form classes in two units.
        # Missing class is reported, not silently fabricated as supported.
        unit = (root / "_Unit115.pas" if cls == "TWindowManForm"
                else root / "_Unit128.pas")
        methods = read_class_method_addresses(unit, cls) if unit.is_file() else {}
        handlers = sorted({name for node in components
                           for name in node["events"].values()})
        result["forms"][cls] = {
            "dfm": form.name,
            "code_unit": unit.name if methods else None,
            "component_count": len(components),
            "event_binding_count": sum(len(n["events"]) for n in components),
            "distinct_dfm_handlers": len(handlers),
            "resolved_dfm_handlers": len(set(handlers) & set(methods)),
            "missing_dfm_handlers": sorted(set(handlers) - set(methods)),
            "declared_methods_without_direct_dfm_binding":
                sorted(set(methods) - set(handlers)),
            "handlers_va": {name: methods.get(name) for name in handlers},
            "pages": {
                page: sum(n["page"] == page for n in components)
                for page in sorted({n["page"] for n in components
                                    if n["page"] is not None})},
            "components": components,
        }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", type=Path, required=True,
                        help="Operator-private extracted Projects folder")
    parser.add_argument("--idp", type=Path, help="Operator-private original IDP")
    parser.add_argument("--output", type=Path, required=True,
                        help="New private metadata JSON (not inside checkout)")
    args = parser.parse_args(argv)
    target = args.output.resolve()
    root = args.projects.resolve()
    if root == target or root in target.parents or target.exists():
        parser.error("Refusing output inside input files or overwrite")
    if not target.parent.is_dir():
        parser.error("Output parent must exist")
    info = build_index(args.projects, args.idp)
    with target.open("x", encoding="utf-8") as out:
        json.dump(info, out, ensure_ascii=False, sort_keys=True, indent=2)
        out.write("\n")
    print("Original forms:", len(info["forms"]))
    for cls, form in info["forms"].items():
        print(cls, form["component_count"], "controls,",
              form["resolved_dfm_handlers"], "/",
              form["distinct_dfm_handlers"], "DFM handlers resolved")
    print("Metadata stays local. No original executable behavior authenticated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
