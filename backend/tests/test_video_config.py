"""The Video tab's settings and the files that carry them into the container (DESIGN.md §46.6, §46.12): the `STUDIO_VIDEO_*` settings (their defaults, their words, what each refuses by
name), the way they reach the video worker, and compose.yaml, .env.example and the Dockerfile that must agree with the code. Nothing here builds an image (that is done on the Spark,
and is NOT tried by these tests); what is checked is that the files agree with the code and with each other, which is what goes wrong first: a setting the code reads that compose does
not pass (switched on in `.env` and never arriving, silently), a default written twice that drifts, the model folder not mounted read-only, and the Dockerfile's step that builds the
LTX environment: its shell is run here against stand-ins for `pip`, `git` and `uv`, so that the branches (off, no commit named, built, failed) are each seen to do what the comments say.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from video_support import models_folder

from studio.config import ConfigError, Settings
from studio.video.engine import EngineConfig
from studio.video.engines.ltx import MEASURED_ON_THE_SPARK

ROOT = Path(__file__).resolve().parents[2]


def repo_file(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def video_names_in_code() -> set[str]:
    """Every STUDIO_VIDEO_* name config.py reads by its literal name."""
    source = (Path(__file__).resolve().parents[1] / "studio" / "config.py").read_text(encoding="utf-8")
    return set(re.findall(r'"(STUDIO_VIDEO_[A-Z0-9_]+)"', source))


IMAGE_SETS = {"STUDIO_VIDEO_LIBS"}  # the Dockerfile sets it (ENV): a person has no reason to
# Where compose's default is deliberately not the code's: the memory check is on at the figure measured on the Spark (the code's own default is the engine's estimate for the real
# engine and nothing for the fake one, which a container does not use). The two folders are NOT here: unset, both are empty in compose as in the code.
DELIBERATE = {"STUDIO_VIDEO_MIN_FREE_GB": "60"}


# ---------------------------------------------------------------- the settings themselves
def test_the_scan_finds_the_settings_it_should():
    names = video_names_in_code()
    assert {"STUDIO_VIDEO_LTX_DIR", "STUDIO_VIDEO_MODELS_DIR", "STUDIO_VIDEO_COMMAND", "STUDIO_VIDEO_PYTHON", "STUDIO_VIDEO_TRANSFORMER", "STUDIO_VIDEO_MIN_FREE_GB", "STUDIO_VIDEO_MAX_SECONDS", "STUDIO_VIDEO_LIBS"} <= names
    assert len(names) >= 18


def test_the_defaults_are_the_ones_measured_and_nothing_is_set_up_unasked():
    s = Settings.from_env({})
    assert s.video_ltx_dir is None and s.video_models_dir is None and s.video_command == () and s.video_python is None and s.video_libs is None and s.video_extra_args == ()
    assert (s.video_transformer, s.video_text_encoder, s.video_video_vae, s.video_audio_vae, s.video_upsampler) == ("", "", "", "", "")
    assert (s.video_quantization, s.video_offload, s.video_timeout_min, s.video_max_seconds) == ("none", "none", 0, 30)
    assert s.video_min_free_gb is None and s.video_min_free_disk_gb == 5.0 and (s.video_ffmpeg, s.video_ffprobe) == ("ffmpeg", "ffprobe")


def test_blank_values_mean_the_default_as_in_a_dotenv_file():
    # `NAME=` in a .env file means "the default", like every other setting (but the names of the two programs, which every STUDIO_*_FFMPEG refuses to have empty: they are shown with their value)
    blank = {name: "" for name in video_names_in_code() - {"STUDIO_VIDEO_FFMPEG", "STUDIO_VIDEO_FFPROBE"}}
    assert Settings.from_env(blank) == Settings.from_env({})
    with pytest.raises(ConfigError, match="STUDIO_VIDEO_FFMPEG"):
        Settings.from_env({"STUDIO_VIDEO_FFMPEG": ""})


def test_the_command_is_read_as_a_command_line_with_quotes_and_the_models_folder_as_a_path(tmp_path):
    s = Settings.from_env({"STUDIO_VIDEO_COMMAND": "'/opt/my env/bin/python' -m ltx_pipelines.distilled", "STUDIO_VIDEO_MODELS_DIR": f" {tmp_path} ", "STUDIO_VIDEO_PYTHON": "/x/python",
                           "STUDIO_VIDEO_EXTRA_ARGS": "--chunked --note 'two words'"})
    assert s.video_command == ("/opt/my env/bin/python", "-m", "ltx_pipelines.distilled") and s.video_models_dir == tmp_path and s.video_python == Path("/x/python")
    assert s.video_extra_args == ("--chunked", "--note", "two words")
    assert Settings.from_env({"STUDIO_VIDEO_MODELS_DIR": "~/ltx-experiment/models"}).video_models_dir == Path("~/ltx-experiment/models").expanduser()  # the way a person writes it
    assert Settings.from_env({"STUDIO_VIDEO_LTX_DIR": " /home/YOU/ltx-experiment/LTX-2 "}).video_ltx_dir == Path("/home/YOU/ltx-experiment/LTX-2")


@pytest.mark.parametrize("name, value", [
    ("STUDIO_VIDEO_QUANTIZATION", "int3"), ("STUDIO_VIDEO_OFFLOAD", "disk"), ("STUDIO_VIDEO_COMMAND", "python 'unclosed"), ("STUDIO_VIDEO_EXTRA_ARGS", "--a 'unclosed"),
    ("STUDIO_VIDEO_MAX_SECONDS", "0"), ("STUDIO_VIDEO_MAX_SECONDS", "9999"), ("STUDIO_VIDEO_MAX_SECONDS", "ten"), ("STUDIO_VIDEO_MIN_FREE_GB", "-1"), ("STUDIO_VIDEO_MIN_FREE_GB", "lots"),
    ("STUDIO_VIDEO_TIMEOUT_MIN", "-5"), ("STUDIO_VIDEO_MIN_FREE_DISK_GB", "-1")])
def test_a_setting_that_cannot_be_used_is_refused_by_name(name, value):
    with pytest.raises(ConfigError, match=name):
        Settings.from_env({name: value})


def test_the_quantization_and_offload_words_are_the_programs_own_and_are_not_case_sensitive():
    assert Settings.from_env({"STUDIO_VIDEO_QUANTIZATION": " FP8-Cast ", "STUDIO_VIDEO_OFFLOAD": "CPU"}).video_quantization == "fp8-cast"
    assert Settings.from_env({"STUDIO_VIDEO_QUANTIZATION": "nvfp4-prequant", "STUDIO_VIDEO_OFFLOAD": "cpu"}).video_offload == "cpu"


def test_the_memory_check_is_none_unless_a_number_is_given_and_0_is_a_number():
    assert Settings.from_env({}).video_min_free_gb is None
    assert Settings.from_env({"STUDIO_VIDEO_MIN_FREE_GB": "0"}).video_min_free_gb == 0.0  # off, as the setting's own comment says
    assert Settings.from_env({"STUDIO_VIDEO_MIN_FREE_GB": "60"}).video_min_free_gb == 60.0


def test_what_the_worker_is_told_is_plain_json_that_the_engine_reads_back_the_same(tmp_path):
    s = Settings.from_env({"STUDIO_VIDEO_MODELS_DIR": str(tmp_path), "STUDIO_VIDEO_LTX_DIR": "/home/YOU/ltx-experiment/LTX-2", "STUDIO_DATA_DIR": str(tmp_path / "data"),
                           "STUDIO_VIDEO_COMMAND": "/e/python -m ltx_pipelines.distilled", "STUDIO_VIDEO_TRANSFORMER": "t.safetensors",
                           "STUDIO_VIDEO_QUANTIZATION": "fp8-cast", "STUDIO_VIDEO_OFFLOAD": "cpu", "STUDIO_VIDEO_TIMEOUT_MIN": "25", "STUDIO_VIDEO_EXTRA_ARGS": "--chunked",
                           "STUDIO_VIDEO_LIBS": "/opt/video-libs", "STUDIO_VIDEO_FFMPEG": "/bin/ffmpeg"})
    sent = json.loads(json.dumps(s.video_engine_config()))  # it travels on a command line as JSON (`--engine-config`)
    config = EngineConfig.from_dict(sent)
    assert config.models_dir == str(tmp_path) and config.command == ("/e/python", "-m", "ltx_pipelines.distilled") and config.files["transformer"] == "t.safetensors"
    assert (config.quantization, config.offload, config.timeout_min, config.extra_args, config.libs, config.ffmpeg) == ("fp8-cast", "cpu", 25, ("--chunked",), "/opt/video-libs", "/bin/ffmpeg")
    assert set(config.files) == {"transformer", "text_encoder", "video_vae", "audio_vae", "upsampler"}
    assert config.ltx_dir == "/home/YOU/ltx-experiment/LTX-2" and config.cache_dir == str(tmp_path / "data" / "video-cache")  # the caches go under the data folder, which is the one place that is written


# ---------------------------------------------------------------- compose.yaml and .env.example
def test_every_video_setting_the_code_reads_is_in_compose_and_in_the_example_file():
    compose, example = repo_file("compose.yaml"), repo_file(".env.example")
    for name in sorted(video_names_in_code() - IMAGE_SETS):
        assert f"{name}:" in compose, f"{name} is read by the code but compose.yaml does not pass it on"
        assert f"\n{name}=" in example, f"{name} is read by the code but .env.example does not show it"


def test_compose_does_not_pass_what_the_code_does_not_read():
    """The other direction: a setting in compose that nothing reads does nothing, and a person would change it and see no effect."""
    passed = set(re.findall(r"^\s+(STUDIO_VIDEO_[A-Z0-9_]+):", repo_file("compose.yaml"), flags=re.M))
    assert passed == video_names_in_code() - IMAGE_SETS


def test_the_values_compose_passes_when_nothing_is_set_are_the_codes_own_defaults_but_for_the_two_that_differ_on_purpose():
    passed = dict(re.findall(r"^\s+(STUDIO_VIDEO_[A-Z0-9_]+): \$\{[A-Z0-9_]+:-([^}]*)\}$", repo_file("compose.yaml"), flags=re.M))
    assert set(passed) == video_names_in_code() - IMAGE_SETS
    assert {name: passed[name] for name in DELIBERATE} == DELIBERATE
    from_compose, from_nothing = Settings.from_env({k: v for k, v in passed.items() if k not in DELIBERATE}), Settings.from_env({})
    for field in (f for f in Settings.__dataclass_fields__ if f.startswith("video_")):
        assert getattr(from_compose, field) == getattr(from_nothing, field), f"compose passes a different default for {field}"  # one set of defaults, the code's
    assert Settings.from_env(passed).video_min_free_gb == 60.0
    assert passed["STUDIO_VIDEO_LTX_DIR"] == "" and passed["STUDIO_VIDEO_MODELS_DIR"] == ""  # unset, the container is told nothing, and the tab says what to set


def test_the_example_files_values_are_the_defaults_too_but_for_the_same_two():
    shown = dict(re.findall(r"^(STUDIO_VIDEO_[A-Z0-9_]+)=(.*)$", repo_file(".env.example"), flags=re.M))
    assert set(shown) == video_names_in_code() - IMAGE_SETS
    assert {name: shown[name] for name in DELIBERATE} == DELIBERATE
    parsed, defaults = Settings.from_env({k: v for k, v in shown.items() if k not in DELIBERATE}), Settings.from_env({})
    for field in (f for f in Settings.__dataclass_fields__ if f.startswith("video_")):
        assert getattr(parsed, field) == getattr(defaults, field), f".env.example shows a value for {field} that is not the default"


def test_both_folders_are_shared_read_only_at_the_same_path_as_on_the_host():
    """Protects the choices that nothing is downloaded, nothing of the person's is changed, and the LTX-2 clone's editable installs (which record absolute host paths under it) still point
    at things that exist: each of the two folders is bind-mounted `:ro` at the SAME path inside the container, named by the very setting the studio is told (DESIGN.md §46.6, as changed)."""
    compose = repo_file("compose.yaml")
    for name, unset_on_host, unset_in_container in (("STUDIO_VIDEO_LTX_DIR", "./data/video-env", "/opt/video-ltx-unset"), ("STUDIO_VIDEO_MODELS_DIR", "./data/video-models", "/opt/video-models-unset")):
        mounts = re.findall(rf"^\s+- \$\{{{name}:-([^}}]*)\}}:\$\{{{name}:-([^}}]*)\}}(:\S+)?$", compose, flags=re.M)
        assert len(mounts) == 1, f"compose.yaml must mount {name} once, at the same path as `${{{name}:-<host default>}}:${{{name}:-<container default>}}:ro`"
        host_default, container_default, mode = mounts[0]
        assert mode == ":ro", f"{name} must be shared read-only"
        # unset: harmless folders, so that docker compose works for someone who has not set it, and the container is told nothing about them
        assert (host_default, container_default) == (unset_on_host, unset_in_container) and container_default.startswith("/") and not host_default.startswith("/")
        assert re.search(rf"^\s+{name}: \$\{{{name}:-\}}$", compose, flags=re.M)
    assert "VIDEO_MODELS_HOST_DIR" not in compose  # the one setting names the folder on the host and in the container: there is no second name to forget


def test_the_example_file_gives_the_exact_two_settings_for_the_spark_and_leaves_them_empty():
    example = repo_file(".env.example")
    assert re.search(r"^#\s+STUDIO_VIDEO_LTX_DIR=/home/YOU/ltx-experiment/LTX-2\s", example, flags=re.M)
    assert re.search(r"^#\s+STUDIO_VIDEO_MODELS_DIR=/home/YOU/ltx-experiment/models\s", example, flags=re.M)
    assert re.search(r"^STUDIO_VIDEO_LTX_DIR=$", example, flags=re.M) and re.search(r"^STUDIO_VIDEO_MODELS_DIR=$", example, flags=re.M)  # a person fills them in; no default guesses a user's name
    assert "docker compose up -d --build" in example and "STUDIO_UID:STUDIO_GID" in example


def test_the_command_that_beats_the_folder_is_written_down_in_the_example_file():
    """STUDIO_VIDEO_COMMAND and STUDIO_VIDEO_PYTHON each beat STUDIO_VIDEO_LTX_DIR (DESIGN.md §46.6), and the example says the command is run as it is, never through uv run."""
    example = repo_file(".env.example")
    assert re.search(r"^#\s+STUDIO_VIDEO_COMMAND=\S+/ltx-experiment/LTX-2/\.venv/bin/python -m ltx_pipelines\.distilled$", example, flags=re.M)
    assert "never through uv run" in example
    assert Settings.from_env({"STUDIO_VIDEO_COMMAND": "/home/YOU/ltx-experiment/LTX-2/.venv/bin/python -m ltx_pipelines.distilled"}).video_command[-2:] == ("-m", "ltx_pipelines.distilled")


def test_the_build_arguments_compose_passes_are_the_ones_the_dockerfile_declares_and_the_ltx_build_is_off_unless_asked_for():
    compose, docker, example = repo_file("compose.yaml"), repo_file("Dockerfile"), repo_file(".env.example")
    args = dict(re.findall(r"^\s+((?:VIDEO_LTX|LTX_[A-Z_]+)): \$\{[A-Z_]+:-([^}]*)\}$", compose, flags=re.M))
    assert set(args) == {"VIDEO_LTX", "LTX_COMMIT", "LTX_PYTHON", "LTX_REPO", "LTX_UV_SYNC_ARGS"}
    for name in args:
        assert re.search(rf"^ARG {name}=", docker, flags=re.M), f"compose passes {name} but the Dockerfile has no ARG for it"
    # off unless asked for; and the commit is the one that was measured working on the Spark, the same in the Dockerfile, compose and the example file and the code that says so
    measured = MEASURED_ON_THE_SPARK["ltx_commit"]
    assert args["VIDEO_LTX"] == "0" and args["LTX_COMMIT"] == measured and args["LTX_UV_SYNC_ARGS"] == ""
    assert re.search(rf"^ARG LTX_COMMIT={measured}$", docker, flags=re.M) and re.search(r"^ARG VIDEO_LTX=0$", docker, flags=re.M)
    assert "\nVIDEO_LTX=0" in example and f"\nLTX_COMMIT={measured}\n" in example


# ---------------------------------------------------------------- the Dockerfile's step, run against stand-ins
def ltx_step(tmp_path: Path) -> str:
    """The Dockerfile's RUN that builds the LTX environment, as the shell command the image builder runs, with the folders it writes to moved under `tmp_path`."""
    docker = repo_file("Dockerfile")
    block = re.search(r"^RUN mkdir -p /opt/video-libs && .*?(?=^ENV STUDIO_VIDEO_LIBS)", docker, flags=re.M | re.S)
    assert block, "the Dockerfile has no step that builds the LTX environment"
    command = block.group(0)[len("RUN "):]
    command = command.replace("\\\n", " ")  # the builder joins a line that ends in a backslash with the next
    return command.replace("/opt/video-libs", str(tmp_path / "video-libs")).replace("/tmp/uv-cache", str(tmp_path / "uv-cache"))


