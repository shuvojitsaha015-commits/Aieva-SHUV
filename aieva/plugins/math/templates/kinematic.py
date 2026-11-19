"""The kinematic template: a projectile and a uniform motion.

* a **projectile**: the trajectory ``x = v0 cos(theta) t``,
  ``y = v0 sin(theta) t - g t^2 / 2`` with the velocity vectors, the apex and
  the range marked;
* **uniform motion**: the position against the time of two objects with the
  meeting point marked.
"""

from __future__ import annotations

import math
from typing import Any

import matplotlib

matplotlib.use("Agg", force=False)

import numpy as np  # noqa: E402

from aieva.core.errors import SolveError  # noqa: E402
from aieva.core.models import ParamSpec, Step, VisualizationResult  # noqa: E402
from aieva.core.plotting import new_subplots  # noqa: E402

#: The gravity that is used when the model does not give one.
DEFAULT_GRAVITY = 9.8


def _degrees(value: float) -> float:
    """The launch angle in radians (the model uses degrees)."""
    return math.radians(value)


def solve(problem: Any) -> Any:
    """Solve the projectile or the uniform motion."""
    if problem.problem_type == "uniform_motion":
        return _solve_uniform_motion(problem)
    return _solve_projectile(problem)


# ------------------------------------------------------------------ projectile
def _solve_projectile(problem: Any) -> Any:
    from aieva.plugins.math.wordproblems import WordProblemSolution

    speed = problem.number("v0")
    angle = problem.number("theta")
    gravity = problem.value("g", DEFAULT_GRAVITY)
    if speed <= 0:
        raise SolveError("The initial speed has to be positive")
    if not 0 < angle < 90:
        raise SolveError("The launch angle has to be between 0 and 90 degrees")

    radians = _degrees(angle)
    flight_time = 2.0 * speed * math.sin(radians) / gravity
    max_height = (speed * math.sin(radians)) ** 2 / (2.0 * gravity)
    travel = speed * math.cos(radians) * flight_time

    steps = [
        Step(
            title="Split the launch speed",
            explanation=(
                f"The horizontal speed is v0*cos(theta) = {speed * math.cos(radians):.4g} m/s "
                f"and the vertical speed is v0*sin(theta) = {speed * math.sin(radians):.4g} m/s."
            ),
            latex=(
                f"v_x = v_0\\cos\\theta = {speed * math.cos(radians):.4g},\\quad "
                f"v_y = v_0\\sin\\theta = {speed * math.sin(radians):.4g}"
            ),
        ),
        Step(
            title="The time of the flight",
            explanation="The ball is back on the ground when y(t) = 0 (the second root).",
            latex=f"t = \\frac{{2 v_0 \\sin\\theta}}{{g}} = {flight_time:.4g}\\ \\text{{s}}",
        ),
        Step(
            title="The highest point",
            explanation="The vertical speed is zero at the apex.",
            latex=f"h = \\frac{{(v_0 \\sin\\theta)^2}}{{2g}} = {max_height:.4g}\\ \\text{{m}}",
        ),
        Step(
            title="How far it flies",
            explanation="The horizontal distance at the time of the flight.",
            latex=f"R = \\frac{{v_0^2 \\sin 2\\theta}}{{g}} = {travel:.4g}\\ \\text{{m}}",
        ),
    ]
    return WordProblemSolution(
        values={
            "max_height": max_height,
            "range": travel,
            "flight_time": flight_time,
            "apex_time": flight_time / 2.0,
        },
        latex={
            "max_height": f"h = {max_height:.4g}\\,\\mathrm{{m}}",
            "range": f"R = {travel:.4g}\\,\\mathrm{{m}}",
            "flight_time": f"t = {flight_time:.4g}\\,\\mathrm{{s}}",
        },
        steps=steps,
    )


