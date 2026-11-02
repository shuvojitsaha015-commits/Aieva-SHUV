"""The floating window above the board.

The background service reads the board in the background - this window shows
what it found. It floats above everything (always on top), sits in the corner
of the board and disappears again after a few seconds, so the teacher sees the
result without touching the computer.

The window is a **separate process**: the service starts it when it is asked
to (``--overlay``) and it only reads the file ``last_result.json``. The data
itself comes from the core (:mod:`aieva.core.service.overlay`), so the
window never talks to the service directly.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any

from aieva.core.service.overlay import pretty, read_result, result_stamp

LOGGER = logging.getLogger(__name__)

#: How often the window looks at the result file (seconds).
POLL_SECONDS = 0.4


def build_overlay_app() -> Any:
    """The Kivy application of the window."""
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.image import Image as KivyImage
    from kivy.uix.label import Label

    from aieva.ui import theme

    class BoardOverlay(App):
        """A small window above the board."""

        title = "Aieva"

        def __init__(self, result_file: str | Path, seconds: float = 8.0, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.result_file = Path(result_file)
            self.seconds = float(seconds)
            self._stamp = ""
            self._hide_at = 0.0
            self.reading: Any = None
            self.answer: Any = None
            self.picture: Any = None

        # ------------------------------------------------------------- build
        def build(self) -> Any:
            Window.always_on_top = True
            Window.borderless = True
            Window.size = (720, 340)
            try:
                Window.alpha = 0.0
            except Exception:  # noqa: BLE001 - not every platform can fade the window
                pass

            root = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(4))
            root.background_color = theme.CARD

            eyebrow = Label(
                text="AIEVA",
                size_hint_y=None,
                height=dp(26),
                font_size=theme.sp_size(12),
                color=theme.ACCENT,
                halign="left",
                valign="middle",
            )
            eyebrow.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            root.add_widget(eyebrow)

            self.reading = Label(
                text="",
                size_hint_y=None,
                height=dp(46),
                font_size=theme.sp_size(26),
                color=theme.TEXT,
                halign="left",
                valign="middle",
            )
            self.reading.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            root.add_widget(self.reading)

            self.answer = Label(
                text="",
                size_hint_y=None,
                height=dp(40),
                font_size=theme.sp_size(19),
                color=theme.PRIMARY,
                halign="left",
                valign="middle",
            )
            self.answer.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            root.add_widget(self.answer)

            self.picture = KivyImage(
                size_hint_y=None,
                height=dp(180),
                allow_stretch=True,
                keep_ratio=True,
                opacity=0,
            )
            root.add_widget(self.picture)

            root.bind(on_touch_down=lambda *_args: self._hide())
            Clock.schedule_interval(self._poll, POLL_SECONDS)
            Clock.schedule_once(lambda _dt: self._place(), 0)
            return root

        def _place(self) -> None:
            """Put the window into the top right corner of the board."""
            try:
                from kivy.core.window import Window

                width, height = Window.size
                Window.top = height - 24
                Window.left = width - 720 - 24
            except Exception:  # noqa: BLE001 - the window stays where it is
                pass

        # ------------------------------------------------------------- the loop
        def _poll(self, _dt: float) -> None:
            payload = read_result(self.result_file)
            if payload is None:
                return
            stamp = result_stamp(payload)
            if stamp != self._stamp:
                self._stamp = stamp
                self._show(payload)
            elif self._hide_at and time.monotonic() >= self._hide_at:
                self._hide()

        def _show(self, payload: dict[str, Any]) -> None:
            reading = payload.get("plain") or payload.get("latex") or ""
            self.reading.text = pretty(reading)
            self.answer.text = payload.get("answer") or ""
            plot = payload.get("plot") or ""
            if plot and Path(plot).is_file():
                self.picture.source = plot
                self.picture.opacity = 1
            else:
                self.picture.opacity = 0
            self._hide_at = time.monotonic() + self.seconds
            self._visible(True)

        def _hide(self) -> None:
            self._visible(False)

        def _visible(self, visible: bool) -> None:
            try:
                from kivy.core.window import Window

                Window.alpha = 1.0 if visible else 0.0
            except Exception:  # noqa: BLE001 - not every platform can fade the window
                pass
            if self.root is not None:
                self.root.opacity = 1 if visible else 0

    return BoardOverlay


def build_parser() -> argparse.ArgumentParser:
    """The command line of the window."""
    parser = argparse.ArgumentParser(
        prog="aieva-overlay", description="The floating window of the Aieva board service."
    )
    parser.add_argument(
        "--result-file",
        default=".aieva_cache/service_state.json",
        help="the state file of the service (the window reads the result next to it)",
    )
    parser.add_argument("--seconds", type=float, default=8.0, help="how long the window stays")
    parser.add_argument("--verbose", action="store_true", help="log every step")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Start the window."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from aieva.core.service.runner import result_path

    target = result_path(args.result_file)
    application = build_overlay_app()(result_file=target, seconds=args.seconds)
    application.run()
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())


__all__ = ["POLL_SECONDS", "build_overlay_app", "build_parser", "main"]
