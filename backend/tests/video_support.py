"""Helpers the video tests share (DESIGN.md §46): a folder of model files laid out as the Spark's is, an engine config that runs the stand-in for the LTX program, a request for
a clip, and a worker running in this process with the fake video engine."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from studio.pipelines import make_pipeline
from studio.video.engine import ConditioningImage, EngineConfig, VideoRequest
from studio.worker import Worker

from speech_support import Capture

RUN_ID = "0123456789abcdef0123456789abcdef"
OTHER_RUN_ID = "fedcba9876543210fedcba9876543210"
FAKE_PROGRAM = Path(__file__).parent / "fake_ltx_program.py"


def models_folder(root: Path, extra: Optional[dict[str, list[str]]] = None) -> Path:
    """A folder of model files laid out the way ComfyUI's is (and the Spark's): one usual file in each usual folder, empty files (the engine never opens them: the program does).
    `extra` adds more files, by folder, for a test of what happens when a folder holds several."""
    layout = {
        "diffusion_models": ["ltx-2.5-22b-distilled.safetensors"], "text_encoders": ["gemma_12b_it.safetensors"],
        "vae": ["ltx_video_vae.safetensors", "ltx_audio_vae.safetensors"], "latent_upscale_models": ["ltx-spatial-upscaler-x2.safetensors"], "model_patches": ["some_patch.safetensors"],
    }
    for folder, names in {**layout, **{k: layout.get(k, []) + v for k, v in (extra or {}).items()}}.items():
        (root / folder).mkdir(parents=True, exist_ok=True)
        for name in names:
            (root / folder / name).write_bytes(b"")
    return root


def program_config(models: Path, **changes: Any) -> EngineConfig:
    """An engine config whose program is the stand-in (`fake_ltx_program.py`), run by the interpreter the tests run in."""
    values: dict[str, Any] = dict(models_dir=str(models), command=(sys.executable, str(FAKE_PROGRAM)))
    values.update(changes)
    return EngineConfig(**values)


def request(out: Path, prompt: str = "a fox in the snow", width: int = 256, height: int = 128, frames: int = 25, fps: int = 24, seed: int = 7,
            images: tuple[ConditioningImage, ...] = ()) -> VideoRequest:
    """A request for a small clip (256x128, 25 frames: about a second), written to `out`."""
    return VideoRequest(prompt=prompt, width=width, height=height, num_frames=frames, fps=fps, seed=seed, variant="distilled", out=str(out), images=images)


def video_job(run_id: str = RUN_ID, **extra: Any) -> dict[str, Any]:
    """A job as the API would send it for a text clip (engine `fake`)."""
    job: dict[str, Any] = {"run_id": run_id, "engine": "fake", "variant": "distilled", "prompt": "a fox in the snow", "width": 256, "height": 128, "num_frames": 25, "fps": 24,
                           "seed": 7, "out": f"video/{run_id}/engine-out.mp4", "images": []}
    job.update(extra)
    return job


def in_process_worker(data_dir: Path, step_delay_ms: int = 0) -> tuple[Worker, Capture]:
    """A video worker running in this process with the fake engine, so a test can call `run` and look at the events without a subprocess."""
    emit = Capture()
    pipeline = make_pipeline("fake", model="", cpu_offload=False, hub_mode="auto", fake_step_delay_ms=step_delay_ms, kind="video", engine="fake", variant="distilled", engine_config={})
    return Worker(pipeline, data_dir, emit, kind="video"), emit  # type: ignore[arg-type]


# ---------------------------------------------------------------- the server, with the fake engine
def accept_licence(client: Any) -> dict[str, Any]:
    """Acknowledge the licence the way a person does, with the revision they saw (nothing else accepts it)."""
    caps = client.get("/api/capabilities").json()["video"]
    response = client.post("/api/video/licence", json={"accept": True, "revision": caps["licence"]["revision"]})
    assert response.status_code == 200, response.text
    return response.json()


def clip_body(prompt: str = "a fox in the snow", **options: Any) -> dict[str, Any]:
    """The body of a request for a small clip (256x128, one second), which the fake engine makes in well under a second."""
    return {"mode": "video", "prompt": prompt, "options": {"width": 256, "height": 128, "seconds": 1, **options}}


def create_clip(client: Any, prompt: str = "a fox in the snow", expect: int = 201, pictures: Optional[list[dict[str, Any]]] = None, **options: Any) -> dict[str, Any]:
    body = clip_body(prompt, **options)
    if pictures is not None:
        body["input_images"] = pictures
    response = client.post("/api/runs", json=body)
    assert response.status_code == expect, response.text
    return response.json()


def wait_for_video_probe(client: Any, timeout: float = 20.0) -> dict[str, Any]:
    """The start-up check of the video engine runs in a process of its own and takes a moment: wait until the capabilities say what it found."""
    import time

    deadline = time.monotonic() + timeout
    while True:
        caps = client.get("/api/capabilities").json()["video"]
        if caps["state"] != "checking":
            return caps
        if time.monotonic() > deadline:
            raise AssertionError("the video engine was still being checked")
        time.sleep(0.05)


def record_events(client) -> list[tuple[str, dict]]:
    """Every event the server publishes from now on, kept in a list (published on the event loop; the list is read after the run)."""
    seen: list[tuple[str, dict]] = []
    bus = client.app.state.bus
    original = bus.publish

    def publish(event, data):
        seen.append((event, data))
        original(event, data)

    bus.publish = publish
    return seen


# ---------------------------------------------------------------- the clone shared from the host (STUDIO_VIDEO_LTX_DIR)
def ltx_clone(root: Path, *, python_link: Optional[str] = None, packages: bool = True) -> Path:
    """A folder laid out as the person's LTX-2 clone is (`<root>/.venv/bin/python` and `<root>/packages/`), whose interpreter runs a STAND-IN for the program and for PyTorch.

    The real clone's `python` is a link to `/usr/bin/python3` and its libraries are installed under `.venv` and `packages/`; here `python` is a small script that starts the interpreter
    the tests run in with a folder of stand-ins first on its path: a `torch` that has the measured version and says whether a GPU is visible (the environment variable
    `FAKE_TORCH_NO_GPU=1` says none), and `ltx_pipelines.distilled`, which is `fake_ltx_program.py`. The studio starts it as `<root>/.venv/bin/python -m ltx_pipelines.distilled`, so what
    is tested is the way the program is found, checked and run, which is all of it that needs no GPU. `python_link` makes `python` a link to that path instead (a dangling one, to
    test the message); `packages=False` leaves out the folder."""
    standin = root / "standin"
    (standin / "torch").mkdir(parents=True)
    (standin / "torch" / "__init__.py").write_text(
        "import os\n__version__ = '2.13.0+cu132'\n\n\nclass version:\n    cuda = '13.2'\n\n\nclass cuda:\n"
        "    @staticmethod\n    def is_available():\n        return os.environ.get('FAKE_TORCH_NO_GPU') != '1'\n\n"
        "    @staticmethod\n    def get_device_name(index):\n        return 'NVIDIA GB10 (stand-in)'\n", encoding="utf-8")
    (standin / "ltx_pipelines").mkdir()
    (standin / "ltx_pipelines" / "__init__.py").write_text("", encoding="utf-8")
    (standin / "ltx_pipelines" / "distilled.py").write_text(
        f"import sys\n\n\ndef main():\n    sys.path.insert(0, {str(Path(__file__).parent)!r})\n    import fake_ltx_program\n    return fake_ltx_program.main()\n\n\n"
        "if __name__ == '__main__':  # as the real module: importing it runs nothing\n    sys.exit(main())\n", encoding="utf-8")
    bin_dir = root / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python"
    if python_link is not None:
        python.symlink_to(python_link)
    else:
        python.write_text(f'#!/bin/sh\nPYTHONPATH="{standin}" exec "{sys.executable}" "$@"\n', encoding="utf-8")
        python.chmod(0o755)
    if packages:
        (root / "packages").mkdir()
    return root
