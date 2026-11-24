"""The real video engine: Lightricks' LTX-2.5, run as a program of its own (DESIGN.md §46.6 option 2).

**How it works.** The LTX program (`python -m ltx_pipelines.distilled`, from github.com/Lightricks/LTX-2) needs Python 3.12, its own PyTorch (2.13 with CUDA 13.2, where the image's
NVIDIA build is 2.9 with CUDA 13.0) and a pile of libraries that must not meet NVIDIA's pinned ones, so it lives in an environment of its own and this engine starts it as a child
process for each clip. There are two ways to have that environment, and the engine runs either the same way:

1. **The person's own clone, shared from the host** (`STUDIO_VIDEO_LTX_DIR`, the way to start with, no rebuild of the image): the LTX-2 folder in which the program was first run
   on the Spark, with its `.venv` and its `packages/`, bind-mounted read-only at the SAME path inside the container (the editable installs under `packages/` record absolute paths, and
   the venv's `python` is a link to `/usr/bin/python3`, which the container has too: Ubuntu 24.04, Python 3.12.3). It is run directly, as `<it>/.venv/bin/python -m
   ltx_pipelines.distilled`, never through `uv run` (which would try to sync the project and write to a tree that is read-only).
2. **An environment the image builds** (`VIDEO_LTX=1`, the commit pinned in the Dockerfile): the same program made by `uv sync` into `/opt/video-libs/ltx`.

Either way it is a one-shot program: it loads every model (about 45 seconds), makes the clip, writes an MP4 with its sound, and ends. So there is
nothing to keep in memory between clips, `load()` only checks that a clip can be made, and Cancel is the end of the process (its whole process group, so no helper is left behind).

**What is measured, on the Spark, with the distilled model** (2026-11-19 and 20): a clip of 1280x704 at 24 frames a second takes 154 s for 5 s of video, 293 s for 10 s, 604 s for 20 s
and 1,036 s for 30 s; the machine's memory in use peaks at 47,273 / 49,126 / 52,746 / 56,973 MiB for those; image to video costs the same as text to video; sizes must be multiples
of 64 (they are the size of the finished video); the file is H.264 with stereo AAC at 48 kHz, about 1.6 MB for 5 s, its sound a little shorter than its picture.

**Then natten became importable** (2026-11-23, the same Spark): the earlier times above were made on the slow fallback of the program's DiffVAE, because natten could not be imported. With it, the same
clips take about 30 s LONGER, a fixed part: a tiny clip (512x320, 9 frames) 75.1 s and 73.8 s where it had taken 45.0 s and 46.3 s, and 5 s at 1280x704 186.4 s where it had taken 154.5 s; the
machine's memory peak is unchanged (47,410 MiB). Whether natten is faster for a 30 s clip is not known. So the table here is the earlier setup's and says so (`source`), and the page
estimates from the clips made on THIS installation whenever there are some of about the length asked for (`VideoStore.timings`; `estimateFromHistory` in the page's video.ts).

**What the program says while it works** is on its standard error, and is the only progress there is: its log lines name each stage, and its progress bars (tqdm) end their updates
with a carriage return and not a newline, so `LtxProgress` cuts what it reads at both. The lines it knows are in the tests, copied from a real run.

Nothing here imports PyTorch or any model library: the program does, in another process.
"""

from __future__ import annotations

import codecs
import json
import logging
import os
import pwd
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from ...pipelines.base import Canceled, OutOfMemory, PipelineError, PipelineUnavailable
from .. import media
from ..engine import (
    CancelCheck, Clip, EngineBase, EngineConfig, Estimate, ProgressCallback, SizePreset, VideoEngineInfo, VideoLicence, VideoRequest,
)
from .ltx_files import FOLDERS, KINDS, LABELS, ModelFiles, find_files

log = logging.getLogger("studio.video.ltx")

MODULE = "ltx_pipelines.distilled"  # the program, run with `python -m`

# The environment in which the program was seen to work, on the Spark, 2026-11-19 and 20 (MEASURED, reported by the person who ran it; nothing here has been run by the studio's own
# tests, which have no GPU). It is what the build check prints, what the capability check compares what it finds with (a note, never a refusal: a newer one may work too), and what
# the Dockerfile pins (the commit). The studio image's own PyTorch is NOT this one, which is why the program has an environment of its own.
MEASURED_ON_THE_SPARK = {
    "date": "2026-11-19/20",
    "ltx_commit": "daa6b16fc7f0f1628f2c9e36a303e3312b333cc6",  # github.com/Lightricks/LTX-2; ltx-core, ltx-pipelines and ltx-trainer are all 1.6.2, installed editable from packages/
    "python": "3.12.3",  # the host's, and the container's (Ubuntu 24.04), at /usr/bin/python3
    "cuda": "13.2",
    "packages": {
        "torch": "2.13.0+cu132", "torchaudio": "2.11.1+cu132", "torchvision": "0.28.0+cu132", "torchcodec": "0.17.0+cu132", "natten": "0.21.7+torch2130cu132",
        "transformers": "5.14.1", "triton": "3.7.1", "safetensors": "0.8.0", "av": "19.0.2", "ltx-core": "1.6.2", "ltx-pipelines": "1.6.2", "ltx-trainer": "1.6.2",
    },
}
# What the studio image has (NVIDIA's NGC PyTorch release 25.10): not usable by the program, which needs the wheels above (they carry their own CUDA user-space libraries; the
# driver is the host's, shared through the nvidia runtime).
IMAGE_TORCH = "2.9.0a0+145a3a7bda.nv25.10 (CUDA 13.0)"

