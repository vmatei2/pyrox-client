#!/usr/bin/env python3
"""Report whether codewiki_docs/ is stale relative to the working tree.

Runs as a SessionStart hook and as the check step of the /codewiki skill.
Stdlib + `git` only: no CodeWiki venv, no GitPython, no LLM. Typical run is
well under 100ms so it can sit on every session start.

Staleness model (mirrors CodeWiki's own MCP-side detection in
codewiki/mcp/tools/analysis.py at snapshot 4c18fac):

  baseline   = codewiki_docs/metadata.json -> generation_info.commit_id
               (written by close_session, NOT by write_doc_file)
  changed    = git diff baseline..HEAD  +  staged + unstaged + untracked
  affected   = modules in module_tree.json owning any changed file
  stale      = affected is non-empty

Granularity is module-level: a changed file only matters if module_tree.json
claims it. A README or CI edit therefore reports fresh, which is correct --
no module doc describes it.

Output: JSON on stdout for the SessionStart hook contract, or a human summary
with --text. Exit code is always 0 except for --exit-code mode; a broken
checker must never block a session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DOCS_DIRNAME = "codewiki_docs"
MAX_FILES_SHOWN = 8
# How often the "never generated" / "incomplete generation" advisories may
# re-appear. Drift notices are not rate limited -- they are actionable.
ADVISORY_INTERVAL_S = 24 * 60 * 60


def git(repo: Path, *args: str, strip: bool = True) -> str | None:
    """Run a git command, returning stdout or None on any failure.

    strip=False matters for `status --porcelain -z`, whose first field starts
    with a significant space (" M path") that .strip() would silently eat,
    shifting the path by one character.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() if strip else out.stdout


def porcelain_paths(repo: Path) -> list[str]:
    """Working-tree paths from `git status`: staged, unstaged, untracked.

    Rename entries ("R  old -> new") contribute both sides, matching how
    CodeWiki collects diff.a_path and diff.b_path.
    """
    raw = git(repo, "status", "--porcelain", "-z", "--untracked-files=all", strip=False)
    if raw is None:
        return []

    paths: list[str] = []
    fields = raw.split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        # For renames/copies git emits the source path as the next NUL field.
        if "R" in status or "C" in status:
            if i < len(fields):
                paths.append(fields[i])
                i += 1
        paths.append(path)
    return paths


