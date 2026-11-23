"""The rules of a request for a clip (DESIGN.md §46.9, §46.10, criterion 446): the frames formula, the multiples of 64, the lengths, the sound, the pictures, and the words and
codes of each refusal. Nothing a person can type may be a 500, so every rule is checked here, with no server and no engine."""

from __future__ import annotations

import pytest

from studio.config import Settings
from studio.runspec import RunCreate, RunRequestError, resolve_run
from studio.video import SECONDS_DEFAULT, frames_for, join_prompt, nearest_frames, nearest_multiples, video_limits
from studio.video.engines import fake, ltx

SETTINGS = Settings(pipeline="fake")


def make(prompt: str = "a fox", mode: str = "video", **options):
    return RunCreate(mode=mode, prompt=prompt, options=options, **({"input_images": options.pop("pictures")} if "pictures" in options else {}))


def resolve(prompt: str = "a fox", pictures=None, settings: Settings = SETTINGS, **options):
    return resolve_run(RunCreate(mode="video", prompt=prompt, options=options, input_images=pictures), settings)


def refused(prompt: str = "a fox", pictures=None, settings: Settings = SETTINGS, **options) -> list[dict]:
    with pytest.raises(RunRequestError) as caught:
        resolve(prompt, pictures, settings, **options)
    return caught.value.detail()


# ---------------------------------------------------------------- the frames rule
@pytest.mark.parametrize("seconds, frames", [(5, 121), (10, 241), (20, 481), (30, 721), (1, 25), (0.5, 17), (0.1, 9), (7.5, 185)])
def test_the_frames_are_8n_plus_1_from_the_seconds_at_24_a_second(seconds, frames):
    """The lengths measured on the Spark (121, 241, 481 and 721 frames for 5, 10, 20 and 30 seconds) come out of the rule, and nothing is shorter than 9 frames."""
    assert frames_for(seconds, 24) == frames
    assert (frames - 1) % 8 == 0


def test_the_rounding_is_half_up_so_that_the_page_says_the_same_number():
    assert frames_for(0.5, 16) == 9  # 8 frames: 8 / 8 = 1.0 -> 8 * 1 + 1
    assert frames_for(1.5, 16) == 25  # 24 / 8 = 3.0
    assert frames_for(0.75, 16) == 17  # 12 / 8 = 1.5, a half: it goes up to 2 (Python's own round() would give 2 here too, but 2.5 -> 2 there)
    assert frames_for(1.25, 16) == 25  # 20 / 8 = 2.5: half-up gives 3 (round() would give 2)


def test_the_nearest_allowed_numbers_are_named_in_the_refusals():
    assert nearest_frames(10) == (9, 17) and nearest_frames(121) == (121, 121) and nearest_frames(0) == (9, 9)
    assert nearest_multiples(720, 64) == (704, 768) and nearest_multiples(704, 64) == (704, 704) and nearest_multiples(30, 64) == (64, 64)


# ---------------------------------------------------------------- a good request
def test_a_request_with_nothing_but_words_takes_every_default():
    run = resolve("a fox in the snow")
    spec = run.video
    assert spec is not None and run.mode == "video"
    assert (spec.width, spec.height) == (1280, 704) and spec.seconds == SECONDS_DEFAULT == 10 and spec.frames == 241 and spec.fps == 24
    assert spec.mode == "text" and spec.quality == "draft" and spec.variant == "distilled" and spec.keep_sound is True and spec.sound == "" and spec.strength == 1.0
    assert spec.seed_was_random and 0 <= spec.seed <= 2**32 - 1
    assert run.prompt == "a fox in the snow" and run.effective_prompt == "a fox in the snow" and run.num_images == 1


def test_the_sound_text_is_joined_to_the_words_and_both_are_kept_apart_in_the_run():
    run = resolve("A fox in the snow", sound="  snow   crunching ", seconds=5)
    assert run.prompt == "A fox in the snow" and run.effective_prompt == "A fox in the snow. Sound: snow crunching"
    assert run.video.sound == "snow crunching" and run.options_snapshot()["sound"] == "snow crunching"
    assert join_prompt("Already ends.", "rain") == "Already ends. Sound: rain" and join_prompt("a fox", "") == "a fox"


