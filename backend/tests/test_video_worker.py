"""The video kind of the GPU worker (DESIGN.md §46.6, criterion 445): the job's checks, the events a clip makes, Cancel, failures, and the process itself.

The worker is driven in this process where that is enough (fast, and the events can be inspected) and as a real subprocess where the protocol itself is the thing being checked."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from video_support import OTHER_RUN_ID, RUN_ID, in_process_worker, video_job

from studio.pipelines.base import Canceled
from studio.video import media
from studio.video.job import VideoJob

BACKEND = Path(__file__).resolve().parent.parent
needs_ffmpeg = pytest.mark.skipif(not media.find_tools().ok, reason="ffmpeg and ffprobe are not installed here")


# ---------------------------------------------------------------- the job's checks
def test_a_good_job_is_read_back_as_it_was_sent_and_its_paths_are_made_absolute_for_the_engine(tmp_path):
    job = VideoJob.from_dict(video_job(), tmp_path)
    assert job.run_id == RUN_ID and job.engine == "fake" and job.variant == "distilled" and (job.width, job.height, job.num_frames, job.fps, job.seed) == (256, 128, 25, 24, 7)
    request = job.request(tmp_path)
    assert request.out == str((tmp_path / "video" / RUN_ID / "engine-out.mp4").resolve()) and request.images == ()


def test_a_start_picture_must_be_a_file_in_the_runs_own_video_folder(tmp_path):
    folder = tmp_path / "video" / RUN_ID
    folder.mkdir(parents=True)
    (folder / "start.png").write_bytes(b"png")
    job = VideoJob.from_dict(video_job(images=[{"path": f"video/{RUN_ID}/start.png", "frame": 0, "strength": 1}]), tmp_path)
    assert job.request(tmp_path).images[0].path == str((folder / "start.png").resolve()) and job.images[0][1:] == (0, 1.0)


@pytest.mark.parametrize("change, why", [
    (dict(run_id="nope"), "bad run_id"),
    (dict(engine=""), "engine and variant"),
    (dict(variant=None), "engine and variant"),
    (dict(prompt="   "), "some words"),
    (dict(prompt=7), "some words"),
    (dict(width="256"), "width must be a whole number"),
    (dict(height=True), "height must be a whole number"),
    (dict(width=255), "even"),
    (dict(width=0), "even"),
    (dict(num_frames=24), "8n + 1"),
    (dict(num_frames=1), "8n + 1"),
    (dict(num_frames=10_001), "8n + 1"),
    (dict(fps=0), "frame rate"),
    (dict(seed=-1), "frame rate or the seed"),
    (dict(out="video/x/engine-out.mov"), ".mp4"),
    (dict(out=f"video/{OTHER_RUN_ID}/engine-out.mp4"), "own video folder"),
    (dict(out="../escape.mp4"), "own video folder"),
    (dict(out="/etc/escape.mp4"), "own video folder"),
    (dict(out="images/x.mp4"), "own video folder"),
    (dict(images=[{"path": "images/x.png"}]), "not a file in the run's own video folder"),
    (dict(images=[{"path": f"video/{RUN_ID}/missing.png"}]), "not a file in the run's own video folder"),
    (dict(images=["start.png"]), "needs a path"),
])
def test_a_bad_job_is_refused_with_a_sentence_that_says_what_is_wrong(tmp_path, change, why):
    with pytest.raises(ValueError) as caught:
        VideoJob.from_dict(video_job(**change), tmp_path)
    assert why in str(caught.value)


def test_a_job_that_is_not_an_object_is_refused(tmp_path):
    with pytest.raises(ValueError, match="not an object"):
        VideoJob.from_dict("job", tmp_path)


def test_a_picture_with_a_frame_or_strength_that_makes_no_sense_is_refused(tmp_path):
    folder = tmp_path / "video" / RUN_ID
    folder.mkdir(parents=True)
    (folder / "start.png").write_bytes(b"png")
    for extra in ({"frame": -1}, {"frame": "0"}, {"strength": 2}, {"strength": True}):
        with pytest.raises(ValueError, match="frame must be a whole number"):
            VideoJob.from_dict(video_job(images=[{"path": f"video/{RUN_ID}/start.png", **extra}]), tmp_path)


# ---------------------------------------------------------------- the events of a clip
@needs_ffmpeg
def test_a_clip_is_one_run_started_progress_video_done_and_run_finished(tmp_path):
    worker, emit = in_process_worker(tmp_path)
    worker.run(video_job())
    kinds = emit.kinds()
    assert kinds[:3] == ["state", "state", "run_started"]  # loading, ready, then the clip begins
    assert kinds.count("run_started") == 1 and kinds.count("video_done") == 1 and kinds[-2:] == ["video_done", "run_finished"]
    done = emit.of("video_done")[0]
    assert done["path"] == f"video/{RUN_ID}/engine-out.mp4" and done["idx"] == 0 and done["seed"] == 7 and (tmp_path / done["path"]).is_file()
    stages = [e["stage"] for e in emit.of("progress")]
    assert [s for i, s in enumerate(stages) if i == 0 or s != stages[i - 1]] == ["start", "text", "denoise", "upscale", "refine", "decode", "write"]
    assert all(e["image"] == 1 and e["of"] == 1 for e in emit.of("progress"))
    assert emit.of("run_finished")[0]["completed"] == 1


@needs_ffmpeg
@pytest.mark.parametrize("word, says, kind", [("[fake:error]", "RuntimeError: the fake video program was told to fail", "error"), ("[fake:oom]", "more memory than was free", "out_of_memory")])
def test_a_failed_clip_is_run_failed_with_the_message_and_no_video_done(tmp_path, word, says, kind):
    worker, emit = in_process_worker(tmp_path)
    worker.run(video_job(prompt=f"a fox {word}"))
    assert emit.kinds()[-1] == "run_failed" and "video_done" not in emit.kinds()
    error = emit.of("run_failed")[0]["error"]
    assert says in error["message"] and error["hint"] and error["kind"] == kind  # the kind is what the server's hint and the page's wording are chosen by


@needs_ffmpeg
def test_cancel_stops_a_clip_that_is_being_made_and_a_cancel_before_it_starts_stops_it_at_once(tmp_path):
    worker, emit = in_process_worker(tmp_path)
    threading.Timer(0.3, lambda: worker.request_cancel(RUN_ID)).start()
    worker.run(video_job(prompt="a fox [fake:slow]"))
    assert emit.kinds()[-1] == "run_canceled" and "video_done" not in emit.kinds() and "run_finished" not in emit.kinds()
    worker2, emit2 = in_process_worker(tmp_path / "other")
    worker2.request_cancel(RUN_ID)
    worker2.run(video_job())
    assert emit2.kinds() == ["state", "state", "run_canceled"]  # loading, ready, canceled: the clip never began
    assert emit2.of("run_canceled")[0]["completed"] == 0


class MuteEngine:
    """An engine that works and says nothing (no progress at all, as a program whose log lines are not recognised): the flag it is handed is the only way to reach it."""

    def generate(self, request, progress, cancelled):
        end = time.monotonic() + 10
        while time.monotonic() < end:
            if cancelled():
                raise Canceled()
            time.sleep(0.01)
        raise AssertionError("it was never told to stop")


class DeafEngine:
    """An engine that never looks at the flag but reports as it goes (as the real one reports every step): Cancel reaches it in the report, which raises."""

    def generate(self, request, progress, cancelled):
        for step in range(1000):
            progress("denoise", step, 1000)
            time.sleep(0.01)
        raise AssertionError("it was never told to stop")


@pytest.mark.parametrize("engine", [MuteEngine, DeafEngine], ids=["through the flag the engine is given", "through the progress report"])
def test_cancel_reaches_an_engine_by_either_road_and_does_not_depend_on_the_other(tmp_path, engine):
    """The worker gives the engine two ways to be stopped (DESIGN.md §46.6): a flag to look at, and a progress callback that raises. An engine may use either, so each must work alone."""
    worker, emit = in_process_worker(tmp_path)
    assert worker.load()
    worker.pipeline = engine()
    threading.Timer(0.3, lambda: worker.request_cancel(RUN_ID)).start()
    started = time.monotonic()
    worker.run(video_job())
    assert emit.kinds()[-1] == "run_canceled" and "run_failed" not in emit.kinds() and "video_done" not in emit.kinds()
    assert time.monotonic() - started < 5  # at once, not when the engine gives up by itself


def test_a_malformed_job_is_run_failed_with_the_reason_and_nothing_is_written(tmp_path):
    worker, emit = in_process_worker(tmp_path)
    worker.run(video_job(num_frames=24))
    assert emit.kinds() == ["run_failed"] and "Malformed job" in emit.of("run_failed")[0]["error"]["message"] and not (tmp_path / "video").exists()


# ---------------------------------------------------------------- the process itself
def run_worker(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "studio.worker", "--kind", "video", "--pipeline", "fake", "--model", "", "--data-dir", str(args[0]), *args[1:]],
                          input=stdin, capture_output=True, text=True, cwd=BACKEND, timeout=60)


@needs_ffmpeg
def test_the_worker_process_says_hello_makes_a_clip_over_the_json_lines_protocol_and_says_bye(tmp_path):
    commands = json.dumps({"cmd": "run", "job": video_job()}) + "\n" + json.dumps({"cmd": "shutdown"}) + "\n"
    done = run_worker(str(tmp_path), "--engine", "fake", "--variant", "distilled", "--fake-step-delay-ms", "0", stdin=commands)
    assert done.returncode == 0, done.stderr
    events = [json.loads(line) for line in done.stdout.splitlines()]
    kinds = [e["event"] for e in events]
    assert kinds[0] == "hello" and events[0]["kind"] == "video" and events[0]["engine"] == "fake"
    assert "video_done" in kinds and kinds[-2:] == ["run_finished", "bye"]
    assert (tmp_path / "video" / RUN_ID / "engine-out.mp4").is_file()


@needs_ffmpeg
def test_the_probe_of_the_worker_process_answers_for_the_video_engine_and_is_told_what_the_server_knows(tmp_path):
    done = subprocess.run([sys.executable, "-m", "studio.worker", "--kind", "video", "--pipeline", "fake", "--model", "", "--data-dir", str(tmp_path), "--engine", "fake", "--probe"],
                          capture_output=True, text=True, cwd=BACKEND, timeout=60)
    answer = json.loads(done.stdout.strip().splitlines()[-1])
    assert answer["event"] == "probe" and answer["ok"] is True
    # the real engine, told nothing about where its files are: unavailable, with the reason in words
    real = subprocess.run([sys.executable, "-m", "studio.worker", "--kind", "video", "--pipeline", "real", "--model", "", "--data-dir", str(tmp_path), "--engine", "ltx", "--probe"],
                          capture_output=True, text=True, cwd=BACKEND, timeout=60)
    said = json.loads(real.stdout.strip().splitlines()[-1])
    assert said["ok"] is False and said["error"]["kind"] == "unavailable" and said["error"]["message"] and said["error"]["hint"]
    # and told where to look, it names the missing thing by its path
    (tmp_path / "models" / "diffusion_models").mkdir(parents=True)  # the right folder with nothing in it: the message then names where each file should be
    config = json.dumps({"models_dir": str(tmp_path / "models"), "command": [sys.executable]})
    told = subprocess.run([sys.executable, "-m", "studio.worker", "--kind", "video", "--pipeline", "real", "--model", "", "--data-dir", str(tmp_path), "--engine", "ltx", "--probe",
                           "--engine-config", config], capture_output=True, text=True, cwd=BACKEND, timeout=60)
    assert str(tmp_path / "models" / "diffusion_models") in json.loads(told.stdout.strip().splitlines()[-1])["error"]["message"]


def test_a_fake_worker_is_refused_a_real_engine_and_the_other_way_round(tmp_path):
    from studio.pipelines import make_pipeline

    with pytest.raises(ValueError, match="does not go with"):
        make_pipeline("fake", model="", cpu_offload=False, hub_mode="auto", fake_step_delay_ms=0, kind="video", engine="ltx", variant="distilled")
    with pytest.raises(ValueError, match="does not go with"):
        make_pipeline("real", model="", cpu_offload=False, hub_mode="auto", fake_step_delay_ms=0, kind="video", engine="fake", variant="distilled")
