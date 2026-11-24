"""The Video tab on the server (DESIGN.md §46.9, §46.10, criteria 441 to 464), with the fake engine and a real ffmpeg: making a clip through `POST /api/runs`, the licence gate,
the files, serving with `Range`, Keep, projects, the bin, delete, search, the queue, Cancel, the memory and disk checks, and the engine swap."""

from __future__ import annotations

import dataclasses
import io
import json
import re
import time
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import create_run, image_bytes, quiet_janitors, stage, wait_for
from PIL import Image
from video_support import accept_licence, create_clip, record_events, wait_for_video_probe

from studio import sysinfo
from studio.jobs import JobManager
from studio.serialize import parse_ts
from studio.config import Settings
from studio.video import media
from studio.video import registry as video_registry
from studio.video.engines.fake import INFO, FakeVideo

pytestmark = pytest.mark.skipif(not media.find_tools().ok, reason="ffmpeg and ffprobe are not installed here")


@pytest.fixture
def video(client_factory):
    """A client whose video engine has been checked and whose licence has been acknowledged."""
    client = client_factory(quiet=True)
    wait_for_video_probe(client)
    accept_licence(client)
    return client


def clip_files(client, run_id: str) -> list[str]:
    folder = client.app.state.storage.root / "video" / run_id
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


# ---------------------------------------------------------------- what the page is told
def test_the_capabilities_say_video_can_run_and_everything_the_form_needs(client_factory):
    client = client_factory(quiet=True)
    caps = wait_for_video_probe(client)
    assert caps["available"] is True and caps["state"] == "ready" and caps["reason"] is None
    assert "video" in client.get("/api/capabilities").json()["modes"]
    assert caps["tools"] == {"ffmpeg": True, "ffprobe": True} and caps["chaining"]["available"] is False
    assert caps["engine"]["id"] == "fake" and caps["memory"] == {"ok": True, "message": None}
    assert [q["id"] for q in caps["qualities"]] == ["draft", "final"] and caps["qualities"][0]["available"] is True and caps["qualities"][1]["available"] is False
    assert caps["licence"]["accepted"] is False and caps["licence"]["revision"] == "fake-1" and caps["licence"]["statement"]
    limits = client.get("/api/capabilities").json()["limits"]["video"]
    assert limits["size"]["multiple"] == 64 and limits["seconds"]["max"] == 30 and limits["estimate"]["points"]


def test_when_the_engine_cannot_run_the_tab_says_why_and_no_clip_is_accepted(client_factory, monkeypatch):
    monkeypatch.setenv("STUDIO_FAKE_VIDEO_UNAVAILABLE", "1")
    client = client_factory(quiet=True)
    caps = wait_for_video_probe(client)
    assert caps["available"] is False and caps["state"] == "unavailable" and "not installed" in caps["reason"] and "STUDIO_FAKE_VIDEO_UNAVAILABLE" in caps["hint"]
    assert "video" not in client.get("/api/capabilities").json()["modes"]
    accept_licence(client)  # the licence can be acknowledged whatever the program: it is the person's, not the machine's
    refusal = create_clip(client, expect=409)
    assert refusal["code"] == "video_unavailable" and "not installed" in refusal["detail"] and refusal["hint"]


def test_a_request_while_the_engine_is_still_being_checked_is_told_to_wait(client_factory):
    client = client_factory(quiet=True)
    wait_for_video_probe(client)  # the real start-up check must be over first: on a busy machine it would finish after the line below and put its own answer over the one this test sets
    jobs = client.app.state.jobs
    jobs._video_probes = {"fake": {"state": "checking"}}  # as the first moments after start-up are
    accept_licence(client)
    refusal = create_clip(client, expect=409)
    assert refusal["code"] == "video_unavailable" and "still being checked" in refusal["detail"]


# ---------------------------------------------------------------- the licence (criterion 447)
def test_no_clip_is_accepted_and_no_model_is_loaded_until_the_licence_is_acknowledged(client_factory):
    client = client_factory(quiet=True)
    wait_for_video_probe(client)
    refusal = create_clip(client, expect=409)
    assert refusal["code"] == "licence_not_accepted" and refusal["hint"]
    load = client.post("/api/model/load", json={"model": "video"})
    assert load.status_code == 409 and load.json()["code"] == "licence_not_accepted"
    assert client.get("/api/status").json()["worker"]["model"] != "video"


def test_the_licence_is_stored_with_its_revision_and_time_and_can_be_withdrawn(video):
    caps = video.get("/api/capabilities").json()["video"]["licence"]
    assert caps["accepted"] is True and caps["accepted_at"].endswith("Z") and caps["outdated"] is False
    assert video.get("/api/video/licence").json()["accepted"] is True
    stored = video.app.state.db.read_one("SELECT value FROM meta WHERE key='video_licence'")
    assert '"revision": "fake-1"' in stored["value"] and "I have read" in stored["value"]
    withdrawn = video.delete("/api/video/licence").json()
    assert withdrawn["accepted"] is False and video.get("/api/capabilities").json()["video"]["licence"]["accepted"] is False
    assert create_clip(video, expect=409)["code"] == "licence_not_accepted"


def test_the_acknowledgement_needs_accept_true_and_the_revision_the_person_saw(client_factory):
    client = client_factory(quiet=True)
    assert client.post("/api/video/licence", json={"accept": False, "revision": "fake-1"}).status_code == 422
    assert client.post("/api/video/licence", json={"accept": "yes", "revision": "fake-1"}).status_code == 422  # strict: only the boolean true
    assert client.post("/api/video/licence", json={"revision": "fake-1"}).status_code == 422
    wrong = client.post("/api/video/licence", json={"accept": True, "revision": "an-old-one"})
    assert wrong.status_code == 422 and wrong.json()["code"] == "licence_revision"
    assert client.get("/api/capabilities").json()["video"]["licence"]["accepted"] is False


def test_nothing_but_the_panel_accepts_not_a_setting_a_header_or_a_default(client_factory):
    assert not [f.name for f in dataclasses.fields(Settings) if "licen" in f.name or "accept" in f.name]  # there is no setting that could
    client = client_factory(quiet=True, video_min_free_gb=0.0)
    wait_for_video_probe(client)
    assert client.get("/api/capabilities", headers={"X-Studio-Licence": "accepted"}).json()["video"]["licence"]["accepted"] is False
    assert create_clip(client, expect=409)["code"] == "licence_not_accepted"


