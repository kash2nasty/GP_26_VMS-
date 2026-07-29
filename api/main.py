"""FastAPI app serving saved sessions to the dashboard.

Run it with:
    .venv\\Scripts\\activate
    uvicorn api.main:app --reload --port 8000

Then browse http://127.0.0.1:8000/docs for an interactive view of the endpoints.

DELIBERATELY NOT IMPORTED: session.voms_session
    It looks like the natural place to get the canonical disclaimer from, but it
    imports tracking.face_tracker, which imports mediapipe -- pulling the whole
    camera stack into the web process for one string. The disclaimer already
    travels inside every session JSON, and the screening/exercise disclaimers come
    from scoring/, which is import-clean. Keep it that way.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scoring.exercises import DISCLAIMER as EXERCISE_DISCLAIMER
from scoring.exercises import SAFETY_NOTE
from scoring.severity import DISCLAIMER as SCREENING_DISCLAIMER

from .capture import router as capture_router
from .repository import TRASH_DIRNAME, SessionNotFound, SessionRepository

# The Next.js dev server. Without these origins the browser blocks the requests.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app = FastAPI(
    title="VMS Screening API",
    description=(
        "Read-only access to saved VOMS visual-motion sessions. Screening data "
        "only -- not a clinical determination."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    # Deletion is invoked by a Next.js Server Action, i.e. server to server, so the
    # browser never issues the DELETE itself and it stays off this list.
    allow_methods=["GET"],
    allow_headers=["*"],
)

repository = SessionRepository()

# Browser capture. Importing this module is cheap -- it defers MediaPipe/OpenCV
# until a capture actually starts, so the read-only endpoints above keep their
# fast, camera-stack-free startup.
app.include_router(capture_router)


def disclaimers() -> dict:
    """Disclaimer text shipped with every response that carries results.

    Sent from the API rather than hardcoded in the frontend so the wording cannot
    drift between the two, and so a frontend rewrite cannot quietly drop it.
    """
    return {
        "screening": SCREENING_DISCLAIMER,
        "exercises": EXERCISE_DISCLAIMER,
        "safety_note": SAFETY_NOTE,
    }


@app.get("/health")
def health():
    return {"status": "ok", "sessions_dir": str(repository.sessions_dir)}


@app.get("/sessions")
def list_sessions():
    """Summaries of every saved session, newest first."""
    summaries, unreadable = repository.list_summaries()
    return {
        "sessions": summaries,
        "unreadable": unreadable,
        "disclaimers": disclaimers(),
    }


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Full detail for one session, including recommended exercises."""
    try:
        result = repository.load(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"No session named {session_id!r}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "id": result.session_id,
        "captured_at": result.captured_at,
        "scoring_source": result.scoring_source,
        "scoring_schema_version": result.scoring_schema_version,
        "summary": repository.summarize(result),
        "session": result.session,
        "disclaimers": disclaimers(),
    }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Remove a session from the dashboard.

    The files are moved into sessions/_deleted/ rather than unlinked. A capture
    records something a person physically did and cannot be regenerated, so an
    accidental click should be recoverable by hand.
    """
    try:
        moved = repository.delete(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"No session named {session_id!r}")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete: {exc}")

    return {
        "id": session_id,
        "deleted": moved,
        "moved_to": f"{TRASH_DIRNAME}/",
        "recoverable": True,
    }