def test_the_options_the_run_stores_are_everything_reuse_and_retry_need():
    snapshot = resolve("a fox", seconds=5, width=512, height=320, seed=9, sound="rain", keep_sound=False).options_snapshot()
    assert snapshot == {
        "mode": "text", "quality": "draft", "engine": "fake", "variant": "distilled", "width": 512, "height": 320, "seconds": 5.0, "frames": 121, "fps": 24, "seed": 9,
        "seed_was_random": False, "sound": "rain", "keep_sound": False, "segments": 1, "start": None,
    }


def test_a_start_picture_makes_it_image_to_video_and_the_options_say_which_input_it_is():
    run = resolve("a fox", pictures=[{"image_id": "a" * 32}])
    assert run.video.mode == "image" and run.options_snapshot()["start"] == {"image": 1, "frame": 0, "strength": 1.0}


def test_frames_may_be_named_instead_of_seconds_when_they_are_a_number_the_model_takes():
    run = resolve("a fox", frames=121)
    assert run.video.frames == 121 and run.video.seconds == pytest.approx(5.042, abs=0.001)


# ---------------------------------------------------------------- the refusals
def only(errors: list[dict]) -> dict:
    assert len(errors) == 1, errors
    return errors[0]


@pytest.mark.parametrize("options, where, code, words", [
    (dict(width=720, height=704), ["body", "options", "width"], "bad_size", "multiple of 64; the nearest are 704 and 768"),
    (dict(width=1280, height=700), ["body", "options", "height"], "bad_size", "multiple of 64; the nearest are 640 and 704"),
    (dict(width=1280), ["body", "options", "height"], "bad_size", "together"),
    (dict(width=0, height=64), ["body", "options", "width"], "bad_size", "between 64 and 1920"),
    (dict(width=2048, height=704), ["body", "options", "width"], "bad_size", "between 64 and 1920"),
    (dict(frames=10), ["body", "options", "frames"], "bad_frames", "nearest are 9 and 17"),
    (dict(frames=8), ["body", "options", "frames"], "bad_frames", "nearest are 9 and 9"),
    (dict(frames=240), ["body", "options", "frames"], "bad_frames", "nearest are 233 and 241"),
    (dict(frames=1001), ["body", "options", "frames"], "too_long", "longer than the 30 seconds"),
    (dict(frames=121, seconds=5), ["body", "options", "frames"], "bad_frames", "not both"),
    (dict(seconds=31), ["body", "options", "seconds"], "too_long", "longest clip is 30 seconds"),
    (dict(seconds=0.5), ["body", "options", "seconds"], "value_error", "at least 1 second"),
    (dict(fps=30), ["body", "options", "fps"], "value_error", "frame rates offered are: 24"),
    (dict(quality="final"), ["body", "options", "quality"], "value_error", "not offered"),
    (dict(quality="best"), ["body", "options", "quality"], "value_error", "Must be one of"),
    (dict(mode="video"), ["body", "options", "mode"], "value_error", "text or image"),
    (dict(mode="image"), ["body", "input_images"], "image_needed", "needs a start picture"),
    (dict(segments=3), ["body", "options", "segments"], "value_error", "one pass"),
    (dict(strength=1.5), ["body", "options", "strength"], "value_error", "between 0 and 1"),
    (dict(seed=-1), ["body", "options", "seed"], "value_error", "between 0 and"),
    (dict(sound="x" * 1001), ["body", "options", "sound"], "value_error", "limit is 1000"),
    (dict(steps=8), ["body", "options", "steps"], "value_error", "Not used for video"),
    (dict(negative_prompt="no"), ["body", "options", "negative_prompt"], "value_error", "Not used for video"),
])
def test_each_refusal_names_its_field_its_code_and_the_nearest_allowed_values(options, where, code, words):
    error = only(refused(**options))
    assert error["loc"] == where and error["type"] == code and words in error["msg"]


