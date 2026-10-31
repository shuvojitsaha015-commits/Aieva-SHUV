"""Aieva - screen-aware AI educational visualization assistant (Math edition, v1).

The package is split into three layers:

``aieva.core``
    Pure-Python math, parsing, caching and service abstractions. **Never imports
    Kivy**, so it can be unit tested headless.
``aieva.plugins``
    Subject implementations (``SubjectPlugin`` subclasses). Also Kivy-free.
``aieva.ui``
    The Kivy user interface. It may only *call* the core, never re-implement it.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
