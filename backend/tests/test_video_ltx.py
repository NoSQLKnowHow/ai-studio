"""The real video engine (DESIGN.md §46.6), without a GPU: `studio/video/engines/ltx.py` runs a program and reads what it says, so a stand-in program (`fake_ltx_program.py`, which
writes the log lines of a real run and a real MP4) lets every part of it be tried here: the command line it builds, the progress it reads (the real log lines, as the parser's fixtures),
how it stops a program (Cancel, the time limit, a worker that is stopped), how a failure is put into words (a Python error, CUDA's out of memory, being killed), and the check of the file.

What this does NOT show is the real program: that it takes these flags, how long it takes, whether it makes a good clip. That is the Spark's to show (docs/SPARK_TEST.md)."""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest
from video_support import FAKE_PROGRAM, models_folder, program_config, request

from studio.pipelines.base import Canceled, OutOfMemory, PipelineError, PipelineUnavailable
from studio.video import media
from studio.video.engine import ConditioningImage, EngineConfig
from studio.video.engines import ltx
from studio.video.engines.ltx import LtxEngine, LtxProgress, build_command, check_ready, child_environment, extract_error, failure_for, inspect_environment, interpreter_command, make_cache_dirs
from studio.video.engines.ltx_files import ModelFiles, find_files, find_one

needs_ffmpeg = pytest.mark.skipif(not media.find_tools().ok, reason="ffmpeg and ffprobe are not installed here")

# What a real run said, as the program wrote it (paths made generic). The bars' updates end in a carriage return, the log lines in a newline.
REAL_RUN = (
    "INFO:ltx_pipelines.utils.blocks.prompt_encoder:Building text encoder from /models/text_encoders/gemma\n"
    "INFO:ltx_pipelines.utils.blocks.prompt_encoder:Prompt encoding complete\n"
    "INFO:ltx_pipelines.chunks.planner:Plan: 1 chunks\n"
    "INFO:ltx_pipelines.utils.blocks.diffusion_stage:Building transformer (standard) from (PosixPath('/models/diffusion_models/ltx.safetensors'),)\n"
    "INFO:ltx_pipelines.utils.blocks.diffusion_stage:Running denoising loop (8 steps, video latent (1, 128, 91, 11, 20), audio latent (1, 8, 751, 16) @ 24.0 fps)\n"
    "\r  0%|          | 0/8 [00:00<?, ?it/s]\r 12%|█▎        | 1/8 [00:14<01:44, 14.90s/it]\r 25%|██▌       | 2/8 [00:29<01:29, 14.95s/it]"
    "\r 88%|████████▊ | 7/8 [01:55<00:16, 16.80s/it]\r100%|██████████| 8/8 [02:11<00:00, 16.40s/it]\n"
    "INFO:ltx_pipelines.utils.blocks.video_upsampler:Building video encoder + spatial upsampler from /models/latent_upscale_models/spatial\n"
    "INFO:ltx_pipelines.utils.blocks.diffusion_stage:Running denoising loop (3 steps, video latent (1, 128, 91, 22, 40), audio latent (1, 8, 751, 16) @ 24.0 fps)\n"
    "\r  0%|          | 0/3 [00:00<?, ?it/s]\r 33%|███▎      | 1/3 [01:40<03:20, 100.1s/it]\r 67%|██████▋   | 2/3 [03:20<01:40, 100.2s/it]\r100%|██████████| 3/3 [05:00<00:00, 100.0s/it]\n"
    "INFO:ltx_pipelines.utils.blocks.video_decoder:Building video decoder from /models/vae/video_vae\n"
    "INFO:ltx_pipelines.utils.blocks.audio_decoder:Building audio decoder + vocoder from /models/vae/audio_vae\n"
    "H.264 encode: 1it [00:00, 59.42it/s]\n"
    "INFO:ltx_pipelines.utils.media_io.encode:Video saved to /data/video/abc/engine-out.mp4\n"
)


def parse(text: str, step: int = 10_000) -> tuple[list[tuple[str, int, int]], LtxProgress]:
    """Everything the parser says of `text`, fed in pieces of `step` characters (so that a line cut in two is read the same)."""
    parser = LtxProgress()
    events: list[tuple[str, int, int]] = []
    for at in range(0, len(text), step):
        events += parser.feed(text[at:at + step])
    events += parser.finish()
    return events, parser


