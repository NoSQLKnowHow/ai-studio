"""HD and Scope (DESIGN.md §46.20, criteria 493 to 500): sizes the model cannot make itself, made a few pixels taller and trimmed to size.

The model makes only multiples of 64 (704 and 1280 work, 720 does not), so 1920x1080 and 1920x800, which the person asked for, cannot be asked of it. The engine's presets say so: the
preset 'hd' is delivered at 1920x1080 and MADE at 1920x1088, 'scope' is delivered at 1920x800 and MADE at 1920x832, and the studio cuts the clip to the delivered size from the middle once it
has been made (the picture converted once more, the sound copied).

What these tests protect, and what each break would do to a person:
  - the rule that says which size is made for which size is one function (`VideoEngineInfo.make_size`), and only a whole preset's size counts, as a pair: a clip of 1920x1081 must not
    quietly be made at 1920x1088, and 1080x1920 (a phone's shape) is not the HD preset turned round;
  - an engine definition with a preset that could not be trimmed (made smaller than delivered, or a size the model does not make) is refused when it is defined, so that the mistake is
    found by a developer and not by a person waiting minutes for a clip;
  - the trim itself, on a real file: the picture is cut from the MIDDLE (the top and bottom rows go, the rest stays where it was), every frame is kept, the sound is copied and not
    converted, and a trim that could not be done is a sentence and not a broken file;
  - through the whole server, with the fake engine: the program is asked for the size it makes, the start picture is made that size, the clip is checked at that size, the file the studio
    keeps is the size that was asked for, the run's options still say what was asked for, and the estimate counts the size that was made;
  - a trim that does not end at the size asked for is a failed run that keeps no clip.
"""

from __future__ import annotations

import dataclasses
import io
import subprocess
from pathlib import Path

import pytest
from conftest import image_bytes, stage, wait_for
from PIL import Image
from video_support import accept_licence, create_clip, wait_for_video_probe

from studio.config import Settings
from studio.runspec import RunCreate, RunRequestError, resolve_run
from studio.video import media, video_limits
from studio.video.engine import SizePreset
from studio.video.engines import fake, ltx

needs_ffmpeg = pytest.mark.skipif(not media.find_tools().ok, reason="ffmpeg and ffprobe are not installed here")
ENGINES = [pytest.param(fake.INFO, id="fake"), pytest.param(ltx.INFO, id="ltx")]


# ---------------------------------------------------------------- which size is made for which size (criterion 493)
@pytest.mark.parametrize("info", ENGINES)
@pytest.mark.parametrize("asked, made", [((1920, 1080), (1920, 1088)), ((1920, 800), (1920, 832))])
def test_the_hd_and_scope_presets_are_made_the_next_multiple_up(info, asked, made):
    """The two sizes that were asked for, and the sizes the model makes for them: the next multiples of 64 above 1080 and above 800."""
    assert info.make_size(*asked) == made
    assert info.is_trimmed_size(*asked) is True
    assert made[0] % info.size_multiple == 0 and made[1] % info.size_multiple == 0


@pytest.mark.parametrize("info", ENGINES)
@pytest.mark.parametrize("size", [(1280, 704), (1024, 576), (704, 1280), (512, 320), (1920, 1088), (1920, 832), (1920, 1024), (256, 256)])
def test_every_other_size_is_made_as_it_is(info, size):
    """A size the model can make is made as it is: nothing is rounded, trimmed or changed for it, whether or not it is a preset."""
    assert info.make_size(*size) == size and info.is_trimmed_size(*size) is False


@pytest.mark.parametrize("info", ENGINES)
@pytest.mark.parametrize("size", [(1920, 1081), (1920, 1079), (1918, 1080), (1080, 1920), (800, 1920), (1920, 801), (1921, 1080), (1856, 800), (1920, 1000)])
def test_only_a_whole_presets_size_is_trimmed_as_a_pair_never_a_side_or_a_nearby_size(info, size):
    """1920x1081 is not HD, 1080x1920 is not HD turned round and 1856x800 is not Scope narrower: no size is rounded up on the person's behalf. The server refuses all of them (the options tests)."""
    assert info.make_size(*size) == size and info.is_trimmed_size(*size) is False


