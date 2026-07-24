#!/usr/bin/env python3
"""Static analysis + bookkeeping for the /codewiki architecture wiki.

Replaces CodeWiki's `analyze_repo` MCP tool for a repo this size. Stdlib only —
no Tree-sitter, no CodeWiki install, no LLM. Python is parsed with `ast`;
JS/TS/JSX/TSX imports and exports are matched with regexes, which is
approximate by nature and flagged as such in the output.

Three subcommands:

  analyze   Build the component index and in-repo import graph. Writes to
            .codewiki/ (gitignored) and prints a clustering brief.
  finalize  Validate a module tree against the index, then write the two
            files the freshness hook reads: codewiki_docs/module_tree.json
            and codewiki_docs/metadata.json (baseline = current HEAD).
  check     Re-validate what is already on disk (docs vs tree, tree vs index).

The on-disk contract is deliberately identical to CodeWiki's, so
.claude/hooks/codewiki-freshness.py works unchanged either way.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PY_EXT = {".py"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx"}
SOURCE_EXT = PY_EXT | JS_EXT

# Directories never worth documenting. Tests are excluded because they
# document themselves; ui/ios is Capacitor's generated Xcode project.
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", "dist", "build", ".codewiki", "codewiki_docs", "wiki",
    "docs", "papers", "example_notebooks", ".claude", ".github", "tests",
}
SKIP_PATH_PREFIXES = ("ui/ios/", "ui/dist/", "ui/android/")
SKIP_FILE_RE = re.compile(r"(^|/)(test_|conftest\.py$)|\.(test|spec)\.[jt]sx?$")

ANALYSIS_DIR = ".codewiki"
DOCS_DIR = "codewiki_docs"

# --- JS/TS surface patterns. Approximate by construction. -------------------
# The clause between `import`/`export` and `from` routinely spans several lines
# ("import {\n  a,\n  b,\n} from './x'"), so this must cross newlines. It cannot
# contain a quote, paren or semicolon, which bounds the lazy match safely.
JS_IMPORT_RE = re.compile(
    r"""\bimport\s+(?:[^'"();]*?\bfrom\s*)?['"]([^'"]+)['"]"""
    r"""|\bexport\s+[^'"();]*?\bfrom\s*['"]([^'"]+)['"]""",
    re.S,
)
JS_REQUIRE_RE = re.compile(r"""(?:require|import)\s*\(\s*['"]([^'"]+)['"]\s*\)""")
JS_EXPORT_RE = re.compile(
    r"""^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)""",
    re.M,
)
JS_TOPLEVEL_FN_RE = re.compile(
    r"""^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|^const\s+([A-Z][\w$]*)\s*=\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>""",
    re.M,
)


def repo_root() -> Path:
    import os
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


