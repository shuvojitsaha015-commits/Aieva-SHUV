"""The rate template: a tank that fills (or empties) with a net rate.

The model gives the inflow, the outflow and the volume of the tank. The
figure shows the quantity against the time and a small diagram of the tank
with the level.
"""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from aieva.core.errors import SolveError  # noqa: E402
from aieva.core.models import ParamSpec, Step, VisualizationResult  # noqa: E402


def solve(problem: Any) -> Any:
    """Solve the filling (or emptying) of the tank."""
    from aieva.plugins.math.wordproblems import WordProblemSolution

    inflow = problem.value("inflow", 0.0)
    outflow = problem.value("outflow", 0.0)
    volume = problem.value("volume", 0.0)
    net = inflow - outflow

    if volume <= 0:
        raise SolveError("The volume of the tank has to be positive")
    if abs(net) < 1e-12:
        raise SolveError("The inflow and the outflow are equal - the level never changes")

    if net > 0:
        time = (volume - problem.value("initial", 0.0)) / net
        meaning = "fills"
    else:
        time = problem.value("initial", 0.0) / (-net)
        meaning = "empties"

    if time < 0:
        raise SolveError("The tank would have to change in the past - check the data")

    steps = [
        Step(
            title="The net rate",
            explanation="What comes in minus what goes out.",
            latex=f"r = {inflow:g} - {outflow:g} = {net:g}\\,\\mathrm{{L/min}}",
        ),
        Step(
            title="How long",
            explanation=f"The tank {meaning} with that net rate.",
            latex=f"t = \\frac{{V}}{{r}} = {time:.4g}\\,\\mathrm{{min}}",
        ),
        Step(
            title="The level",
            explanation="The quantity against the time.",
            latex=f"V(t) = {problem.value('initial', 0.0):g} + {net:g}t",
        ),
    ]
    return WordProblemSolution(
        values={
            "time": time,
            "net_rate": net,
            "final_volume": problem.value("initial", 0.0) + net * time,
        },
        latex={
            "time": f"t = {time:.4g}\\,\\mathrm{{min}}",
            "net_rate": f"r = {net:g}\\,\\mathrm{{L/min}}",
        },
        steps=steps,
    )


def render(problem: Any, solution: Any) -> VisualizationResult:
    """Draw the quantity against the time and the tank diagram."""
    inflow = problem.value("inflow", 0.0)
    outflow = problem.value("outflow", 0.0)
    volume = problem.value("volume", 0.0)
    initial = problem.value("initial", 0.0)
    net = solution.values["net_rate"]
    time = solution.values["time"]

    times = np.linspace(0.0, max(time * 1.1, 1.0), 200)
    quantities = initial + net * times

    fig, (ax, tank) = plt.subplots(
        1, 2, figsize=(8.0, 5.0), dpi=100, gridspec_kw={"width_ratios": [2.0, 1.0]}
    )
    ax.plot(times, quantities, color="#1f77b4", linewidth=2.5, label="the level")
    ax.axhline(volume, color="#d62728", linestyle="--", linewidth=1.2, label="the capacity")
    ax.axvline(time, color="#2ca02c", linestyle=":", linewidth=1.6, label=f"t = {time:.3g} min")
    ax.plot([time], [initial + net * time], "o", color="#2ca02c", markersize=8, zorder=5)
    ax.set_xlabel("t (min)")
    ax.set_ylabel("volume (L)")
    ax.set_title("the tank level")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)

    # the tank
    tank.add_patch(Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor="#444444", linewidth=2))
    level = max(0.0, min(1.0, (initial + net * time) / volume if volume else 0.0))
    tank.add_patch(
        Rectangle((0.1, 0.1), 0.8, 0.8 * level, facecolor="#4080f0", edgecolor="none", alpha=0.55)
    )
    tank.text(
        0.5,
        0.94,
        f"{initial + net * time:.4g} / {volume:g} L",
        ha="center",
        color="#2ca02c",
        fontsize=11,
    )
    tank.text(
        0.5, 0.02, f"in {inflow:g} / out {outflow:g}", ha="center", color="#888888", fontsize=9
    )
    tank.set_xlim(0, 1)
    tank.set_ylim(0, 1)
    tank.set_xticks([])
    tank.set_yticks([])
    tank.set_title("the tank")

    fig.subplots_adjust(left=0.10, right=0.97, top=0.92, bottom=0.10, wspace=0.25)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name="inflow", default=inflow, min=0.0, max=max(inflow * 2, 1.0), step=0.5),
            ParamSpec(
                name="outflow", default=outflow, min=0.0, max=max(outflow * 2, 1.0), step=0.5
            ),
        ],
        meta={
            "kind": "word_problem",
            "template": "rate_tank",
            "time": time,
            "net_rate": net,
            "warnings": [],
        },
    )


__all__ = ["render", "solve"]
