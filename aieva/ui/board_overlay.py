"""The floating control above the board.

The background service reads the board in the background - this window shows
what it found. It floats above everything (always on top) and has three
faces:

* the **control** - a small messenger-like button on the **left edge** of
  the screen, in the middle. It is narrow, so it never covers the writing.
  *Scan* reads the board, *Drag* lets the teacher pull a rectangle over the
  writing.
* the **popup** - the reading, the solution, the explanation and the graph.
  It appears **next to the problem** (the service says where the problem
  was) and disappears again after a few seconds.
* the **selector** - the teacher drags a rectangle over a picture of the
  board; that part of the board is read.

The window is a **separate process**: it only writes a small request file
and reads the result file. The service does the work.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any

from aieva.core.service.overlay import pretty, read_result, result_stamp
from aieva.core.service.scan import request_path, write_request

LOGGER = logging.getLogger(__name__)

#: How often the window looks at the result file (seconds).
POLL_SECONDS = 0.35

#: The size of the control (a slim pill on the left edge).
CONTROL_SIZE = (86, 208)

#: The size of the popup.
POPUP_SIZE = (700, 520)

#: The distance to the edge of the screen (pixels).
MARGIN = 18


def control_position(
    screen_size: tuple[int, int], control_size: tuple[int, int] = CONTROL_SIZE, margin: int = MARGIN
) -> tuple[int, int]:
    """Where the control sits: the left edge, in the middle of the screen.

    The coordinates are the ones Kivy uses (``left`` from the left edge,
    ``top`` from the **bottom** of the screen).
    """
    width, height = screen_size
    _ = width
    return margin, (height + control_size[1]) // 2


def popup_position(
    screen_size: tuple[int, int],
    popup_size: tuple[int, int] = POPUP_SIZE,
    region: tuple[int, int, int, int] | None = None,
    margin: int = MARGIN,
) -> tuple[int, int]:
    """Where the popup goes: next to the problem, never off the screen.

    ``region`` is the rectangle of the problem in the pixels of the board
    (top down). It is ``None`` when the whole board was read - then the
    popup goes to the left edge.
    """
    width, height = screen_size
    popup_width, popup_height = popup_size
    if not region:
        return margin, (height + popup_height) // 2

    left, top, right, bottom = region
    x = right + margin
    if x + popup_width > width - margin:
        x = left - popup_width - margin
    if x < margin:
        x = margin

    # the region counts from the top, the window counts from the bottom
    y_top = height - top
    if y_top + popup_height > height - margin:
        y_top = height - margin - popup_height
    if y_top < margin:
        y_top = margin
    return int(x), int(y_top)


def grab_screen() -> Any:
    """A picture of the screen (``None`` when there is no screen)."""
    try:
        from PIL import ImageGrab

        return ImageGrab.grab(all_screens=False).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - no screen on a server
        LOGGER.info("The screen could not be captured: %s", exc)
        return None


def build_overlay_app() -> Any:
    """The Kivy application of the window."""
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.image import Image as KivyImage
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView

    from aieva.ui import theme

    class BoardOverlay(App):
        """The control and the popup of the board."""

        title = "Aieva"

        def __init__(self, state_file: str | Path, seconds: float = 10.0, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.state_file = Path(state_file)
            self.seconds = float(seconds)
            self._stamp = ""
            self._hide_at = 0.0
            self._scanning = False
            self._selecting = False
            self.reading: Any = None
            self.answer: Any = None
            self.steps: Any = None
            self.picture: Any = None
            self.card: Any = None
            self.scan_button: Any = None
            self.drag_button: Any = None
            self.selector: Any = None
            self._screen_picture: str = ""

        # ------------------------------------------------------------- build
        def build(self) -> Any:
            Window.always_on_top = True
            Window.borderless = True
            Window.size = CONTROL_SIZE
            try:
                Window.alpha = 1.0
            except Exception:  # noqa: BLE001 - not every platform can fade the window
                pass

            root = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(4))
            root.background_color = theme.CARD
            self._draw_pill(root)

            # --- the popup (hidden while there is nothing to show) -------
            self.card = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=0,
                spacing=dp(4),
            )
            self.reading = Label(
                text="",
                size_hint_y=None,
                height=dp(44),
                font_size=theme.sp_size(24),
                color=theme.TEXT,
                halign="left",
                valign="middle",
            )
            self.reading.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            self.card.add_widget(self.reading)

            self.answer = Label(
                text="",
                size_hint_y=None,
                height=dp(38),
                font_size=theme.sp_size(18),
                color=theme.PRIMARY,
                halign="left",
                valign="middle",
            )
            self.answer.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            self.card.add_widget(self.answer)

            self.picture = KivyImage(
                size_hint_y=None,
                height=dp(220),
                allow_stretch=True,
                keep_ratio=True,
                opacity=0,
            )
            self.card.add_widget(self.picture)

            # the explanation of the solution - it may be long, so it scrolls
            self.steps = Label(
                text="",
                font_size=theme.sp_size(14),
                color=theme.TEXT_MUTED,
                halign="left",
                valign="top",
            )
            self.steps.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            self.steps.bind(
                texture_size=lambda w, value: setattr(w, "height", max(dp(40), value[1]))
            )
            scroll = ScrollView(do_scroll_x=False)
            scroll.add_widget(self.steps)
            self.card.add_widget(scroll)

            root.add_widget(self.card)

            # --- the control ---------------------------------------------
            self.scan_button = Button(
                text="Scan",
                size_hint_y=None,
                height=dp(44),
                background_normal="",
                background_color=theme.PRIMARY,
                color=theme.TEXT,
                font_size=theme.sp_size(15),
            )
            self.scan_button.bind(on_release=lambda _b: self._ask_for_scan())
            root.add_widget(self.scan_button)

            self.drag_button = Button(
                text="Drag",
                size_hint_y=None,
                height=dp(34),
                background_normal="",
                background_color=theme.SURFACE_ALT,
                color=theme.TEXT,
                font_size=theme.sp_size(13),
            )
            self.drag_button.bind(on_release=lambda _b: self._ask_for_region())
            root.add_widget(self.drag_button)

            Clock.schedule_interval(self._poll, POLL_SECONDS)
            Clock.schedule_once(lambda _dt: self._place(), 0)
            return root

        @staticmethod
        def _draw_pill(root: Any) -> None:
            """Round the corners of the control (it is a pill, not a bar)."""
            from kivy.graphics import Color, RoundedRectangle

            from aieva.ui import theme

            with root.canvas.before:
                Color(*theme.CARD)
                root._pill = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(18)])
            root.bind(pos=BoardOverlay._move_pill, size=BoardOverlay._move_pill)

        @staticmethod
        def _move_pill(root: Any, *_args: Any) -> None:
            try:
                root._pill.pos = root.pos
                root._pill.size = root.size
            except Exception:  # noqa: BLE001 - the widget is gone
                pass

        # ------------------------------------------------------------- places
        def _place(self) -> None:
            """Put the control on the left edge, in the middle of the screen."""
            try:
                from kivy.core.window import Window

                width, height = Window.size
                left, top = control_position((width, height))
                Window.left = left
                Window.top = top
            except Exception:  # noqa: BLE001 - the window stays where it is
                pass

        def _place_popup(self, region: tuple[int, int, int, int] | None) -> None:
            """Put the popup next to the problem."""
            try:
                from kivy.core.window import Window

                width, height = Window.size
                left, top = popup_position((width, height), region=region)
                Window.left = left
                Window.top = top
            except Exception:  # noqa: BLE001 - the window stays where it is
                pass

        # ------------------------------------------------------------ the loop
        def _poll(self, _dt: float) -> None:
            payload = read_result(self.result_file)
            if payload is None:
                return
            stamp = result_stamp(payload)
            if stamp != self._stamp:
                self._stamp = stamp
                self._show(payload)
            elif self._hide_at and time.monotonic() >= self._hide_at:
                self._collapse()

        # ------------------------------------------------------------- actions
        def _ask_for_scan(self) -> None:
            """The teacher tapped the button - read the board.

            The area the teacher picked last is read again, so the answer is
            about the writing and not about the whole screen.
            """
            write_request(self.state_file)
            self._scanning = True
            self.scan_button.text = "Reading..."
            self.scan_button.background_color = theme.SURFACE_ALT

        def _ask_for_region(self) -> None:
            """The teacher wants to pull a rectangle over the writing."""
            image = grab_screen()
            if image is None:
                self.scan_button.text = "No screen"
                return
            self._show_selector(image)

        def _show_selector(self, image: Any) -> None:
            """Show the board with the draggable area (the whole screen)."""
            from kivy.core.window import Window

            from aieva.ui.widgets.region_selector import RegionSelector

            self._selecting = True
            self._screen_picture = str(Path(self.state_file).with_name("board_select.png"))
            try:
                image.save(self._screen_picture, format="PNG")
            except OSError as exc:  # pragma: no cover - a read only disk
                LOGGER.info("The picture of the board could not be saved: %s", exc)
                self._selecting = False
                return

            selector = RegionSelector()
            selector.on_confirm = self._on_region_confirmed
            selector.on_cancel = self._on_region_cancelled
            self.selector = selector
            self._resize_to_screen()
            Window.add_widget(selector)

        def _resize_to_screen(self) -> None:
            """Make the window as big as the screen (for the drag)."""
            try:
                from kivy.core.window import Window

                width, height = Window.size
                Window.size = (width, height)
                Window.left = 0
                Window.top = height
            except Exception:  # noqa: BLE001 - the window stays where it is
                pass

        def _on_region_confirmed(self, region: tuple[int, int, int, int]) -> None:
            """The teacher pulled the rectangle - read that part of the board."""
            from kivy.core.window import Window

            from aieva.core.service.scan import remember_region

            self._close_selector()
            if self.selector is not None:
                Window.remove_widget(self.selector)
                self.selector = None
            self._selecting = False

            remember_region(self.state_file, region)
            write_request(self.state_file, region)
            self._scanning = True
            self.scan_button.text = "Reading..."
            self.scan_button.background_color = theme.SURFACE_ALT
            self._collapse()

        def _on_region_cancelled(self) -> None:
            """The teacher stepped back - the control stays."""
            from kivy.core.window import Window

            self._close_selector()
            if self.selector is not None:
                Window.remove_widget(self.selector)
                self.selector = None
            self._selecting = False
            self._collapse()

        def _close_selector(self) -> None:
            """Leave the full screen mode."""
            try:
                from kivy.core.window import Window

                Window.size = CONTROL_SIZE
                self._place()
            except Exception:  # noqa: BLE001 - the window stays where it is
                pass

        # -------------------------------------------------------------- result
        def _show(self, payload: dict[str, Any]) -> None:
            reading = payload.get("plain") or payload.get("latex") or ""
            self.reading.text = pretty(reading)
            self.answer.text = payload.get("answer") or ""
            self.steps.text = steps_text(payload.get("steps"))
            plot = payload.get("plot") or ""
            if plot and Path(plot).is_file():
                self.picture.source = plot
                self.picture.opacity = 1
            else:
                self.picture.opacity = 0
            self._scanning = False
            self.scan_button.text = "Scan"
            self.scan_button.background_color = theme.PRIMARY
            self._expand(payload.get("region"))
            self._hide_at = time.monotonic() + self.seconds

        def _expand(self, region: Any = None) -> None:
            """Show the popup."""
            from kivy.metrics import dp

            self.card.height = dp(420)
            self.card.opacity = 1
            for child in self.card.children:
                child.opacity = 1
            self._resize(POPUP_SIZE)
            self._place_popup(_as_region(region))

        def _collapse(self) -> None:
            """Go back to the control."""

            self.card.height = 0
            self.card.opacity = 0
            for child in self.card.children:
                child.opacity = 0
            self._resize(CONTROL_SIZE)
            self._place()

        def _resize(self, size: tuple[int, int]) -> None:
            """Change the size of the window."""
            try:
                from kivy.core.window import Window

                Window.size = size
            except Exception:  # noqa: BLE001 - not every platform can resize it
                pass

        # ------------------------------------------------------------ the file
        @property
        def result_file(self) -> Path:
            """The file the service writes."""
            from aieva.core.service.runner import result_path

            return result_path(self.state_file)

        @property
        def request_file(self) -> Path:
            """The file the button writes."""
            return request_path(self.state_file)

    return BoardOverlay


def steps_text(steps: Any) -> str:
    """The explanation of the solution as text."""
    if not steps:
        return ""
    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        if isinstance(step, dict):
            text = step.get("text") or step.get("explanation") or step.get("latex") or ""
        else:
            text = str(step)
        if not text:
            continue
        lines.append(f"{index}. {text}")
    return "\n".join(lines)


def _as_region(value: Any) -> tuple[int, int, int, int] | None:
    """The rectangle of the problem (``None`` when there is none)."""
    if not value or len(value) != 4:
        return None
    try:
        return tuple(int(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def build_parser() -> argparse.ArgumentParser:
    """The command line of the window."""
    parser = argparse.ArgumentParser(
        prog="aieva-overlay", description="The floating control of the Aieva board service."
    )
    parser.add_argument(
        "--state-file",
        "--result-file",
        dest="state_file",
        default=".aieva_cache/service_state.json",
        help="the status file of the service (the window reads the result next to it)",
    )
    parser.add_argument("--seconds", type=float, default=10.0, help="how long the popup stays")
    parser.add_argument("--verbose", action="store_true", help="log every step")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Start the window."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    application = build_overlay_app()(state_file=args.state_file, seconds=args.seconds)
    application.run()
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())


__all__ = [
    "CONTROL_SIZE",
    "MARGIN",
    "POLL_SECONDS",
    "POPUP_SIZE",
    "build_overlay_app",
    "build_parser",
    "control_position",
    "grab_screen",
    "main",
    "popup_position",
    "steps_text",
]
