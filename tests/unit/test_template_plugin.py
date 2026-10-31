"""The template plugin of Phase 12 - the proof that the architecture is ready.

The template shows how a subject is added. These tests check that it really
works and that it stays invisible in the application (a directory with a
leading underscore is ignored by the registry).
"""

from __future__ import annotations

import matplotlib
import pytest

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402

from aieva.core.errors import ParseError  # noqa: E402
from aieva.core.models import ParsedInput  # noqa: E402
from aieva.core.plugin_registry import PluginRegistry, subject_metas  # noqa: E402
from aieva.plugins._template_plugin.plugin import TemplatePlugin  # noqa: E402


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


def test_the_template_parses_a_number():
    plugin = TemplatePlugin()
    parsed = plugin.parse(ParsedInput(raw="42.5 m"))
    assert parsed.sympy_expr == pytest.approx(42.5)


def test_the_template_refuses_junk():
    plugin = TemplatePlugin()
    with pytest.raises(ParseError):
        plugin.parse(ParsedInput(raw=""))
    with pytest.raises(ParseError):
        plugin.parse(ParsedInput(raw="not a number"))


def test_the_template_solves():
    plugin = TemplatePlugin()
    result = plugin.solve(ParsedInput(raw="7"))
    assert result.answer_text == "7"
    assert result.steps


def test_the_template_draws():
    plugin = TemplatePlugin()
    result = plugin.visualize(ParsedInput(raw="3"))
    assert result.figure is not None
    assert result.meta["value"] == pytest.approx(3.0)
    assert result.figure.get_axes()


def test_the_template_publishes_metadata():
    meta = TemplatePlugin().meta()
    assert meta.name == "template"
    assert meta.display_name == "Template"
    assert meta.description
    assert meta.available is True


def test_the_template_is_not_registered():
    """The registry ignores the directories with a leading underscore."""
    names = [meta.name for meta in subject_metas(only_available=False)]
    assert "template" not in names
    assert "math" in names


def test_the_template_is_not_discovered_by_the_registry(tmp_path):
    registry = PluginRegistry()
    found = registry.discover(package_path=tmp_path)
    assert found == []


def test_a_copy_of_the_template_becomes_a_subject(tmp_path):
    """A copy of the template is a working subject - without a core change."""
    import shutil
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "aieva" / "plugins" / "_template_plugin"
    target = tmp_path / "biology"
    shutil.copytree(source, target)
    (target / "plugin.py").write_text(
        (target / "plugin.py")
        .read_text(encoding="utf-8")
        .replace('name = "template"', 'name = "biology"')
        .replace('display_name = "Template"', 'display_name = "Biology"'),
        encoding="utf-8",
    )

    registry = PluginRegistry()
    found = registry.discover(package_path=tmp_path)
    assert "biology" in found
    plugin = registry.get("biology")
    assert plugin.display_name == "Biology"
    assert plugin.visualize(ParsedInput(raw="5")).figure is not None


def test_the_template_does_not_import_kivy():
    from pathlib import Path

    source = Path(TemplatePlugin.__module__.replace(".", "/")).with_suffix(".py")
    text = Path(__import__("aieva.plugins._template_plugin.plugin", fromlist=["x"]).__file__)
    assert "import kivy" not in text.read_text(encoding="utf-8")
    assert source.name == "plugin.py"
