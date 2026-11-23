"""What the API does with clips (DESIGN.md §46): the licence the person must acknowledge, the checks before a clip is queued, the start picture, taking a finished file in, and the
description of all of it that the page reads (`capabilities.video`).

The job manager owns the queue and the worker; this class owns what a clip means. It is synchronous where it touches files (the job manager calls it in a thread), as `SpeechService`
is.
"""

from __future__ import annotations

import json
import secrets
import shutil
from pathlib import Path
from typing import Any, Optional

from ..config import Settings
from ..db import Database
from ..serialize import utcnow
from ..storage import Storage
from . import OFFERED_QUALITIES, QUALITIES, registry
from .engine import VideoEngineInfo
from .job import CLIP_NAME
from .media import MediaError, Tools, check_output, find_tools, finish_clip, make_poster, make_thumbnail, prepare_start_picture, probe_clip
from .store import VideoStore

LICENCE_KEY = "video_licence"  # the one row of `meta` that holds the acknowledgement (DESIGN.md §46.7): there is no setting, default or header that makes one
DISK_MARGIN = 1.5  # a clip's estimated size is multiplied by this before it is compared with the free space (DESIGN.md §46.9)
GIB = 1024**3


class VideoRefused(Exception):
    """A request about clips that cannot be done just now (DESIGN.md §46.10). `status` and `code` are the response's; `hint` says what to do about it."""

    def __init__(self, status: int, code: str, message: str, hint: Optional[str] = None):
        super().__init__(message)
        self.status, self.code, self.message, self.hint = status, code, message, hint


def size_text(count: float) -> str:
    """A number of bytes as a person reads it: `2.0 GB`, `340 MB`."""
    if count >= GIB / 2:
        return f"{count / GIB:.1f} GB"
    return f"{max(1, round(count / 1024 / 1024))} MB"


