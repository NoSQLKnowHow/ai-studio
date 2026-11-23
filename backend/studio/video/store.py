"""The SQL of clips (DESIGN.md §46.9). Everything here is a fixed statement with bound values. The job manager and the routes go through this class, so the shape of the tables is
known in one place."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional, Sequence

from ..db import Database
from ..serialize import parse_ts


class VideoStore:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------ a finished clip
    def add_clip(self, video: dict[str, Any], segment: dict[str, Any]) -> None:
        """Record a finished clip and its one segment, in one transaction: a clip is never half there."""
        with self.db.tx() as c:
            c.execute(f"INSERT INTO videos ({', '.join(video)}) VALUES ({', '.join('?' for _ in video)})", tuple(video.values()))
            c.execute("DELETE FROM video_segments WHERE run_id=? AND idx=?", (segment["run_id"], segment["idx"]))
            c.execute(f"INSERT INTO video_segments ({', '.join(segment)}) VALUES ({', '.join('?' for _ in segment)})", tuple(segment.values()))

    def get_video(self, video_id: str) -> Optional[sqlite3.Row]:
        return self.db.read_one("SELECT * FROM videos WHERE id=?", (video_id,))

    def video_of_run(self, run_id: str) -> Optional[sqlite3.Row]:
        return self.db.read_one("SELECT * FROM videos WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (run_id,))

    def videos_for_runs(self, run_ids: Sequence[str]) -> dict[str, Optional[sqlite3.Row]]:
        """The clip of each run in `run_ids` (None for a run that has made none yet)."""
        found: dict[str, Optional[sqlite3.Row]] = {run_id: None for run_id in run_ids}
        if not run_ids:
            return found
        marks = ",".join("?" * len(run_ids))
        for row in self.db.read_all(f"SELECT * FROM videos WHERE run_id IN ({marks}) ORDER BY created_at", tuple(run_ids)):
            found[row["run_id"]] = row
        return found

    def segments_for_runs(self, run_ids: Sequence[str]) -> dict[str, list[sqlite3.Row]]:
        found: dict[str, list[sqlite3.Row]] = {run_id: [] for run_id in run_ids}
        if not run_ids:
            return found
        marks = ",".join("?" * len(run_ids))
        for row in self.db.read_all(f"SELECT * FROM video_segments WHERE run_id IN ({marks}) ORDER BY run_id, idx", tuple(run_ids)):
            found[row["run_id"]].append(row)
        return found

    def timings(self, model_prefix: str, limit: int) -> list[dict[str, Any]]:
        """How long the clips that were made here took, newest first, for the page's estimate of how long the next one will (DESIGN.md §46.8). One entry for each clip that was MADE (status
        done) by the model whose id starts with `model_prefix` (another engine's times say nothing about this one's), each with what was asked for (the length, the size and the frame
        rate, which are what the work depends on) and `took`: seconds from the run's start to its end, which is what the person waited, loading the models included. A run with no
        times, or whose end is before its start, is left out. Clips in the bin count: how long they took is still true."""
        found: list[dict[str, Any]] = []
        rows = self.db.read_all(
            "SELECT options_json, started_at, finished_at FROM runs WHERE mode='video' AND status='done' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND substr(model_id, 1, ?) = ? ORDER BY finished_at DESC, seq DESC LIMIT ?", (len(model_prefix), model_prefix, int(limit)))
        for row in rows:
            try:
                options = json.loads(row["options_json"])
                took = (parse_ts(row["finished_at"]) - parse_ts(row["started_at"])).total_seconds()
                entry = {"seconds": float(options["seconds"]), "width": int(options["width"]), "height": int(options["height"]), "fps": int(options["fps"]), "took": round(took, 1)}
            except (KeyError, TypeError, ValueError):
                continue
            if took > 0 and entry["seconds"] > 0:
                found.append(entry)
        return found

    def total_bytes(self) -> int:
        """What the clips of the history and the bin take on disk, in bytes (shown on the tab: clips are large)."""
        row = self.db.read_one("SELECT COALESCE(SUM(bytes), 0) AS n FROM videos")
        return int(row["n"]) if row is not None else 0
