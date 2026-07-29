"""Single code path from a session dict to a scored, recommendation-bearing dict.

Both score_session.py (standalone re-scoring) and run_session.py (--score at the
end of a live capture) call enrich_session() so the two routes cannot drift apart.
"""
from __future__ import annotations

from . import exercises, severity


def enrich_session(session: dict) -> dict:
    """Return a copy of `session` with screening and exercise blocks appended.

    The original session data is left untouched, so re-scoring an old file with
    updated logic never destroys the underlying capture.
    """
    summary = severity.summarize(session)
    recommendations = exercises.recommend(
        summary["severity_tier"], summary["status"]
    )

    enriched = dict(session)
    enriched["screening_summary"] = summary
    enriched["recommended_exercises"] = recommendations
    return enriched


def describe(enriched: dict) -> str:
    """One-line human-readable summary for terminal output."""
    summary = enriched.get("screening_summary") or {}
    tier = summary.get("severity_tier")
    composite = summary.get("composite_score")
    status = summary.get("status")
    count = len((enriched.get("recommended_exercises") or {}).get("exercises", []))

    if tier is None:
        return f"screening: no tier assigned (status: {status})"
    return (
        f"screening tier: {tier} (composite {composite}, status: {status}) "
        f"- {count} general exercise suggestions"
    )
