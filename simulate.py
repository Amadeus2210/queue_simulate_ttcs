import tkinter as tk
from tkinter import ttk, messagebox
import math
import random
import heapq
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

BG_DARK   = "#2b2b2b"
BG_PANEL  = "#3c3f41"
PURPLE    = "#8b44ac"
PURPLE_HV = "#a855c8"
GREEN     = "#2ecc71"
GREEN_HV  = "#27ae60"
RED_BTN   = "#e74c3c"
RED_HV    = "#c0392b"
TEXT      = "#f0f0f0"
BORDER    = "#555555"
LABEL_FG  = "#cccccc"

BTN_FONT   = ("Consolas", 10, "bold")
TITLE_FONT = ("Consolas", 12, "bold")
LBL_FONT   = ("Segoe UI", 10)
ENTRY_FONT = ("Consolas", 10)


# ══════════════════════════════════════════════════════════════════════
#  ANALYTIC METRICS
# ══════════════════════════════════════════════════════════════════════

def metrics_mm1(lam, mu):
    """M/M/1 – classical formulas."""
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=float('inf'), Lq=float('inf'),
                    W=float('inf'), Wq=float('inf'))
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
        return dict(rho=rho, L=float('inf'), Lq=float('inf'),
                    W=float('inf'), Wq=float('inf'))
    sum_term = sum(a**n / math.factorial(n) for n in range(C))
    sum_term += a**C / (math.factorial(C) * (1 - rho))
    P0 = 1 / sum_term
    Cw = (a**C / (math.factorial(C) * (1 - rho))) * P0
    Lq = Cw * rho / (1 - rho)
    Wq = Lq / lam
    W  = Wq + 1 / mu
    L  = lam * W
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_mm1k(lam, mu, K):
    """M/M/1/K – finite capacity."""
    rho = lam / mu
    if abs(rho - 1.0) < 1e-9:
        P0 = 1 / (K + 1)
        L  = K / 2
    else:
        P0 = (1 - rho) / (1 - rho**(K + 1))
        L  = rho * (1 - (K + 1) * rho**K + K * rho**(K + 1)) / \
             ((1 - rho) * (1 - rho**(K + 1)))
    Pk      = P0 * rho**K
    lam_eff = lam * (1 - Pk)
    W       = L / lam_eff if lam_eff > 0 else float('inf')
    Wq      = W - 1 / mu
    Lq      = lam_eff * Wq
    return dict(rho=rho, L=L, Lq=max(0, Lq), W=W, Wq=max(0, Wq))


def metrics_mg1(lam, mu, sigma):
    """M/G/1 – Pollaczek–Khinchine formula.
    sigma = std dev của service time (người dùng nhập).
    """
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=float('inf'), Lq=float('inf'),
                    W=float('inf'), Wq=float('inf'))
    ES  = 1.0 / mu
    ES2 = sigma**2 + ES**2          # E[S²] = Var[S] + (E[S])²
    Lq  = lam**2 * ES2 / (2 * (1 - rho))
    Wq  = Lq / lam
    W   = Wq + ES
    L   = lam * W
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_md1(lam, mu):
    """M/D/1 – Deterministic service time (special case of M/G/1, σ=0)."""
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=float('inf'), Lq=float('inf'),
                    W=float('inf'), Wq=float('inf'))
    # P-K formula with σ=0  →  E[S²] = (1/μ)²
    ES  = 1.0 / mu
    ES2 = ES**2                     # σ=0, so E[S²] = E[S]²
    Lq  = lam**2 * ES2 / (2 * (1 - rho))
    Wq  = Lq / lam
    W   = Wq + ES
    L   = lam * W
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def compute_metrics(model, lam, mu, K=None, C=None, sigma=None):
    try:
        if model == "M/M/1":
            return metrics_mm1(lam, mu)
        elif model == "M/M/C":
            return metrics_mmc(lam, mu, C)
        elif model == "M/M/1/K":
            return metrics_mm1k(lam, mu, K)
        elif model == "M/G/1":
            s = sigma if sigma is not None else 1.0 / mu
            return metrics_mg1(lam, mu, s)
        elif model == "M/D/1":
            return metrics_md1(lam, mu)
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════
#  SIMULATION HELPERS
# ══════════════════════════════════════════════════════════════════════

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
#  MODEL 1: M/M/1
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
#  MODEL 2: M/M/C
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
            # free the server whose finish time is closest to t
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
#  MODEL 3: M/M/1/K
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
#  MODEL 4: M/G/1
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
        """Sample service time ~ Normal(1/μ, σ), truncated at 0."""
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
#  MODEL 5: M/D/1
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


