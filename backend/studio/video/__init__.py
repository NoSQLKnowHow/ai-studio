"""Video: clips made by LTX-2.5 (DESIGN.md §46).

The package is split so that each part can be understood and tested on its own:
  engine.py, registry.py, engines/   the engine interface, the list of engines, one file per engine (the real LTX program, and the fake one the tests use)
  options.py                         what a request for a clip is: the rules for its length, size, sound and pictures, and the words of its errors
  job.py                             the job the API sends the video worker, and the checks the worker makes before it believes one
  media.py                           ffmpeg and ffprobe: reading a clip's facts, making it playable everywhere, its poster and thumbnail
  schema.py, store.py                the tables of clips and their segments
  service.py, routes.py              what the API does with clips (the licence, the checks before a run, taking a finished clip in), and the HTTP routes

This file holds the few constants the server and the page share, and `video_limits`, which tells the page every number it needs, so that the page repeats none.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from .engine import VideoEngineInfo

VIDEO = "video"  # the fourth kind of model the worker can hold (DESIGN.md §46.6): one engine in one variant, identified by its model key `video:<engine>:<variant>`

# The two qualities the form names, and the checkpoint each is (DESIGN.md §46.16 item 5): Draft is the distilled model (8 steps, then 3 more at twice the size), Final the full "dev" one.
# Only Draft is offered until the dev checkpoint has been tried on the Spark.
QUALITIES: dict[str, str] = {"draft": "distilled", "final": "dev"}
OFFERED_QUALITIES = ("draft",)

SECONDS_MIN = 1  # the shortest clip a person can ask for
SECONDS_CHOICES = (5, 10, 20, 30)  # the lengths the form offers as buttons (the number box takes any in between)
SECONDS_DEFAULT = 10  # DESIGN.md §46.16 as adjusted by what the Spark showed: longer clips can show odd body motion (a turn at 20 s, flickering arms at 30 s)
LONG_FROM_SECONDS = 10  # the form says so under any length above this
LONG_NOTE = "Longer clips can show odd body motion; try another seed."
SOUND_CHARS = 1000  # the longest "what you hear" text
MIN_FRAMES = 9  # the model's smallest clip: 8 + 1


def frames_for(seconds: float, fps: int) -> int:
    """The number of frames a clip of `seconds` at `fps` really has: `8 × round(seconds × fps ÷ 8) + 1`, at least 9 (DESIGN.md §46.9). The model wants 8n + 1 frames, so 10 seconds at 24 frames
    a second is 8 × 30 + 1 = 241, 20 seconds 481 and 30 seconds 721, which are the lengths the Spark was measured at. The rounding is half-up (not Python's round-half-even), so that
    the page, which uses Math.round, says the same number."""
    return max(MIN_FRAMES, 8 * math.floor(seconds * fps / 8 + 0.5) + 1)


def seconds_of(frames: int, fps: int) -> float:
    """How long `frames` frames last, as the file's own picture track will say it: (frames - 1) is the first frame at time 0, but a player counts every frame's duration, so frames ÷ fps."""
    return frames / fps


def nearest_frames(frames: int) -> tuple[int, int]:
    """The allowed frame counts either side of a number that is not one (8n + 1): the next one down (at least 9) and the next one up. A number that is allowed gives itself twice."""
    if frames >= MIN_FRAMES and (frames - 1) % 8 == 0:
        return frames, frames
    lower = max(MIN_FRAMES, ((frames - 1) // 8) * 8 + 1)
    return lower, lower + 8 if lower < frames else lower


def nearest_multiples(value: int, multiple: int) -> tuple[int, int]:
    """The multiples of `multiple` either side of `value` (the one below, at least `multiple` itself, and the one above)."""
    lower = max(multiple, (value // multiple) * multiple)
    return lower, lower + multiple if lower < value else lower


def join_prompt(scene: str, sound: str) -> str:
    """The one text the model is sent. The model's card has one prompt and no field for sound, so what happens and what you hear are two boxes on the page and are joined here, the sound
    after the scene in a sentence of its own (DESIGN.md §46.9). How best to word it is for the Spark's first clips to settle; until then it is plain: the scene, a full stop if it has
    none, then "Sound:" and the person's words, which they can make as long or as short as they like."""
    scene, sound = " ".join(scene.split()), " ".join(sound.split())
    if not sound:
        return scene
    if scene and scene[-1] not in ".!?":
        scene += "."
    return f"{scene} Sound: {sound}"


def video_limits(settings: Any, info: VideoEngineInfo, history: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    """`capabilities.limits.video` (DESIGN.md §46.10): every number the form obeys, so that the page repeats none of them.

    `estimate` is how long a clip takes: the engine's table of measured times (which is from one setup of one machine, and says so in `source`), the length buckets the page sorts clips
    into (the upper edges: the form's own length choices, so that "about this long" means what the form offers), and `history`, the times of the clips that were made HERE (`VideoStore.timings`),
    from which the page computes the estimate whenever there are clips of about the length asked for, and falls back to the table when there are not (DESIGN.md §46.8, as changed)."""
    choices = [s for s in SECONDS_CHOICES if s <= settings.video_max_seconds]
    return {
        "size": {"multiple": info.size_multiple, "min": info.size_min, "max": info.size_max, "default": [info.size_default[0], info.size_default[1]],
                 "presets": [preset.as_dict() for preset in info.size_presets]},
        "seconds": {"min": SECONDS_MIN, "max": settings.video_max_seconds, "default": min(SECONDS_DEFAULT, settings.video_max_seconds),
                    "choices": [s for s in SECONDS_CHOICES if s <= settings.video_max_seconds], "long_from": LONG_FROM_SECONDS, "long_note": LONG_NOTE},
        "fps": list(info.fps_choices),
        "images": {"start": 1, "end": 0},  # one start picture; an end picture is not offered yet
        "sound_chars": SOUND_CHARS,
        "prompt_chars": settings.max_prompt_chars,
        "estimate": {**info.estimate.as_dict(), "buckets": choices, "history": [dict(entry) for entry in history]},
        "qualities": {"default": "draft", "offered": list(OFFERED_QUALITIES)},
    }
