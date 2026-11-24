"""The Video tab's routes (DESIGN.md §46.10): the clip and its poster and thumbnail, and the licence. Making a clip is `POST /api/runs` with `mode: "video"`, like music and vector.

A clip is served as a `FileResponse`, which answers `Range` (206 with `Content-Range`, 416 for a range that cannot be met) and says `Accept-Ranges: bytes`, so that a player can seek and
start playing before the file has all arrived (§26.3 does the same for a track). A clip's file never changes, so it is cached as immutable.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from .. import naming
from ..serialize import parse_ts
from ..storage import StorageError, check_id
from .service import VideoRefused

IMMUTABLE = "private, max-age=31536000, immutable"


class LicenceBody(BaseModel):
    """The acknowledgement (DESIGN.md §46.7): `accept` must be true, and `revision` is the one of the licence the person saw."""

    model_config = ConfigDict(extra="forbid", strict=True)
    accept: bool
    revision: str


def _error(status: int, detail: str, code: str, hint: Optional[str] = None) -> JSONResponse:
    content: dict[str, Any] = {"detail": detail, "code": code}
    if hint:
        content["hint"] = hint
    return JSONResponse(status_code=status, content=content)


def add_routes(app: FastAPI) -> None:
    """Add the video routes to the app. They take the job manager, the database and the storage from `app.state`, as the other routes do."""

    def found(request: Request, video_id: str, column: str) -> Any:
        """(the clip's row, the file's path) for one of a clip's three files (`column` is `path`, `poster_path` or `thumb_path`), or an error response. A clip is not served when its run is
        in the bin (Restore it first), and a file that is gone, or was never made, is a 404 like any other."""
        try:
            check_id(video_id)
        except StorageError:
            return _error(404, "Clip not found.", "not_found")
        jobs = request.app.state.jobs
        video = jobs.video.store.get_video(video_id)
        if video is None or not video[column]:
            return _error(404, "Clip not found.", "not_found")
        run = jobs.db.get_run(video["run_id"])
        if run is None or run["deleted_at"] is not None:
            return _error(404, "This clip is in the bin. Restore it to watch it.", "not_found")
        try:
            path = request.app.state.storage.abs(video[column])
        except StorageError:
            return _error(404, "Clip not found.", "not_found")
        if not path.is_file():
            return _error(404, "The clip's file is no longer on the disk.", "file_missing")
        return video, run, path

    @app.get("/api/videos/{video_id}")
    async def get_video(video_id: str, request: Request, download: bool = False) -> Any:
        """The MP4, with `Range`. `?download=1` makes it an attachment named like the other downloads (`video_<words>_<N>s_s<seed>_<date>.mp4`)."""
        answer = found(request, video_id, "path")
        if isinstance(answer, JSONResponse):
            return answer
        video, run, path = answer
        headers = {"Cache-Control": IMMUTABLE}
        if download:
            name = naming.video_filename(prompt=run["prompt"], seconds=video["seconds"], seed=video["seed"], created_at=parse_ts(run["created_at"]))
            headers["Content-Disposition"] = naming.content_disposition(name, default="video.mp4")
        return FileResponse(path, media_type="video/mp4", headers=headers)

    @app.get("/api/videos/{video_id}/poster")
    async def get_poster(video_id: str, request: Request) -> Any:
        """The clip's first frame, full size: what the player shows before it plays."""
        answer = found(request, video_id, "poster_path")
        if isinstance(answer, JSONResponse):
            return answer
        return FileResponse(answer[2], media_type="image/jpeg", headers={"Cache-Control": IMMUTABLE})

    @app.get("/api/videos/{video_id}/thumb")
    async def get_video_thumb(video_id: str, request: Request) -> Any:
        """The clip's thumbnail, for the queue and the history."""
        answer = found(request, video_id, "thumb_path")
        if isinstance(answer, JSONResponse):
            return answer
        return FileResponse(answer[2], media_type="image/webp", headers={"Cache-Control": IMMUTABLE})

    @app.post("/api/video/check", status_code=202)
    async def check_video_again(request: Request) -> Any:
        """Run the video engine's start-up check again (DESIGN.md §46.8): for a person who has put a folder, a permission or a program right and must not have to restart the container.
        Answers at once (`202`, `started`); the outcome arrives as `capabilities.updated` and in `capabilities.video`. Rate-limited (`429 video_check_too_soon`), and refused while a clip
        is being made (`409 video_busy`); a check that is under way is not started twice (`started: false`)."""
        jobs = request.app.state.jobs
        try:
            return jobs.recheck_video()
        except VideoRefused as exc:
            return _error(exc.status, exc.message, exc.code, exc.hint)

    @app.get("/api/video/licence")
    async def get_licence(request: Request) -> Any:
        return request.app.state.jobs.video.licence()

    @app.post("/api/video/licence")
    async def accept_licence(body: LicenceBody, request: Request) -> Any:
        """Acknowledge the licence: `accept` must be true and `revision` the current one. There is no other way to do it (no setting, no default): an acknowledgement nobody read
        would be worth nothing (DESIGN.md §46.7)."""
        jobs = request.app.state.jobs
        if not body.accept:
            return _error(422, "To acknowledge the licence, accept must be true.", "licence_not_accepted")
        try:
            licence = await asyncio.to_thread(jobs.video.accept_licence, body.revision)
        except VideoRefused as exc:
            return _error(exc.status, exc.message, exc.code, exc.hint)
        jobs.publish_capabilities()  # every open page learns that the form can be used
        return licence

    @app.delete("/api/video/licence")
    async def withdraw_licence(request: Request) -> Any:
        """Withdraw the acknowledgement: the tab is disabled again. Clips already made are untouched."""
        jobs = request.app.state.jobs
        licence = await asyncio.to_thread(jobs.video.withdraw_licence)
        jobs.publish_capabilities()
        return licence
