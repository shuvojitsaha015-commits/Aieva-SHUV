"""The application must start even when an optional package is missing.

On Python 3.12 and newer ``distutils`` is gone from the standard library.
A virtual environment without ``setuptools`` therefore cannot import
``kivy_garden.matplotlib`` - and the application died at the import of the
3D plot:

    ModuleNotFoundError: No module named 'distutils'

The plot has a picture as a fallback, so the application has to start
without the backend. These tests keep that promise.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

BACKEND = "kivy_garden.matplotlib.backend_kivyagg"


def test_the_application_starts_without_the_kivy_matplotlib_backend() -> None:
    """A computer without setuptools must still open the application."""
    with patch.dict(sys.modules, {BACKEND: None}):
        for name in (
            "aieva.ui.widgets.plot3d_view",
            "aieva.ui.screens.plot3d",
            "aieva.ui.screens.linalg",
            "aieva.ui.app",
        ):
            module = importlib.import_module(name)
            importlib.reload(module)