REBUILD_HINT = "On the host, run uv sync in the LTX-2 folder (the way the environment was first made), then press Check again. For the environment built into the image: rebuild it with VIDEO_LTX=1."
NOT_SET_UP_HINT = ("Set STUDIO_VIDEO_LTX_DIR in .env to your LTX-2 folder on the host, and STUDIO_VIDEO_MODELS_DIR to the folder of model files, then docker compose up -d "
                   "(README, Video). Or build the program into the image with VIDEO_LTX=1, or name it with STUDIO_VIDEO_COMMAND.")
LICENCE_URL = "https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x"
# Bumped by whoever next reads the licence's binding text (DESIGN.md §46.7). The summary below is the model card's own words; the binding text has not been read by whoever wrote this.
LICENCE_REVISION = "1"

INFO = VideoEngineInfo(
    id="ltx", title="LTX-2.5", model_id="Lightricks/LTX-2.5", variants=("distilled",), default_variant="distilled",
    licence=VideoLicence(
        name="LTX-2.x Community License Agreement",
        summary=("Commercial and production use is free for an entity with less than $10 million of annual revenue; over that a paid agreement is needed; "
                 "passing on fine-tunes may need a paid licence. (The code is Apache-2.0; the weights are under this licence.)"),
        url=LICENCE_URL, revision=LICENCE_REVISION,
        statement="I have read the LTX-2.x Community License Agreement and my use of the studio's video clips is covered by it.",
        notice="Made with LTX-2.5 by Lightricks, under the LTX-2.x Community License Agreement."),
    memory_gb=56.0,  # the machine's memory in use peaked at 56,973 MiB (55.6 GiB) for a 30 s clip, of which about 3 GB is what an idle machine uses
    size_multiple=64, size_min=256, size_max=1920, size_default=(1280, 704),
    size_presets=(SizePreset("landscape", "1280×704", 1280, 704), SizePreset("quick", "1024×576 (quick look)", 1024, 576),
                  SizePreset("portrait", "704×1280", 704, 1280), SizePreset("tiny", "512×320 (a test)", 512, 320)),
    fps_choices=(24,),
    estimate=Estimate(points=((0.0, 45.0), (5.0, 154.0), (10.0, 293.0), (20.0, 604.0), (30.0, 1036.0)), reference_pixels=1280 * 704, kind="measured",
                      source="measured on one Spark setup, 2026-11-19/20 (no natten)"),
    bytes_per_second=320_000.0,  # 1.6 MB for 5 s at 1280x704
    notes="One program run for each clip: it loads its models (about 45 s), makes the clip and ends.",
)


# ------------------------------------------------------------------ the command line
def ltx_python(ltx_dir: str) -> str:
    """The interpreter of the LTX-2 clone shared from the host: its own virtual environment, which was made there by `uv sync` and is run directly (never `uv run`)."""
    return str(Path(ltx_dir).expanduser() / ".venv" / "bin" / "python")


def interpreter_command(config: EngineConfig) -> tuple[str, ...]:
    """The command that starts the program, from the settings: `STUDIO_VIDEO_COMMAND` as it is; else `<STUDIO_VIDEO_PYTHON> -m ltx_pipelines.distilled`; else the person's clone,
    `<STUDIO_VIDEO_LTX_DIR>/.venv/bin/python -m ltx_pipelines.distilled`; else the environment the image builds, `<STUDIO_VIDEO_LIBS>/ltx/bin/python -m ltx_pipelines.distilled`. Empty
    when nothing says how. (The order is from the most to the least specific: a command written out beats a folder, and a folder somebody named beats what the image has.)"""
    if config.command:
        return tuple(config.command)
    if config.python:
        return (config.python, "-m", MODULE)
    if config.ltx_dir:
        return (ltx_python(config.ltx_dir), "-m", MODULE)
    if config.libs:
        return (str(Path(config.libs) / "ltx" / "bin" / "python"), "-m", MODULE)
    return ()


def build_command(command: Sequence[str], config: EngineConfig, files: ModelFiles, request: VideoRequest) -> list[str]:
    """The exact command line for one clip (DESIGN.md §46.6). The five files and the clip's words, size, length, rate and seed are always given; a picture to start from is
    `--image <path> <frame> <strength>` (frame 0 is the first); `--quantization` and `--offload cpu` only when the settings ask for them; `STUDIO_VIDEO_EXTRA_ARGS` last.

    A prompt that begins with a dash is given as `--prompt=<text>` so that the program's own argument reader cannot take it for an option; every other is two words, as the program was
    run by hand on the Spark."""
    argv = [*command,
            "--transformer-path", str(files.transformer), "--text-encoder-path", str(files.text_encoder), "--video-vae-path", str(files.video_vae),
            "--audio-vae-path", str(files.audio_vae), "--spatial-upsampler-path", str(files.upsampler)]
    argv += [f"--prompt={request.prompt}"] if request.prompt.startswith("-") else ["--prompt", request.prompt]
    argv += ["--output-path", request.out, "--seed", str(request.seed), "--frame-rate", f"{float(request.fps)}", "--width", str(request.width), "--height", str(request.height),
             "--num-frames", str(request.num_frames)]
    for image in request.images:
        argv += ["--image", image.path, str(image.frame_index), f"{image.strength:g}"]
    if config.quantization != "none":
        argv += ["--quantization", config.quantization]
    if config.offload == "cpu":
        argv += ["--offload", "cpu"]
    argv += list(config.extra_args)
    return argv