def test_a_licence_that_changed_is_asked_for_again_and_says_why(video, monkeypatch):
    newer = dataclasses.replace(INFO, licence=dataclasses.replace(INFO.licence, revision="fake-2"))
    monkeypatch.setattr(FakeVideo, "INFO", newer)
    licence = video.get("/api/capabilities").json()["video"]["licence"]
    assert licence["accepted"] is False and licence["outdated"] is True and licence["revision"] == "fake-2"
    assert create_clip(video, expect=409)["code"] == "licence_not_accepted"
    assert video.post("/api/video/licence", json={"accept": True, "revision": "fake-2"}).json()["accepted"] is True
    wait_for(video, create_clip(video)["id"])


def test_an_acknowledgement_of_another_licence_with_the_same_revision_does_not_count(video, monkeypatch):
    """The acknowledgement is of one licence (its name) at one revision: a model whose licence is another one is not covered by what was read for this one, even if the two happen to
    be at the same revision (DESIGN.md §46.7). The revision alone would say yes."""
    assert video.get("/api/capabilities").json()["video"]["licence"]["accepted"] is True  # the fixture acknowledged the fake engine's licence
    other = dataclasses.replace(INFO, licence=dataclasses.replace(INFO.licence, name="Another licence entirely"))
    monkeypatch.setattr(FakeVideo, "INFO", other)
    licence = video.get("/api/capabilities").json()["video"]["licence"]
    assert licence["revision"] == INFO.licence.revision and licence["accepted"] is False
    assert create_clip(video, expect=409)["code"] == "licence_not_accepted"


# ---------------------------------------------------------------- a clip, from request to files
def test_a_clip_is_queued_made_checked_and_recorded_with_the_facts_the_file_itself_gives(video):
    queued = create_clip(video, "a fox in the snow", sound="snow crunching", seconds=1, seed=77)
    assert queued["mode"] == "video" and queued["status"] in ("queued", "running") and queued["video"] is None and queued["segments"] == []
    assert queued["prompt"] == "a fox in the snow" and queued["effective_prompt"] == "a fox in the snow. Sound: snow crunching"
    done = wait_for(video, queued["id"])
    assert done["status"] == "done" and done["error"] is None and done["model_id"] == "fake-video · distilled" and done["options"]["engine"] == "fake"
    clip = done["video"]
    assert (clip["width"], clip["height"], clip["frames"], clip["fps"], clip["seed"]) == (256, 128, 25, 24.0, 77) and clip["has_audio"] and clip["note"] is None
    assert (clip["audio_channels"], clip["audio_rate"]) == (2, 48000) and clip["seconds"] == pytest.approx(25 / 24, abs=0.01)
    assert done["segments"] == [{"idx": 0, "status": "done", "seconds": clip["seconds"]}]
    # the facts are the file's own
    root = video.app.state.storage.root
    path = root / "video" / done["id"] / "clip.mp4"
    facts = media.probe_clip("ffprobe", path)
    assert (facts.width, facts.frames, facts.has_audio, facts.bytes) == (256, 25, True, clip["bytes"]) and facts.playable_everywhere
    # what is left on the disk: the clip, its poster and its thumbnail; the program's own file is gone
    assert clip_files(video, done["id"]) == ["clip.mp4", "poster.jpg"] and (root / "thumbs" / done["id"] / "video.webp").is_file()
    assert Image.open(root / "video" / done["id"] / "poster.jpg").size == (256, 128)


def test_the_file_has_its_index_at_the_front_and_carries_the_licence_notice_and_the_words(video):
    """Protects DESIGN.md §46.9: the saved clip starts playing before it has all arrived (faststart: `moov` before `mdat`), and a clip that leaves the studio still says what
    made it (the engine's licence notice as the file's comment) and from which words (its title)."""
    done = wait_for(video, create_clip(video, "A fox in the snow")["id"])
    data = (video.app.state.storage.root / "video" / done["id"] / "clip.mp4").read_bytes()
    assert 0 < data.find(b"moov") < data.find(b"mdat")
    assert b"Made with the fake video engine." in data and b"A fox in the snow" in data


def test_the_whole_run_is_told_over_the_event_stream_with_the_real_stages(video):
    seen = record_events(video)
    run = wait_for(video, create_clip(video)["id"])
    progress = [data["progress"]["stage"] for event, data in seen if event == "run.progress" and data["id"] == run["id"]]
    assert [s for i, s in enumerate(progress) if i == 0 or s != progress[i - 1]] == ["start", "text", "denoise", "upscale", "refine", "decode", "write"]
    steps = [(data["progress"]["step"], data["progress"]["steps"]) for event, data in seen if event == "run.progress" and data["progress"]["stage"] == "refine"]
    assert (3, 3) in steps
    updates = [data for event, data in seen if event == "run.updated" and data["id"] == run["id"]]
    assert any(u["video"] is not None for u in updates) and updates[-1]["status"] == "done"


def test_a_clip_with_no_sound_track_is_finished_with_a_note_and_is_not_a_failure(video):
    done = wait_for(video, create_clip(video, "a fox [fake:silent]")["id"])
    assert done["status"] == "done" and done["video"]["has_audio"] is False and done["video"]["note"] == "This clip has no sound track."
    assert done["video"]["audio_channels"] is None


def test_no_sound_removes_the_track_from_the_saved_file_and_is_not_a_note(video):
    done = wait_for(video, create_clip(video, keep_sound=False, sound="rain")["id"])
    assert done["status"] == "done" and done["video"]["has_audio"] is False and done["video"]["note"] is None and done["options"]["keep_sound"] is False
    assert done["options"]["sound"] == "rain"  # the words are kept: they are the clip's record


@pytest.mark.parametrize("word, says", [("[fake:error]", "The video program stopped: RuntimeError: the fake video program was told to fail"), ("[fake:oom]", "This clip needed more memory than was free")])
def test_a_clip_that_fails_says_why_in_words_and_leaves_nothing_but_the_card(video, word, says):
    failed = wait_for(video, create_clip(video, f"a fox {word}")["id"])
    assert failed["status"] == "failed" and says in failed["error"]["message"] and failed["error"]["hint"] and failed["video"] is None
    assert clip_files(video, failed["id"]) == []  # a half-made file is not left
    again = wait_for(video, create_clip(video)["id"])  # and the worker goes on: the next clip is made
    assert again["status"] == "done"


