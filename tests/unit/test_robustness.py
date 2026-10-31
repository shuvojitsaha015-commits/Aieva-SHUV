"""The robustness pass of Phase 12.

No input may crash the application: the empty input, a huge exponent, a
division by zero, an undefined region, a server that does not answer, a
wrong key and a slider that is dragged too fast.
"""

from __future__ import annotations

import time

import pytest

from aieva.core.errors import CloudError, ParseError, SolveError


@pytest.fixture(autouse=True)
def _restore_the_environment():
    """The tests change the environment - the next test has to see the old values."""
    import os

    from aieva.config import get_settings

    names = ("AIEVA_SERVER_URL", "AIEVA_QUALITY", "AIEVA_OFFLINE_MODE", "AIEVA_CACHE_DIR")
    old = {name: os.environ.get(name) for name in names}
    yield
    for name, value in old.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    get_settings(reload=True)


# ------------------------------------------------------------------ the input
def test_an_empty_input_is_refused():
    from aieva.core.safe_parse import parse_text_expression

    with pytest.raises(ParseError):
        parse_text_expression("")
    with pytest.raises(ParseError):
        parse_text_expression("   ")


def test_an_empty_input_does_not_crash_the_solver():
    from aieva.plugins.math.solver import solve_expression

    with pytest.raises((ParseError, SolveError)):
        solve_expression("")


def test_a_huge_exponent_is_refused_quickly():
    """``x**999999999`` would kill the process when SymPy computes the roots."""
    from aieva.core.safe_parse import parse_text_expression
    from aieva.plugins.math.solver import solve_expression

    start = time.perf_counter()
    with pytest.raises(ParseError):
        parse_text_expression("x**999999999")
    with pytest.raises((ParseError, SolveError)):
        solve_expression("x**999999999 = 2")
    assert (time.perf_counter() - start) < 5.0


def test_a_huge_exponent_inside_an_equation_is_refused():
    from aieva.core.safe_parse import parse_equation

    with pytest.raises(ParseError):
        parse_equation("y = x**(10**10)")


def test_a_division_by_zero_has_a_clear_message():
    from aieva.plugins.math.solver import solve_expression

    with pytest.raises(SolveError) as error:
        solve_expression("1/0")
    assert "not defined" in str(error.value)


def test_an_undefined_region_is_masked_in_the_plot():
    """``1/x`` has a pole - the figure must not show an infinity."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    import numpy as np

    from aieva.plugins.math.equations import mask_discontinuities

    with np.errstate(divide="ignore", invalid="ignore"):
        y = 1.0 / np.linspace(-5.0, 5.0, 1001)
    masked = mask_discontinuities(y)
    values = np.asarray(masked, dtype=float)
    # the pole is broken (NaN) and no infinity is drawn
    assert np.isnan(values).any()
    assert not np.isinf(values).any()
    plt.close("all")


def test_a_very_long_input_is_refused():
    from aieva.core.safe_parse import parse_text_expression

    with pytest.raises(ParseError):
        parse_text_expression("x + " * 200 + "1")


def test_junk_is_refused():
    from aieva.core.safe_parse import parse_text_expression

    for text in ("__import__('os')", "x.__class__", "1; import os", "x + y +"):
        with pytest.raises(ParseError):
            parse_text_expression(text)


# ---------------------------------------------------------------- the server
def test_a_server_that_does_not_answer_gives_a_clear_error(monkeypatch):
    """The app has to fall back to the manual input."""
    import httpx

    from aieva.core.llm.client import AievaServerClient

    def _timeout(*args, **kwargs):
        raise httpx.ConnectTimeout("the server does not answer")

    monkeypatch.setattr(httpx, "post", _timeout)
    monkeypatch.setattr(httpx, "get", _timeout)

    with pytest.raises(CloudError) as error:
        AievaServerClient(server_url="http://127.0.0.1:9").word_problem("a ball")
    assert "could not be reached" in str(error.value)


def test_a_wrong_key_gives_a_clear_error(monkeypatch):
    import httpx

    from aieva.core.llm.client import AievaServerClient

    def _unauthorized(*args, **kwargs):
        request = httpx.Request("POST", "http://127.0.0.1:8000/api/math/wordproblem")
        response = httpx.Response(401, request=request, json={"detail": "not allowed"})
        raise httpx.HTTPStatusError("401", request=request, response=response)

    monkeypatch.setattr(httpx, "post", _unauthorized)

    with pytest.raises(CloudError):
        AievaServerClient(server_url="http://127.0.0.1:8000").word_problem("a ball")


def test_the_offline_mode_does_not_call_the_server(monkeypatch):
    """In the offline mode the cloud is never used."""
    import httpx

    from aieva.core.llm.client import AievaServerClient

    def _boom(*args, **kwargs):
        raise AssertionError("the server must not be called in the offline mode")

    monkeypatch.setattr(httpx, "post", _boom)
    monkeypatch.setattr(httpx, "get", _boom)
    monkeypatch.setenv("AIEVA_OFFLINE_MODE", "true")

    from aieva.config import get_settings

    get_settings(reload=True)
    try:
        settings = get_settings()
        assert settings.offline_mode is True
        assert settings.cloud_enabled is False
        client = AievaServerClient()
        assert client.server_url  # the client still exists
    finally:
        monkeypatch.setenv("AIEVA_OFFLINE_MODE", "false")
        get_settings(reload=True)
