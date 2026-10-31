"""The touch drawing canvas (whiteboard).

The strokes are kept as data so that :meth:`Whiteboard.export_to_image` can
reproduce them with Pillow - this works headless (no OpenGL round trip) and is
therefore easy to unit test.

Palm rejection: touches whose contact area is bigger than
:attr:`Whiteboard.palm_threshold` are ignored. Not every platform reports the
contact size, so the check is defensive and can be switched off.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kivy.graphics import Color, Line
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.widget import Widget

from aieva.ui import theme


@dataclass
class Stroke:
    """One drawn line."""

    points: list[float] = field(default_factory=list)
    color: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    width: float = theme.DEFAULT_PEN_WIDTH

    def to_dict(self) -> dict[str, Any]:
        return {"points": list(self.points), "color": list(self.color), "width": self.width}


class Whiteboard(Widget):
    """A simple touch drawing surface."""

    pen_color: StringProperty = StringProperty("black")
    pen_width: NumericProperty = NumericProperty(theme.DEFAULT_PEN_WIDTH)
    eraser: BooleanProperty = BooleanProperty(False)
    #: Ignore large contacts (a palm resting on the board).
    palm_rejection: BooleanProperty = BooleanProperty(True)
    #: A contact bigger than this many pixels is treated as a palm.
    palm_threshold: NumericProperty = NumericProperty(60.0)

    strokes: ListProperty = ListProperty([])
    _active: ObjectProperty = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_line: Line | None = None
        self._current_color: Color | None = None

    # ----------------------------------------------------------------- touch
    def on_touch_down(self, touch: Any) -> bool:
        if not self.collide_point(*touch.pos):
            return False
        if self._is_palm(touch):
            return True
        touch.ud["whiteboard"] = self
        stroke = Stroke(
            points=[touch.x, touch.y],
            color=self._effective_color(),
            width=self._effective_width(),
        )
        self.strokes.append(stroke)
        self._active = touch
        self._draw_stroke(stroke)
        return True

    def on_touch_move(self, touch: Any) -> bool:
        if self._active is not touch:
            return False
        stroke = self.strokes[-1] if self.strokes else None
        if stroke is None:
            return False
        stroke.points.extend([touch.x, touch.y])
        self._refresh_stroke(stroke)
        return True

    def on_touch_up(self, touch: Any) -> bool:
        if self._active is not touch:
            return False
        self._active = None
        return True

    # ------------------------------------------------------------- commands
    def clear(self) -> None:
        """Remove every stroke."""
        self.strokes = []
        self.canvas.clear()

    def undo(self) -> None:
        """Remove the last stroke."""
        if not self.strokes:
            return
        self.strokes = list(self.strokes[:-1])
        self._redraw_all()

    def set_pen_color(self, name: str) -> None:
        """Select a pen colour by name (``black``, ``red``, ...)."""
        self.pen_color = name

    def set_eraser(self, enabled: bool) -> None:
        """Switch the eraser on or off."""
        self.eraser = enabled

    # -------------------------------------------------------------- export
    def export_to_image(self):
        """Return the whiteboard content as a :class:`PIL.Image.Image`."""
        from PIL import Image, ImageDraw

        width = max(int(self.width), 1)
        height = max(int(self.height), 1)
        image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        for stroke in self.strokes:
            points = list(stroke.points)
            if len(points) < 4:
                continue
            pairs = list(zip(points[0::2], points[1::2], strict=False))
            colour = tuple(int(component * 255) for component in stroke.color[:3]) + (255,)
            draw.line(pairs, fill=colour, width=max(int(stroke.width), 1), joint="curve")
        return image

    # ------------------------------------------------------------ internals
    def _effective_color(self) -> tuple[float, float, float, float]:
        if self.eraser:
            return (1.0, 1.0, 1.0, 1.0)
        return theme.PEN_PALETTE.get(self.pen_color)

    def _effective_width(self) -> float:
        if self.eraser:
            return max(self.pen_width * 3, 8.0)
        return self.pen_width

    def _is_palm(self, touch: Any) -> bool:
        """Heuristic palm rejection based on the contact size, when available."""
        if not self.palm_rejection:
            return False
        flag = getattr(touch, "palm", None)
        if flag is not None:
            return bool(flag)
        radius = getattr(touch, "major_radius", None)
        if radius is None:
            radius = getattr(touch, "radius", None)
        if radius is None:
            return False
        try:
            return float(radius) > float(self.palm_threshold)
        except (TypeError, ValueError):
            return False

    def _draw_stroke(self, stroke: Stroke) -> None:
        with self.canvas:
            self._current_color = Color(*stroke.color)
            self._current_line = Line(
                points=stroke.points, width=stroke.width, cap="round", joint="round"
            )

    def _refresh_stroke(self, stroke: Stroke) -> None:
        if self._current_line is not None:
            self._current_line.points = stroke.points

    def _redraw_all(self) -> None:
        self.canvas.clear()
        for stroke in self.strokes:
            self._draw_stroke(stroke)


__all__ = ["Stroke", "Whiteboard"]
