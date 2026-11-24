"""The fake video engine: what every automated test and the browser tests use (DESIGN.md §46.6, criterion 444). It is the test engine, not the product: the product is `ltx.py`.

Like the fake image, music and speech engines it proves the plumbing and not the picture or the sound. It makes a **real MP4 with a real sound track**, with ffmpeg's own test
sources, at the width, height, number of frames and frame rate asked for: a moving gradient whose colours come from the seed and the prompt, and a sine tone whose pitch comes from
them. The same request always gives the same file, a different seed a different one. A start picture is the clip's first frame (so a test can see that image to video carried
the picture across): the picture, slowly zooming in.

It also says what the real program says. The real engine reads its progress from the program's log (`ltx.LtxProgress`); this one writes the same lines, in the same order, and reads
them with the same parser, so a test of the worker, the queue and the page sees the real stages (`text`, `denoise`, `upscale`, `refine`, `decode`, `write`) and the real step counts
(8, then 3). A failure is made the same way, through the real engine's `failure_for`, so the words of a failed clip are the real ones.

Directives (anywhere in the prompt): `[fake:error]` fails the clip, `[fake:oom]` fails it with the out-of-memory words, `[fake:slow]` makes it take about six seconds in small slices
that look for Cancel, `[fake:silent]` writes no sound track (a clip the page must say has none). `STUDIO_FAKE_VIDEO_UNAVAILABLE=1` makes the start-up check fail, as a machine with no
video program does. `STUDIO_FAKE_STEP_DELAY_MS` is the pause for each step, as for the other fakes.
"""

from __future__ import annotations

import os
import subprocess
import time
import zlib
from pathlib import Path
from typing import Any

from ...pipelines.base import Canceled, PipelineError, PipelineUnavailable
from .. import media
from ..engine import CancelCheck, Clip, EngineBase, EngineConfig, Estimate, ProgressCallback, SizePreset, VideoEngineInfo, VideoLicence, VideoRequest
from .ltx import LtxProgress, failure_for

ERROR_DIRECTIVE = "[fake:error]"
OOM_DIRECTIVE = "[fake:oom]"
SLOW_DIRECTIVE = "[fake:slow]"
SILENT_DIRECTIVE = "[fake:silent]"
SLOW_SECONDS = 6.0  # how long a [fake:slow] clip takes, in all
SLICE_SECONDS = 0.05  # how often a slow clip looks for Cancel

INFO = VideoEngineInfo(
    id="fake", title="Fake video", model_id="fake-video", variants=("distilled", "dev"), default_variant="distilled",
    licence=VideoLicence(
        name="Test licence", summary="A stand-in for the real licence's summary, so that the page's licence panel has something to show in a test.",
        url="https://example.org/test-licence", revision="fake-1", statement="I have read the test licence and my use of this test clip is covered by it.",
        notice="Made with the fake video engine."),
    memory_gb=0.1, size_multiple=64, size_min=64, size_max=1920, size_default=(1280, 704),
    size_presets=(SizePreset("landscape", "1280×704", 1280, 704), SizePreset("hd", "HD 1920×1080", 1920, 1080, 1920, 1088),
                  SizePreset("scope", "Scope 2.40:1 · 1920×800", 1920, 800, 1920, 832), SizePreset("quick", "1024×576 (quick look)", 1024, 576),
                  SizePreset("portrait", "704×1280", 704, 1280), SizePreset("tiny", "512×320 (a test)", 512, 320)),
    fps_choices=(24,),
    estimate=Estimate(points=((0.0, 1.0), (5.0, 2.0), (30.0, 6.0)), reference_pixels=1280 * 704, kind="stand-in", source="the test engine's own: a few seconds"),
    bytes_per_second=320_000.0, notes="A stand-in that makes a test clip with ffmpeg.",
)


def _colour_and_tone(prompt: str, seed: int) -> tuple[int, int, int, float, int]:
    """The gradient's two colours, how fast it moves, the tone's pitch and the gradient's own seed: all from the prompt and the seed, so that the same request gives the same clip."""
    hashed = zlib.crc32(f"{prompt}|{seed}".encode("utf-8"))
    other = zlib.crc32(f"{seed}|{prompt}".encode("utf-8"))
    return hashed & 0xFFFFFF, other & 0xFFFFFF, 0.01 + (hashed >> 24) % 5 / 100, 150 + (other >> 8) % 600, hashed


