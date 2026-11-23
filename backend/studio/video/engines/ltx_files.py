"""Finding the five model files LTX-2.5 needs, in the folder the person already has them in (DESIGN.md §46.7, as changed: the files are not downloaded by the studio).

The program is given each file by its own flag (`--transformer-path`, `--text-encoder-path`, `--video-vae-path`, `--audio-vae-path`, `--spatial-upsampler-path`), so the studio must
say which file is which. A person who has set `STUDIO_VIDEO_MODELS_DIR` to a folder laid out the way ComfyUI lays models out (`diffusion_models/`, `text_encoders/`, `vae/`,
`latent_upscale_models/`) can leave the file names empty and each is found in its usual folder by a word in its name; a person whose files are named otherwise sets the name in
`STUDIO_VIDEO_TRANSFORMER` and the others. Either way the answer is a list of problems in words (the path that is missing, or the names that were found and the setting that picks
one), never a guess among several files: the wrong checkpoint would make a clip that is wrong in a way nobody can see.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# The five files, in the order the program's flags list them. `kind` is also the key of `EngineConfig.files`.
KINDS = ("transformer", "text_encoder", "video_vae", "audio_vae", "upsampler")

# Where each kind is looked for under the models folder, and the words that tell it from its neighbours in that folder (the VAE folder holds two files: the picture's and the
# sound's). A file that matches none of the words is still taken when it is the only one in its folder.
FOLDERS = {"transformer": "diffusion_models", "text_encoder": "text_encoders", "video_vae": "vae", "audio_vae": "vae", "upsampler": "latent_upscale_models"}
WORDS = {"transformer": ("distilled",), "text_encoder": ("gemma",), "video_vae": ("video",), "audio_vae": ("audio",), "upsampler": ("spatial", "upscal")}
SETTINGS = {"transformer": "STUDIO_VIDEO_TRANSFORMER", "text_encoder": "STUDIO_VIDEO_TEXT_ENCODER", "video_vae": "STUDIO_VIDEO_VIDEO_VAE",
            "audio_vae": "STUDIO_VIDEO_AUDIO_VAE", "upsampler": "STUDIO_VIDEO_UPSAMPLER"}
LABELS = {"transformer": "the distilled model", "text_encoder": "the text encoder", "video_vae": "the picture VAE", "audio_vae": "the sound VAE", "upsampler": "the spatial upsampler"}
# A name with one of these in it is a smaller copy of a model (quantized to fewer bits): used only when the person asks for it by name, or when it is the only one there is.
SMALLER_COPIES = ("fp8", "fp4", "nvfp4", "int8", "int4", "gguf", "q4", "q5", "q6", "q8")


@dataclass(frozen=True)
class ModelFiles:
    """The five files, each an absolute path that exists (the text encoder may be a folder: a model in Hugging Face's own layout)."""

    transformer: Path
    text_encoder: Path
    video_vae: Path
    audio_vae: Path
    upsampler: Path

    def as_dict(self) -> dict[str, str]:
        return {kind: str(getattr(self, kind)) for kind in KINDS}


@dataclass(frozen=True)
class FileProblem:
    """Why one file could not be found: `message` says what is missing and where, `hint` says which setting settles it."""

    kind: str
    message: str
    hint: str


def _listing(folder: Path) -> list[Path]:
    """What is in a folder, sorted by name; a folder that cannot be read is empty."""
    try:
        return sorted(folder.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []


def _names(paths: list[Path]) -> str:
    return ", ".join(p.name for p in paths) if paths else "nothing"


def find_one(kind: str, models_dir: Optional[Path], configured: str) -> tuple[Optional[Path], Optional[FileProblem]]:
    """The file for one kind: (its path, None) or (None, the problem). A configured name is taken as it is (relative to the models folder, or absolute) and must exist; an empty one
    is looked for in the kind's usual folder."""
    setting = SETTINGS[kind]
    set_it = f"Set {setting} to its file name (relative to STUDIO_VIDEO_MODELS_DIR, or a full path)."
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            if models_dir is None:
                return None, FileProblem(kind, f"{setting} is a relative name ({configured}) but STUDIO_VIDEO_MODELS_DIR is not set.", "Set STUDIO_VIDEO_MODELS_DIR to the folder that holds the model files.")
            path = models_dir / path
        if not path.exists():
            return None, FileProblem(kind, f"The file for {LABELS[kind]} is not there: {path}", f"Check {setting}, and that the folder is shared with the container (docker compose).")
        return path, None
    if models_dir is None:
        return None, FileProblem(kind, f"Where {LABELS[kind]} is kept is not set.", "Set STUDIO_VIDEO_MODELS_DIR to the folder that holds diffusion_models, text_encoders, vae and latent_upscale_models.")
    folder = models_dir / FOLDERS[kind]
    if not folder.is_dir():
        return None, FileProblem(kind, f"The folder for {LABELS[kind]} is not there: {folder}", f"Check STUDIO_VIDEO_MODELS_DIR, or {set_it}")
    entries = [p for p in _listing(folder) if not p.name.startswith(".")]
    if kind in ("video_vae", "audio_vae"):  # the folder holds both VAEs: the other one's file is never a candidate, not even as the only file left
        other = WORDS["audio_vae" if kind == "video_vae" else "video_vae"]
        entries = [p for p in entries if not any(word in p.name.lower() for word in other) or any(word in p.name.lower() for word in WORDS[kind])]
    named = [p for p in entries if any(word in p.name.lower() for word in WORDS[kind])]
    candidates = named or (entries if len(entries) == 1 else [])
    if len(candidates) > 1:  # prefer the full-size copy over a smaller one
        full = [p for p in candidates if not any(mark in p.name.lower() for mark in SMALLER_COPIES)]
        candidates = full or candidates
    if len(candidates) == 1:
        return candidates[0], None
    if not candidates:
        return None, FileProblem(kind, f"No file for {LABELS[kind]} was found in {folder} (it holds: {_names(entries)}).", set_it)
    return None, FileProblem(kind, f"More than one file could be {LABELS[kind]} in {folder}: {_names(candidates)}.", set_it)


def find_files(models_dir: Optional[Path], configured: dict[str, str]) -> tuple[Optional[ModelFiles], list[FileProblem]]:
    """All five files, or every problem found (not only the first, so that one look at the Video tab says everything that must be put right)."""
    found: dict[str, Path] = {}
    problems: list[FileProblem] = []
    for kind in KINDS:
        path, problem = find_one(kind, models_dir, configured.get(kind, ""))
        if path is not None:
            found[kind] = path
        elif problem is not None:
            problems.append(problem)
    if problems:
        return None, problems
    return ModelFiles(**found), []