@pytest.mark.parametrize("info", ENGINES)
def test_the_presets_the_form_offers_are_all_sizes_the_server_accepts_and_the_trimmed_ones_say_what_is_made(info):
    """Every preset is one the server takes (as a pair, for the trimmed ones), and the page is told what is made for each, so that it repeats no rule of its own."""
    settings = Settings(pipeline="real" if info is ltx.INFO else "fake")
    limits = video_limits(settings, info)["size"]["presets"]
    assert [p["id"] for p in limits] == ["landscape", "hd", "scope", "quick", "portrait", "tiny"]
    for preset in limits:
        run = resolve_run(RunCreate(mode="video", prompt="a fox", options={"width": preset["width"], "height": preset["height"]}), settings)
        assert (run.video.width, run.video.height) == (preset["width"], preset["height"])  # the run is asked for what the person chose
        assert (preset["make_width"], preset["make_height"]) == info.make_size(preset["width"], preset["height"])
    by_id = {p["id"]: p for p in limits}
    assert (by_id["hd"]["width"], by_id["hd"]["height"], by_id["hd"]["make_width"], by_id["hd"]["make_height"]) == (1920, 1080, 1920, 1088)
    assert (by_id["scope"]["width"], by_id["scope"]["height"], by_id["scope"]["make_width"], by_id["scope"]["make_height"]) == (1920, 800, 1920, 832)
    assert (by_id["landscape"]["make_width"], by_id["landscape"]["make_height"]) == (1280, 704)  # a preset that is not trimmed says it is made as it is


def test_the_scope_preset_is_2_40_to_1_and_hd_is_16_to_9():
    """The shapes the person asked for: a CinemaScope-style 2.40:1 and full HD's 16:9."""
    presets = {p.id: p for p in ltx.INFO.size_presets}
    assert presets["scope"].width / presets["scope"].height == pytest.approx(2.40, abs=0.001)
    assert presets["hd"].width / presets["hd"].height == pytest.approx(16 / 9, abs=0.001)
    assert "1920×1080" in presets["hd"].label and "1920×800" in presets["scope"].label and "2.40:1" in presets["scope"].label


# ---------------------------------------------------------------- a preset that could not be trimmed is refused when it is defined (criterion 494)
@pytest.mark.parametrize("preset, why", [
    (SizePreset("x", "x", 1920, 1080, 1920, 1090), "not a size the model makes"),    # made at a size the model does not make
    (SizePreset("x", "x", 1920, 1100, 1920, 1088), "smaller than"),                    # made smaller than delivered: nothing to trim
    (SizePreset("x", "x", 1920, 1000, 1920, 1088), "smaller than"),                    # more than one step of 64 taller: that is a different size, not a trim
    (SizePreset("x", "x", 1919, 1080, 1920, 1088), "even"),                            # an odd side cannot be a 4:2:0 picture
])
def test_a_preset_that_cannot_be_trimmed_is_refused_where_the_engine_is_defined(preset, why):
    with pytest.raises(ValueError, match=why):
        dataclasses.replace(ltx.INFO, size_presets=(*ltx.INFO.size_presets, preset))


def test_a_preset_that_is_not_trimmed_needs_none_of_that():
    """Presets that are made as they are (every preset until HD and Scope) are not looked at by the rule: the sizes the model makes are what they are."""
    info = dataclasses.replace(ltx.INFO, size_presets=(SizePreset("a", "a", 1280, 704),))
    assert info.make_size(1280, 704) == (1280, 704)


