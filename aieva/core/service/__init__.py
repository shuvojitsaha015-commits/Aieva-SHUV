"""The background service of the smart board.

Aieva is an **application** that works in the background of the board: it
looks at the board, notices what was written, reads the mathematics, solves
it and draws the graph - without anybody having to touch the computer.

The package is pure Python (no Kivy), so the service runs headless on a
board computer and can be tested without a screen.

The parts:

* :mod:`aieva.core.service.config` - the settings of the service,
* :mod:`aieva.core.service.state` - the status file,
* :mod:`aieva.core.service.triggers` - when the board is worth reading,
* :mod:`aieva.core.service.sources` - where the pictures come from,
* :mod:`aieva.core.service.runner` - the service itself,
* :mod:`aieva.core.service.autostart` - starting with the computer,
* :mod:`aieva.core.service.overlay` - the floating window above the board.
"""

from aieva.core.service.config import SOURCES, ServiceConfig
from aieva.core.service.runner import BackgroundService, ServiceRun, result_path
from aieva.core.service.state import ServiceState
from aieva.core.service.triggers import TriggerPolicy

__all__ = [
    "SOURCES",
    "BackgroundService",
    "ServiceConfig",
    "ServiceRun",
    "ServiceState",
    "TriggerPolicy",
    "result_path",
]
