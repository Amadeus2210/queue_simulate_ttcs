"""
Queueing ModelSim  –  Live Interactive Simulator
Models: M/M/1  |  M/M/C  |  M/G/1  |  M/G/C  |  M/M/1/K
"""

import tkinter as tk
from tkinter import messagebox
import math
import random
import time
import threading

# ─────────────────────────── palette ──────────────────────────────────
BG        = "#1a1a2e"
PANEL     = "#16213e"
CARD      = "#0f3460"
PURPLE    = "#9b59b6"
PURPLE_HV = "#bb76d6"
CYAN      = "#00d4ff"
GREEN     = "#2ecc71"
GREEN_HV  = "#27ae60"
YELLOW    = "#f1c40f"
RED       = "#e74c3c"
RED_HV    = "#c0392b"
ORANGE    = "#e67e22"
TEXT      = "#ecf0f1"
MUTED     = "#7f8c8d"
BORDER    = "#2c3e50"

F_TITLE  = ("Consolas", 13, "bold")
F_HEAD   = ("Consolas", 10, "bold")
F_BODY   = ("Segoe UI", 9)
F_MONO   = ("Consolas", 10)
F_BIG    = ("Consolas", 16, "bold")
F_SMALL  = ("Segoe UI", 8)


# ══════════════════════════════════════════════════════════════════════
#  ANALYTIC METRICS
# ══════════════════════════════════════════════════════════════════════

def metrics_mm1(lam, mu):
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=math.inf, Lq=math.inf, W=math.inf, Wq=math.inf)
    L  = rho / (1 - rho)
    Lq = rho**2 / (1 - rho)
    W  = 1 / (mu - lam)
    Wq = lam / (mu * (mu - lam))
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_mmc(lam, mu, C):
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
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=math.inf, Lq=math.inf, W=math.inf, Wq=math.inf)
    ES  = 1 / mu
    ES2 = sigma**2 + ES**2
    Lq  = lam**2 * ES2 / (2 * (1 - rho))
    Wq  = Lq / lam
    W   = Wq + ES
    L   = lam * W
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_mgc(lam, mu, C, sigma):
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


def metrics_mm1k(lam, mu, K):
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
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════
#  LIVE QUEUE ENGINE
# ══════════════════════════════════════════════════════════════════════

class Customer:
    _id = 0
    def __init__(self, arrival):
        Customer._id += 1
        self.id      = Customer._id
        self.arrival = arrival
        self.start   = None
        self.finish  = None


class QueueEngine:
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

        self._running   = False
        self._thread    = None
        self._next_auto = 0.0

        self.total_arrived = 0
        self.total_served  = 0
        self.total_balked  = 0
        self.sum_W         = 0.0
        self.sum_Wq        = 0.0

        self.area_system   = 0.0
        self.area_queue    = 0.0
        self.busy_time     = 0.0

        self.last_event_time = time.time()
        self.start_time      = self.last_event_time

    def _service_time(self):
        if self.model in ("M/M/1", "M/M/C", "M/M/1/K"):
            return random.expovariate(self.mu)
        else:
            ES = 1 / self.mu
            return max(0.001, random.gauss(ES, self.sigma))

    def _assign(self, c, now):
        for i, srv in enumerate(self.servers):
            if srv is None:
                c.start  = now
                svc      = self._service_time()
                c.finish = now + svc
                self.servers[i]     = c
                self.server_free[i] = c.finish
                return True
        return False

    def _update_time_avg_stats(self, now):
        dt = now - self.last_event_time
        n_q = len(self.queue)
        n_s = sum(1 for s in self.servers if s is not None)
        self.area_system += (n_q + n_s) * dt
        self.area_queue  += n_q * dt
        self.busy_time   += n_s * dt
        self.last_event_time = now

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
                            nxt = self.queue.pop(0)
                            nxt.start  = now
                            svc        = self._service_time()
                            nxt.finish = now + svc
                            self.servers[i]     = nxt
                            self.server_free[i] = nxt.finish
            time.sleep(0.05)

    def start(self):
        self._running   = True
        self._thread    = threading.Thread(target=self._tick, daemon=True)
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
            L_emp  = self.area_system / elapsed
            Lq_emp = self.area_queue / elapsed
            rho_emp = self.busy_time / (elapsed * self.C)
            finish_times = [max(0, c.finish - now) for c in s_snap if c is not None]
            if n_s < self.C:
                exp_wait = 0.0
            else:
                sorted_free = sorted(self.server_free)
                exp_wait = max(0, sorted_free[0] - now) + \
                           len(q_snap) * (1 / self.mu)
            return {
                "now":         now,
                "queue":       q_snap,
                "servers":     s_snap,
                "n_queue":     n_q,
                "n_servers":   n_s,
                "n_system":    n_sys,
                "total_arr":   self.total_arrived,
                "total_svc":   self.total_served,
                "total_balk":  self.total_balked,
                "W_emp":       W_emp,
                "Wq_emp":      Wq_emp,
                "L_emp":       L_emp,
                "Lq_emp":      Lq_emp,
                "finish_times": finish_times,
                "exp_wait":     exp_wait,
                "rho_emp":      rho_emp,
            }


