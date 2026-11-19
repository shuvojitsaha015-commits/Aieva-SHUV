"""Charts for every subject.

A chart is not a maths thing. A table of speeds in physics, a table of pH
values in chemistry and a table of counts in biology are all charts - so the
renderer lives in the **core** and not in the maths plugin. Every subject
plugin can use it, and a new subject (physics, chemistry, biology) needs
nothing but a call to :func:`chart_figure`.

The data of a chart is a list of labels with a list of values::

    ChartData(labels=["Mon", "Tue", "Wed"], values=[12.0, 15.0, 9.0])

Three kinds are drawn:

* **bar** - a comparison of the values,
* **line** - a development over time (or over the labels),
* **pie** - a share of the whole.

The table itself is read by Gemini - it comes with the reading of the board
(as ``chart`` in the answer of the OCR). When the table is written as text
(a row of numbers, a list of pairs), :func:`parse_table` understands the
common shapes.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The kinds of chart that can be drawn.
CHART_KINDS = ("bar", "line", "pie")

#: The colours of the bars / the line (they fit the dark theme of the board).
SERIES_COLORS = ("#1f77b4", "#7a5af5", "#2ca02c", "#d62728", "#ff9f1c", "#17becf")

#: The colour of the axis and the text.
AXIS_COLOR = "#444444"


@dataclass
class ChartData:
    """The data of a chart: labels with values."""

    #: What the labels mean (the headline of the chart).
    title: str = ""
    #: The names of the bars / the points.
    labels: list[str] = field(default_factory=list)
    #: The numbers.
    values: list[float] = field(default_factory=list)
    #: The kind of the chart (``bar``, ``line`` or ``pie``).
    kind: str = "bar"
    #: The name of the unit of the values (shown on the axis).
    unit: str = ""

    def __post_init__(self) -> None:
        self.kind = (self.kind or "bar").strip().lower()
        if self.kind not in CHART_KINDS:
            self.kind = "bar"
        # the labels and the values have to be as long as the shorter one
        count = min(len(self.labels), len(self.values))
        self.labels = list(self.labels)[:count]
        self.values = [float(value) for value in list(self.values)[:count]]

    def is_empty(self) -> bool:
        """``True`` when there is nothing to draw."""
        return not self.values

    def to_dict(self) -> dict[str, Any]:
        """The data as a plain dictionary (it goes into the JSON result)."""
        return {
            "title": self.title,
            "labels": list(self.labels),
            "values": list(self.values),
            "kind": self.kind,
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ChartData:
        """Read the data back from a dictionary."""
        if not isinstance(payload, dict):
            return cls()
        labels = [str(item) for item in (payload.get("labels") or [])]
        values: list[float] = []
        for item in payload.get("values") or []:
            try:
                values.append(float(item))
            except (TypeError, ValueError):
                continue
        return cls(
            title=str(payload.get("title") or ""),
            labels=labels,
            values=values,
            kind=str(payload.get("kind") or "bar"),
            unit=str(payload.get("unit") or ""),
        )


def _style_axis(ax: Any, data: ChartData) -> None:
    """The look of the axis (the same as the other graphs of the board)."""
    ax.set_title(data.title or "", fontsize=13)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS_COLOR)
    ax.spines["bottom"].set_color(AXIS_COLOR)
    ax.tick_params(colors=AXIS_COLOR, labelsize=9)
    ax.grid(axis="y", color="#dddddd", linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)


def bar_chart(
    data: ChartData,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> Any:
    """A bar chart - a comparison of the values."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    positions = list(range(len(data.values)))
    bars = ax.bar(
        positions,
        data.values,
        color=SERIES_COLORS[0],
        edgecolor="none",
    )
    for bar, value in zip(bars, data.values, strict=True):
        ax.annotate(
            _number(value),
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=AXIS_COLOR,
        )
    ax.set_xticks(positions)
    ax.set_xticklabels(data.labels)
    if data.unit:
        ax.set_ylabel(data.unit)
    _style_axis(ax, data)
    fig.tight_layout()
    return fig


def line_chart(
    data: ChartData,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> Any:
    """A line chart - the development of the values."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    positions = list(range(len(data.values)))
    ax.plot(
        positions,
        data.values,
        color=SERIES_COLORS[0],
        linewidth=2.0,
        marker="o",
        markersize=5,
    )
    ax.set_xticks(positions)
    ax.set_xticklabels(data.labels)
    if data.unit:
        ax.set_ylabel(data.unit)
    _style_axis(ax, data)
    fig.tight_layout()
    return fig


def pie_chart(
    data: ChartData,
    figsize: tuple[float, float] = (6.0, 5.5),
    dpi: int = 100,
) -> Any:
    """A pie chart - the share of every value."""
    import matplotlib.pyplot as plt

    total = sum(abs(value) for value in data.values)
    if total <= 0:
        total = 1.0
    shares = [abs(value) / total for value in data.values]
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    wedges, _texts, autotexts = ax.pie(
        shares,
        labels=data.labels,
        autopct="%1.1f%%",
        colors=list(SERIES_COLORS)[: len(shares)] or None,
        startangle=90,
        textprops={"fontsize": 9, "color": AXIS_COLOR},
    )
    for text in autotexts:
        text.set_color("#ffffff")
    ax.set_title(data.title or "", fontsize=13)
    ax.axis("equal")
    fig.tight_layout()
    return fig


def chart_figure(
    data: ChartData,
    figsize: tuple[float, float] = (7.0, 5.0),
    dpi: int = 100,
) -> Any:
    """The figure of the chart - the kind of the data decides the drawing."""
    if data.is_empty():
        raise ValueError("There is nothing to draw")
    if data.kind == "pie":
        return pie_chart(data, figsize=figsize, dpi=dpi)
    if data.kind == "line":
        return line_chart(data, figsize=figsize, dpi=dpi)
    return bar_chart(data, figsize=figsize, dpi=dpi)


# --------------------------------------------------------------------- tables
#: ``label: value`` - the simplest table of all.
_PAIR_RE = re.compile(r"([A-Za-z0-9_][A-Za-z0-9 _.\-/]*?)\s*[:=]\s*(-?\d+(?:\.\d+)?)")

#: A row of numbers only (``12, 15, 9``).
_ROW_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?(?:\s*[,;]\s*-?\d+(?:\.\d+)?)*)\s*$")


def parse_table(text: str, kind: str = "bar", title: str = "") -> ChartData | None:
    """Read a table out of a text.

    Two shapes are understood:

    * ``Mon: 12, Tue: 15, Wed: 9`` - a name with a number,
    * ``12, 15, 9`` - only the numbers (the labels are counted).

    ``None`` comes back when the text is not a table.
    """
    if not text:
        return None
    pairs = _PAIR_RE.findall(text)
    if pairs:
        labels = [label.strip() for label, _value in pairs]
        values = [float(value) for _label, value in pairs]
        if labels and values:
            return ChartData(title=title, labels=labels, values=values, kind=kind)

    row = _ROW_RE.match(text)
    if row:
        values = [float(part.strip()) for part in row.group(1).split(",") if part.strip()]
        if len(values) >= 2:
            labels = [str(index + 1) for index in range(len(values))]
            return ChartData(title=title, labels=labels, values=values, kind=kind)
    return None


def _number(value: float) -> str:
    """A short form of a number (no trailing zeros)."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


__all__ = [
    "AXIS_COLOR",
    "CHART_KINDS",
    "SERIES_COLORS",
    "ChartData",
    "bar_chart",
    "chart_figure",
    "line_chart",
    "parse_table",
    "pie_chart",
]