# ══════════════════════════════════════════════════════════════════════
#  PLOT WINDOW  (6 subplots, same layout as original)
# ══════════════════════════════════════════════════════════════════════

class PlotWindow(tk.Toplevel):
    def __init__(self, parent, model_name, results):
        super().__init__(parent)
        self.title(f"{model_name}  –  Simulation Plots")
        self.configure(bg=BG_DARK)
        self.resizable(True, True)
        self.results = results
        self._build(model_name)

    def _build(self, model_name):
        hdr = tk.Label(self,
                       text=f"  {model_name}  –  Simulation Results  ",
                       bg=PURPLE, fg=TEXT, font=TITLE_FONT, pady=6)
        hdr.pack(fill="x")

        r     = self.results
        waits = [w for w in r["waiting_sys"] if w is not None]

        plots = [
            ("Entities in System",      "Time",       "# Entities",
             r["times"][:len(r["entities_sys"])],
             r["entities_sys"],
             PURPLE, True),

            ("Waiting in Queue",        "Time",       "# Waiting",
             r["times"][:len(r["waiting_q"])],
             r["waiting_q"],
             "#3498db", True),

            ("Waiting Time per Customer", "Customer #", "Wait (time units)",
             list(range(len(waits))),
             waits,
             "#e67e22", False),

            ("Departure Times",         "Customer #", "Departure Time",
             list(range(len(r["departure_times"]))),
             r["departure_times"],
             GREEN, False),

            ("Balking (Cumulative)",    "Time",       "Customers Balked",
             r["times"][:len(r["balking"])],
             r["balking"],
             RED_BTN, True),

            ("Arrival Times",           "Customer #", "Arrival Time",
             list(range(len(r["arrival_times"]))),
             r["arrival_times"],
             "#1abc9c", False),
        ]

        fig, axes = plt.subplots(3, 2, figsize=(12, 9))
        fig.patch.set_facecolor("#1e1e1e")

        for ax, (title, xlabel, ylabel, x, y, color, step) in zip(axes.flat, plots):
            ax.set_facecolor("#252526")
            ax.tick_params(colors=TEXT, labelsize=8)
            ax.xaxis.label.set_color(TEXT)
            ax.yaxis.label.set_color(TEXT)
            ax.title.set_color(PURPLE_HV)
            for spine in ax.spines.values():
                spine.set_edgecolor(BORDER)

            if len(x) == 0 or len(y) == 0:
                ax.text(0.5, 0.5, "No data", transform=ax.transAxes,
                        ha="center", va="center", color="#888888")
            elif step:
                ax.step(x, y, where="post", color=color, linewidth=1.6)
                ax.fill_between(x, y, step="post", color=color, alpha=0.15)
            else:
                ax.plot(x, y, "o", color=color, markersize=3, alpha=0.75)

            ax.set_xlabel(xlabel, fontsize=8)
            ax.set_ylabel(ylabel, fontsize=8)
            ax.set_title(title, fontsize=9, pad=6, fontweight="bold")

        fig.tight_layout(pad=2.0)

        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)


# ══════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════