def test_a_file_that_is_not_the_clip_asked_for_is_a_failed_run_with_the_reason(video, monkeypatch):
    """The server trusts the file's own facts and not the engine's word: a clip of another size than was asked for is refused, with what was found."""
    original = media.check_output
    monkeypatch.setattr(media, "check_output", lambda *a, **k: "The program wrote a 1x1 clip; 256x128 was asked for.")
    monkeypatch.setattr("studio.video.service.check_output", media.check_output)
    failed = wait_for(video, create_clip(video)["id"])
    assert failed["status"] == "failed" and "The clip could not be finished: The program wrote a 1x1 clip" in failed["error"]["message"] and failed["video"] is None
    monkeypatch.setattr(media, "check_output", original)


# ---------------------------------------------------------------- serving (criterion 457)
def test_the_clip_is_served_with_range_requests_so_a_player_can_seek(video):
    done = wait_for(video, create_clip(video)["id"])
    url, size = done["video"]["url"], done["video"]["bytes"]
    whole = video.get(url)
    assert whole.status_code == 200 and whole.headers["content-type"] == "video/mp4" and whole.headers["accept-ranges"] == "bytes" and len(whole.content) == size
    assert "immutable" in whole.headers["cache-control"]
    part = video.get(url, headers={"Range": "bytes=100-199"})
    assert part.status_code == 206 and part.content == whole.content[100:200] and part.headers["content-range"] == f"bytes 100-199/{size}"
    tail = video.get(url, headers={"Range": "bytes=-50"})
    assert tail.status_code == 206 and tail.content == whole.content[-50:]
    beyond = video.get(url, headers={"Range": f"bytes={size + 10}-"})
    assert beyond.status_code == 416 and beyond.headers["content-range"] == f"bytes */{size}"


def test_the_download_is_an_attachment_named_in_the_studios_style_and_the_poster_and_thumbnail_are_images(video):
    done = wait_for(video, create_clip(video, "A red fox, running", seed=4821)["id"])
    named = video.get(done["video"]["download_url"])
    assert re.fullmatch(r'attachment; filename="video_red-fox-running_1s_s4821_\d{8}-\d{6}\.mp4"; filename\*=UTF-8\'\'video_red-fox-running_1s_s4821_\d{8}-\d{6}\.mp4', named.headers["content-disposition"])
    assert "content-disposition" not in video.get(done["video"]["url"]).headers
    poster = video.get(done["video"]["poster_url"])
    assert poster.headers["content-type"] == "image/jpeg" and Image.open(io.BytesIO(poster.content)).size == (256, 128)
    thumb = video.get(done["video"]["thumb_url"])
    assert thumb.headers["content-type"] == "image/webp" and Image.open(io.BytesIO(thumb.content)).format == "WEBP"


def test_an_unknown_malformed_binned_or_missing_clip_is_a_404_in_words(video):
    for bad in ("0" * 32, "nope", "../x"):
        assert video.get(f"/api/videos/{bad}").status_code == 404
    done = wait_for(video, create_clip(video)["id"])
    assert video.post(f"/api/runs/{done['id']}/bin").status_code == 200
    binned = video.get(done["video"]["url"])
    assert binned.status_code == 404 and "in the bin" in binned.json()["detail"] and video.get(done["video"]["poster_url"]).status_code == 404
    assert video.post(f"/api/runs/{done['id']}/restore").status_code == 200 and video.get(done["video"]["url"]).status_code == 200
    (video.app.state.storage.root / "video" / done["id"] / "clip.mp4").unlink()
    gone = video.get(done["video"]["url"])
    assert gone.status_code == 404 and gone.json()["code"] == "file_missing"


# ---------------------------------------------------------------- image to video (criterion 446, 468)
def test_a_start_picture_is_cut_to_the_clips_shape_made_rgb_and_is_the_first_frame(video):
    root = video.app.state.storage.root
    red = stage(video, image_bytes((200, 30, 30), size=(100, 100)))  # a square picture for a clip of 2:1
    queued = create_clip(video, "the red room", pictures=[{"upload_id": red["upload_id"]}])
    assert queued["options"]["mode"] == "image" and queued["options"]["start"] == {"image": 1, "frame": 0, "strength": 1.0} and len(queued["inputs"]) == 1
    done = wait_for(video, queued["id"])
    assert done["status"] == "done" and (done["video"]["width"], done["video"]["height"]) == (256, 128)  # the clip is the size asked for, whatever the picture's
    first = Image.open(io.BytesIO(video.get(done["video"]["poster_url"]).content)).convert("RGB")
    r, g, b = first.getpixel((60, 60))
    assert abs(r - 200) < 14 and abs(g - 30) < 14 and abs(b - 30) < 14
    assert clip_files(video, done["id"]) == ["clip.mp4", "poster.jpg"]  # the clip's own copy of the picture is gone, the person's stays with the run
    assert (root / "inputs" / done["id"] / "1.png").is_file() and done["inputs"][0]["width"] == 100
    assert video.get(f"/api/uploads/{red['upload_id']}").status_code in (404, 405) and video.delete(f"/api/uploads/{red['upload_id']}").status_code == 404  # the upload was used up


def test_a_picture_the_studio_already_has_can_start_a_clip_animate_this(video):
    picture = wait_for(video, create_run(video, "a lighthouse at dusk")["id"])
    done = wait_for(video, create_clip(video, "the lighthouse comes alive", pictures=[{"image_id": picture["images"][0]["id"]}])["id"])
    assert done["status"] == "done" and done["options"]["mode"] == "image" and done["inputs"][0]["id"] != picture["images"][0]["id"]  # the clip has a copy of its own
    # the clip's own copy can start another: what Retry and Reuse do
    again = wait_for(video, create_clip(video, "again", pictures=[{"image_id": done["inputs"][0]["id"]}])["id"])
    assert again["status"] == "done"


def test_a_picture_that_is_gone_or_used_is_a_422_that_names_the_picture(video):
    used = stage(video, image_bytes())
    wait_for(video, create_clip(video, pictures=[{"upload_id": used["upload_id"]}])["id"])
    refusal = video.post("/api/runs", json={**{"mode": "video", "prompt": "x", "input_images": [{"upload_id": used["upload_id"]}]}, "options": {"seconds": 1, "width": 256, "height": 128}})
    assert refusal.status_code == 422 and refusal.json()["detail"][0]["loc"] == ["body", "input_images", 0] and "already used" in refusal.json()["detail"][0]["msg"]
    refusal = video.post("/api/runs", json={"mode": "video", "prompt": "x", "input_images": [{"image_id": "f" * 32}], "options": {"seconds": 1, "width": 256, "height": 128}})
    assert refusal.status_code == 422 and "no longer exists" in refusal.json()["detail"][0]["msg"]


