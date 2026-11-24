"""What a request for a clip is (DESIGN.md §46.9, §46.10): its options, the rules they obey, and the words of each refusal.

`check_video` is the one place the rules are written. It returns the resolved request (`VideoSpec`) or the list of field errors; `runspec.resolve_run` turns that into the
usual 422, with the same field paths the page shows its messages beside. Nothing a person can type is a 500: every option is checked here before anything is queued.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Optional

from .. import presets as P
from . import MIN_FRAMES, OFFERED_QUALITIES, QUALITIES, SECONDS_MIN, SOUND_CHARS, frames_for, join_prompt, nearest_frames, nearest_multiples
from .engine import VideoEngineInfo

# One field error: (the path of the field, the words, a code). The code is what the 422 carries as the error's `type`, so a caller can tell `bad_size` from `too_long`.
FieldError = tuple[tuple[Any, ...], str, str]

# The options that mean something only for a video clip. Sending one with another kind of run is a mistake the page should hear about (as for the Vector-only options).
ONLY_FOR_VIDEO = ("mode", "quality", "seconds", "fps", "sound", "keep_sound", "segments", "frames", "strength")


@dataclass(frozen=True)
class VideoSpec:
    """A clip as it was asked for, with every default filled in and every rule checked: what is stored in the run's options and what the worker is sent."""

    mode: str  # "text" or "image"
    quality: str  # "draft"
    variant: str  # the checkpoint that quality is: "distilled"
    engine: str
    width: int
    height: int
    seconds: float  # as asked (or, when `frames` was named, what they last)
    frames: int  # as made: always 8n + 1
    fps: int
    seed: int
    seed_was_random: bool
    sound: str  # "what you hear"; empty for none
    keep_sound: bool
    strength: float
    effective_prompt: str  # what the model is sent: what happens, then the sound text (`join_prompt`)

    def options_snapshot(self) -> dict[str, Any]:
        """Exactly what the run used; Reuse and Retry restore from this. `start` says which input is the start picture (image mode only)."""
        return {
            "mode": self.mode, "quality": self.quality, "engine": self.engine, "variant": self.variant, "width": self.width, "height": self.height,
            "seconds": self.seconds, "frames": self.frames, "fps": self.fps, "seed": self.seed, "seed_was_random": self.seed_was_random,
            "sound": self.sound, "keep_sound": self.keep_sound, "segments": 1,
            "start": {"image": 1, "frame": 0, "strength": self.strength} if self.mode == "image" else None,
        }


