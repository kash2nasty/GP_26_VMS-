"""Where a finished session gets written, and under what name.

Shared by run_session.py (webcam capture from the CLI) and api/capture.py (capture
from the browser) so the two cannot drift into producing differently-shaped or
differently-named files. The API's reader keys sessions off these filenames, so a
divergence here would show up as sessions silently missing from the dashboard.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scoring.pipeline import enrich_session

SESSIONS_DIR = Path("sessions")

# Must stay in step with api/repository.py, which parses these back out.
RAW_SUFFIX = ".json"
SCORED_SUFFIX = ".scored.json"
FILENAME_PREFIX = "session_"
STAMP_FORMAT = "%Y%m%dT%H%M%SZ"


@dataclass
class SaveResult:
    session_id: str
    raw_path: Path
    scored_path: Path | None
    # The scored dict when scoring ran, otherwise the raw one.
    result: dict

    @property
    def written(self) -> list[Path]:
        return [p for p in (self.raw_path, self.scored_path) if p is not None]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime(STAMP_FORMAT)


def save_session(
    result: dict,
    out_dir: Path | str = SESSIONS_DIR,
    score: bool = True,
    session_id: str | None = None,
) -> SaveResult:
    """Write a session to disk, optionally with the screening/exercise blocks.

    The raw capture is ALWAYS written, even when scoring is requested. It is the
    expensive artifact, re-scoring it later with updated thresholds is a
    first-class use case, and score_session.py skips .scored.json inputs -- so a
    scored-only output would be a dead end.
    """
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = session_id or utc_stamp()

    raw_path = directory / f"{FILENAME_PREFIX}{stamp}{RAW_SUFFIX}"
    raw_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    scored_path = None
    final = result
    if score:
        final = enrich_session(result)
        scored_path = directory / f"{FILENAME_PREFIX}{stamp}{SCORED_SUFFIX}"
        scored_path.write_text(json.dumps(final, indent=2), encoding="utf-8")

    return SaveResult(
        session_id=stamp,
        raw_path=raw_path,
        scored_path=scored_path,
        result=final,
    )
