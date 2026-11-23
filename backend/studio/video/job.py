"""The job the API sends the video worker, and the checks the worker makes before it believes one (DESIGN.md §46.6).

One job is one clip. The API decides every file name; the worker only checks that each lies where it should (the start picture in the run's video folder, the clip to be written in
the same folder), as it checks the paths of the images and tracks it writes. A job that fails the checks is refused whole, with a message, and nothing is written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import MIN_FRAMES
from .engine import ConditioningImage, VideoRequest

RUN_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_FRAMES = 3000  # far above any clip a person can ask for (STUDIO_VIDEO_MAX_SECONDS is at most 300 s, 7,200 frames at 24 a second is refused earlier): a sanity ceiling
MAX_SIDE = 8192
MAX_PROMPT = 200_000
CLIP_NAME = "engine-out.mp4"  # what the engine writes; the server turns it into clip.mp4 when it has checked it (service.accept_clip)


@dataclass(frozen=True)
class VideoJob:
    run_id: str
    engine: str
    variant: str
    prompt: str
    width: int
    height: int
    num_frames: int
    fps: int
    seed: int
    out: str  # where the engine writes, relative to the data folder: video/<run>/engine-out.mp4
    images: tuple[tuple[str, int, float], ...] = ()  # (path relative to the data folder, frame index, strength)

    @classmethod
    def from_dict(cls, raw: Any, data_dir: Path) -> "VideoJob":
        """Read and check a job as it came over the wire. Raises ValueError with a sentence that says what is wrong."""
        if not isinstance(raw, dict):
            raise ValueError("the job is not an object")
        run_id = raw.get("run_id")
        if not isinstance(run_id, str) or not RUN_ID.match(run_id):
            raise ValueError("bad run_id")
        engine, variant = raw.get("engine"), raw.get("variant")
        if not isinstance(engine, str) or not engine or not isinstance(variant, str) or not variant:
            raise ValueError("a video job names its engine and variant")
        prompt = raw.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT:
            raise ValueError("a video job needs some words, and not an enormous amount")
        numbers = {}
        for name in ("width", "height", "num_frames", "fps", "seed"):
            value = raw.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be a whole number")
            numbers[name] = value
        if not 8 <= numbers["width"] <= MAX_SIDE or not 8 <= numbers["height"] <= MAX_SIDE or numbers["width"] % 2 or numbers["height"] % 2:
            raise ValueError("the size must be even, and not enormous")
        if not MIN_FRAMES <= numbers["num_frames"] <= MAX_FRAMES or (numbers["num_frames"] - 1) % 8:
            raise ValueError("the number of frames must be 8n + 1")
        if not 1 <= numbers["fps"] <= 120 or numbers["seed"] < 0:
            raise ValueError("the frame rate or the seed is out of range")
        folder = (data_dir / "video" / run_id).resolve()
        out = raw.get("out")
        if not isinstance(out, str) or not out.endswith(".mp4"):
            raise ValueError("a video job needs the name of an .mp4 file to write")
        if (data_dir / out).resolve().parent != folder:
            raise ValueError(f"{out!r} is not in the run's own video folder")
        images = []
        for item in raw.get("images") or []:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("a picture to start from needs a path")
            path = (data_dir / item["path"]).resolve()
            if path.parent != folder or not path.is_file():
                raise ValueError(f"the start picture {item['path']!r} is not a file in the run's own video folder")
            frame, strength = item.get("frame", 0), item.get("strength", 1.0)
            if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0 or isinstance(strength, bool) or not isinstance(strength, (int, float)) or not 0 <= strength <= 1:
                raise ValueError("a picture's frame must be a whole number from 0 and its strength between 0 and 1")
            images.append((item["path"], frame, float(strength)))
        return cls(run_id=run_id, engine=engine, variant=variant, prompt=prompt, out=out, images=tuple(images), **numbers)

    def request(self, data_dir: Path) -> VideoRequest:
        """The call to make on the engine: every path made absolute (the engine is a program in another folder)."""
        return VideoRequest(
            prompt=self.prompt, width=self.width, height=self.height, num_frames=self.num_frames, fps=self.fps, seed=self.seed, variant=self.variant,
            out=str((data_dir / self.out).resolve()),
            images=tuple(ConditioningImage(path=str((data_dir / path).resolve()), frame_index=frame, strength=strength) for path, frame, strength in self.images),
        )
