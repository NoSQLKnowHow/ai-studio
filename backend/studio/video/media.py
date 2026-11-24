"""ffmpeg and ffprobe, for clips (DESIGN.md §46.9): reading a finished file's own facts, checking it, making it play everywhere, and its poster and thumbnail.

Everything here is synchronous (it runs a program and waits); callers run it in a thread. A program that is missing, fails or says something unreadable is a `MediaError`
whose message is a sentence a person can read, never a traceback.

The rule behind `probe_clip` is the same as for Speech's audio (DESIGN.md §38.4): the studio trusts the file's own header over anything the engine says about it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

from PIL import Image

PROGRAM_SECONDS = 600  # a remux takes a second and a conversion of a long clip a few minutes; a program that takes longer than this is stuck
BROWSER_VIDEO = ("h264",)  # what every browser and phone plays (with the pixel format below)
BROWSER_PIXEL_FORMATS = ("yuv420p", "yuvj420p")
BROWSER_AUDIO = ("aac",)
THUMB_MAX = 512


class MediaError(Exception):
    """ffmpeg or ffprobe could not do what was asked; the message says why, in words."""


@dataclass(frozen=True)
class Tools:
    """Whether the two programs can be run here (`capabilities.video.tools`)."""

    ffmpeg: bool
    ffprobe: bool

    @property
    def ok(self) -> bool:
        return self.ffmpeg and self.ffprobe

    def reason(self) -> Optional[str]:
        missing = [name for name, found in (("ffmpeg", self.ffmpeg), ("ffprobe", self.ffprobe)) if not found]
        return None if not missing else f"{' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} not installed, and a clip cannot be read or made playable without {'it' if len(missing) == 1 else 'them'}."

    def as_dict(self) -> dict[str, bool]:
        return {"ffmpeg": self.ffmpeg, "ffprobe": self.ffprobe}


def find_tools(ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> Tools:
    """Look for the two programs on the PATH (or at the path given)."""
    return Tools(ffmpeg=shutil.which(ffmpeg) is not None, ffprobe=shutil.which(ffprobe) is not None)


@dataclass(frozen=True)
class ClipFacts:
    """What a clip file says of itself. `frames` is the picture track's own count (or, where the container gives none, the duration times the rate)."""

    width: int
    height: int
    fps: float
    frames: int
    seconds: float  # the picture track's length (the sound is a little shorter or longer; that is the file's way)
    video_codec: str
    pixel_format: str
    has_audio: bool
    audio_codec: Optional[str]
    audio_channels: Optional[int]
    audio_rate: Optional[int]
    bytes: int
    audio_seconds: Optional[float] = None  # the sound track's own length, which is the file's to say (the real program's is a few ms shorter than its picture)

    @property
    def playable_everywhere(self) -> bool:
        """H.264 in a pixel format every browser takes, with AAC sound if there is any: a file that is, is only remuxed (its streams are copied, not converted)."""
        return (self.video_codec in BROWSER_VIDEO and self.pixel_format in BROWSER_PIXEL_FORMATS
                and (not self.has_audio or self.audio_codec in BROWSER_AUDIO))


def _run(argv: list[str], what: str) -> subprocess.CompletedProcess[str]:
    """Run a program and return its result, or raise `MediaError` with a sentence for a program that is missing, is stuck or could not be started."""
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=PROGRAM_SECONDS, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise MediaError(f"{argv[0]} is not installed, so {what} could not be done.") from None
    except subprocess.TimeoutExpired:
        raise MediaError(f"{argv[0]} took too long to {what} and was stopped.") from None
    except OSError as exc:
        raise MediaError(f"{argv[0]} could not be run ({exc.strerror or exc}).") from None


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else "it gave no reason"