# ---------------------------------------------------------------- the progress parser
def test_a_real_run_is_read_stage_by_stage_in_order():
    events, parser = parse(REAL_RUN)
    stages = [stage for stage, _step, _steps in events]
    # the stages come in the program's own order, each once or more, and never go back
    order = ["text", "denoise", "upscale", "refine", "decode", "write"]
    assert [s for i, s in enumerate(stages) if i == 0 or s != stages[i - 1]] == order
    assert events[0] == ("text", 0, 1) and events[-1] == ("write", 1, 1)
    assert parser.saved == "/data/video/abc/engine-out.mp4"


def test_the_two_denoising_loops_are_the_rough_pass_and_the_sharpening_pass_with_their_step_counts():
    events, _ = parse(REAL_RUN)
    assert ("denoise", 0, 8) in events and ("refine", 0, 3) in events  # the loops announce their size
    assert [e for e in events if e[0] == "denoise" and e[1]] == [("denoise", n, 8) for n in (1, 2, 7, 8)]
    assert [e for e in events if e[0] == "refine" and e[1]] == [("refine", n, 3) for n in (1, 2, 3)]


def test_the_progress_bar_is_read_on_both_carriage_returns_and_newlines():
    bar_only = "\r  0%|          | 0/8 [00:00<?, ?it/s]\r 12%|█▎        | 1/8 [00:14<01:44, 14.90s/it]"
    parser = LtxProgress()
    parser.feed("INFO:x:Running denoising loop (8 steps, video latent (1,), audio latent (1,) @ 24.0 fps)\n")
    # the update that has no carriage return after it yet is not a whole line, and is kept for the next read
    assert parser.feed(bar_only) == [("denoise", 0, 8)]
    assert parser.feed("\r 25%|██▌       | 2/8 [00:29<01:29, 14.95s/it]\n") == [("denoise", 1, 8), ("denoise", 2, 8)]


@pytest.mark.parametrize("step", [1, 2, 3, 7, 50, 1000])
def test_the_events_are_the_same_however_the_output_is_cut_into_reads(step):
    assert parse(REAL_RUN, step)[0] == parse(REAL_RUN)[0]


def test_a_line_the_parser_does_not_know_changes_nothing():
    parser = LtxProgress()
    assert parser.feed("WARNING:some.library:a new warning a later version prints\nFetching 3 files: 100%|██████████| 3/3 [00:00<00:00, 9.9it/s]\n") == []
    assert parser.stage == "start"  # a bar outside the two loops is not a step of the clip


def test_the_stage_is_the_loops_not_the_words_of_the_log():
    # the second loop is the sharpening pass whatever is said before it: it is told by order
    parser = LtxProgress()
    assert parser.feed("Running denoising loop (5 steps, x)\nRunning denoising loop (2 steps, y)\n") == [("denoise", 0, 5), ("refine", 0, 2)]


# ---------------------------------------------------------------- the files
def test_the_five_files_are_found_in_their_usual_folders(tmp_path):
    models = models_folder(tmp_path)
    files, problems = find_files(models, {})
    assert problems == [] and isinstance(files, ModelFiles)
    assert files.transformer.name == "ltx-2.5-22b-distilled.safetensors" and files.text_encoder.name == "gemma_12b_it.safetensors"
    assert files.video_vae.name == "ltx_video_vae.safetensors" and files.audio_vae.name == "ltx_audio_vae.safetensors"  # the two VAEs share a folder and are told apart by a word
    assert files.upsampler.name == "ltx-spatial-upscaler-x2.safetensors"


def test_a_smaller_copy_of_a_model_is_not_taken_for_the_full_size_one(tmp_path):
    models = models_folder(tmp_path, {"diffusion_models": ["ltx-2.5-22b-distilled-fp8.safetensors"]})
    files, _ = find_files(models, {})
    assert files is not None and files.transformer.name == "ltx-2.5-22b-distilled.safetensors"


def test_two_files_that_could_both_be_the_one_are_listed_and_the_setting_that_picks_is_named(tmp_path):
    models = models_folder(tmp_path, {"diffusion_models": ["ltx-2.5-22b-distilled-v2.safetensors"]})
    files, problems = find_files(models, {})
    assert files is None and len(problems) == 1
    assert "More than one file" in problems[0].message and "ltx-2.5-22b-distilled.safetensors" in problems[0].message and "ltx-2.5-22b-distilled-v2.safetensors" in problems[0].message
    assert "STUDIO_VIDEO_TRANSFORMER" in problems[0].hint
    # and the setting settles it
    files, problems = find_files(models, {"transformer": "diffusion_models/ltx-2.5-22b-distilled-v2.safetensors"})
    assert problems == [] and files is not None and files.transformer.name.endswith("-v2.safetensors")


