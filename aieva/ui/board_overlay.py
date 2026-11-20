"""The floating messenger chat bubble for Aieva.

Floats above all windows (always on top, borderless).
Has two faces:
* **The Bubble**: A compact, sleek chat bubble on the screen (sticky to the
  left edge, draggable anywhere). Has 'Scan', 'Drag' and 'App' buttons.
* **The Popup**: Expands right next to the math problem that was solved, showing
  the recognized equation, the complete step-by-step calculus/algebra solution,
  and any generated plot. Can be closed with X or auto-dismisses.
"""

from __future__ import annotations

import os

os.environ.setdefault("KIVY_NO_ARGS", "1")

import argparse
import ctypes
import ctypes.wintypes
import logging
import threading
import time
from pathlib import Path
from typing import Any

from kivy.config import Config


def _screen_wh() -> tuple[int, int]:
    """Primary monitor size in physical pixels."""
    try:
        u32 = ctypes.windll.user32
        u32.SetProcessDPIAware()
        w = int(u32.GetSystemMetrics(0))
        h = int(u32.GetSystemMetrics(1))
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return 1920, 1080


SCREEN_W, SCREEN_H = _screen_wh()

#: Bubble dimensions
BUBBLE_WIDTH = 110
BUBBLE_HEIGHT = 180
CONTROL_SIZE = (BUBBLE_WIDTH, BUBBLE_HEIGHT)

#: Popup dimensions
POPUP_WIDTH = 540
POPUP_HEIGHT = 420
POPUP_SIZE = (POPUP_WIDTH, POPUP_HEIGHT)

MARGIN = 18

# Initial desktop coords (top-left origin, 0,0 is top-left of monitor)
_INIT_LEFT = MARGIN
_INIT_TOP = max(MARGIN, (SCREEN_H - BUBBLE_HEIGHT) // 2)

Config.set("graphics", "borderless", "1")
Config.set("graphics", "resizable", "0")
Config.set("graphics", "width", str(BUBBLE_WIDTH))
Config.set("graphics", "height", str(BUBBLE_HEIGHT))
Config.set("graphics", "position", "custom")
Config.set("graphics", "left", str(_INIT_LEFT))
Config.set("graphics", "top", str(_INIT_TOP))
Config.set("graphics", "always_on_top", "1")
Config.set("graphics", "window_state", "visible")

LOGGER = logging.getLogger(__name__)

POLL_SECONDS = 0.35


def control_position(
    screen_size: tuple[int, int],
    control_size: tuple[int, int] = CONTROL_SIZE,
    margin: int = MARGIN,
) -> tuple[int, int]:
    """Position on the left edge (top-down desktop coords)."""
    _w, h = screen_size
    return margin, (h + control_size[1]) // 2


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos() -> tuple[int, int]:
    """Desktop mouse cursor position."""
    pt = POINT()
    try:
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x), int(pt.y)
    except Exception:
        return 0, 0


def screen_dimensions() -> tuple[int, int]:
    return SCREEN_W, SCREEN_H


def grab_desktop(region: tuple[int, int, int, int] | None = None) -> Any:
    """Grab whole desktop or a crop region in top-down coords."""
    try:
        from PIL import ImageGrab

        if region and len(region) == 4:
            return ImageGrab.grab(bbox=region, all_screens=False).convert("RGB")
        return ImageGrab.grab(all_screens=False).convert("RGB")
    except Exception as exc:
        LOGGER.info("Screen grab failed: %s", exc)
        return None


