"""Sanity check for the container image. The Dockerfile runs it at build time; you can re-run it
in a running container:  docker compose exec studio python /app/docker/check_image.py

Fails (exit 1) when:
- pip replaced one of NVIDIA's own builds (torch and friends, listed in /app/ngc-pins.txt),
- PyTorch is not a CUDA build,
- the backend can't import the Qwen-Image-2.1 pipeline the way the server will
  (studio.pipelines.real.import_runtime, which also catches diffusers' placeholder classes),
- the music worker can't import the MiniMax-Music3 pipeline with its own copy of diffusers (STUDIO_MUSIC_LIBS),
- the built web page is missing.
Not fatal (a note): spandrel for Enlarge and vtracer + shapely for Vector cannot be imported or used, and each speech engine (Qwen3-TTS, Voxtral, Kokoro, Piper)
and ffmpeg: an engine that cannot run is reported with its reason, and the Speech tab shows the same reason on its pill (DESIGN.md section 38.3). The same for Video: one line says whether
the LTX program's command is found and which Python and PyTorch it has, and how many of the model files are there (none are, in a build: they are mounted when the container runs).
No GPU is needed: builds don't get one, so whether CUDA can see a GPU is reported, not required.
"""

from __future__ import annotations

import importlib.metadata as md
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PINS = Path("/app/ngc-pins.txt")
# Printed up front, so a failed build log says what was installed. The second half are optional
# extras that NVIDIA's image may bundle and that diffusers/transformers use automatically if present.
REPORTED = ("torch", "torchvision", "triton", "numpy", "transformers", "diffusers", "accelerate",
            "huggingface_hub", "tokenizers", "safetensors", "pillow",
            "flash_attn", "flash_attn_3", "transformer_engine", "torchao", "xformers", "apex", "kernels")


def installed_versions() -> str:
    found = []
    for name in REPORTED:
        try:
            found.append(f"{name}=={md.version(name)}")
        except md.PackageNotFoundError:
            pass
    return ", ".join(found)


# What a subprocess runs to ask one speech engine whether it can run here: the same check the server makes at start-up (studio.speech.registry.probe_engine),
# printed as one line of JSON. A PipelineError (the engine says why it cannot) is an answer; anything else is a crash and is reported as one.
SPEECH_PROBE = """
import json, sys
from studio.pipelines.base import PipelineError
from studio.speech.registry import probe_engine
try:
    print(json.dumps({"ok": probe_engine(sys.argv[1])}))
except PipelineError as exc:
    print(json.dumps({"no": exc.message, "hint": exc.hint}))
"""


def speech_notes() -> list[str]:
    """One line for ffmpeg and one for each real speech engine, as notes. An engine is probed in a process with its own folder of libraries first on the path, as the
    speech worker will have it (studio.worker_client.worker_env), so that Qwen3-TTS's transformers is checked where it will be used. A probe that gets as far as
    asking for a GPU has already imported the engine's libraries, which is what a build can check; there is no GPU in a build."""
    notes: list[str] = []
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        notes.append("Speech: ffmpeg is not installed; a voice recording that is not a plain WAV will be refused (DESIGN.md section 38.4)")
    else:
        version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True).stdout.splitlines()
        notes.append("Speech: " + (version[0] if version else "ffmpeg is installed"))
        # the audiobook (M4B) file needs an AAC encoder and the MP4 writer (DESIGN.md section 44.4): the studio's own check is run, so that the note says what the Speech tab will say
        try:
            from studio.speech.audiobook import probe

            found = probe(ffmpeg)
            notes.append("Speech: ffmpeg has an AAC encoder (the audiobook file can be made)" if found.available else f"Speech: the audiobook file cannot be made: {found.reason}")
        except Exception as exc:  # noqa: BLE001 - only a note
            notes.append(f"Speech: could not find out whether ffmpeg can make the audiobook file ({type(exc).__name__}: {exc})")
    try:
        from studio.config import Settings
        from studio.speech import registry
        from studio.worker_client import worker_env

        settings = Settings.from_env()
        engines = registry.engine_ids("real")
    except Exception as exc:  # noqa: BLE001 - only a note
        return notes + [f"Speech: the engines could not be listed ({type(exc).__name__}: {exc})"]
    for engine_id in engines:
        try:
            run = subprocess.run([sys.executable, "-c", SPEECH_PROBE, engine_id], capture_output=True, text=True, env=worker_env(settings, "speech", engine_id),
                                 timeout=300)
            answer = json.loads(run.stdout.strip().splitlines()[-1])
        except (subprocess.TimeoutExpired, ValueError, IndexError) as exc:
            notes.append(f"Speech: {engine_id}: the check itself failed ({type(exc).__name__}); see the build log")
            continue
        if "ok" in answer:
            notes.append(f"Speech: {engine_id}: can run ({answer['ok'].get('device', 'device not stated')})")
        else:
            notes.append(f"Speech: {engine_id}: not available here: {answer['no']}" + (f" ({answer['hint']})" if answer.get("hint") else ""))
    return notes


