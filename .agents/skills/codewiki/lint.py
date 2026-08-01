#!/usr/bin/env python3
"""Lint the generated architecture overview: Mermaid syntax, links, structure.

Replaces the validation CodeWiki's `write_doc_file` did via a Node subprocess.
This is a *lint*, not a parse: it catches the syntax mistakes LLMs actually
make in Mermaid rather than proving a diagram renders. For true parsing,
`npx -y @mermaid-js/mermaid-cli -i file.md` will do it at the cost of pulling
Chromium; this runs in milliseconds with no dependencies.

The directory contract is deliberately strict: overview.md is the only file
allowed in codewiki_docs/.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

DOCS_DIR = "codewiki_docs"

VALID_HEADERS = (
    "graph", "flowchart", "sequenceDiagram", "classDiagram", "stateDiagram",
    "stateDiagram-v2", "erDiagram", "journey", "gantt", "pie", "gitGraph",
    "mindmap", "timeline", "quadrantChart", "requirementDiagram", "C4Context",
    "block-beta", "sankey-beta", "xychart-beta",
)

# Directives we ban in generated docs: they either need a live DOM or silently
# do nothing in a static renderer.
BANNED_DIRECTIVES = ("click ", "linkStyle ", "callback ")

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
NODE_DEF_RE = re.compile(r"\b([A-Za-z_][\w]*)\s*[\[\(\{]")
ARROW_RE = re.compile(r"(-->|---|-\.->|==>|--x|--o|<-->)")


def repo_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env).resolve() if env else Path(__file__).resolve().parents[3]


def extract_mermaid(text: str) -> list[tuple[int, list[str]]]:
    """Return [(first_body_line_number, body_lines)] for each ```mermaid block."""
    blocks: list[tuple[int, list[str]]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```mermaid"):
            start = i + 2  # 1-indexed line of the first body line
            body: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                body.append(lines[i])
                i += 1
            if body:
                blocks.append((start, body))
        i += 1
    return blocks


def lint_mermaid(block: list[str], first_line: int, rel: str) -> list[tuple[str, str]]:
    """Return [(level, message)] for one diagram."""
    out: list[tuple[str, str]] = []
    body = [ln for ln in block if ln.strip() and not ln.strip().startswith("%%")]
    if not body:
        return [("error", f"{rel}:{first_line}: empty mermaid block")]

    header = body[0].strip()
    if not header.startswith(VALID_HEADERS):
        out.append((
            "error",
            f"{rel}:{first_line}: diagram must start with a type "
            f"(graph TD, flowchart LR, sequenceDiagram, ...), got {header[:40]!r}",
        ))

    is_flowchart = header.startswith(("graph", "flowchart"))

    depth = 0
    for offset, raw in enumerate(block):
        line = raw.strip()
        lineno = first_line + offset
        if not line or line.startswith("%%"):
            continue

        stripped = line.split("%%")[0].strip()

        if stripped.startswith("subgraph"):
            depth += 1
        elif stripped == "end":
            depth -= 1
            if depth < 0:
                out.append(("error", f"{rel}:{lineno}: 'end' without a matching 'subgraph'"))
                depth = 0

        for banned in BANNED_DIRECTIVES:
            if stripped.startswith(banned):
                out.append((
                    "error",
                    f"{rel}:{lineno}: '{banned.strip()}' is not allowed in generated docs",
                ))

        if stripped.count('"') % 2:
            out.append(("error", f"{rel}:{lineno}: odd number of double quotes"))

        for opener, closer in (("[", "]"), ("(", ")"), ("{", "}")):
            if stripped.count(opener) != stripped.count(closer):
                out.append((
                    "warn",
                    f"{rel}:{lineno}: unbalanced {opener}{closer} — "
                    "quote the label if it contains brackets",
                ))
                break

        if is_flowchart:
            # Unquoted labels containing characters that end the label early.
            for label in re.findall(r"\[([^\]\[]*)\]", stripped):
                if label.startswith('"') and label.endswith('"'):
                    continue
                bad = [ch for ch in "()<>{}&#" if ch in label]
                if bad:
                    out.append((
                        "error",
                        f"{rel}:{lineno}: label {label[:30]!r} contains {''.join(bad)} — "
                        'wrap it in double quotes: ["like this"]',
                    ))

            # `end` as a node id breaks the flowchart parser.
            for node in NODE_DEF_RE.findall(stripped):
                if node == "end":
                    out.append((
                        "error",
                        f"{rel}:{lineno}: 'end' cannot be a node id — rename it",
                    ))

            if ARROW_RE.search(stripped):
                left, _, right = re.split(ARROW_RE, stripped, maxsplit=1)[:3]
                if not left.strip() or not right.strip():
                    out.append(("error", f"{rel}:{lineno}: arrow with a missing endpoint"))

    if depth > 0:
        out.append((
            "error",
            f"{rel}:{first_line}: {depth} unclosed 'subgraph' block(s) — each needs an 'end'",
        ))
    return out