def normalize(paths: list[str], docs_dirname: str) -> list[str]:
    """Drop generated paths and de-duplicate, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if not p:
            continue
        if p.startswith(".codewiki/") or p == docs_dirname or p.startswith(docs_dirname + "/"):
            continue
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def find_affected(module_tree: dict, changed: list[str]) -> tuple[set[str], set[str]]:
    """Map changed files to (affected leaf-ish modules, cascade parents).

    Matching is deliberately identical to CodeWiki's _find_affected_modules so
    this check agrees with what analyze_repo will report later.
    """
    affected: set[str] = set()
    cascade: set[str] = set()

    def walk(tree: dict, parents: list[str]) -> None:
        for name, info in tree.items():
            if not isinstance(info, dict):
                continue
            hit = False
            for comp in info.get("components", []):
                comp_file = str(comp).split("::")[0]
                for cf in changed:
                    if (
                        comp_file == cf
                        or comp_file.endswith("/" + cf)
                        or cf.endswith("/" + comp_file)
                        or cf.startswith(comp_file + "/")
                        or comp_file.startswith(cf + "/")
                    ):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                affected.add(name)
                cascade.update(parents)
            children = info.get("children")
            if isinstance(children, dict) and children:
                walk(children, parents + [name])

    walk(module_tree, [])
    if affected:
        cascade.add("overview")
    return affected, cascade


def check(repo: Path) -> dict:
    """Return a status dict. `state` is the field callers should branch on."""
    docs = repo / DOCS_DIRNAME
    metadata_path = docs / "metadata.json"
    tree_path = docs / "module_tree.json"

    if not metadata_path.exists() or not tree_path.exists():
        return {"state": "absent", "docs_dir": DOCS_DIRNAME}

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        module_tree = json.loads(tree_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"state": "unreadable", "detail": str(exc)}

    if not isinstance(module_tree, dict) or not module_tree:
        # The failure mode from a partially-failed run: docs exist but nothing
        # is mapped, so every later freshness check would falsely say "fresh".
        return {"state": "empty_tree", "docs_dir": DOCS_DIRNAME}

    info = metadata.get("generation_info", {}) if isinstance(metadata, dict) else {}
    baseline = info.get("commit_id")
    generated_at = info.get("timestamp")
    head = git(repo, "rev-parse", "HEAD")

    changed: list[str] = []
    baseline_ok = True

    if baseline and head and baseline != head:
        diff = git(repo, "diff", "--name-only", f"{baseline}..{head}")
        if diff is None:
            # Rebased, gc'd or shallow: the baseline commit is gone. Cannot
            # enumerate committed drift -- say so rather than claim fresh.
            baseline_ok = False
        elif diff:
            changed.extend(diff.splitlines())

    changed.extend(porcelain_paths(repo))
    changed = normalize(changed, DOCS_DIRNAME)

    if not baseline_ok:
        return {
            "state": "baseline_lost",
            "baseline": baseline,
            "generated_at": generated_at,
            "docs_dir": DOCS_DIRNAME,
        }

    affected, cascade = find_affected(module_tree, changed)

    return {
        "state": "stale" if affected else "fresh",
        "baseline": baseline,
        "head": head,
        "generated_at": generated_at,
        "docs_dir": DOCS_DIRNAME,
        "changed_files": changed,
        "affected_modules": sorted(affected),
        "cascade_modules": sorted(cascade),
    }


def advisory_due(repo: Path, key: str) -> bool:
    """Rate limit the non-actionable notices to once per ADVISORY_INTERVAL_S."""
    # hashlib, not hash(): PYTHONHASHSEED randomization would give every run a
    # different marker filename and silently defeat the rate limit.
    digest = hashlib.sha1(str(repo).encode("utf-8")).hexdigest()[:10]
    marker = Path(os.environ.get("TMPDIR", "/tmp")) / f"claude-codewiki-{key}-{digest}"
    now = time.time()
    try:
        if marker.exists() and now - marker.stat().st_mtime < ADVISORY_INTERVAL_S:
            return False
        marker.touch()
    except OSError:
        return True
    return True


def summarize(result: dict, repo: Path, for_hook: bool) -> str | None:
    """Render the message for the agent, or None to stay silent."""
    state = result["state"]

    if state == "fresh":
        if for_hook:
            return None
        return "codewiki_docs/ is up to date: no changed file maps to a documented module."

    if state == "absent":
        if for_hook and not advisory_due(repo, "absent"):
            return None
        return (
            "CodeWiki architecture docs have never been generated for this repo "
            "(no codewiki_docs/metadata.json). If the user wants generated "
            "architecture documentation, run the `codewiki` skill; otherwise ignore this."
        )

    if state == "empty_tree":
        if for_hook and not advisory_due(repo, "empty"):
            return None
        return (
            "codewiki_docs/module_tree.json is empty — a previous generation ran but "
            "never saved a module tree, so freshness checks cannot work. Re-run the "
            "`codewiki` skill in full mode to rebuild the baseline."
        )

    if state == "unreadable":
        if for_hook and not advisory_due(repo, "unreadable"):
            return None
        return (
            f"codewiki_docs/ metadata is unreadable ({result.get('detail')}). "
            "Re-run the `codewiki` skill in full mode."
        )

    if state == "baseline_lost":
        if for_hook and not advisory_due(repo, "baseline"):
            return None
        return (
            f"codewiki_docs/ records baseline commit {str(result.get('baseline'))[:8]}, which is "
            "no longer reachable (rebase, squash or gc). Incremental drift cannot be computed. "
            "Run the `codewiki` skill in full mode to re-baseline."
        )

    # stale
    files = result["changed_files"]
    shown = ", ".join(files[:MAX_FILES_SHOWN])
    if len(files) > MAX_FILES_SHOWN:
        shown += f", +{len(files) - MAX_FILES_SHOWN} more"
    lines = [
        "CodeWiki architecture docs are stale.",
        f"  Baseline: {str(result.get('baseline'))[:8]} ({result.get('generated_at')})",
        f"  Changed since: {shown}",
        f"  Modules to update: {', '.join(result['affected_modules'])}",
    ]
    if result["cascade_modules"]:
        lines.append(f"  Parents to refresh: {', '.join(result['cascade_modules'])}")
    lines.append(
        "  Mention this once, then continue with the user's request. Offer the "
        "`codewiki` skill (incremental mode) — do not start a regeneration unprompted."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the raw status dict")
    parser.add_argument("--text", action="store_true", help="emit a human summary, always")
    parser.add_argument(
        "--exit-code",
        action="store_true",
        help="exit 1 when docs are stale (for scripts/CI)",
    )
    args = parser.parse_args()

    repo = Path(os.environ.get("CLAUDE_PROJECT_DIR", "")) if os.environ.get(
        "CLAUDE_PROJECT_DIR"
    ) else Path(__file__).resolve().parents[2]

    try:
        result = check(repo)
    except Exception as exc:  # never break a session over a doc check
        if args.json:
            print(json.dumps({"state": "error", "detail": str(exc)}))
        return 0

    if args.json:
        print(json.dumps(result, indent=2))
        return 1 if (args.exit_code and result["state"] == "stale") else 0

    message = summarize(result, repo, for_hook=not args.text)

    if args.text:
        print(message or "codewiki_docs/ is up to date.")
        return 1 if (args.exit_code and result["state"] == "stale") else 0

    if message:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": message,
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
