"""The fake video engine (DESIGN.md §46.6, criteria 443 and 444): it is the test engine, so what the other tests rely on is tried here once. It must write a REAL MP4 with a REAL sound
track, of the size, frames and rate asked for, the same bytes for the same request and other bytes for another seed; a start picture must be the first frame; it must say what the real
program says (the stages and the step counts), and fail, run out of memory, be slow, be silent and stop for Cancel when asked to. Also: a new engine is one file and one line."""

from __future__ import annotations

import dataclasses
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


# ---------------------------------------------------------------- the sound and the picture agree (DESIGN.md §46.13 criterion 487)
def make_mp4(path, picture_seconds, sound_seconds):
    """A real H.264 and AAC file made by ffmpeg whose sound is `sound_seconds` long and whose picture is `picture_seconds`: the sound is cut or padded to the length asked for."""
    import subprocess

    done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=128x64:r=24:d={picture_seconds}", "-f", "lavfi", "-i", f"sine=frequency=300:sample_rate=48000:duration={sound_seconds}",
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", str(max(picture_seconds, sound_seconds)), str(path)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


@pytest.mark.skipif(not media.find_tools().ok, reason="ffmpeg and ffprobe are not installed here")
@pytest.mark.parametrize("picture, sound, noted", [(5.0, 4.969, False), (5.0, 4.955, False), (5.0, 5.0, False), (5.0, 4.8, True), (5.0, 5.4, True)])
def test_a_clip_whose_sound_is_much_shorter_or_longer_than_its_picture_gets_a_note_and_the_few_ms_the_real_program_leaves_do_not(tmp_path, picture, sound, noted):
    """The real program's sound is 31 ms short at 5 s and 30 s and 45 ms at the tiny size (MEASURED): nothing is said of that. A sound 200 ms short or 400 ms long is."""
    path = tmp_path / "c.mp4"
    make_mp4(path, picture, sound)
    facts = media.probe_clip("ffprobe", path)
    assert facts.audio_seconds is not None
    note = media.sync_note(facts)
    assert (note is not None) is noted, (facts.seconds, facts.audio_seconds, note)
    if noted:
        assert note.startswith("The sound and the picture differ by ") and (" ms: the sound stops early." in note or " ms: the sound runs on after the picture." in note)


def test_no_sound_or_no_length_is_never_a_sync_note():
    facts = media.ClipFacts(width=1, height=1, fps=24.0, frames=24, seconds=1.0, video_codec="h264", pixel_format="yuv420p", has_audio=False, audio_codec=None, audio_channels=None,
                            audio_rate=None, bytes=1)
    assert media.sync_note(facts) is None
    assert media.sync_note(dataclasses.replace(facts, has_audio=True, audio_seconds=None)) is None
    assert media.sync_note(dataclasses.replace(facts, has_audio=True, audio_seconds=2.0)) is not None  # (but a known, far-off length is)
    assert media.SYNC_TOLERANCE_MS == 100


def test_a_start_picture_with_transparency_is_laid_on_white_and_cut_to_the_clips_shape_from_the_middle(tmp_path):
    """DESIGN.md §46.13 criterion 490: the picture handed to the program is exactly the clip's size, cover-cropped, RGB; transparency is flattened on white (the form says so)."""
    source, target = tmp_path / "in.png", tmp_path / "out.png"
    picture = Image.new("RGBA", (200, 100), (0, 0, 0, 0))  # fully transparent, with an opaque red square in the middle
    picture.paste((255, 0, 0, 255), (75, 25, 125, 75))
    picture.save(source)
    media.prepare_start_picture(source, target, 128, 128)  # a square clip from a 2:1 picture: the sides are cut, nothing is stretched
    with Image.open(target) as made:
        assert made.mode == "RGB" and made.size == (128, 128)
        assert made.getpixel((2, 2)) == (255, 255, 255)  # transparent became white, not black
        assert made.getpixel((64, 64))[0] > 240 and made.getpixel((64, 64))[1] < 20  # the red square is in the middle
    plain = Image.new("RGB", (64, 64), (10, 20, 30))
    plain.save(source)
    media.prepare_start_picture(source, target, 64, 64)
    with Image.open(target) as made:
        assert made.mode == "RGB" and made.getpixel((5, 5)) == (10, 20, 30)


# ---------------------------------------------------------------- the check of a file an engine wrote (DESIGN.md §46.8)
def facts_of(width: int, height: int, seconds: float) -> "media.ClipFacts":
    return media.ClipFacts(width=width, height=height, fps=24.0, frames=round(seconds * 24), seconds=seconds, video_codec="h264", pixel_format="yuv420p", has_audio=True, audio_codec="aac",
                           audio_channels=2, audio_rate=48000, bytes=1000, audio_seconds=seconds)


def test_a_clip_of_the_size_and_about_the_length_asked_for_is_accepted():
    assert media.check_output(facts_of(1280, 704, 10.0), width=1280, height=704, frames=241, fps=24) is None  # 241 frames at 24 a second is 10.04 s
    assert media.check_output(facts_of(1280, 704, 10.5), width=1280, height=704, frames=241, fps=24) is None  # inside the 5% (0.5 s) that is allowed


@pytest.mark.parametrize("width, height", [(640, 352), (1280, 700), (704, 1280)])
def test_a_clip_of_another_size_than_asked_for_is_refused_in_words_that_name_both_sizes(width, height):
    said = media.check_output(facts_of(width, height, 10.0), width=1280, height=704, frames=241, fps=24)
    assert said == f"The program wrote a {width}x{height} clip; 1280x704 was asked for."  # the size is the first thing checked: a clip of the wrong size is wrong whatever its length


@pytest.mark.parametrize("seconds, accepted", [(10.6, False), (9.4, False), (10.5, True), (9.6, True)])
def test_the_length_may_differ_by_five_percent_and_no_more(seconds, accepted):
    said = media.check_output(facts_of(1280, 704, seconds), width=1280, height=704, frames=241, fps=24)
    assert (said is None) is accepted
    if not accepted:
        assert f"a clip of {seconds:.1f} seconds; about 10.0 were asked for" in said


@pytest.mark.parametrize("seconds, accepted", [(1.3, False), (0.7, False), (1.2, True), (0.8, True)])
def test_a_short_clip_may_differ_by_a_quarter_of_a_second_where_five_percent_would_be_less(seconds, accepted):
    """25 frames at 24 a second is 1.04 s: 5% is 0.05 s, which no real encoder meets, so the allowance has a floor of a quarter of a second."""
    assert (media.check_output(facts_of(256, 128, seconds), width=256, height=128, frames=25, fps=24) is None) is accepted
