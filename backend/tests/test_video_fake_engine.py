"""The fake video engine (DESIGN.md §46.6, criteria 443 and 444): it is the test engine, so what the other tests rely on is tried here once. It must write a REAL MP4 with a REAL sound
track, of the size, frames and rate asked for, the same bytes for the same request and other bytes for another seed; a start picture must be the first frame; it must say what the real
program says (the stages and the step counts), and fail, run out of memory, be slow, be silent and stop for Cancel when asked to. Also: a new engine is one file and one line."""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path

import pytest
from PIL import Image
from video_support import request

from studio.pipelines.base import Canceled, OutOfMemory, PipelineError, PipelineUnavailable
from studio.video import media, registry
from studio.video.engine import ConditioningImage, EngineBase, EngineConfig, VideoEngineInfo
from studio.video.engines import fake, ltx
from studio.video.engines.fake import FakeVideo

needs_ffmpeg = pytest.mark.skipif(not media.find_tools().ok, reason="ffmpeg and ffprobe are not installed here")
BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent


def engine(delay: int = 0) -> FakeVideo:
    return FakeVideo(EngineConfig(step_delay_ms=delay))


def make(tmp_path: Path, name: str = "a.mp4", **changes):
    events: list[tuple[str, int, int]] = []
    clip = engine().generate(request(tmp_path / name, **changes), lambda *e: events.append(e), lambda: False)
    return Path(clip.path), events


@needs_ffmpeg
def test_the_clip_is_a_real_mp4_with_a_stereo_48k_sound_track_of_the_size_frames_and_rate_asked_for(tmp_path):
    path, _ = make(tmp_path, width=320, height=192, frames=49, fps=24)
    facts = media.probe_clip("ffprobe", path)
    assert (facts.width, facts.height, facts.frames, facts.fps) == (320, 192, 49, 24.0)
    assert facts.video_codec == "h264" and facts.pixel_format == "yuv420p"
    assert (facts.has_audio, facts.audio_codec, facts.audio_channels, facts.audio_rate) == (True, "aac", 2, 48000)
    assert facts.seconds == pytest.approx(49 / 24, abs=0.01)
    assert facts.playable_everywhere


@needs_ffmpeg
def test_the_same_request_gives_the_same_bytes_and_another_seed_or_another_prompt_gives_other_bytes(tmp_path):
    a, _ = make(tmp_path, "a.mp4", seed=5)
    b, _ = make(tmp_path, "b.mp4", seed=5)
    c, _ = make(tmp_path, "c.mp4", seed=6)
    d, _ = make(tmp_path, "d.mp4", seed=5, prompt="a heron on a lake")
    assert a.read_bytes() == b.read_bytes()
    assert a.read_bytes() != c.read_bytes() and a.read_bytes() != d.read_bytes()


@needs_ffmpeg
def test_a_silent_directive_writes_no_sound_track_and_the_facts_say_so(tmp_path):
    path, _ = make(tmp_path, prompt="a fox [fake:silent]")
    facts = media.probe_clip("ffprobe", path)
    assert facts.has_audio is False and facts.audio_codec is None and facts.frames == 25


@needs_ffmpeg
def test_a_start_picture_is_the_first_frame_of_the_clip(tmp_path):
    """The point of the picture in the fake: a test can see that image to video carried a picture across (DESIGN.md §46.6). The first frame is the picture, up to compression."""
    picture = tmp_path / "start.png"
    Image.new("RGB", (256, 128), (200, 30, 30)).save(picture)
    path, _ = make(tmp_path, images=(ConditioningImage(str(picture), 0, 1.0),))
    frame = tmp_path / "f0.png"
    media.make_poster("ffmpeg", path, tmp_path / "f0.jpg")
    first = Image.open(tmp_path / "f0.jpg").convert("RGB")
    assert first.size == (256, 128)
    r, g, b = first.getpixel((40, 40))
    assert abs(r - 200) < 12 and abs(g - 30) < 12 and abs(b - 30) < 12
    # and a clip with no picture is not that colour
    plain, _ = make(tmp_path, "plain.mp4")
    media.make_poster("ffmpeg", plain, tmp_path / "p0.jpg")
    pr, pg, pb = Image.open(tmp_path / "p0.jpg").convert("RGB").getpixel((40, 40))
    assert not (abs(pr - 200) < 40 and abs(pg - 30) < 40 and abs(pb - 30) < 40) and frame is not None


def test_a_start_picture_that_is_not_there_is_an_error_and_not_a_crash(tmp_path):
    with pytest.raises(PipelineError, match="start picture is not there"):
        make(tmp_path, images=(ConditioningImage(str(tmp_path / "gone.png"), 0, 1.0),))


@needs_ffmpeg
def test_it_reports_the_real_programs_stages_in_order_with_the_real_step_counts(tmp_path):
    _, events = make(tmp_path)
    stages = [stage for stage, _, _ in events]
    assert [s for i, s in enumerate(stages) if i == 0 or s != stages[i - 1]] == ["start", "text", "denoise", "upscale", "refine", "decode", "write"]
    assert [e for e in events if e[0] == "denoise" and e[1] and e[1] == e[2]] == [("denoise", 8, 8)] and ("refine", 3, 3) in events and events[-1] == ("write", 1, 1)