def test_a_bad_request_is_a_422_with_the_field_path_and_code_and_queues_nothing(video):
    bad = video.post("/api/runs", json={"mode": "video", "prompt": "a fox", "options": {"width": 720, "height": 704}})
    assert bad.status_code == 422 and bad.json()["detail"][0]["loc"] == ["body", "options", "width"] and bad.json()["detail"][0]["type"] == "bad_size"
    assert video.get("/api/runs?kind=video").json()["runs"] == []  # neither bad request left a run behind
    # a word that is no option of a clip is not an error (the other kinds of run read their options the same way) and is not kept in the run's record either
    unknown = video.post("/api/runs", json={"mode": "video", "prompt": "a fox", "options": {"width": 256, "height": 128, "seconds": 1, "colours": 3}})
    assert unknown.status_code == 201 and "colours" not in unknown.json()["options"]
    wait_for(video, unknown.json()["id"])


# ---------------------------------------------------------------- the queue, Cancel, the checks (criteria 449, 451, 453, 455)
def test_a_clip_is_one_queue_entry_of_kind_video_that_can_be_moved_while_it_waits(client_factory):
    client = client_factory(quiet=True, fake_step_delay_ms=1)
    wait_for_video_probe(client)
    accept_licence(client)
    first = create_clip(client, "first [fake:slow]")
    second = create_clip(client, "second")
    third = create_clip(client, "third")
    listing = client.get("/api/queue").json()
    assert listing["running"]["kind"] == "video" and listing["running"]["id"] == first["id"] and [q["kind"] for q in listing["queued"]] == ["video", "video"]
    moved = client.post("/api/queue/move", json={"id": third["id"], "before": second["id"]})
    assert moved.status_code == 200 and [q["id"] for q in moved.json()["queued"]] == [third["id"], second["id"]]
    assert client.post(f"/api/runs/{first['id']}/cancel").status_code == 202
    assert wait_for(client, third["id"])["status"] == "done"


def test_a_clip_counts_once_against_the_queue_cap(client_factory):
    client = client_factory(quiet=True, queue_cap=1)
    wait_for_video_probe(client)
    accept_licence(client)
    create_clip(client, "running [fake:slow]")
    time.sleep(0.5)
    create_clip(client, "waiting")
    refused = create_clip(client, "one too many", expect=429)
    assert refused["code"] == "queue_full"


def test_a_queued_clip_is_canceled_at_once_and_a_running_one_stops_and_leaves_no_clip(client_factory):
    client = client_factory(quiet=True)
    wait_for_video_probe(client)
    accept_licence(client)
    running = create_clip(client, "slow one [fake:slow]")
    waiting = create_clip(client, "waiting one")
    assert client.post(f"/api/runs/{waiting['id']}/cancel").json()["status"] == "canceled"
    deadline = time.monotonic() + 10
    while client.get(f"/api/runs/{running['id']}").json()["status"] != "running" and time.monotonic() < deadline:
        time.sleep(0.02)
    started = time.monotonic()
    assert client.post(f"/api/runs/{running['id']}/cancel").status_code == 202
    stopped = wait_for(client, running["id"])
    assert stopped["status"] == "canceled" and stopped["video"] is None and stopped["segments"] == [] and time.monotonic() - started < 4
    assert clip_files(client, running["id"]) == [] and not client.app.state.db.read_all("SELECT * FROM videos")
    assert client.get("/api/status").json()["worker"]["state"] == "ready"  # the worker is the same one, ready for the next
    assert wait_for(client, create_clip(client, "after the cancel")["id"])["status"] == "done"


def test_too_little_free_memory_fails_the_clip_at_once_with_the_usual_words_and_hint(client_factory, monkeypatch):
    client = client_factory(quiet=True, video_min_free_gb=60.0)
    wait_for_video_probe(client)
    accept_licence(client)
    monkeypatch.setattr(sysinfo, "memory", lambda: {"total_gb": 121.0, "available_gb": 5.0})
    assert client.get("/api/capabilities").json()["video"]["memory"]["ok"] is False
    failed = wait_for(client, create_clip(client)["id"])
    assert failed["status"] == "failed" and failed["error"]["message"] == "Not enough free memory to load the video model: 5.0 GB available, 60 GB required (STUDIO_VIDEO_MIN_FREE_GB)."
    assert "Hermes" in failed["error"]["hint"]
    monkeypatch.setattr(sysinfo, "memory", lambda: {"total_gb": 121.0, "available_gb": 80.0})
    assert wait_for(client, create_clip(client)["id"])["status"] == "done"
    # the check is made for every clip, not only for a worker that has just been started: the worker is alive now, and memory goes short again
    monkeypatch.setattr(sysinfo, "memory", lambda: {"total_gb": 121.0, "available_gb": 7.0})
    again = wait_for(client, create_clip(client)["id"])
    assert again["status"] == "failed" and "7.0 GB available" in again["error"]["message"]


def test_the_memory_check_is_off_for_the_fake_engine_unless_asked_for_and_0_turns_it_off(client_factory, monkeypatch):
    monkeypatch.setattr(sysinfo, "memory", lambda: {"total_gb": 121.0, "available_gb": 0.5})
    for setting in (None, 0.0):
        client = client_factory(quiet=True, video_min_free_gb=setting)
        wait_for_video_probe(client)
        accept_licence(client)
        assert wait_for(client, create_clip(client)["id"])["status"] == "done"


def test_the_real_engines_memory_check_is_what_was_measured_plus_four_and_the_settings_own_number_wins(client_factory):
    """Protects DESIGN.md §46.8: with the real pipeline the clip needs the engine's measured peak (55.6 GiB for 30 seconds on the Spark, kept as 56) and 4 GB for the programs beside it, unless
    STUDIO_VIDEO_MIN_FREE_GB says otherwise (0 turns the check off); the fake pipeline has no check unless asked, so that no test depends on the machine's memory."""
    client = client_factory(quiet=True)
    jobs = client.app.state.jobs
    measured = video_registry.info("ltx").memory_gb
    assert 55.6 <= measured <= 57  # the measured 55.6 GiB, rounded up
    assert jobs._video_needed_gb("fake") is None  # the fake pipeline: no check
    real = dataclasses.replace(jobs.settings, pipeline="real", video_min_free_gb=None)
    jobs.settings = real
    assert jobs._video_needed_gb("ltx") == pytest.approx(measured + 4.0) and jobs._video_needed_gb("no-such-engine") is None
    jobs.settings = dataclasses.replace(real, video_min_free_gb=33.0)
    assert jobs._video_needed_gb("ltx") == 33.0
    jobs.settings = dataclasses.replace(real, video_min_free_gb=0.0)
    assert jobs._video_needed_gb("ltx") is None


