"""The first way to run the video program: the person's own LTX-2 clone, shared from the host (DESIGN.md §46.6, as changed; STUDIO_VIDEO_LTX_DIR).

The clone was made on the Spark, with its virtual environment under `.venv` and its libraries installed editable from `packages/`; compose shares it into the container read-only, at the
same path (the editable installs record absolute paths). The studio runs `<it>/.venv/bin/python -m ltx_pipelines.distilled` DIRECTLY (never `uv run`, which would try to sync a tree
that is read-only), in a cleaned environment (none of the NGC image's `LD_LIBRARY_PATH`, no `PYTHONPATH`, no bytecode written, every cache under the data folder).

What these tests protect: each thing that can be wrong with the clone is its own message with the path, who the studio runs as, and what to change; the order a person would fix them in;
a clone that is right runs a clip start to finish with the environment the program is meant to have; and how the found environment is compared with the one measured working.
Nothing here needs a GPU or the real program: the clone is a stand-in (video_support.ltx_clone). **What it cannot tell is whether the real clone, mounted into the real container,
works: that is the Spark's to test.**
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from video_support import ltx_clone, models_folder, request

from studio.pipelines.base import PipelineUnavailable
from studio.video import media
from studio.video.engine import EngineConfig
from studio.video.engines import ltx
from studio.video.engines.ltx import MEASURED_ON_THE_SPARK, Environment, LtxEngine, check_ltx_dir, check_model_files, check_ready, inspect_environment, interpreter_command, who

needs_ffmpeg = pytest.mark.skipif(not media.find_tools().ok, reason="ffmpeg and ffprobe are not installed here")


def cannot_access(monkeypatch, *paths: Path) -> None:
    """Make `os.access` say that the studio's user can use none of `paths` (read, run, enter), as a file owned by someone else with no permission for others would: the tests run as
    root in some places, where `chmod 000` stops nothing, and what is tested here is the message, not the kernel."""
    real = os.access
    blocked = {str(path) for path in paths}
    monkeypatch.setattr(ltx.os, "access", lambda path, mode, **kw: False if str(path) in blocked else real(path, mode, **kw))


@pytest.fixture(autouse=True)
def this_python_is_new_enough(monkeypatch):
    """The stand-in runs in the interpreter the tests run in, which may be older than the 3.12 the real program needs; the rule about the version has its own test."""
    monkeypatch.setattr(ltx, "MIN_PYTHON", (3, 0))


def config(tmp_path: Path, clone: Path, **changes) -> EngineConfig:
    values = dict(ltx_dir=str(clone), models_dir=str(models_folder(tmp_path / "models")), cache_dir=str(tmp_path / "data" / "video-cache"))
    values.update(changes)
    return EngineConfig(**values)


# ---------------------------------------------------------------- the clone, step by step
def test_a_clone_that_is_laid_out_as_the_real_one_passes_every_step(tmp_path):
    clone = ltx_clone(tmp_path / "LTX-2")
    assert check_ltx_dir(str(clone)) is None


def test_a_folder_that_is_not_there_is_named_with_the_setting_and_the_sharing(tmp_path):
    message, hint = check_ltx_dir(str(tmp_path / "missing"))
    assert message == f"The LTX-2 folder is not there: {tmp_path / 'missing'}."
    assert "STUDIO_VIDEO_LTX_DIR" in hint and "same path" in hint and "docker compose up -d" in hint


def test_a_file_is_not_a_folder(tmp_path):
    (tmp_path / "a-file").write_text("x")
    message, hint = check_ltx_dir(str(tmp_path / "a-file"))
    assert "is not a folder" in message and "STUDIO_VIDEO_LTX_DIR" in hint


def test_a_folder_the_studio_cannot_read_says_who_it_runs_as_and_what_to_change(tmp_path, monkeypatch):
    clone = ltx_clone(tmp_path / "LTX-2")
    cannot_access(monkeypatch, clone)
    message, hint = check_ltx_dir(str(clone))
    assert f"The studio cannot read the LTX-2 folder {clone}" in message and who() in message and f"(uid {os.getuid()}, gid {os.getgid()})" in message
    assert f"chmod -R a+rX {clone}" in hint and "STUDIO_UID" in hint and "STUDIO_GID" in hint


def test_a_clone_with_no_virtual_environment_says_how_to_make_one(tmp_path):
    (tmp_path / "LTX-2" / "packages").mkdir(parents=True)
    message, hint = check_ltx_dir(str(tmp_path / "LTX-2"))
    assert message == f"The LTX-2 folder has no Python environment: {tmp_path / 'LTX-2' / '.venv' / 'bin' / 'python'} is not there."
    assert "uv sync" in hint and str(tmp_path / "LTX-2") in hint


def test_an_environment_whose_python_link_leads_nowhere_names_the_link_and_the_containers_python(tmp_path):
    """The real clone's python is a link to /usr/bin/python3 on the host. The container (Ubuntu 24.04) has Python 3.12.3 there too; an environment made with another Python would
    leave a link to something that is not there, and this is how the person is told."""
    clone = ltx_clone(tmp_path / "LTX-2", python_link="/home/someone/.local/share/uv/python/cpython-3.12/bin/python3.12")
    message, hint = check_ltx_dir(str(clone))
    assert "is a link to /home/someone/.local/share/uv/python/cpython-3.12/bin/python3.12, which is not in the container" in message
    assert "/usr/bin/python3" in hint and "3.12" in hint


def test_a_python_the_studio_cannot_run_says_so_with_who_it_is(tmp_path, monkeypatch):
    clone = ltx_clone(tmp_path / "LTX-2")
    cannot_access(monkeypatch, clone / ".venv" / "bin" / "python")
    message, hint = check_ltx_dir(str(clone))
    assert "cannot run the LTX-2 environment's Python" in message and who() in message and "chmod -R a+rX" in hint


def test_a_folder_without_packages_is_not_taken_for_an_ltx_2_clone(tmp_path):
    clone = ltx_clone(tmp_path / "LTX-2", packages=False)
    message, hint = check_ltx_dir(str(clone))
    assert "has no packages/ folder" in message and "does not look like a LTX-2 clone" in message and ".venv and packages/" in hint


def test_who_says_the_user_and_the_ids():
    text = who()
    assert text.endswith(f"(uid {os.getuid()}, gid {os.getgid()})") and len(text.split()) >= 3


# ---------------------------------------------------------------- the models, readable
def test_a_model_folder_that_is_not_there_is_one_message_with_its_path_and_the_sharing(tmp_path):
    with pytest.raises(PipelineUnavailable) as caught:
        check_model_files(EngineConfig(models_dir=str(tmp_path / "nope")))
    assert caught.value.message == f"The folder of model files is not there: {tmp_path / 'nope'}." and "STUDIO_VIDEO_MODELS_DIR" in caught.value.hint and "same path" in caught.value.hint


def test_a_model_file_the_studio_cannot_read_is_named_with_who_and_what_to_change(tmp_path, monkeypatch):
    models = models_folder(tmp_path / "models")
    target = models / "diffusion_models" / "ltx-2.5-22b-distilled.safetensors"
    other = models / "text_encoders" / "gemma_12b_it.safetensors"
    cannot_access(monkeypatch, target, other)
    with pytest.raises(PipelineUnavailable) as caught:
        check_model_files(EngineConfig(models_dir=str(models)))
    assert f"The studio cannot read the distilled model: {target}" in caught.value.message and who() in caught.value.message
    assert f"chmod -R a+rX {models}" in caught.value.hint and "STUDIO_UID" in caught.value.hint and "1 other file(s) cannot be read either" in caught.value.hint


def test_readable_model_files_pass(tmp_path):
    check_model_files(EngineConfig(models_dir=str(models_folder(tmp_path / "models"))))


# ---------------------------------------------------------------- the whole check, in order
@needs_ffmpeg
def test_the_check_of_a_good_clone_runs_its_python_and_reports_the_versions_and_the_gpu(tmp_path):
    result = check_ready(config(tmp_path, ltx_clone(tmp_path / "LTX-2")))
    assert result["command"] == [str(tmp_path / "LTX-2" / ".venv" / "bin" / "python"), "-m", "ltx_pipelines.distilled"]
    assert result["device"] == {"name": "NVIDIA GB10 (stand-in)", "torch": "2.13.0+cu132", "cuda": "13.2"}
    assert (tmp_path / "data" / "video-cache").is_dir()  # the check already made the cache folders the program would write to


@needs_ffmpeg
def test_the_first_thing_wrong_is_told_first_the_clone_then_the_models_then_the_environment(tmp_path, monkeypatch):
    clone = ltx_clone(tmp_path / "LTX-2")
    good_models = str(models_folder(tmp_path / "models"))
    with pytest.raises(PipelineUnavailable) as caught:  # a clone that is not there, with models that are not either: the clone is first
        check_ready(EngineConfig(ltx_dir=str(tmp_path / "gone"), models_dir=str(tmp_path / "no-models")), inspect=False)
    assert "LTX-2 folder is not there" in caught.value.message
    with pytest.raises(PipelineUnavailable) as caught:  # a good clone, models that are not there
        check_ready(EngineConfig(ltx_dir=str(clone), models_dir=str(tmp_path / "no-models")), inspect=False)
    assert "folder of model files is not there" in caught.value.message
    monkeypatch.setenv("FAKE_TORCH_NO_GPU", "1")  # good clone, good models: the environment is what is wrong
    with pytest.raises(PipelineUnavailable) as caught:
        check_ready(EngineConfig(ltx_dir=str(clone), models_dir=good_models, cache_dir=str(tmp_path / "cache")))
    assert "cannot see the GPU" in caught.value.message and "runtime: nvidia" in caught.value.hint and MEASURED_ON_THE_SPARK["packages"]["torch"] in caught.value.hint


@needs_ffmpeg
def test_nothing_set_says_which_two_settings_to_make(tmp_path):
    with pytest.raises(PipelineUnavailable) as caught:
        check_ready(EngineConfig(models_dir=str(models_folder(tmp_path / "models"))), inspect=False)
    assert "not set up" in caught.value.message
    assert "STUDIO_VIDEO_LTX_DIR" in caught.value.hint and "STUDIO_VIDEO_MODELS_DIR" in caught.value.hint and "docker compose up -d" in caught.value.hint


@needs_ffmpeg
def test_an_image_built_without_the_program_and_no_folder_named_says_so_before_it_asks_about_the_models(tmp_path):
    """The image always says where its own environment WOULD be (STUDIO_VIDEO_LIBS), built or not; with nothing built and no clone named, the first thing to tell is that the program is
    not set up, which the two settings put right, and not a complaint about the model folder (which the person is about to be asked for anyway)."""
    with pytest.raises(PipelineUnavailable) as caught:
        check_ready(EngineConfig(libs=str(tmp_path / "video-libs")), inspect=False)  # no models either: the program comes first
    assert "no LTX-2 folder is named, and the program is not built into this image" in caught.value.message and "STUDIO_VIDEO_LTX_DIR" in caught.value.hint
    built = tmp_path / "video-libs" / "ltx" / "bin"
    built.mkdir(parents=True)
    (built / "python").write_text("#!/bin/sh\nexit 0\n")
    (built / "python").chmod(0o755)
    with pytest.raises(PipelineUnavailable) as caught:  # built in: now it is the models that are missing
        check_ready(EngineConfig(libs=str(tmp_path / "video-libs")), inspect=False)
    assert "model" in caught.value.message.lower()


@needs_ffmpeg
def test_a_command_or_an_interpreter_that_is_named_is_not_second_guessed_by_the_clone_checks(tmp_path):
    """STUDIO_VIDEO_COMMAND and STUDIO_VIDEO_PYTHON win over the clone (§46.6): whoever wrote the command knows what it is, so the clone's own layout is not required of them."""
    models = str(models_folder(tmp_path / "models"))
    seen = EngineConfig(ltx_dir=str(tmp_path / "gone"), models_dir=models, command=(sys.executable, "-c", "pass"))
    assert interpreter_command(seen) == (sys.executable, "-c", "pass")
    with pytest.raises(PipelineUnavailable) as caught:
        check_ready(seen)  # it fails later (this interpreter is no LTX), but not because the clone is not there
    assert "LTX-2 folder" not in caught.value.message


