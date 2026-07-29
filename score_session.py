"""CLI: score an existing session JSON and emit an enriched copy.

Kept standalone from run_session.py because re-scoring previously captured
sessions with updated logic is a real use case -- the capture is expensive and
the scoring thresholds are provisional.

Examples:
    python score_session.py sessions/session_20260729T024816Z.json
    python score_session.py sessions/*.json
    python score_session.py sessions/s.json --out-dir reports --quiet
    python score_session.py sessions/s.json --stdout          # don't write a file
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scoring.pipeline import describe, enrich_session

SCORED_SUFFIX = ".scored.json"


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Score an existing VOMS session JSON and emit an enriched copy."
    )
    p.add_argument("paths", nargs="+", help="One or more session JSON files.")
    p.add_argument("--out-dir", default=None,
                   help="Where to write scored output. Default: alongside the input.")
    p.add_argument("--stdout", action="store_true",
                   help="Print the enriched JSON without writing a file.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress the per-file summary line.")
    return p.parse_args(argv)


def scored_path(source: Path, out_dir: str | None) -> Path:
    # Strip a .json tail so we get session_x.scored.json, not session_x.json.scored.json
    stem = source.name[:-len(".json")] if source.name.endswith(".json") else source.name
    directory = Path(out_dir) if out_dir else source.parent
    return directory / f"{stem}{SCORED_SUFFIX}"


def score_file(source: Path, out_dir: str | None, to_stdout: bool, quiet: bool) -> dict:
    session = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(session, dict):
        raise ValueError("expected a JSON object at the top level")

    enriched = enrich_session(session)

    if to_stdout:
        print(json.dumps(enriched, indent=2))
    else:
        target = scored_path(source, out_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(enriched, indent=2), encoding="utf-8")
        if not quiet:
            print(f"{source.name}: {describe(enriched)}")
            print(f"  -> {target}")

    return enriched


def main(argv=None):
    args = parse_args(argv)

    failures = 0
    for raw in args.paths:
        source = Path(raw)
        if not source.exists():
            print(f"error: no such file: {source}", file=sys.stderr)
            failures += 1
            continue
        # Don't recursively score our own output.
        if source.name.endswith(SCORED_SUFFIX):
            if not args.quiet:
                print(f"skipping already-scored file: {source.name}", file=sys.stderr)
            continue
        try:
            score_file(source, args.out_dir, args.stdout, args.quiet)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"error: {source}: {exc}", file=sys.stderr)
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
