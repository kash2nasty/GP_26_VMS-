"""Read-only HTTP API over the saved session JSON files.

Deliberately isolated from the capture path: nothing here imports camera or
MediaPipe code. It reads what run_session.py already wrote, and borrows
scoring.pipeline to score any capture that was saved without a scored counterpart.
"""
