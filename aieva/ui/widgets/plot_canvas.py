"""The abstraction over the two ways a Matplotlib figure can be shown.

On the desktop the figure is drawn by ``kivy_garden.matplotlib`` (a real
canvas). Some Android builds cannot use that backend, so the figure is
rendered to a **PNG texture** instead and shown in a normal image widget.

The application always uses :class:`PlotCanvas`; the backend is chosen
automatically, so the same code runs on the board and on the desktop.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image

LOGGER = logging.getLogger(__name__)

#: The name of the backend that is used.
BACKEND: str = "kivyagg"

#: The resolution of the PNG fallback.
PNG_DPI = 100

#: The size of the PNG fallback (in inches).
PNG_SIZE = (8.0, 5.0)


def kivyagg_available() -> bool:
    """``True`` when the Kivy Matplotlib backend can be used."""
    try:
        from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - the package is optional
        LOGGER.info("The Kivy Matplotlib backend is not available: %s", exc)
        return False
    return True


def select_backend() -> str:
    """Pick the backend - ``kivyagg`` or ``png``."""
    return "kivyagg" if kivyagg_available() else "png"


def figure_to_png(figure: Any, dpi: int = PNG_DPI) -> bytes:
    """Render a figure into PNG bytes."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=dpi)
    return buffer.getvalue()


def png_to_texture(data: bytes) -> Any:
    """Turn PNG bytes into a Kivy texture."""
    from kivy.graphics.texture import Texture
    from PIL import Image as PILImage

    picture = PILImage.open(io.BytesIO(data)).convert("RGBA")
    texture = Texture.create(size=picture.size)
    texture.blit_buffer(picture.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
    texture.flip_vertical()
    return texture


def figure_cache_key(figure: Any) -> str:
    """A key that describes the content of a figure (for the render cache)."""
    from aieva.core.cache import render_key

    parts: list[str] = []
    try:
        for axes in figure.get_axes():
            for line in axes.get_lines():
                parts.append(str(list(line.get_xdata())[:32]))
                parts.append(str(list(line.get_ydata())[:32]))
            for collection in axes.collections:
                offsets = collection.get_offsets()
                parts.append(str(offsets[:32].tolist()) if len(offsets) else "")
    except Exception as exc:  # noqa: BLE001 - a broken figure
        LOGGER.info("The figure could not be described: %s", exc)
    if not parts:
        parts.append(str(id(figure)))
    return render_key(*parts)


def figure_to_texture(figure: Any, dpi: int = PNG_DPI, use_cache: bool = True) -> Any:
    """Render a figure into a Kivy texture (the PNG fallback).

    The picture is cached on disk, so that the same figure is not rendered
    twice (the sliders of a board redraw the picture often).
    """
    from aieva.core.cache import cached_render

    try:
        if use_cache:
            data = cached_render(figure_cache_key(figure), lambda: figure_to_png(figure, dpi=dpi))
        else:
            data = figure_to_png(figure, dpi=dpi)
        return png_to_texture(data)
    except Exception as exc:  # noqa: BLE001 - a broken figure
        LOGGER.info("The figure could not be rendered: %s", exc)
        return None


class PlotCanvas(BoxLayout):
    """Shows a Matplotlib figure.

    ``PlotCanvas`` behaves like the Kivy Agg canvas (``draw_idle()``,
    ``figure``), but it falls back to a PNG texture when the Agg backend is
    not available.
    """

    def __init__(self, figure: Any = None, backend: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.backend = backend or select_backend()
        self.figure = None
        self.canvas_widget: Any = None
        self._image: Image | None = None
        if figure is not None:
            self.set_figure(figure)

    # ------------------------------------------------------------------ api
    def set_figure(self, figure: Any) -> None:
        """Show another figure."""
        self.figure = figure
        self.clear_widgets()
        self.canvas_widget = None
        self._image = None
        if figure is None:
            return
        if self.backend == "kivyagg":
            from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg

            self.canvas_widget = FigureCanvasKivyAgg(figure)
            self.add_widget(self.canvas_widget)
            return
        self._image = Image(allow_stretch=True, keep_ratio=True)
        self.add_widget(self._image)
        self.draw_idle()

    def draw_idle(self) -> None:
        """Redraw the figure."""
        if self.figure is None:
            return
        if self.canvas_widget is not None:
            self.canvas_widget.draw_idle()
            return
        if self._image is None:
            return
        texture = figure_to_texture(self.figure)
        if texture is not None:
            self._image.texture = texture


__all__ = [
    "BACKEND",
    "PNG_DPI",
    "PNG_SIZE",
    "PlotCanvas",
    "figure_cache_key",
    "figure_to_png",
    "figure_to_texture",
    "kivyagg_available",
    "png_to_texture",
    "select_backend",
]