class FakeVideo(EngineBase):
    """The fake engine (see the module's first paragraphs)."""

    INFO = INFO

    @classmethod
    def probe(cls, config: EngineConfig) -> dict[str, Any]:
        if os.environ.get("STUDIO_FAKE_VIDEO_UNAVAILABLE", "").strip().lower() in ("1", "true", "yes"):
            raise PipelineUnavailable("The fake video program is not installed.", hint="This is a test; unset STUDIO_FAKE_VIDEO_UNAVAILABLE.")
        tools = media.find_tools(config.ffmpeg, config.ffprobe)
        if not tools.ok:
            raise PipelineUnavailable(tools.reason() or "ffmpeg is missing.", hint="The fake engine writes its clips with ffmpeg.")
        return {"device": "fake"}

    def load(self) -> dict[str, Any]:
        if self.config.step_delay_ms:
            time.sleep(self.config.step_delay_ms / 1000)  # a little time to load, so that a test can see the "loading" state of a worker
        return {"device": "fake"}

    # ------------------------------------------------------------------ the pretend program
    def _script(self, request: VideoRequest) -> list[tuple[str, int]]:
        """What the real program would write, as (text, how many steps' worth of time it takes): a log line, or a bar's update. Each line is whole; the bar's updates end in a carriage
        return, as tqdm's do, and the last of a bar's lines ends in a newline."""
        lines: list[tuple[str, int]] = [
            ("INFO:ltx_pipelines.utils.blocks.prompt_encoder:Building text encoder from /fake/text_encoder\n", 1),
            ("INFO:ltx_pipelines.utils.blocks.prompt_encoder:Prompt encoding complete\n", 1),
            ("INFO:ltx_pipelines.chunks.planner:Plan: 1 chunks\n", 0),
            ("INFO:ltx_pipelines.utils.blocks.diffusion_stage:Building transformer (standard) from (PosixPath('/fake/transformer'),)\n", 1),
        ]
        for loop, steps in enumerate((8, 3)):
            if loop == 1:
                lines.append(("INFO:ltx_pipelines.utils.blocks.video_upsampler:Building video encoder + spatial upsampler from /fake/upsampler\n", 1))
            lines.append((f"INFO:ltx_pipelines.utils.blocks.diffusion_stage:Running denoising loop ({steps} steps, video latent (1, 128, "
                          f"{request.num_frames // 8 + 1}, {request.height // 64 * (loop + 1)}, {request.width // 64 * (loop + 1)}), audio latent (1, 8, 751, 16) @ {float(request.fps)} fps)\n", 0))
            lines.append((f"\r  0%|          | 0/{steps} [00:00<?, ?it/s]", 0))
            for step in range(1, steps + 1):
                lines.append((f"\r{step * 100 // steps:3d}%|{'█' * step}{' ' * (steps - step)}| {step}/{steps} [00:0{step % 10}<00:00, 1.00s/it]" + ("\n" if step == steps else ""), 1))
        lines += [
            ("INFO:ltx_pipelines.utils.blocks.video_decoder:Building video decoder from /fake/video_vae\n", 1),
            ("INFO:ltx_pipelines.utils.blocks.audio_decoder:Building audio decoder + vocoder from /fake/audio_vae\n", 1),
            ("H.264 encode: 1it [00:00, 59.42it/s]\n", 0),
        ]
        return lines

    def _wait(self, seconds: float, cancelled: CancelCheck) -> None:
        """Take `seconds`, in slices, looking for Cancel between them. Raises Canceled."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if cancelled():
                raise Canceled()
            time.sleep(min(SLICE_SECONDS, max(0.0, end - time.monotonic())))

    def generate(self, request: VideoRequest, progress: ProgressCallback, cancelled: CancelCheck) -> Clip:
        if cancelled():
            raise Canceled()
        prompt = request.prompt
        script = self._script(request)
        timed = [item for item in script if item[1]]
        # how long one step's worth of time is: the setting's, or for a slow clip an even share of six seconds
        pause = SLOW_SECONDS / len(timed) if SLOW_DIRECTIVE in prompt else self.config.step_delay_ms / 1000
        parser = LtxProgress()
        progress("start", 0, 0)
        shown: list[str] = []
        for number, (text, weight) in enumerate(script):
            for stage, step, steps in parser.feed(text):
                progress(stage, step, steps)
            shown.append(text.strip())
            if number == 5:  # inside the first denoising loop: where a failed program fails
                if ERROR_DIRECTIVE in prompt:
                    raise failure_for([*shown, "RuntimeError: the fake video program was told to fail on this clip"], 1)
                if OOM_DIRECTIVE in prompt:
                    raise failure_for([*shown, "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 20.00 GiB"], 1)
            if weight and pause:
                self._wait(pause, cancelled)
            elif cancelled():
                raise Canceled()
        for stage, step, steps in parser.finish():
            progress(stage, step, steps)
        out = self._make_file(request, cancelled, silent=SILENT_DIRECTIVE in prompt)
        for stage, step, steps in parser.feed(f"INFO:ltx_pipelines.utils.media_io.encode:Video saved to {out}\n"):
            progress(stage, step, steps)
        return Clip(str(out))

    # ------------------------------------------------------------------ the file
    def _make_file(self, request: VideoRequest, cancelled: CancelCheck, *, silent: bool) -> Path:
        """Write the clip with ffmpeg: the gradient (or the start picture), the tone, H.264 and AAC, at the size, length and rate asked for. Everything that could make two runs of
        the same request differ is switched off (one thread, no encoder version in the file), so that the same request gives the same bytes."""
        out = Path(request.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        c0, c1, speed, pitch, gradient_seed = _colour_and_tone(request.prompt, request.seed)
        seconds = request.num_frames / request.fps
        argv = [self.config.ffmpeg, "-v", "error", "-y", "-threads", "1"]
        if request.images:
            picture = Path(request.images[0].path)
            if not picture.is_file():
                raise PipelineError(f"The start picture is not there: {picture}", hint="Add the picture again.")
            # the picture, slowly zooming in; frame 0 is the picture as it is (`on` is the output frame's number, from 0)
            argv += ["-loop", "1", "-framerate", str(request.fps), "-i", str(picture)]
            zoom = ["-vf", f"zoompan=z='min(1+on*0.0008,1.2)':d=1:s={request.width}x{request.height}:fps={request.fps},format=yuv420p"]  # an output option: after the inputs
        else:
            zoom = []
            argv += ["-f", "lavfi", "-i", f"gradients=s={request.width}x{request.height}:r={request.fps}:c0=0x{c0:06x}:c1=0x{c1:06x}:speed={speed}:seed={gradient_seed}:d={seconds + 0.2:.3f}"]
        if not silent:  # the sound is a little shorter than the picture, as the real program's is
            argv += ["-f", "lavfi", "-i", f"sine=frequency={pitch}:sample_rate=48000:duration={max(0.1, seconds - 0.042):.3f}"]
        argv += [*zoom, "-frames:v", str(request.num_frames), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
        argv += ["-an"] if silent else ["-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-ac", "2"]
        argv += ["-movflags", "+faststart", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", "-map_metadata", "-1", str(out)]
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except OSError as exc:
            raise PipelineUnavailable(f"ffmpeg could not be started: {exc.strerror or exc}.", hint="The fake engine writes its clips with ffmpeg.") from exc
        while proc.poll() is None:
            if cancelled():
                proc.kill()
                proc.wait()
                out.unlink(missing_ok=True)
                raise Canceled()
            time.sleep(0.02)
        assert proc.stderr is not None
        problem = proc.stderr.read().strip()
        if proc.returncode != 0 or not out.is_file():
            out.unlink(missing_ok=True)
            raise PipelineError(f"ffmpeg could not make the test clip: {problem.splitlines()[-1] if problem else 'no reason given'}", hint="The fake engine writes its clips with ffmpeg.")
        return out
