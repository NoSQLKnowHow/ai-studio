"""A stand-in for the LTX program, `python -m ltx_pipelines.distilled`, for the tests of the real engine (backend/studio/video/engines/ltx.py).

The real engine does not import any model library: it starts a program, reads what it writes to its standard error, and checks the file it leaves. So the part of it that can be
tested without a GPU is all of it, if something stands in for the program. This file takes the same flags the engine gives the real one (the five model files, `--prompt`,
`--output-path`, `--seed`, `--frame-rate`, `--width`, `--height`, `--num-frames`, `--image`, `--quantization`, `--offload`) and does what the real one does as far as the engine can see:
it writes the log lines and progress bars of a real run (copied from one, with the paths made generic) to its standard error, with the bars' updates ending in a carriage return, and
writes an H.264 and AAC MP4 of the size and length asked for with ffmpeg.

How it behaves is chosen by words in the prompt, as the fake engines' are: `[ltx:error]` fails with a Python error, `[ltx:oom]` fails with CUDA's out-of-memory error, `[ltx:killed]` kills
itself the way the system's out-of-memory killer does, `[ltx:slow]` takes ten seconds in small steps (so that a test can cancel it), `[ltx:silent]` writes no sound, `[ltx:short]` writes a clip
that is far too short, `[ltx:nofile]` ends happily and writes nothing. Every call is recorded in the file named by FAKE_LTX_RECORD (as one JSON line: its arguments and a few facts about its
environment), so that a test can see exactly what the engine ran.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("transformer", "text-encoder", "video-vae", "audio-vae", "spatial-upsampler"):
        parser.add_argument(f"--{name}-path", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--seed", type=int, default=10)
    parser.add_argument("--frame-rate", type=float, default=24.0)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--num-frames", type=int, required=True)
    parser.add_argument("--image", nargs="+", action="append", default=[])
    parser.add_argument("--quantization")
    parser.add_argument("--offload")
    parser.add_argument("--chunked", action="store_true")
    args = parser.parse_args()

    record = os.environ.get("FAKE_LTX_RECORD")
    if record:
        with open(record, "a", encoding="utf-8") as out:
            out.write(json.dumps({"argv": sys.argv[1:], "pythonpath": os.environ.get("PYTHONPATH"), "ld": os.environ.get("LD_LIBRARY_PATH"), "pid": os.getpid(),
                                  "pgid": os.getpgid(0), "unbuffered": os.environ.get("PYTHONUNBUFFERED"),
                                  "env": {name: os.environ.get(name) for name in ("PYTHONDONTWRITEBYTECODE", "TRITON_CACHE_DIR", "TORCHINDUCTOR_CACHE_DIR", "TORCH_HOME", "HF_HOME",
                                                                                "XDG_CACHE_HOME", "HOME", "PATH", "CUDA_VISIBLE_DEVICES", "VIRTUAL_ENV", "PYTHONHOME")}}) + "\n")

    err = sys.stderr
    delay = 0.01

    def say(text: str) -> None:
        err.write(text)
        err.flush()

    def pause(seconds: float = delay) -> None:
        time.sleep(seconds)

    prompt = args.prompt
    say("INFO:ltx_pipelines.utils.blocks.prompt_encoder:Building text encoder from /models/text_encoders/gemma\n")
    pause()
    say("INFO:ltx_pipelines.utils.blocks.prompt_encoder:Prompt encoding complete\n")
    say("INFO:ltx_pipelines.chunks.planner:Plan: 1 chunks\n")
    say("INFO:ltx_pipelines.utils.blocks.diffusion_stage:Building transformer (standard) from (PosixPath('/models/diffusion_models/ltx-distilled.safetensors'),)\n")
    say(f"INFO:ltx_pipelines.utils.blocks.diffusion_stage:Running denoising loop (8 steps, video latent (1, 128, 91, {args.height // 64}, {args.width // 64}), "
        f"audio latent (1, 8, 751, 16) @ {args.frame_rate} fps)\n")
    say("\r  0%|          | 0/8 [00:00<?, ?it/s]")
    slow = "[ltx:slow]" in prompt
    for step in range(1, 9):
        pause(1.25 if slow else delay)
        say(f"\r{step * 100 // 8:3d}%|{'█' * step}{' ' * (8 - step)}| {step}/8 [00:{step:02d}<00:00, 14.90s/it]")
        if step == 3:
            if "[ltx:error]" in prompt:
                say("\nTraceback (most recent call last):\n  File \"/app/main.py\", line 3, in <module>\n    run()\nRuntimeError: the fake program was told to fail\n")
                return 1
            if "[ltx:oom]" in prompt:
                say("\nTraceback (most recent call last):\n  File \"/app/main.py\", line 3, in <module>\n    run()\n"
                    "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 20.00 GiB. GPU 0 has a total capacity of 119.7 GiB\n")
                return 1
            if "[ltx:killed]" in prompt:
                os.kill(os.getpid(), signal.SIGKILL)
    say("\n")
    say("INFO:ltx_pipelines.utils.blocks.video_upsampler:Building video encoder + spatial upsampler from /models/latent_upscale_models/spatial-x2\n")
    say(f"INFO:ltx_pipelines.utils.blocks.diffusion_stage:Running denoising loop (3 steps, video latent (1, 128, 91, {args.height // 32}, {args.width // 32}), "
        f"audio latent (1, 8, 751, 16) @ {args.frame_rate} fps)\n")
    say("\r  0%|          | 0/3 [00:00<?, ?it/s]")
    for step in range(1, 4):
        pause()
        say(f"\r{step * 100 // 3:3d}%|{'█' * step}{' ' * (3 - step)}| {step}/3 [00:{step:02d}<00:00, 16.80s/it]")
    say("\n")
    say("INFO:ltx_pipelines.utils.blocks.video_decoder:Building video decoder from /models/vae/video_vae\n")
    say("INFO:ltx_pipelines.utils.blocks.audio_decoder:Building audio decoder + vocoder from /models/vae/audio_vae\n")
    say("H.264 encode: 1it [00:00, 59.42it/s]\n")

    if "[ltx:nofile]" in prompt:
        return 0
    frames = 9 if "[ltx:short]" in prompt else args.num_frames
    seconds = frames / args.frame_rate
    argv = ["ffmpeg", "-v", "error", "-y", "-threads", "1", "-f", "lavfi", "-i", f"testsrc2=s={args.width}x{args.height}:r={args.frame_rate}:d={seconds + 0.2:.3f}"]
    if "[ltx:silent]" not in prompt:
        argv += ["-f", "lavfi", "-i", f"sine=frequency=330:sample_rate=48000:duration={max(0.1, seconds - 0.03):.3f}"]
    argv += ["-frames:v", str(frames), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    argv += ["-an"] if "[ltx:silent]" in prompt else ["-c:a", "aac", "-ar", "48000", "-ac", "2"]
    argv += [args.output_path]
    done = subprocess.run(argv, capture_output=True, text=True)
    if done.returncode != 0:
        say(done.stderr)
        return 1
    say(f"INFO:ltx_pipelines.utils.media_io.encode:Video saved to {args.output_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
