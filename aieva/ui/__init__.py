"""Kivy user interface layer.

Every widget in here is allowed to import the core, but the core never imports
Kivy. Long running work (OCR, LLM, symbolic algebra) must be dispatched to a
worker thread and marshalled back onto the main thread with ``Clock.schedule_once``.
"""

from __future__ import annotations

__all__: list[str] = []
