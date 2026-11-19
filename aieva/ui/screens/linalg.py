"""The linear algebra screen: vectors, matrices, eigen values, systems, complex.

The maths lives in :mod:`aieva.plugins.math.linalg` and
:mod:`aieva.plugins.math.complexnum`; this screen only builds the controls.
"""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner

from aieva.core.errors import AievaError
from aieva.plugins.math import complexnum, linalg
from aieva.ui import theme
from aieva.ui.widgets.controls import labelled_input, matrix_grid, mode_button, slider_row
from aieva.ui.widgets.header import ScreenHeader
from aieva.ui.widgets.toast import show_toast
from aieva.ui.workers import run_in_background

#: The available modes.
MODES: tuple[str, ...] = ("vectors", "matrix", "eigen", "system", "complex")


class LinearAlgebraScreen(Screen):
    """Controls and plot for the linear algebra visualisations."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "linalg"
        self.mode = "vectors"
        self._matrix_size = 2
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.add_widget(
            ScreenHeader("Linear algebra", "Matrices, vectors, eigen values and complex numbers")
        )

        modes = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        for mode in MODES:
            button = mode_button(mode.title())
            button.bind(on_release=lambda _b, name=mode: self.set_mode(name))
            modes.add_widget(button)
        root.add_widget(modes)

        self.controls = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(4 * theme.SLIDER_HEIGHT_DP),
            spacing=dp(4),
        )
        root.add_widget(self.controls)

        self.plot_area = BoxLayout(orientation="vertical")
        root.add_widget(self.plot_area)

        self.info_label = Label(
            text="",
            size_hint_y=None,
            height=dp(56),
            font_size=theme.sp_size(14),
            color=theme.TEXT_MUTED,
            halign="left",
            valign="middle",
        )
        self.info_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        root.add_widget(self.info_label)

        self.add_widget(root)
        self._rebuild_controls()

    # -------------------------------------------------------------- controls
    def _rebuild_controls(self) -> None:
        self.controls.clear_widgets()
        self.sliders: dict[str, Any] = {}

        if self.mode == "vectors":
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(theme.INPUT_HEIGHT_DP),
                spacing=dp(theme.GAP_DP),
            )
            self.vector_input = labelled_input("a=(1,2), b=(3,1)", "a=(1,2), b=(3,1)")
            row.add_widget(self.vector_input)
            self.vector_operation = Spinner(
                text="add",
                values=["add", "subtract", "scale", "dot", "cross"],
                size_hint_x=None,
                width=dp(170),
                height=dp(44),
                background_normal="",
                background_color=theme.SURFACE_ALT,
                color=theme.TEXT,
            )
            row.add_widget(self.vector_operation)
            self.controls.add_widget(row)
            self._add_slider("scale", "scalar", -5.0, 5.0, 2.0)
        elif self.mode in ("matrix", "eigen"):
            size_row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(theme.INPUT_HEIGHT_DP),
                spacing=dp(theme.GAP_DP),
            )
            size_label = Label(
                text="matrix size",
                color=theme.TEXT,
                font_size=theme.sp_size(15),
                size_hint_x=None,
                width=dp(140),
            )
            self.size_spinner = Spinner(
                text=f"{self._matrix_size}x{self._matrix_size}",
                values=["2x2", "3x3"],
                size_hint_x=None,
                width=dp(140),
                height=dp(44),
                background_normal="",
                background_color=theme.SURFACE_ALT,
                color=theme.TEXT,
            )
            self.size_spinner.bind(text=self._on_size_changed)
            size_row.add_widget(size_label)
            size_row.add_widget(self.size_spinner)
            self.controls.add_widget(size_row)

            grid, cells = matrix_grid(self.matrix_size())
            self.matrix_cells = cells
            self.controls.add_widget(grid)

            if self.mode == "matrix":
                self._add_slider("rotation", "rotation (deg)", -180.0, 180.0, 0.0, step=1.0)
                self._add_slider("shear", "shear", -2.0, 2.0, 0.0, step=0.05)
        elif self.mode == "system":
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(theme.INPUT_HEIGHT_DP),
                spacing=dp(theme.GAP_DP),
            )
            self.system_input = labelled_input("2x+y=5; x-y=1", "2x+y=5; x-y=1")
            row.add_widget(self.system_input)
            self.controls.add_widget(row)
        elif self.mode == "complex":
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(theme.INPUT_HEIGHT_DP),
                spacing=dp(theme.GAP_DP),
            )
            self.complex_input = labelled_input("3 + 4i", "z = 3 + 4i")
            self.complex_second = labelled_input("1 + i", "w = 1 + i")
            row.add_widget(self.complex_input)
            row.add_widget(self.complex_second)
            self.controls.add_widget(row)

            operation_row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(theme.SLIDER_HEIGHT_DP),
                spacing=dp(theme.GAP_DP),
            )
            operation_row.add_widget(
                Label(text="operation", color=theme.TEXT, font_size=theme.sp_size(15))
            )
            self.complex_operation = Spinner(
                text="none",
                values=["none", "add", "multiply", "multiply_i", "conjugate", "power", "roots"],
                size_hint_x=None,
                width=dp(190),
                height=dp(44),
                background_normal="",
                background_color=theme.SURFACE_ALT,
                color=theme.TEXT,
            )
            operation_row.add_widget(self.complex_operation)
            self.controls.add_widget(operation_row)
            self._add_slider("n", "exponent / roots", 1.0, 12.0, 3.0, step=1.0)

    def _add_slider(
        self,
        name: str,
        label: str,
        minimum: float,
        maximum: float,
        default: float,
        step: float | None = None,
    ) -> None:
        row, slider, _value_label = slider_row(label, minimum, maximum, default, step)
        self.controls.add_widget(row)
        self.sliders[name] = slider

    def _on_size_changed(self, _widget: Any, value: str) -> None:
        size = 3 if value == "3x3" else 2
        if size == self._matrix_size:
            return
        self._matrix_size = size
        self._rebuild_controls()

    def matrix_size(self) -> int:
        return self._matrix_size

    def slider_value(self, name: str, default: float = 0.0) -> float:
        slider = self.sliders.get(name)
        return float(slider.value) if slider is not None else default

    # ----------------------------------------------------------------- API
    def set_mode(self, mode: str) -> None:
        """Switch the linear algebra mode."""
        if mode not in MODES:
            return
        self.mode = mode
        self._rebuild_controls()
        self.info_label.text = ""

    def _read_matrix(self) -> list[list[float]]:
        size = self.matrix_size()
        values: list[list[float]] = []
        for row_index in range(size):
            row_values = []
            for column_index in range(size):
                cell = self.matrix_cells[row_index][column_index]
                try:
                    row_values.append(float(cell.text.strip() or 0.0))
                except ValueError as exc:
                    raise ValueError(f"'{cell.text}' is not a number") from exc
            values.append(row_values)
        return values

    def update_plot(self) -> None:
        """(Re)compute the visualisation for the current mode."""
        try:
            work = self._build_worker()
        except ValueError as exc:
            show_toast(str(exc))
            return
        if work is None:
            return

        def on_done(result: Any) -> None:
            self._show(result)

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, AievaError):
                show_toast(str(exc))
            else:
                show_toast(f"Could not build the plot: {exc}")

        run_in_background(work, on_done, on_error, name="aieva-linalg")

    def _build_worker(self):
        if self.mode == "vectors":
            operation = self.vector_operation.text
            scale = self.slider_value("scale", 2.0)
            text = self.vector_input.text
            return lambda: linalg.vector_view(text, operation=operation, scale=scale)
        if self.mode in ("matrix", "eigen"):
            matrix = self._read_matrix()
            if self.mode == "eigen":
                return lambda: linalg.eigen_view(matrix)
            rotation = self.slider_value("rotation", 0.0)
            shear = self.slider_value("shear", 0.0)
            return lambda: linalg.matrix_view(matrix, rotation=rotation, shear=shear)
        if self.mode == "system":
            text = self.system_input.text
            return lambda: linalg.system_view(text)
        if self.mode == "complex":
            z = self.complex_input.text
            w = self.complex_second.text
            operation = self.complex_operation.text
            n = int(self.slider_value("n", 3.0))
            return lambda: complexnum.argand_view(z, operation=operation, w=w, n=n)
        return None

    def _canvas(self, figure: Any) -> Any:
        """A live canvas - or a picture when the backend is not there.

        The Kivy Matplotlib backend needs setuptools on Python 3.12 and
        newer; without it the figure is shown as an image.
        """
        from aieva.ui.widgets.plot_canvas import figure_to_png, png_to_texture

        try:
            from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg

            return FigureCanvasKivyAgg(figure)
        except Exception:  # noqa: BLE001 - the backend is optional
            from kivy.uix.image import Image

            picture = Image(size_hint=(1, 1))
            picture.texture = png_to_texture(figure_to_png(figure))
            return picture

    def _show(self, result: Any) -> None:
        """Show a computed visualisation."""
        self.plot_area.clear_widgets()
        if result.figure is not None:
            self.plot_area.add_widget(self._canvas(result.figure))

        meta = result.meta or {}
        lines: list[str] = []
        if meta.get("kind") == "matrix":
            lines.append(f"det(M) = {meta.get('determinant'):.6g}   (area scale)")
        elif meta.get("kind") == "eigen":
            lines.append("eigen values: " + ", ".join(meta.get("eigenvalues", [])))
            if meta.get("exact_eigenvalues"):
                lines.append("exact: " + ", ".join(meta["exact_eigenvalues"]))
        elif meta.get("kind") == "system":
            lines.append(meta.get("explanation", ""))
            if meta.get("point"):
                point = meta["point"]
                lines.append("solution: (" + ", ".join(f"{value:.6g}" for value in point) + ")")
        elif meta.get("kind") in ("complex", "vectors"):
            lines.append(meta.get("annotation", ""))
        for warning in meta.get("warnings", []) or []:
            lines.append(f"! {warning}")
        self.info_label.text = "\n".join(lines)


__all__ = ["MODES", "LinearAlgebraScreen"]