def popup_position(
    screen_size: tuple[int, int],
    popup_size: tuple[int, int] = (POPUP_WIDTH, POPUP_HEIGHT),
    region: tuple[int, int, int, int] | None = None,
    bubble_pos: tuple[int, int] | None = None,
    margin: int = MARGIN,
) -> tuple[int, int]:
    """Position the popup next to the math problem or bubble (top-left origin)."""
    sw, sh = screen_size
    pw, ph = popup_size

    if region and len(region) == 4:
        r_left, r_top, r_right, _r_bottom = region
        # Try right of problem
        x = r_right + margin
        if x + pw > sw - margin:
            # Try left of problem
            x = r_left - pw - margin
        if x < margin:
            x = margin
        y = r_top
        if y + ph > sh - margin:
            y = sh - margin - ph
        if y < margin:
            y = margin
        return int(x), int(y)

    if bubble_pos:
        bx, by = bubble_pos
        x = bx + BUBBLE_WIDTH + margin
        if x + pw > sw - margin:
            x = bx - pw - margin
        if x < margin:
            x = margin
        y = min(max(margin, by), sh - ph - margin)
        return int(x), int(y)

    return margin, (sh - ph) // 2


def build_overlay_app() -> Any:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.graphics import Color, Line, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.image import Image as KivyImage
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from aieva.core.service.overlay import pretty, read_result, result_stamp
    from aieva.core.service.scan import (
        read_region,
        remember_region,
        request_path,
        write_request,
    )

    BG_BUBBLE = (0.07, 0.09, 0.16, 0.96)
    BG_CARD = (0.09, 0.11, 0.20, 0.98)
    COLOR_BORDER = (0.28, 0.38, 0.65, 0.85)
    COLOR_PRIMARY = (0.15, 0.46, 0.98, 1.0)
    COLOR_ACCENT = (0.48, 0.42, 0.98, 1.0)
    COLOR_SURFACE = (0.14, 0.17, 0.30, 1.0)
    COLOR_TEXT = (0.97, 0.98, 1.0, 1.0)
    COLOR_MUTED = (0.68, 0.72, 0.85, 1.0)

    class BoardOverlay(App):
        title = "Aieva Overlay"

        def __init__(self, state_file: str | Path, seconds: float = 25.0, **kw: Any) -> None:
            super().__init__(**kw)
            self.state_file = Path(state_file)
            self.seconds = float(seconds)
            self._stamp = ""
            self._hide_at = 0.0
            self._is_popup = False
            self._is_selecting = False
            self._bubble_desktop = (_INIT_LEFT, _INIT_TOP)

            # Drag tracking
            self._dragging = False
            self._drag_cursor_start = (0, 0)
            self._drag_win_start = (0, 0)

            # Views & widgets
            self.root_box: BoxLayout | None = None
            self.bubble_view: BoxLayout | None = None
            self.popup_view: BoxLayout | None = None
            self.scan_button: Button | None = None
            self.select_button: Button | None = None
            self.reading_label: Label | None = None
            self.answer_label: Label | None = None
            self.steps_label: Label | None = None
            self.picture: KivyImage | None = None
            self.selector: Any = None
            self._is_solving = False

        def build(self) -> Widget:
            Window.clearcolor = (0.05, 0.07, 0.14, 1)

            self.root_box = BoxLayout(orientation="vertical")
            self._draw_bg(self.root_box, BG_BUBBLE, radius=18)

            self._build_bubble_view()
            self._build_popup_view()

            self.root_box.add_widget(self.bubble_view)

            # Compatibility aliases
            self.drag_button = self.select_button
            self.reading = self.reading_label
            self.answer = self.answer_label
            self.steps = self.steps_label
            self.card = self.popup_view

            Clock.schedule_interval(self._poll, POLL_SECONDS)
            return self.root_box

        # ------------------------------------------------------------- views
        def _build_bubble_view(self) -> None:
            box = BoxLayout(
                orientation="vertical",
                spacing=dp(5),
                padding=[dp(7), dp(8), dp(7), dp(8)],
                size_hint=(1, 1),
            )

            # Drag handle
            header = Label(
                text="[b]⋮⋮ Aieva[/b]",
                markup=True,
                size_hint=(1, None),
                height=dp(26),
                font_size=sp(13),
                color=COLOR_ACCENT,
                halign="center",
                valign="middle",
            )
            header.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
            box.add_widget(header)

            # Scan button
            self.scan_button = Button(
                text="Scan",
                size_hint=(1, None),
                height=dp(44),
                background_normal="",
                background_color=COLOR_PRIMARY,
                color=COLOR_TEXT,
                font_size=sp(14),
                bold=True,
            )
            self.scan_button.bind(on_release=lambda _: self._on_scan_clicked())
            box.add_widget(self.scan_button)

            # Drag area selection button
            self.select_button = Button(
                text="Drag",
                size_hint=(1, None),
                height=dp(38),
                background_normal="",
                background_color=COLOR_SURFACE,
                color=COLOR_TEXT,
                font_size=sp(13),
            )
            self.select_button.bind(on_release=lambda _: self._start_region_selection())
            box.add_widget(self.select_button)

            # Open Main App button
            app_btn = Button(
                text="App",
                size_hint=(1, None),
                height=dp(32),
                background_normal="",
                background_color=(0.11, 0.14, 0.25, 1),
                color=COLOR_MUTED,
                font_size=sp(12),
            )
            app_btn.bind(on_release=lambda _: self._open_full_app())
            box.add_widget(app_btn)

            self.bubble_view = box

        def _build_popup_view(self) -> None:
            card = BoxLayout(
                orientation="vertical",
                spacing=dp(6),
                padding=[dp(14), dp(10), dp(14), dp(10)],
                size_hint=(1, 1),
            )

            top_bar = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(32))
            title = Label(
                text="[b]Aieva Math Solution[/b]",
                markup=True,
                font_size=sp(16),
                color=COLOR_ACCENT,
                halign="left",
                valign="middle",
            )
            title.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
            top_bar.add_widget(title)

            close_btn = Button(
                text="✕",
                size_hint=(None, 1),
                width=dp(36),
                background_normal="",
                background_color=COLOR_SURFACE,
                color=COLOR_TEXT,
                font_size=sp(14),
                bold=True,
            )
            close_btn.bind(on_release=lambda _: self._collapse_to_bubble())
            top_bar.add_widget(close_btn)
            card.add_widget(top_bar)

            self.reading_label = Label(
                text="",
                size_hint=(1, None),
                height=dp(34),
                font_size=sp(15),
                color=COLOR_TEXT,
                halign="left",
                valign="middle",
            )
            self.reading_label.bind(size=lambda w, _: setattr(w, "text_size", (w.width, None)))
            card.add_widget(self.reading_label)

            self.answer_label = Label(
                text="",
                size_hint=(1, None),
                height=dp(34),
                font_size=sp(17),
                bold=True,
                color=COLOR_PRIMARY,
                halign="left",
                valign="middle",
            )
            self.answer_label.bind(size=lambda w, _: setattr(w, "text_size", (w.width, None)))
            card.add_widget(self.answer_label)

            self.picture = KivyImage(
                size_hint=(1, None),
                height=dp(120),
                allow_stretch=True,
                keep_ratio=True,
                opacity=0,
            )
            card.add_widget(self.picture)

            self.steps_label = Label(
                text="",
                font_size=sp(13),
                color=COLOR_MUTED,
                halign="left",
                valign="top",
                size_hint_y=None,
            )
            self.steps_label.bind(size=lambda w, _: setattr(w, "text_size", (w.width, None)))
            self.steps_label.bind(
                texture_size=lambda w, v: setattr(w, "height", max(dp(40), v[1]))
            )
            scroll = ScrollView(do_scroll_x=False, size_hint=(1, 1))
            scroll.add_widget(self.steps_label)
            card.add_widget(scroll)

            self.popup_view = card

        # ---------------------------------------------------------- window hooks
        def on_start(self) -> None:
            Window.bind(on_touch_down=self._on_window_touch_down)
            Window.bind(on_touch_move=self._on_window_touch_move)
            Window.bind(on_touch_up=self._on_window_touch_up)
            self._ensure_win32_topmost()

        def _ensure_win32_topmost(self) -> None:
            """Ensure HWND_TOPMOST via Win32."""
            try:
                info = Window._win.get_window_info()
                hwnd = getattr(info, "window", None)
                if hwnd:
                    u32 = ctypes.windll.user32
                    HWND_TOPMOST = -1
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_SHOWWINDOW = 0x0040
                    u32.SetWindowPos(
                        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                    )
                    u32.ShowWindow(hwnd, 5)  # SW_SHOW
            except Exception as exc:
                LOGGER.info("Topmost hook: %s", exc)

        # ------------------------------------------------------------- dragging
        def _on_window_touch_down(self, _win: Any, touch: Any) -> bool:
            if self._is_popup or self._is_selecting:
                return False
            # Drag area is top 36px of bubble (Kivy Y is from bottom: y > height - 36)
            if touch.y > Window.height - dp(36):
                self._dragging = True
                self._drag_cursor_start = get_cursor_pos()
                self._drag_win_start = (Window.left, Window.top)
                touch.grab(self)
                return True
            return False

        def _on_window_touch_move(self, _win: Any, touch: Any) -> bool:
            if self._dragging and touch.grab_current is self:
                cx, cy = get_cursor_pos()
                dx = cx - self._drag_cursor_start[0]
                dy = cy - self._drag_cursor_start[1]
                new_left = self._drag_win_start[0] + dx
                new_top = self._drag_win_start[1] + dy
                Window.left = new_left
                Window.top = new_top
                self._bubble_desktop = (new_left, new_top)
                return True
            return False

        def _on_window_touch_up(self, _win: Any, touch: Any) -> bool:
            if self._dragging and touch.grab_current is self:
                self._dragging = False
                touch.ungrab(self)
                # Sticky snapping: if near left edge, snap to left margin
                if Window.left < 90:
                    Window.left = MARGIN
                    self._bubble_desktop = (MARGIN, Window.top)
                elif Window.left > SCREEN_W - BUBBLE_WIDTH - 90:
                    Window.left = SCREEN_W - BUBBLE_WIDTH - MARGIN
                    self._bubble_desktop = (Window.left, Window.top)
                return True
            return False

        # ------------------------------------------------------------- polling
        def _poll(self, _dt: float) -> None:
            if self._is_selecting:
                return
            payload = read_result(self.result_file)
            if payload is None:
                return
            stamp = result_stamp(payload)
            if stamp != self._stamp:
                self._stamp = stamp
                self._show_result(payload)
            elif self._hide_at and time.monotonic() >= self._hide_at:
                self._collapse_to_bubble()

        # ------------------------------------------------------------- actions
        def _on_scan_clicked(self) -> None:
            """When Scan is clicked: if region exists, scan it; otherwise open Drag selector."""
            reg = read_region(self.state_file)
            if reg is None:
                # Prompt user to select region
                self._start_region_selection()
            else:
                self._trigger_scan(reg)

        def _ask_for_scan(self) -> None:
            reg = read_region(self.state_file)
            self._trigger_scan(reg)

        def _trigger_scan(self, region: tuple[int, int, int, int] | None) -> None:
            if self._is_solving:
                return
            self._is_solving = True
            if self.scan_button:
                self.scan_button.text = "Reading..."
                self.scan_button.background_color = COLOR_SURFACE

            # Write request for background service if running
            write_request(self.state_file, region)

            # In addition, run in background thread for guaranteed execution
            threading.Thread(
                target=self._run_solve_worker,
                args=(region,),
                daemon=True,
            ).start()

        def _run_solve_worker(self, region: tuple[int, int, int, int] | None) -> None:
            """Self-contained background scan to ensure immediate execution."""
            try:
                img = grab_desktop(region)
                if img is None:
                    Clock.schedule_once(lambda _: self._reset_scan_button("No screen"), 0)
                    self._is_solving = False
                    return

                from aieva.core.ocr.pipeline import OcrPipeline
                from aieva.plugins.math.classify import classify
                from aieva.plugins.math.solver import solve_expression

                pipeline = OcrPipeline()
                result = pipeline.run(img)

                text = (result.plain or result.latex or "").strip()
                answer = ""
                answer_latex = ""
                steps: list[dict[str, Any]] = []

                if text:
                    try:
                        c = classify(text)
                        outcome = solve_expression(text, classification=c)
                        res = outcome.result
                        answer = res.answer_text
                        answer_latex = res.answer_latex
                        steps = [s.to_dict() for s in res.steps]
                    except Exception as exc:
                        LOGGER.info("SymPy solve fallback: %s", exc)

                if not answer:
                    answer = getattr(result, "answer", "") or "Could not solve equation"
                    answer_latex = getattr(result, "answer_latex", answer)
                    steps = getattr(result, "steps", []) or []

                payload = {
                    "created_at": time.time(),
                    "source": "overlay_scan",
                    "latex": result.latex,
                    "plain": result.plain,
                    "answer": answer,
                    "answer_latex": answer_latex,
                    "steps": steps,
                    "plot": "",
                    "region": list(region) if region else None,
                }

                # Publish result to disk
                import json

                self.result_file.parent.mkdir(parents=True, exist_ok=True)
                self.result_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

                Clock.schedule_once(lambda _: self._show_result(payload), 0)
            except Exception as exc:
                LOGGER.warning("Worker solve failed: %s", exc)
                Clock.schedule_once(lambda _: self._reset_scan_button("Error"), 0)
            finally:
                self._is_solving = False

        def _reset_scan_button(self, text: str = "Scan") -> None:
            if self.scan_button:
                self.scan_button.text = text
                self.scan_button.background_color = COLOR_PRIMARY

        def _start_region_selection(self) -> None:
            from aieva.ui.widgets.region_selector import RegionSelector

            self._is_selecting = True
            sw, sh = screen_dimensions()

            Window.size = (sw, sh)
            Window.left = 0
            Window.top = 0

            self.root_box.clear_widgets()

            selector = RegionSelector()
            selector.on_confirm = self._on_region_confirmed
            selector.on_cancel = self._on_region_cancelled
            self.selector = selector
            self.root_box.add_widget(selector)

        def _on_region_confirmed(self, region: tuple[int, int, int, int]) -> None:
            self._close_selector()
            remember_region(self.state_file, region)
            self._trigger_scan(region)

        def _on_region_cancelled(self) -> None:
            self._close_selector()

        def _close_selector(self) -> None:
            self._is_selecting = False
            self.root_box.clear_widgets()
            self.root_box.add_widget(self.bubble_view)
            Window.size = (BUBBLE_WIDTH, BUBBLE_HEIGHT)
            Window.left = self._bubble_desktop[0]
            Window.top = self._bubble_desktop[1]
            self._draw_bg(self.root_box, BG_BUBBLE, radius=18)
            self._ensure_win32_topmost()

        def _open_full_app(self) -> None:
            import subprocess
            import sys

            root = Path(__file__).resolve().parents[2]
            cmd = [sys.executable, "-m", "aieva.ui.app"]
            env = dict(os.environ)
            env["PYTHONPATH"] = str(root)
            try:
                subprocess.Popen(
                    cmd,
                    cwd=str(root),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                LOGGER.warning("Could not launch app: %s", exc)

        # ------------------------------------------------------------- display
        def _show_result(self, payload: dict[str, Any]) -> None:
            reading = payload.get("plain") or payload.get("latex") or ""
            answer = payload.get("answer") or ""
            steps = payload.get("steps") or []
            plot = payload.get("plot") or ""

            if self.reading_label:
                self.reading_label.text = pretty(reading) if reading else ""
            if self.answer_label:
                self.answer_label.text = answer if answer else "No solution found"
            if self.steps_label:
                self.steps_label.text = _format_steps(steps)

            if self.picture:
                if plot and Path(plot).is_file():
                    self.picture.source = plot
                    self.picture.opacity = 1
                    self.picture.reload()
                else:
                    self.picture.opacity = 0

            self._reset_scan_button("Scan")
            self._expand_to_popup(payload.get("region"))
            self._hide_at = time.monotonic() + self.seconds

        def _expand_to_popup(self, region: Any = None) -> None:
            self._is_popup = True
            if self.popup_view:
                self.popup_view.height = dp(POPUP_HEIGHT)
            self.root_box.clear_widgets()
            self._draw_bg(self.root_box, BG_CARD, radius=14)
            self.root_box.add_widget(self.popup_view)

            Window.size = (POPUP_WIDTH, POPUP_HEIGHT)
            sw, sh = screen_dimensions()
            reg_tuple = None
            if region and len(region) == 4:
                try:
                    reg_tuple = tuple(int(x) for x in region)
                except Exception:
                    pass

            x, y = popup_position(
                (sw, sh), (POPUP_WIDTH, POPUP_HEIGHT), reg_tuple, self._bubble_desktop
            )
            Window.left = x
            Window.top = y
            self._ensure_win32_topmost()

        def _collapse_to_bubble(self) -> None:
            self._is_popup = False
            self._hide_at = 0.0
            if self.popup_view:
                self.popup_view.height = 0
            self.root_box.clear_widgets()
            self._draw_bg(self.root_box, BG_BUBBLE, radius=18)
            self.root_box.add_widget(self.bubble_view)

            Window.size = (BUBBLE_WIDTH, BUBBLE_HEIGHT)
            Window.left = self._bubble_desktop[0]
            Window.top = self._bubble_desktop[1]
            self._ensure_win32_topmost()

        _show = _show_result
        _collapse = _collapse_to_bubble

        # ------------------------------------------------------------- helpers
        def _draw_bg(self, widget: Widget, color: tuple[float, ...], radius: int = 16) -> None:
            widget.canvas.before.clear()
            with widget.canvas.before:
                Color(*color)
                widget._bg_rect = RoundedRectangle(
                    pos=widget.pos, size=widget.size, radius=[dp(radius)]
                )
                Color(*COLOR_BORDER)
                widget._border_line = Line(
                    rounded_rectangle=(
                        widget.x, widget.y, widget.width, widget.height, dp(radius)
                    ),
                    width=1.2,
                )
            widget.bind(pos=self._update_bg, size=self._update_bg)

        def _update_bg(self, widget: Widget, *_: Any) -> None:
            try:
                widget._bg_rect.pos = widget.pos
                widget._bg_rect.size = widget.size
                widget._border_line.rounded_rectangle = (
                    widget.x, widget.y, widget.width, widget.height, dp(16)
                )
            except Exception:
                pass

        @property
        def result_file(self) -> Path:
            from aieva.core.service.runner import result_path

            return result_path(self.state_file)

        @property
        def request_file(self) -> Path:
            from aieva.core.service.scan import request_path

            return request_path(self.state_file)

    return BoardOverlay


def _format_steps(steps: Any) -> str:
    if not steps:
        return ""
    lines: list[str] = []
    for idx, s in enumerate(steps, 1):
        if isinstance(s, dict):
            text = s.get("text") or s.get("explanation") or s.get("latex") or ""
        else:
            text = str(s)
        if text:
            lines.append(f"{idx}. {text}")
    return "\n".join(lines)


steps_text = _format_steps


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
    parser.add_argument("--seconds", type=float, default=25.0, help="how long the popup stays")
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
    "BUBBLE_HEIGHT",
    "BUBBLE_WIDTH",
    "POPUP_HEIGHT",
    "POPUP_WIDTH",
    "build_overlay_app",
    "build_parser",
    "main",
    "popup_position",
]