def check_video(*, prompt: str, sent: set[str], opts: Any, pictures: int, info: VideoEngineInfo, max_seconds: int, max_prompt_chars: int) -> tuple[Optional[VideoSpec], list[FieldError]]:
    """Check one request for a clip. `opts` is the request's `RunOptions` (the fields this uses are named in `ONLY_FOR_VIDEO` and `width`, `height`, `seed`), `sent` the names the
    request actually carried, and `pictures` how many input pictures it came with. Returns (the resolved request, []) or (None, the errors)."""
    errors: list[FieldError] = []

    scene = prompt.strip()
    if not scene:
        errors.append((("prompt",), "Say what happens in the clip.", "value_error"))
    elif len(scene) > max_prompt_chars:
        errors.append((("prompt",), f"The words are {len(scene)} characters; the limit is {max_prompt_chars}.", "value_error"))

    sound = " ".join((opts.sound or "").split())
    if len(sound) > SOUND_CHARS:
        errors.append((("options", "sound"), f"What you hear is {len(sound)} characters; the limit is {SOUND_CHARS}.", "value_error"))
    keep_sound = True if opts.keep_sound is None else bool(opts.keep_sound)

    # text to video, or image to video: image mode needs a start picture, and a picture without image mode is a mistake worth saying
    mode = opts.mode if opts.mode is not None else ("image" if pictures else "text")
    if mode not in ("text", "image"):
        errors.append((("options", "mode"), "Must be text or image.", "value_error"))
    elif mode == "image" and pictures == 0:
        errors.append((("input_images",), "Image to video needs a start picture.", "image_needed"))
    elif mode == "text" and pictures:
        errors.append((("input_images",), "A picture is only used for Image to video: set mode to image, or send none.", "value_error"))
    if pictures > info_images_limit(info):
        errors.append((("input_images",), f"A clip starts from {info_images_limit(info)} picture; an end picture is not offered yet.", "too_many_images"))

    # the quality is the checkpoint (distilled is Draft); only what has been tried on the Spark is offered
    quality = opts.quality or "draft"
    if quality not in QUALITIES:
        errors.append((("options", "quality"), f"Must be one of: {', '.join(QUALITIES)}.", "value_error"))
    elif quality not in OFFERED_QUALITIES:
        errors.append((("options", "quality"), f"{quality.capitalize()} is not offered on this machine yet.", "value_error"))
    variant = QUALITIES.get(quality, info.default_variant)
    if variant not in info.variants and quality in OFFERED_QUALITIES:
        errors.append((("options", "quality"), f"The {info.title} engine has no {variant} model.", "value_error"))

    # size: both or neither, a multiple of what the model needs, and not outside the sizes it is meant for
    width, height = opts.width, opts.height
    if (width is None) != (height is None):
        errors.append((("options", "height" if width is not None else "width"), "Width and height must be given together.", "bad_size"))
        width = height = None
    if width is None or height is None:
        width, height = info.size_default
    elif not info.is_trimmed_size(width, height):  # a preset's size that is made bigger and trimmed (HD 1920x1080) is allowed as a pair, and only as that pair (§46.20)
        for name, value in (("width", width), ("height", height)):
            if not info.size_min <= value <= info.size_max:
                errors.append((("options", name), f"Must be between {info.size_min} and {info.size_max} pixels.", "bad_size"))
            elif value % info.size_multiple:
                below, above = nearest_multiples(value, info.size_multiple)
                errors.append((("options", name), f"Must be a multiple of {info.size_multiple}; the nearest are {below} and {above}. (The HD and Scope sizes are the exceptions: they are offered as buttons.)", "bad_size"))

    fps = opts.fps if opts.fps is not None else info.fps_choices[0]
    if fps not in info.fps_choices:
        errors.append((("options", "fps"), f"The frame rates offered are: {', '.join(str(f) for f in info.fps_choices)}.", "value_error"))
        fps = info.fps_choices[0]

    # the length: seconds (the form's way; the server works out the frames) or frames (an API caller's, which must already be a number the model takes)
    if opts.frames is not None and opts.seconds is not None:
        errors.append((("options", "frames"), "Give the length as seconds or as frames, not both.", "bad_frames"))
        seconds, frames = float(max_seconds), MIN_FRAMES
    elif opts.frames is not None:
        frames = opts.frames
        below, above = nearest_frames(frames)
        if frames < MIN_FRAMES or (frames - 1) % 8:
            errors.append((("options", "frames"), f"The model makes 8n + 1 frames (9, 17, 25, ...); the nearest are {below} and {above}.", "bad_frames"))
        elif frames > frames_for(max_seconds, fps):
            errors.append((("options", "frames"), f"{frames} frames at {fps} a second is longer than the {max_seconds} seconds this machine allows.", "too_long"))
        seconds = round(frames / fps, 3)
    else:
        seconds = float(opts.seconds if opts.seconds is not None else min(10, max_seconds))
        if seconds < SECONDS_MIN:
            errors.append((("options", "seconds"), f"A clip is at least {SECONDS_MIN} second.", "value_error"))
        elif seconds > max_seconds:
            errors.append((("options", "seconds"), f"The longest clip is {max_seconds} seconds (STUDIO_VIDEO_MAX_SECONDS).", "too_long"))
        frames = frames_for(seconds, fps)

    if opts.segments is not None and opts.segments != 1:
        errors.append((("options", "segments"), "A clip is made in one pass; joining several is not offered yet.", "value_error"))
    strength = 1.0 if opts.strength is None else opts.strength
    if not 0.0 <= strength <= 1.0:
        errors.append((("options", "strength"), "Must be between 0 and 1.", "value_error"))
    if opts.seed is not None and not 0 <= opts.seed <= P.SEED_MAX:
        errors.append((("options", "seed"), f"Must be between 0 and {P.SEED_MAX}.", "value_error"))
    # options that mean something for a picture and nothing for a clip
    for name in ("steps", "num_images", "negative_prompt", "cfg_scale", "transparent", "resolution", "shape_from", "draft", "full", "duration", "tracks", "fields"):
        if name in sent:
            errors.append((("options", name), "Not used for video.", "value_error"))

    if errors:
        return None, errors
    seed_was_random = opts.seed is None
    seed = secrets.randbelow(P.SEED_MAX + 1) if seed_was_random else opts.seed
    return VideoSpec(
        mode=mode, quality=quality, variant=variant, engine=info.id, width=width, height=height, seconds=seconds, frames=frames, fps=fps, seed=seed, seed_was_random=seed_was_random,
        sound=sound, keep_sound=keep_sound, strength=strength, effective_prompt=join_prompt(scene, sound),
    ), []


def info_images_limit(info: VideoEngineInfo) -> int:
    """How many pictures a clip may start from: one (the start picture), if the engine can do image to video at all."""
    return 1 if info.image_to_video else 0
