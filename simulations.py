"""
simulations.py – Discrete-event simulation functions for each queueing model.
Each function returns a results dict with time-series data.
"""
import random
import heapq

ARRIVAL   = 0
DEPARTURE = 1


def _init_results():
    return {
        "times":           [0.0],
        "entities_sys":    [0],
        "waiting_q":       [0],
        "waiting_sys":     [],
        "departure_times": [],
        "arrival_times":   [],
        "balking":         [0],
    }


def _snapshot(res, t, in_system, n_in_queue, total_balk):
    res["times"].append(t)
    res["entities_sys"].append(in_system)
    res["waiting_q"].append(n_in_queue)
    res["balking"].append(total_balk)


# ══════════════════════════════════════════════════════════════════════
#  M/M/1
# ══════════════════════════════════════════════════════════════════════

def mm1_simulate(lam, mu, n_events=100):
    """M/M/1: Poisson arrivals, Exponential service, 1 server, ∞ capacity."""
    res         = _init_results()
    in_system   = 0
    server_busy = False
    queue       = []
    heap        = []
    eid         = [0]
    dep_count   = [0]

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    schedule(random.expovariate(lam), ARRIVAL)

    while heap and dep_count[0] < n_events:
        t, etype, _ = heapq.heappop(heap)
        _snapshot(res, t, in_system,
                  max(0, in_system - (1 if server_busy else 0)), 0)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)
            in_system += 1
            if not server_busy:
                server_busy = True
                res["waiting_sys"].append(0.0)
                schedule(t + random.expovariate(mu), DEPARTURE)
            else:
                queue.append(t)
            schedule(t + random.expovariate(lam), ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            dep_count[0] += 1
            in_system -= 1
            if queue:
                arrive_t = queue.pop(0)
                res["waiting_sys"].append(t - arrive_t)
                schedule(t + random.expovariate(mu), DEPARTURE)
            else:
                server_busy = False

    return res


# ══════════════════════════════════════════════════════════════════════
#  M/M/C
# ══════════════════════════════════════════════════════════════════════

def mmc_simulate(lam, mu, C, n_events=100):
    """M/M/C: Poisson arrivals, Exponential service, C servers, ∞ capacity."""
    res       = _init_results()
    in_system = 0
    servers   = [0.0] * C   # each entry = time server becomes free
    queue     = []
    heap      = []
    eid       = [0]
    dep_count = [0]

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    def n_busy(t):
        return sum(1 for s in servers if s > t)

    schedule(random.expovariate(lam), ARRIVAL)

    while heap and dep_count[0] < n_events:
        t, etype, _ = heapq.heappop(heap)
        busy_now = n_busy(t)
        _snapshot(res, t, in_system, max(0, in_system - busy_now), 0)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)
            in_system += 1
            earliest_free = min(servers)
            if earliest_free <= t:
                idx = servers.index(earliest_free)
                res["waiting_sys"].append(0.0)
                svc_end = t + random.expovariate(mu)
                servers[idx] = svc_end
                schedule(svc_end, DEPARTURE)
            else:
                queue.append(t)
            schedule(t + random.expovariate(lam), ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            dep_count[0] += 1
            in_system -= 1
            idx = min(range(C), key=lambda i: abs(servers[i] - t))
            servers[idx] = t
            if queue:
                arrive_t = queue.pop(0)
                res["waiting_sys"].append(t - arrive_t)
                svc_end = t + random.expovariate(mu)
                servers[idx] = svc_end
                schedule(svc_end, DEPARTURE)

    return res


# ══════════════════════════════════════════════════════════════════════
#  M/M/1/K
# ══════════════════════════════════════════════════════════════════════

def mm1k_simulate(lam, mu, K, n_events=100):
    """M/M/1/K: Poisson arrivals, Exponential service, 1 server, capacity K."""
    res         = _init_results()
    in_system   = 0
    server_busy = False
    queue       = []
    total_balk  = 0
    heap        = []
    eid         = [0]
    dep_count   = [0]

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    schedule(random.expovariate(lam), ARRIVAL)

    while heap and dep_count[0] < n_events:
        t, etype, _ = heapq.heappop(heap)
        _snapshot(res, t, in_system,
                  max(0, in_system - (1 if server_busy else 0)), total_balk)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)
            if in_system < K:
                in_system += 1
                if not server_busy:
                    server_busy = True
                    res["waiting_sys"].append(0.0)
                    schedule(t + random.expovariate(mu), DEPARTURE)
                else:
                    queue.append(t)
            else:
                total_balk += 1
            schedule(t + random.expovariate(lam), ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            dep_count[0] += 1
            in_system -= 1
            if queue:
                arrive_t = queue.pop(0)
                res["waiting_sys"].append(t - arrive_t)
                schedule(t + random.expovariate(mu), DEPARTURE)
            else:
                server_busy = False

    return res


# ══════════════════════════════════════════════════════════════════════
#  M/G/1
# ══════════════════════════════════════════════════════════════════════

def mg1_simulate(lam, mu, sigma, n_events=100):
    """M/G/1: Poisson arrivals, General (Normal truncated) service, 1 server.
    mu    = mean service rate  → mean service time = 1/mu
    sigma = std dev of service time
    """
    res         = _init_results()
    in_system   = 0
    server_busy = False
    queue       = []
    heap        = []
    eid         = [0]
    dep_count   = [0]

    def svc_time():
        return max(1e-9, random.gauss(1.0 / mu, sigma))

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    schedule(random.expovariate(lam), ARRIVAL)

    while heap and dep_count[0] < n_events:
        t, etype, _ = heapq.heappop(heap)
        _snapshot(res, t, in_system,
                  max(0, in_system - (1 if server_busy else 0)), 0)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)
            in_system += 1
            if not server_busy:
                server_busy = True
                res["waiting_sys"].append(0.0)
                schedule(t + svc_time(), DEPARTURE)
            else:
                queue.append(t)
            schedule(t + random.expovariate(lam), ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            dep_count[0] += 1
            in_system -= 1
            if queue:
                arrive_t = queue.pop(0)
                res["waiting_sys"].append(t - arrive_t)
                schedule(t + svc_time(), DEPARTURE)
            else:
                server_busy = False

    return res


# ══════════════════════════════════════════════════════════════════════
#  M/D/1
# ══════════════════════════════════════════════════════════════════════

def md1_simulate(lam, mu, n_events=100):
    """M/D/1: Poisson arrivals, Deterministic service time = 1/μ, 1 server."""
    res         = _init_results()
    in_system   = 0
    server_busy = False
    queue       = []
    heap        = []
    eid         = [0]
    dep_count   = [0]
    svc_time    = 1.0 / mu          # constant

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    schedule(random.expovariate(lam), ARRIVAL)

    while heap and dep_count[0] < n_events:
        t, etype, _ = heapq.heappop(heap)
        _snapshot(res, t, in_system,
                  max(0, in_system - (1 if server_busy else 0)), 0)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)
            in_system += 1
            if not server_busy:
                server_busy = True
                res["waiting_sys"].append(0.0)
                schedule(t + svc_time, DEPARTURE)
            else:
                queue.append(t)
            schedule(t + random.expovariate(lam), ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            dep_count[0] += 1
            in_system -= 1
            if queue:
                arrive_t = queue.pop(0)
                res["waiting_sys"].append(t - arrive_t)
                schedule(t + svc_time, DEPARTURE)
            else:
                server_busy = False

    return res