# -------------------------------------------------------------- uniform motion
def _solve_uniform_motion(problem: Any) -> Any:
    from aieva.plugins.math.wordproblems import WordProblemSolution

    speed_one = problem.number("v1")
    speed_two = problem.number("v2")
    start_one = problem.value("x1", 0.0)
    start_two = problem.value("x2", 0.0)

    difference = speed_one - speed_two
    if abs(difference) < 1e-12:
        raise SolveError("The two objects have the same speed - they never meet")
    meeting_time = (start_two - start_one) / difference
    if meeting_time < 0:
        raise SolveError("The objects meet in the past - check the start positions")
    meeting_point = start_one + speed_one * meeting_time

    steps = [
        Step(
            title="The two positions",
            explanation="Every object moves with a constant speed.",
            latex=f"x_1(t) = {start_one:g} + {speed_one:g}t,\\quad x_2(t) = {start_two:g} + {speed_two:g}t",
        ),
        Step(
            title="They meet",
            explanation="The positions are equal at that moment.",
            latex=f"t = \\frac{{{start_two:g} - {start_one:g}}}{{{speed_one:g} - {speed_two:g}}}"
            f" = {meeting_time:.4g}\\,\\mathrm{{s}}",
        ),
        Step(
            title="Where they meet",
            explanation="The position at that moment.",
            latex=f"x = {meeting_point:.4g}\\,\\mathrm{{m}}",
        ),
    ]
    return WordProblemSolution(
        values={"meeting_time": meeting_time, "meeting_point": meeting_point},
        latex={
            "meeting_time": f"t = {meeting_time:.4g}\\,\\mathrm{{s}}",
            "meeting_point": f"x = {meeting_point:.4g}\\,\\mathrm{{m}}",
        },
        steps=steps,
    )


# ------------------------------------------------------------------ rendering
def render(problem: Any, solution: Any) -> VisualizationResult:
    """Draw the trajectory or the position against the time."""
    if problem.problem_type == "uniform_motion":
        return _render_uniform_motion(problem, solution)
    return _render_projectile(problem, solution)


def _render_projectile(problem: Any, solution: Any) -> VisualizationResult:
    speed = problem.number("v0")
    angle = problem.number("theta")
    gravity = problem.value("g", DEFAULT_GRAVITY)
    radians = _degrees(angle)

    flight_time = solution.values["flight_time"]
    travel = solution.values["range"]
    max_height = solution.values["max_height"]

    times = np.linspace(0.0, flight_time, 200)
    xs = speed * math.cos(radians) * times
    ys = speed * math.sin(radians) * times - 0.5 * gravity * times**2

    fig, ax = new_subplots(figsize=(7.5, 5.5), dpi=100)
    ax.plot(xs, ys, color="#1f77b4", linewidth=2.5, label="trajectory")
    ax.axhline(0, color="#444444", linewidth=1.2)

    # the velocity vectors at three moments (scaled so that they fit)
    reference = max(speed, 1e-9)
    vector_scale = 0.22 * travel / reference
    moments = (
        (0.0, "t = 0", 0.02 * travel, 0.16 * max_height, "left"),
        (0.5, "t = T/2", 0.02 * travel, 0.08 * max_height, "left"),
        (1.0, "t = T", -0.02 * travel, 0.16 * max_height, "right"),
    )
    for fraction, label, offset_x, offset_y, alignment in moments:
        moment = flight_time * fraction
        x = speed * math.cos(radians) * moment
        y = speed * math.sin(radians) * moment - 0.5 * gravity * moment**2
        vx = speed * math.cos(radians)
        vy = speed * math.sin(radians) - gravity * moment
        ax.quiver(
            x,
            y,
            vx * vector_scale,
            vy * vector_scale,
            angles="xy",
            scale_units="xy",
            scale=1,
            color="#d62728",
            width=0.005,
            zorder=3,
        )
        ax.plot([x], [y], "o", color="#d62728", markersize=5, zorder=4)
        ax.text(
            x + offset_x,
            y + offset_y,
            label,
            color="#d62728",
            fontsize=10,
            ha=alignment,
        )

    ax.plot([travel / 2], [max_height], "*", color="#2ca02c", markersize=16, zorder=5)
    ax.text(
        0.03 * travel,
        1.08 * max_height,
        f"apex {max_height:.3g} m",
        color="#2ca02c",
        fontsize=11,
        ha="left",
    )
    ax.plot([travel], [0], "o", color="#ff7f0e", markersize=7, zorder=5)
    ax.annotate(
        f"range {travel:.3g} m",
        xy=(travel, 0),
        xytext=(travel * 0.68, max_height * 0.12),
        color="#ff7f0e",
        fontsize=11,
        arrowprops={"arrowstyle": "->", "color": "#ff7f0e"},
    )

    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"projectile: v0 = {speed:g} m/s, theta = {angle:g} deg")
    ax.set_xlim(-0.06 * travel, 1.10 * travel)
    ax.set_ylim(-0.08 * max_height, 1.16 * max_height)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)
    fig.subplots_adjust(left=0.12, right=0.96, top=0.92, bottom=0.10)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(
                name="v0", default=speed, min=max(speed * 0.1, 1.0), max=speed * 2.0, step=0.5
            ),
            ParamSpec(name="theta", default=angle, min=1.0, max=89.0, step=1.0),
        ],
        meta={
            "kind": "word_problem",
            "template": "kinematic_projectile",
            "flight_time": flight_time,
            "max_height": max_height,
            "range": travel,
            "warnings": [],
        },
    )


