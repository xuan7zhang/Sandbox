"""Student-t helpers without scipy (the run venv has none): CDF via the regularized incomplete beta."""
from __future__ import annotations

import math
import statistics as st


def _betacf(a, b, x, itmax=300, eps=3e-14):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = 1e-300 if abs(d) < 1e-300 else d
        c = 1.0 + aa / c; c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = 1e-300 if abs(d) < 1e-300 else d
        c = 1.0 + aa / c; c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d; de = d * c; h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def t_sf2(t, df):
    """Two-sided p-value of |T| >= |t|."""
    return betai(df / 2.0, 0.5, df / (df + t * t))


def t_ppf975(df):
    lo, hi = 0.0, 100.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if t_sf2(mid, df) > 0.05:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def ci95_half(xs):
    return t_ppf975(len(xs) - 1) * st.stdev(xs) / len(xs) ** 0.5


def welch_p(x, y):
    vx, vy = st.variance(x) / len(x), st.variance(y) / len(y)
    if vx + vy == 0:
        return 0.0 if st.mean(x) != st.mean(y) else 1.0
    t = (st.mean(x) - st.mean(y)) / math.sqrt(vx + vy)
    df = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1)) if vx and vy else len(x) + len(y) - 2
    return t_sf2(t, df)
