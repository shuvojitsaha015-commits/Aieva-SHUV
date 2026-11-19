"""The 3D plot view: touch rotation, pinch zoom and the button fallback.

The plan asks for both: a one finger drag rotates the camera, a two finger
pinch zooms, **and** on screen buttons that always work (the fallback for
boards where a multi touch gesture is unreliable).
"""

from __future__ import annotations

import math
from typing import Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button

from aieva.ui import theme

# The Matplotlib backend of Kivy is optional: on a computer without
# setuptools (Python 3.12 and newer do not bring it any more) the import of
# "kivy_garden.matplotlib" fails with "No module named 'distutils'". The
# application must still start then - the 3D plot falls back to a picture.
try:
    from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
except Exception as _exc:  # noqa: BLE001 - the backend is optional
    LOGGER_MESSAGE = f"The Kivy Matplotlib backend is not available: {_exc}"

    class FigureCanvasKivyAgg:  # type: ignore[no-redef]
        """A stand-in for the missing backend."""

        def __init__(self, figure: Any = None, **kwargs: Any) -> None:
            raise RuntimeError(
                "The Kivy Matplotlib backend is not available - install setuptools "
                "and kivy-garden.matplotlib (pip install setuptools kivy-garden.matplotlib)"
            )


#: How often the canvas is redrawn while the user drags (seconds).
REDRAW_INTERVAL = 1.0 / 30.0

#: How much the camera turns per pixel of drag.
DEGREES_PER_PIXEL = 0.4

#: How much the zoom changes between two pinches of the same distance.
ZOOM_SENSITIVITY = 1.0


class Plot3DCanvas(FigureCanvasKivyAgg):
    """A Matplotlib canvas that rotates instead of panning."""

    def __init__(self, figure: Any, **kwargs: Any) -> None:
        self.session: Any = None
        self._touches: dict[int, Any] = {}
        self._last_positions: dict[int, tuple[float, float]] = {}
        self._pinch_distance: float = 0.0
        self._dirty = False
        self._redraw_event = Clock.create_trigger(self._redraw, REDRAW_INTERVAL)
        super().__init__(figure=figure, **kwargs)

    # ------------------------------------------------------------------ api
    def set_session(self, session: Any) -> None:
        """Attach the session that owns the figure."""
        self.session = session
        self.figure = session.figure
        self.draw()

    def apply_view(self) -> None:
        """Copy the camera of the session into the figure and redraw."""
        if self.session is None:
            return
        self.session._apply_view()
        self._dirty = True
        self._redraw_event()

    def _redraw(self, *_args: Any) -> None:
        if self._dirty:
            self._dirty = False
            self.draw()

    # --------------------------------------------------------------- touch
    def on_touch_down(self, touch: Any) -> bool:
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        self._touches[touch.uid] = touch
        self._last_positions[touch.uid] = (touch.x, touch.y)
        if len(self._touches) == 1:
            self._start_interaction()
        elif len(self._touches) == 2:
            self._pinch_distance = self._touch_distance()
        return True

    def on_touch_move(self, touch: Any) -> bool:
        if touch.uid not in self._touches:
            return super().on_touch_move(touch)
        if len(self._touches) >= 2:
            distance = self._touch_distance()
            if self._pinch_distance > 1.0 and distance > 1.0:
                factor = distance / self._pinch_distance
                if self.session is not None:
                    self.session.zoom_by(factor**ZOOM_SENSITIVITY)
                self._pinch_distance = distance
                self.apply_view()
            return True
        if self.session is None:
            return True
        last_x, last_y = self._last_positions.get(touch.uid, (touch.x, touch.y))
        delta_x = float(touch.x) - float(last_x)
        delta_y = float(touch.y) - float(last_y)
        self._last_positions[touch.uid] = (touch.x, touch.y)
        self.session.rotate(
            d_elevation=-delta_y * DEGREES_PER_PIXEL, d_azimuth=delta_x * DEGREES_PER_PIXEL
        )
        self.apply_view()
        return True

    def on_touch_up(self, touch: Any) -> bool:
        if touch.uid not in self._touches:
            return super().on_touch_up(touch)
        self._touches.pop(touch.uid, None)
        self._last_positions.pop(touch.uid, None)
        if not self._touches:
            self._end_interaction()
        elif len(self._touches) == 1:
            self._pinch_distance = 0.0
        return True

    # ------------------------------------------------------------ internals
    def _touch_distance(self) -> float:
        points = [touch.pos for touch in self._touches.values()]
        if len(points) < 2:
            return 0.0
        return math.dist(points[0], points[1])

    def _start_interaction(self) -> None:
        if self.session is not None:
            self.session.begin_interaction()
            self.figure = self.session.figure

    def _end_interaction(self) -> None:
        if self.session is not None:
            self.session.end_interaction()
            self.figure = self.session.figure
        self.apply_view()


