"""The charts of the board (every subject can use them)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg", force=False)

from pathlib import Path

import pytest

from aieva.core.charts import (
    CHART_KINDS,
    ChartData,
    bar_chart,
    chart_figure,
    line_chart,
    parse_table,
    pie_chart,
)


@pytest.fixture(autouse=True)
def _close_the_figures():
    """Every figure of the test is closed again (matplotlib counts them)."""
    yield
    import matplotlib.pyplot as plt

    plt.close("all")


def test_the_data_keeps_the_labels_and_the_values_apart() -> None:
    data = ChartData(labels=["Mon", "Tue", "Wed"], values=[12.0, 15.5, 9.0])
    assert len(data.labels) == 3
    assert len(data.values) == 3
    assert not data.is_empty()


def test_too_many_labels_are_cut_off() -> None:
    data = ChartData(labels=["a", "b", "c"], values=[1.0, 2.0])
    assert len(data.labels) == 2
    assert len(data.values) == 2


def test_an_unknown_kind_becomes_a_bar_chart() -> None:
    assert ChartData(kind="sun").kind == "bar"


def test_the_data_can_be_written_down_and_read_back() -> None:
    data = ChartData(title="Speeds", labels=["a", "b"], values=[1.0, 2.0], kind="line", unit="m/s")
    payload = data.to_dict()
    again = ChartData.from_dict(payload)
    assert again.title == "Speeds"
    assert again.kind == "line"
    assert again.unit == "m/s"
    assert again.values == [1.0, 2.0]


def test_the_bar_chart_is_drawn(tmp_path: Path) -> None:
    data = ChartData(title="Marks", labels=["Mon", "Tue"], values=[12.0, 15.0])
    figure = bar_chart(data)
    target = tmp_path / "bar.png"
    figure.savefig(target, dpi=90)
    assert target.stat().st_size > 0


def test_the_line_chart_is_drawn(tmp_path: Path) -> None:
    data = ChartData(labels=["1", "2", "3"], values=[1.0, 4.0, 9.0], kind="line")
    figure = line_chart(data)
    target = tmp_path / "line.png"
    figure.savefig(target, dpi=90)
    assert target.stat().st_size > 0


def test_the_pie_chart_is_drawn(tmp_path: Path) -> None:
    data = ChartData(labels=["a", "b"], values=[30.0, 70.0], kind="pie")
    figure = pie_chart(data)
    target = tmp_path / "pie.png"
    figure.savefig(target, dpi=90)
    assert target.stat().st_size > 0


def test_the_kind_decides_the_drawing() -> None:
    bar = ChartData(labels=["a", "b"], values=[1.0, 2.0], kind="bar")
    line = ChartData(labels=["a", "b"], values=[1.0, 2.0], kind="line")
    pie = ChartData(labels=["a", "b"], values=[1.0, 2.0], kind="pie")
    assert chart_figure(bar) is not None
    assert chart_figure(line) is not None
    assert chart_figure(pie) is not None


def test_an_empty_chart_cannot_be_drawn() -> None:
    with pytest.raises(ValueError):
        chart_figure(ChartData())


def test_a_table_with_names_is_read() -> None:
    data = parse_table("Mon: 12, Tue: 15, Wed: 9")
    assert data is not None
    assert data.labels == ["Mon", "Tue", "Wed"]
    assert data.values == [12.0, 15.0, 9.0]


def test_a_row_of_numbers_is_read() -> None:
    data = parse_table("12, 15, 9")
    assert data is not None
    assert data.values == [12.0, 15.0, 9.0]
    assert len(data.labels) == 3


def test_a_text_that_is_no_table_gives_nothing() -> None:
    assert parse_table("hello world") is None
    assert parse_table("") is None


def test_the_kinds_are_known() -> None:
    assert "bar" in CHART_KINDS
    assert "line" in CHART_KINDS
    assert "pie" in CHART_KINDS


def test_the_maths_plugin_draws_a_table_as_a_chart() -> None:
    """The table of the board becomes a chart - not an expression."""
    from aieva.core.models import ParsedInput
    from aieva.plugins.math.plugin import MathPlugin

    result = MathPlugin().visualize(ParsedInput(raw="Mon: 12, Tue: 15, Wed: 9", kind="text"))
    assert result.meta["kind"] == "chart"
    assert result.figure is not None


def test_the_maths_plugin_still_draws_a_function() -> None:
    from aieva.core.models import ParsedInput
    from aieva.plugins.math.plugin import MathPlugin

    result = MathPlugin().visualize(ParsedInput(raw="y = x**2 + 3*x", kind="text"))
    assert result.meta["kind"] != "chart"
