"""The **Settings** screen (Phase 11).

The screen holds the settings a teacher changes while the application is
running:

* the URL of the Aieva server,
* the quality of the renderer (low / normal / high),
* the offline mode,
* the thickness of the pen and the palm rejection of the whiteboard.

The settings are written to the cache directory
(``<cache>/user_settings.json``) and are applied to the environment, so the
next start of the application uses them.
"""

from __future__ import annotations

import logging
from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

from aieva.core.user_settings import (
    DEFAULT_QUALITY,
    MAX_PALM_THRESHOLD,
    MAX_PEN_WIDTH,
    MIN_PALM_THRESHOLD,
    MIN_PEN_WIDTH,
    QUALITY_LEVELS,
    UserSettings,
)
from aieva.ui import theme
from aieva.ui.widgets.header import ScreenHeader
from aieva.ui.widgets.toast import show_toast

LOGGER = logging.getLogger(__name__)


class SettingsScreen(Screen):
    """The settings of the application."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "settings"
        self.settings = UserSettings.load()
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        outer = BoxLayout(orientation="vertical")
        outer.add_widget(
            ScreenHeader("Settings", "The server, the quality, the pen and the palm rejection")
        )

        # the form is longer than a small screen - it scrolls
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.size_hint_y = None
        # the scroll view needs to know how tall the form is
        root.bind(minimum_height=root.setter("height"))

        # --- the server ------------------------------------------------
        root.add_widget(self._label("Aieva server (OCR, explanations, word problems)"))
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.INPUT_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.server_input = TextInput(
            text=self.settings.server_url,
            multiline=False,
            hint_text="http://127.0.0.1:8000",
            font_size=theme.sp_size(16),
            background_color=theme.SURFACE,
            foreground_color=theme.TEXT,
            cursor_color=theme.PRIMARY,
            padding=[dp(12), dp(14)],
        )
        row.add_widget(self.server_input)
        root.add_widget(row)

        # --- the quality -----------------------------------------------
        root.add_widget(self._label("Quality of the renderer"))
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.quality_spinner = Spinner(
            text=self.settings.quality,
            values=list(QUALITY_LEVELS),
            size_hint_x=None,
            width=dp(180),
            height=dp(44),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
        )
        row.add_widget(self.quality_spinner)
        quality_hint = self._label("low = a small mesh (a slow board), high = a smooth picture")
        row.add_widget(quality_hint)
        root.add_widget(row)

        # --- the offline mode ------------------------------------------
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        row.add_widget(self._label("Offline mode (no cloud calls at all)"))
        self.offline_switch = Switch(active=self.settings.offline_mode)
        row.add_widget(self.offline_switch)
        root.add_widget(row)

        # --- the pen ---------------------------------------------------
        root.add_widget(self._label("Thickness of the pen"))
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.SLIDER_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.pen_slider = Slider(
            min=MIN_PEN_WIDTH,
            max=MAX_PEN_WIDTH,
            step=0.5,
            value=self.settings.pen_width,
        )
        row.add_widget(self.pen_slider)
        self.pen_label = self._label(f"{self.settings.pen_width:g} px")
        self.pen_slider.bind(value=self._on_pen)
        row.add_widget(self.pen_label)
        root.add_widget(row)

        # --- the palm rejection ----------------------------------------
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        row.add_widget(self._label("Ignore a palm that rests on the board"))
        self.palm_switch = Switch(active=self.settings.palm_rejection)
        row.add_widget(self.palm_switch)
        root.add_widget(row)

        root.add_widget(self._label("A contact bigger than this is treated as a palm"))
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.SLIDER_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.palm_slider = Slider(
            min=MIN_PALM_THRESHOLD,
            max=MAX_PALM_THRESHOLD,
            step=1,
            value=self.settings.palm_threshold,
        )
        row.add_widget(self.palm_slider)
        self.palm_label = self._label(f"{self.settings.palm_threshold:g} px")
        self.palm_slider.bind(value=self._on_palm)
        row.add_widget(self.palm_label)
        root.add_widget(row)

        # --- the background service -------------------------------------
        root.add_widget(self._label("Background service - the board is watched on its own"))
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        row.add_widget(self._label("Watch the board while the application is open"))
        self.service_switch = Switch(active=self.settings.background_service)
        row.add_widget(self.service_switch)
        root.add_widget(row)

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        self.service_status = self._label("The service is stopped.")
        row.add_widget(self.service_status)
        root.add_widget(row)

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        start_button = Button(
            text="Start",
            size_hint_x=None,
            width=dp(130),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        start_button.bind(on_release=lambda _b: self._service_action("start"))
        row.add_widget(start_button)

        stop_button = Button(
            text="Stop",
            size_hint_x=None,
            width=dp(130),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        stop_button.bind(on_release=lambda _b: self._service_action("stop"))
        row.add_widget(stop_button)

        auto_button = Button(
            text="Start with the computer",
            size_hint_x=None,
            width=dp(260),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        auto_button.bind(on_release=lambda _b: self._service_action("install"))
        row.add_widget(auto_button)

        check_button = Button(
            text="Check this computer",
            size_hint_x=None,
            width=dp(220),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        check_button.bind(on_release=lambda _b: self._service_action("check"))
        row.add_widget(check_button)
        root.add_widget(row)

        # --- the actions -----------------------------------------------
        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(theme.BUTTON_HEIGHT_DP),
            spacing=dp(theme.GAP_DP),
        )
        save_button = Button(
            text="Save",
            size_hint_x=None,
            width=dp(170),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        save_button.bind(on_release=lambda _b: self.save())
        actions.add_widget(save_button)

        reset_button = Button(
            text="Reset",
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        reset_button.bind(on_release=lambda _b: self.reset())
        actions.add_widget(reset_button)

        home_button = Button(
            text="Home",
            size_hint_x=None,
            width=dp(140),
            background_normal="",
            background_color=theme.SURFACE_ALT,
            color=theme.TEXT,
            font_size=theme.sp_size(16),
        )
        home_button.bind(on_release=lambda _b: self._go_home())
        actions.add_widget(home_button)
        root.add_widget(actions)

        self.status_label = Label(
            text="",
            size_hint_y=None,
            height=dp(30),
            font_size=theme.sp_size(14),
            color=theme.TEXT_MUTED,
            halign="left",
            valign="middle",
        )
        self.status_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        root.add_widget(self.status_label)

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(root)
        outer.add_widget(scroll)
        self.add_widget(outer)

    def _label(self, text: str) -> Label:
        label = Label(
            text=text,
            size_hint_y=None,
            height=dp(32),
            font_size=theme.sp_size(15),
            color=theme.TEXT_MUTED,
            halign="left",
            valign="middle",
        )
        label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        return label

    # ---------------------------------------------------- the background service
    def _service_action(self, action: str) -> None:
        """Tell the application what the teacher asked for."""
        if self.on_service_action is not None:
            self.on_service_action(action)

    def set_service_status(self, text: str) -> None:
        """Show what the background service is doing."""
        self.service_status.text = text

    #: Called with "start", "stop" or "install" when a button is pressed.
    on_service_action: Any = None

    # ------------------------------------------------------------- the values
    def _on_pen(self, _widget: Any, value: float) -> None:
        self.pen_label.text = f"{value:g} px"

    def _on_palm(self, _widget: Any, value: float) -> None:
        self.palm_label.text = f"{value:g} px"

    def current_settings(self) -> UserSettings:
        """The settings that the screen shows."""
        return UserSettings(
            server_url=self.server_input.text,
            quality=self.quality_spinner.text,
            offline_mode=self.offline_switch.active,
            pen_width=self.pen_slider.value,
            palm_rejection=self.palm_switch.active,
            palm_threshold=self.palm_slider.value,
            background_service=self.service_switch.active,
        )

    def save(self) -> None:
        """Write the settings and apply them."""
        settings = self.current_settings()
        try:
            path = settings.save()
        except OSError as exc:
            show_toast(f"The settings could not be written: {exc}")
            return
        settings.apply_to_environment()
        self.settings = settings
        self.status_label.text = f"Saved in {path}"
        show_toast("The settings were saved")
        if self.on_settings_saved is not None:
            self.on_settings_saved(settings)

    def reset(self) -> None:
        """Put the default settings back."""
        self.settings = UserSettings()
        self.server_input.text = ""
        self.quality_spinner.text = DEFAULT_QUALITY
        self.offline_switch.active = False
        self.pen_slider.value = self.settings.pen_width
        self.palm_switch.active = True
        self.palm_slider.value = self.settings.palm_threshold
        self.service_switch.active = True
        self.status_label.text = "The defaults are shown - press 'Save' to keep them."

    #: Called with the new settings after they were saved.
    on_settings_saved: Any = None

    def _go_home(self) -> None:
        if self.manager is not None:
            self.manager.current = "home"


__all__ = ["SettingsScreen"]
