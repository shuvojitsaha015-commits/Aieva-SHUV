"""Phase 2: plugin discovery must work automatically."""

from __future__ import annotations

from pathlib import Path

import pytest

from aieva.core.errors import PluginError
from aieva.core.models import ParsedInput
from aieva.core.plugin_base import SubjectPlugin
from aieva.core.plugin_registry import PluginRegistry, available_plugins, get_plugin

PLUGIN_SOURCE = '''
"""A dummy plugin used by the tests."""

from aieva.core.models import ParsedInput, SolveResult, VisualizationResult
from aieva.core.plugin_base import SubjectPlugin


class DummyPlugin(SubjectPlugin):
    name = "dummy"
    display_name = "Dummy subject"

    def parse(self, parsed_input: ParsedInput) -> ParsedInput:
        return parsed_input

    def solve(self, parsed_input: ParsedInput) -> SolveResult:
        return SolveResult(problem_type="dummy", answer_text="42")

    def visualize(self, parsed_input: ParsedInput, **opts) -> VisualizationResult:
        return VisualizationResult(meta={"dummy": True})

    def capabilities(self) -> list[str]:
        return ["dummy_capability"]
'''


@pytest.fixture
def dummy_package(tmp_path: Path) -> Path:
    package = tmp_path / "dummy_plugins"
    package.mkdir()
    (package / "__init__.py").write_text('"""Dummy plugin package."""\n')
    (package / "dummy_subject").mkdir()
    (package / "dummy_subject" / "__init__.py").write_text('"""Dummy subject."""\n')
    (package / "dummy_subject" / "plugin.py").write_text(PLUGIN_SOURCE)
    return package


def test_discovery_registers_dropped_plugin(dummy_package: Path) -> None:
    registry = PluginRegistry()
    discovered = registry.discover(package="dummy_plugins", package_path=str(dummy_package))
    assert "dummy" in discovered
    plugin = registry.get("dummy")
    assert isinstance(plugin, SubjectPlugin)
    assert plugin.capabilities() == ["dummy_capability"]
    result = plugin.solve(ParsedInput(raw="anything"))
    assert result.answer_text == "42"


def test_unknown_plugin_raises() -> None:
    registry = PluginRegistry()
    with pytest.raises(PluginError):
        registry.get("nope")


def test_math_plugin_is_registered() -> None:
    """The real math plugin must be discoverable in the shipped package."""
    registry = PluginRegistry()
    registry.discover()
    assert "math" in registry.names()


def test_module_level_helpers() -> None:
    assert "math" in available_plugins()
    plugin = get_plugin("math")
    assert plugin.name == "math"
    assert plugin.capabilities()


def test_register_rejects_non_plugins() -> None:
    registry = PluginRegistry()
    with pytest.raises(PluginError):
        registry.register(object())  # type: ignore[arg-type]