def probe_clip(ffprobe: str, path: Path) -> ClipFacts:
    """Read a clip's facts with ffprobe. Raises `MediaError` for a file ffprobe cannot read or that has no picture track."""
    done = _run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], "read the clip")
    if done.returncode != 0:
        raise MediaError(f"The clip could not be read: {_last_line(done.stderr)}")
    try:
        found = json.loads(done.stdout)
    except ValueError:
        raise MediaError("The clip could not be read: ffprobe's answer was not understood.") from None
    streams = found.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError("The file has no picture in it.")
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fps = _rate(video.get("avg_frame_rate")) or _rate(video.get("r_frame_rate")) or 0.0
    seconds = _float(video.get("duration")) or _float((found.get("format") or {}).get("duration")) or 0.0
    frames = _int(video.get("nb_frames")) or (round(seconds * fps) if fps and seconds else 0)
    return ClipFacts(
        width=_int(video.get("width")) or 0, height=_int(video.get("height")) or 0, fps=fps, frames=frames, seconds=seconds,
        video_codec=str(video.get("codec_name") or ""), pixel_format=str(video.get("pix_fmt") or ""),
        has_audio=audio is not None, audio_codec=str(audio.get("codec_name")) if audio else None,
        audio_channels=_int(audio.get("channels")) if audio else None, audio_rate=_int(audio.get("sample_rate")) if audio else None,
        bytes=path.stat().st_size, audio_seconds=(_float(audio.get("duration")) or None) if audio else None,
    )


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rate(value: Any) -> Optional[float]:
    """A frame rate as ffprobe writes it, `24/1` or `30000/1001`; None for `0/0`, which it writes for a track that has none."""
    try:
        rate = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None
    return float(rate) if rate > 0 else None


# How far the sound's length may be from the picture's before the clip gets a note (DESIGN.md §46.13 criterion 487). The real program's sound is 31 ms short at 5 s and at 30 s, and 45 ms at
# the tiny size (MEASURED, 2026-11-19/20): that is how the file is made, and is not mentioned. A difference above this is a sound that stops early or runs on, which a person should know.
SYNC_TOLERANCE_MS = 100


def sync_note(facts: ClipFacts) -> Optional[str]:
    """A sentence for a clip whose sound and picture differ in length by more than `SYNC_TOLERANCE_MS`, or None (no sound, no length known, or a difference that is how the file is made)."""
    if not facts.has_audio or not facts.audio_seconds or not facts.seconds:
        return None
    difference = round(abs(facts.audio_seconds - facts.seconds) * 1000)
    if difference <= SYNC_TOLERANCE_MS:
        return None
    return f"The sound and the picture differ by {difference} ms: the sound {'stops early' if facts.audio_seconds < facts.seconds else 'runs on after the picture'}."


def check_output(facts: ClipFacts, *, width: int, height: int, frames: int, fps: int, tolerance: float = 0.05) -> Optional[str]:
    """Whether a clip an engine wrote is the clip that was asked for: a sentence saying how it is not, or None when it is. The picture must be the size asked for, and its
    length within `tolerance` (5%, but at least a quarter of a second) of what the frames and the rate come to. An engine that stops early or writes a still is caught here."""
    if (facts.width, facts.height) != (width, height):
        return f"The program wrote a {facts.width}x{facts.height} clip; {width}x{height} was asked for."
    expected = frames / fps
    allowed = max(0.25, expected * tolerance)
    if abs(facts.seconds - expected) > allowed:
        return f"The program wrote a clip of {facts.seconds:.1f} seconds; about {expected:.1f} were asked for."
    return None


