#!/usr/bin/env python3
"""Read-only Stage111 AST/Go graph. No private original sources or runtime claims."""
from __future__ import annotations
import argparse, ast, json, pathlib, re
from collections import Counter

CORE = ("mvk_compatible/core", "mvk_compatible/desktop")
GO = "tools/research/native_tcp10230_stage108_live_recording_r6_1/source"
URL = "https://github.com/shonentez-afk/MVK-Reader-Web/blob/"

def target_module(name, level, current):
    if level:
        parts = list(current.parent.parts)
        prefix = parts[:max(0, len(parts) - level + 1)]
        return "/".join(prefix + name.split(".")) + ".py" if name else "/".join(prefix) + ".py"
    return name.replace(".", "/") + ".py"

def analyze(repo, sha="UNPINNED"):
    repo = pathlib.Path(repo)
    files = []
    for dirname in CORE:
        path = repo / dirname
        if path.is_dir():
            files.extend(sorted(x for x in path.glob("*.py") if x.name != "__init__.py"))
    # The real desktop entrypoint is outside core/desktop; it must be indexed.
    entry = repo / 'mvk_compatible' / '__main__.py'
    if entry.is_file():
        files.append(entry)
    root = repo / GO
    if root.is_dir():
        files.extend(sorted(x for x in root.glob("*.go") if not x.name.endswith("_test.go")))
    nodes, edges, parsed, errors = {}, [], {}, []
    def add_node(kind, rel, name, line=1):
        key = kind + ":" + rel + ("::" + name if kind != "file" else "")
        group = "Go R6.1" if rel.endswith(".go") else "Qt Desktop" if "/desktop/" in rel else "Python Core"
        nodes[key] = {"id": key, "type": kind, "name": name, "path": rel, "line": line,
                      "group": group, "url": URL + sha + "/" + rel + "#L" + str(line)}
        return key
    for file in files:
        rel = file.relative_to(repo).as_posix()
        fid = add_node("file", rel, file.name)
        source = file.read_text(encoding="utf-8-sig", errors="replace")
        if file.suffix == ".go":
            pattern = r"^\s*func\s+(?:\(\s*\w+\s+\*?(\w+)\s*\)\s*)?(\w+)\s*\("
            for m in re.finditer(pattern, source, re.M):
                line = source.count("\n", 0, m.start()) + 1
                name = (m.group(1) + "." if m.group(1) else "") + m.group(2)
                nid = add_node("function", rel, name, line)
                edges.append({"from": fid, "to": nid, "type": "contains", "evidence": "Go declaration regex"})
            continue
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            errors.append({"path": rel, "error": str(exc)})
            continue
        aliases, imports, defs = {}, set(), []
        for item in tree.body:
            if isinstance(item, ast.Import):
                for alias in item.names:
                    module = alias.name.replace(".", "/") + ".py"
                    aliases[alias.asname or alias.name.split(".")[0]] = module
                    imports.add(module)
            elif isinstance(item, ast.ImportFrom):
                module = target_module(item.module or "", item.level, file.relative_to(repo))
                imports.add(module)
                for alias in item.names:
                    if alias.name != "*":
                        aliases[alias.asname or alias.name] = module + "::" + alias.name
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.append((item.name, item, None))
            elif isinstance(item, ast.ClassDef):
                cid = add_node("class", rel, item.name, item.lineno)
                edges.append({"from": fid, "to": cid, "type": "contains", "evidence": "Python AST"})
                for child in item.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        defs.append((item.name + "." + child.name, child, item.name))
        for name, item, owner in defs:
            nid = add_node("function", rel, name, item.lineno)
            nodes[nid]["end_line"] = item.end_lineno
            nodes[nid]["docstring"] = (ast.get_docstring(item) or "")[:1000]
            edges.append({"from": "class:" + rel + "::" + owner if owner else fid,
                          "to": nid, "type": "contains", "evidence": "Python AST"})
        parsed[rel] = (defs, aliases, imports)
    seen = set()
    for rel, (defs, aliases, imports) in parsed.items():
        originfile = "file:" + rel
        for module in imports:
            dest = "file:" + module
            if dest in nodes and (originfile, dest) not in seen:
                edges.append({"from": originfile, "to": dest, "type": "imports", "evidence": "Python AST"})
                seen.add((originfile, dest))
        for name, node, owner in defs:
            origin = "function:" + rel + "::" + name
            # Imports inside a function are common in Stage111's CLI/UI entrypoint.
            local_aliases = dict(aliases)
            for part in ast.walk(node):
                if isinstance(part, ast.ImportFrom):
                    target = target_module(part.module or '', part.level, pathlib.Path(rel))
                    for imported in part.names:
                        if imported.name != '*':
                            local_aliases[imported.asname or imported.name] = target + '::' + imported.name
                elif isinstance(part, ast.Import):
                    for imported in part.names:
                        local_aliases[imported.asname or imported.name.split('.')[0]] = imported.name.replace('.', '/') + '.py'
            for part in ast.walk(node):
                if not isinstance(part, ast.Call):
                    continue
                f, dest = part.func, None
                if isinstance(f, ast.Name):
                    dest = "function:" + rel + "::" + f.id
                    if f.id in local_aliases and "::" in local_aliases[f.id]:
                        dest = "function:" + local_aliases[f.id]
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    obj = f.value.id
                    if obj in ("self", "cls") and owner:
                        dest = "function:" + rel + "::" + owner + "." + f.attr
                    elif obj in local_aliases and "::" not in local_aliases[obj]:
                        dest = "function:" + local_aliases[obj] + "::" + f.attr
                key = (origin, dest, part.lineno)
                if dest in nodes and dest != origin and key not in seen:
                    edges.append({"from": origin, "to": dest, "type": "call-site",
                                  "line": part.lineno, "evidence": "Python AST, not runtime"})
                    seen.add(key)
    counts = Counter(item["type"] for item in nodes.values())
    counts.update({"files_scanned": len(files), "edges": len(edges), "parse_errors": len(errors)})
    return {"metadata": {"scope": "PUBLIC_STAGE111_ONLY", "sha": sha,
                         "limitations": "Python AST conservative edges incl. function-local imports; Go regex declarations replaced by separate Go AST artifact; no original parity"},
            "counts": dict(counts), "nodes": list(nodes.values()), "edges": edges, "errors": errors}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument("--sha", default="UNPINNED")
    parser.add_argument("--out", type=pathlib.Path,
                        default=pathlib.Path("docs/architecture/mvkview-recovery/stage111-public-graph.json"))
    args = parser.parse_args()
    data = analyze(args.repo, args.sha)
    if not data["counts"]["files_scanned"] or data["errors"]:
        raise SystemExit("Missing sources or Python parse errors: " + str(data["errors"][:5]))
    output = args.out if args.out.is_absolute() else args.repo / args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["counts"], ensure_ascii=False))

if __name__ == "__main__":
    main()