@pytest.mark.parametrize("word, kind, says", [("[fake:error]", PipelineError, "RuntimeError: the fake video program was told to fail"), ("[fake:oom]", OutOfMemory, "more memory than was free")])
def test_a_failure_is_made_the_way_the_real_engines_are_so_its_words_are_the_real_ones(tmp_path, word, kind, says):
    with pytest.raises(kind) as caught:
        make(tmp_path, prompt=f"a fox {word}")
    assert says in caught.value.message and (type(caught.value) is OutOfMemory) == (kind is OutOfMemory)
    assert not (tmp_path / "a.mp4").exists()


def test_a_slow_clip_stops_for_cancel_within_a_slice_and_leaves_no_file(tmp_path):
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()
    started = time.monotonic()
    with pytest.raises(Canceled):
        engine().generate(request(tmp_path / "s.mp4", prompt="a fox [fake:slow]"), lambda *e: None, stop.is_set)
    assert time.monotonic() - started < 2.5 and not (tmp_path / "s.mp4").exists()  # not the six seconds it would take
    with pytest.raises(Canceled):  # a Cancel pressed before it starts stops it before anything is made
        engine().generate(request(tmp_path / "t.mp4"), lambda *e: None, lambda: True)


def test_the_progress_callback_can_cancel_too(tmp_path):
    def on_progress(stage: str, step: int, steps: int) -> None:
        if stage == "denoise" and step == 3:
            raise Canceled()

    with pytest.raises(Canceled):
        engine().generate(request(tmp_path / "c.mp4"), on_progress, lambda: False)


def test_the_fake_probe_and_load_need_only_ffmpeg(monkeypatch):
    config = EngineConfig()
    assert FakeVideo.probe(config) == {"device": "fake"} if media.find_tools().ok else True
    monkeypatch.setattr(media, "find_tools", lambda *a: media.Tools(ffmpeg=False, ffprobe=False))
    with pytest.raises(PipelineUnavailable, match="ffmpeg and ffprobe are not installed"):
        FakeVideo.probe(config)
    monkeypatch.setenv("STUDIO_FAKE_VIDEO_UNAVAILABLE", "1")  # what a test sets to see the page cope with a machine that cannot make clips
    with pytest.raises(PipelineUnavailable, match="not installed"):
        FakeVideo.probe(config)
    assert FakeVideo(config).load() == {"device": "fake"}


def test_the_fake_engine_says_what_it_is_in_the_records_the_page_reads():
    info = fake.INFO
    assert info.id == "fake" and info.variants == ("distilled", "dev") and info.size_multiple == 64 and info.estimate.kind == "stand-in"
    assert info.licence.revision == "fake-1" and info.licence.statement and info.as_dict()["licence"]["name"] == "Test licence"


# ---------------------------------------------------------------- the registry (criterion 443)
class ToyVideo(EngineBase):
    """An engine that exists only in this test: one class in one place is all a new model needs."""

    INFO = VideoEngineInfo(id="toy", title="Toy", licence=fake.INFO.licence, model_id="toy/model", variants=("a",), default_variant="a", memory_gb=1.0, size_multiple=64, size_min=64, size_max=256,
                           size_default=(64, 64), size_presets=(), fps_choices=(8,), estimate=fake.INFO.estimate, bytes_per_second=1.0)

    @classmethod
    def probe(cls, config):
        return {"device": "toy"}


def test_a_new_engine_is_one_class_and_one_line_and_the_fakes_are_all_the_fake_pipeline_offers():
    assert registry.engine_ids("fake") == ["fake"] and registry.engine_ids("real") == ["ltx"] and registry.primary("fake") == "fake"
    registry.register(ToyVideo)
    try:
        assert registry.engine_ids("fake") == ["fake", "toy"] and registry.info("toy").title == "Toy" and registry.probe_engine("toy", EngineConfig()) == {"device": "toy"}
        assert registry.make_engine("toy", EngineConfig()).name == "toy"
        with pytest.raises(registry.UnknownEngine):
            registry.make_engine("toy", EngineConfig(), "no-such-variant")
    finally:
        registry.unregister("toy")
    assert "toy" not in registry.engine_ids("fake")
    with pytest.raises(registry.UnknownEngine):
        registry.engine_class("nope")


def test_no_code_names_an_engine_outside_the_registry_and_the_engine_files():
    """Criterion 443 is a promise about the whole code base, so it is checked against the source: the real engine's id written as a string anywhere else (the queue, the worker, the
    database, the API, the page) is a place that would need editing for the next model. Prose and comments are fine; so are settings, whose names say video and not the model."""
    names = re.compile(r"""["'`]ltx["'`]""")
    offenders = []
    for root in (BACKEND / "studio", REPO / "frontend" / "src"):
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx"} or ("engines" in path.parts and "video" in path.parts) or path.name == "registry.py" or "test" in path.name.lower():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if names.search(line):
                    offenders.append(f"{path.relative_to(REPO)}:{number}: {line.strip()[:80]}")
    assert not offenders, "\n".join(offenders)
    assert ltx.INFO.id == "ltx"