# What the program is told to write, and where, under the cache folder (the data folder's `video-cache`): the clone it runs from may be read-only, and the person's home in the
# container is not a place anything is kept, so every cache the program or its libraries would write goes somewhere the studio's user can always write.
CACHE_FOLDERS = {"TRITON_CACHE_DIR": "triton", "TORCHINDUCTOR_CACHE_DIR": "torchinductor", "TORCH_HOME": "torch", "TORCH_EXTENSIONS_DIR": "torch-extensions",
                 "CUDA_CACHE_PATH": "cuda", "HF_HOME": "huggingface", "XDG_CACHE_HOME": "xdg"}
# These two are the person's own when they are set to a place that can be written (the image sets HF_HOME to the shared model cache, which holds what has been downloaded already);
# the others are always ours, so that two programs never share a compiled-kernel cache.
THE_PERSONS_IF_WRITABLE = ("HF_HOME", "XDG_CACHE_HOME")


def _writable(path: str) -> bool:
    """Whether the studio's user can write in a folder that exists (or could make it, when its parent exists)."""
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe.is_dir() and os.access(probe, os.W_OK | os.X_OK)


def child_environment(base: Optional[dict[str, str]] = None, cache_dir: str = "") -> dict[str, str]:
    """The environment the program runs in (DESIGN.md §46.6). It is the worker's, made clean: the program's interpreter is another Python with its own PyTorch (2.13, CUDA 13.2), and
    the image's NVIDIA one (2.9, CUDA 13.0) must not leak into it by any road.

    * `PYTHONPATH`, `PYTHONHOME` and `VIRTUAL_ENV` are removed (the studio's own libraries must not be read by another version of Python), and so is **all** of `LD_LIBRARY_PATH` (the
      NGC image fills it with the folders of its own PyTorch and CUDA, which the program's PyTorch must not find first: its wheels carry their own CUDA libraries, and the driver is
      found where the nvidia runtime puts it). `HOME`, `PATH` and `CUDA_VISIBLE_DEVICES` are kept, with everything else the worker had.
    * Python writes no bytecode (the clone is read-only) and its output is not buffered, so that the progress lines arrive as they are written.
    * With a `cache_dir`, the caches the program and its libraries would write (Triton's, PyTorch Inductor's, PyTorch's, Hugging Face's, the CUDA JIT's, `XDG_CACHE_HOME`) are
      pointed under it (see `CACHE_FOLDERS`), since the container's home is not kept and the clone is not writable. `HF_HOME` and `XDG_CACHE_HOME` stay the person's own when they are
      set to a folder that can be written.
    A pure function of its arguments and the folder permissions: it makes no folder (`make_cache_dirs` does)."""
    env = dict(os.environ if base is None else base)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "LD_LIBRARY_PATH"):
        env.pop(name, None)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if cache_dir:
        for name, folder in CACHE_FOLDERS.items():
            if name in THE_PERSONS_IF_WRITABLE and env.get(name) and _writable(env[name]):
                continue
            env[name] = str(Path(cache_dir) / folder)
    return env


def make_cache_dirs(env: dict[str, str], cache_dir: str) -> None:
    """Make the cache folders `child_environment` pointed under `cache_dir`, before a program starts. A folder that cannot be made is logged and left: the program then says what it
    cannot write, which is a better message than a refusal here."""
    if not cache_dir:
        return
    root = str(Path(cache_dir))
    for name in CACHE_FOLDERS:
        path = env.get(name, "")
        if Path(path).is_relative_to(root):
            try:
                Path(path).mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                log.warning("could not make the video program's cache folder %s: %s", path, exc)


# ------------------------------------------------------------------ what the program says
_TQDM = re.compile(r"(\d+)%\|[^|]*\|\s*(\d+)/(\d+)")
_LOOP = re.compile(r"Running denoising loop \((\d+) steps?")


class LtxProgress:
    """Turns what the program writes to its standard error into (stage, step, steps) reports (DESIGN.md §46.8).

    The program makes the clip in a fixed order, and says so as it goes: it reads the words (`text`), runs the first, rough pass of 8 steps over a small picture (`denoise`),
    builds the upsampler (`upscale`), runs a second pass of 3 steps at the full size (`refine`), decodes the picture and the sound (`decode`) and writes the file (`write`). Its two
    denoising loops are told apart by order: the first is `denoise`, the second `refine`. Anything not known is ignored, so a line a later version adds changes nothing.

    `feed` takes whatever was read, in any chunks: a bar's updates end in a carriage return, a log line in a newline, and a line that is not finished yet is kept for the next call.
    A step bar counts only in the two denoising stages (`step` of `steps`); the rest report `0` of `0` while they work and `1` of `1` when done, where the program says so."""

    def __init__(self) -> None:
        self._rest = ""
        self._loops = 0
        self.stage = "start"
        self.saved: Optional[str] = None  # the path in the line `Video saved to <path>`, once it has been said

    def feed(self, text: str) -> list[tuple[str, int, int]]:
        parts = re.split(r"[\r\n]", self._rest + text)
        self._rest = parts.pop()  # what follows the last separator is not a whole line yet
        return [event for part in parts if (event := self._line(part)) is not None]

    def finish(self) -> list[tuple[str, int, int]]:
        """The last line, when the program ended without ending it."""
        rest, self._rest = self._rest, ""
        event = self._line(rest)
        return [event] if event is not None else []

    def _line(self, line: str) -> Optional[tuple[str, int, int]]:
        line = line.strip()
        if not line:
            return None
        bar = _TQDM.search(line)
        if bar:
            if self.stage in ("denoise", "refine"):
                return self.stage, int(bar.group(2)), int(bar.group(3))
            return None
        if "Building text encoder" in line:
            self.stage = "text"
            return "text", 0, 1
        if "Prompt encoding complete" in line:
            return "text", 1, 1
        if "Building transformer" in line:
            self.stage = "denoise"
            return "denoise", 0, 0
        loop = _LOOP.search(line)
        if loop:
            self._loops += 1
            self.stage = "denoise" if self._loops == 1 else "refine"
            return self.stage, 0, int(loop.group(1))
        if "Building video encoder + spatial upsampler" in line:
            self.stage = "upscale"
            return "upscale", 0, 1
        if "Building video decoder" in line:
            self.stage = "decode"
            return "decode", 0, 2
        if "Building audio decoder" in line:
            self.stage = "decode"
            return "decode", 1, 2
        if "H.264 encode" in line:
            self.stage = "write"
            return "write", 0, 1
        if "Video saved to" in line:
            self.stage = "write"
            self.saved = line.split("Video saved to", 1)[1].strip()
            return "write", 1, 1
        return None


