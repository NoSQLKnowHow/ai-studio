"""The Video tab's tables (schema 14, DESIGN.md §46.9).

A clip is a row of `runs` with mode 'video' (so the queue, the bin, projects, Cancel, tags, notes, search and the history work on it unchanged) and these tables hang off it. (There is no table
of speeds: how long a clip takes is worked out from the runs themselves, `VideoStore.timings`, which keeps no second copy of what the history already says.)
  videos          the clip a finished run made: one row for each run, with what its file says of itself
  video_segments  the pieces a clip is made of: one for a clip made in one pass (which is every clip today); the table is the same for a clip joined from several
The run's own mode is allowed by the CHECK on `runs.mode` in db.py, which schema 14 widens (the table is rebuilt, as schemas 3, 7 and 10 did).
"""

from __future__ import annotations

VIDEO_SCHEMA = """
-- The clip a finished video run made, one for each run (a clip takes minutes: there is no "4 pictures" here). The three paths are relative to the data folder:
-- <data>/video/<run>/clip.mp4, <data>/video/<run>/poster.jpg and <data>/thumbs/<run>/video.webp. Every number is what ffprobe found in the file, not what the engine said.
-- `note` is anything the checks found that the person should know (no sound track where one was asked for).
CREATE TABLE IF NOT EXISTS videos (
    id             TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    seed           INTEGER NOT NULL,
    width          INTEGER NOT NULL,
    height         INTEGER NOT NULL,
    fps            REAL NOT NULL,
    frames         INTEGER NOT NULL,
    seconds        REAL NOT NULL,
    has_audio      INTEGER NOT NULL,
    audio_channels INTEGER,
    audio_rate     INTEGER,
    bytes          INTEGER NOT NULL,
    path           TEXT NOT NULL,
    poster_path    TEXT NOT NULL,
    thumb_path     TEXT,
    created_at     TEXT NOT NULL,
    note           TEXT
);
CREATE INDEX IF NOT EXISTS idx_videos_run ON videos(run_id);
-- The pieces of a clip (DESIGN.md §46.5). A clip made in one pass has one row; a clip joined from several has several, and the table is the same, so the schema does not
-- wait for how long a pass turns out to be. `start_image` is the path of the picture the segment began from (the person's start picture, or the last frame of the one before).
CREATE TABLE IF NOT EXISTS video_segments (
    run_id      TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('queued','running','done','failed','canceled')),
    seed        INTEGER NOT NULL,
    frames      INTEGER NOT NULL,
    seconds     REAL NOT NULL,
    prompt      TEXT NOT NULL,
    start_image TEXT,
    path        TEXT,
    started_at  TEXT,
    finished_at TEXT,
    error       TEXT,
    PRIMARY KEY (run_id, idx)
);
"""