class QueueApp(tk.Tk):
    MODELS = ["M/M/1", "M/M/C", "M/M/1/K", "M/G/1", "M/D/1"]

    # Fields active for each model
    _ACTIVE = {
        "M/M/1":   {"lam", "mu"},
        "M/M/C":   {"lam", "mu", "C"},
        "M/M/1/K": {"lam", "mu", "K"},
        "M/G/1":   {"lam", "mu", "sigma"},
        "M/D/1":   {"lam", "mu"},
    }

    def __init__(self):
        super().__init__()
        self.title("Queueing ModelSim")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self._selected_model = tk.StringVar(value="M/M/1")
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────
    def _build_ui(self):
        title_bar = tk.Frame(self, bg="#1a1a2e", height=32)
        title_bar.pack(fill="x")
        tk.Label(title_bar, text="  ⬡  Queueing ModelSim",
                 bg="#1a1a2e", fg=PURPLE, font=TITLE_FONT
                 ).pack(side="left", pady=4)

        outer = tk.Frame(self, bg=BG_DARK, padx=10, pady=10)
        outer.pack(fill="both", expand=True)

        # ── Models panel ──────────────────────────────────────────────
        mdl_frame = tk.LabelFrame(outer, text=" Models ",
                                  bg=BG_PANEL, fg=PURPLE, font=BTN_FONT,
                                  bd=2, relief="groove", padx=10, pady=10)
        mdl_frame.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ns")

        for m in self.MODELS:
            tk.Radiobutton(mdl_frame, text=m,
                           variable=self._selected_model, value=m,
                           indicatoron=False,
                           bg=PURPLE, fg=TEXT,
                           selectcolor=PURPLE_HV,
                           activebackground=PURPLE_HV,
                           font=BTN_FONT, width=10,
                           relief="flat", bd=0, pady=8,
                           cursor="hand2",
                           command=self._on_model_change
                           ).pack(fill="x", pady=4)

        # ── Inputs panel ──────────────────────────────────────────────
        inp_frame = tk.LabelFrame(outer, text=" Inputs ",
                                  bg=BG_PANEL, fg=PURPLE, font=BTN_FONT,
                                  bd=2, relief="groove", padx=16, pady=12)
        inp_frame.grid(row=0, column=1, sticky="nsew")

        # lam, mu, K, C, sigma
        fields = [
            ("Arrival rate (λ):",        "lam",   "2"),
            ("Service rate (μ):",        "mu",    "3"),
            ("Queue Capacity (K):",      "K",     "10"),
            ("Servers (C):",             "C",     "2"),
            ("Std-dev of svc time (σ):", "sigma", ""),
        ]

        self._entries = {}
        self._labels  = {}
        for i, (label, key, default) in enumerate(fields):
            lbl = tk.Label(inp_frame, text=label, bg=BG_PANEL, fg=LABEL_FG,
                           font=LBL_FONT, anchor="w")
            lbl.grid(row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            self._labels[key] = lbl

            e = tk.Entry(inp_frame, font=ENTRY_FONT, width=12,
                         bg="#1e1e1e", fg=TEXT, insertbackground=TEXT,
                         relief="flat", bd=4,
                         highlightthickness=1, highlightcolor=PURPLE,
                         highlightbackground=BORDER)
            e.insert(0, default)
            e.grid(row=i, column=1, sticky="ew", pady=5)
            self._entries[key] = e

        inp_frame.grid_columnconfigure(1, weight=1)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = tk.Frame(inp_frame, bg=BG_PANEL)
        btn_row.grid(row=len(fields), column=0, columnspan=2,
                     pady=(16, 0), sticky="ew")

        tk.Button(btn_row, text="✕  Quit",
                  command=self.destroy,
                  bg=RED_BTN, fg=TEXT, font=BTN_FONT,
                  activebackground=RED_HV, activeforeground=TEXT,
                  relief="flat", bd=0, padx=20, pady=10,
                  cursor="hand2"
                  ).pack(side="left", expand=True, fill="x", padx=(0, 8))

        tk.Button(btn_row, text="▶  Calculate",
                  command=self._calculate,
                  bg=GREEN, fg=TEXT, font=BTN_FONT,
                  activebackground=GREEN_HV, activeforeground=TEXT,
                  relief="flat", bd=0, padx=20, pady=10,
                  cursor="hand2"
                  ).pack(side="left", expand=True, fill="x")

        # ── Performance Metrics panel ─────────────────────────────────
        res_frame = tk.LabelFrame(outer, text=" Performance Metrics ",
                                  bg=BG_PANEL, fg=PURPLE, font=BTN_FONT,
                                  bd=2, relief="groove", padx=16, pady=10)
        res_frame.grid(row=1, column=0, columnspan=2,
                       pady=(10, 0), sticky="ew")
        outer.grid_columnconfigure(1, weight=1)

        metric_defs = [
            ("ρ",  "Utilisation",              "rho"),
            ("L",  "Avg. customers in system", "L"),
            ("Lq", "Avg. customers in queue",  "Lq"),
            ("W",  "Avg. time in system",      "W"),
            ("Wq", "Avg. waiting time",        "Wq"),
        ]

        self._metric_vars = {}
        for col, (sym, desc, key) in enumerate(metric_defs):
            cell = tk.Frame(res_frame, bg=BG_PANEL)
            cell.grid(row=0, column=col, padx=10, pady=4, sticky="ew")
            res_frame.grid_columnconfigure(col, weight=1)

            tk.Label(cell, text=sym, bg=BG_PANEL, fg=PURPLE,
                     font=("Consolas", 13, "bold")).pack()
            tk.Label(cell, text=desc, bg=BG_PANEL, fg="#888888",
                     font=("Segoe UI", 8)).pack()

            var = tk.StringVar(value="—")
            tk.Label(cell, textvariable=var, bg="#1e1e1e", fg=GREEN,
                     font=("Consolas", 11, "bold"),
                     width=10, relief="flat", pady=4
                     ).pack(fill="x", pady=(4, 0))
            self._metric_vars[key] = var

        self._on_model_change()

    # ── model change → hide/show fields ──────────────────────────────
    def _on_model_change(self):
        model  = self._selected_model.get()
        active = self._ACTIVE.get(model, {"lam", "mu"})

        for key, entry in self._entries.items():
            lbl = self._labels[key]
            if key in active:
                lbl.grid()
                entry.grid()
                entry.config(state="normal")
            else:
                entry.config(state="normal")
                entry.delete(0, "end")
                entry.grid_remove()
                lbl.grid_remove()

        if hasattr(self, "_metric_vars"):
            for var in self._metric_vars.values():
                var.set("—")

    # ── parse helpers ─────────────────────────────────────────────────
    def _pf(self, key, default=None):
        try:
            s = self._entries[key].get().strip()
            if "/" in s:
                a, b = s.split("/")
                return float(a) / float(b)
            return float(s)
        except Exception:
            return default

    def _pi(self, key, default=None):
        try:
            return int(self._entries[key].get().strip())
        except Exception:
            return default

    # ── calculate ────────────────────────────────────────────────────
    def _calculate(self):
        model = self._selected_model.get()
        lam   = self._pf("lam")
        mu    = self._pf("mu")

        if lam is None or lam <= 0:
            messagebox.showerror("Input Error", "Invalid Arrival rate (λ)"); return
        if mu is None or mu <= 0:
            messagebox.showerror("Input Error", "Invalid Service rate (μ)"); return

        try:
            if model == "M/M/1":
                results = mm1_simulate(lam, mu)

            elif model == "M/M/C":
                C = self._pi("C")
                if C is None or C < 1:
                    messagebox.showerror("Input Error", "Servers C phải ≥ 1"); return
                results = mmc_simulate(lam, mu, C)

            elif model == "M/M/1/K":
                K = self._pi("K")
                if K is None or K < 1:
                    messagebox.showerror("Input Error", "Capacity K phải ≥ 1"); return
                results = mm1k_simulate(lam, mu, K)

            elif model == "M/G/1":
                sigma = self._pf("sigma")
                if sigma is None or sigma < 0:
                    messagebox.showerror("Input Error",
                                         "Std-dev σ phải ≥ 0\n(σ=0 → M/D/1)"); return
                results = mg1_simulate(lam, mu, sigma)

            elif model == "M/D/1":
                results = md1_simulate(lam, mu)

            else:
                messagebox.showerror("Error", "Unknown model"); return

        except Exception as ex:
            messagebox.showerror("Simulation Error", str(ex)); return

        # show plots
        PlotWindow(self, model, results)

        # analytic metrics
        sigma_val = self._pf("sigma", None)
        m = compute_metrics(model, lam, mu,
                            K=self._pi("K"),
                            C=self._pi("C"),
                            sigma=sigma_val)
        if m:
            for key, var in self._metric_vars.items():
                val = m.get(key)
                if val is None:
                    var.set("—")
                elif math.isinf(val):
                    var.set("∞")
                else:
                    var.set(f"{val:.4f}")
        else:
            for var in self._metric_vars.values():
                var.set("N/A")


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QueueApp()
    app.mainloop()