def test_a_clip_that_would_not_fit_on_the_disk_is_refused_with_the_figures_before_it_is_queued(client_factory):
    client = client_factory(quiet=True, video_min_free_disk_gb=10.0**9)
    wait_for_video_probe(client)
    accept_licence(client)
    refused = create_clip(client, expect=507)
    assert refused["code"] == "storage_full" and re.search(r"needs about \d+ MB of disk, and [\d.]+ (GB|MB) is free", refused["detail"]) and refused["hint"]
    assert client.get("/api/runs?kind=video").json()["runs"] == []


# ---------------------------------------------------------------- the models take turns (criterion 449)
def test_a_clip_unloads_the_image_model_to_make_room_and_the_next_picture_loads_it_again(video):
    wait_for(video, create_run(video, "a first picture")["id"])
    assert video.get("/api/status").json()["worker"]["model"] == "image"
    wait_for(video, create_clip(video)["id"])
    worker = video.get("/api/status").json()["worker"]
    assert (worker["model"], worker["engine"], worker["variant"]) == ("video", "fake", "distilled") and worker["state"] == "ready"
    wait_for(video, create_run(video, "a second picture")["id"])
    assert video.get("/api/status").json()["worker"]["model"] == "image"


def test_load_and_unload_work_for_the_video_model_and_check_what_they_are_asked(video):
    started = video.post("/api/model/load", json={"model": "video"})
    assert started.status_code in (200, 202)
    deadline = time.monotonic() + 10
    while video.get("/api/status").json()["worker"]["state"] != "ready" and time.monotonic() < deadline:
        time.sleep(0.02)
    worker = video.get("/api/status").json()["worker"]
    assert (worker["model"], worker["engine"], worker["variant"]) == ("video", "fake", "distilled")
    assert video.post("/api/model/unload", json={"model": "video"}).status_code == 200 and video.get("/api/status").json()["worker"]["state"] == "unloaded"
    assert video.post("/api/model/load", json={"model": "video", "engine": "nope"}).json()["code"] == "unknown_engine"
    assert video.post("/api/model/load", json={"model": "video", "engine": "fake", "variant": "huge"}).json()["code"] == "unknown_variant"
    assert video.post("/api/model/load", json={"model": "video", "variant": "dev"}).status_code in (200, 202)  # the other quality is another model: it is a model of its own


def test_changing_quality_is_changing_model_and_stops_the_loaded_worker_first(video):
    jobs = video.app.state.jobs
    assert jobs.model_id_for("video:fake:distilled") == "fake-video · distilled" and jobs.model_id_for("video:fake:dev") == "fake-video · dev"
    wait_for(video, create_clip(video)["id"])
    assert jobs._model == "video:fake:distilled"
    video.post("/api/model/load", json={"model": "video", "variant": "dev"})
    deadline = time.monotonic() + 10
    while jobs._model != "video:fake:dev" and time.monotonic() < deadline:
        time.sleep(0.02)
    assert jobs._model == "video:fake:dev"


# ---------------------------------------------------------------- a clip is a run (criteria 442, 459, 461)
def test_a_clip_can_be_kept_filed_in_a_project_tagged_and_noted_like_every_other_run(video):
    done = wait_for(video, create_clip(video, "a fox", sound="rain")["id"])
    assert done["pinned"] is False and done["expires_at"] is not None  # a clip expires as pictures and music do, unless it is kept
    assert video.patch(f"/api/runs/{done['id']}", json={"pinned": True}).json()["pinned"] is True
    project = video.post("/api/projects", json={"name": "Fox clips"}).json()
    filed = video.put(f"/api/runs/{done['id']}/project", json={"project_id": project["id"]}).json()
    assert filed["project_id"] == project["id"] and filed["pinned"] is True
    assert video.get("/api/projects").json()["projects"][0]["counts"]["video"] == 1
    tagged = video.put(f"/api/runs/{done['id']}/tags", json={"tags": ["winter", "fox"]}).json()
    assert tagged["tags"] == ["fox", "winter"] and tagged["mode"] == "video" and tagged["video"] is not None
    assert video.put(f"/api/runs/{done['id']}/notes", json={"notes": "the good one"}).json()["notes"] == "the good one"


def test_search_finds_the_words_what_you_hear_notes_and_tags_and_not_the_settings(video):
    done = wait_for(video, create_clip(video, "A heron on a frozen lake", sound="wind over ice, distant crows", seed=31337)["id"])
    video.put(f"/api/runs/{done['id']}/notes", json={"notes": "for the intro"})
    video.put(f"/api/runs/{done['id']}/tags", json={"tags": ["birds"]})
    other = wait_for(video, create_clip(video, "A tractor in a field")["id"])

    def found(text: str, **more: str) -> list[str]:
        return [r["id"] for r in video.get("/api/runs", params={"kind": "video", "q": text, **more}).json()["runs"]]

    assert found("heron") == [done["id"]] and found("crows") == [done["id"]] and found("intro") == [done["id"]] and found("birds") == [done["id"]]
    assert found("tractor") == [other["id"]] and found("heron crows") == [done["id"]] and found("heron tractor") == []
    for setting in ("draft", "distilled", "fake", "256", "31337", "24"):  # nothing of a clip's settings is searched (DESIGN.md §45.4 rule 1)
        assert found(setting) == [], setting
    assert video.get("/api/runs", params={"q": "crows"}).json()["runs"][0]["id"] == done["id"]  # on every tab's list too, with no kind named


def test_the_tab_has_its_own_counts_facets_and_model_filter(video):
    done = wait_for(video, create_clip(video)["id"])
    wait_for(video, create_run(video, "a picture")["id"])
    counts = video.get("/api/runs/counts").json()
    assert counts["video"] == {"all": 1, "kept": 0, "deleted": 0, "deleted_items": 0} and counts["image"]["all"] == 1
    facets = video.get("/api/runs/facets", params={"kind": "video"}).json()
    assert facets == {"models": [{"value": "fake-video · distilled", "count": 1}], "sizes": []}  # no Size on Video in 1.27 (§46.11)
    assert [r["id"] for r in video.get("/api/runs", params={"kind": "video", "model": "fake-video · distilled"}).json()["runs"]] == [done["id"]]
    assert video.get("/api/runs", params={"kind": "video", "model": "fake-pipeline"}).json()["runs"] == []
    assert [r["id"] for r in video.get("/api/runs", params={"kind": "image"}).json()["runs"]] == [r["id"] for r in video.get("/api/runs", params={"kind": "image"}).json()["runs"] if r["mode"] != "video"]


