"""Domain error hierarchy.

Only the UI layer converts these into user-facing messages; the core raises them.
Every error carries a human readable ``message`` attribute.
"""

from __future__ import annotations


class AievaError(Exception):
    """Base class for every error raised by Aieva."""

    def __init__(self, message: str = "", *, detail: str = "") -> None:
        self.message = message or self.__class__.__name__
        self.detail = detail
        super().__init__(self.message)

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.detail:
            return f"{self.message} ({self.detail})"
        return self.message


class ParseError(AievaError):
    """Raised when user/LLM supplied text cannot be parsed safely."""


class OcrError(AievaError):
    """Raised when optical character recognition fails."""


class SolveError(AievaError):
    """Raised when a problem cannot be solved symbolically."""


class VisualizationError(AievaError):
    """Raised when a figure cannot be produced."""


class CloudError(AievaError):
    """Raised when the fog/cloud server is unreachable or returns an error."""


class PluginError(AievaError):
    """Raised when a subject plugin misbehaves or is not registered."""


class CacheError(AievaError):
    """Raised for unusable cache entries (never fatal - the cache is best effort)."""


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