def head_commit(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def iter_sources(repo: Path):
    for path in sorted(repo.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_EXT:
            continue
        rel = path.relative_to(repo).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(repo).parts[:-1]):
            continue
        if rel.startswith(SKIP_PATH_PREFIXES) or SKIP_FILE_RE.search(rel):
            continue
        yield rel, path


# --- Python -----------------------------------------------------------------

def python_module_names(rel: str) -> list[str]:
    """Dotted names a file may be imported as, longest first.

    src-layout means src/pyrox/core.py is imported as pyrox.core, never
    src.pyrox.core, so both spellings are registered and resolution picks
    whichever the importer actually wrote.
    """
    parts = rel[:-3].split("/")
    names = []
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if parts:
        names.append(".".join(parts))
        if parts[0] == "src" and len(parts) > 1:
            names.append(".".join(parts[1:]))
    return names


def parse_python(rel: str, path: Path) -> tuple[list[dict], list[tuple[str, int]]]:
    """Return (components, raw_imports). raw_imports is [(dotted, level)]."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (SyntaxError, OSError, UnicodeDecodeError):
        return [], []

    components: list[dict] = []
    imports: list[tuple[str, int]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            components.append({
                "id": f"{rel}::{node.name}",
                "file": rel,
                "name": node.name,
                "kind": "class",
                "line": node.lineno,
                "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
                "methods": methods,
                "doc": ast.get_docstring(node, clean=True),
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            components.append({
                "id": f"{rel}::{node.name}",
                "file": rel,
                "name": node.name,
                "kind": "function",
                "line": node.lineno,
                "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
                "public": not node.name.startswith("_"),
                "doc": ast.get_docstring(node, clean=True),
            })

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, 0))
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "", node.level))

    return components, imports


def resolve_python_import(
    dotted: str, level: int, importer: str, by_module: dict[str, str]
) -> str | None:
    if level:  # relative: walk up from the importer's package
        base = importer.split("/")[:-1]
        for _ in range(level - 1):
            if base:
                base.pop()
        target = "/".join(base + (dotted.split(".") if dotted else []))
        for cand in (f"{target}.py", f"{target}/__init__.py"):
            if cand in by_module.values() or cand in _ALL_FILES:
                return cand
        return None

    parts = dotted.split(".")
    while parts:  # longest prefix wins: pyrox.core.X -> pyrox.core
        hit = by_module.get(".".join(parts))
        if hit:
            return hit
        parts.pop()
    return None


# --- JavaScript / TypeScript ------------------------------------------------

def parse_js(rel: str, path: Path) -> tuple[list[dict], list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], []

    names: list[str] = []
    for m in JS_EXPORT_RE.finditer(text):
        names.append(m.group(1))
    for m in JS_TOPLEVEL_FN_RE.finditer(text):
        names.append(m.group(1) or m.group(2))

    seen: set[str] = set()
    components = []
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        components.append({
            "id": f"{rel}::{name}",
            "file": rel,
            "name": name,
            "kind": "component" if name[:1].isupper() else "function",
            "approximate": True,
        })

    specs = {g for match in JS_IMPORT_RE.findall(text) for g in match if g}
    specs |= set(JS_REQUIRE_RE.findall(text))
    return components, sorted(specs)


def resolve_js_import(spec: str, importer: str, all_files: set[str]) -> str | None:
    if not spec.startswith("."):
        return None  # bare specifier: node_modules, not ours
    base = Path(importer).parent / spec
    try:
        target = base.resolve().relative_to(Path(importer).parent.resolve().anchor)
    except ValueError:
        target = base
    norm = Path(str(base)).as_posix()
    # Normalize ".." segments without touching the filesystem.
    stack: list[str] = []
    for part in norm.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if stack:
                stack.pop()
        else:
            stack.append(part)
    cand_base = "/".join(stack)
    for suffix in ("", ".js", ".jsx", ".ts", ".tsx",
                   "/index.js", "/index.jsx", "/index.ts", "/index.tsx"):
        cand = cand_base + suffix
        if cand in all_files:
            return cand
    return None


# --- Analysis ---------------------------------------------------------------

_ALL_FILES: set[str] = set()


def analyze(repo: Path) -> dict:
    global _ALL_FILES
    files = list(iter_sources(repo))
    _ALL_FILES = {rel for rel, _ in files}

    by_module: dict[str, str] = {}
    for rel, _ in files:
        if rel.endswith(".py"):
            for name in python_module_names(rel):
                by_module.setdefault(name, rel)

    components: list[dict] = []
    edges: list[list[str]] = []
    per_file: dict[str, dict] = {}

    for rel, path in files:
        if rel.endswith(".py"):
            comps, raw = parse_python(rel, path)
            targets = {
                t for dotted, level in raw
                if (t := resolve_python_import(dotted, level, rel, by_module))
                and t != rel
            }
        else:
            comps, specs = parse_js(rel, path)
            targets = {
                t for spec in specs
                if (t := resolve_js_import(spec, rel, _ALL_FILES)) and t != rel
            }

        components.extend(comps)
        for t in sorted(targets):
            edges.append([rel, t])
        try:
            loc = sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
        except OSError:
            loc = 0
        per_file[rel] = {"loc": loc, "components": len(comps), "imports": sorted(targets)}

    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    for src, dst in edges:
        fan_out[src] += 1
        fan_in[dst] += 1

    for rel, info in per_file.items():
        info["fan_in"] = fan_in.get(rel, 0)
        info["fan_out"] = fan_out.get(rel, 0)

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "commit": head_commit(repo),
        "files": per_file,
        "components": components,
        "edges": edges,
        "totals": {
            "files": len(per_file),
            "components": len(components),
            "edges": len(edges),
            "loc": sum(f["loc"] for f in per_file.values()),
        },
    }


def brief(result: dict) -> str:
    """A clustering brief: what to read to decide module boundaries."""
    files = result["files"]
    lines = [
        f"{result['totals']['files']} files, {result['totals']['components']} components, "
        f"{result['totals']['loc']} LOC, {result['totals']['edges']} in-repo import edges.",
        "",
        "Top-level directories:",
    ]
    by_dir: dict[str, list[str]] = defaultdict(list)
    for rel in files:
        by_dir[rel.split("/")[0]].append(rel)
    for d, members in sorted(by_dir.items(), key=lambda kv: -len(kv[1])):
        loc = sum(files[m]["loc"] for m in members)
        lines.append(f"  {d:<20} {len(members):>3} files  {loc:>6} LOC")

    lines += ["", "Hubs (most depended upon):"]
    for rel, info in sorted(files.items(), key=lambda kv: -kv[1]["fan_in"])[:10]:
        if info["fan_in"]:
            lines.append(f"  fan-in {info['fan_in']:>2}  {rel}")

    lines += ["", "Entry points (nothing in-repo imports them):"]
    orphans = [r for r, i in files.items() if i["fan_in"] == 0 and i["fan_out"] > 0]
    for rel in sorted(orphans)[:15]:
        lines.append(f"  {rel}")
    if len(orphans) > 15:
        lines.append(f"  ... and {len(orphans) - 15} more")

    lines += ["", "Largest files (read these first):"]
    for rel, info in sorted(files.items(), key=lambda kv: -kv[1]["loc"])[:10]:
        lines.append(f"  {info['loc']:>5} LOC  {rel}")
    return "\n".join(lines)


# --- Finalize / check -------------------------------------------------------

def load_index(repo: Path) -> dict | None:
    p = repo / ANALYSIS_DIR / "analysis.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def validate_tree(tree: dict, index: dict) -> list[str]:
    """Every component ID in the tree must exist in the index."""
    known = {c["id"] for c in index["components"]}
    known_files = set(index["files"])
    problems: list[str] = []

    def walk(node: dict, path: str) -> None:
        for name, info in node.items():
            here = f"{path}/{name}" if path else name
            if not isinstance(info, dict):
                problems.append(f"{here}: value is not an object")
                continue
            comps = info.get("components", [])
            if not isinstance(comps, list):
                problems.append(f"{here}: 'components' must be a list")
                continue
            for comp in comps:
                if comp in known:
                    continue
                # A bare file path is acceptable; a hallucinated symbol is not.
                if comp.split("::")[0] in known_files and "::" not in comp:
                    continue
                problems.append(f"{here}: unknown component {comp!r}")
            children = info.get("children", {})
            if children:
                walk(children, here)

    walk(tree, "")
    covered = {c for info in _flatten(tree) for c in info.get("components", [])}
    orphan_files = sorted(
        f for f in known_files
        if not any(c.split("::")[0] == f for c in covered)
    )
    if orphan_files:
        problems.append(
            f"{len(orphan_files)} file(s) in no module: {', '.join(orphan_files[:8])}"
            + (" ..." if len(orphan_files) > 8 else "")
        )
    return problems


def _flatten(tree: dict):
    for info in tree.values():
        if isinstance(info, dict):
            yield info
            yield from _flatten(info.get("children", {}) or {})


def finalize(repo: Path, tree_path: Path, force: bool) -> int:
    index = load_index(repo)
    if index is None:
        print("No .codewiki/analysis.json — run `analyze.py analyze` first.", file=sys.stderr)
        return 2
    try:
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read module tree: {exc}", file=sys.stderr)
        return 2

    problems = validate_tree(tree, index)
    docs = repo / DOCS_DIR
    module_names = [name for name in _names(tree)]
    missing_docs = [n for n in module_names if not (docs / f"{n}.md").exists()]
    if missing_docs:
        problems.append(f"no .md written for: {', '.join(missing_docs)}")
    if not (docs / "overview.md").exists():
        problems.append("overview.md is missing")

    if problems and not force:
        print("Refusing to finalize:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\nFix these, or pass --force to write the baseline anyway.", file=sys.stderr)
        return 1

    docs.mkdir(parents=True, exist_ok=True)
    (docs / "module_tree.json").write_text(
        json.dumps(tree, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    commit = head_commit(repo)
    metadata_path = docs / "metadata.json"
    existing: dict = {}
    if metadata_path.exists():
        try:
            existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    existing["generation_info"] = {
        **existing.get("generation_info", {}),
        # Baseline on the commit the analysis saw, not on HEAD at write time.
        "commit_id": index.get("commit") or commit,
        "timestamp": datetime.now().isoformat(),
        "generator": "claude-code/codewiki-skill",
    }
    existing["statistics"] = {
        "total_components": index["totals"]["components"],
        "files": index["totals"]["files"],
        "modules": len(module_names),
    }
    existing["files_generated"] = sorted(p.name for p in docs.glob("*.md"))
    metadata_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    if problems:
        print("Finalized with warnings:")
        for p in problems:
            print(f"  - {p}")
    print(
        f"Baseline written: {len(module_names)} modules, "
        f"commit {(index.get('commit') or 'unknown')[:8]}."
    )
    return 0


def _names(tree: dict):
    for name, info in tree.items():
        yield name
        if isinstance(info, dict):
            yield from _names(info.get("children", {}) or {})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_an = sub.add_parser("analyze", help="build the component index and import graph")
    p_an.add_argument("--json", action="store_true", help="print the full index instead of the brief")

    p_fin = sub.add_parser("finalize", help="validate a module tree and write the baseline")
    p_fin.add_argument("tree", type=Path, help="path to the module tree JSON")
    p_fin.add_argument("--force", action="store_true", help="write despite validation problems")

    sub.add_parser("check", help="validate what is already on disk")

    args = parser.parse_args()
    repo = repo_root()

    if args.cmd == "analyze":
        result = analyze(repo)
        out_dir = repo / ANALYSIS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "analysis.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(brief(result))
            print(f"\nFull index: {ANALYSIS_DIR}/analysis.json")
        return 0

    if args.cmd == "finalize":
        return finalize(repo, args.tree, args.force)

    # check
    index = load_index(repo)
    tree_path = repo / DOCS_DIR / "module_tree.json"
    if index is None or not tree_path.exists():
        print("Nothing to check: run analyze and finalize first.", file=sys.stderr)
        return 2
    problems = validate_tree(json.loads(tree_path.read_text(encoding="utf-8")), index)
    if problems:
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Module tree is consistent with the current analysis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