def _render_uniform_motion(problem: Any, solution: Any) -> VisualizationResult:
    speed_one = problem.number("v1")
    speed_two = problem.number("v2")
    start_one = problem.value("x1", 0.0)
    start_two = problem.value("x2", 0.0)
    meeting_time = solution.values["meeting_time"]

    times = np.linspace(0.0, max(meeting_time * 1.35, 1.0), 200)
    fig, ax = new_subplots(figsize=(7.5, 5.5), dpi=100)
    ax.plot(times, start_one + speed_one * times, color="#1f77b4", linewidth=2.5, label="object 1")
    ax.plot(times, start_two + speed_two * times, color="#ff7f0e", linewidth=2.5, label="object 2")
    meeting_point = solution.values["meeting_point"]
    ax.plot([meeting_time], [meeting_point], "o", color="#2ca02c", markersize=9, zorder=5)
    highest = max(start_one + speed_one * times.max(), start_two + speed_two * times.max())
    ax.annotate(
        f"they meet at t = {meeting_time:.3g} s\nx = {meeting_point:.3g} m",
        xy=(meeting_time, meeting_point),
        xytext=(times.max() * 0.05, highest * 0.25),
        color="#2ca02c",
        fontsize=11,
        arrowprops={"arrowstyle": "->", "color": "#2ca02c"},
    )
    ax.set_xlabel("t (s)")
    ax.set_ylabel("x (m)")
    ax.set_title("uniform motion")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    fig.subplots_adjust(left=0.12, right=0.96, top=0.92, bottom=0.10)

    return VisualizationResult(
        figure=fig,
        parameters=[
            ParamSpec(name="v1", default=speed_one, min=0.0, max=max(speed_one * 2, 5.0), step=0.1),
            ParamSpec(name="v2", default=speed_two, min=0.0, max=max(speed_two * 2, 5.0), step=0.1),
        ],
        meta={
            "kind": "word_problem",
            "template": "uniform_motion",
            "meeting_time": meeting_time,
            "meeting_point": meeting_point,
            "warnings": [],
        },
    )


def animation_points(problem: Any, solution: Any) -> dict[str, Any]:
    """The data that the Kivy animation of the ball needs."""
    speed = problem.number("v0")
    angle = problem.number("theta")
    gravity = problem.value("g", DEFAULT_GRAVITY)
    radians = _degrees(angle)
    flight_time = solution.values["flight_time"]
    times = np.linspace(0.0, flight_time, 120)
    return {
        "times": times,
        "x": speed * math.cos(radians) * times,
        "y": speed * math.sin(radians) * times - 0.5 * gravity * times**2,
        "flight_time": flight_time,
    }


__all__ = ["DEFAULT_GRAVITY", "animation_points", "render", "solve"]