# ------------------------------------------------------------------ what it says when it fails
_OUT_OF_MEMORY = ("out of memory", "outofmemoryerror", "std::bad_alloc", "cannot allocate memory", "cuda error: out of memory")
_ERROR_LINE = re.compile(r"^(?:[\w.]+\.)?\w*(?:Error|Exception|Exit)\b.*|^(?:ERROR|CRITICAL)\b.*|.*\berror:\s.*", re.IGNORECASE)
_NOISE = re.compile(r"^(?:INFO|DEBUG|WARNING)\b|\d+%\||\bit/s\]|^\s*File \"|^\s*at |^Traceback|^\^+$")
OOM_MESSAGE = ("This clip needed more memory than was free. Try a smaller size or a shorter length, or turn on STUDIO_VIDEO_QUANTIZATION, or unload the other models.")


def extract_error(lines: Sequence[str], returncode: int) -> tuple[str, bool]:
    """The one line that says why the program failed, and whether it was for want of memory: (message, out_of_memory). `lines` are the last lines the program wrote.

    Out of memory is recognised by its usual words (CUDA's, PyTorch's, the allocator's), or by the program having been killed (exit 137 or signal 9: what the system does to a
    process when memory runs out). Otherwise the last line that reads as an error is taken (`RuntimeError: ...`, `error: unrecognized arguments ...`), and failing that the last line
    that is not a log line or a progress bar. The server's log holds everything; this is what a person is told."""
    cleaned = [line.strip() for line in lines if line.strip()]
    for line in reversed(cleaned):
        if any(mark in line.lower() for mark in _OUT_OF_MEMORY):
            return OOM_MESSAGE, True
    if returncode in (-9, 137):
        return OOM_MESSAGE, True
    for line in reversed(cleaned):
        if _ERROR_LINE.match(line) and not _NOISE.search(line):
            return _short(line), False
    for line in reversed(cleaned):
        if not _NOISE.search(line):
            return _short(line), False
    return f"The video program stopped without saying why (exit code {returncode}).", False


def failure_for(lines: Sequence[str], returncode: int) -> PipelineError:
    """The error to raise for a program that failed: `OutOfMemory` (with the usual out-of-memory words) or a `PipelineError` that carries the program's own reason. The fake engine
    uses it too, so that the words a person sees for a failed clip are the same wherever the failure was made."""
    message, memory = extract_error(lines, returncode)
    if memory:
        return OutOfMemory(message, hint="The server's log has the program's own words.")
    return PipelineError(f"The video program stopped: {message}", hint="The server's log has the program's last lines.")


def _short(line: str, limit: int = 300) -> str:
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"


# ------------------------------------------------------------------ the environment the program runs in
_INSPECT = r"""
import json, sys, importlib, importlib.util
out = {"python": list(sys.version_info[:3])}
try:
    import torch
    out["torch"] = torch.__version__
    out["cuda_built"] = torch.version.cuda
    out["cuda"] = bool(torch.cuda.is_available())
    out["gpu"] = torch.cuda.get_device_name(0) if out["cuda"] else None
except Exception as exc:
    out["torch_error"] = type(exc).__name__ + ": " + str(exc)
try:
    out["ltx_found"] = importlib.util.find_spec("ltx_pipelines") is not None
    if out["ltx_found"]:
        importlib.import_module("ltx_pipelines.distilled")
        out["ltx_ok"] = True
except Exception as exc:
    out["ltx_error"] = type(exc).__name__ + ": " + str(exc)
# the versions of the libraries the program was measured with (from their metadata: nothing is imported for this), and whether natten really imports: the measured environment's
# own log said it was NOT installed while its package list had it, which nobody has explained, so this says what is true here and never refuses on it
from importlib import metadata
out["packages"] = {}
for name in %(packages)s:
    try:
        out["packages"][name] = metadata.version(name)
    except Exception:
        pass
try:
    import natten
    out["natten"] = "imports"
except Exception as exc:
    out["natten"] = type(exc).__name__ + ": " + str(exc)
print(json.dumps(out))
"""
_INSPECT = _INSPECT % {"packages": repr(sorted(MEASURED_ON_THE_SPARK["packages"]))}
INSPECT_SECONDS = 240  # importing PyTorch and the program's libraries the first time (a cold disk cache) can take a minute or two
MIN_PYTHON = (3, 12)  # the program's own requirement (DESIGN.md §46.3)