def stand_ins(tmp_path: Path, failing: str = "") -> tuple[Path, Path]:
    """Folders with stand-ins for `pip`, `git` and `uv` that write down what they were called with (and the environment `uv` saw), and fail if told to. Returns (bin folder, log file)."""
    bin_dir, log = tmp_path / "bin", tmp_path / "calls.log"
    bin_dir.mkdir()
    for name in ("pip", "git", "uv"):
        script = bin_dir / name
        script.write_text(
            "#!/bin/sh\n"
            f'echo "{name} $@ | PWD=$PWD UV_PROJECT_ENVIRONMENT=$UV_PROJECT_ENVIRONMENT UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR" >> "{log}"\n'
            + (f'[ "{name}" = "{failing}" ] && exit 1\n' if failing else "")
            # a clone is a folder, with a lock file when the test says the clone has one (uv.lock is what makes the sync use the measured versions as they are)
            + ('if [ "$1" = "clone" ]; then mkdir -p "$3"; [ "$STAND_IN_LOCK" = "1" ] && touch "$3/uv.lock"; fi\n' if name == "git" else "")
            + "exit 0\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return bin_dir, log


def run_step(tmp_path: Path, bin_dir: Path, **build_args: str) -> subprocess.CompletedProcess:
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "VIDEO_LTX": "0", "LTX_REPO": "https://example.org/LTX-2.git", "LTX_COMMIT": "", "LTX_PYTHON": "3.12", "LTX_UV_SYNC_ARGS": "", **build_args}
    return subprocess.run(["/bin/sh", "-c", ltx_step(tmp_path)], capture_output=True, text=True, env=env, cwd=tmp_path)


