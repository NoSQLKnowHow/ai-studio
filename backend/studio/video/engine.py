"""The interface every video engine implements, and the records that go with it (DESIGN.md §46.6).

An engine is one model behind a small, fixed surface (Lightricks' LTX-2.5 today; the fake engine of the tests). Nothing outside `video/engines/` and `video/registry.py` names an
engine: the queue, the worker, the database, the API and the page all ask `VideoEngineInfo` what an engine can do and ask the engine to make a clip, exactly as Speech does
(`speech/engine.py`). A test scans the source to keep it so.

Everything in this module is plain Python and imports no model library, so the API process can describe an engine without loading anything.

Four things are here:
  * the descriptive records the page is shown (`VideoLicence`, `Estimate`, `VideoEngineInfo`);
  * the request and result of one call to an engine (`ConditioningImage`, `VideoRequest`, `Clip`);
  * `EngineConfig`, what the server tells the worker about the environment the engine runs in;
  * the `VideoEngine` protocol itself, and `EngineBase`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

# What an engine calls now and then while it works: (stage, step, steps). `stage` is one of `STAGES`; `step` and `steps` are 0 when the engine cannot say how far a stage has got
# (a stage that is only starting). The callback may raise `Canceled` (pipelines.base); an engine lets it through.
ProgressCallback = Callable[[str, int, int], None]
# True means the person pressed Cancel: the engine stops as soon as it can and raises `Canceled`.
CancelCheck = Callable[[], bool]

# The stages of a clip, in the order they happen. They are the real program's own steps (what its log says it is doing, `engines/ltx.py`), and the fake engine reports the same ones,
# so the page has one list of words for them (frontend/src/video.ts).
STAGES = ("start", "text", "denoise", "upscale", "refine", "decode", "write")


@dataclass(frozen=True)
class VideoLicence:
    """What an engine's model is licensed under, for the panel the person must acknowledge before the first clip (DESIGN.md §46.7).

    `summary` is the model card's own words about it and is shown marked as a summary; `url` is the binding text. `revision` is bumped by whoever next re-reads that text: an
    acknowledgement made under an older revision is asked for again. `statement` is the sentence the person confirms."""

    name: str
    summary: str
    url: str
    revision: str
    statement: str
    noncommercial: bool = False
    notice: str = ""  # one sentence written into each clip's file information

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "summary": self.summary, "url": self.url, "revision": self.revision, "statement": self.statement,
                "noncommercial": self.noncommercial, "notice": self.notice}


@dataclass(frozen=True)
class Estimate:
    """How long a clip takes, as a table the page interpolates (DESIGN.md §46.8). `points` are (seconds of video, seconds of work) at `reference_pixels` and 24 frames a second, the
    first being (0, the fixed cost of one run). A bigger or smaller picture scales only the part above that fixed cost, in proportion to its pixels. `kind` is `measured` for a table
    taken on the Spark and `stand-in` for the fake engine's, and `source` says where the numbers are from, so the page can say "about" and never claim more."""

    points: tuple[tuple[float, float], ...]
    reference_pixels: int
    kind: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {"points": [list(point) for point in self.points], "reference_pixels": self.reference_pixels, "kind": self.kind, "source": self.source,
                "overhead_s": self.points[0][1] if self.points else 0.0}


@dataclass(frozen=True)
class SizePreset:
    id: str
    label: str
    width: int
    height: int

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class VideoEngineInfo:
    """Everything the queue, the memory check and the page need to know about an engine without naming it (DESIGN.md §46.6)."""

    id: str  # the engine's name in the registry and in the API: lower case, digits and hyphens
    title: str
    licence: VideoLicence
    model_id: str  # what a run records in `model_id` (the Model filter reads it), with the variant after it: "<model_id> · distilled"
    variants: tuple[str, ...]  # the checkpoints: only one is ever used at a time, and changing it changes the model (it is part of the model key)
    default_variant: str
    memory_gb: float  # the most memory a clip was seen to use (a peak of the whole machine's), for the check before a clip (§9a)
    size_multiple: int  # width and height must be multiples of this (64 for LTX-2.5 as measured: 704 and 1280 work, 720 does not)
    size_min: int
    size_max: int
    size_default: tuple[int, int]
    size_presets: tuple[SizePreset, ...]
    fps_choices: tuple[int, ...]  # the frame rates offered; the first is the default
    estimate: Estimate
    bytes_per_second: float  # what a second of clip takes on disk at the reference size, for the disk check (§46.9)
    image_to_video: bool = True
    sound: bool = True  # the model makes the sound with the picture
    interruptible: bool = True  # Cancel stops a clip that is being made, not only between clips
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "licence": self.licence.as_dict(), "model_id": self.model_id, "variants": list(self.variants),
            "default_variant": self.default_variant, "memory_gb": self.memory_gb, "interruptible": self.interruptible, "image_to_video": self.image_to_video,
            "sound": self.sound, "notes": self.notes,
        }