# ---------------------------------------------------------------- the trim, on a real file (criteria 495, 496)
def banded_clip(path: Path, made: tuple[int, int], trim: tuple[int, int], *, frames: int = 25) -> None:
    """A clip of the size the program makes whose edges are told apart by colour: red where the trim will take the top, green just inside it, blue just inside the bottom edge and yellow
    where the trim will take the bottom. After a trim from the middle the first row is green and the last is blue; a trim from the wrong place shows as another colour. With sound (a tone)."""
    width, height = made
    top = (height - trim[1]) // 2  # even for the sizes whose colours are checked (4 and 16), so that the colour blocks of a 4:2:0 picture line up with the cut
    boxes = ",".join([
        f"drawbox=x=0:y=0:w=iw:h={top}:color=red:t=fill",
        f"drawbox=x=0:y={top}:w=iw:h=8:color=green:t=fill",
        f"drawbox=x=0:y={height - top - 8}:w=iw:h=8:color=blue:t=fill",
        f"drawbox=x=0:y={height - top}:w=iw:h={top}:color=yellow:t=fill",
        "format=yuv420p",
    ])
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s={width}x{height}:r=24", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
         "-vf", boxes, "-frames:v", str(frames), "-c:v", "libx264", "-crf", "12", "-c:a", "aac", "-ac", "2", "-shortest", str(path)],
        capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def first_frame(path: Path, into: Path) -> Image.Image:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-frames:v", "1", str(into)], check=True)
    return Image.open(into).convert("RGB")


def stream_hash(path: Path, stream: str) -> str:
    """The MD5 of one stream's packets exactly as stored (`-c copy`): two files with the same hash hold the same compressed bytes for that stream, so the stream was copied and not converted."""
    done = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", stream, "-c", "copy", "-f", "md5", "-"], capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.startswith("MD5="), done.stderr
    return done.stdout.strip()


def near(pixel: tuple[int, int, int], expected: tuple[int, int, int], slack: int = 40) -> bool:
    return all(abs(a - b) <= slack for a, b in zip(pixel, expected))


@needs_ffmpeg
@pytest.mark.parametrize("made, trim", [((1920, 1088), (1920, 1080)), ((1920, 832), (1920, 800))])
def test_the_picture_is_cut_from_the_middle_every_frame_is_kept_and_the_sound_is_copied(tmp_path, made, trim):
    raw, kept = tmp_path / "raw.mp4", tmp_path / "clip.mp4"
    banded_clip(raw, made, trim)
    facts = media.probe_clip("ffprobe", raw)
    assert (facts.width, facts.height, facts.frames) == (*made, 25) and facts.audio_codec == "aac"

    done = media.finish_clip("ffmpeg", "ffprobe", raw, kept, facts=facts, keep_sound=True, comment="c", title="t", trim_to=trim)

    assert (done.width, done.height) == trim and done.frames == 25 and done.fps == pytest.approx(24)  # the size asked for, and not one frame fewer
    assert done.video_codec == "h264" and done.pixel_format == "yuv420p" and done.playable_everywhere  # plays everywhere, as every kept clip does
    # the sound is the program's own, copied: the same codec, channels and rate, the same length, and the very same compressed packets (a conversion would change them)
    assert (done.audio_codec, done.audio_channels, done.audio_rate) == ("aac", 2, 48000)
    assert done.audio_seconds == pytest.approx(facts.audio_seconds, abs=0.001)
    assert stream_hash(kept, "0:a:0") == stream_hash(raw, "0:a:0")
    assert stream_hash(kept, "0:v:0") != stream_hash(raw, "0:v:0")  # and the picture, which was cut, is a new one
    # from the middle: the red rows above and the yellow rows below are gone, the first row is what was just inside the top and the last row what was just inside the bottom
    frame = first_frame(kept, tmp_path / "first.png")
    assert frame.size == trim
    assert near(frame.getpixel((960, 0)), (0, 127, 0)) and near(frame.getpixel((960, 7)), (0, 127, 0))
    assert near(frame.getpixel((960, trim[1] - 1)), (0, 0, 255)) and near(frame.getpixel((960, trim[1] - 8)), (0, 0, 255))
    assert not any(near(frame.getpixel((960, y)), (255, 0, 0)) or near(frame.getpixel((960, y)), (255, 255, 0)) for y in (0, 1, trim[1] - 2, trim[1] - 1))
    assert not (tmp_path / "clip.mp4.part.mp4").exists()  # the half-written file is never left behind