def test_the_ltx_step_is_valid_shell_and_does_nothing_but_say_so_when_it_is_not_asked_for(tmp_path):
    bin_dir, log = stand_ins(tmp_path)
    assert subprocess.run(["/bin/sh", "-n", "-c", ltx_step(tmp_path)]).returncode == 0
    done = run_step(tmp_path, bin_dir)
    assert done.returncode == 0 and "NOTE: the LTX program is not built into this image" in done.stdout and "STUDIO_VIDEO_COMMAND" in done.stdout and "STUDIO_VIDEO_LTX_DIR" in done.stdout
    assert not log.exists(), "nothing is installed or downloaded unless VIDEO_LTX=1"
    assert (tmp_path / "video-libs").is_dir()  # the folder is made either way, so that the setting can point at it and the check can look


def test_asking_for_the_ltx_build_with_an_empty_commit_stops_the_build_with_a_message_that_says_what_to_do(tmp_path):
    """Protects the rule that the environment is made from ONE commit seen to work, never from whatever is newest (DESIGN.md §46.6): the Dockerfile's default is the measured commit, and
    a build that names an EMPTY one is a failed build, in words."""
    bin_dir, log = stand_ins(tmp_path)
    done = run_step(tmp_path, bin_dir, VIDEO_LTX="1", LTX_COMMIT="")
    assert done.returncode == 1 and "VIDEO_LTX=1 needs LTX_COMMIT" in done.stderr and "git -C ~/ltx-experiment/LTX-2 rev-parse HEAD" in done.stderr and "https://example.org/LTX-2.git" in done.stderr
    assert not log.exists()


