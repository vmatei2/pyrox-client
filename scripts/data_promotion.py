"""Assess whether a candidate DuckDB pointer should be promoted.

The upstream ``hyrox_analysis`` pipeline owns ``latest.json``. This helper is
used by the consumer's refresh workflow to validate that candidate against the
pointer contract understood by the running service and to decide whether its
SHA differs from ``deploy-current.json``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from pyrox_api_service.fetch_db import ArtifactPointer, parse_pointer


@dataclass(frozen=True)
class PromotionDecision:
    """Validated candidate/current pointers and the resulting action."""

    candidate: ArtifactPointer
    current: ArtifactPointer
    promote: bool


def load_pointer(path: Path) -> dict[str, Any]:
    """Read a pointer JSON object from ``path`` with a clear validation error."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read pointer JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"pointer JSON in {path} must be an object")
    return payload


def assess_promotion(
    candidate_payload: Mapping[str, Any],
    current_payload: Mapping[str, Any],
) -> PromotionDecision:
    """Validate both pointers and promote only when their SHA-256 values differ."""
    candidate = parse_pointer(dict(candidate_payload))
    current = parse_pointer(dict(current_payload))
    return PromotionDecision(
        candidate=candidate,
        current=current,
        promote=candidate.sha256 != current.sha256,
    )


def _write_github_outputs(path: Path, decision: PromotionDecision) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"promote={'true' if decision.promote else 'false'}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument(
        "--github-output",
        type=Path,
        help="Append workflow outputs to this GitHub Actions output file.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    decision = assess_promotion(
        load_pointer(args.candidate),
        load_pointer(args.current),
    )
    if args.github_output:
        _write_github_outputs(args.github_output, decision)
    print(
        json.dumps(
            {
                "candidate": asdict(decision.candidate),
                "current": asdict(decision.current),
                "promote": decision.promote,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