@dataclass(frozen=True)
class Environment:
    """What looking at the program's environment found. `problem` is None when a clip can be made, else the reason, with a `hint` saying what to do."""

    command: tuple[str, ...]
    python: Optional[tuple[int, ...]] = None
    torch: Optional[str] = None
    cuda_built: Optional[str] = None
    cuda: Optional[bool] = None
    gpu: Optional[str] = None
    importable: Optional[bool] = None
    packages: Optional[dict[str, str]] = None  # the versions found of the libraries the program was measured with
    natten: Optional[str] = None  # "imports", or why it does not (a note only)
    problem: Optional[str] = None
    hint: Optional[str] = None

    def summary(self) -> str:
        """One line for the build's check and the log: what was found, in a few words."""
        parts = [f"command {' '.join(self.command)}"]
        if self.python:
            parts.append("Python " + ".".join(str(n) for n in self.python))
        if self.torch:
            parts.append(f"torch {self.torch}" + (f" (CUDA {self.cuda_built}, " + (f"GPU {self.gpu}" if self.cuda else "no GPU visible") + ")" if self.cuda_built else " (no CUDA)"))
        if self.importable is not None:
            parts.append(f"{MODULE} {'imports' if self.importable else 'does not import'}")
        return ", ".join(parts)


    def differences(self) -> list[str]:
        """How what was found differs from the environment measured working on the Spark: a list of short phrases, empty when it is the same (as far as it was looked at). Only a
        note for the person: a newer environment may work, and what stops a clip is a problem, never a difference."""
        measured = MEASURED_ON_THE_SPARK
        found: list[str] = []
        if self.python and ".".join(str(n) for n in self.python) != measured["python"]:
            found.append(f"Python {'.'.join(str(n) for n in self.python)} (measured {measured['python']})")
        for name, wanted in measured["packages"].items():
            have = self.torch if name == "torch" else (self.packages or {}).get(name)
            if have is None and self.packages is not None and name != "torch":
                found.append(f"{name} not found (measured {wanted})")
            elif have is not None and have != wanted:
                found.append(f"{name} {have} (measured {wanted})")
        if self.natten and self.natten != "imports":
            found.append(f"natten does not import here ({self.natten})")
        return found


def _program_found(command: Sequence[str]) -> Optional[str]:
    """The reason the program cannot be started (it is not there, or cannot be run), or None. The first word of the command is looked for on the PATH, or at its path."""
    first = command[0]
    found = shutil.which(first)
    if found is None:
        what = "was not found" if os.sep not in first else "is not there or cannot be run"
        return f"The video program {what}: {first}"
    return None


