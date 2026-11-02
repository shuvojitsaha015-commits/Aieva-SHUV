"""Kivy application entry point.

Run with::

    python -m aieva.ui.app

The window is configured for 1280x720 desktop development.

The application is **subject agnostic**: the screens are built from the plugin
registry metadata, so a new subject (Biology, Chemistry, Physics, ...) only
needs a new plugin module - never a change in this file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from kivy.config import Config

# Kivy must not try to parse the argv of pytest / other tools.
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
from aieva.ui.screens.whiteboard import WhiteboardScreen  # noqa: E402
from aieva.ui.screens.wordproblem import WordProblemScreen  # noqa: E402
from aieva.ui.widgets.plot_modal import PlotModal  # noqa: E402
from aieva.ui.widgets.tab_bar import TabBar  # noqa: E402
from aieva.ui.widgets.toast import show_toast  # noqa: E402
from aieva.ui.workers import run_in_background  # noqa: E402

KV_FILE = Path(__file__).with_name("main.kv")

#: The subject that is active when the application starts.
DEFAULT_SUBJECT = "math"

#: The screen that is open when the application starts.
DEFAULT_SCREEN = "home"

#: The destinations of the navigation bar: ``(screen, label)``.
TABS: list[tuple[str, str]] = [
    ("home", "Home"),
    ("whiteboard", "Whiteboard"),
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
        # No unhandled exception may reach the teacher: the handler writes
        # the traceback into aieva.log and shows a toast.
        install_global_handler(self._report_error)
        if KV_FILE.is_file():
            Builder.load_file(str(KV_FILE))

        manager = ScreenManager()
        self.manager = manager
        self.home = HomeScreen()
        self.whiteboard_screen = WhiteboardScreen()
        self.solver_screen = SolverScreen()
        self.documents_screen = DocumentsScreen()
        self.calculus_screen = CalculusScreen()
        self.linalg_screen = LinearAlgebraScreen()
        self.plot3d_screen = Plot3DScreen()
        self.wordproblem_screen = WordProblemScreen()
        self.settings_screen = SettingsScreen()

        manager.add_widget(self.home)
        manager.add_widget(self.whiteboard_screen)
        manager.add_widget(self.calculus_screen)
        manager.add_widget(self.linalg_screen)
        manager.add_widget(self.plot3d_screen)
        manager.add_widget(self.solver_screen)
        manager.add_widget(self.wordproblem_screen)
        manager.add_widget(self.documents_screen)
        manager.add_widget(self.settings_screen)

        self.home.on_request_plot = self._on_request_plot
        self.solver_screen.capture_provider = self._capture_board
        self.solver_screen.on_visualize = self._on_request_plot
        self.documents_screen.on_plot_requested = self._on_request_plot
        self.documents_screen.on_solve_requested = self._on_request_solve_text

        # The OCR runs in the background - the UI thread is never blocked.
        self.ocr_worker = OcrWorker(name="aieva-app-ocr")
        self.solver_screen.ocr_worker = self.ocr_worker
        self.home.on_subject_changed = self._on_subject_changed
        self.whiteboard_screen.on_request_plot = self._on_request_plot
        self.whiteboard_screen.on_request_solve = self._on_request_solve

        self.plot_modal: PlotModal | None = None
        self.current_subject: str = DEFAULT_SUBJECT
        self.home.set_subjects(subject_metas())

        # The settings of the user (the server, the quality, the pen) are
        # applied before the first screen uses them.
        self.user_settings = UserSettings.load()
        self.user_settings.apply_to_environment()
        self.whiteboard_screen.apply_settings(self.user_settings)
        self.settings_screen.on_settings_saved = self._on_settings_saved

        # The background service: it watches the board while the teacher works.
        self.service: BackgroundService | None = None
        self.settings_screen.on_service_action = self._on_service_action
        if self.user_settings.background_service:
            self.start_background_service()

        # The navigation bar is on every screen - the settings have their own
        # tab, so the teacher never has to look for them.
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
        container.add_widget(bar_scroll)
        container.add_widget(manager)
        # the screens were measured before the bar took its space
        Clock.schedule_once(lambda _dt: self._relayout_screens(), 0)
        return container

    def _relayout_screens(self) -> None:
        """Measure the screens again - the bar changed the space they have."""
        manager = self.manager
        if manager is None:
            return
        manager.do_layout()
        for screen in manager.children:
            screen.do_layout()
            for child in screen.children:
                child.do_layout()

    def _on_tab_selected(self, screen_name: str) -> None:
        """The user pressed a tab."""
        if self.manager is not None and screen_name in self.manager.screen_names:
            self.manager.current = screen_name

    def _on_screen_changed(self, _manager: Any, current: str) -> None:
        """The screen changed - the navigation bar follows."""
        tab_bar = getattr(self, "tab_bar", None)
        if tab_bar is not None:
            tab_bar.highlight(current)

    def on_stop(self) -> None:
        """Stop the background worker when the app closes."""
        worker = getattr(self, "ocr_worker", None)
        if worker is not None:
            worker.stop()
        self.stop_background_service()

    # ------------------------------------------------------ the background service
    def start_background_service(self) -> None:
        """Start the watcher of the board (it runs in a thread)."""
        if self.service is not None and self.service.is_running:
            return
        config = ServiceConfig.from_env()
        self.service = BackgroundService(config=config, notifier=self._on_service_result)
        self.service.start()
        self.settings_screen.set_service_status("The service is watching the board.")

    def stop_background_service(self) -> None:
        """Stop the watcher of the board."""
        if self.service is not None:
            self.service.stop()
            self.service = None
        self.settings_screen.set_service_status("The service is stopped.")

    def _on_service_result(self, payload: dict[str, Any]) -> None:
        """The service read the board - the status of the settings follows."""
        Clock.schedule_once(lambda _dt: self._show_service_result(payload), 0)

    def _show_service_result(self, payload: dict[str, Any]) -> None:
        reading = payload.get("plain") or payload.get("latex") or ""
        answer = payload.get("answer") or ""
        text = f"The board was read: {reading}" if reading else "The board was read."
        if answer:
            text += f"  {answer}"
        self.settings_screen.set_service_status(text)

    def _on_service_action(self, action: str) -> None:
        """The teacher pressed a button of the background service."""
        if action == "start":
            self.start_background_service()
        elif action == "stop":
            self.stop_background_service()
        elif action == "install":
            self._install_autostart()
        self._refresh_service_status()

    def _install_autostart(self) -> None:
        """Start the service automatically with the computer."""
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
        """The plugin of the currently selected subject."""
        return get_plugin(self.current_subject)

    def _on_subject_changed(self, subject: str) -> None:
        self.current_subject = subject or DEFAULT_SUBJECT

    # ------------------------------------------------------------- actions
    def _on_request_plot(self, text: str, kind: str) -> None:
        """Parse the input in a worker thread and open the plot modal."""
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
            self.plot_modal = PlotModal(
                figure=figure,
                session=session if hasattr(session, "set_param") else None,
                parameters=parameters,
                latex=getattr(latex, "latex", "") or parsed_input.latex or "",
                title=f"Aieva - {self.current_subject}",
            )
            self.plot_modal.open()

        def on_error(exc: BaseException) -> None:
            self._report_error(exc)

        run_in_background(work, on_done, on_error, name="aieva-parse")

    def _on_settings_saved(self, settings: Any) -> None:
        """The user changed the settings - the whiteboard follows."""
        self.user_settings = settings
        self.whiteboard_screen.apply_settings(settings)

    def _on_request_solve_text(self, text: str) -> None:
        """Solve a piece of text that came from a document."""
        if self.manager is not None:
            self.manager.current = "solver"
        self.solver_screen.solve_text(text)

    def _capture_board(self) -> Any:
        """The image of the whiteboard (the capture source of the solver)."""
        return self.whiteboard_screen.whiteboard.export_to_image()

    def _on_request_solve(self, image: Any) -> None:
        """The user asked to solve the board - switch to the solver screen."""
        if self.manager is not None:
            self.manager.current = "solver"
        self.solver_screen.run_ocr(image)

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
