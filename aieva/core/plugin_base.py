"""The contract every Aieva subject plugin implements.

A plugin turns a :class:`~aieva.core.models.ParsedInput` into a solution
(:class:`~aieva.core.models.SolveResult`) and/or a visualisation
(:class:`~aieva.core.models.VisualizationResult`).

Adding Biology / Chemistry / Physics later means writing one new module - the
core never has to change.

Plugins are **configuration driven** (see the master handoff document, section
7.4): every plugin publishes a :class:`PluginMeta` describing its name, the
optional packages it needs and the UI hints it gives. The UI builds itself from
that metadata, so no subject is ever hard-coded in the interface.
"""

from __future__ import annotations

import importlib.util
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(frozen=True)
class PluginMeta:
    """Static description of a subject plugin."""

    #: Short, unique, lower case identifier (e.g. ``"math"``).
    name: str
    #: Human readable name shown in the UI.
    display_name: str = ""
    #: One line explanation shown under the subject button.
    description: str = ""
    #: Importable module names the plugin needs (``"rdkit"``, ``"py3dmol"``, ...).
    requires: tuple[str, ...] = ()
    #: The features the plugin offers (see :meth:`SubjectPlugin.capabilities`).
    provides: tuple[str, ...] = ()
    #: Hints for the UI layer, e.g. ``{"viewer": "3d"}`` or ``{"editor": "grid"}``.
    ui_hints: dict[str, str] = field(default_factory=dict)
    #: Sort order in the subject list (lower comes first).
    order: int = 100

    def missing_requirements(self) -> list[str]:
        """The required packages that are not importable in this environment."""
        missing: list[str] = []
        for module in self.requires:
            try:
                found = importlib.util.find_spec(module) is not None
            except (ImportError, ValueError, ModuleNotFoundError):
                found = False
            if not found:
                missing.append(module)
        return missing

    @property
    def available(self) -> bool:
        """True when every optional dependency of the plugin is installed."""
        return not self.missing_requirements()


class SubjectPlugin(ABC):
    """Abstract base class of every subject plugin."""

    #: Short, unique, lower case identifier (e.g. ``"math"``).
    name: ClassVar[str] = ""

    #: Human readable name shown in the UI.
    display_name: ClassVar[str] = ""

    #: One line explanation shown under the subject button.
    description: ClassVar[str] = ""

    #: Optional packages this plugin needs (checked with :meth:`is_available`).
    requires: ClassVar[tuple[str, ...]] = ()

    #: Hints for the UI layer (``{"viewer": "3d"}`` ...).
    ui_hints: ClassVar[dict[str, str]] = {}

    #: Sort order in the subject list.
    order: ClassVar[int] = 100

    @abstractmethod
    def parse(self, parsed_input: Any) -> Any:
        """Normalise the input for this subject.

        The default implementation is a no-op; plugins override it when they
        need to interpret the raw text differently.
        """

    @abstractmethod
    def solve(self, parsed_input: Any) -> Any:
        """Solve the problem and return the result (with steps and warnings)."""

    @abstractmethod
    def visualize(self, parsed_input: Any, **opts: Any) -> Any:
        """Produce a figure for the problem."""

    def capabilities(self) -> list[str]:
        """The features this plugin supports (used by the UI to build menus)."""
        return []

    def create_session(self, parsed_input: Any, **opts: Any) -> Any | None:
        """Return an interactive visualisation (figure + sliders) if supported.

        The returned object must implement
        :class:`~aieva.core.models.VisualizationSession`. Plugins without
        dynamic parameters simply return ``None`` and the UI falls back to the
        static figure produced by :meth:`visualize`.
        """
        return None

    # ----------------------------------------------------------- metadata
    def meta(self) -> PluginMeta:
        """The metadata of this plugin (used to build the UI without hard-coding)."""
        return PluginMeta(
            name=self.name,
            display_name=self.display_name or self.name.title(),
            description=self.description,
            requires=tuple(self.requires),
            provides=tuple(self.capabilities()),
            ui_hints=dict(self.ui_hints),
            order=self.order,
        )

    def is_available(self) -> bool:
        """True when all optional dependencies of the plugin are installed."""
        return not self.meta().missing_requirements()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<{type(self).__name__} name={self.name!r}>"


__all__ = ["PluginMeta", "SubjectPlugin"]
