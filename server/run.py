"""Run the Aieva fog server with safe logging (works with python and pythonw)."""

from __future__ import annotations

import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")  # noqa: SIM115

import uvicorn

from server.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
