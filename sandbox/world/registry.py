from __future__ import annotations

from typing import Dict, List, Type

from .base import World

_REGISTRY: Dict[str, Type[World]] = {}


def register_world(cls: Type[World]) -> Type[World]:
    _REGISTRY[cls.name] = cls
    return cls


def get_world(name: str, seed: int = 0) -> World:
    _ensure_builtin()
    if name not in _REGISTRY:
        raise KeyError(f"unknown world '{name}'. known: {sorted(_REGISTRY)}")
    return _REGISTRY[name](seed=seed)


def list_worlds() -> List[str]:
    _ensure_builtin()
    return sorted(_REGISTRY)


def _ensure_builtin() -> None:
    # Import side-effect registers the built-in worlds.
    from . import worlds  # noqa: F401