def test_the_ltx_environment_is_made_by_uv_from_the_named_commit_in_a_place_of_its_own_under_nvidias_pins(tmp_path):
    bin_dir, log = stand_ins(tmp_path)
    done = run_step(tmp_path, bin_dir, VIDEO_LTX="1", LTX_COMMIT="abc1234def")
    assert done.returncode == 0, done.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    libs = tmp_path / "video-libs"
    assert calls[0].startswith("pip install -c /app/ngc-pins.txt uv ")  # the only thing installed beside NVIDIA's builds is uv, under their pins
    assert calls[1].startswith(f"git clone https://example.org/LTX-2.git {libs}/ltx-src")
    assert calls[2].startswith(f"git -C {libs}/ltx-src checkout --detach abc1234def")
    assert calls[3].startswith("uv sync --python 3.12 | ") and f"PWD={libs}/ltx-src" in calls[3]  # run inside the checkout; no uv.lock in this clone: uv resolves
    assert f"UV_PROJECT_ENVIRONMENT={libs}/ltx" in calls[3] and f"UV_PYTHON_INSTALL_DIR={libs}/python" in calls[3]  # the environment and its Python are under /opt/video-libs, not in NVIDIA's
    assert len(calls) == 4 and "NOTE" not in done.stdout


def test_a_clone_with_a_lock_file_is_synced_from_it_as_it_is_and_extra_arguments_come_after(tmp_path):
    """With a uv.lock the libraries are the ones that were measured, so the sync is --frozen; STUDIO's LTX_UV_SYNC_ARGS adds more."""
    bin_dir, log = stand_ins(tmp_path)
    done = run_step(tmp_path, bin_dir, VIDEO_LTX="1", LTX_COMMIT="abc1234def", LTX_UV_SYNC_ARGS="--extra x", STAND_IN_LOCK="1")
    assert done.returncode == 0, done.stderr
    assert log.read_text(encoding="utf-8").splitlines()[3].startswith("uv sync --frozen --extra x --python 3.12 | ")