@needs_ffmpeg
def test_converting_the_picture_once_more_does_not_show(tmp_path):
    """The trim converts the picture, which a stream copy would not. Measured on a detailed test picture (text, gradients, edges), CRF 14 changed it by 0.17 of 255 on average, CRF 18 by 0.27,
    CRF 40 by 1.32 and CRF 51 by 4.69: a limit of 1.0 passes what the studio does and catches a setting that would be seen."""
    raw, kept = tmp_path / "raw.mp4", tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1088:rate=24", "-frames:v", "9", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(raw)], check=True)
    media.finish_clip("ffmpeg", "ffprobe", raw, kept, facts=media.probe_clip("ffprobe", raw), keep_sound=False, comment="c", title="t", trim_to=(1920, 1080))
    before = first_frame(raw, tmp_path / "before.png").crop((0, 4, 1920, 1084))  # the rows the trim keeps
    after = first_frame(kept, tmp_path / "after.png")
    assert after.size == before.size == (1920, 1080)
    from PIL import ImageChops, ImageStat

    assert max(ImageStat.Stat(ImageChops.difference(before, after)).mean) < 1.0


@needs_ffmpeg
def test_a_trim_keeps_the_metadata_and_the_index_at_the_front_like_every_kept_clip(tmp_path):
    raw, kept = tmp_path / "raw.mp4", tmp_path / "clip.mp4"
    banded_clip(raw, (1920, 1088), (1920, 1080))
    media.finish_clip("ffmpeg", "ffprobe", raw, kept, facts=media.probe_clip("ffprobe", raw), keep_sound=True, comment="Made with a test", title="a fox", trim_to=(1920, 1080))
    tags = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment,title", "-of", "default=nw=1", str(kept)], capture_output=True, text=True).stdout
    assert "comment=Made with a test" in tags and "title=a fox" in tags
    data = kept.read_bytes()
    assert 0 <= data.find(b"moov") < data.find(b"mdat")  # `faststart`: the index comes before the data, so that it starts playing before it is all downloaded


@needs_ffmpeg
def test_a_trim_with_the_sound_taken_out_has_no_sound_and_keeps_every_frame(tmp_path):
    raw, kept = tmp_path / "raw.mp4", tmp_path / "clip.mp4"
    banded_clip(raw, (1920, 1088), (1920, 1080))
    done = media.finish_clip("ffmpeg", "ffprobe", raw, kept, facts=media.probe_clip("ffprobe", raw), keep_sound=False, comment="c", title="t", trim_to=(1920, 1080))
    assert (done.width, done.height, done.frames, done.has_audio) == (1920, 1080, 25, False)


@needs_ffmpeg
def test_a_trim_can_take_pixels_from_the_sides_as_well_and_the_result_is_the_size_asked_for(tmp_path):
    """The preset sizes trim the height only, but the rule is general: a clip is cut from the middle on both axes."""
    raw, kept = tmp_path / "raw.mp4", tmp_path / "clip.mp4"
    banded_clip(raw, (320, 192), (312, 184), frames=9)
    done = media.finish_clip("ffmpeg", "ffprobe", raw, kept, facts=media.probe_clip("ffprobe", raw), keep_sound=True, comment="c", title="t", trim_to=(312, 184))
    assert (done.width, done.height, done.frames) == (312, 184, 9)


@needs_ffmpeg
@pytest.mark.parametrize("trim", [(1920, 1090), (1922, 1080), (1920, 1079), (1919, 1080), (0, 1080), (1920, 0)])
def test_a_trim_that_cannot_be_done_is_a_sentence_and_leaves_no_file(tmp_path, trim):
    """Bigger than the clip, or an odd side (which a 4:2:0 picture cannot have), or nothing at all: said in words, and no half-made clip is left to be taken for one."""
    raw, kept = tmp_path / "raw.mp4", tmp_path / "clip.mp4"
    banded_clip(raw, (1920, 1088), (1920, 1080), frames=9)
    with pytest.raises(media.MediaError, match=r"cannot be trimmed to"):
        media.finish_clip("ffmpeg", "ffprobe", raw, kept, facts=media.probe_clip("ffprobe", raw), keep_sound=True, comment="c", title="t", trim_to=trim)
    assert not kept.exists() and not (tmp_path / "clip.mp4.part.mp4").exists()