class Plot3DView(BoxLayout):
    """The canvas plus the camera buttons."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", dp(theme.GAP_DP))
        super().__init__(**kwargs)
        self.session: Any = None
        self.plot_canvas: Plot3DCanvas | None = None
        self._auto_rotate_event: Any = None
        self._build()

    # ------------------------------------------------------------------ ui
    def _build(self) -> None:
        self.canvas_box = BoxLayout(size_hint_y=1)
        self.add_widget(self.canvas_box)

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(4),
        )
        specs: tuple[tuple[str, str], ...] = (
            ("rotate_left", "<"),
            ("rotate_up", "^"),
            ("rotate_down", "v"),
            ("rotate_right", ">"),
            ("zoom_in", "+"),
            ("zoom_out", "-"),
            ("reset", "reset"),
            ("auto_rotate", "auto"),
        )
        for name, caption in specs:
            button = Button(
                text=caption,
                background_normal="",
                background_color=theme.SURFACE_ALT,
                color=theme.TEXT,
                font_size=theme.sp_size(16),
            )
            button.bind(on_release=lambda _b, action=name: self._button(action))
            buttons.add_widget(button)
            if name == "auto_rotate":
                self.auto_rotate_button = button
        self.add_widget(buttons)

    # ----------------------------------------------------------------- api
    def set_session(self, session: Any) -> None:
        """Show the figure of a :class:`Plot3DSession`."""
        self.session = session
        if self.plot_canvas is None:
            self.plot_canvas = Plot3DCanvas(figure=session.figure)
            self.canvas_box.add_widget(self.plot_canvas)
        else:
            self.plot_canvas.session = session
            self.plot_canvas.figure = session.figure
        self.plot_canvas.set_session(session)

    def _button(self, action: str) -> None:
        session = self.session
        if session is None:
            return
        if action == "rotate_left":
            session.rotate(d_azimuth=-15.0)
        elif action == "rotate_right":
            session.rotate(d_azimuth=15.0)
        elif action == "rotate_up":
            session.rotate(d_elevation=10.0)
        elif action == "rotate_down":
            session.rotate(d_elevation=-10.0)
        elif action == "zoom_in":
            session.zoom_by(1.2)
        elif action == "zoom_out":
            session.zoom_by(1 / 1.2)
        elif action == "reset":
            session.reset_view()
        elif action == "auto_rotate":
            self.toggle_auto_rotate()
        if self.plot_canvas is not None:
            self.plot_canvas.apply_view()

    def toggle_auto_rotate(self) -> bool:
        """Start or stop the automatic rotation. Returns the new state."""
        session = self.session
        if session is None:
            return False
        session.auto_rotate = not session.auto_rotate
        if session.auto_rotate:
            if self._auto_rotate_event is None:
                self._auto_rotate_event = Clock.create_trigger(self._auto_rotate_step, 1 / 20.0)
            self._auto_rotate_event()
        else:
            if self._auto_rotate_event is not None:
                self._auto_rotate_event.cancel()
        if hasattr(self, "auto_rotate_button"):
            self.auto_rotate_button.background_color = (
                theme.ACCENT if session.auto_rotate else theme.SURFACE_ALT
            )
        return session.auto_rotate

    def _auto_rotate_step(self, _dt: float) -> None:
        session = self.session
        if session is None or not session.auto_rotate:
            return
        session.step_auto_rotate(1 / 20.0)
        if self.plot_canvas is not None:
            self.plot_canvas.apply_view()
        if self._auto_rotate_event is not None:
            self._auto_rotate_event()


__all__ = ["Plot3DCanvas", "Plot3DView"]