@dataclass(frozen=True)
class ConditioningImage:
    """A picture the clip starts from (or arrives at): an absolute path to a picture already made the clip's own size, the frame it conditions (0 is the first), and how firmly (1.0)."""

    path: str
    frame_index: int = 0
    strength: float = 1.0


@dataclass(frozen=True)
class VideoRequest:
    """One call to an engine: make one clip (DESIGN.md §46.6). `out` is the absolute path the engine writes its MP4 to; the server has checked that it lies in the run's folder."""

    prompt: str
    width: int
    height: int
    num_frames: int  # always 8n + 1
    fps: int
    seed: int
    variant: str
    out: str
    images: tuple[ConditioningImage, ...] = ()


@dataclass(frozen=True)
class Clip:
    """What an engine made: the file it wrote. The server reads the file's own facts with ffprobe and trusts them over anything the engine says."""

    path: str


@dataclass(frozen=True)
class EngineConfig:
    """What the server tells the worker about the environment an engine runs in (`Settings.video_engine_config`, passed as `--engine-config`)."""

    models_dir: str = ""
    ltx_dir: str = ""  # the LTX-2 clone shared from the host (`<ltx_dir>/.venv/bin/python`), the first way to run the program
    cache_dir: str = ""  # where the program may write its caches (triton, inductor, Hugging Face, torch); under the data folder
    files: dict[str, str] = field(default_factory=dict)  # transformer, text_encoder, video_vae, audio_vae, upsampler: a path relative to `models_dir`, or absolute, or ""
    command: tuple[str, ...] = ()
    python: str = ""
    libs: str = ""
    extra_args: tuple[str, ...] = ()
    quantization: str = "none"
    offload: str = "none"
    timeout_min: int = 0
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    step_delay_ms: int = 0  # the fake engine only: a pause for each step, so that a test can see a clip wait
    hub_mode: str = "auto"

    @classmethod
    def from_dict(cls, raw: Optional[dict[str, Any]], *, step_delay_ms: int = 0, hub_mode: str = "auto") -> "EngineConfig":
        raw = raw or {}
        return cls(
            models_dir=str(raw.get("models_dir") or ""), ltx_dir=str(raw.get("ltx_dir") or ""), cache_dir=str(raw.get("cache_dir") or ""), files={str(k): str(v) for k, v in (raw.get("files") or {}).items()},
            command=tuple(str(x) for x in raw.get("command") or ()), python=str(raw.get("python") or ""), libs=str(raw.get("libs") or ""),
            extra_args=tuple(str(x) for x in raw.get("extra_args") or ()), quantization=str(raw.get("quantization") or "none"),
            offload=str(raw.get("offload") or "none"), timeout_min=int(raw.get("timeout_min") or 0), ffmpeg=str(raw.get("ffmpeg") or "ffmpeg"),
            ffprobe=str(raw.get("ffprobe") or "ffprobe"), step_delay_ms=step_delay_ms, hub_mode=hub_mode,
        )

    def models_path(self) -> Optional[Path]:
        return Path(self.models_dir).expanduser() if self.models_dir else None


class VideoEngine(Protocol):
    """What an engine class provides. `INFO` is a class attribute, so the API process can describe an engine without an instance."""

    INFO: VideoEngineInfo

    @classmethod
    def probe(cls, config: EngineConfig) -> dict[str, Any]:
        """Can this engine run here? Cheap: loads no weights. Raises `PipelineUnavailable` with a reason and a hint (in words a person can act on) when it cannot; returns a dict
        (it may carry `device`) when it can."""

    def load(self) -> dict[str, Any]:
        """Get ready. The real engine has nothing to hold in memory (its program loads the model for every clip, and ends); it checks that it can run. Raises `PipelineError`."""

    def generate(self, request: VideoRequest, progress: ProgressCallback, cancelled: CancelCheck) -> Clip:
        """Make one clip. Raises `PipelineError` (`OutOfMemory` for the usual out-of-memory words), or `Canceled` when `cancelled()` became true."""

    def unload(self) -> None:
        """Let go of anything held. The worker process exits right after, so this is a courtesy."""


class EngineBase:
    """What every engine class shares, so each engine file holds only what is its own: it keeps the config it was made with and answers `name`."""

    INFO: VideoEngineInfo

    def __init__(self, config: EngineConfig, variant: str = ""):
        self.config = config
        self.variant = variant or self.INFO.default_variant

    @property
    def name(self) -> str:
        return self.INFO.id

    def unload(self) -> None:
        return None

    def download_plan(self) -> Any:
        """The real engine downloads nothing (the model files are the person's own), and the fake pretends to only when a test asks (DESIGN.md section 39): None says nothing."""
        return None
