"""The steps panel: a scrollable list of the solution steps.

Every step shows a title, a plain language explanation and the formula - the
formula is rendered with Matplotlib's mathtext into a texture (with a plain
text fallback when mathtext cannot read the LaTeX).
"""

from __future__ import annotations

import logging
from typing import Any

from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from aieva.core.models import Step
from aieva.ui import theme

LOGGER = logging.getLogger(__name__)

#: The width of a rendered formula (pixels).
FORMULA_WIDTH = 700

#: The height of a rendered formula (pixels).
FORMULA_HEIGHT = 90


def render_math_texture(
    latex: str, width: int = FORMULA_WIDTH, height: int = FORMULA_HEIGHT
) -> Any:
    """Render a formula into a Kivy texture (``None`` when mathtext fails)."""
    if not latex or not latex.strip():
        return None
    try:
        import matplotlib

        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt

        figure = plt.figure(figsize=(width / 100.0, height / 100.0), dpi=100)
        figure.patch.set_alpha(0.0)
        figure.text(
            0.5,
            0.5,
            f"${latex}$",
            ha="center",
            va="center",
            fontsize=22,
            color="#f0f2f7",
        )
        figure.canvas.draw()
        canvas = figure.canvas
        buffer = canvas.buffer_rgba()
        texture_width, texture_height = canvas.get_width_height()
        plt.close(figure)
        texture = Texture.create(size=(texture_width, texture_height))
        texture.blit_buffer(bytes(buffer), colorfmt="rgba", bufferfmt="ubyte")
        texture.flip_vertical()
        return texture
    except Exception as exc:  # noqa: BLE001 - mathtext is picky
        LOGGER.info("The formula could not be rendered: %s", exc)
        return None


class StepsPanel(ScrollView):
    """Shows the steps of a solution."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("do_scroll_x", False)
        kwargs.setdefault("bar_width", dp(8))
        super().__init__(**kwargs)
        self.container = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        self.container.bind(minimum_height=self.container.setter("height"))
        self.add_widget(self.container)
        self._textures: dict[str, Any] = {}

    # ------------------------------------------------------------------ api
    def clear(self) -> None:
        """Remove every step."""
        self.container.clear_widgets()

    def show_steps(self, steps: list[Step], title: str = "") -> None:
        """Show a list of :class:`~aieva.core.models.Step`."""
        self.clear()
        if title:
            self.container.add_widget(self._heading(title))
        if not steps:
            self.container.add_widget(
                self._label("No steps - the problem could not be solved.", theme.TEXT_MUTED)
            )
            return
        for index, step in enumerate(steps, start=1):
            self.container.add_widget(self._step_widget(index, step))

    # ------------------------------------------------------------ internals
    def _heading(self, text: str) -> Label:
        label = Label(
            text=text,
            size_hint_y=None,
            height=dp(40),
            font_size=theme.sp_size(19),
            color=theme.PRIMARY,
            halign="left",
            valign="middle",
            bold=True,
        )
        label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        return label

    def _label(self, text: str, color: tuple[float, float, float, float]) -> Label:
        label = Label(
            text=text,
            size_hint_y=None,
            height=dp(34),
            font_size=theme.sp_size(15),
            color=color,
            halign="left",
            valign="top",
        )
        label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        return label

    def _step_widget(self, index: int, step: Step) -> BoxLayout:
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(90), spacing=dp(4))
        title = Label(
            text=f"{index}. {step.title}",
            size_hint_y=None,
            height=dp(30),
            font_size=theme.sp_size(16),
            color=theme.TEXT,
            halign="left",
            valign="middle",
            bold=True,
        )
        title.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        box.add_widget(title)

        if step.explanation:
            explanation = Label(
                text=step.explanation,
                size_hint_y=None,
                height=dp(30),
                font_size=theme.sp_size(14),
                color=theme.TEXT_MUTED,
                halign="left",
                valign="top",
            )
            explanation.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            box.add_widget(explanation)

        if step.latex:
            texture = self._texture_for(step.latex)
            if texture is not None:
                image = Image(
                    texture=texture,
                    size_hint_y=None,
                    height=dp(70),
                    allow_stretch=True,
                    keep_ratio=True,
                )
                box.add_widget(image)
                box.height = dp(140)
            else:
                box.add_widget(self._label(step.latex, theme.ACCENT))
        return box

    def _texture_for(self, latex: str) -> Any:
        if latex not in self._textures:
            self._textures[latex] = render_math_texture(latex)
        return self._textures[latex]


__all__ = ["FORMULA_HEIGHT", "FORMULA_WIDTH", "StepsPanel", "render_math_texture"]
