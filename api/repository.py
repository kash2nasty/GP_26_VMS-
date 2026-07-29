"""Session discovery and loading. No FastAPI here, so it can be tested directly.

THE THREE SHAPES THAT ACTUALLY EXIST ON DISK
    run_session.py has changed over time, so sessions/ is not uniform:

    1. raw + scored pair    -- the normal case now
    2. scored only          -- captured by an older --score run that wrote no raw file
    3. raw only             -- captured without --score

    A "session" here is the logical unit, keyed by its timestamp, not a file. Case 3
    is scored in memory via scoring.pipeline so the API can always serve a tier;
    `scoring_source` says which happened so the UI never implies a stored score
    that does not exist.

WHY STALE SCORES ARE SERVED AS-IS
    Some scored files were written by scoring schema 0.1.0, before protocol
    fidelity existed. Re-scoring them on read would make the API disagree with the
    file on disk, and this phase is read-only. They are served unchanged with
    `scoring_schema_version` exposed, so the UI can mark them as needing a
    re-score rather than silently presenting different numbers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from scoring.pipeline import enrich_session

SCORED_SUFFIX = ".scored.json"
RAW_SUFFIX = ".json"
FILENAME_PREFIX = "session_"

# Deleted sessions move here rather than being unlinked. A capture is an
# irreplaceable record of something a person physically did, and it cannot be
# regenerated from anything on disk, so a misclick should be recoverable. This is
# a subdirectory, and discover() only looks at files, so trashed sessions
# disappear from the dashboard exactly as if they had been removed.
TRASH_DIRNAME = "_deleted"

# Fallback timestamp format, matching the stamp run_session.py puts in filenames.
FILENAME_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSIONS_DIR = REPO_ROOT / "sessions"


class SessionNotFound(KeyError):
    """Raised when no file backs the requested session id."""


@dataclass
class SessionFiles:
    """The file(s) backing one logical session."""
    session_id: str
    raw_path: Path | None = None
    scored_path: Path | None = None

    @property
    def preferred_path(self) -> Path:
        """The scored file when present, else the raw capture."""
        return self.scored_path or self.raw_path


@dataclass
class LoadResult:
    session_id: str
    captured_at: str | None
    scoring_source: str          # "file" | "computed"
    scoring_schema_version: str | None
    session: dict = field(repr=False)


def split_filename(name: str):
    """Return (session_id, is_scored) for a session filename, or (None, False).

    Order matters: ".scored.json" must be tested before ".json", since the former
    also ends with the latter.
    """
    if name.endswith(SCORED_SUFFIX):
        stem, scored = name[: -len(SCORED_SUFFIX)], True
    elif name.endswith(RAW_SUFFIX):
        stem, scored = name[: -len(RAW_SUFFIX)], False
    else:
        return None, False

    if stem.startswith(FILENAME_PREFIX):
        stem = stem[len(FILENAME_PREFIX):]
    return (stem or None), scored


def _iso_from_unix(value) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        stamp = datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return stamp.isoformat().replace("+00:00", "Z")


def _iso_from_session_id(session_id: str) -> str | None:
    try:
        stamp = datetime.strptime(session_id, FILENAME_STAMP_FORMAT)
    except ValueError:
        return None
    return stamp.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def captured_at_for(session_id: str, session: dict) -> str | None:
    """Prefer the recorded start time; fall back to the filename stamp.

    started_at_unix is when capture actually began, whereas the filename stamp is
    when the file was written (roughly the end), so the recorded value is the more
    accurate of the two.
    """
    recorded = _iso_from_unix((session.get("session") or {}).get("started_at_unix"))
    return recorded or _iso_from_session_id(session_id)


def _get(block, key, default=None):
    return block.get(key, default) if isinstance(block, dict) else default


class SessionRepository:
    """Reads session JSON from a directory. Never writes."""

    def __init__(self, sessions_dir: Path | str = DEFAULT_SESSIONS_DIR):
        self.sessions_dir = Path(sessions_dir)

    # ---- discovery -------------------------------------------------------

    def discover(self) -> dict[str, SessionFiles]:
        """Group every session file in the directory by logical session id."""
        found: dict[str, SessionFiles] = {}
        if not self.sessions_dir.is_dir():
            return found

        for path in sorted(self.sessions_dir.iterdir()):
            if not path.is_file():
                continue
            session_id, is_scored = split_filename(path.name)
            if session_id is None:
                continue
            entry = found.setdefault(session_id, SessionFiles(session_id))
            if is_scored:
                entry.scored_path = path
            else:
                entry.raw_path = path
        return found

    # ---- loading ---------------------------------------------------------

    def load(self, session_id: str) -> LoadResult:
        entry = self.discover().get(session_id)
        if entry is None or entry.preferred_path is None:
            raise SessionNotFound(session_id)

        path = entry.preferred_path
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: expected a JSON object at the top level")

        if entry.scored_path is not None:
            source = "file"
        else:
            # Raw-only capture: score it in memory so the UI still gets a tier.
            data = enrich_session(data)
            source = "computed"

        summary = data.get("screening_summary") or {}
        return LoadResult(
            session_id=session_id,
            captured_at=captured_at_for(session_id, data),
            scoring_source=source,
            scoring_schema_version=_get(summary, "scoring_schema_version"),
            session=data,
        )

    # ---- deletion --------------------------------------------------------

    @property
    def trash_dir(self) -> Path:
        return self.sessions_dir / TRASH_DIRNAME

    def delete(self, session_id: str) -> list[str]:
        """Move a session's files into the trash directory.

        Returns the filenames moved. Raises SessionNotFound if the id matches
        nothing.

        The paths are taken from discover(), never built by joining the incoming
        id onto a directory. That matters because `session_id` arrives from a URL:
        constructing `sessions_dir / f"session_{session_id}.json"` would let
        "../../something" escape the directory, whereas looking the id up among
        filenames that were actually found on disk cannot.
        """
        entry = self.discover().get(session_id)
        if entry is None or entry.preferred_path is None:
            raise SessionNotFound(session_id)

        self.trash_dir.mkdir(parents=True, exist_ok=True)
        moved: list[str] = []
        for path in (entry.raw_path, entry.scored_path):
            if path is None:
                continue
            target = self.trash_dir / path.name
            # Never clobber a previous deletion of the same name.
            if target.exists():
                stem = target.name
                counter = 2
                while target.exists():
                    target = self.trash_dir / f"{stem}.{counter}"
                    counter += 1
            path.replace(target)
            moved.append(path.name)
        return moved

    # ---- summaries -------------------------------------------------------

    @staticmethod
    def summarize(result: LoadResult) -> dict:
        """Flatten one session into the fields the list view needs."""
        s = result.session
        summary = _get(s, "screening_summary") or {}
        quality = _get(summary, "data_quality") or {}
        fidelity = _get(summary, "protocol_fidelity") or {}
        symptoms = _get(s, "self_reported_symptoms") or {}
        tracking = _get(s, "tracking_quality") or {}
        head = _get(s, "head_motion") or {}

        return {
            "id": result.session_id,
            "captured_at": result.captured_at,
            "duration_s": _get(_get(s, "session") or {}, "duration_s"),
            "symptom_score": _get(symptoms, "score"),
            "symptom_provided": bool(_get(symptoms, "provided")),
            "severity_tier": _get(summary, "severity_tier"),
            "composite_score": _get(summary, "composite_score"),
            "status": _get(summary, "status"),
            "objective_signal_usable": _get(quality, "objective_signal_usable"),
            "gates_failed": _get(quality, "gates_failed") or [],
            "completed_reps": _get(head, "completed_reps"),
            "face_detection_rate": _get(tracking, "face_detection_rate"),
            # None (not False) when the session predates protocol fidelity, so the
            # UI can distinguish "not comparable" from "never assessed".
            "comparable_to_clinical_protocol": _get(
                fidelity, "comparable_to_clinical_protocol"
            ),
            "scoring_source": result.scoring_source,
            "scoring_schema_version": result.scoring_schema_version,
        }

    def list_summaries(self) -> tuple[list[dict], list[dict]]:
        """Return (summaries newest-first, unreadable files).

        A malformed file must not take down the whole list, but it must not vanish
        silently either -- it comes back in the second list so the UI can show it.
        """
        summaries, broken = [], []
        for session_id in self.discover():
            try:
                summaries.append(self.summarize(self.load(session_id)))
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                broken.append({"id": session_id, "error": str(exc)})

        # Sort newest first. Sessions with no resolvable timestamp sort last rather
        # than crashing the comparison.
        summaries.sort(key=lambda s: (s["captured_at"] or ""), reverse=True)
        broken.sort(key=lambda b: b["id"], reverse=True)
        return summaries, broken