# ══════════════════════════════════════════════════════════════════════
#  RESULT WINDOW
# ══════════════════════════════════════════════════════════════════════

def show_results_window(parent, snap, model):
    win = tk.Toplevel(parent)
    win.title("Simulation Results")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.grab_set()

    # ── header ────────────────────────────────────────────────────────
    hdr = tk.Frame(win, bg="#0d0d1a", pady=10)
    hdr.pack(fill="x")
    tk.Label(hdr, text="■  SIMULATION STOPPED",
             bg="#0d0d1a", fg=RED, font=("Consolas", 12, "bold")
             ).pack(side="left", padx=14)
    tk.Label(hdr, text=f"Model: {model}",
             bg="#0d0d1a", fg=MUTED, font=F_BODY
             ).pack(side="right", padx=14)

    body = tk.Frame(win, bg=BG, padx=20, pady=16)
    body.pack(fill="both", expand=True)

    # ── metric cards ─────────────────────────────────────────────────
    metrics_title = tk.Label(body,
        text="AVERAGE PERFORMANCE METRICS",
        bg=BG, fg=PURPLE, font=("Consolas", 9, "bold"))
    metrics_title.pack(anchor="w", pady=(0, 8))

    cards_frame = tk.Frame(body, bg=BG)
    cards_frame.pack(fill="x", pady=(0, 14))

    rho = snap["rho_emp"]
    L   = snap["L_emp"]
    Lq  = snap["Lq_emp"]
    W   = snap["W_emp"]
    Wq  = snap["Wq_emp"]

    def fmt(v):
        if math.isinf(v): return "∞"
        if v >= 10000:    return f"{v:,.0f}"
        if v >= 100:      return f"{v:.1f}"
        return f"{v:.4f}"

    metric_cards = [
        ("ρ",  "Utilisation",        fmt(rho),       CYAN,   "Server busy fraction"),
        ("L",  "Avg in System",      fmt(L),          GREEN,  "Customers in system"),
        ("Lq", "Avg in Queue",       fmt(Lq),         YELLOW, "Customers waiting"),
        ("W",  "Avg System Time",    f"{fmt(W)} s",   ORANGE, "Time per customer"),
        ("Wq", "Avg Wait Time",      f"{fmt(Wq)} s",  RED,    "Queue wait per customer"),
    ]

    for i, (sym, label, val, color, desc) in enumerate(metric_cards):
        card = tk.Frame(cards_frame, bg=CARD, padx=14, pady=12,
                        highlightthickness=1, highlightbackground=color)
        card.grid(row=0, column=i, padx=5, sticky="ew")
        cards_frame.grid_columnconfigure(i, weight=1)

        tk.Label(card, text=sym, bg=CARD, fg=color,
                 font=("Consolas", 20, "bold")).pack()
        tk.Label(card, text=label, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 8)).pack()
        tk.Label(card, text=val, bg="#0a0a1a", fg=color,
                 font=("Consolas", 14, "bold"),
                 pady=6, padx=8, width=10).pack(fill="x", pady=(6, 2))
        tk.Label(card, text=desc, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 7)).pack()

    # ── traffic summary ───────────────────────────────────────────────
    sep = tk.Frame(body, bg=BORDER, height=1)
    sep.pack(fill="x", pady=(4, 12))

    tk.Label(body, text="TRAFFIC SUMMARY",
             bg=BG, fg=PURPLE, font=("Consolas", 9, "bold")
             ).pack(anchor="w", pady=(0, 8))

    stats_frame = tk.Frame(body, bg=PANEL, padx=16, pady=12)
    stats_frame.pack(fill="x")

    stats = [
        ("Customers arrived",  str(snap["total_arr"]),  TEXT),
        ("Customers served",   str(snap["total_svc"]),  GREEN),
        ("Customers balked",   str(snap["total_balk"]), RED),
        ("In system at stop",  str(snap["n_system"]),   YELLOW),
    ]

    for col, (lbl, val, color) in enumerate(stats):
        fr = tk.Frame(stats_frame, bg=PANEL)
        fr.grid(row=0, column=col, padx=20, sticky="w")
        stats_frame.grid_columnconfigure(col, weight=1)
        tk.Label(fr, text=lbl, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w")
        tk.Label(fr, text=val, bg=PANEL, fg=color,
                 font=("Consolas", 18, "bold")).pack(anchor="w")

    # ── close button ─────────────────────────────────────────────────
    tk.Button(body, text="✕  Close",
              command=win.destroy,
              bg=CARD, fg=TEXT, font=F_HEAD,
              activebackground=BORDER,
              relief="flat", bd=0, pady=10, cursor="hand2"
              ).pack(fill="x", pady=(16, 0))

    # centre on parent
    win.update_idletasks()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    px = parent.winfo_x()
    py = parent.winfo_y()
    ww = win.winfo_width()
    wh = win.winfo_height()
    win.geometry(f"+{px + (pw - ww)//2}+{py + (ph - wh)//2}")


# ══════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════

def fmt(v):
    if math.isinf(v): return "∞"
    if v >= 10000:    return f"{v:,.0f}"
    if v >= 100:      return f"{v:.1f}"
    return f"{v:.3f}"


class App(tk.Tk):
    MODELS = ["M/M/1", "M/M/C", "M/G/1", "M/G/C", "M/M/1/K"]

    def __init__(self):
        super().__init__()
        self.title("Queueing ModelSim  –  Live")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 600)

        self._engine  = None
        self._running = False
        self._selected = tk.StringVar(value="M/M/1")
        self._queue_rows = []
        self._build_ui()
        self._on_model_change()
        self._poll()

    # ──────────────────────────── UI ──────────────────────────────────
    def _build_ui(self):
        bar = tk.Frame(self, bg="#0d0d1a", pady=6)
        bar.pack(fill="x")
        tk.Label(bar, text="⬡  Queueing ModelSim  –  Live Simulator",
                 bg="#0d0d1a", fg=CYAN, font=F_TITLE).pack(side="left", padx=12)

        root = tk.Frame(self, bg=BG, padx=10, pady=10)
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(1, weight=1)

        left = tk.Frame(root, bg=BG)
        left.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(0, 10))

        mf = tk.LabelFrame(left, text=" Model ", bg=PANEL, fg=PURPLE,
                           font=F_HEAD, bd=1, relief="groove", padx=8, pady=8)
        mf.pack(fill="x", pady=(0, 8))
        for m in self.MODELS:
            tk.Radiobutton(mf, text=m, variable=self._selected, value=m,
                           indicatoron=False, bg=CARD, fg=TEXT,
                           selectcolor=PURPLE, activebackground=PURPLE_HV,
                           font=F_HEAD, width=9, relief="flat", pady=7,
                           cursor="hand2",
                           command=self._on_model_change).pack(fill="x", pady=3)

        inf = tk.LabelFrame(left, text=" Parameters ", bg=PANEL, fg=PURPLE,
                            font=F_HEAD, bd=1, relief="groove", padx=10, pady=8)
        inf.pack(fill="x", pady=(0, 8))
        self._entries = {}
        self._elabels = {}
        fields = [
            ("Service rate μ  :", "mu",    "3"),
            ("Servers C       :", "C",     "2"),
            ("Capacity K      :", "K",     "10"),
            ("Std-dev σ (svc) :", "sigma", ""),
        ]
        for i, (lbl, key, dflt) in enumerate(fields):
            l = tk.Label(inf, text=lbl, bg=PANEL, fg=MUTED, font=F_BODY, anchor="w")
            l.grid(row=i, column=0, sticky="w", pady=3, padx=(0, 6))
            self._elabels[key] = l
            e = tk.Entry(inf, font=F_MONO, width=7, bg="#0d0d1a", fg=CYAN,
                         insertbackground=CYAN, relief="flat", bd=3,
                         highlightthickness=1, highlightcolor=PURPLE,
                         highlightbackground=BORDER)
            e.insert(0, dflt)
            e.grid(row=i, column=1, sticky="ew", pady=3)
            self._entries[key] = e
        inf.grid_columnconfigure(1, weight=1)

        cf = tk.Frame(left, bg=BG)
        cf.pack(fill="x", pady=(0, 6))
        self._start_btn = tk.Button(cf, text="▶  Start",
                                    command=self._start_sim,
                                    bg=GREEN, fg="#000", font=F_HEAD,
                                    activebackground=GREEN_HV,
                                    relief="flat", bd=0, pady=9, cursor="hand2")
        self._start_btn.pack(fill="x", pady=(0, 4))
        self._stop_btn = tk.Button(cf, text="■  Stop",
                                   command=self._stop_sim,
                                   bg=RED, fg=TEXT, font=F_HEAD,
                                   activebackground=RED_HV,
                                   relief="flat", bd=0, pady=9, cursor="hand2",
                                   state="disabled")
        self._stop_btn.pack(fill="x", pady=(0, 4))
        tk.Button(cf, text="✕  Quit", command=self.destroy,
                  bg="#2c2c2c", fg=MUTED, font=F_HEAD,
                  relief="flat", bd=0, pady=9, cursor="hand2").pack(fill="x")

        mc = tk.LabelFrame(root, text=" Live Queue Metrics ",
                           bg=PANEL, fg=PURPLE, font=F_HEAD,
                           bd=1, relief="groove", padx=10, pady=8)
        mc.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        metric_defs = [
            ("ρ",  "Utilisation", "rho"),
            ("L",  "In System",   "L"),
            ("Lq", "In Queue",    "Lq"),
            ("W",  "Time/System", "W"),
            ("Wq", "Wait Time",   "Wq"),
        ]
        self._m_theory = {}
        self._m_emp    = {}
        for col, (sym, desc, key) in enumerate(metric_defs):
            cell = tk.Frame(mc, bg=CARD, padx=8, pady=6)
            cell.grid(row=0, column=col, padx=5, pady=2, sticky="ew")
            mc.grid_columnconfigure(col, weight=1)
            tk.Label(cell, text=sym,  bg=CARD, fg=CYAN,
                     font=("Consolas", 14, "bold")).pack()
            tk.Label(cell, text=desc, bg=CARD, fg=MUTED, font=F_SMALL).pack()
            ve = tk.StringVar(value="—")
            tk.Label(cell, textvariable=ve, bg="#0a1a0a", fg=GREEN,
                     font=F_HEAD, width=9, pady=3).pack(fill="x", pady=(2, 0))
            self._m_emp[key] = ve

        qf = tk.LabelFrame(root, text=" Live Queue ",
                           bg=PANEL, fg=PURPLE, font=F_HEAD,
                           bd=1, relief="groove", padx=10, pady=8)
        qf.grid(row=1, column=1, sticky="nsew", pady=(0, 8))

        self._server_frame = tk.Frame(qf, bg=PANEL)
        self._server_frame.pack(fill="x", pady=(0, 8))
        self._server_labels = []

        tk.Label(qf, text="Waiting in queue:", bg=PANEL, fg=MUTED, font=F_BODY).pack(anchor="w")

        q_wrap = tk.Frame(qf, bg=PANEL)
        q_wrap.pack(fill="both", expand=True)

        self._qcanvas = tk.Canvas(q_wrap, bg="#0d0d1a", height=120, highlightthickness=0)
        vsb = tk.Scrollbar(q_wrap, orient="vertical", command=self._qcanvas.yview)
        self._qcanvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._qcanvas.pack(side="left", fill="both", expand=True)

        self._q_inner = tk.Frame(self._qcanvas, bg="#0d0d1a")
        self._q_win   = self._qcanvas.create_window((0, 0), window=self._q_inner, anchor="nw")
        self._q_inner.bind("<Configure>",
            lambda e: self._qcanvas.configure(scrollregion=self._qcanvas.bbox("all")))

        tk.Button(qf, text="➕  Add Customer Manually",
                  command=self._add_manual,
                  bg=ORANGE, fg=TEXT, font=F_HEAD,
                  activebackground="#d35400",
                  relief="flat", bd=0, pady=10, cursor="hand2"
                  ).pack(fill="x", pady=(8, 0))

        ib = tk.Frame(root, bg=PANEL, padx=10, pady=8)
        ib.grid(row=2, column=1, sticky="ew")

        self._info_vars = {}
        info_defs = [
            ("Arrived",               "arr",    TEXT),
            ("Served",                "svc",    GREEN),
            ("Balked",                "balk",   RED),
            ("In System",             "nsys",   YELLOW),
            ("Next server free in",   "nxtfin", CYAN),
            ("Your order done in",    "ordone", ORANGE),
            ("Est. wait if join now", "wait",   ORANGE),
        ]
        for col, (lbl, key, color) in enumerate(info_defs):
            fr = tk.Frame(ib, bg=PANEL)
            fr.grid(row=0, column=col, padx=8, sticky="w")
            ib.grid_columnconfigure(col, weight=1)
            tk.Label(fr, text=lbl, bg=PANEL, fg=MUTED, font=F_SMALL).pack(anchor="w")
            v = tk.StringVar(value="—")
            tk.Label(fr, textvariable=v, bg=PANEL, fg=color,
                     font=("Consolas", 10, "bold")).pack(anchor="w")
            self._info_vars[key] = v

    def _on_model_change(self):
        model = self._selected.get()
        vis = {
            "M/M/1":   {"mu"},
            "M/M/C":   {"mu", "C"},
            "M/G/1":   {"mu", "sigma"},
            "M/G/C":   {"mu", "C", "sigma"},
            "M/M/1/K": {"mu", "K"},
        }.get(model, {"lam", "mu"})
        for key, e in self._entries.items():
            lbl = self._elabels[key]
            if key in vis:
                lbl.grid()
                e.grid()
                e.config(state="normal")
            else:
                e.config(state="normal")
                e.delete(0, "end")
                e.grid_remove()
                lbl.grid_remove()
        for v in self._m_emp.values():
            v.set("—")

    def _rebuild_servers(self, C):
        for w in self._server_frame.winfo_children():
            w.destroy()
        self._server_labels = []
        tk.Label(self._server_frame, text="Servers:",
                 bg=PANEL, fg=MUTED, font=F_BODY
                 ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        for i in range(C):
            fr = tk.Frame(self._server_frame, bg=CARD, padx=6, pady=4)
            fr.grid(row=0, column=i + 1, padx=4)
            tk.Label(fr, text=f"S{i+1}", bg=CARD, fg=MUTED, font=F_SMALL).pack()
            lbl = tk.Label(fr, text="idle", bg=CARD, fg=MUTED, font=F_HEAD, width=10, pady=3)
            lbl.pack()
            self._server_labels.append(lbl)

    def _pf(self, key, default=None):
        try:
            s = self._entries[key].get().strip()
            if not s: return default
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

    def _start_sim(self):
        model = self._selected.get()
        mu    = self._pf("mu")
        C     = self._pi("C", 1)
        K     = self._pi("K", 999)
        sigma = self._pf("sigma", None)

        if not mu or mu <= 0:
            messagebox.showerror("Input", "μ phải > 0"); return
        if model in ("M/M/C", "M/G/C") and (not C or C < 1):
            messagebox.showerror("Input", "C phải ≥ 1"); return
        if model == "M/M/1/K" and (not K or K < 1):
            messagebox.showerror("Input", "K phải ≥ 1"); return

        if self._engine:
            self._engine.stop()

        Customer._id = 0
        c_val = C if C else 1
        k_val = K if K else 999
        self._engine = QueueEngine(model, mu, C=c_val, K=k_val, sigma=sigma)
        self._engine.start()
        self._running = True
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._rebuild_servers(c_val)

    def _stop_sim(self):
        if self._engine:
            self._engine.stop()
            snap  = self._engine.snapshot()
            model = self._selected.get()
            show_results_window(self, snap, model)

        self._running = False
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")

    def _add_manual(self):
        if not self._engine:
            messagebox.showinfo("Info", "Khởi động simulation trước."); return
        _, status = self._engine.add_customer()
        if status == "balked":
            messagebox.showwarning("Hàng đợi đầy", "Hệ thống đầy – khách rời đi (balked)!")

    def _poll(self):
        if self._running and self._engine:
            try:
                snap = self._engine.snapshot()
                self._update_ui(snap)
            except Exception:
                pass
        self.after(200, self._poll)

    def _update_ui(self, snap):
        now = snap["now"]
        self._info_vars["arr"].set(str(snap["total_arr"]))
        self._info_vars["svc"].set(str(snap["total_svc"]))
        self._info_vars["balk"].set(str(snap["total_balk"]))
        self._info_vars["nsys"].set(str(snap["n_system"]))

        ft = snap["finish_times"]
        if ft:
            nxt = min(ft)
            self._info_vars["nxtfin"].set(f"{nxt:.2f}s")
            exp_finish = snap["exp_wait"] + (1 / self._engine.mu)
            self._info_vars["ordone"].set(f"{exp_finish:.2f}s")
        else:
            self._info_vars["nxtfin"].set("idle")
            self._info_vars["ordone"].set(f"{1/self._engine.mu:.2f}s")

        self._info_vars["wait"].set(f"{snap['exp_wait']:.2f}s")

        rho = snap["rho_emp"]
        self._m_emp["rho"].set(fmt(rho))
        self._m_emp["L"].set(fmt(snap["L_emp"]))
        self._m_emp["Lq"].set(fmt(snap["Lq_emp"]))
        self._m_emp["W"].set(fmt(snap["W_emp"]))
        self._m_emp["Wq"].set(fmt(snap["Wq_emp"]))

        for i, c in enumerate(snap["servers"]):
            if i >= len(self._server_labels):
                break
            lbl = self._server_labels[i]
            if c is None:
                lbl.config(text="idle", fg=MUTED, bg=CARD)
            else:
                rem = max(0, c.finish - now)
                lbl.config(text=f"#{c.id}  {rem:.1f}s", fg=GREEN, bg="#0a2a0a")

        queue_data = snap["queue"]
        while len(self._queue_rows) < len(queue_data):
            row = tk.Frame(self._q_inner, bg="#0d1520", pady=2, padx=4)
            pos_lbl  = tk.Label(row, bg=PURPLE, fg=TEXT, font=("Consolas", 9, "bold"), width=3)
            pos_lbl.pack(side="left", padx=(0, 6))
            cust_lbl = tk.Label(row, bg="#0d1520", fg=TEXT, font=F_MONO, width=14)
            cust_lbl.pack(side="left")
            wait_lbl = tk.Label(row, bg="#0d1520", fg=YELLOW, font=F_MONO, width=14)
            wait_lbl.pack(side="left")
            est_lbl  = tk.Label(row, bg="#0d1520", fg=ORANGE, font=F_MONO, width=18)
            est_lbl.pack(side="left")
            done_lbl = tk.Label(row, bg="#0d1520", fg=CYAN, font=F_MONO)
            done_lbl.pack(side="left")
            row.pack(fill="x", padx=2, pady=1)
            self._queue_rows.append({
                "frame": row, "pos": pos_lbl, "cust": cust_lbl,
                "wait": wait_lbl, "est": est_lbl, "done": done_lbl
            })

        avg_svc = 1 / self._engine.mu
        for i, row_data in enumerate(self._queue_rows):
            if i >= len(queue_data):
                row_data["frame"].pack_forget()
                continue
            row_data["frame"].pack(fill="x", padx=2, pady=1)
            c = queue_data[i]
            waited   = now - c.arrival
            base_wait = min(ft) if ft else avg_svc
            est_wait  = base_wait + (i * avg_svc / self._engine.C)
            est_done  = est_wait + avg_svc
            row_data["pos"].config(text=f" {i+1:02d} ")
            row_data["cust"].config(text=f"Customer #{c.id}")
            row_data["wait"].config(text=f" waited {waited:.1f}s")
            row_data["est"].config(text=f" chờ thêm ≈ {est_wait:.1f}s")
            row_data["done"].config(text=f" xong lúc ≈ +{est_done:.1f}s")

        if not queue_data:
            if not hasattr(self, "_empty_lbl"):
                self._empty_lbl = tk.Label(self._q_inner, text="  — queue empty —",
                                           bg="#0d0d1a", fg=MUTED, font=F_BODY)
            self._empty_lbl.pack(anchor="w", pady=6)
        else:
            if hasattr(self, "_empty_lbl"):
                self._empty_lbl.pack_forget()

        self._qcanvas.configure(scrollregion=self._qcanvas.bbox("all"))


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()