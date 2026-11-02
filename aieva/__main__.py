"""``python -m aieva`` - the Aieva background application.

The board service is the heart of Aieva: it runs in the background of the
smart board, reads what is written there and works on it (OCR, the solution,
the graph). The window of the teacher (``python -m aieva.ui.app``) is the
manual part next to it - both use the same core.

Everything the command line of the service offers is available here::

    python -m aieva run
    python -m aieva status
    python -m aieva install-autostart
"""

from __future__ import annotations

from aieva.core.service.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