def test_a_missing_file_is_reported_with_its_full_path_and_every_problem_at_once(tmp_path):
    models = models_folder(tmp_path)
    (models / "vae" / "ltx_audio_vae.safetensors").unlink()
    (models / "latent_upscale_models" / "ltx-spatial-upscaler-x2.safetensors").unlink()
    files, problems = find_files(models, {"text_encoder": "text_encoders/not-there.safetensors"})
    assert files is None
    messages = " | ".join(p.message for p in problems)
    assert str(models / "text_encoders" / "not-there.safetensors") in messages  # a file named by the person: its full path
    assert "the sound VAE" in messages and "the spatial upsampler" in messages and len(problems) == 3


def test_no_models_folder_is_said_and_a_missing_folder_names_its_path(tmp_path):
    _, problems = find_files(None, {})
    assert len(problems) == 5 and all("STUDIO_VIDEO_MODELS_DIR" in p.message + p.hint for p in problems)
    path, problem = find_one("transformer", tmp_path / "nope", "")
    assert path is None and problem is not None and str(tmp_path / "nope" / "diffusion_models") in problem.message


def test_a_text_encoder_may_be_a_folder_in_hugging_faces_own_layout(tmp_path):
    models = models_folder(tmp_path)
    (models / "text_encoders" / "gemma_12b_it.safetensors").unlink()
    (models / "text_encoders" / "gemma-12b").mkdir()
    files, problems = find_files(models, {})
    assert problems == [] and files is not None and files.text_encoder.is_dir()


# ---------------------------------------------------------------- the command line
def files_for(tmp_path) -> ModelFiles:
    files, problems = find_files(models_folder(tmp_path), {})
    assert files is not None, problems
    return files


def test_the_command_line_is_the_one_the_program_was_run_with_by_hand(tmp_path):
    files = files_for(tmp_path)
    out = tmp_path / "video" / "x" / "engine-out.mp4"
    argv = build_command(("/opt/video-libs/ltx/bin/python", "-m", "ltx_pipelines.distilled"), EngineConfig(), files, request(out, "a red fox", 1280, 704, 241, 24, 4821))
    assert argv == [
        "/opt/video-libs/ltx/bin/python", "-m", "ltx_pipelines.distilled",
        "--transformer-path", str(files.transformer), "--text-encoder-path", str(files.text_encoder), "--video-vae-path", str(files.video_vae),
        "--audio-vae-path", str(files.audio_vae), "--spatial-upsampler-path", str(files.upsampler),
        "--prompt", "a red fox", "--output-path", str(out), "--seed", "4821", "--frame-rate", "24.0", "--width", "1280", "--height", "704", "--num-frames", "241",
    ]  # no quantization, no offload, no picture: none of those flags


def test_a_start_picture_is_image_path_frame_strength_and_the_settings_add_their_flags(tmp_path):
    files = files_for(tmp_path)
    config = EngineConfig(quantization="fp8-cast", offload="cpu", extra_args=("--chunked", "--auto-duration", "5", "30"))
    picture = ConditioningImage(path="/data/video/x/start.png", frame_index=0, strength=1.0)
    argv = build_command(("python", "-m", "ltx_pipelines.distilled"), config, files, request(tmp_path / "o.mp4", images=(picture,)))
    assert argv[argv.index("--image"):argv.index("--image") + 4] == ["--image", "/data/video/x/start.png", "0", "1"]
    assert "--quantization" in argv and argv[argv.index("--quantization") + 1] == "fp8-cast"
    assert argv[argv.index("--offload") + 1] == "cpu"
    assert argv[-4:] == ["--chunked", "--auto-duration", "5", "30"]  # what the person added comes last, as given


def test_a_prompt_that_begins_with_a_dash_is_given_in_the_equals_form_so_it_cannot_be_an_option(tmp_path):
    files = files_for(tmp_path)
    argv = build_command(("python",), EngineConfig(), files, request(tmp_path / "o.mp4", prompt="--seed 1 is not what I mean"))
    assert "--prompt=--seed 1 is not what I mean" in argv and "--prompt" not in argv