def inspect_environment(command: Sequence[str], env: Optional[dict[str, str]] = None, cache_dir: str = "") -> Environment:
    """Look at the environment the program runs in, without making a clip (DESIGN.md §46.6): is the command there, which Python and PyTorch does it have, can PyTorch see the GPU, and
    does the program import, with which versions of its libraries. A command that is an interpreter (`.../python -m ltx_pipelines.distilled`) is asked directly; any other (`uv run ...`) is asked for `--help`, which is
    what it can answer. Never raises: what is wrong is in `problem` and `hint`."""
    command = tuple(command)
    if not command:
        return Environment(command, problem="No video program is set up.", hint=NOT_SET_UP_HINT)
    missing = _program_found(command)
    if missing:
        return Environment(command, problem=missing, hint="Check STUDIO_VIDEO_LTX_DIR (or STUDIO_VIDEO_COMMAND, STUDIO_VIDEO_PYTHON), and that the folder is shared with the container (docker compose).")
    environment = env if env is not None else child_environment(cache_dir=cache_dir)
    if env is None:
        make_cache_dirs(environment, cache_dir)
    is_python = os.path.basename(command[0]).startswith("python")
    if not is_python:  # `uv run ...` and the like: it can only be asked whether it starts
        try:
            done = subprocess.run([*command, "--help"], capture_output=True, text=True, timeout=INSPECT_SECONDS, env=environment, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return Environment(command, problem=f"The video program could not be started ({type(exc).__name__}: {exc}).", hint="Run the command by hand in the container to see why.")
        if done.returncode != 0:
            message, _ = extract_error((done.stderr or done.stdout).splitlines(), done.returncode)
            return Environment(command, importable=False, problem=f"The video program did not start: {message}", hint="Run the command with --help by hand in the container to see why.")
        return Environment(command, importable=True)
    try:
        done = subprocess.run([command[0], "-c", _INSPECT], capture_output=True, text=True, timeout=INSPECT_SECONDS, env=environment, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Environment(command, problem=f"The video program's Python could not be run ({type(exc).__name__}: {exc}).", hint=f"To see why, run it by hand: docker exec ai-image-studio {command[0]} -c 'import torch, ltx_pipelines'")
    try:
        facts = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        message, _ = extract_error(done.stderr.splitlines(), done.returncode)
        return Environment(command, problem=f"The video program's Python did not answer: {message}", hint=f"To see why, run it by hand: docker exec ai-image-studio {command[0]} -c 'import torch, ltx_pipelines'")
    python = tuple(facts.get("python") or ())
    report = dict(command=command, python=python or None, torch=facts.get("torch"), cuda_built=facts.get("cuda_built"), cuda=facts.get("cuda"), gpu=facts.get("gpu"),
                  packages=facts.get("packages") or {}, natten=facts.get("natten"))
    if python and python[:2] < MIN_PYTHON:
        return Environment(**report, problem=f"The video program's Python is {'.'.join(map(str, python))}; LTX-2 needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.",
                           hint="Make the environment with Python 3.12 (uv sync --python 3.12), the Python the container has too.")
    if facts.get("torch_error"):
        return Environment(**report, problem=f"PyTorch does not import in the video program's environment ({facts['torch_error']}).", hint=REBUILD_HINT)
    if not facts.get("ltx_found"):
        return Environment(**report, importable=False, problem="The LTX-2 program (ltx_pipelines) is not installed in that environment.", hint=REBUILD_HINT)
    if facts.get("ltx_error"):
        return Environment(**report, importable=False, problem=f"The LTX-2 program does not import ({facts['ltx_error']}).", hint=REBUILD_HINT)
    if not facts.get("cuda"):
        return Environment(**report, importable=True, problem="PyTorch in the video program's environment cannot see the GPU.",
                           hint=f"Its PyTorch must be a CUDA build (the one measured working is torch {MEASURED_ON_THE_SPARK['packages']['torch']}), and the container must have the GPU: "
                                f"docker exec ai-image-studio nvidia-smi must show it. If it does, send back the output of: docker exec ai-image-studio env | grep -i -E 'cuda|triton|ld_library'.")
    return Environment(**report, importable=True)


def who() -> str:
    """Who the studio runs as in the container, in the words a message gives so that a person knows which user must be able to read what: `studio (uid 1000, gid 1000)`."""
    uid, gid = os.getuid(), os.getgid()
    try:
        return f"{pwd.getpwuid(uid).pw_name} (uid {uid}, gid {gid})"
    except KeyError:  # the container has no name for the user it was told to run as (STUDIO_UID): the numbers are what the host's `ls -ln` shows
        return f"uid {uid}, gid {gid}"


def _cannot_read(path: Path) -> bool:
    return not os.access(path, os.R_OK | (os.X_OK if path.is_dir() else 0))


def check_ltx_dir(ltx_dir: str) -> Optional[tuple[str, str]]:
    """The first thing wrong with the LTX-2 clone shared from the host, as (the message, what to do), or None when it can be used (DESIGN.md §46.6, as changed). Each step has its own
    reason, in the order a person would put them right: there is a folder, it can be read by the user the studio runs as, it has the virtual environment's interpreter and that
    interpreter's link leads somewhere, it can be run, and the folder has its `packages/` (the editable installs under it are what the program is made of)."""
    root = Path(ltx_dir).expanduser()
    mount = "compose.yaml shares it at the same path (STUDIO_VIDEO_LTX_DIR), read-only; after changing .env run docker compose up -d again."
    if not root.exists():
        return (f"The LTX-2 folder is not there: {root}.", f"STUDIO_VIDEO_LTX_DIR must be the folder on the host that LTX-2 was cloned into. {mount}")
    if not root.is_dir():
        return (f"The LTX-2 folder is not a folder: {root}.", "STUDIO_VIDEO_LTX_DIR must be the folder that LTX-2 was cloned into, not a file.")
    if _cannot_read(root):
        return (f"The studio cannot read the LTX-2 folder {root}: it runs as {who()}.",
                f"On the host: chmod -R a+rX {root} and press Check again; or set STUDIO_UID and STUDIO_GID in .env to the folder's owner (ls -ln shows the numbers) and run docker compose up -d.")
    python = root / ".venv" / "bin" / "python"
    if not os.path.lexists(python):
        return (f"The LTX-2 folder has no Python environment: {python} is not there.",
                f"Make it on the host with uv sync in {root} (as it was made for the first run of LTX), then docker compose up -d.")
    if not python.exists():  # a link that leads nowhere: the venv's python is a link to the host's /usr/bin/python3, which the container must have too
        target = os.readlink(python) if python.is_symlink() else str(python)
        return (f"The LTX-2 environment's Python is a link to {target}, which is not in the container.",
                "The container has Python 3.12 at /usr/bin/python3 (Ubuntu 24.04); an environment made with another Python cannot be shared. Make it with uv sync --python 3.12 on the host.")
    if not os.access(python, os.X_OK):
        return (f"The studio cannot run the LTX-2 environment's Python {python}: it runs as {who()}.", f"On the host: chmod -R a+rX {root}/.venv and press Check again; or set STUDIO_UID and STUDIO_GID in .env to the folder's owner and run docker compose up -d.")
    if not (root / "packages").is_dir():
        return (f"{root} has no packages/ folder, so it does not look like a LTX-2 clone.",
                "STUDIO_VIDEO_LTX_DIR must be the folder that LTX-2 was cloned into (it holds .venv and packages/: the program's own libraries are installed from there).")
    return None


def check_model_files(config: EngineConfig) -> None:
    """The model files, found and readable (DESIGN.md §46.7): raises `PipelineUnavailable` for the first thing wrong. Every problem found is in the hint, so that one look says what to
    put right; a file the studio's user cannot read is its own reason, with who that is and what to change."""
    models = config.models_path()
    named_all = all(config.files.get(kind) for kind in KINDS)  # every file is named by its own setting: the folder's layout does not matter
    if models is None and not named_all:
        raise PipelineUnavailable("The folder of model files is not set.", hint="Set STUDIO_VIDEO_MODELS_DIR in .env to the folder that holds diffusion_models, text_encoders, vae and latent_upscale_models, "
                                                                                 "then docker compose up -d (README, Video).")
    if models is not None and not models.is_dir():
        raise PipelineUnavailable(f"The folder of model files is not there: {models}.",
                                  hint="STUDIO_VIDEO_MODELS_DIR must be the folder on the host that holds diffusion_models, text_encoders, vae and latent_upscale_models. "
                                       "compose.yaml shares it at the same path, read-only; after changing .env run docker compose up -d again.")
    if models is not None and not named_all and not any((models / folder).is_dir() for folder in set(FOLDERS.values())):  # the wrong folder, one level off: say so once
        held = sorted(p.name for p in models.iterdir() if not p.name.startswith("."))[:8] if os.access(models, os.R_OK | os.X_OK) else []
        raise PipelineUnavailable(f"The folder of model files holds none of diffusion_models, text_encoders, vae or latent_upscale_models: {models} (it holds: {', '.join(held) or 'nothing'}).",
                                  hint="STUDIO_VIDEO_MODELS_DIR must be the folder that CONTAINS those folders (for the first run on the Spark: the models folder inside ltx-experiment), not one of them and not its parent.")
    found, problems = find_files(models, config.files)
    if problems:
        also = f" Also wrong: {' '.join(p.message for p in problems[1:])}" if len(problems) > 1 else ""
        raise PipelineUnavailable(problems[0].message, hint=problems[0].hint + also)
    assert found is not None
    unreadable = [(kind, Path(path)) for kind, path in found.as_dict().items() if _cannot_read(Path(path))]
    if unreadable:
        kind, path = unreadable[0]
        raise PipelineUnavailable(f"The studio cannot read {LABELS[kind]}: {path} (it runs as {who()}).",
                                  hint=f"On the host: chmod -R a+rX {models or path.parent} and press Check again; or set STUDIO_UID and STUDIO_GID in .env to the folder's owner (ls -ln shows the numbers) and run docker compose up -d."
                                       + (f" {len(unreadable) - 1} other file(s) cannot be read either." if len(unreadable) > 1 else ""))


def check_ready(config: EngineConfig, *, inspect: bool = True) -> dict[str, Any]:
    """What a probe does: the programs, the clone, the files and the environment, in the order a person would fix them. Raises `PipelineUnavailable` for the first thing wrong, in
    words and with what to do; returns what was found (it carries `device`) when a clip can be made.

    The order: ffmpeg and ffprobe; whether any program is set up; the LTX-2 clone shared from the host (when that is the way: its folder, its readability, its interpreter, its
    `packages/`: `check_ltx_dir`); the model folder and the five files and that they can be read; and last, the slow look at the environment (`inspect_environment`: the program's
    Python is run to import PyTorch and the program, to say their versions and whether the GPU is visible). The result is kept by the server, which asks once at start-up: the page
    never waits for the slow part."""
    tools = media.find_tools(config.ffmpeg, config.ffprobe)
    if not tools.ok:
        raise PipelineUnavailable(tools.reason() or "ffmpeg is missing.", hint="Install ffmpeg in the image (apt-get install ffmpeg), or set STUDIO_VIDEO_FFMPEG and STUDIO_VIDEO_FFPROBE.")
    command = interpreter_command(config)
    if not command:
        raise PipelineUnavailable("Video is not set up: no program is named to make clips.", hint=NOT_SET_UP_HINT)
    named_by_hand = bool(config.command or config.python)
    if config.ltx_dir and not named_by_hand:  # the clone shared from the host is the program: look at it before anything else about it
        wrong = check_ltx_dir(config.ltx_dir)
        if wrong:
            raise PipelineUnavailable(wrong[0], hint=wrong[1])
    elif not named_by_hand and not Path(command[0]).exists():  # only the image's own folder is left, and the image was built without the program: say that, before the models
        raise PipelineUnavailable("Video is not set up: no LTX-2 folder is named, and the program is not built into this image.", hint=NOT_SET_UP_HINT)
    check_model_files(config)
    result: dict[str, Any] = {"command": list(command)}
    if inspect:
        environment = inspect_environment(command, cache_dir=config.cache_dir)
        if environment.problem:
            raise PipelineUnavailable(environment.problem, hint=environment.hint)
        differences = environment.differences()
        log.info("the video program's environment: %s%s", environment.summary(), f"; differs from the measured one in: {'; '.join(differences)}" if differences else "; as measured")
        result["device"] = {"name": environment.gpu, "torch": environment.torch, "cuda": environment.cuda_built}
        if differences:
            result["differences"] = differences
    return result


# ------------------------------------------------------------------ the engine
def _die_with_parent() -> None:
    """Run in the child before it starts the program: ask Linux to kill it when the worker that started it goes (PR_SET_PDEATHSIG = 1), so that a worker that is terminated cannot
    leave a program making a clip nobody is waiting for, with 50 GB of memory. The libc is opened once, at import (see `_LIBC`), because a child must not import anything."""
    if _LIBC is not None:
        _LIBC.prctl(1, int(signal.SIGKILL))


try:
    import ctypes

    _LIBC: Optional[Any] = ctypes.CDLL("libc.so.6", use_errno=True)
except (OSError, ImportError):  # not Linux: no such protection, and no such risk the studio has been built for
    _LIBC = None

TAIL_LINES = 120  # how much of the end of the program's output is kept, for the reason a clip failed
KILL_GRACE_SECONDS = 5.0  # how long a program that was asked to stop may take before it is killed
POLL_SECONDS = 0.2


class LtxEngine(EngineBase):
    """LTX-2.5 through its own program (see the module's first paragraphs)."""

    INFO = INFO
    SECONDS_PER_MINUTE = 60.0  # what STUDIO_VIDEO_TIMEOUT_MIN counts in; an attribute so that a test can make a minute short

    @classmethod
    def probe(cls, config: EngineConfig) -> dict[str, Any]:
        return check_ready(config, inspect=True)

    def load(self) -> dict[str, Any]:
        """There is nothing to load: the program loads its models for every clip. This checks that a clip can be made (the files and the programs, not the slow look at PyTorch,
        which the start-up check did), so that a problem is a message and not a clip that fails a minute in."""
        return check_ready(self.config, inspect=False)

    def generate(self, request: VideoRequest, progress: ProgressCallback, cancelled: CancelCheck) -> Clip:
        config = self.config
        command = interpreter_command(config)
        files, problems = find_files(config.models_path(), config.files)
        if not command or files is None:
            reason = problems[0] if problems else None
            raise PipelineUnavailable(reason.message if reason else "No video program is set up.", hint=reason.hint if reason else "See the Video tab.")
        argv = build_command(command, config, files, request)
        out = Path(request.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.unlink(missing_ok=True)  # a file left by an earlier try must never be taken for this clip's
        log.info("starting the video program: %s", " ".join(argv[:3]) + " ...")
        progress("start", 0, 0)
        try:
            environment = child_environment(cache_dir=config.cache_dir)
            make_cache_dirs(environment, config.cache_dir)
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment, start_new_session=True,
                                    preexec_fn=_die_with_parent if _LIBC is not None else None)
        except OSError as exc:
            raise PipelineUnavailable(f"The video program could not be started: {exc.strerror or exc} ({argv[0]}).", hint="Check the setting that names it (STUDIO_VIDEO_COMMAND).") from exc
        events: "queue.Queue[tuple[str, int, int]]" = queue.Queue()
        tail: list[str] = []
        reader = threading.Thread(target=self._read, args=(proc, events, tail), name="ltx-output", daemon=True)
        reader.start()
        deadline = time.monotonic() + config.timeout_min * self.SECONDS_PER_MINUTE if config.timeout_min else None
        try:
            while True:
                self._report(events, progress)  # may raise Canceled (the worker's callback does, when Cancel has been pressed)
                if cancelled():
                    raise Canceled()
                if deadline is not None and time.monotonic() > deadline:
                    self._stop(proc)
                    raise PipelineError(f"The clip took longer than the {config.timeout_min} minutes STUDIO_VIDEO_TIMEOUT_MIN allows, and was stopped.",
                                        hint="Try a shorter clip or a smaller size, or raise the limit (0 turns it off).")
                if proc.poll() is not None:
                    break
                time.sleep(POLL_SECONDS)
        except BaseException:  # Canceled, a worker being stopped, anything: the program must not outlive the wish for its clip
            self._stop(proc)
            raise
        reader.join(timeout=10)
        self._report(events, progress)
        if proc.returncode != 0:
            log.error("the video program failed (exit code %s); its last lines:\n%s", proc.returncode, "\n".join(tail[-30:]))
            raise failure_for(tail, proc.returncode)
        return Clip(self._validated(out, request))

    @staticmethod
    def _read(proc: "subprocess.Popen[bytes]", events: "queue.Queue[tuple[str, int, int]]", tail: list[str]) -> None:
        """In a thread: read the program's output as it comes, give the progress it reports to the engine's own thread (the callback may raise, which a reader thread cannot
        usefully do), and keep the last lines. The output is decoded as it arrives (a character may be cut by a read) and anything that is not text is replaced, not fatal."""
        parser = LtxProgress()
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        assert proc.stdout is not None
        pending = ""
        while True:
            chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
            if not chunk:
                break
            text = decoder.decode(chunk)
            for event in parser.feed(text):
                events.put(event)
            pending += text
            *lines, pending = re.split(r"[\r\n]", pending)
            tail.extend(line for line in lines if line.strip() and not _TQDM.search(line))
            del tail[:-TAIL_LINES]
        for event in parser.finish():
            events.put(event)
        if pending.strip():
            tail.append(pending)

    @staticmethod
    def _report(events: "queue.Queue[tuple[str, int, int]]", progress: ProgressCallback) -> None:
        while True:
            try:
                stage, step, steps = events.get_nowait()
            except queue.Empty:
                return
            progress(stage, step, steps)

    @staticmethod
    def _stop(proc: "subprocess.Popen[bytes]") -> None:
        """End the program and everything it started: ask politely (the whole process group, which `start_new_session` made), then insist."""
        if proc.poll() is not None:
            return
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                break
            try:
                proc.wait(timeout=KILL_GRACE_SECONDS if sig == signal.SIGTERM else 30)
                break
            except subprocess.TimeoutExpired:
                continue

    def _validated(self, out: Path, request: VideoRequest) -> str:
        """The clip the program wrote, or a reason there is none: the file must exist and be a clip of the size and about the length that was asked for (media.check_output).
        A missing sound track is not a failure here: the server notes it on the clip (DESIGN.md §46.8)."""
        if not out.is_file() or out.stat().st_size == 0:
            raise PipelineError("The video program finished but wrote no clip.", hint="The server's log has the program's last lines.")
        try:
            facts = media.probe_clip(self.config.ffprobe, out)
        except media.MediaError as exc:
            raise PipelineError(f"The video program wrote a file that is not a clip: {exc}", hint="The server's log has the program's last lines.") from exc
        wrong = media.check_output(facts, width=request.width, height=request.height, frames=request.num_frames, fps=request.fps)
        if wrong:
            raise PipelineError(wrong, hint="The clip was not kept.")
        if not facts.has_audio:
            log.warning("the video program wrote a clip with no sound track")
        return str(out)


__all__ = ["INFO", "LtxEngine", "LtxProgress", "MEASURED_ON_THE_SPARK", "build_command", "check_ltx_dir", "check_model_files", "check_ready", "child_environment", "make_cache_dirs", "who", "extract_error", "failure_for", "inspect_environment", "interpreter_command", "KINDS", "LABELS"]
