"""The floating overlay – a draggable messenger-style chat bubble.

The bubble sits on the **left edge** of the screen and can be **dragged**
anywhere.  It has two faces:

* the **pill** – a small capsule with a *Scan* button.  Tap it to read the
  screen for maths.
* the **popup** – the reading, the solution, the step-by-step explanation
  and (optionally) a plot.  It appears next to the pill after a scan.

The overlay is a **separate process**: it writes a scan-request file and
polls a result file.  The background service does the heavy lifting.
"""

from __future__ import annotations

import os

os.environ.setdefault("KIVY_NO_ARGS", "1")

import argparse
import logging
import threading
import time
from pathlib import Path
from typing import Any

from aieva.core.service.overlay import pretty, read_result, result_stamp
from aieva.core.service.scan import request_path, write_request

LOGGER = logging.getLogger(__name__)

#: How often the window polls the result file (seconds).
POLL_SECONDS = 0.5

#: Pill dimensions (the collapsed control).
PILL_WIDTH = 120
PILL_HEIGHT = 140

#: Popup dimensions (the expanded result card).
POPUP_WIDTH = 480
POPUP_HEIGHT = 520

#: Distance from screen edges (pixels).
MARGIN = 12


def screen_dimensions() -> tuple[int, int]:
    """The width and height of the primary monitor in pixels."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if w > 0 and h > 0:
            return int(w), int(h)
    except Exception:
        pass
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=False)
        return img.width, img.height
    except Exception:
        pass
    from kivy.core.window import Window
    return Window.size


def build_overlay_app() -> Any:
    """Build and return the Kivy application class."""
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.graphics import Color, Rectangle, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.image import Image as KivyImage
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from aieva.ui import theme

    # ----- colours for the bubble -----
    BG = (0.08, 0.08, 0.16, 0.95)
    BTN_SCAN = (0.10, 0.45, 0.95, 1)
    BTN_IDLE = (0.15, 0.15, 0.30, 1)
    TXT = (0.95, 0.95, 0.97, 1)
    TXT_DIM = (0.60, 0.63, 0.75, 1)
    ACCENT = (0.48, 0.42, 0.94, 1)

    class DraggableBubble(FloatLayout):
        """A floating widget that can be dragged around the screen."""

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._dragging = False
            self._drag_offset = (0.0, 0.0)

        def on_touch_down(self, touch: Any) -> bool:
            if self.collide_point(*touch.pos):
                # Only drag from the header / pill area (top 60 dp)
                local_y = touch.y - self.y
                if local_y > self.height - dp(60):
                    self._dragging = True
                    self._drag_offset = (touch.x - self.x, touch.y - self.y)
                    return True
            return super().on_touch_down(touch)

        def on_touch_move(self, touch: Any) -> bool:
            if self._dragging:
                self.x = touch.x - self._drag_offset[0]
                self.y = touch.y - self._drag_offset[1]
                return True
            return super().on_touch_move(touch)

        def on_touch_up(self, touch: Any) -> bool:
            if self._dragging:
                self._dragging = False
                return True
            return super().on_touch_up(touch)

    class BoardOverlay(App):
        """Messenger-style chat bubble for Aieva OCR."""

        title = "Aieva"

        def __init__(self, state_file: str | Path, seconds: float = 15.0, **kw: Any) -> None:
            super().__init__(**kw)
            self.state_file = Path(state_file)
            self.seconds = float(seconds)
            self._stamp = ""
            self._hide_at = 0.0
            self._scanning = False
            self._expanded = False
            # widgets
            self.bubble: DraggableBubble | None = None
            self.reading_label: Label | None = None
            self.answer_label: Label | None = None
            self.steps_label: Label | None = None
            self.picture: KivyImage | None = None
            self.scan_btn: Button | None = None
            self.card: BoxLayout | None = None

        # ---------------------------------------------------------------- build
        def build(self) -> Widget:
            Window.borderless = True
            Window.always_on_top = True
            try:
                Window.clearcolor = (0, 0, 0, 0)
            except Exception:
                pass

            # Make the window fill the screen so the bubble can be dragged
            # anywhere, but the window itself is transparent.
            sw, sh = screen_dimensions()
            Window.size = (sw, sh)
            Window.left = 0
            Window.top = sh

            root = FloatLayout()

            # -- The bubble container --
            self.bubble = DraggableBubble(
                size_hint=(None, None),
                size=(PILL_WIDTH, PILL_HEIGHT),
                pos=(MARGIN, sh // 2 - PILL_HEIGHT // 2),
            )
            self._draw_bg(self.bubble)

            # -- Header (drag handle) --
            header = Label(
                text="[b]Aieva[/b]",
                markup=True,
                size_hint=(1, None),
                height=dp(36),
                font_size=sp(16),
                color=ACCENT,
                halign="center",
                valign="middle",
                pos_hint={"top": 1},
            )
            header.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
            self.bubble.add_widget(header)

            # -- Result card (hidden initially) --
            self.card = BoxLayout(
                orientation="vertical",
                spacing=dp(4),
                padding=[dp(8), dp(4), dp(8), dp(4)],
                size_hint=(1, None),
                height=0,
                opacity=0,
                pos_hint={"top": 0.75},
            )

            self.reading_label = Label(
                text="",
                size_hint_y=None,
                height=dp(32),
                font_size=sp(15),
                color=TXT,
                halign="left",
                valign="middle",
                text_size=(POPUP_WIDTH - dp(20), None),
            )
            self.reading_label.bind(
                size=lambda w, _: setattr(w, "text_size", (w.width, None))
            )
            self.card.add_widget(self.reading_label)

            self.answer_label = Label(
                text="",
                size_hint_y=None,
                height=dp(28),
                font_size=sp(16),
                bold=True,
                color=ACCENT,
                halign="left",
                valign="middle",
                text_size=(POPUP_WIDTH - dp(20), None),
            )
            self.answer_label.bind(
                size=lambda w, _: setattr(w, "text_size", (w.width, None))
            )
            self.card.add_widget(self.answer_label)

            self.picture = KivyImage(
                size_hint_y=None,
                height=dp(160),
                allow_stretch=True,
                keep_ratio=True,
                opacity=0,
            )
            self.card.add_widget(self.picture)

            # steps in a scroll
            self.steps_label = Label(
                text="",
                font_size=sp(13),
                color=TXT_DIM,
                halign="left",
                valign="top",
                size_hint_y=None,
            )
            self.steps_label.bind(
                size=lambda w, _: setattr(w, "text_size", (w.width, None))
            )
            self.steps_label.bind(
                texture_size=lambda w, v: setattr(w, "height", max(dp(30), v[1]))
            )
            scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
            scroll.add_widget(self.steps_label)
            self.card.add_widget(scroll)

            self.bubble.add_widget(self.card)

            # -- Scan button --
            self.scan_btn = Button(
                text="🔍  Scan",
                size_hint=(0.9, None),
                height=dp(44),
                pos_hint={"center_x": 0.5, "y": 0.04},
                background_normal="",
                background_color=BTN_SCAN,
                color=TXT,
                font_size=sp(16),
                bold=True,
            )
            self.scan_btn.bind(on_release=lambda _: self._ask_for_scan())
            self.bubble.add_widget(self.scan_btn)

            root.add_widget(self.bubble)
            Clock.schedule_interval(self._poll, POLL_SECONDS)
            return root

        # ------------------------------------------------ background painting
        def _draw_bg(self, widget: Widget) -> None:
            with widget.canvas.before:
                Color(*BG)
                widget._bg_rect = RoundedRectangle(
                    pos=widget.pos, size=widget.size, radius=[dp(18)]
                )
            widget.bind(pos=self._update_bg, size=self._update_bg)

        @staticmethod
        def _update_bg(widget: Widget, *_: Any) -> None:
            try:
                widget._bg_rect.pos = widget.pos
                widget._bg_rect.size = widget.size
            except Exception:
                pass

        # ------------------------------------------------------------ polling
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

        # ------------------------------------------------------------ actions
        def _ask_for_scan(self) -> None:
            """The user tapped Scan – write the request file."""
            if self._scanning:
                return
            write_request(self.state_file)
            self._scanning = True
            if self.scan_btn:
                self.scan_btn.text = "⏳  Reading..."
                self.scan_btn.background_color = BTN_IDLE

        # ------------------------------------------------------------ display
        def _show(self, payload: dict[str, Any]) -> None:
            reading = payload.get("plain") or payload.get("latex") or ""
            if self.reading_label:
                self.reading_label.text = f"📝  {pretty(reading)}" if reading else ""
            if self.answer_label:
                answer = payload.get("answer") or ""
                self.answer_label.text = f"✅  {answer}" if answer else ""

            if self.steps_label:
                self.steps_label.text = _steps_text(payload.get("steps"))

            plot = payload.get("plot") or ""
            if self.picture:
                if plot and Path(plot).is_file():
                    self.picture.source = plot
                    self.picture.opacity = 1
                    self.picture.reload()
                else:
                    self.picture.opacity = 0

            self._scanning = False
            if self.scan_btn:
                self.scan_btn.text = "🔍  Scan"
                self.scan_btn.background_color = BTN_SCAN

            self._expand()
            self._hide_at = time.monotonic() + self.seconds

        def _expand(self) -> None:
            """Show the popup card – enlarge the bubble."""
            if self._expanded:
                return
            self._expanded = True
            if self.bubble:
                self.bubble.size = (POPUP_WIDTH, POPUP_HEIGHT)
            if self.card:
                self.card.height = POPUP_HEIGHT - dp(100)
                self.card.opacity = 1
                for c in self.card.children:
                    c.opacity = 1

        def _collapse(self) -> None:
            """Shrink back to the pill."""
            self._expanded = False
            self._hide_at = 0.0
            if self.card:
                self.card.height = 0
                self.card.opacity = 0
                for c in self.card.children:
                    c.opacity = 0
            if self.bubble:
                self.bubble.size = (PILL_WIDTH, PILL_HEIGHT)

        # -------------------------------------------------------- file helpers
        @property
        def result_file(self) -> Path:
            from aieva.core.service.runner import result_path
            return result_path(self.state_file)

    return BoardOverlay


def _steps_text(steps: Any) -> str:
    if not steps:
        return ""
    lines: list[str] = []
    for idx, step in enumerate(steps, 1):
        if isinstance(step, dict):
            text = step.get("text") or step.get("explanation") or step.get("latex") or ""
        else:
            text = str(step)
        if text:
            lines.append(f"{idx}. {text}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aieva-overlay",
        description="The floating Aieva chat bubble (OCR scan overlay).",
    )
    parser.add_argument(
        "--state-file",
        dest="state_file",
        default=".aieva_cache/service_state.json",
        help="the status file of the service",
    )
    parser.add_argument("--seconds", type=float, default=15.0, help="how long the popup stays")
    parser.add_argument("--verbose", action="store_true", help="log every step")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app_cls = build_overlay_app()
    app_cls(state_file=args.state_file, seconds=args.seconds).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PILL_WIDTH",
    "PILL_HEIGHT",
    "POPUP_WIDTH",
    "POPUP_HEIGHT",
    "POLL_SECONDS",
    "build_overlay_app",
    "build_parser",
    "main",
]