def test_delete_sends_a_clip_to_the_bin_and_delete_forever_removes_every_file_and_row(video):
    root = video.app.state.storage.root
    done = wait_for(video, create_clip(video)["id"])
    assert video.post(f"/api/runs/{done['id']}/bin").status_code == 200
    assert (root / "video" / done["id"] / "clip.mp4").is_file()  # in the bin its files stay: Restore needs them
    assert video.get("/api/runs/counts").json()["video"]["deleted"] == 1
    assert video.delete(f"/api/runs/{done['id']}").status_code == 204
    assert not (root / "video" / done["id"]).exists() and not (root / "thumbs" / done["id"]).exists()
    db = video.app.state.db
    assert db.read_all("SELECT * FROM videos") == [] and db.read_all("SELECT * FROM video_segments") == []


def test_empty_bin_and_the_daily_clean_up_take_a_clips_files_through_the_one_place_they_go(client_factory):
    client = client_factory(quiet=True, retention_days=1)
    wait_for_video_probe(client)
    accept_licence(client)
    root = client.app.state.storage.root
    old = wait_for(client, create_clip(client, "an old one")["id"])
    kept = wait_for(client, create_clip(client, "a kept one")["id"])
    client.patch(f"/api/runs/{kept['id']}", json={"pinned": True})
    with client.app.state.db.tx() as c:  # both were made long ago
        c.execute("UPDATE runs SET created_at='2020-01-01T00:00:00.000Z'")
    jobs = client.app.state.jobs
    client.portal.call(jobs.sweep_expired)
    assert client.get(f"/api/runs/{old['id']}").json()["deleted_at"] is not None and client.get(f"/api/runs/{kept['id']}").json()["deleted_at"] is None  # expired to the bin; kept stays
    assert client.delete("/api/bin").json()["deleted"] == 1
    assert not (root / "video" / old["id"]).exists() and (root / "video" / kept["id"] / "clip.mp4").is_file()


def test_retry_makes_the_same_clip_again_and_the_queue_title_is_the_words(video):
    failed = wait_for(video, create_clip(video, "will fail [fake:error]", seed=5)["id"])
    assert failed["status"] == "failed"
    queued = create_clip(video, "will not fail", seed=5)
    assert video.get(f"/api/runs/{queued['id']}").json()["options"]["seed"] == 5
    assert wait_for(video, queued["id"])["status"] == "done"


# ---------------------------------------------------------------- how long clips took here (DESIGN.md §46.8, as changed)
def estimate_of(client) -> dict:
    return client.get("/api/capabilities").json()["limits"]["video"]["estimate"]


def test_the_estimate_carries_the_times_of_the_clips_made_here_newest_first_and_only_of_clips_that_were_made(video):
    assert estimate_of(video)["history"] == [] and estimate_of(video)["buckets"] == [5, 10, 20, 30]  # nothing made yet: the page uses the table
    first = wait_for(video, create_clip(video, "first", seconds=2, width=256, height=128)["id"])
    second = wait_for(video, create_clip(video, "second", seconds=1, width=320, height=192)["id"])
    wait_for(video, create_clip(video, "failing [fake:error]")["id"])  # a clip that failed took time too, and says nothing about how long one takes
    canceled = create_clip(video, "slow [fake:slow]")
    video.post(f"/api/runs/{canceled['id']}/cancel")
    wait_for(video, canceled["id"])
    history = estimate_of(video)["history"]
    assert [(h["seconds"], h["width"], h["height"], h["fps"]) for h in history] == [(1.0, 320, 192, 24), (2.0, 256, 128, 24)]  # the second clip first
    assert all(h["took"] > 0 for h in history)
    # `took` is what the person waited: from the run's start to its end, as the run itself says
    seconds = lambda run: (parse_ts(run["finished_at"]) - parse_ts(run["started_at"])).total_seconds()  # noqa: E731
    assert history[0]["took"] == pytest.approx(seconds(second), abs=0.06) and history[1]["took"] == pytest.approx(seconds(first), abs=0.06)