def lint_file(path: Path, repo: Path, known_docs: set[str]) -> list[tuple[str, str]]:
    rel = path.relative_to(repo).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [("error", f"{rel}: unreadable ({exc})")]

    findings: list[tuple[str, str]] = []

    blocks = extract_mermaid(text)
    if not blocks and path.name != "overview.md":
        findings.append(("warn", f"{rel}: no Mermaid diagram — every module doc should have one"))
    for first_line, body in blocks:
        findings.extend(lint_mermaid(body, first_line, rel))

    for lineno, line in enumerate(text.split("\n"), 1):
        for label, target in LINK_RE.findall(line):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean = target.split("#")[0]
            if not clean:
                continue
            if clean.endswith(".md"):
                # Sibling doc, repo-relative path, or a peer of the file itself:
                # any of the three resolving is enough.
                if (
                    clean not in known_docs
                    and not (repo / clean).exists()
                    and not (path.parent / clean).exists()
                ):
                    findings.append((
                        "error",
                        f"{rel}:{lineno}: link to missing doc {clean!r} (label {label!r})",
                    ))
            elif not (path.parent / clean).exists() and not (repo / clean).exists():
                findings.append((
                    "warn", f"{rel}:{lineno}: link target {clean!r} does not exist"
                ))

    heading_text = text
    if text.startswith("---\n"):
        frontmatter_end = text.find("\n---\n", 4)
        if frontmatter_end >= 0:
            heading_text = text[frontmatter_end + 5 :]
    if not heading_text.lstrip().startswith("#"):
        findings.append(("warn", f"{rel}: does not start with a top-level heading"))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path, help="specific files (default: all)")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    repo = repo_root()
    docs = repo / DOCS_DIR

    unexpected: list[Path] = []
    if args.files:
        targets = [f if f.is_absolute() else repo / f for f in args.files]
    else:
        if not docs.exists():
            print(f"No {DOCS_DIR}/ to lint.", file=sys.stderr)
            return 2
        targets = [docs / "overview.md"]
        unexpected = sorted(path for path in docs.iterdir() if path.name != "overview.md")

    if not targets:
        print(f"No markdown files found in {DOCS_DIR}/.", file=sys.stderr)
        return 2

    known_docs = {p.name for p in docs.glob("*.md")} if docs.exists() else set()

    errors = warnings = 0
    for path in unexpected:
        print(f"ERROR {path.relative_to(repo)}: overview.md must be the only generated file")
        errors += 1
    for path in targets:
        for level, message in lint_file(path, repo, known_docs):
            print(f"{level.upper():<5} {message}")
            if level == "error":
                errors += 1
            else:
                warnings += 1

    total = len(targets)
    print(f"\n{total} file(s): {errors} error(s), {warnings} warning(s).")
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