class VideoService:
    def __init__(self, settings: Settings, db: Database, storage: Storage):
        self.settings = settings
        self.db = db
        self.storage = storage
        self.store = VideoStore(db)
        self._tools: Optional[Tools] = None

    # ------------------------------------------------------------------ the engine, and what is on the machine
    def engine_id(self) -> str:
        return registry.primary(self.settings.pipeline)

    def info(self) -> VideoEngineInfo:
        return registry.info(self.engine_id())

    # How many of the newest finished clips the page is told the times of: enough for a median of each length, few enough to be a small answer.
    TIMINGS_LIMIT = 40

    def timings(self) -> list[dict[str, Any]]:
        """The times of the clips this engine's model made here, newest first (DESIGN.md §46.8): what the page estimates the next clip's time from. Only the current engine's: the
        run's `model_id` starts with the engine's own."""
        return self.store.timings(f"{self.info().model_id} · ", self.TIMINGS_LIMIT)

    def tools(self) -> Tools:
        """Whether ffmpeg and ffprobe can be run here: looked for once and the answer kept, so asking costs nothing (a program that is installed later needs a restart, as for Speech)."""
        if self._tools is None:
            self._tools = find_tools(self.settings.video_ffmpeg, self.settings.video_ffprobe)
        return self._tools

    # ------------------------------------------------------------------ the licence (DESIGN.md §46.7)
    def licence(self) -> dict[str, Any]:
        """The licence panel's facts: what the person must acknowledge, and whether (and when) they did. An acknowledgement made under another licence or an older revision of it does
        not count: the person is asked again."""
        licence = self.info().licence
        row = self.db.read_one("SELECT value FROM meta WHERE key=?", (LICENCE_KEY,))
        given: dict[str, Any] = {}
        if row is not None:
            try:
                given = json.loads(row["value"])
            except ValueError:
                given = {}
        accepted = given.get("name") == licence.name and given.get("revision") == licence.revision
        return {**licence.as_dict(), "accepted": accepted, "accepted_at": given.get("accepted_at") if accepted else None,
                "outdated": bool(given) and not accepted}  # `outdated`: they acknowledged an earlier revision, so the panel says why it is asking again

    def accept_licence(self, revision: str) -> dict[str, Any]:
        """Record the acknowledgement, with the revision the person saw. Raises `VideoRefused` (422) for a revision that is not the current one: they saw words that have changed."""
        licence = self.info().licence
        if revision != licence.revision:
            raise VideoRefused(422, "licence_revision", "The licence has changed since this page was loaded. Reload the page and read it again.")
        value = json.dumps({"name": licence.name, "revision": licence.revision, "accepted_at": utcnow(), "statement": licence.statement})
        with self.db.tx() as c:
            c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (LICENCE_KEY, value))
        return self.licence()

    def withdraw_licence(self) -> dict[str, Any]:
        """Take the acknowledgement back: the tab is disabled again. Clips already made are untouched."""
        with self.db.tx() as c:
            c.execute("DELETE FROM meta WHERE key=?", (LICENCE_KEY,))
        return self.licence()

    # ------------------------------------------------------------------ before a clip is queued
    def check_ready(self, probe: dict[str, Any]) -> None:
        """Refuse a clip that cannot be made at all, in the order a person would put it right: the licence (409 `licence_not_accepted`), then whether the video program can run here
        (409 `video_unavailable`, with the start-up check's own reason and hint). `probe` is the job manager's record of that check."""
        if not self.licence()["accepted"]:
            raise VideoRefused(409, "licence_not_accepted", "You need to acknowledge the video model's licence before a clip can be made.",
                               "Open the Video tab, read the licence and tick the box.")
        state = probe.get("state")
        if state == "done":
            return
        if state in (None, "pending", "running", "checking"):
            raise VideoRefused(409, "video_unavailable", "The video program is still being checked.", "Try again in a moment.")
        error = probe.get("error") or {}
        raise VideoRefused(409, "video_unavailable", error.get("message") or "Video cannot run on this machine.", error.get("hint"))

    def estimated_bytes(self, width: int, height: int, seconds: float) -> int:
        """About how big a clip will be: what a second takes at the reference size (measured: 1.6 MB for 5 s at 1280x704), in proportion to the picture's pixels, with a floor."""
        info = self.info()
        pixels = max(1, width * height) / max(1, info.estimate.reference_pixels)
        return max(1024 * 1024, int(info.bytes_per_second * seconds * pixels))

    def check_disk(self, width: int, height: int, seconds: float) -> None:
        """Refuse a clip that would not fit (507 `storage_full`, with the figures, DESIGN.md §46.9): the free space on the data volume must cover the clip's estimated size, with a
        margin, and still leave STUDIO_VIDEO_MIN_FREE_DISK_GB."""
        estimate = self.estimated_bytes(width, height, seconds) * DISK_MARGIN
        try:
            free = shutil.disk_usage(self.storage.root).free
        except OSError:
            return  # not knowing is not a reason to refuse
        floor = self.settings.video_min_free_disk_gb * GIB
        if free < estimate + floor:
            raise VideoRefused(507, "storage_full", f"This clip needs about {size_text(estimate)} of disk, and {size_text(free)} is free"
                                                    + (f" (and {self.settings.video_min_free_disk_gb:g} GB must stay free)." if floor else "."),
                               "Delete clips or other runs you no longer need, or free space on the disk the data folder is on.")

    # ------------------------------------------------------------------ the start picture and the clip
    def prepare_start(self, row: Any) -> Optional[str]:
        """Make the clip's start picture (DESIGN.md §46.11): the person's picture cut to the clip's shape from the middle and made RGB, saved in the run's video folder. Returns its path
        relative to the data folder, or None for a clip with no start picture. Raises ValueError with a sentence when the picture cannot be used. In a thread."""
        options = json.loads(row["options_json"])
        if not options.get("start"):
            return None
        inputs = self.db.inputs_for_runs([row["id"]])[row["id"]]
        if not inputs:
            raise ValueError("The start picture is no longer there. Add it again and make the clip again.")
        target = self.storage.video_dir(row["id"]) / "start.png"
        try:
            prepare_start_picture(self.storage.abs(inputs[0]["path"]), target, options["width"], options["height"])
        except (OSError, ValueError) as exc:
            raise ValueError(f"The start picture could not be read ({getattr(exc, 'strerror', None) or exc}). Add it again.") from exc
        return self.storage.rel(target)

    def accept_clip(self, row: Any, event: dict[str, Any]) -> dict[str, Any]:
        """Take in the file the worker reports (DESIGN.md §46.9), in a thread: check that it lies in the run's own folder, read its own facts with ffprobe and trust them over the
        engine's word, check that it is the clip that was asked for, make it the file the studio keeps (playable everywhere, the sound taken out if the person asked for none, the
        index at the front), make its poster and thumbnail, and record it. Raises `MediaError` (in words) for a file that is not a clip or that cannot be finished, and
        StorageError for a path that is outside the folder. A clip with no sound where sound was asked for is finished, with a note, and is not a failure (§46.8)."""
        run_id = row["id"]
        options = json.loads(row["options_json"])
        raw = self.storage.accept_worker_video(str(event["path"]), run_id)
        ffmpeg, ffprobe = self.settings.video_ffmpeg, self.settings.video_ffprobe
        facts = probe_clip(ffprobe, raw)
        wrong = check_output(facts, width=options["width"], height=options["height"], frames=options["frames"], fps=options["fps"])
        if wrong:
            raise MediaError(wrong)
        folder = self.storage.video_dir(run_id)
        final = folder / "clip.mp4"
        info = self.info()
        made = finish_clip(ffmpeg, ffprobe, raw, final, facts=facts, keep_sound=bool(options.get("keep_sound", True)), comment=info.licence.notice, title=" ".join(row["prompt"].split())[:80])
        raw.unlink(missing_ok=True)
        (folder / "start.png").unlink(missing_ok=True)  # the person's own picture is kept with the run (its inputs); this was the clip's copy of it, made its size
        poster = folder / "poster.jpg"
        make_poster(ffmpeg, final, poster)
        thumb = make_thumbnail_for(self.storage, run_id, poster)
        note = None
        if options.get("keep_sound", True) and not made.has_audio:
            note = "This clip has no sound track."
        now = utcnow()
        video_id = secrets.token_hex(16)
        inputs = self.db.inputs_for_runs([run_id])[run_id]
        self.store.add_clip({
            "id": video_id, "run_id": run_id, "seed": int(event.get("seed", row["seed"])), "width": made.width, "height": made.height, "fps": round(made.fps, 3), "frames": made.frames,
            "seconds": round(made.seconds, 3), "has_audio": int(made.has_audio), "audio_channels": made.audio_channels, "audio_rate": made.audio_rate, "bytes": made.bytes,
            "path": self.storage.rel(final), "poster_path": self.storage.rel(poster), "thumb_path": self.storage.rel(thumb), "created_at": now, "note": note,
        }, {
            "run_id": run_id, "idx": 0, "status": "done", "seed": int(row["seed"]), "frames": made.frames, "seconds": round(made.seconds, 3), "prompt": row["effective_prompt"],
            "start_image": inputs[0]["path"] if inputs else None, "path": self.storage.rel(final), "started_at": row["started_at"], "finished_at": now, "error": None,
        })
        return {"video_id": video_id, "work_seconds": event.get("work_seconds")}

    # ------------------------------------------------------------------ what the page reads
    def status(self, probe: dict[str, Any], memory: Optional[str]) -> dict[str, Any]:
        """`capabilities.video` (DESIGN.md §46.10). `probe` is the job manager's record of the start-up check (`pending`, `running`, `done` or `failed` with the engine's own reason
        and hint); `memory` is why a clip could not start for want of free memory right now, or None. The tab is `available` when a clip can be made on this machine at all; whether the
        person has acknowledged the licence is its own answer (`licence.accepted`), because the page shows the licence panel and not the reason."""
        info = self.info()
        error = probe.get("error") or {}
        state = {"done": "ready", "failed": "unavailable"}.get(str(probe.get("state")), "checking")
        tools = self.tools()
        available = state == "ready" and tools.ok
        reason: Optional[str] = None
        hint: Optional[str] = None
        if state == "checking":
            reason = "The video program is still being checked."
        elif state == "unavailable":
            reason, hint = error.get("message") or "Video cannot run on this machine.", error.get("hint")
        elif not tools.ok:
            reason, hint = tools.reason(), "Install ffmpeg in the image."
        qualities = [{"id": quality, "label": quality.capitalize(), "available": quality in OFFERED_QUALITIES and QUALITIES[quality] in info.variants,
                      "reason": None if quality in OFFERED_QUALITIES else "Not tried on this machine yet."} for quality in QUALITIES]
        return {
            "available": available, "state": state, "reason": reason, "hint": hint, "engine": info.as_dict(), "licence": self.licence(), "qualities": qualities,
            "chaining": {"available": False, "reason": "A clip is made in one pass; joining several is not built yet."},
            "tools": tools.as_dict(), "memory": {"ok": memory is None, "message": memory}, "clips_bytes": self.store.total_bytes(),
        }


def make_thumbnail_for(storage: Storage, run_id: str, poster: Path) -> Path:
    """The clip's thumbnail beside the run's other thumbnails: <data>/thumbs/<run>/video.webp."""
    thumb = storage.thumbs / run_id / "video.webp"
    make_thumbnail(poster, thumb)
    return thumb


__all__ = ["CLIP_NAME", "VideoRefused", "VideoService", "size_text"]