def test_the_estimate_goes_by_the_last_forty_clips_and_no_more(video):
    """DESIGN.md §46.8: the page needs the recent clips, not every clip there has ever been (a machine's speed changes: a new driver, natten); the server sends the last 40, newest first."""
    base = parse_ts(wait_for(video, create_clip(video, "one real clip")["id"])["finished_at"])
    with video.app.state.db.tx() as c:
        for n in range(45):  # 45 more clips that took n + 1 seconds each, finished one second apart after the real one
            finished = (base + timedelta(seconds=n + 1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            started = base.strftime("%Y-%m-%dT%H:%M:%S.000Z")  # all started when the real one finished, so that clip n took n + 1 seconds
            c.execute("INSERT INTO runs (id, created_at, started_at, finished_at, status, mode, prompt, effective_prompt, steps, seed, num_images, model_id, options_json, width, height) "
                      "VALUES (?, ?, ?, ?, 'done', 'video', 'p', 'p', 8, 1, 1, 'fake-video · distilled', ?, 256, 128)",
                      (f"{n:032x}", started, started, finished, json.dumps({"seconds": 1.0, "width": 256, "height": 128, "fps": 24}),))
    history = estimate_of(video)["history"]
    assert len(history) == 40
    assert [h["took"] for h in history][:3] == [45.0, 44.0, 43.0] and history[-1]["took"] == 6.0  # the newest forty of the 46, the newest first


def test_a_clip_in_the_bin_still_counts_but_a_clip_of_another_engine_does_not(video):
    done = wait_for(video, create_clip(video, "binned")["id"])
    video.post(f"/api/runs/{done['id']}/bin")
    assert len(estimate_of(video)["history"]) == 1  # how long it took is still true
    with video.app.state.db.tx() as c:
        c.execute("UPDATE runs SET model_id='Lightricks/LTX-2.5 · distilled' WHERE id=?", (done["id"],))  # as if the real engine had made it
    assert estimate_of(video)["history"] == []  # this engine's estimate is from this engine's clips


def test_a_finished_clip_tells_every_open_page_so_that_each_estimates_from_it(video):
    seen = record_events(video)
    wait_for(video, create_clip(video)["id"])
    assert [data for event, data in seen if event == "capabilities.updated"]  # one more measured time: the pages ask for the capabilities again
    seen.clear()
    wait_for(video, create_clip(video, "fails [fake:error]")["id"])
    assert not [data for event, data in seen if event == "capabilities.updated"]  # a failure measured nothing


# ---------------------------------------------------------------- Check again (DESIGN.md §46.8, phase 2)
@pytest.fixture
def broken(client_factory, monkeypatch):
    """A server whose video program cannot be found (the fake engine's way of saying so), after its start-up check has finished: the state a person is in before they put something right."""
    monkeypatch.setenv("STUDIO_FAKE_VIDEO_UNAVAILABLE", "1")
    client = client_factory(quiet=True)
    assert wait_for_video_probe(client)["state"] == "unavailable"
    monkeypatch.setattr(JobManager, "VIDEO_CHECK_SECONDS", 0.0)  # (the rate limit has its own test)
    return client


def test_check_again_finds_what_was_put_right_without_a_restart_and_tells_every_open_page(broken, monkeypatch):
    seen = record_events(broken)
    monkeypatch.delenv("STUDIO_FAKE_VIDEO_UNAVAILABLE")  # the person has fixed it
    started = broken.post("/api/video/check")
    assert started.status_code == 202 and started.json() == {"started": True, "state": "checking"}
    assert broken.get("/api/capabilities").json()["video"]["state"] in ("checking", "ready")  # it says so while it looks, and the tab is not offered a form for it
    caps = wait_for_video_probe(broken)
    assert caps["state"] == "ready" and caps["available"] is True and caps["reason"] is None
    assert "video" in broken.get("/api/capabilities").json()["modes"]
    updates = [data["video"]["state"] for event, data in seen if event == "capabilities.updated"]
    assert updates[0] == "checking" and updates[-1] == "ready"  # the pages heard when it began and when it ended
    accept_licence(broken)
    assert wait_for(broken, create_clip(broken)["id"])["status"] == "done"  # and a clip can be made now


def test_check_again_that_finds_it_still_wrong_says_the_same_reason_and_does_not_hang_on_checking(broken):
    reason = broken.get("/api/capabilities").json()["video"]["reason"]
    assert broken.post("/api/video/check").status_code == 202
    caps = wait_for_video_probe(broken)
    assert caps["state"] == "unavailable" and caps["reason"] == reason and caps["available"] is False


def test_pressing_it_again_inside_the_limit_is_a_429_in_words_and_after_it_is_allowed(broken, monkeypatch):
    monkeypatch.setattr(JobManager, "VIDEO_CHECK_SECONDS", 3600.0)
    assert broken.post("/api/video/check").status_code == 202
    wait_for_video_probe(broken)
    again = broken.post("/api/video/check")
    assert again.status_code == 429 and again.json()["code"] == "video_check_too_soon"
    assert "was checked" in again.json()["detail"] and "Wait" in again.json()["hint"]
    monkeypatch.setattr(JobManager, "VIDEO_CHECK_SECONDS", 0.0)
    assert broken.post("/api/video/check").status_code == 202


def test_a_check_that_is_under_way_is_not_started_twice(broken):
    broken.app.state.jobs._video_probes["fake"] = {"state": "checking"}  # as it is while the first press (or the start-up check) is still looking
    answer = broken.post("/api/video/check")
    assert answer.status_code == 202 and answer.json() == {"started": False, "state": "checking"}


def test_a_check_is_refused_while_a_clip_is_being_made(video):
    video.app.state.jobs.VIDEO_CHECK_SECONDS = 0.0
    running = create_clip(video, "slow [fake:slow]")
    deadline = time.monotonic() + 10
    while video.get(f"/api/runs/{running['id']}").json()["status"] != "running" and time.monotonic() < deadline:
        time.sleep(0.02)
    refused = video.post("/api/video/check")
    assert refused.status_code == 409 and refused.json()["code"] == "video_busy" and refused.json()["hint"] == "Check again when it is done."
    video.post(f"/api/runs/{running['id']}/cancel")
    wait_for(video, running["id"])
    assert video.post("/api/video/check").status_code == 202  # and when it is done, it is allowed


def test_a_check_looks_for_ffmpeg_again(broken, monkeypatch):
    """A program installed or made runnable since the start-up check is found: the answer about ffmpeg is not kept for ever."""
    monkeypatch.delenv("STUDIO_FAKE_VIDEO_UNAVAILABLE")
    jobs = broken.app.state.jobs
    jobs.video._tools = media.Tools(ffmpeg=False, ffprobe=False)  # what the start-up check found, before it was installed
    assert broken.get("/api/capabilities").json()["video"]["tools"] == {"ffmpeg": False, "ffprobe": False}
    broken.post("/api/video/check")
    caps = wait_for_video_probe(broken)
    assert caps["tools"] == {"ffmpeg": True, "ffprobe": True} and caps["available"] is True


def test_a_check_that_itself_goes_wrong_ends_in_words_and_not_in_checking_for_ever(broken, monkeypatch):
    async def explode(self, engine_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(JobManager, "_probe_video_engine", explode)
    broken.post("/api/video/check")
    caps = wait_for_video_probe(broken)
    assert caps["state"] == "unavailable" and caps["reason"] == "The video check could not be run: boom" and caps["hint"] == "See the server's log."


# ---------------------------------------------------------------- what is NOT in 1.27 (DESIGN.md §46.16): each is absent from the API, not only from the page
def test_final_quality_is_not_offered_or_accepted(video):
    caps = video.get("/api/capabilities").json()
    assert [q["id"] for q in caps["video"]["qualities"] if q["available"]] == ["draft"]
    assert caps["limits"]["video"]["qualities"] == {"default": "draft", "offered": ["draft"]}
    refused = video.post("/api/runs", json=clip_body_with(quality="final"))
    assert refused.status_code == 422 and refused.json()["detail"][0]["loc"] == ["body", "options", "quality"] and "not offered" in refused.json()["detail"][0]["msg"]
    assert video.post("/api/model/load", json={"model": "video", "variant": "dev"}).status_code in (200, 202)  # (the test engine has a second variant; the real one has only `distilled`)
    assert media_variants() == ("distilled",)  # the real engine knows no dev checkpoint, so the page can never be offered one


def test_an_end_picture_a_chain_of_clips_and_the_programs_chunked_mode_are_not_offered(video):
    limits = video.get("/api/capabilities").json()["limits"]["video"]
    assert limits["images"] == {"start": 1, "end": 0}  # one start picture, no end picture
    assert video.get("/api/capabilities").json()["video"]["chaining"]["available"] is False
    refused = video.post("/api/runs", json=clip_body_with(segments=3))
    assert refused.status_code == 422 and refused.json()["detail"][0]["loc"] == ["body", "options", "segments"]
    one, two = stage(video, image_bytes()), stage(video, image_bytes((9, 9, 9)))
    both = video.post("/api/runs", json={**clip_body_with(), "input_images": [{"upload_id": one["upload_id"]}, {"upload_id": two["upload_id"]}]})
    assert both.status_code == 422 and both.json()["detail"][0]["type"] == "too_many_images"  # a second picture would be an end picture
    # an option of a later release is refused by name (the request model forbids what it does not know), not ignored and not stored
    for name, value in (("end", {"image": 2}), ("continued_from", "x"), ("chunked", True), ("captions", True)):
        answer = video.post("/api/runs", json=clip_body_with(**{name: value}))
        assert answer.status_code == 422, name
        assert answer.json()["detail"][0]["type"] == "extra_forbidden" and answer.json()["detail"][0]["loc"] == ["body", "options", name]
    assert video.get("/api/runs?kind=video").json()["runs"] == []  # nothing was queued by any of the refusals


def test_the_program_is_never_run_in_chunked_mode_unless_the_person_asked_for_it_in_the_extra_arguments(tmp_path):
    from studio.video.engines.ltx import build_command
    from video_support import models_folder, program_config, request
    from studio.video.engines.ltx_files import find_files

    config = program_config(models_folder(tmp_path / "models"))
    files, _ = find_files(config.models_path(), config.files)
    argv = build_command(("python", "-m", "ltx_pipelines.distilled"), config, files, request(tmp_path / "o.mp4"))
    assert "--chunked" not in argv and "--quantization" not in argv and "--offload" not in argv  # only what the settings ask for
    asked = build_command(("python", "-m", "ltx_pipelines.distilled"), program_config(models_folder(tmp_path / "m2"), extra_args=("--chunked",)), files, request(tmp_path / "o.mp4"))
    assert asked[-1] == "--chunked"  # and then last, as the person wrote it


def clip_body_with(**options):
    return {"mode": "video", "prompt": "a fox", "options": {"width": 256, "height": 128, "seconds": 1, **options}}


def media_variants() -> tuple:
    from studio.video import registry

    return registry.info("ltx").variants


# ---------------------------------------------------------------- retention: a clip expires like a picture, and kept ones never do (DESIGN.md §46.9)
def aged(client, *run_ids, created="2020-01-01T00:00:00.000Z", deleted_at=None):
    with client.app.state.db.tx() as c:
        for run_id in run_ids:
            c.execute("UPDATE runs SET created_at=?, deleted_at=? WHERE id=?", (created, deleted_at, run_id))


def test_a_clip_expires_after_the_retention_days_unless_it_is_kept_or_filed_and_waits_in_the_bin_before_it_goes(client_factory):
    client = client_factory(quiet=True, retention_days=30, bin_days=7)
    wait_for_video_probe(client)
    accept_licence(client)
    root = client.app.state.storage.root
    plain, kept, filed, fresh = (wait_for(client, create_clip(client, name)["id"]) for name in ("plain", "kept", "filed", "fresh"))
    client.patch(f"/api/runs/{kept['id']}", json={"pinned": True})
    project = client.post("/api/projects", json={"name": "Foxes"}).json()
    client.put(f"/api/runs/{filed['id']}/project", json={"project_id": project["id"]})
    aged(client, plain["id"], kept["id"], filed["id"])  # three clips made long ago; the fourth is new
    assert client.portal.call(client.app.state.jobs.sweep_expired) == 0  # nothing is deleted for good yet: the old plain clip goes to the bin
    state = {name: client.get(f"/api/runs/{run['id']}").json()["deleted_at"] is not None for name, run in (("plain", plain), ("kept", kept), ("filed", filed), ("fresh", fresh))}
    assert state == {"plain": True, "kept": False, "filed": False, "fresh": False}
    assert (root / "video" / plain["id"] / "clip.mp4").is_file()  # in the bin its files stay, so that Restore works
    aged(client, plain["id"], deleted_at="2020-01-02T00:00:00.000Z")  # and it has been there for longer than the bin keeps things
    assert client.portal.call(client.app.state.jobs.sweep_expired) == 1
    assert client.get(f"/api/runs/{plain['id']}").status_code == 404
    assert not (root / "video" / plain["id"]).exists() and not (root / "thumbs" / plain["id"]).exists()  # every file of it, through the one place files go
    for survivor in (kept, filed, fresh):
        assert (root / "video" / survivor["id"] / "clip.mp4").is_file()


def test_with_retention_switched_off_no_clip_ever_expires(client_factory):
    client = client_factory(quiet=True, retention_days=0)
    wait_for_video_probe(client)
    accept_licence(client)
    run = wait_for(client, create_clip(client)["id"])
    aged(client, run["id"])
    client.portal.call(client.app.state.jobs.sweep_expired)
    assert client.get(f"/api/runs/{run['id']}").json()["deleted_at"] is None
    assert run["expires_at"] is None or run["expires_at"] > "2020"  # (it also says so on the card: nothing to warn about)


def test_a_restored_clip_plays_again_and_is_not_swept_at_once(video):
    run = wait_for(video, create_clip(video)["id"])
    video.post(f"/api/runs/{run['id']}/bin")
    assert video.get(run["video"]["url"]).status_code == 404
    restored = video.post(f"/api/runs/{run['id']}/restore")
    assert restored.status_code == 200 and restored.json()["deleted_at"] is None
    assert video.get(run["video"]["url"]).status_code == 200


def test_a_clip_whose_sound_and_picture_differ_by_more_than_a_tenth_of_a_second_carries_the_note_and_is_still_a_finished_clip(video, monkeypatch):
    """Criterion 487: the file is finished and playable; the note is for the person. (The fake engine's sound is 30 ms short, which gets none: the test below the rule is in test_video_fake_engine.)"""
    plain = wait_for(video, create_clip(video)["id"])
    assert plain["video"]["note"] is None  # the fake engine's own few ms are how the file is made
    monkeypatch.setattr("studio.video.service.sync_note", lambda facts: "The sound and the picture differ by 250 ms: the sound stops early.")
    noted = wait_for(video, create_clip(video, "noted")["id"])
    assert noted["status"] == "done" and noted["video"]["note"] == "The sound and the picture differ by 250 ms: the sound stops early."
    assert video.get(noted["video"]["url"]).status_code == 200