# ---------------------------------------------------------------- the environment, compared with the measured one
def found(**changes) -> Environment:
    base = dict(command=("p",), python=(3, 12, 3), torch="2.13.0+cu132", cuda_built="13.2", cuda=True, gpu="GB10", importable=True,
                packages={name: version for name, version in MEASURED_ON_THE_SPARK["packages"].items() if name != "torch"}, natten="imports")
    base.update(changes)
    return Environment(**base)


def test_an_environment_that_is_the_measured_one_differs_in_nothing():
    assert found().differences() == []


def test_a_different_version_is_a_note_that_names_what_was_measured():
    notes = found(torch="2.14.0+cu132", python=(3, 12, 4), packages={**found().packages, "transformers": "5.15.0"}).differences()
    assert "torch 2.14.0+cu132 (measured 2.13.0+cu132)" in notes and "Python 3.12.4 (measured 3.12.3)" in notes and "transformers 5.15.0 (measured 5.14.1)" in notes
    assert len(notes) == 3


def test_a_library_that_is_missing_is_a_note_and_natten_that_does_not_import_is_its_own_note():
    packages = {name: version for name, version in found().packages.items() if name != "triton"}
    notes = found(packages=packages, natten="ModuleNotFoundError: No module named 'natten'").differences()
    assert "triton not found (measured 3.7.1)" in notes and any(n.startswith("natten does not import here") for n in notes)


