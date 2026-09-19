"""
Pure-Python p-value / tail-probability functions (no scipy/numpy dependency).

Used by the statcheck forensic pass to recompute p-values from reported test
statistics. Implementations are the standard Numerical-Recipes incomplete-beta /
incomplete-gamma routines; validated against known values in
test_forensic_checks.py to ~4 decimal places.

All functions return two-sided tail probabilities unless noted.
"""
import math

_EPS = 3.0e-12
_FPMIN = 1.0e-300
_MAXIT = 400


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _FPMIN:
        d = _FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, _MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < _EPS:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _gser(a: float, x: float) -> float:
    """Incomplete gamma P(a, x) via series representation."""
    gln = math.lgamma(a)
    ap = a
    s = 1.0 / a
    d = s
    for _ in range(_MAXIT):
        ap += 1.0
        d *= x / ap
        s += d
        if abs(d) < abs(s) * _EPS:
            break
    return s * math.exp(-x + a * math.log(x) - gln)


def _gcf(a: float, x: float) -> float:
    """Incomplete gamma Q(a, x) via continued fraction."""
    gln = math.lgamma(a)
    b = x + 1.0 - a
    c = 1.0 / _FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, _MAXIT):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = b + an / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < _EPS:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def gammq(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) = 1 - P(a, x)."""
    if x < 0.0 or a <= 0.0:
        return float("nan")
    if x == 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gser(a, x)
    return _gcf(a, x)


# ── Two-sided tail probabilities ───────────────────────────────────────────

def norm_p_two(z: float) -> float:
    """Two-sided p for a standard normal / z statistic."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def t_p_two(t: float, df: float) -> float:
    """Two-sided p for Student's t: P(|T| > |t|)."""
    if df <= 0:
        return float("nan")
    t = abs(t)
    return betai(df / 2.0, 0.5, df / (df + t * t))


def f_p(f: float, df1: float, df2: float) -> float:
    """Upper-tail p for an F statistic: P(F_{df1,df2} > f). (F tests are one-tailed.)"""
    if df1 <= 0 or df2 <= 0 or f < 0:
        return float("nan")
    return betai(df2 / 2.0, df1 / 2.0, df2 / (df2 + df1 * f))


def chi2_p(x: float, df: float) -> float:
    """Upper-tail p for a chi-square statistic: P(X^2_df > x). (One-tailed.)"""
    if df <= 0 or x < 0:
        return float("nan")
    return gammq(df / 2.0, x / 2.0)


def r_p_two(r: float, df: float) -> float:
    """Two-sided p for a Pearson correlation with df = n - 2."""
    if df <= 0 or abs(r) >= 1.0:
        return float("nan") if abs(r) > 1.0 else 0.0
    t = r * math.sqrt(df / (1.0 - r * r))
    return t_p_two(t, df)
