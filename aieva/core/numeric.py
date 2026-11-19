"""Dependency free numerical helpers.

The application is a Windows program, where SciPy is painful to package.
Everything the maths core needs numerically therefore lives here and SciPy is
only an *optional* accelerator:

* adaptive Simpson and Gauss-Kronrod quadrature (replaces ``scipy.integrate.quad``);
* trapezoid / Simpson rules for sampled data;
* Brent's root finder (replaces ``scipy.optimize.brentq``);
* Ramer-Douglas-Peucker polyline simplification and the shoelace formula
  (used by the "area of a drawn shape" feature).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence


# --------------------------------------------------------------------- quadrature
def adaptive_simpson(
    func: Callable[[float], float],
    a: float,
    b: float,
    tol: float = 1e-10,
    max_depth: int = 24,
) -> float:
    """Integrate ``func`` from ``a`` to ``b`` with the adaptive Simpson rule."""
    if a == b:
        return 0.0
    if b < a:
        return -adaptive_simpson(func, b, a, tol, max_depth)

    fa = func(a)
    fb = func(b)
    midpoint = 0.5 * (a + b)
    fm = func(midpoint)
    whole = (b - a) / 6.0 * (fa + 4.0 * fm + fb)

    def _recurse(
        left: float, right: float, fl: float, fr: float, fmid: float, whole: float, depth: int
    ) -> float:
        mid = 0.5 * (left + right)
        lmid = 0.5 * (left + mid)
        rmid = 0.5 * (mid + right)
        flmid = func(lmid)
        frmid = func(rmid)
        left_part = (mid - left) / 6.0 * (fl + 4.0 * flmid + fmid)
        right_part = (right - mid) / 6.0 * (fmid + 4.0 * frmid + fr)
        if depth <= 0:
            return left_part + right_part
        if abs(left_part + right_part - whole) <= 15.0 * tol:
            return left_part + right_part + (left_part + right_part - whole) / 15.0
        return _recurse(left, mid, fl, fmid, flmid, left_part, depth - 1) + _recurse(
            mid, right, fmid, fr, frmid, right_part, depth - 1
        )

    return _recurse(a, b, fa, fb, fm, whole, max_depth)


#: Nodes and weights of the 15 point Gauss-Kronrod rule (positive half).
_GAUSS_KRONROD_NODES: tuple[float, ...] = (
    0.9914553711208126,
    0.9491079123427585,
    0.8648644233597691,
    0.7415311855993944,
    0.5860872354676911,
    0.4058451513773972,
    0.2077849550078985,
    0.0,
)
_GAUSS_KRONROD_WEIGHTS: tuple[float, ...] = (
    0.02293532201052922,
    0.06309209262997855,
    0.10479001032225018,
    0.14065325971552591,
    0.16900472663926790,
    0.19035057806478541,
    0.20443294007529889,
    0.20948214108472783,
)

#: Nodes and weights of the embedded 7 point Gauss rule (positive half).
_GAUSS7_NODES: tuple[float, ...] = (
    0.9491079123427585,
    0.7415311855993944,
    0.4058451513773972,
    0.0,
)
_GAUSS7_WEIGHTS: tuple[float, ...] = (
    0.1294849661688697,
    0.2797053914892766,
    0.3818300505051189,
    0.4179591836734694,
)


def gauss_kronrod(
    func: Callable[[float], float],
    a: float,
    b: float,
) -> tuple[float, float]:
    """Gauss-Kronrod (G7,K15) quadrature. Returns ``(value, error_estimate)``."""
    if a == b:
        return 0.0, 0.0
    sign = 1.0
    if b < a:
        a, b = b, a
        sign = -1.0
    centre = 0.5 * (a + b)
    half = 0.5 * (b - a)

    total = 0.0
    for index, node in enumerate(_GAUSS_KRONROD_NODES):
        weight = _GAUSS_KRONROD_WEIGHTS[index]
        if node == 0.0:
            total += weight * func(centre)
        else:
            total += weight * (func(centre - half * node) + func(centre + half * node))

    gauss = 0.0
    for index, node in enumerate(_GAUSS7_NODES):
        weight = _GAUSS7_WEIGHTS[index]
        if node == 0.0:
            gauss += weight * func(centre)
        else:
            gauss += weight * (func(centre - half * node) + func(centre + half * node))

    value = total * half
    gauss_value = gauss * half
    error = abs(value - gauss_value)
    return sign * value, error


def quad(
    func: Callable[[float], float],
    a: float,
    b: float,
    tol: float = 1e-10,
) -> tuple[float, float]:
    """Numerically integrate ``func`` from ``a`` to ``b``.

    Returns ``(value, error_estimate)``. Uses SciPy when it is installed and
    falls back to the internal Gauss-Kronrod / adaptive Simpson otherwise.
    """
    try:  # pragma: no cover - depends on the environment
        from scipy.integrate import quad as scipy_quad  # type: ignore import-not-found

        value, error = scipy_quad(func, a, b, epsabs=tol, limit=200)
        return float(value), float(error)
    except Exception:  # noqa: BLE001 - SciPy is optional
        value, error = gauss_kronrod(func, a, b)
        if error > tol:
            value = adaptive_simpson(func, a, b, tol=tol)
            error = abs(value - gauss_kronrod(func, a, b)[0])
        return value, error


# ------------------------------------------------------------- sampled data
def trapezoid(y_values: Sequence[float], x_values: Sequence[float] | None = None) -> float:
    """Trapezoidal rule over sampled data."""
    y = list(y_values)
    if len(y) < 2:
        return 0.0
    if x_values is None:
        x = [float(index) for index in range(len(y))]
    else:
        x = [float(value) for value in x_values]
    total = 0.0
    for index in range(len(y) - 1):
        total += (x[index + 1] - x[index]) * (y[index] + y[index + 1]) / 2.0
    return total


def simpson(y_values: Sequence[float], x_values: Sequence[float] | None = None) -> float:
    """Composite Simpson rule over sampled data (odd number of points)."""
    y = list(y_values)
    if len(y) < 3:
        return trapezoid(y, x_values)
    if x_values is None:
        x = [float(index) for index in range(len(y))]
    else:
        x = [float(value) for value in x_values]
    if len(y) % 2 == 0:  # Simpson needs an even number of intervals
        y = y[:-1]
        x = x[:-1]
    n = len(y) - 1
    h = (x[-1] - x[0]) / n
    total = y[0] + y[-1]
    for index in range(1, n):
        total += y[index] * (4.0 if index % 2 else 2.0)
    return total * h / 3.0


# ------------------------------------------------------------- root finding
def brentq(
    func: Callable[[float], float],
    a: float,
    b: float,
    tol: float = 1e-12,
    max_iterations: int = 100,
) -> float:
    """Brent's method: find a root of ``func`` in ``[a, b]``."""
    fa = func(a)
    fb = func(b)
    if fa == 0.0:
        return a
    if fb == 0.0:
        return b
    if fa * fb > 0:
        raise ValueError("brentq: the interval does not bracket a root")
    if abs(fa) < abs(fb):
        a, b = b, a
        fa, fb = fb, fa
    c, fc = a, fa
    d = e = b - a
    for _ in range(max_iterations):
        if fb * fc > 0:
            c, fc = a, fa
            d = e = b - a
        if abs(fc) < abs(fb):
            a, b, c = b, c, b
            fa, fb, fc = fb, fc, fb
        tol1 = 2.0 * 2.22e-16 * abs(b) + 0.5 * tol
        xm = 0.5 * (c - b)
        if abs(xm) <= tol1 or fb == 0.0:
            return b
        if abs(e) >= tol1 and abs(fa) > abs(fb):
            s = fb / fa
            if a == c:
                p = 2.0 * xm * s
                q = 1.0 - s
            else:
                q = fa / fc
                r = fb / fc
                p = s * (2.0 * xm * q * (q - r) - (b - a) * (r - 1.0))
                q = (q - 1.0) * (r - 1.0) * (s - 1.0)
            if p > 0:
                q = -q
            p = abs(p)
            min1 = 3.0 * xm * q - abs(tol1 * q)
            min2 = abs(e * q)
            if 2.0 * p < min(min1, min2):
                e, d = d, p / q
            else:
                d = xm
                e = d
        else:
            d = xm
            e = d
        a, fa = b, fb
        if abs(d) > tol1:
            b += d
        else:
            b += tol1 if xm > 0 else -tol1
        fb = func(b)
    return b