def test_a_command_that_cannot_say_its_versions_is_not_told_off_for_libraries_it_never_looked_at():
    assert found(packages=None, natten=None).differences() == []  # `uv run ...` is only asked whether it starts


def test_the_measured_environment_is_what_the_spark_reported():
    assert MEASURED_ON_THE_SPARK["ltx_commit"] == "daa6b16fc7f0f1628f2c9e36a303e3312b333cc6"
    assert MEASURED_ON_THE_SPARK["python"] == "3.12.3" and MEASURED_ON_THE_SPARK["cuda"] == "13.2"
    assert {"torch", "torchaudio", "torchvision", "torchcodec", "natten", "transformers", "triton", "safetensors", "av", "ltx-core", "ltx-pipelines", "ltx-trainer"} == set(MEASURED_ON_THE_SPARK["packages"])
    assert MEASURED_ON_THE_SPARK["packages"]["torch"] == "2.13.0+cu132" and MEASURED_ON_THE_SPARK["packages"]["ltx-pipelines"] == "1.6.2"


def test_the_look_at_the_environment_reads_the_stand_ins_and_the_libraries_it_has_metadata_for(tmp_path):
    environment = inspect_environment((str(ltx_clone(tmp_path / "LTX-2") / ".venv" / "bin" / "python"), "-m", "ltx_pipelines.distilled"), cache_dir=str(tmp_path / "cache"))
    assert environment.problem is None and (environment.torch, environment.cuda_built, environment.cuda, environment.gpu) == ("2.13.0+cu132", "13.2", True, "NVIDIA GB10 (stand-in)")
    assert environment.importable is True and environment.natten is not None and environment.natten != "imports"  # the stand-in has no natten: it says why, and does not refuse
    assert isinstance(environment.packages, dict)
    assert environment.differences()  # the stand-in has no metadata for the libraries: each is a note


