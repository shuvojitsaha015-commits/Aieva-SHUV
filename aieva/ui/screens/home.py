"""The home screen: the dashboard of the application.

The screen is **subject agnostic**: the list of subjects is built from the
plugin registry metadata, so Biology / Chemistry / Physics can be added later
without touching this file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from aieva.core.history import History
from aieva.core.plugin_base import PluginMeta
from aieva.core.plugin_registry import subject_metas
from aieva.ui import theme
from aieva.ui.widgets.card import CardButton, Chip, Panel
from aieva.ui.widgets.input_bar import InputBar


class HomeScreen(Screen):
    """Landing screen of the application."""

    #: Called with ``(text, kind)`` when the user submits an equation.
    on_request_plot: Callable[[str, str], None] | None = None
    #: Called with the subject name when the user picks another subject.
    on_subject_changed: Callable[[str], None] | None = None
    #: Called when the teacher taps the lens (read what is on the board).
    on_scan_board: Callable[[], None] | None = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.name = "home"
        self.history = History()
        self.subjects: list[PluginMeta] = []
        self.selected_subject: str = ""
        self._subject_buttons: dict[str, Button] = {}
        self._build()
        self.set_subjects(subject_metas())

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = BoxLayout(
            orientation="vertical", padding=dp(theme.PANEL_PADDING_DP), spacing=dp(theme.GAP_DP)
        )
        root.add_widget(self._build_hero())

        self.cards = GridLayout(
            cols=4,
            spacing=dp(theme.GAP_DP),
            size_hint_y=None,
            height=dp(2 * theme.CARD_HEIGHT_DP + theme.GAP_DP),
        )
        self.whiteboard_button = self._card(
            "Whiteboard", "Draw an equation with the finger, then plot it", "✎", theme.ACCENT
        )
        self.whiteboard_button.bind(on_release=lambda _b: self._go("whiteboard"))
        self.type_button = self._card(
            "Type an equation", "Type it and watch the figure change", "=", theme.ACCENT
        )
        self.type_button.bind(on_release=lambda _b: self.focus_input())
        self.calculus_button = self._card(
            "Calculus", "Integrals, Riemann sums and tangents", "∫", theme.PRIMARY
        )
        self.calculus_button.bind(on_release=lambda _b: self._go("calculus"))
        self.linalg_button = self._card(
            "Linear algebra", "Matrices, eigen values and the Argand plane", "λ", theme.PRIMARY
        )
        self.linalg_button.bind(on_release=lambda _b: self._go("linalg"))
        self.plot3d_button = self._card(
            "3D plots", "Surfaces with touch rotation and zoom", "◍", theme.PRIMARY
        )
        self.plot3d_button.bind(on_release=lambda _b: self._go("plot3d"))
        self.solve_button = self._card(
            "Solve from screen", "Read the board and get the steps", "◉", theme.WARNING
        )
        self.solve_button.bind(on_release=lambda _b: self._go("solver"))
        self.documents_button = self._card(
            "Documents", "The equations of a PDF, PPTX or DOCX", "▤", theme.TEXT_MUTED
        )
        self.documents_button.bind(on_release=lambda _b: self._go("documents"))
        self.wordproblem_button = self._card(
            "Word problem", "Analyse it, confirm it, watch the picture", "✦", theme.ACCENT
        )
        self.wordproblem_button.bind(on_release=lambda _b: self._go("wordproblem"))
        for button in (
            self.whiteboard_button,
            self.type_button,
            self.calculus_button,
            self.linalg_button,
            self.plot3d_button,
            self.solve_button,
            self.documents_button,
            self.wordproblem_button,
        ):
            self.cards.add_widget(button)
        root.add_widget(self.cards)

        root.add_widget(self._build_history())

        self.input_bar = InputBar()
        self.input_bar.on_submit = self._on_submitted
        root.add_widget(self.input_bar)

        self.add_widget(root)

    def _build_hero(self) -> BoxLayout:
        """The headline of the dashboard and the subject picker."""
        hero = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(84),
            spacing=dp(theme.GAP_DP),
        )

        titles = BoxLayout(orientation="vertical", spacing=dp(2))
        headline = Label(
            text="Mathematics you can touch.",
            size_hint_y=None,
            height=dp(38),
            font_size=theme.sp_size(28),
            color=theme.TEXT,
            halign="left",
            valign="middle",
        )
        headline.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        titles.add_widget(headline)

        self.subject_label = Label(
            text="Type an equation, move a parameter and watch the picture appear.",
            size_hint_y=None,
            height=dp(26),
            font_size=theme.sp_size(14),
            color=theme.TEXT_MUTED,
            halign="left",
            valign="middle",
        )
        self.subject_label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        titles.add_widget(self.subject_label)
        hero.add_widget(titles)

        # The lens of the board: one tap and the board is read.
        self.scan_button = Button(
            text="Scan the board",
            size_hint_x=None,
            width=dp(170),
            height=dp(44),
            background_normal="",
            background_color=theme.PRIMARY,
            color=theme.TEXT,
            font_size=theme.sp_size(15),
        )
        self.scan_button.bind(on_release=lambda _b: self.scan_board())
        hero.add_widget(self.scan_button)

        self.subject_row = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            width=dp(150),
            height=dp(44),
            spacing=dp(theme.GAP_DP),
        )
        hero.add_widget(self.subject_row)
        return hero

    def _build_history(self) -> Panel:
        """The recent equations, in a panel of their own."""
        panel = Panel()
        heading = Label(
            text="Recent equations",
            size_hint_y=None,
            height=dp(26),
            font_size=theme.sp_size(15),
            color=theme.TEXT_MUTED,
            halign="left",
            valign="middle",
        )
        heading.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
        panel.add_widget(heading)

        self.history_list = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2), padding=[0, 0, 0, dp(2)]
        )
        self.history_list.bind(
            minimum_height=self.history_list.setter("height"),
        )
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.history_list)
        panel.add_widget(scroll)
        return panel

    def _card(
        self,
        title: str,
        subtitle: str,
        glyph: str,
        accent: tuple[float, float, float, float],
    ) -> CardButton:
        """One tile of the grid."""
        return CardButton(title=title, subtitle=subtitle, glyph=glyph, accent=accent)

    # ----------------------------------------------------------------- API
    def set_subjects(self, subjects: list[PluginMeta]) -> None:
        """Show the subjects published by the plugin registry."""
        self.subjects = list(subjects)
        self.subject_row.clear_widgets()
        self._subject_buttons.clear()
        for meta in self.subjects:
            button = Chip(text=meta.display_name or meta.name.title())
            button.bind(on_release=lambda _b, name=meta.name: self.select_subject(name))
            self._subject_buttons[meta.name] = button
            self.subject_row.add_widget(button)
        total = sum(button.width for button in self._subject_buttons.values())
        total += dp(theme.GAP_DP) * max(len(self._subject_buttons) - 1, 0)
        self.subject_row.width = max(total, dp(120))
        if self.subjects:
            names = [meta.name for meta in self.subjects]
            if self.selected_subject not in names:
                self.select_subject(names[0])
        else:
            self.selected_subject = ""

    def select_subject(self, subject: str) -> None:
        """Switch the active subject (the app resolves the plugin)."""
        self.selected_subject = subject
        for name, button in self._subject_buttons.items():
            button.set_active(name == subject)
        if self.on_subject_changed is not None:
            self.on_subject_changed(subject)

    def on_pre_enter(self, *_args: Any) -> None:
        self.refresh_history()

    def focus_input(self) -> None:
        """Focus the manual input (the 'Type an equation' card)."""
        self.input_bar.text_input.focus = True

    def scan_board(self) -> None:
        """The teacher tapped the lens - read what is on the board."""
        if self.on_scan_board is not None:
            self.on_scan_board()

    def refresh_history(self) -> None:
        """Rebuild the history list from :class:`~aieva.core.history.History`."""
        self.history_list.clear_widgets()
        entries = self.history.recent(12)
        if not entries:
            label = Label(
                text="Nothing yet - type an equation below.",
                size_hint_y=None,
                height=dp(34),
                font_size=theme.sp_size(14),
                color=theme.TEXT_MUTED,
                halign="left",
                valign="middle",
            )
            label.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            self.history_list.add_widget(label)
            return
        for entry in entries:
            button = Button(
                text=entry.raw,
                size_hint_y=None,
                height=dp(38),
                background_normal="",
                background_color=theme.SURFACE,
                color=theme.TEXT,
                font_size=theme.sp_size(15),
                halign="left",
            )
            button.bind(
                on_release=lambda _b, raw=entry.raw, kind=entry.kind, subject=entry.subject: self._load_history_entry(
                    raw, kind, subject
                )
            )
            button.bind(size=lambda w, _v: setattr(w, "text_size", w.size))
            self.history_list.add_widget(button)

    def remember(self, raw: str, kind: str = "text", subject: str = "math") -> None:
        """Store an equation in the history and refresh the list."""
        self.history.add(raw=raw, kind=kind, subject=subject or "math")
        self.refresh_history()

    # ------------------------------------------------------------ internals
    def _load_history_entry(self, raw: str, kind: str, subject: str) -> None:
        if subject and subject != self.selected_subject:
            self.select_subject(subject)
        self.input_bar.set_kind(kind)
        self.input_bar.set_text(raw)
        self.focus_input()

    def _on_submitted(self, text: str, kind: str) -> None:
        if self.on_request_plot is not None:
            self.on_request_plot(text, kind)

    def _go(self, screen_name: str) -> None:
        manager = self.manager
        if manager is None:
            return
        if screen_name in manager.screen_names:
            manager.current = screen_name


__all__ = ["HomeScreen"]
