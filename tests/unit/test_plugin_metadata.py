"""The architecture must serve the whole product, not only mathematics.

These tests lock in the parts of the design that every future subject
(Biology, Chemistry, Physics) and the voice layer rely on.
"""

from __future__ import annotations

import pytest

from aieva.core.errors import PluginError
from aieva.core.models import VisualizationSession
from aieva.core.plugin_base import PluginMeta
from aieva.core.plugin_registry import PluginRegistry, get_plugin, subject_metas
from aieva.plugins.math.plugin import MathPlugin


def test_math_plugin_publishes_metadata() -> None:
    meta = MathPlugin().meta()
    assert meta.name == "math"
    assert meta.display_name == "Mathematics"
    assert meta.description
    assert "equation_plot" in meta.provides
    assert meta.available is True


def test_plugin_meta_reports_missing_requirements() -> None:
    meta = PluginMeta(name="chemistry", requires=("a_package_that_does_not_exist",))
    assert meta.available is False
    assert meta.missing_requirements() == ["a_package_that_does_not_exist"]


def test_subject_metas_are_ordered_and_generic() -> None:
    metas = subject_metas(only_available=False)
    assert any(meta.name == "math" for meta in metas)
    assert all(isinstance(meta, PluginMeta) for meta in metas)
    orders = [meta.order for meta in metas]
    assert orders == sorted(orders)


def test_registry_can_hold_a_second_subject(tmp_path) -> None:
    """A second plugin must show up without any change in the core."""
    package = tmp_path / "extra_plugins"
    package.mkdir()
    (package / "__init__.py").write_text('"""Extra plugins."""\n')
    (package / "biology").mkdir()
    (package / "biology" / "__init__.py").write_text('"""Biology."""\n')
    (package / "biology" / "plugin.py").write_text(
        '"""A minimal second subject."""\n\n'
        "from aieva.core.plugin_base import SubjectPlugin\n\n\n"
        "class BiologyPlugin(SubjectPlugin):\n"
        '    name = "biology"\n'
        '    display_name = "Biology"\n'
        '    description = "Organs, cells and simulations."\n'
        "    order = 20\n"
        '    requires = ("a_package_that_does_not_exist",)\n\n'
        "    def parse(self, parsed_input):\n"
        "        return parsed_input\n\n"
        "    def solve(self, parsed_input):\n"
        "        return None\n\n"
        "    def visualize(self, parsed_input, **opts):\n"
        "        return None\n"
    )
    registry = PluginRegistry()
    registry.discover(package="extra_plugins", package_path=str(package))
    assert "biology" in registry.names()

    metas = registry.subjects()
    biology = next(meta for meta in metas if meta.name == "biology")
    assert biology.available is False  # the optional dependency is missing
    assert "biology" not in [meta.name for meta in registry.available_subjects()]


def test_create_session_is_optional() -> None:
    """A plugin without dynamic parameters returns ``None``."""
    plugin = MathPlugin()
    assert plugin.create_session is not None


def test_math_session_implements_the_protocol() -> None:
    from aieva.core.models import ParsedInput

    plugin = MathPlugin()
    parsed = plugin.parse(ParsedInput(raw="y = m*x + c", kind="text"))
    session = plugin.create_session(parsed)
    assert isinstance(session, VisualizationSession)
    assert {spec.name for spec in session.parameters} == {"m", "c"}
    assert session.figure is not None


def test_core_never_imports_kivy() -> None:
    """The core and the plugins must stay headless."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for folder in ("aieva/core", "aieva/plugins"):
        for path in (root / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "import kivy" in text or "from kivy" in text:
                offenders.append(str(path.relative_to(root)))
    assert offenders == []


def test_unknown_subject_raises() -> None:
    with pytest.raises(PluginError):
        get_plugin("does-not-exist")
