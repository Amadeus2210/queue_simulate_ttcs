"""
live_engine.py – Real-time queue engine with time-series recording.
"""
import random
import threading
import time


class Customer:
    _id = 0

    def __init__(self, arrival):
        Customer._id += 1
        self.id      = Customer._id
        self.arrival = arrival
        self.start   = None
        self.finish  = None


class QueueEngine:
    # Seconds between each recorded data point
    RECORD_INTERVAL = 0.5

    def __init__(self, model, mu, C=1, K=999, sigma=None):
        self.model  = model
        self.mu     = mu
        self.C      = C
        self.K      = K
        self.sigma  = sigma if sigma is not None else 1 / mu

        self.lock        = threading.Lock()
        self.queue       = []
        self.servers     = [None] * C
        self.server_free = [0.0] * C

        self._running = False
        self._thread  = None

        self.total_arrived = 0
        self.total_served  = 0
        self.total_balked  = 0
        self.sum_W         = 0.0
        self.sum_Wq        = 0.0

        self.area_system = 0.0
        self.area_queue  = 0.0
        self.busy_time   = 0.0

        self.last_event_time = time.time()
        self.start_time      = self.last_event_time

        # time-series storage: (elapsed, rho, L, Lq, W, Wq)
        self.ts_time = []
        self.ts_rho  = []
        self.ts_L    = []
        self.ts_Lq   = []
        self.ts_W    = []
        self.ts_Wq   = []
        self._next_record = self.start_time + self.RECORD_INTERVAL

    # ── internal helpers ──────────────────────────────────────────────

    def _service_time(self):
        if self.model in ("M/M/1", "M/M/C", "M/M/1/K"):
            return random.expovariate(self.mu)
        else:
            ES = 1 / self.mu
            return max(0.001, random.gauss(ES, self.sigma))

    def _assign(self, c, now):
        for i, srv in enumerate(self.servers):
            if srv is None:
                c.start          = now
                svc              = self._service_time()
                c.finish         = now + svc
                self.servers[i]     = c
                self.server_free[i] = c.finish
                return True
        return False

    def _update_time_avg_stats(self, now):
        dt  = now - self.last_event_time
        n_q = len(self.queue)
        n_s = sum(1 for s in self.servers if s is not None)
        self.area_system += (n_q + n_s) * dt
        self.area_queue  += n_q * dt
        self.busy_time   += n_s * dt
        self.last_event_time = now

    def _record_snapshot(self, now):
        """Append one data point to the time-series arrays (call while holding lock)."""
        elapsed = max(0.001, now - self.start_time)
        rho_emp = self.busy_time / (elapsed * self.C)
        L_emp   = self.area_system / elapsed
        Lq_emp  = self.area_queue  / elapsed
        n       = self.total_served
        W_emp   = self.sum_W  / n if n > 0 else 0.0
        Wq_emp  = self.sum_Wq / n if n > 0 else 0.0

        self.ts_time.append(elapsed)
        self.ts_rho.append(min(rho_emp, 2.0))   # cap display at 2
        self.ts_L.append(L_emp)
        self.ts_Lq.append(Lq_emp)
        self.ts_W.append(W_emp)
        self.ts_Wq.append(Wq_emp)

    # ── public API ────────────────────────────────────────────────────

    def add_customer(self):
        now = time.time()
        with self.lock:
            self._update_time_avg_stats(now)
            in_sys = len(self.queue) + sum(1 for s in self.servers if s is not None)
            if in_sys >= self.K:
                self.total_balked += 1
                return None, "balked"
            c = Customer(now)
            self.total_arrived += 1
            if self._assign(c, now):
                return c, "served"
            self.queue.append(c)
            return c, "queued"

    def _tick(self):
        while self._running:
            now = time.time()
            with self.lock:
                self._update_time_avg_stats(now)
                for i, c in enumerate(self.servers):
                    if c is not None and now >= c.finish:
                        self.total_served += 1
                        self.sum_W  += c.finish - c.arrival
                        self.sum_Wq += c.start  - c.arrival
                        self.servers[i] = None
                        if self.queue:
                            nxt        = self.queue.pop(0)
                            nxt.start  = now
                            svc        = self._service_time()
                            nxt.finish = now + svc
                            self.servers[i]     = nxt
                            self.server_free[i] = nxt.finish
                if now >= self._next_record:
                    self._record_snapshot(now)
                    self._next_record = now + self.RECORD_INTERVAL
            time.sleep(0.05)

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._tick, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def snapshot(self):
        now = time.time()
        with self.lock:
            q_snap = list(self.queue)
            s_snap = list(self.servers)
            n_q    = len(q_snap)
            n_s    = sum(1 for s in s_snap if s is not None)
            n_sys  = n_q + n_s
            n      = self.total_served
            W_emp  = self.sum_W  / n if n > 0 else 0
            Wq_emp = self.sum_Wq / n if n > 0 else 0
            elapsed = max(0.001, now - self.start_time)
            L_emp   = self.area_system / elapsed
            Lq_emp  = self.area_queue  / elapsed
            rho_emp = self.busy_time   / (elapsed * self.C)
            finish_times = [max(0, c.finish - now) for c in s_snap if c is not None]
            if n_s < self.C:
                exp_wait = 0.0
            else:
                sorted_free = sorted(self.server_free)
                exp_wait = max(0, sorted_free[0] - now) + \
                           len(q_snap) * (1 / self.mu)
            return {
                "now":          now,
                "queue":        q_snap,
                "servers":      s_snap,
                "n_queue":      n_q,
                "n_servers":    n_s,
                "n_system":     n_sys,
                "total_arr":    self.total_arrived,
                "total_svc":    self.total_served,
                "total_balk":   self.total_balked,
                "W_emp":        W_emp,
                "Wq_emp":       Wq_emp,
                "L_emp":        L_emp,
                "Lq_emp":       Lq_emp,
                "finish_times": finish_times,
                "exp_wait":     exp_wait,
                "rho_emp":      rho_emp,
                # time-series copies
                "ts_time": list(self.ts_time),
                "ts_rho":  list(self.ts_rho),
                "ts_L":    list(self.ts_L),
                "ts_Lq":   list(self.ts_Lq),
                "ts_W":    list(self.ts_W),
                "ts_Wq":   list(self.ts_Wq),
            }
