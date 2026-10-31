"""Make the preview screenshots of the Aieva app.

The script starts the real application (under Xvfb), walks through every
screen, lets the background workers finish and grabs a picture of the window.

    python3 scripts/make_preview.py          # -> preview/*.png

It is a development helper - it is not part of the application.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("DISPLAY", ":99")

from kivy.clock import Clock  # noqa: E402

from aieva.ui.app import AievaApp  # noqa: E402

PREVIEW = ROOT / "preview"


def grab(name: str) -> None:
    """Take a picture of the (virtual) screen."""
    PREVIEW.mkdir(parents=True, exist_ok=True)
    target = PREVIEW / f"{name}.png"
    try:
        subprocess.run(
            ["import", "-window", "root", str(target)],
            check=True,
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":99")},
        )
        print(f"  saved {target.name}")
    except Exception as exc:  # noqa: BLE001 - the preview is a nicety
        print(f"  could not take the screenshot {name}: {exc}")


def main() -> int:
    app = AievaApp()

    def prepare() -> None:
        print("building the preview...")

    def home() -> None:
        app.manager.current = "home"

    def home_shot() -> None:
        grab("01-home")

    def whiteboard() -> None:
        from aieva.ui.widgets.whiteboard import Stroke

        app.manager.current = "whiteboard"
        board = app.whiteboard_screen.whiteboard
        board.strokes = []
        # a parabola, drawn as a white stroke on the dark board
        points: list[float] = []
        for index in range(41):
            x = 200 + index * 20
            y = 560 - (index - 20) ** 2 * 0.9
            points.extend([x, y])
        board.strokes.append(Stroke(points=points, color=(1, 1, 1, 1), width=4))
        board.strokes.append(
            Stroke(points=[200, 560, 1000, 560], color=(0.35, 0.85, 0.6, 1), width=2)
        )
        board.strokes.append(
            Stroke(points=[600, 120, 600, 600], color=(0.35, 0.85, 0.6, 1), width=2)
        )
        board._redraw_all()

    def whiteboard_shot() -> None:
        grab("02-whiteboard")

    def calculus() -> None:
        app.manager.current = "calculus"
        screen = app.calculus_screen
        screen.set_mode("integral")
        screen.function_input.text = "sin(x)"
        screen.sliders["a"].value = 0.0
        screen.sliders["b"].value = 3.14159
        screen.update_plot()

    def calculus_shot() -> None:
        grab("03-calculus-integral")

    def linalg() -> None:
        app.manager.current = "linalg"
        screen = app.linalg_screen
        screen.set_mode("matrix")
        screen.matrix_cells[0][0].text = "2"
        screen.matrix_cells[0][1].text = "-1"
        screen.matrix_cells[1][0].text = "1"
        screen.matrix_cells[1][1].text = "0"
        screen.update_plot()

    def linalg_shot() -> None:
        grab("04-linalg-matrix")

    def plot3d() -> None:
        app.manager.current = "plot3d"
        screen = app.plot3d_screen
        screen.expression_input.text = "z = x**2 + y**2"
        screen.quality_spinner.text = "low"
        screen.update_plot()

    def plot3d_shot() -> None:
        grab("05-3d-surface")

    def solver() -> None:
        app.manager.current = "solver"
        screen = app.solver_screen
        screen.solve_text("x**2 + 3*x - 2 = 0")

    def solver_shot() -> None:
        grab("06-solver-steps")

    def equation_sliders() -> None:
        """Demo A: type an equation and open the modal with the sliders."""
        app.manager.current = "home"
        app._on_request_plot("y = m*x + c", "text")

    def equation_sliders_shot() -> None:
        grab("07-equation-sliders")

    def close_the_modal() -> None:
        """The modal stays on top - close it before the next screen."""
        modal = getattr(app, "plot_modal", None)
        if modal is not None:
            modal.dismiss()

    def wordproblem() -> None:
        """Demo G: a word problem (the local model - the server is not running)."""
        app.manager.current = "wordproblem"
        screen = app.wordproblem_screen
        screen.problem_input.text = (
            "A ball is thrown with 20 m/s at 45 degrees. " "How high does it fly and how far?"
        )
        screen.analyse()

    def wordproblem_shot() -> None:
        grab("08-wordproblem")

    def documents() -> None:
        """Demo H: read a document and list the equations."""
        app.manager.current = "documents"
        screen = app.documents_screen
        fixture = ROOT / "tests" / "fixtures" / "docs" / "equations.docx"
        screen.chooser.selection = [str(fixture)]
        screen.read_document()

    def documents_shot() -> None:
        grab("09-documents")

    def settings() -> None:
        """The settings of the teacher."""
        app.manager.current = "settings"

    def settings_shot() -> None:
        grab("10-settings")

    steps = [
        (0.8, prepare),
        (1.2, home),
        (1.5, home_shot),
        (1.2, whiteboard),
        (1.5, whiteboard_shot),
        (1.5, calculus),
        (4.0, calculus_shot),
        (1.2, linalg),
        (4.0, linalg_shot),
        (1.2, plot3d),
        (5.0, plot3d_shot),
        (1.2, solver),
        (4.0, solver_shot),
        (1.2, equation_sliders),
        (5.0, equation_sliders_shot),
        (1.0, close_the_modal),
        (1.2, wordproblem),
        (5.0, wordproblem_shot),
        (1.2, documents),
        (5.0, documents_shot),
        (1.2, settings),
        (2.0, settings_shot),
        (0.5, lambda: app.stop()),
    ]

    state = {"index": 0}

    def run_next(_dt: float) -> None:
        index = state["index"]
        if index >= len(steps):
            app.stop()
            return
        state["index"] = index + 1
        delay, function = steps[index]
        try:
            function()
        except Exception as exc:  # noqa: BLE001 - the preview must not crash
            print(f"  step {index} failed: {exc}")
        Clock.schedule_once(run_next, delay)

    Clock.schedule_once(run_next, 1.5)
    app.run()
    print("preview done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