def test_the_dockerfiles_default_commit_is_the_measured_one_and_the_step_says_what_it_adds_and_what_is_not_tried():
    docker = repo_file("Dockerfile")
    assert f"ARG LTX_COMMIT={MEASURED_ON_THE_SPARK['ltx_commit']}\n" in docker
    for words in ("THIS IMAGE'S PYTORCH IS NOT THAT ONE", "torch 2.9.0a0 for CUDA 13.0", "torch 2.13.0+cu132", "several GB", "NOT TRIED", "STUDIO_VIDEO_LTX_DIR", "/usr/bin/python3"):
        assert words in docker, words


def test_a_build_of_the_ltx_environment_that_fails_is_a_note_and_not_a_failed_image(tmp_path):
    """No network or a resolve that fails must not stop the studio from being built: the Video tab says the program is not installed (DESIGN.md §46.6)."""
    for failing in ("pip", "git", "uv"):
        sandbox = tmp_path / failing
        sandbox.mkdir()
        bin_dir, _ = stand_ins(sandbox, failing=failing)
        done = run_step(sandbox, bin_dir, VIDEO_LTX="1", LTX_COMMIT="abc1234def")
        assert done.returncode == 0 and "NOTE: the LTX environment could not be built" in done.stdout, failing


def test_the_ltx_step_comes_after_the_pins_exist_and_before_the_build_check_runs():
    docker = repo_file("Dockerfile")
    assert docker.index("ngc_pins.py") < docker.index("ARG VIDEO_LTX=0") < docker.index("python /app/docker/check_image.py")
    assert "ENV STUDIO_VIDEO_LIBS=/opt/video-libs" in docker