def video_ffmpeg_note() -> str:
    """One `Video:` line for the H.264 encoder (libx264). The HD (1920x1080) and Scope (1920x800) sizes are made a few pixels taller and trimmed to size by ffmpeg, which converts the picture
    once more and so needs an H.264 encoder (DESIGN.md section 46.20); every other size only has its streams copied. A note, like every line here: it never fails the build."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return "Video: ffmpeg is not installed, so no clip can be finished"
    try:
        listing = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Video: could not find out whether ffmpeg has an H.264 encoder ({type(exc).__name__}: {exc})"
    # the encoder's NAME is the second column of a line (` V....D libx264   libx264 H.264 / AVC ...`): the description of `libx264rgb` also says "libx264", and is not the encoder
    if "libx264" in {match.group(1) for match in re.finditer(r"^\s*[VAS][.A-Z]{5}\s+(\S+)", listing, re.MULTILINE)}:
        return "Video: ffmpeg has an H.264 encoder (libx264): the HD and Scope sizes can be trimmed to size"
    return "Video: ffmpeg has no H.264 encoder (libx264), so the HD (1920x1080) and Scope (1920x800) sizes cannot be trimmed to size; the other sizes are not affected"


def video_notes() -> list[str]:
    """All the `Video:` lines: the program's (`video_program_notes`), then the one for ffmpeg's H.264 encoder, which is separate because it is true whether or not a program is set up."""
    return [*video_program_notes(), video_ffmpeg_note()]


def video_program_notes() -> list[str]:
    """The `Video:` lines (DESIGN.md section 46.6): what was measured working, whether this image can run the program the first way (the host's LTX-2 clone shared in, whose python is a link
    to /usr/bin/python3) or the second (built in), with the same check the server makes at start-up (so that the line says what the Video tab will say). Nothing here can fail the build:
    a program that is not built in, a Python that is too old, a PyTorch that is not a CUDA build, model files that are not mounted (a build has none of them, and no clone) are each
    a note. A build has no GPU, so whether PyTorch sees one is reported and not required."""
    notes: list[str] = []
    try:
        from studio.config import Settings
        from studio.video.engine import EngineConfig
        from studio.video.engines.ltx import IMAGE_TORCH, MEASURED_ON_THE_SPARK, inspect_environment, interpreter_command
        from studio.video.engines.ltx_files import find_files

        measured = MEASURED_ON_THE_SPARK
        packages = measured["packages"]
        notes.append(
            f"Video: measured working on the Spark ({measured['date']}): LTX-2 commit {measured['ltx_commit'][:7]} (ltx-core, ltx-pipelines, ltx-trainer {packages['ltx-core']}), Python {measured['python']}, "
            f"torch {packages['torch']} (CUDA {measured['cuda']}), transformers {packages['transformers']}, triton {packages['triton']}, natten {packages['natten']}")
        notes.append(f"Video: this image's own PyTorch is {IMAGE_TORCH}, which the program cannot use: it runs in an environment of its own (STUDIO_VIDEO_LTX_DIR, shared from the host, or built in with VIDEO_LTX=1)")
        # the first way depends on this: the clone's .venv/bin/python is a link to /usr/bin/python3, so the image must have the same Python there
        system_python = "/usr/bin/python3"
        if os.path.exists(system_python):
            done = subprocess.run([system_python, "--version"], capture_output=True, text=True, timeout=30)
            found = (done.stdout or done.stderr).strip().replace("Python ", "")
            notes.append(f"Video: {system_python} is Python {found}" + (" (as measured: the host's environment can run here)" if found == measured["python"] else f" (the measured one is {measured['python']}; an environment whose python links here may not run)"))
        else:
            notes.append(f"Video: {system_python} is not in this image, so an environment shared from the host whose python links there cannot run here")

        config = EngineConfig.from_dict(Settings.from_env().video_engine_config())
        command = interpreter_command(config)
        if not command:
            notes.append("Video: no program is set up in this build (STUDIO_VIDEO_LTX_DIR is empty and the LTX environment is not built in: build with VIDEO_LTX=1, or share your clone with STUDIO_VIDEO_LTX_DIR); the Video tab will say so")
            return notes
        report = inspect_environment(command, cache_dir=config.cache_dir)
        if report.problem:
            notes.append(f"Video: not available here: {report.problem}" + (f" ({report.hint})" if report.hint else "") + f"; found: {report.summary()}")
        else:
            differences = report.differences()
            notes.append(f"Video: the LTX program can be started: {report.summary()}" + (f"; differs from the measured one in: {'; '.join(differences)}" if differences else "; as measured"))
        found_files, problems = find_files(config.models_path(), config.files)
        if found_files is not None:
            notes.append("Video: all five model files were found in " + str(config.models_dir))
        else:
            notes.append(f"Video: model files: {problems[0].message} ({len(problems)} of 5 not found; expected in a build, where nothing is mounted yet)")
    except Exception as exc:  # noqa: BLE001 - only a note
        notes.append(f"Video: could not find out whether the LTX program can run ({type(exc).__name__}: {exc})")
    return notes


def main() -> int:
    problems: list[str] = []
    notes: list[str] = []
    print(f"check_image: Python {sys.version.split()[0]}; installed: {installed_versions()}", flush=True)

    if PINS.exists():
        for line in PINS.read_text().split():
            name, _, wanted = line.partition("==")
            installed = md.version(name)
            if installed != wanted:
                problems.append(f"{name} is {installed}, but NVIDIA's image shipped {wanted}: pip replaced it")
    else:
        notes.append(f"{PINS} not found (outside the image?), skipped the NVIDIA-build check")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from studio.pipelines.base import PipelineUnavailable
    from studio.pipelines.real import describe_supports, import_runtime

    try:
        torch, pipeline_cls = import_runtime()
    except PipelineUnavailable as exc:
        problems.append(f"{exc.message} ({exc.hint})" if exc.hint else exc.message)
        if exc.__cause__ is not None:  # the whole chain, so a failed build explains itself
            print("check_image: traceback of the import failure:", file=sys.stderr, flush=True)
            traceback.print_exception(exc.__cause__, file=sys.stderr)
        pip_check = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
        print("check_image: pip check says:\n" + (pip_check.stdout + pip_check.stderr).strip()[:4000],
              file=sys.stderr, flush=True)
    else:
        import diffusers
        import transformers

        if not torch.version.cuda:
            problems.append(f"PyTorch {torch.__version__} is not a CUDA build")
        notes.append(f"torch {torch.__version__} (CUDA {torch.version.cuda}), diffusers {diffusers.__version__}, "
                     f"transformers {transformers.__version__}")
        notes.append(f"pipeline features: {describe_supports(pipeline_cls)}")
        notes.append("GPU visible now: " + ("yes, " + torch.cuda.get_device_name(0) if torch.cuda.is_available()
                                            else "no (expected during a build)"))

    # The music worker runs with its own copy of diffusers first on its path (DESIGN.md §26.4): check it imports there.
    music_libs = os.environ.get("STUDIO_MUSIC_LIBS", "").strip()
    if music_libs:
        code = ("from studio.pipelines.real_music import import_music_runtime; import diffusers; "
                "torch, cls = import_music_runtime(); print(diffusers.__version__, cls.__name__)")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (music_libs, str(Path(__file__).resolve().parents[1] / "backend"),
                                                                       os.environ.get("PYTHONPATH", "")) if p))
        music = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
        if music.returncode:
            problems.append("the music worker cannot import its pipeline with the diffusers in " + music_libs + ": "
                            + (music.stderr.strip().splitlines() or ["(no message)"])[-1]
                            + " (DESIGN.md section 26.4; docker/check_image.py prints the full error below)")
            print("check_image: music import failed:\n" + music.stderr[-4000:], file=sys.stderr, flush=True)
        else:
            notes.append(f"music worker: diffusers {music.stdout.split()[0]} from {music_libs}")
    else:
        notes.append("STUDIO_MUSIC_LIBS is not set (outside the image?), skipped the music import check")

    # Enlarge (DESIGN.md section 28.3) needs spandrel. A copy that cannot be imported is not a failed build: the page says that
    # Enlarge is unavailable and why, and everything else works.
    try:
        import spandrel

        notes.append(f"Enlarge: spandrel {getattr(spandrel, '__version__', md.version('spandrel'))}")
    except Exception as exc:  # noqa: BLE001 - whatever went wrong, it is only a note
        notes.append(f"Enlarge: spandrel cannot be imported here ({type(exc).__name__}: {exc}); the page will say Enlarge is unavailable")

    # Vector (DESIGN.md section 31.6) needs vtracer and shapely. As with spandrel, a copy that cannot be imported (or cannot make a file) is
    # a note and not a failed build: capabilities.vector says that Vector is unavailable and why, and everything else works. A tiny
    # picture is run through the real clean-up, so that "they import" also means "they run" on this machine's architecture.
    try:
        from studio.vector import VectorOptions, available, build_vector

        usable, reason, _hint = available()
        if not usable:
            notes.append(f"Vector: unavailable ({reason}); the Vector tab will say so")
        else:
            import io

            import shapely
            import vtracer  # noqa: F401
            from PIL import Image, ImageDraw

            picture = Image.new("RGB", (64, 64), "white")
            ImageDraw.Draw(picture).rectangle((8, 8, 55, 55), fill="black")
            png = io.BytesIO()
            picture.save(png, "PNG")
            made = build_vector(png.getvalue(), VectorOptions(colours=2, width_mm=20, height_mm=20, min_feature_mm=0.5))
            notes.append(f"Vector: vtracer {md.version('vtracer')}, shapely {shapely.__version__} (GEOS {shapely.geos_version_string}) made "
                         f"a {len(made.layers)}-layer SVG from a test picture")
    except Exception as exc:  # noqa: BLE001 - whatever went wrong, it is only a note
        notes.append(f"Vector: cannot make a test file here ({type(exc).__name__}: {exc}); the Vector tab will say it is unavailable")

    # Speech (DESIGN.md section 38.3). Every engine and ffmpeg are optional: what cannot run is a note, and the Speech tab says why on the engine's pill.
    notes.extend(speech_notes())

    # Video (DESIGN.md section 46.6): the LTX program's own environment, built into the image or shared from the host. Only a note, whatever it finds.
    notes.extend(video_notes())

    static = Path(os.environ.get("STUDIO_STATIC_DIR", "/app/static")) / "index.html"
    if not static.is_file():
        problems.append(f"the web page is missing: {static}")

    for note in notes:
        print("check_image:", note)
    for problem in problems:
        print("check_image: PROBLEM:", problem, file=sys.stderr)
    print("check_image:", "FAILED" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
