"""Kivy-free core of Aieva: models, parsing, caching and service abstractions.

Nothing in this package may import Kivy. The UI layer depends on the core, never
the other way around.
"""

from __future__ import annotations

from aieva.core.errors import (
    AievaError,
    CacheError,
    CloudError,
    OcrError,
    ParseError,
    PluginError,
    SolveError,
    VisualizationError,
)

__all__ = [
    "AievaError",
    "CacheError",
    "CloudError",
    "OcrError",
    "ParseError",
    "PluginError",
    "SolveError",
    "VisualizationError",
]