# ---------------------------------------------------------------- the build-time check
@pytest.fixture(scope="module")
def check_image():
    spec = importlib.util.spec_from_file_location("check_image_for_video_tests", ROOT / "docker" / "check_image.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_image_for_video_tests"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clean_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith("STUDIO_VIDEO_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("STUDIO_VIDEO_LIBS", "")  # the image sets it; a test says what it wants
    return monkeypatch


def test_the_build_check_says_first_what_was_measured_working_and_that_the_images_pytorch_is_not_it(check_image, clean_env):
    notes = check_image.video_notes()
    commit = MEASURED_ON_THE_SPARK["ltx_commit"]
    assert notes[0].startswith("Video: measured working on the Spark (2026-11-19/20): LTX-2 commit daa6b16 ")
    assert "Python 3.12.3" in notes[0] and "torch 2.13.0+cu132 (CUDA 13.2)" in notes[0] and "transformers 5.14.1" in notes[0] and "triton 3.7.1" in notes[0] and commit[:7] in notes[0]
    assert "this image's own PyTorch is 2.9.0a0+145a3a7bda.nv25.10 (CUDA 13.0)" in notes[1] and "cannot use" in notes[1]
    assert all(n.startswith("Video: ") for n in notes)


def test_the_build_check_looks_at_the_python_a_shared_environment_links_to(check_image, clean_env):
    notes = check_image.video_notes()
    system = next(n for n in notes if "/usr/bin/python3" in n)
    assert "is Python 3." in system or "is not in this image" in system  # whichever this machine has: one line either way, never a failure
    assert "(as measured" in system or "the measured one is 3.12.3" in system or "is not in this image" in system


def test_with_nothing_set_up_the_build_check_says_so_in_one_line_after_the_facts(check_image, clean_env):
    notes = check_image.video_notes()
    assert notes[-1] == ("Video: no program is set up in this build (STUDIO_VIDEO_LTX_DIR is empty and the LTX environment is not built in: build with VIDEO_LTX=1, or share your clone "
                         "with STUDIO_VIDEO_LTX_DIR); the Video tab will say so")


def test_a_program_that_cannot_start_and_model_files_that_are_not_there_are_notes_with_their_reasons(check_image, clean_env, tmp_path):
    clean_env.setenv("STUDIO_VIDEO_COMMAND", f"{tmp_path}/no/such/python -m ltx_pipelines.distilled")
    clean_env.setenv("STUDIO_VIDEO_MODELS_DIR", str(tmp_path / "empty"))
    notes = check_image.video_notes()
    assert all(n.startswith("Video: ") for n in notes)
    assert "not available here" in notes[-2] and "no/such/python" in notes[-2]
    assert "model files:" in notes[-1] and "5 of 5 not found" in notes[-1] and "not there" in notes[-1]


def test_model_files_that_are_all_there_are_said_to_be_found(check_image, clean_env, tmp_path):
    clean_env.setenv("STUDIO_VIDEO_COMMAND", f"{sys.executable} -m ltx_pipelines.distilled")
    clean_env.setenv("STUDIO_VIDEO_MODELS_DIR", str(models_folder(tmp_path / "models")))
    notes = check_image.video_notes()
    assert notes[-2].startswith("Video: ")  # whichever it finds of this Python (it has no LTX): a line either way
    assert notes[-1] == f"Video: all five model files were found in {tmp_path / 'models'}"


def test_a_clone_that_works_is_said_to_start_with_what_differs_from_the_measured_one(check_image, clean_env, tmp_path, monkeypatch):
    """The stand-in clone has the measured torch and none of the other libraries' metadata, so the line says it can be started and lists what is not as measured."""
    from video_support import ltx_clone

    monkeypatch.setattr("studio.video.engines.ltx.MIN_PYTHON", (3, 0))
    clean_env.setenv("STUDIO_VIDEO_LTX_DIR", str(ltx_clone(tmp_path / "LTX-2")))
    clean_env.setenv("STUDIO_VIDEO_MODELS_DIR", str(models_folder(tmp_path / "models")))
    clean_env.setenv("STUDIO_DATA_DIR", str(tmp_path / "data"))
    notes = check_image.video_notes()
    started = next(n for n in notes if n.startswith("Video: the LTX program can be started"))
    assert "torch 2.13.0+cu132 (CUDA 13.2, GPU NVIDIA GB10 (stand-in))" in started and "differs from the measured one in:" in started and "natten does not import here" in started


def test_the_build_check_never_fails_whatever_goes_wrong_looking(check_image, clean_env, monkeypatch):
    """Protects the promise that the `Video:` lines are notes only: even a settings error or a crash inside the check is one line and not an exception (the build must not fail)."""
    clean_env.setenv("STUDIO_VIDEO_QUANTIZATION", "int3")  # a settings error
    notes = check_image.video_notes()
    assert notes[-1].startswith("Video: could not find out whether the LTX program can run (ConfigError")
    clean_env.delenv("STUDIO_VIDEO_QUANTIZATION")
    monkeypatch.setattr("studio.video.engines.ltx.inspect_environment", lambda command, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    clean_env.setenv("STUDIO_VIDEO_COMMAND", "/x/python -m ltx_pipelines.distilled")
    assert check_image.video_notes()[-1] == "Video: could not find out whether the LTX program can run (RuntimeError: boom)"
