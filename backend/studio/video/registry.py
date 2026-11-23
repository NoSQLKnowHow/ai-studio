"""The list of video engines, and the one place that names them (DESIGN.md §46.6).

**Adding a model is one file in `engines/` and one line in `REAL_ENGINES` below.** Nothing else in the studio names an engine, and a test scans the source to keep it that way.
An engine is imported only when it is asked for. `STUDIO_PIPELINE=fake` offers the fake engine and nothing else; the real setting offers the real ones.
"""

from __future__ import annotations

import importlib
from typing import Any, Type

from ..pipelines.base import PipelineUnavailable
from .engine import EngineConfig, VideoEngine, VideoEngineInfo

# id -> (module, class). The first is the engine the studio offers.
REAL_ENGINES: dict[str, tuple[str, str]] = {
    "ltx": ("studio.video.engines.ltx", "LtxEngine"),
}
FAKE_ENGINES: dict[str, tuple[str, str]] = {
    "fake": ("studio.video.engines.fake", "FakeVideo"),
}

# Engines added while the program runs. Only a test does this (to prove that a new engine needs nothing else); the key is the engine's id.
_ADDED: dict[str, Type[Any]] = {}


class UnknownEngine(KeyError):
    """No engine has this id (or it is not offered by the current pipeline setting)."""


def register(engine_class: Type[Any]) -> None:
    """Add an engine class for the life of the process (tests)."""
    _ADDED[engine_class.INFO.id] = engine_class


def unregister(engine_id: str) -> None:
    _ADDED.pop(engine_id, None)


def engine_ids(pipeline: str) -> list[str]:
    """The ids of the engines this setting offers, in display order."""
    known = list(FAKE_ENGINES if pipeline == "fake" else REAL_ENGINES)
    known += [engine_id for engine_id in _ADDED if engine_id not in known]
    return known


def primary(pipeline: str) -> str:
    """The engine the studio offers: the first. (There is one video model; a second would need a choice on the page, which 1.27 does not have.)"""
    return engine_ids(pipeline)[0]


def engine_class(engine_id: str) -> Type[VideoEngine]:
    """The class of an engine, importing its module now. Raises `UnknownEngine`, or `PipelineUnavailable` when the module cannot be imported."""
    if engine_id in _ADDED:
        return _ADDED[engine_id]
    entry = FAKE_ENGINES.get(engine_id) or REAL_ENGINES.get(engine_id)
    if entry is None:
        raise UnknownEngine(engine_id)
    module_name, class_name = entry
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise PipelineUnavailable(f"The {engine_id} video engine could not be loaded ({exc}).", hint="See the server log.") from exc
    return getattr(module, class_name)


def info(engine_id: str) -> VideoEngineInfo:
    return engine_class(engine_id).INFO


def make_engine(engine_id: str, config: EngineConfig, variant: str = "") -> VideoEngine:
    """An engine ready to `load`. `variant` must be one the engine has (empty means its own default)."""
    cls = engine_class(engine_id)
    if variant and variant not in cls.INFO.variants:
        raise UnknownEngine(f"{engine_id}/{variant}")
    return cls(config, variant)  # type: ignore[call-arg]


def probe_engine(engine_id: str, config: EngineConfig) -> dict[str, Any]:
    """The engine's own check that it can run here (no weights loaded). Raises `PipelineError` (`PipelineUnavailable` for a reason a person can act on)."""
    return engine_class(engine_id).probe(config)