# ------------------------------------------------------------------- geometry
def ramer_douglas_peucker(
    points: Sequence[tuple[float, float]],
    epsilon: float = 2.0,
) -> list[tuple[float, float]]:
    """Simplify a polyline (Ramer-Douglas-Peucker)."""
    if len(points) < 3:
        return [tuple(point) for point in points]  # type: ignore[misc]

    start = points[0]
    end = points[-1]
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy)
    max_distance = -1.0
    index = 0
    for position, point in enumerate(points):
        x0, y0 = point
        if norm == 0:
            distance = math.hypot(x0 - x1, y0 - y1)
        else:
            distance = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm
        if distance > max_distance:
            index = position
            max_distance = distance
    if max_distance > epsilon:
        left = ramer_douglas_peucker(points[: index + 1], epsilon)
        right = ramer_douglas_peucker(points[index:], epsilon)
        return left[:-1] + right
    return [tuple(start), tuple(end)]  # type: ignore[misc]


def polygon_area(points: Sequence[tuple[float, float]]) -> float:
    """The area of a closed polygon (shoelace formula)."""
    if len(points) < 3:
        return 0.0
    total = 0.0
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def polyline_area(
    points: Sequence[tuple[float, float]],
    baseline: float = 0.0,
) -> float:
    """The area between a polyline and a horizontal baseline."""
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        total += (x2 - x1) * ((y1 - baseline) + (y2 - baseline)) / 2.0
    return abs(total)


def is_scipy_available() -> bool:
    """True when SciPy can be imported (it is optional)."""
    try:  # pragma: no cover - depends on the environment
        import scipy  # type: ignore import-not-found  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


__all__ = [
    "adaptive_simpson",
    "brentq",
    "gauss_kronrod",
    "is_scipy_available",
    "polygon_area",
    "polyline_area",
    "quad",
    "ramer_douglas_peucker",
    "simpson",
    "trapezoid",
]
