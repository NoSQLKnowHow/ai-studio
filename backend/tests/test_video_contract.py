"""The Video tab's contract file (DESIGN.md §46.10, as §38.9 does for Speech and §31.12 for Vector): `video_contract.json` is what the server sends, captured from a real run of
the fake video engine, and the page's tests build their fixtures from it and compare its keys with the page's types. This file is the server's half: it makes the same captures
again and fails if the keys or the kinds of value have moved, so the page cannot be tested against an answer the server no longer gives.

Only the shape is compared (the keys at every depth, and the kind of value where both sides have one), never the values: ids, times and sizes differ on every run.
To change the contract on purpose, run this file once with UPDATE_VIDEO_CONTRACT=1, look at what changed in the diff, and update the page's types to match.

The captures need a real ffmpeg (a clip is a real MP4), so the file is skipped where there is none; the contract file itself is made on a machine that has it.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import image_bytes, stage, wait_for
from test_speech_contract import key_paths, kinds
from video_support import accept_licence, create_clip, record_events, wait_for_video_probe

from studio.video import media
from studio.video import options as video_options
from studio.video import routes

pytestmark = pytest.mark.skipif(not media.find_tools().ok, reason="ffmpeg and ffprobe are not installed here")

CONTRACT = Path(__file__).parent / "video_contract.json"

# The bodies the page sends. The licence body refuses a key it does not know (`extra="forbid"`), so its fields are the request's contract. A clip is asked for with
# `POST /api/runs`, whose `options` the server reads by name: the names that mean something to a clip are the contract of that part of the request.
REQUEST_FIELDS = {
    "licence": sorted(routes.LicenceBody.model_fields),
    "run_options": sorted(set(video_options.ONLY_FOR_VIDEO) | {"width", "height", "seed"}),
}


def build(client) -> dict[str, Any]:
    """Make each answer the page reads, in one scenario the same way every time, and return them by name."""
    caps = wait_for_video_probe(client)
    out: dict[str, Any] = {"requests": REQUEST_FIELDS, "capabilities_video_unaccepted": caps, "limits_video": client.get("/api/capabilities").json()["limits"]["video"]}
    out["licence_refusal"] = create_clip(client, expect=409)
    out["licence_answer"] = accept_licence(client)
    out["capabilities_video"] = client.get("/api/capabilities").json()["video"]
    out["licence_withdrawn"] = client.delete("/api/video/licence").json()
    accept_licence(client)

    events = record_events(client)
    # a clip from words, with what you hear, and the events of its making
    text = create_clip(client, "a fox in the snow", sound="snow crunching", seconds=1, seed=77)
    out["run_queued"] = text
    out["run_text"] = wait_for(client, text["id"])
    out["progress_event"] = next(data for event, data in events if event == "run.progress" and data["id"] == text["id"] and data["progress"]["stage"] == "denoise")
    # a clip from a picture: the start picture is an input, `start` says so, and the answer has the picture's own facts
    red = stage(client, image_bytes((200, 30, 30), size=(100, 100)))
    out["run_image"] = wait_for(client, create_clip(client, "the red room", pictures=[{"upload_id": red["upload_id"]}])["id"])
    # a clip with no sound track (a note, not a failure) and one that failed (the words and the hint)
    out["run_silent"] = wait_for(client, create_clip(client, "a quiet fox [fake:silent]")["id"])
    out["run_failed"] = wait_for(client, create_clip(client, "a fox [fake:error]")["id"])
    # the queue while one clip makes and another waits, and a clip canceled while it ran
    running = create_clip(client, "slow one [fake:slow]")
    waiting = create_clip(client, "waiting one")
    deadline = time.monotonic() + 10
    while client.get(f"/api/runs/{running['id']}").json()["status"] != "running" and time.monotonic() < deadline:
        time.sleep(0.02)
    out["queue"] = client.get("/api/queue").json()
    client.post(f"/api/runs/{running['id']}/cancel")
    out["run_canceled"] = wait_for(client, running["id"])
    wait_for(client, waiting["id"])
    out["counts"] = client.get("/api/runs/counts").json()["video"]
    out["facets"] = client.get("/api/runs/facets", params={"kind": "video"}).json()
    out["list"] = client.get("/api/runs", params={"kind": "video", "limit": 2}).json()
    # the limits again, now that clips have been made here: the estimate carries their times (DESIGN.md §46.8, as changed), which the page computes the next clip's time from
    out["limits_video_with_history"] = client.get("/api/capabilities").json()["limits"]["video"]
    return out


@pytest.fixture
def video(client_factory):
    return client_factory(quiet=True)


def test_the_contract_file_is_what_the_server_sends(video):
    live = build(video)
    if os.environ.get("UPDATE_VIDEO_CONTRACT") == "1":
        CONTRACT.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stored = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert set(stored) == set(live), "the contract names other answers than the test makes"
    assert stored["requests"] == live["requests"], "a field of a request has been added, removed or renamed (run with UPDATE_VIDEO_CONTRACT=1, then update the page)"
    for name in sorted(set(live) - {"requests"}):
        assert key_paths(stored[name]) == key_paths(live[name]), f"{name}: the keys have changed (run with UPDATE_VIDEO_CONTRACT=1, then update the page's types)"
        live_kinds, stored_kinds = kinds(live[name]), kinds(stored[name])
        for path in sorted(set(live_kinds) & set(stored_kinds)):
            assert live_kinds[path] == stored_kinds[path], f"{name}.{path}: the kind of value has changed"


def test_the_contract_covers_each_state_the_page_has_to_draw(video):
    """A fixture is only as good as what it holds: each optional key has a value somewhere in it, so a key the page's type lacks shows up."""
    stored = json.loads(CONTRACT.read_text(encoding="utf-8"))
    text, image, silent, failed = stored["run_text"], stored["run_image"], stored["run_silent"], stored["run_failed"]
    assert text["mode"] == "video" and text["status"] == "done" and text["video"]["has_audio"] is True and text["video"]["url"] and text["video"]["poster_url"] and text["segments"]
    assert text["options"]["sound"] and text["options"]["start"] is None and text["effective_prompt"] != text["prompt"]
    assert image["options"]["mode"] == "image" and image["options"]["start"] == {"image": 1, "frame": 0, "strength": 1.0} and image["inputs"]
    assert silent["video"]["has_audio"] is False and silent["video"]["note"] and silent["video"]["audio_channels"] is None
    assert failed["status"] == "failed" and failed["error"]["message"] and failed["error"]["hint"] and failed["video"] is None
    assert stored["run_canceled"]["status"] == "canceled" and stored["run_queued"]["video"] is None
    assert stored["queue"]["running"]["kind"] == "video" and stored["queue"]["queued"]
    caps = stored["capabilities_video"]
    assert caps["licence"]["accepted"] is True and stored["capabilities_video_unaccepted"]["licence"]["accepted"] is False and caps["qualities"] and caps["engine"]["id"] == "fake"
    assert stored["licence_refusal"]["code"] == "licence_not_accepted" and stored["licence_refusal"]["hint"]
    assert stored["limits_video"]["estimate"]["points"] and stored["progress_event"]["progress"]["stage"] == "denoise"
    assert stored["limits_video"]["estimate"]["history"] == [] and stored["limits_video"]["estimate"]["buckets"] == [5, 10, 20, 30]
    history = stored["limits_video_with_history"]["estimate"]["history"]
    assert history and all(set(entry) == {"seconds", "width", "height", "fps", "took"} for entry in history)  # a made clip's time: what was asked for, and how long it took