def test_the_command_comes_from_the_command_then_the_interpreter_then_the_ltx_folder_then_the_images_environment():
    """Protects the order of §46.6 as changed: the most specific wins. The clone shared from the host runs DIRECTLY as `<it>/.venv/bin/python` (never `uv run`, which would try to sync a
    read-only tree), and the image's own environment is the last thing looked for."""
    assert interpreter_command(EngineConfig(command=("uv", "run", "x"), python="/p", ltx_dir="/home/u/LTX-2", libs="/l")) == ("uv", "run", "x")
    assert interpreter_command(EngineConfig(python="/p/python", ltx_dir="/home/u/LTX-2", libs="/l")) == ("/p/python", "-m", "ltx_pipelines.distilled")
    assert interpreter_command(EngineConfig(ltx_dir="/home/u/ltx-experiment/LTX-2", libs="/l")) == ("/home/u/ltx-experiment/LTX-2/.venv/bin/python", "-m", "ltx_pipelines.distilled")
    assert "uv" not in interpreter_command(EngineConfig(ltx_dir="/home/u/LTX-2"))
    assert interpreter_command(EngineConfig(libs="/opt/video-libs")) == ("/opt/video-libs/ltx/bin/python", "-m", "ltx_pipelines.distilled")
    assert interpreter_command(EngineConfig()) == ()


# What the NGC image's own environment looks like for this purpose, and what the Spark's child must not inherit (DESIGN.md §46.6): the image's PyTorch (2.9, CUDA 13.0) must not meet the
# program's (2.13, CUDA 13.2).
NGC = {"PATH": "/usr/local/cuda/bin:/usr/bin", "HOME": "/tmp", "CUDA_VISIBLE_DEVICES": "0", "PYTHONPATH": "/app/backend:/usr/lib/python3/dist-packages", "PYTHONHOME": "/x", "VIRTUAL_ENV": "/v",
       "LD_LIBRARY_PATH": "/usr/local/lib/python3.12/dist-packages/torch/lib:/usr/local/cuda/compat/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64", "HF_HOME": "/models",
       "HF_HUB_OFFLINE": "1"}


def test_the_program_does_not_see_the_studios_python_or_the_images_cuda_libraries(tmp_path):
    env = child_environment(NGC, str(tmp_path / "cache"))
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "LD_LIBRARY_PATH"):
        assert name not in env, name  # ALL of LD_LIBRARY_PATH goes (the driver is found where the nvidia runtime puts it), not only what looks like the image's PyTorch
    assert (env["PATH"], env["HOME"], env["CUDA_VISIBLE_DEVICES"], env["HF_HUB_OFFLINE"]) == (NGC["PATH"], "/tmp", "0", "1")  # what the program needs, and the worker's offline wish, stay


def test_the_program_writes_no_bytecode_into_its_read_only_tree_and_its_output_is_not_buffered():
    env = child_environment({"PATH": "/bin"})
    assert env["PYTHONDONTWRITEBYTECODE"] == "1" and env["PYTHONUNBUFFERED"] == "1"