# ---------------------------------------------------------------- a clip, with the environment the program is meant to have
@needs_ffmpeg
def test_a_clip_is_made_by_the_clones_python_in_a_cleaned_environment_with_its_caches_under_the_data_folder(tmp_path, monkeypatch):
    clone = ltx_clone(tmp_path / "LTX-2")
    cache = tmp_path / "data" / "video-cache"
    record = tmp_path / "record.jsonl"
    monkeypatch.setenv("FAKE_LTX_RECORD", str(record))
    # what the NGC image gives the studio, and what the program must not get
    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/local/lib/python3.12/dist-packages/torch/lib:/usr/local/cuda/compat/lib:/usr/local/nvidia/lib")
    monkeypatch.setenv("PYTHONPATH", "/app/backend")
    monkeypatch.setenv("VIRTUAL_ENV", "/opt/studio-venv")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    out = tmp_path / "data" / "video" / "x" / "engine-out.mp4"
    clip = LtxEngine(config(tmp_path, clone)).generate(request(out, seed=5), lambda *e: None, lambda: False)
    assert clip.path == str(out) and out.is_file()
    ran = json.loads(record.read_text().splitlines()[0])
    assert ran["ld"] is None and ran["env"]["VIRTUAL_ENV"] is None and ran["env"]["PYTHONHOME"] is None  # none of the image's libraries or Python
    assert ran["env"]["PYTHONDONTWRITEBYTECODE"] == "1" and ran["unbuffered"] == "1"
    assert ran["env"]["CUDA_VISIBLE_DEVICES"] == "0" and ran["env"]["HOME"] == os.environ["HOME"] and ran["env"]["PATH"] == os.environ["PATH"]
    for name, folder in (("TRITON_CACHE_DIR", "triton"), ("TORCHINDUCTOR_CACHE_DIR", "torchinductor"), ("TORCH_HOME", "torch")):
        assert ran["env"][name] == str(cache / folder) and (cache / folder).is_dir(), name
    assert ran["pgid"] == ran["pid"]  # its own process group, as for every program