@needs_ffmpeg
def test_without_a_trim_the_streams_are_copied_as_before(tmp_path):
    """The ordinary size is not touched by any of this: a clip that plays everywhere is only remuxed, and no picture is converted for it (the trim is for HD and Scope alone)."""
    raw, kept = tmp_path / "raw.mp4", tmp_path / "clip.mp4"
    banded_clip(raw, (1280, 704), (1280, 704), frames=9)
    before = media.probe_clip("ffprobe", raw)
    done = media.finish_clip("ffmpeg", "ffprobe", raw, kept, facts=before, keep_sound=True, comment="c", title="t")
    assert (done.width, done.height, done.frames) == (1280, 704, 9) and done.video_codec == "h264"
    # both streams are the program's own bytes: copied, not converted
    assert stream_hash(kept, "0:v:0") == stream_hash(raw, "0:v:0") and stream_hash(kept, "0:a:0") == stream_hash(raw, "0:a:0")


# ---------------------------------------------------------------- through the whole server, with the fake engine (criteria 497 to 500)
@pytest.fixture
def video(client_factory):
    client = client_factory(quiet=True)
    wait_for_video_probe(client)
    accept_licence(client)
    return client


@pytest.fixture
def finish_calls(monkeypatch):
    """What `accept_clip` hands `finish_clip`: the size of the file the program wrote and the size it was told to trim it to. The real function still runs."""
    calls: list[dict] = []
    original = media.finish_clip

    def spy(ffmpeg, ffprobe, source, target, *, facts, **rest):
        calls.append({"made": (facts.width, facts.height), "trim_to": rest.get("trim_to")})
        return original(ffmpeg, ffprobe, source, target, facts=facts, **rest)

    monkeypatch.setattr("studio.video.service.finish_clip", spy)
    return calls


@needs_ffmpeg
@pytest.mark.parametrize("asked, made", [((1920, 1080), (1920, 1088)), ((1920, 800), (1920, 832))])
def test_the_program_is_asked_for_the_size_it_makes_and_the_clip_kept_is_the_size_asked_for(video, finish_calls, asked, made):
    queued = create_clip(video, "a wide shot", width=asked[0], height=asked[1])
    assert (queued["options"]["width"], queued["options"]["height"]) == asked  # the run says what the person asked for, and only that
    assert "make_width" not in queued["options"]
    done = wait_for(video, queued["id"])
    assert done["status"] == "done", done["error"]
    # the fake program wrote the size it was ASKED for, which is the one the job carried: that is how the make size got through the queue and the worker
    assert finish_calls == [{"made": made, "trim_to": asked}]
    clip = done["video"]
    assert (clip["width"], clip["height"], clip["frames"]) == (*asked, 25) and clip["has_audio"] and clip["note"] is None
    root = video.app.state.storage.root
    facts = media.probe_clip("ffprobe", root / "video" / done["id"] / "clip.mp4")
    assert (facts.width, facts.height, facts.frames) == (*asked, 25) and facts.video_codec == "h264" and facts.pixel_format == "yuv420p" and facts.playable_everywhere
    assert Image.open(root / "video" / done["id"] / "poster.jpg").size == asked  # the poster and the thumbnail are of the kept clip
    assert sorted(p.name for p in (root / "video" / done["id"]).iterdir()) == ["clip.mp4", "poster.jpg"]  # the program's taller file is gone


@needs_ffmpeg
def test_an_ordinary_size_is_not_trimmed(video, finish_calls):
    done = wait_for(video, create_clip(video)["id"])
    assert done["status"] == "done" and (done["video"]["width"], done["video"]["height"]) == (256, 128)
    assert finish_calls == [{"made": (256, 128), "trim_to": None}]


@needs_ffmpeg
def test_the_start_picture_is_made_the_size_the_program_makes_and_is_still_the_first_frame(video, monkeypatch):
    """The program is given a picture of the size it makes, so that it scales nothing, and the trim then takes the same middle: the first frame is the picture."""
    from studio.video import service

    seen: list[tuple[int, int]] = []
    original = service.prepare_start_picture
    monkeypatch.setattr("studio.video.service.prepare_start_picture", lambda source, target, width, height: (seen.append((width, height)), original(source, target, width, height))[1])
    red = stage(video, image_bytes((200, 30, 30), size=(400, 300)))
    done = wait_for(video, create_clip(video, "the red room", width=1920, height=1080, pictures=[{"upload_id": red["upload_id"]}])["id"])
    assert done["status"] == "done", done["error"]
    assert seen == [(1920, 1088)]
    assert (done["video"]["width"], done["video"]["height"]) == (1920, 1080)
    poster = Image.open(io.BytesIO(video.get(done["video"]["poster_url"]).content)).convert("RGB")
    assert near(poster.getpixel((960, 540)), (200, 30, 30), slack=14)


