"""Kivy application entry point.

Run with::

    python -m aieva.ui.app

The application is **subject agnostic**: the screens are built from the plugin
registry metadata, so a new subject only needs a new plugin module.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from kivy.config import Config

os.environ.setdefault("KIVY_NO_ARGS", "1")

Config.set("graphics", "width", "1280")
Config.set("graphics", "height", "720")
Config.set("graphics", "resizable", "1")
Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("kivy", "exit_on_escape", "1")

from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.lang import Builder  # noqa: E402
from kivy.metrics import dp  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402
from kivy.uix.screenmanager import ScreenManager  # noqa: E402
from kivy.uix.scrollview import ScrollView  # noqa: E402

from aieva.core.errors import AievaError, ParseError  # noqa: E402
from aieva.core.models import ParsedInput  # noqa: E402
from aieva.core.ocr.worker import OcrWorker  # noqa: E402
from aieva.core.plotting import FigureOwner  # noqa: E402
from aieva.core.plugin_base import SubjectPlugin  # noqa: E402
from aieva.core.plugin_registry import get_plugin, subject_metas  # noqa: E402
from aieva.core.service.config import ServiceConfig  # noqa: E402
from aieva.core.service.runner import BackgroundService  # noqa: E402
from aieva.core.user_settings import UserSettings  # noqa: E402
from aieva.ui import theme  # noqa: E402
from aieva.ui.error_handler import install_global_handler  # noqa: E402
from aieva.ui.screens.calculus import CalculusScreen  # noqa: E402
from aieva.ui.screens.documents import DocumentsScreen  # noqa: E402
from aieva.ui.screens.home import HomeScreen  # noqa: E402
from aieva.ui.screens.linalg import LinearAlgebraScreen  # noqa: E402
from aieva.ui.screens.plot3d import Plot3DScreen  # noqa: E402
from aieva.ui.screens.settings import SettingsScreen  # noqa: E402
from aieva.ui.screens.solver import SolverScreen  # noqa: E402
from aieva.ui.screens.wordproblem import WordProblemScreen  # noqa: E402
from aieva.ui.widgets.lens import LensOverlay, LensResult  # noqa: E402
from aieva.ui.widgets.plot_modal import PlotModal  # noqa: E402
from aieva.ui.widgets.tab_bar import TabBar  # noqa: E402
from aieva.ui.widgets.toast import show_toast  # noqa: E402
from aieva.ui.workers import run_in_background  # noqa: E402

LOGGER = logging.getLogger(__name__)

for _noisy in ("matplotlib", "matplotlib.font_manager", "PIL"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

KV_FILE = Path(__file__).with_name("main.kv")

DEFAULT_SUBJECT = "math"
DEFAULT_SCREEN = "home"

CANVAS_PUBLISH_SECONDS = 1.2

#: Tabs – whiteboard removed.
TABS: list[tuple[str, str]] = [
    ("home", "Home"),
    ("solver", "Solve"),
    ("calculus", "Calculus"),
    ("linalg", "Algebra"),
    ("plot3d", "3D"),
    ("wordproblem", "Word problems"),
    ("documents", "Documents"),
    ("settings", "Settings"),
]


class AievaApp(App):
    """The main Kivy application."""

    title = "Aieva"

    def build(self) -> BoxLayout:
        self.title = "Aieva"
        install_global_handler(self._report_error)
        if KV_FILE.is_file():
            Builder.load_file(str(KV_FILE))

        from kivy.core.window import Window

        try:
            Window.keep_screen_on = True
        except Exception:
            pass

        manager = ScreenManager()
        self.manager = manager
        self.home = HomeScreen()
        self.solver_screen = SolverScreen()
        self.documents_screen = DocumentsScreen()
        self.calculus_screen = CalculusScreen()
        self.linalg_screen = LinearAlgebraScreen()
        self.plot3d_screen = Plot3DScreen()
        self.wordproblem_screen = WordProblemScreen()
        self.settings_screen = SettingsScreen()

        manager.add_widget(self.home)
        manager.add_widget(self.calculus_screen)
        manager.add_widget(self.linalg_screen)
        manager.add_widget(self.plot3d_screen)
        manager.add_widget(self.solver_screen)
        manager.add_widget(self.wordproblem_screen)
        manager.add_widget(self.documents_screen)
        manager.add_widget(self.settings_screen)

        self.home.on_request_plot = self._on_request_plot
        self.solver_screen.capture_provider = lambda: None
        self.solver_screen.on_visualize = self._on_request_plot
        self.documents_screen.on_plot_requested = self._on_request_plot
        self.documents_screen.on_solve_requested = self._on_request_solve_text

        self.ocr_worker = OcrWorker(name="aieva-app-ocr")
        self.solver_screen.ocr_worker = self.ocr_worker
        self.home.on_subject_changed = self._on_subject_changed
        self.home.on_scan_board = self.scan_board

        self.plot_modal: PlotModal | None = None
        self._plot_owner: FigureOwner | None = None
        self._plot_session: Any = None
        self.lens_overlay: LensOverlay | None = None
        self.lens_result: LensResult | None = None
        self.current_subject: str = DEFAULT_SUBJECT
        self.home.set_subjects(subject_metas())

        self.user_settings = UserSettings.load()
        self.user_settings.apply_to_environment()
        self.settings_screen.on_settings_saved = self._on_settings_saved

        self.service: BackgroundService | None = None
        self.settings_screen.on_service_action = self._on_service_action
        if self.user_settings.background_service:
            self.start_background_service()

        self.tab_bar = TabBar(TABS)
        self.tab_bar.on_select = self._on_tab_selected
        manager.bind(current=self._on_screen_changed)
        self.tab_bar.highlight(DEFAULT_SCREEN)

        bar_scroll = ScrollView(
            do_scroll_x=True,
            do_scroll_y=False,
            size_hint_y=None,
            height=dp(theme.TITLE_BAR_DP),
            bar_width=0,
            bar_color=(0, 0, 0, 0),
        )
        bar_scroll.add_widget(self.tab_bar)

        container = BoxLayout(orientation="vertical")
        self._bar_scroll = bar_scroll
        container.add_widget(bar_scroll)
        container.add_widget(manager)
        Clock.schedule_once(lambda _dt: self._relayout_screens(), 0)
        return container

    def _relayout_screens(self) -> None:
        manager = self.manager
        if manager is None:
            return
        manager.do_layout()
        for screen in manager.children:
            screen.do_layout()
            for child in screen.children:
                child.do_layout()

    def _on_tab_selected(self, screen_name: str) -> None:
        if self.manager is not None and screen_name in self.manager.screen_names:
            self.manager.current = screen_name

    def _on_screen_changed(self, _manager: Any, current: str) -> None:
        tab_bar = getattr(self, "tab_bar", None)
        if tab_bar is not None:
            tab_bar.highlight(current)

    def on_stop(self) -> None:
        worker = getattr(self, "ocr_worker", None)
        if worker is not None:
            worker.stop()
        self.stop_background_service()
        self._release_plot()

    # ------------------------------------------------- background service
    def start_background_service(self) -> None:
        if self.service is not None and self.service.is_running:
            return
        config = ServiceConfig.from_env()
        self.service = BackgroundService(config=config, notifier=self._on_service_result)
        self.service.start()
        self.settings_screen.set_service_status("The service is watching the board.")

    def stop_background_service(self) -> None:
        if self.service is not None:
            self.service.stop()
            self.service = None
        self.settings_screen.set_service_status("The service is stopped.")

    def _on_service_result(self, payload: dict[str, Any]) -> None:
        Clock.schedule_once(lambda _dt: self._show_service_result(payload), 0)

    def _show_service_result(self, payload: dict[str, Any]) -> None:
        reading = payload.get("plain") or payload.get("latex") or ""
        answer = payload.get("answer") or ""
        text = f"The board was read: {reading}" if reading else "The board was read."
        if answer:
            text += f"  {answer}"
        self.settings_screen.set_service_status(text)

    def _on_service_action(self, action: str) -> None:
        if action == "start":
            self.start_background_service()
        elif action == "stop":
            self.stop_background_service()
        elif action == "install":
            self._install_autostart()
        elif action == "check":
            self._check_computer()
        self._refresh_service_status()

    def _check_computer(self) -> None:
        def work() -> Any:
            from aieva.core.doctor import build_report
            return build_report()

        def on_done(report: Any) -> None:
            if report.ready:
                self.settings_screen.set_service_status(
                    "This computer is ready - the board is read in the background."
                )
                return
            problems = report.problems
            names = ", ".join(check.name for check in problems[:3])
            self.settings_screen.set_service_status(f"{len(problems)} thing(s) to fix: {names}")

        def on_error(exc: BaseException) -> None:
            self.settings_screen.set_service_status(f"The check failed: {exc}")

        run_in_background(work, on_result=on_done, on_error=on_error, name="aieva-doctor")

    def _install_autostart(self) -> None:
        from aieva.core.service.autostart import install_autostart
        message = install_autostart(project_dir=Path.cwd())
        self.settings_screen.set_service_status(message.splitlines()[0])

    def _refresh_service_status(self) -> None:
        service = self.service
        if service is None or not service.is_running:
            self.settings_screen.set_service_status("The service is stopped.")
        else:
            self.settings_screen.set_service_status("The service is watching the board.")

    # --------------------------------------------------------------- state
    @property
    def plugin(self) -> SubjectPlugin:
        return get_plugin(self.current_subject)

    def _on_subject_changed(self, subject: str) -> None:
        self.current_subject = subject or DEFAULT_SUBJECT

    # ------------------------------------------------------------- actions
    def _on_request_plot(self, text: str, kind: str) -> None:
        parsed = ParsedInput(raw=text, kind=kind, source="manual")
        plugin = self.plugin

        def work() -> tuple[Any, Any]:
            parsed_input = plugin.parse(parsed)
            session = plugin.create_session(parsed_input)
            if session is None:
                result = plugin.visualize(parsed_input)
                session = result
            return session, parsed_input

        def on_done(result: tuple[Any, Any]) -> None:
            session, parsed_input = result
            self.home.remember(parsed_input.raw, parsed_input.kind, self.current_subject)
            figure = getattr(session, "figure", None)
            parameters = getattr(session, "parameters", []) or []
            latex = getattr(session, "info", None)

            self._release_plot()

            owner = FigureOwner(figure)
            self._plot_owner = owner
            self._plot_session = session
            self.plot_modal = PlotModal(
                figure=figure,
                session=session if hasattr(session, "set_param") else None,
                parameters=parameters,
                latex=getattr(latex, "latex", "") or parsed_input.latex or "",
                title=f"Aieva - {self.current_subject}",
                owner=owner,
            )
            self.plot_modal.open()

        def on_error(exc: BaseException) -> None:
            self._report_error(exc)

        run_in_background(work, on_done, on_error, name="aieva-parse")

    def _release_plot(self) -> None:
        modal, self.plot_modal = self.plot_modal, None
        owner, self._plot_owner = self._plot_owner, None
        session, self._plot_session = self._plot_session, None

        if modal is not None:
            try:
                modal.dismiss()
            except Exception as exc:
                LOGGER.info("The plot could not be closed: %s", exc)
            modal.dispose()
        if owner is not None:
            owner.release()
        if session is not None:
            close = getattr(session, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    LOGGER.info("The plot session could not be closed: %s", exc)

    def _on_settings_saved(self, settings: Any) -> None:
        self.user_settings = settings

    def _on_request_solve_text(self, text: str) -> None:
        if self.manager is not None:
            self.manager.current = "solver"
        self.solver_screen.solve_text(text)

    # ------------------------------------------------- lens (screen OCR scan)
    def scan_board(self) -> None:
        """Scan the screen for maths via the lens overlay."""
        if self.lens_overlay is not None or self.lens_result is not None:
            return
        service = self._service_for_scan()
        if service is None:
            show_toast("No capture source is available for the board.")
            return

        def grab() -> Any:
            source = service.source
            if source is None:
                raise RuntimeError("no capture source")
            return source.grab().image

        def on_capture(image: Any) -> None:
            self._show_lens(image)

        def on_error(exc: BaseException) -> None:
            show_toast(f"The board could not be captured: {exc}")

        run_in_background(grab, on_result=on_capture, on_error=on_error, name="aieva-lens")

    def _service_for_scan(self) -> BackgroundService | None:
        if self.service is None:
            self.start_background_service()
        return self.service

    def _show_lens(self, image: Any) -> None:
        overlay = LensOverlay(image=image)
        overlay.set_image(image)
        overlay.on_confirm = self._on_lens_confirmed
        overlay.on_cancel = self._close_lens
        self.lens_overlay = overlay
        from kivy.core.window import Window
        Window.add_widget(overlay)

    def _close_lens(self) -> None:
        from kivy.core.window import Window
        if self.lens_overlay is not None:
            Window.remove_widget(self.lens_overlay)
            self.lens_overlay = None

    def _on_lens_confirmed(self, region: tuple[int, int, int, int]) -> None:
        self._close_lens()
        service = self._service_for_scan()
        if service is None:
            show_toast("The board service is not available.")
            return

        from aieva.core.service.scan import remember_region
        remember_region(service.config.state_file, region)

        def read() -> Any:
            return service.scan_now(region)

        def on_result(run: Any) -> None:
            self._show_lens_result(run)

        def on_error(exc: BaseException) -> None:
            show_toast(f"The board could not be read: {exc}")

        run_in_background(read, on_result=on_result, on_error=on_error, name="aieva-lens-ocr")

    def _show_lens_result(self, run: Any) -> None:
        popup = LensResult()
        popup.show(
            reading=run.plain or run.latex,
            answer=run.answer,
            steps=run.steps,
            plot=run.plot,
            note=f"read in {run.duration_ms:.0f} ms",
        )
        popup.on_close = self._close_lens_result
        popup.on_open = self._open_lens_result
        self.lens_result = popup
        from kivy.core.window import Window
        Window.add_widget(popup)

    def _close_lens_result(self) -> None:
        from kivy.core.window import Window
        if self.lens_result is not None:
            Window.remove_widget(self.lens_result)
            self.lens_result = None

    def _open_lens_result(self, reading: str) -> None:
        self._close_lens_result()
        if self.manager is not None:
            self.manager.current = "solver"
        if reading:
            self.solver_screen.solve_text(reading)

    def _on_request_solve(self, image: Any) -> None:
        if self.manager is not None:
            self.manager.current = "solver"
        self.solver_screen.run_ocr(image)

    def _on_canvas_changed(self, image: Any = None) -> None:
        """Compatibility stub (whiteboard feature removed)."""
        if getattr(self, "_canvas_publish", None) is not None:
            self._canvas_publish.cancel()
        self._canvas_publish = Clock.schedule_once(
            lambda _dt: self._publish_canvas(image), getattr(self, "CANVAS_PUBLISH_SECONDS", 1.2)
        )

    def _publish_canvas(self, image: Any = None) -> None:
        """Publish canvas/board image to service folder if available."""
        if image is None:
            image = self._export_canvas()
        if image is not None:
            try:
                from aieva.core.service.canvas import publish_canvas
                from aieva.core.service.config import ServiceConfig

                folder = ServiceConfig.from_env().folder
                publish_canvas(folder, image)
            except Exception:
                pass

    def _export_canvas(self) -> Any:
        """Compatibility stub."""
        return None

    def _report_error(self, exc: BaseException) -> None:
        if isinstance(exc, ParseError):
            show_toast(f"Could not read that equation: {exc.message}")
        elif isinstance(exc, AievaError):
            show_toast(str(exc))
        else:
            show_toast(f"Something went wrong: {exc}")


def main() -> None:
    """Console entry point."""
    AievaApp().run()


if __name__ == "__main__":
    main()