def finish_clip(ffmpeg: str, ffprobe: str, source: Path, target: Path, *, facts: ClipFacts, keep_sound: bool, comment: str, title: str,
                trim_to: Optional[tuple[int, int]] = None) -> ClipFacts:
    """Make the file the studio keeps from the one the engine wrote, and return its facts: the streams copied if they already play everywhere (H.264 and AAC), converted if not,
    with the sound taken out if the person asked for none, the index at the front (`faststart`, so that it starts playing before it is all downloaded) and, in its file
    information, the licence notice (as the comment) and the words that made it (as the title; MP4 has no place for the name of the program that finished it, and ffmpeg drops a
    tag it cannot place, so none is asked for). The new file is written beside the final name and renamed into it, so that a half-written file is never taken for a clip.

    `trim_to` is a (width, height) smaller than the clip by a few pixels, for the sizes the model cannot make itself (HD 1920x1080 is made 1920x1088; DESIGN.md §46.20): the picture
    is cut to it from the middle, which means it is converted once more (H.264 at CRF 18, the quality the studio's other conversion uses: on a detailed test picture it changed the picture by
    0.27 of 255 on average, which is not to be seen), and the sound is copied as it is. How big the file then is, for the program's real clips, is for the Spark's first HD clip to say."""
    partial = target.with_name(target.name + ".part.mp4")
    partial.unlink(missing_ok=True)
    argv = [ffmpeg, "-v", "error", "-y", "-i", str(source), "-map", "0:v:0"]
    if keep_sound and facts.has_audio:
        argv += ["-map", "0:a:0"]
    if trim_to is not None:
        width, height = trim_to
        if not (0 < width <= facts.width and 0 < height <= facts.height) or width % 2 or height % 2:
            raise MediaError(f"A {facts.width}x{facts.height} clip cannot be trimmed to {width}x{height}.")
        argv += ["-vf", f"crop={width}:{height}:{(facts.width - width) // 2}:{(facts.height - height) // 2}",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium"]
        if keep_sound and facts.has_audio:
            argv += ["-c:a", "copy"] if facts.audio_codec in BROWSER_AUDIO else ["-c:a", "aac", "-b:a", "192k"]
    elif facts.playable_everywhere:
        argv += ["-c", "copy"]
    else:  # a codec some browsers or phones cannot play: converted once, here (DESIGN.md §46.9)
        argv += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium"]
        if keep_sound and facts.has_audio:
            argv += ["-c:a", "aac", "-b:a", "192k"]
    argv += ["-movflags", "+faststart", "-metadata", f"comment={comment}", "-metadata", f"title={title}", str(partial)]
    done = _run(argv, "finish the clip")
    if done.returncode != 0 or not partial.is_file():
        partial.unlink(missing_ok=True)
        raise MediaError(f"The clip could not be finished: {_last_line(done.stderr)}")
    os.replace(partial, target)
    return probe_clip(ffprobe, target)


def make_poster(ffmpeg: str, clip: Path, poster: Path) -> None:
    """The first frame, full size, as a JPEG: what the player shows before it plays (and what the page uses as the clip's picture)."""
    partial = poster.with_name(poster.name + ".part.jpg")
    partial.unlink(missing_ok=True)
    done = _run([ffmpeg, "-v", "error", "-y", "-i", str(clip), "-frames:v", "1", "-q:v", "3", str(partial)], "make the clip's poster")
    if done.returncode != 0 or not partial.is_file():
        partial.unlink(missing_ok=True)
        raise MediaError(f"The clip's poster could not be made: {_last_line(done.stderr)}")
    os.replace(partial, poster)


def make_thumbnail(poster: Path, thumb: Path) -> None:
    """A small WebP of the poster, for the queue and the history grid (as a picture's thumbnail is). Written beside its name and renamed, like every file here."""
    thumb.parent.mkdir(parents=True, exist_ok=True)
    partial = thumb.with_name(thumb.name + ".part")
    try:
        with Image.open(poster) as image:
            image.load()
            small = image.convert("RGB")
        small.thumbnail((THUMB_MAX, THUMB_MAX), Image.Resampling.LANCZOS)
        small.save(partial, format="WEBP", quality=80, method=4)
        os.replace(partial, thumb)
    finally:
        partial.unlink(missing_ok=True)


def prepare_start_picture(source: Path, target: Path, width: int, height: int) -> None:
    """Make a start picture the clip's own size (DESIGN.md §46.11): cut to the clip's shape from the middle (a cover crop, never a stretch), made RGB (a picture with transparency is laid
    on white), and saved as a PNG. What the model does with a picture of another size is not known, so it is never asked to guess."""
    from PIL import ImageOps

    with Image.open(source) as opened:
        opened.load()
        picture = ImageOps.exif_transpose(opened)
        if picture.mode in ("RGBA", "LA", "PA") or "transparency" in picture.info:
            rgba = picture.convert("RGBA")
            flat = Image.new("RGB", rgba.size, (255, 255, 255))
            flat.paste(rgba, mask=rgba.getchannel("A"))
            picture = flat
        picture = ImageOps.fit(picture.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        picture.save(partial, format="PNG")
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