def test_a_picture_without_image_mode_and_two_pictures_are_refused():
    error = only(refused(pictures=[{"image_id": "a" * 32}], mode="text"))
    assert error["loc"] == ["body", "input_images"] and "set mode to image" in error["msg"]
    error = only(refused(pictures=[{"image_id": "a" * 32}, {"image_id": "b" * 32}]))
    assert error["type"] == "too_many_images" and error["loc"] == ["body", "input_images"]


def test_empty_words_and_too_many_are_refused_and_a_longest_length_is_the_settings():
    assert only(refused(prompt="   "))["msg"] == "Say what happens in the clip."
    assert "limit is 8000" in only(refused(prompt="x" * 8001))["msg"]
    assert resolve(seconds=30).video.frames == 721
    assert "longest clip is 20 seconds (STUDIO_VIDEO_MAX_SECONDS)" in only(refused(settings=Settings(pipeline="fake", video_max_seconds=20), seconds=21))["msg"]
    assert resolve(seconds=20, settings=Settings(pipeline="fake", video_max_seconds=20)).video.frames == 481


def test_several_mistakes_are_all_told_at_once_so_the_form_can_mark_them_together():
    errors = refused(prompt="", width=720, height=700, seconds=99, fps=7)
    assert {e["loc"][-1] for e in errors} == {"prompt", "width", "height", "seconds", "fps"}


@pytest.mark.parametrize("mode, extra", [("generate", {}), ("music", {}), ("vector", {})])
@pytest.mark.parametrize("name, value", [("seconds", 5), ("sound", "x"), ("keep_sound", False), ("quality", "draft"), ("fps", 24), ("frames", 9), ("segments", 1), ("strength", 1.0), ("mode", "text")])
def test_a_video_option_sent_with_another_kind_of_run_is_refused(mode, extra, name, value):
    with pytest.raises(RunRequestError) as caught:
        resolve_run(RunCreate(mode=mode, prompt="a fox", options={name: value}), SETTINGS)
    assert any(e["loc"] == ["body", "options", name] and "Only used for Video" in e["msg"] for e in caught.value.detail())


def test_lyrics_are_not_used_for_video():
    with pytest.raises(RunRequestError) as caught:
        resolve_run(RunCreate(mode="video", prompt="a fox", lyrics="la la"), SETTINGS)
    assert any(e["loc"] == ["body", "lyrics"] for e in caught.value.detail())


# ---------------------------------------------------------------- what the page is told
def test_the_limits_are_the_engines_and_the_settings_not_numbers_of_the_pages_own():
    limits = video_limits(SETTINGS, fake.INFO)
    assert limits["size"]["multiple"] == 64 and limits["size"]["default"] == [1280, 704]
    assert [(p["width"], p["height"]) for p in limits["size"]["presets"]][0] == (1280, 704)
    assert all(p["width"] % 64 == 0 and p["height"] % 64 == 0 for p in limits["size"]["presets"])  # every preset is one the server accepts
    assert limits["seconds"] == {"min": 1, "max": 30, "default": 10, "choices": [5, 10, 20, 30], "long_from": 10, "long_note": "Longer clips can show odd body motion; try another seed."}
    assert limits["fps"] == [24] and limits["images"] == {"start": 1, "end": 0} and limits["sound_chars"] == 1000
    assert video_limits(Settings(pipeline="fake", video_max_seconds=15), fake.INFO)["seconds"]["choices"] == [5, 10]
    assert limits["estimate"]["kind"] == "stand-in" and video_limits(Settings(pipeline="real"), ltx.INFO)["estimate"]["kind"] == "measured"


def test_the_real_engines_sizes_are_at_least_256_and_at_most_1920():
    error = only(refused(settings=Settings(pipeline="real"), width=128, height=256))
    assert error["loc"] == ["body", "options", "width"] and "between 256 and 1920" in error["msg"]


def test_every_preset_of_the_real_engine_passes_the_rules_of_the_real_engine():
    for preset in ltx.INFO.size_presets:
        run = resolve_run(RunCreate(mode="video", prompt="a fox", options={"width": preset.width, "height": preset.height}), Settings(pipeline="real"))
        assert (run.video.width, run.video.height) == (preset.width, preset.height) and run.video.engine == "ltx"