def test_every_cache_the_program_would_write_is_under_the_cache_folder_which_the_studio_can_write(tmp_path):
    cache = tmp_path / "video-cache"
    env = child_environment({"PATH": "/bin", "HOME": "/nonexistent"}, str(cache))
    expected = {"TRITON_CACHE_DIR": "triton", "TORCHINDUCTOR_CACHE_DIR": "torchinductor", "TORCH_HOME": "torch", "TORCH_EXTENSIONS_DIR": "torch-extensions", "CUDA_CACHE_PATH": "cuda",
                "HF_HOME": "huggingface", "XDG_CACHE_HOME": "xdg"}
    assert {name: env[name] for name in expected} == {name: str(cache / folder) for name, folder in expected.items()}
    assert env["HOME"] == "/nonexistent"  # HOME itself is not touched: the caches are named one by one
    assert child_environment({"PATH": "/bin"}).keys() == {"PATH", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE"}  # no cache folder named: none set


def test_the_persons_own_hf_home_and_xdg_cache_stay_when_they_can_be_written_and_are_ours_when_they_cannot(tmp_path):
    cache = tmp_path / "video-cache"
    mine = tmp_path / "models"
    mine.mkdir()
    kept = child_environment({"HF_HOME": str(mine), "XDG_CACHE_HOME": str(mine)}, str(cache))
    assert kept["HF_HOME"] == str(mine) and kept["XDG_CACHE_HOME"] == str(mine)
    assert kept["TRITON_CACHE_DIR"] == str(cache / "triton")  # the kernel caches are never shared
    a_file = tmp_path / "a-file"
    a_file.write_text("x")  # nothing can be made below a file, whoever asks (root can write anywhere else, so this is the way to a place that cannot be written)
    lost = child_environment({"HF_HOME": str(a_file / "hf"), "XDG_CACHE_HOME": str(a_file / "xdg")}, str(cache))
    assert lost["HF_HOME"] == str(cache / "huggingface") and lost["XDG_CACHE_HOME"] == str(cache / "xdg")
    read_only = tmp_path / "read-only"
    read_only.mkdir()
    read_only.chmod(0o500)
    try:
        if os.geteuid() != 0:  # root can write anywhere: the rule is about whoever the studio runs as
            assert child_environment({"HF_HOME": str(read_only / "hf")}, str(cache))["HF_HOME"] == str(cache / "huggingface")
    finally:
        read_only.chmod(0o700)


def test_the_cache_folders_are_made_before_the_program_starts_and_only_the_ones_under_the_cache(tmp_path):
    cache = tmp_path / "data" / "video-cache"
    mine = tmp_path / "mine"
    mine.mkdir()
    env = child_environment({"HF_HOME": str(mine)}, str(cache))
    make_cache_dirs(env, str(cache))
    assert sorted(p.name for p in cache.iterdir()) == ["cuda", "torch", "torch-extensions", "torchinductor", "triton", "xdg"]  # not huggingface: it is the person's
    assert not (mine / "huggingface").exists()
    make_cache_dirs(env, "")  # no folder named: nothing is made, and nothing fails
    make_cache_dirs({"TRITON_CACHE_DIR": "/proc/forbidden/triton"}, "/proc/forbidden")  # a folder that cannot be made is logged, not raised


# ---------------------------------------------------------------- what a failure says
@pytest.mark.parametrize("lines, code, message, memory", [
    (["INFO:x:fine", "Traceback (most recent call last):", '  File "/a.py", line 3, in <module>', "RuntimeError: shapes do not match"], 1, "RuntimeError: shapes do not match", False),
    (["torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 20.00 GiB"], 1, ltx.OOM_MESSAGE, True),
    (["RuntimeError: CUDA error: out of memory", "CUDA kernel errors might be asynchronously reported"], 1, ltx.OOM_MESSAGE, True),
    (["terminate called after throwing an instance of 'std::bad_alloc'"], -6, ltx.OOM_MESSAGE, True),
    (["INFO:x:loading", " 50%|█████     | 4/8 [00:30<00:30, 7.0s/it]"], -9, ltx.OOM_MESSAGE, True),  # killed with no word: what the system does when memory runs out
    (["INFO:x:loading"], 137, ltx.OOM_MESSAGE, True),
    (["usage: distilled.py [-h]", "distilled.py: error: unrecognized arguments: --bogus"], 2, "distilled.py: error: unrecognized arguments: --bogus", False),
    (["ModuleNotFoundError: No module named 'ltx_core'"], 1, "ModuleNotFoundError: No module named 'ltx_core'", False),
    (["INFO:x:a log line", "something went wrong in a way with no name"], 1, "something went wrong in a way with no name", False),
    ([], 3, "The video program stopped without saying why (exit code 3).", False),
    (["INFO:x:only a log line", " 12%|█▎        | 1/8 [00:14<01:44, 14.90s/it]"], 3, "The video program stopped without saying why (exit code 3).", False),
])
def test_the_one_line_that_says_why_a_program_failed(lines, code, message, memory):
    assert extract_error(lines, code) == (message, memory)


def test_an_out_of_memory_failure_is_the_usual_out_of_memory_error_and_the_rest_carry_the_programs_words():
    assert isinstance(failure_for(["torch.OutOfMemoryError: CUDA out of memory."], 1), OutOfMemory)
    error = failure_for(["RuntimeError: boom"], 1)
    assert type(error) is PipelineError and error.message == "The video program stopped: RuntimeError: boom" and error.hint
    assert "STUDIO_VIDEO_QUANTIZATION" in ltx.OOM_MESSAGE  # the three things a person can do, as the spec words them


def test_a_very_long_line_is_cut_for_the_page():
    message, _ = extract_error(["RuntimeError: " + "x" * 1000], 1)
    assert len(message) == 300 and message.endswith("…")


# ---------------------------------------------------------------- the engine, with the stand-in program
@needs_ffmpeg
def test_a_clip_is_made_by_running_the_program_and_its_progress_is_the_real_stages(tmp_path):
    models = models_folder(tmp_path / "models")
    record = tmp_path / "record.jsonl"
    os.environ["FAKE_LTX_RECORD"] = str(record)
    try:
        events: list[tuple[str, int, int]] = []
        out = tmp_path / "video" / "x" / "engine-out.mp4"
        clip = LtxEngine(program_config(models)).generate(request(out, seed=123), lambda *event: events.append(event), lambda: False)
    finally:
        del os.environ["FAKE_LTX_RECORD"]
    assert clip.path == str(out) and out.is_file()
    stages = [stage for stage, _, _ in events]
    assert stages[0] == "start" and [s for i, s in enumerate(stages) if i == 0 or s != stages[i - 1]] == ["start", "text", "denoise", "upscale", "refine", "decode", "write"]
    assert ("denoise", 8, 8) in events and ("refine", 3, 3) in events
    # what the program was run with: the request's own numbers, and none of the studio's Python
    ran = json.loads(record.read_text().splitlines()[0])
    argv = ran["argv"]
    assert argv[argv.index("--seed") + 1] == "123" and argv[argv.index("--width") + 1] == "256" and argv[argv.index("--num-frames") + 1] == "25"
    assert ran["pythonpath"] is None and ran["unbuffered"] == "1"
    assert ran["pgid"] == ran["pid"]  # its own process group, so that Cancel can end it and anything it started
    facts = media.probe_clip("ffprobe", out)
    assert (facts.width, facts.height, facts.frames, facts.has_audio, facts.audio_channels, facts.audio_rate) == (256, 128, 25, True, 2, 48000)


@needs_ffmpeg
def test_a_start_picture_is_given_to_the_program_as_image_path_frame_strength(tmp_path):
    models = models_folder(tmp_path / "models")
    record = tmp_path / "record.jsonl"
    picture = tmp_path / "start.png"
    picture.write_bytes(b"png")
    os.environ["FAKE_LTX_RECORD"] = str(record)
    try:
        LtxEngine(program_config(models)).generate(request(tmp_path / "v" / "o.mp4", images=(ConditioningImage(str(picture), 0, 1.0),)), lambda *e: None, lambda: False)
    finally:
        del os.environ["FAKE_LTX_RECORD"]
    argv = json.loads(record.read_text().splitlines()[0])["argv"]
    assert argv[argv.index("--image"):argv.index("--image") + 4] == ["--image", str(picture), "0", "1"]


@needs_ffmpeg
@pytest.mark.parametrize("word, kind, says", [
    ("[ltx:error]", PipelineError, "RuntimeError: the fake program was told to fail"),
    ("[ltx:oom]", OutOfMemory, "more memory than was free"),
    ("[ltx:killed]", OutOfMemory, "more memory than was free"),
])
def test_a_program_that_fails_is_a_readable_error_and_leaves_no_clip(tmp_path, word, kind, says):
    models = models_folder(tmp_path / "models")
    out = tmp_path / "v" / "o.mp4"
    with pytest.raises(kind) as caught:
        LtxEngine(program_config(models)).generate(request(out, prompt=f"a fox {word}"), lambda *e: None, lambda: False)
    assert says in caught.value.message and caught.value.hint and not out.exists()
    assert (type(caught.value) is OutOfMemory) == (kind is OutOfMemory)


@needs_ffmpeg
def test_cancel_ends_the_program_and_everything_it_started_within_a_moment(tmp_path):
    models = models_folder(tmp_path / "models")
    record = tmp_path / "record.jsonl"
    os.environ["FAKE_LTX_RECORD"] = str(record)
    stop = threading.Event()
    seen: list[str] = []
    threading.Timer(0.8, stop.set).start()  # pressed while the second pass is not yet reached: the slow program takes ten seconds
    started = time.monotonic()
    try:
        with pytest.raises(Canceled):
            LtxEngine(program_config(models)).generate(request(tmp_path / "v" / "o.mp4", prompt="a fox [ltx:slow]"), lambda stage, *_: seen.append(stage), stop.is_set)
    finally:
        del os.environ["FAKE_LTX_RECORD"]
    assert time.monotonic() - started < 6  # not the ten seconds the program would have taken
    pid = json.loads(record.read_text().splitlines()[0])["pid"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:  # the process is gone (a zombie is gone too: it was waited for)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("the program is still running after Cancel")
    assert "denoise" in seen


@needs_ffmpeg
def test_cancel_raised_by_the_progress_callback_stops_the_program_too(tmp_path):
    """The worker's own callback raises Canceled between two reports; the engine must end the program then as well."""
    models = models_folder(tmp_path / "models")

    def callback(stage: str, step: int, steps: int) -> None:
        if stage == "denoise" and step >= 2:
            raise Canceled()

    started = time.monotonic()
    with pytest.raises(Canceled):
        LtxEngine(program_config(models)).generate(request(tmp_path / "v" / "o.mp4", prompt="a fox [ltx:slow]"), callback, lambda: False)
    assert time.monotonic() - started < 6


@needs_ffmpeg
def test_a_clip_that_takes_longer_than_the_limit_is_stopped_with_the_setting_named(tmp_path, monkeypatch):
    monkeypatch.setattr(LtxEngine, "SECONDS_PER_MINUTE", 0.5)  # one "minute" is half a second here
    models = models_folder(tmp_path / "models")
    with pytest.raises(PipelineError) as caught:
        LtxEngine(program_config(models, timeout_min=1)).generate(request(tmp_path / "v" / "o.mp4", prompt="a fox [ltx:slow]"), lambda *e: None, lambda: False)
    assert "STUDIO_VIDEO_TIMEOUT_MIN" in caught.value.message and "1 minutes" in caught.value.message


@needs_ffmpeg
def test_a_program_that_ends_well_but_writes_no_clip_or_a_wrong_one_is_an_error_and_not_a_clip(tmp_path):
    models = models_folder(tmp_path / "models")
    with pytest.raises(PipelineError, match="wrote no clip"):
        LtxEngine(program_config(models)).generate(request(tmp_path / "a" / "o.mp4", prompt="a fox [ltx:nofile]"), lambda *e: None, lambda: False)
    with pytest.raises(PipelineError, match="clip of 0.4 seconds; about 1.0 were asked for"):
        LtxEngine(program_config(models)).generate(request(tmp_path / "b" / "o.mp4", prompt="a fox [ltx:short]"), lambda *e: None, lambda: False)
    # (a clip of the wrong size is the same check, in media.check_output, tested with the facts it takes)


@needs_ffmpeg
def test_a_clip_with_no_sound_is_returned_and_left_to_the_server_to_note(tmp_path):
    models = models_folder(tmp_path / "models")
    out = tmp_path / "v" / "o.mp4"
    clip = LtxEngine(program_config(models)).generate(request(out, prompt="a fox [ltx:silent]"), lambda *e: None, lambda: False)
    assert Path(clip.path) == out and not media.probe_clip("ffprobe", out).has_audio


def test_a_program_that_cannot_be_started_is_unavailable_with_its_name(tmp_path):
    models = models_folder(tmp_path / "models")
    with pytest.raises(PipelineUnavailable, match="could not be started"):
        LtxEngine(program_config(models, command=(str(tmp_path / "no-such-program"),))).generate(request(tmp_path / "o.mp4"), lambda *e: None, lambda: False)


def test_no_program_set_up_and_files_missing_are_unavailable_with_the_reason(tmp_path):
    with pytest.raises(PipelineUnavailable, match="No video program is set up"):
        LtxEngine(EngineConfig(models_dir=str(models_folder(tmp_path)))).generate(request(tmp_path / "o.mp4"), lambda *e: None, lambda: False)
    with pytest.raises(PipelineUnavailable) as caught:
        LtxEngine(program_config(tmp_path / "empty")).generate(request(tmp_path / "o.mp4"), lambda *e: None, lambda: False)
    assert str(tmp_path / "empty" / "diffusion_models") in caught.value.message


# ---------------------------------------------------------------- the check at start-up
@needs_ffmpeg
def test_the_start_up_check_names_the_first_thing_that_is_wrong_in_the_order_a_person_would_fix_it(tmp_path, monkeypatch):
    models = models_folder(tmp_path / "models")
    # 1. no program at all
    with pytest.raises(PipelineUnavailable) as caught:
        check_ready(EngineConfig(models_dir=str(models)), inspect=False)
    assert "not set up" in caught.value.message and all(word in (caught.value.hint or "") for word in ("STUDIO_VIDEO_LTX_DIR", "STUDIO_VIDEO_MODELS_DIR", "VIDEO_LTX=1", "STUDIO_VIDEO_COMMAND"))
    # 2. a model folder that is not there says so once, with its path and the setting; one that is there but lacks files names each file's folder (the program is not looked at
    #    before the files are: it takes a minute)
    with pytest.raises(PipelineUnavailable) as caught:
        check_ready(program_config(tmp_path / "none"), inspect=False)
    assert f"The folder of model files is not there: {tmp_path / 'none'}" in caught.value.message and "STUDIO_VIDEO_MODELS_DIR" in (caught.value.hint or "")
    (tmp_path / "empty").mkdir()
    with pytest.raises(PipelineUnavailable) as caught:
        check_ready(program_config(tmp_path / "empty"), inspect=False)
    assert str(tmp_path / "empty" / "diffusion_models") in caught.value.message
    # 3. a program that is not there
    with pytest.raises(PipelineUnavailable) as caught:
        check_ready(program_config(models, command=("/nowhere/python", "-m", "ltx_pipelines.distilled")), inspect=True)
    assert "is not there or cannot be run: /nowhere/python" in caught.value.message
    with pytest.raises(PipelineUnavailable) as caught:  # a bare name is looked for on the PATH
        check_ready(program_config(models, command=("no-such-python-anywhere", "-m", "ltx_pipelines.distilled")), inspect=True)
    assert "was not found: no-such-python-anywhere" in caught.value.message
    # 4. ffmpeg missing comes first of all
    monkeypatch.setattr(media, "find_tools", lambda *a: media.Tools(ffmpeg=False, ffprobe=True))
    with pytest.raises(PipelineUnavailable, match="ffmpeg is not installed"):
        check_ready(program_config(models), inspect=False)


def test_an_environment_that_cannot_run_the_program_says_why_in_words(monkeypatch):
    """The interpreter the tests run in has no PyTorch and no LTX, and is not 3.12 here: each way an environment can be wrong is told in its own words. The Python rule is moved by hand
    so that this holds on whichever Python the tests run in."""
    command = (sys.executable, "-m", "ltx_pipelines.distilled")
    monkeypatch.setattr(ltx, "MIN_PYTHON", (99, 0))  # whatever this Python is, it is too old
    too_old = inspect_environment(command)
    assert too_old.problem is not None and f"Python is {sys.version_info[0]}.{sys.version_info[1]}" in too_old.problem and "needs 99.0 or newer" in too_old.problem and "uv sync" in (too_old.hint or "")
    monkeypatch.setattr(ltx, "MIN_PYTHON", (3, 0))
    no_torch = inspect_environment(command)  # then the next thing: this interpreter has no PyTorch (and so cannot say whether it sees a GPU)
    assert no_torch.problem is not None and "PyTorch does not import" in no_torch.problem and no_torch.python is not None and no_torch.python[:2] == sys.version_info[:2]
    assert no_torch.hint and no_torch.summary().startswith("command ")


def test_a_command_that_is_not_an_interpreter_is_asked_for_help_and_a_failure_is_its_own_words(tmp_path):
    good = tmp_path / "uvlike"
    good.write_text('#!/bin/sh\n[ "$1" = "--help" ] && exit 0\nexit 1\n')
    bad = tmp_path / "broken"
    bad.write_text("#!/bin/sh\necho \"ModuleNotFoundError: No module named 'ltx_pipelines'\" >&2\nexit 1\n")
    for script in (good, bad):
        script.chmod(0o755)
    assert inspect_environment((str(good),)).problem is None
    broken = inspect_environment((str(bad),))
    assert broken.problem is not None and "No module named 'ltx_pipelines'" in broken.problem
    assert inspect_environment(()).problem and "VIDEO_LTX" in (inspect_environment(()).hint or "")
    assert "is not there or cannot be run" in (inspect_environment((str(tmp_path / "missing"),)).problem or "")


def test_the_estimate_table_is_the_measured_one():
    estimate = ltx.INFO.estimate
    assert estimate.kind == "measured" and estimate.reference_pixels == 1280 * 704
    assert estimate.points == ((0.0, 45.0), (5.0, 154.0), (10.0, 293.0), (20.0, 604.0), (30.0, 1036.0))  # the Spark's own: 154 s, 293 s, 604 s and 1,036 s for 5, 10, 20 and 30 s
    assert ltx.INFO.size_multiple == 64 and ltx.INFO.fps_choices == (24,) and ltx.INFO.memory_gb >= 55.6  # a 30 s clip peaked at 56,973 MiB of the machine's memory