@needs_ffmpeg
def test_a_trim_that_does_not_end_at_the_size_asked_for_is_a_failed_run_that_keeps_no_clip(video, monkeypatch):
    """The studio keeps a clip only if the file it keeps is the size that was asked for: a finishing step that left the taller picture is caught and said in words."""
    original = media.finish_clip
    monkeypatch.setattr("studio.video.service.finish_clip", lambda *a, **k: original(*a, **{**k, "trim_to": None}))
    failed = wait_for(video, create_clip(video, "forgot to trim", width=1920, height=1080)["id"])
    assert failed["status"] == "failed" and failed["video"] is None
    assert "The finished clip is 1920x1088; 1920x1080 was asked for." in failed["error"]["message"]
    folder = video.app.state.storage.root / "video" / failed["id"]
    assert not (folder / "clip.mp4").exists()


@needs_ffmpeg
def test_what_the_program_wrote_is_checked_against_the_size_it_was_asked_to_make_and_not_the_size_that_is_kept(video, monkeypatch):
    """The check on the file the program wrote is against the size the program was ASKED for (1920x1088). Were it against the size that is kept (1920x1080), every HD clip would be refused."""
    original = media.check_output
    seen: list[tuple[int, int]] = []

    def spy(facts, *, width, height, **rest):
        seen.append((width, height))
        return original(facts, width=width, height=height, **rest)

    monkeypatch.setattr("studio.video.service.check_output", spy)
    done = wait_for(video, create_clip(video, "checked", width=1920, height=1080)["id"])
    assert done["status"] == "done" and seen == [(1920, 1088)]


@needs_ffmpeg
def test_the_estimate_counts_the_size_that_was_made_and_not_the_size_that_was_kept(video):
    done = wait_for(video, create_clip(video, "work done", width=1920, height=800)["id"])
    assert done["status"] == "done"
    history = video.get("/api/capabilities").json()["limits"]["video"]["estimate"]["history"]
    assert [(h["width"], h["height"]) for h in history] == [(1920, 832)]  # the work was a 1920x832 clip; the next clip's estimate scales from that


@needs_ffmpeg
def test_a_clip_made_at_a_trimmed_size_can_be_asked_for_again_from_its_own_options(video):
    """Retry and Reuse send the options back as they were stored: HD must be accepted again exactly as it was, with no field the server does not know."""
    first = wait_for(video, create_clip(video, "again", width=1920, height=1080, seed=5)["id"])
    options = first["options"]
    again = video.post("/api/runs", json={"mode": "video", "prompt": "again", "options": {"width": options["width"], "height": options["height"], "seconds": 1, "seed": options["seed"]}})
    assert again.status_code == 201, again.text
    assert wait_for(video, again.json()["id"])["status"] == "done"


# ---------------------------------------------------------------- what is refused (criterion 493)
@pytest.mark.parametrize("size", [(1920, 1081), (1080, 1920), (1920, 1000), (1856, 800), (1918, 1080)])
def test_a_size_next_to_a_preset_is_refused_with_the_multiples_it_could_have_been(size):
    with pytest.raises(RunRequestError) as caught:
        resolve_run(RunCreate(mode="video", prompt="a fox", options={"width": size[0], "height": size[1]}), Settings(pipeline="fake"))
    detail = caught.value.detail()
    assert detail and {e["loc"][-1] for e in detail} <= {"width", "height"} and all(e["loc"][:2] == ["body", "options"] for e in detail)
    assert any("multiple of 64" in e["msg"] for e in detail)
    assert any("HD and Scope" in e["msg"] for e in detail)  # the sentence says where the two exceptions are
