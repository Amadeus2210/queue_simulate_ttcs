"""
metrics.py – Analytic queueing-theory formulas.
All functions return a dict with keys: rho, L, Lq, W, Wq.
"""
import math


def metrics_mm1(lam, mu):
    """M/M/1 – classical formulas."""
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=math.inf, Lq=math.inf, W=math.inf, Wq=math.inf)
    L  = rho / (1 - rho)
    Lq = rho**2 / (1 - rho)
    W  = 1 / (mu - lam)
    Wq = lam / (mu * (mu - lam))
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_mmc(lam, mu, C):
    """M/M/C – Erlang-C formulas."""
    rho = lam / (C * mu)
    a   = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=math.inf, Lq=math.inf, W=math.inf, Wq=math.inf)
    s   = sum(a**n / math.factorial(n) for n in range(C))
    s  += a**C / (math.factorial(C) * (1 - rho))
    P0  = 1 / s
    Cw  = (a**C / (math.factorial(C) * (1 - rho))) * P0
    Lq  = Cw * rho / (1 - rho)
    Wq  = Lq / lam
    W   = Wq + 1 / mu
    L   = lam * W
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_mg1(lam, mu, sigma):
    """M/G/1 – Pollaczek–Khinchine formula.
    sigma = std dev of service time.
    """
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=math.inf, Lq=math.inf, W=math.inf, Wq=math.inf)
    ES  = 1.0 / mu
    ES2 = sigma**2 + ES**2          # E[S²] = Var[S] + (E[S])²
    Lq  = lam**2 * ES2 / (2 * (1 - rho))
    Wq  = Lq / lam
    W   = Wq + ES
    L   = lam * W
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_mgc(lam, mu, C, sigma):
    """M/G/C – approximation via M/M/C + CV² adjustment."""
    base = metrics_mmc(lam, mu, C)
    if math.isinf(base["Lq"]):
        return base
    ES  = 1 / mu
    CV2 = (sigma * mu)**2
    Lq  = base["Lq"] * (1 + CV2) / 2
    Wq  = Lq / lam
    W   = Wq + ES
    L   = lam * W
    rho = lam / (C * mu)
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_md1(lam, mu):
    """M/D/1 – Deterministic service (special case of M/G/1, σ=0)."""
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=math.inf, Lq=math.inf, W=math.inf, Wq=math.inf)
    ES  = 1.0 / mu
    ES2 = ES**2                     # σ=0, so E[S²] = E[S]²
    Lq  = lam**2 * ES2 / (2 * (1 - rho))
    Wq  = Lq / lam
    W   = Wq + ES
    L   = lam * W
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_mm1k(lam, mu, K):
    """M/M/1/K – finite capacity."""
    rho = lam / mu
    if abs(rho - 1.0) < 1e-9:
        P0 = 1 / (K + 1)
        L  = K / 2
    else:
        P0 = (1 - rho) / (1 - rho**(K + 1))
        L  = rho * (1 - (K + 1) * rho**K + K * rho**(K + 1)) \
             / ((1 - rho) * (1 - rho**(K + 1)))
    Pk      = P0 * rho**K
    lam_eff = lam * (1 - Pk)
    W       = L / lam_eff if lam_eff > 0 else math.inf
    Wq      = W - 1 / mu
    Lq      = lam_eff * Wq
    return dict(rho=rho, L=L, Lq=max(0, Lq), W=W, Wq=max(0, Wq))


def compute_metrics(model, lam, mu, C=1, K=10, sigma=None):
    """Dispatch to the correct analytic formula by model name."""
    try:
        if sigma is None:
            sigma = 1 / mu
        if model == "M/M/1":
            return metrics_mm1(lam, mu)
        elif model == "M/M/C":
            return metrics_mmc(lam, mu, C)
        elif model == "M/G/1":
            return metrics_mg1(lam, mu, sigma)
        elif model == "M/G/C":
            return metrics_mgc(lam, mu, C, sigma)
        elif model == "M/M/1/K":
            return metrics_mm1k(lam, mu, K)
        elif model == "M/D/1":
            return metrics_md1(lam, mu)
    except Exception:
        pass
    return None
