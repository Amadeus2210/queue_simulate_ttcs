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


def metrics_dd1k(lam, mu, K):
    """D/D/1/K – deterministic closed-form."""
    rho = lam / mu
    if rho < 1:
        L  = rho
        Lq = 0.0
        W  = 1 / mu
        Wq = 0.0
    elif rho == 1:
        L  = K / 2
        Lq = max(0, K / 2 - 1)
        W  = L / lam
        Wq = Lq / lam
    else:
        L  = K
        Lq = K - 1
        lam_eff = mu
        W  = L / lam_eff
        Wq = Lq / lam_eff
    return dict(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq)


def metrics_mm1(lam, mu):
    """M/M/1 – classical formulas (requires ρ < 1)."""
    rho = lam / mu
    if rho >= 1:
        return dict(rho=rho, L=float('inf'), Lq=float('inf'),
                    W=float('inf'), Wq=float('inf'))
    L  = rho / (1 - rho)
    Lq = rho**2 / (1 - rho)
    W  = 1 / (mu - lam)
    Wq = lam / (mu * (mu - lam))
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


def metrics_mmC(lam, mu, C):
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


def metrics_mmCk(lam, mu, C, K):
    """M/M/C/K – finite capacity multi-server."""
    rho = lam / mu
    r   = lam / (C * mu)

    P = [0.0] * (K + 1)
    sum_val = sum(rho**n / math.factorial(n) for n in range(C))
    if abs(r - 1.0) < 1e-9:
        sum_val += rho**C / math.factorial(C) * (K - C + 1)
    else:
        sum_val += rho**C / math.factorial(C) * \
                   (1 - r**(K - C + 1)) / (1 - r)
    P0 = 1 / sum_val if sum_val > 0 else 0

    for n in range(K + 1):
        if n < C:
            P[n] = rho**n / math.factorial(n) * P0
        else:
            P[n] = rho**n / (math.factorial(C) * C**(n - C)) * P0

    PK      = P[K]
    lam_eff = lam * (1 - PK)
    L       = sum(n * P[n] for n in range(K + 1))
    Lq      = sum((n - C) * P[n] for n in range(C, K + 1))
    W       = L / lam_eff if lam_eff > 0 else float('inf')
    Wq      = Lq / lam_eff if lam_eff > 0 else float('inf')
    util    = lam_eff / (C * mu)
    return dict(rho=util, L=L, Lq=max(0, Lq), W=W, Wq=max(0, Wq))


def compute_metrics(model, lam, mu, K=None, C=None):
    """Dispatch to the right analytic formula."""
    try:
        if model == "D/D/1/K":
            return metrics_dd1k(lam, mu, K)
        elif model == "M/M/1":
            return metrics_mm1(lam, mu)
        elif model == "M/M/1/K":
            return metrics_mm1k(lam, mu, K)
        elif model == "M/M/C":
            return metrics_mmC(lam, mu, C)
        elif model == "M/M/C/K":
            return metrics_mmCk(lam, mu, C, K)
    except Exception:
        pass
    return None


ARRIVAL   = 0
DEPARTURE = 1


def _init_results():
    """Khởi tạo dict kết quả rỗng."""
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
    """Ghi snapshot tại thời điểm t."""
    res["times"].append(t)
    res["entities_sys"].append(in_system)
    res["waiting_q"].append(n_in_queue)
    res["balking"].append(total_balk)


def _pad_results(res):
    return res


# ══════════════════════════════════════════════════════════════════════
#  MODEL 1: D/D/1/K  (Deterministic)
# ══════════════════════════════════════════════════════════════════════

def dd1k_simulate(lam, mu, K, M, n_events=100):
    """
    D/D/1/K event-based simulation.
    Arrivals và departures đều được schedule chính xác.
    M = số customer ban đầu trong hệ thống.
    """
    inter_arr = 1.0 / lam
    svc_time  = 1.0 / mu

    res         = _init_results()
    total_balk  = 0
    event_ctr   = [0]       
    eid         = [0]

    # State
    in_system      = min(M, K)
    server_busy    = False
    server_free_at = 0.0
    queue          = []          
    heap           = []

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    if in_system > 0:
        server_busy    = True
        server_free_at = svc_time
        for i in range(in_system - 1):
            queue.append(0.0)     
        schedule(svc_time, DEPARTURE)

    # Schedule arrival đầu tiên
    schedule(inter_arr, ARRIVAL)
    next_arr_time = inter_arr

    res["entities_sys"][0] = in_system
    res["waiting_q"][0]    = max(0, in_system - (1 if server_busy else 0))

    while heap and event_ctr[0] < n_events:
        t, etype, _ = heapq.heappop(heap)

        _snapshot(res, t, in_system,
                  max(0, in_system - (1 if server_busy else 0)),
                  total_balk)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)
            event_ctr[0] += 1

            if in_system < K:
                in_system += 1
                if not server_busy:
                    # Server rảnh → phục vụ ngay (D/D/1: không chờ)
                    server_busy    = True
                    server_free_at = t + svc_time
                    res["waiting_sys"].append(0.0)
                    schedule(server_free_at, DEPARTURE)
                else:
                    queue.append(t)
            else:
                total_balk += 1

            # Schedule arrival kế tiếp
            next_arr_time += inter_arr
            schedule(next_arr_time, ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            in_system -= 1         

            if queue:
                arrive_t  = queue.pop(0)
                wait_time = t - arrive_t   
                res["waiting_sys"].append(wait_time)
                server_free_at = t + svc_time
                schedule(server_free_at, DEPARTURE)
            else:
                server_busy = False

    return _pad_results(res)


# ══════════════════════════════════════════════════════════════════════
#  MODEL 2: M/M/1  (Vô hạn capacity, 1 server)
# ══════════════════════════════════════════════════════════════════════

def mm1_simulate(lam, mu, n_events=100):
    """
    M/M/1 event-based simulation.
    Không giới hạn capacity → không có balking.
    """
    res        = _init_results()
    in_system  = 0
    server_busy = False
    queue      = []          
    heap       = []
    eid        = [0]
    dep_count  = [0]

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    schedule(random.expovariate(lam), ARRIVAL)

    while heap and dep_count[0] < n_events:
        t, etype, _ = heapq.heappop(heap)

        _snapshot(res, t, in_system,
                  max(0, in_system - (1 if server_busy else 0)),
                  0)

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
                arrive_t  = queue.pop(0)
                wait_time = t - arrive_t
                res["waiting_sys"].append(wait_time)
                schedule(t + random.expovariate(mu), DEPARTURE)
            else:
                server_busy = False

    return _pad_results(res)


# ══════════════════════════════════════════════════════════════════════
#  MODEL 3: M/M/1/K  (Finite capacity, 1 server)
# ══════════════════════════════════════════════════════════════════════

def mm1k_simulate(lam, mu, K, n_events=100):
    """
    M/M/1/K event-based simulation đúng chuẩn.

    LỖI GỐC đã sửa: in_system -= 1 chỉ xảy ra trong event DEPARTURE,
    KHÔNG phải ngay sau khi schedule service.
    """
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
                  max(0, in_system - (1 if server_busy else 0)),
                  total_balk)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)

            if in_system < K:
                in_system += 1

                if not server_busy:
                    # Server rảnh → phục vụ ngay, không chờ
                    server_busy = True
                    res["waiting_sys"].append(0.0)
                    schedule(t + random.expovariate(mu), DEPARTURE)
                else:
                    # Server bận → vào queue chờ
                    queue.append(t)
            else:
                # Hệ thống đầy (in_system == K) → balking
                total_balk += 1

            schedule(t + random.expovariate(lam), ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            dep_count[0] += 1
            in_system -= 1     

            if queue:
                arrive_t  = queue.pop(0)
                wait_time = t - arrive_t
                res["waiting_sys"].append(wait_time)
                schedule(t + random.expovariate(mu), DEPARTURE)
            else:
                server_busy = False

    return _pad_results(res)


# ══════════════════════════════════════════════════════════════════════
#  MODEL 4: M/M/C  (Vô hạn capacity, C servers)
# ══════════════════════════════════════════════════════════════════════

def mmC_simulate(lam, mu, C, n_events=100):
    """
    M/M/C event-based simulation.
    servers[] là list thời điểm mỗi server rảnh.
    Customer được assign cho server rảnh sớm nhất (min(servers)).
    """
    res        = _init_results()
    in_system  = 0
    servers    = [0.0] * C     
    queue      = []            
    heap       = []
    eid        = [0]
    dep_count  = [0]

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    def n_busy(t):
        """Số server đang bận tại thời điểm t."""
        return sum(1 for s in servers if s > t)

    schedule(random.expovariate(lam), ARRIVAL)

    while heap and dep_count[0] < n_events:
        t, etype, _ = heapq.heappop(heap)

        busy_now = n_busy(t)
        _snapshot(res, t, in_system,
                  max(0, in_system - busy_now),
                  0)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)
            in_system += 1

            # Tìm server rảnh sớm nhất
            earliest_free = min(servers)
            if earliest_free <= t:
                # Có server rảnh → phục vụ ngay
                idx = servers.index(earliest_free)
                res["waiting_sys"].append(0.0)
                svc_end    = t + random.expovariate(mu)
                servers[idx] = svc_end
                schedule(svc_end, DEPARTURE)
            else:
                # Tất cả C servers đều bận → vào queue
                queue.append(t)

            schedule(t + random.expovariate(lam), ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            dep_count[0] += 1
            in_system -= 1         
            closest_idx = min(range(C), key=lambda i: abs(servers[i] - t))
            servers[closest_idx] = t   

            if queue:
                arrive_t  = queue.pop(0)
                wait_time = t - arrive_t
                res["waiting_sys"].append(wait_time)
                svc_end = t + random.expovariate(mu)
                servers[closest_idx] = svc_end
                schedule(svc_end, DEPARTURE)

    return _pad_results(res)


# ══════════════════════════════════════════════════════════════════════
#  MODEL 5: M/M/C/K  (Finite capacity, C servers)
# ══════════════════════════════════════════════════════════════════════

def mmCk_simulate(lam, mu, C, K, n_events=100):
    """
    M/M/C/K event-based simulation.
    Kết hợp finite capacity (balking khi in_system == K)
    và multi-server (assign server rảnh sớm nhất).
    """
    res        = _init_results()
    in_system  = 0
    servers    = [0.0] * C
    queue      = []
    total_balk = 0
    heap       = []
    eid        = [0]
    dep_count  = [0]

    def schedule(t, etype):
        heapq.heappush(heap, (t, etype, eid[0]))
        eid[0] += 1

    def n_busy(t):
        return sum(1 for s in servers if s > t)

    schedule(random.expovariate(lam), ARRIVAL)

    while heap and dep_count[0] < n_events:
        t, etype, _ = heapq.heappop(heap)

        busy_now = n_busy(t)
        _snapshot(res, t, in_system,
                  max(0, in_system - busy_now),
                  total_balk)

        if etype == ARRIVAL:
            res["arrival_times"].append(t)

            if in_system < K:
                in_system += 1

                earliest_free = min(servers)
                if earliest_free <= t:
                    # Server rảnh → phục vụ ngay
                    idx = servers.index(earliest_free)
                    res["waiting_sys"].append(0.0)
                    svc_end      = t + random.expovariate(mu)
                    servers[idx] = svc_end
                    schedule(svc_end, DEPARTURE)
                else:
                    queue.append(t)
            else:
                total_balk += 1

            schedule(t + random.expovariate(lam), ARRIVAL)

        elif etype == DEPARTURE:
            res["departure_times"].append(t)
            dep_count[0] += 1
            in_system -= 1        

            closest_idx = min(range(C), key=lambda i: abs(servers[i] - t))
            servers[closest_idx] = t

            if queue:
                arrive_t  = queue.pop(0)
                wait_time = t - arrive_t
                res["waiting_sys"].append(wait_time)
                svc_end = t + random.expovariate(mu)
                servers[closest_idx] = svc_end
                schedule(svc_end, DEPARTURE)

    return _pad_results(res)


# ══════════════════════════════════════════════════════════════════════
#  PLOT WINDOW
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
        hdr = tk.Label(self, text=f"  {model_name}  –  Simulation Results  ",
                       bg=PURPLE, fg=TEXT, font=TITLE_FONT, pady=6)
        hdr.pack(fill="x")

        r = self.results

        n_sys = min(len(r["times"]), len(r["entities_sys"]))
        n_q   = min(len(r["times"]), len(r["waiting_q"]))
        waits = [w for w in r["waiting_sys"] if w is not None]

        plots = [
            ("Entities in System", "Time", "# Entities",
            r["times"][:len(r["entities_sys"])],
            r["entities_sys"][:len(r["entities_sys"])],
            PURPLE, True),

            ("Waiting in Queue", "Time", "# Waiting",
            r["times"][:len(r["waiting_q"])],
            r["waiting_q"][:len(r["waiting_q"])],
            "#3498db", True),

            ("Waiting Time per Customer", "Customer #", "Wait (time units)",
            list(range(len(waits))),
            waits,
            "#e67e22", False),

            ("Departure Times", "Customer #", "Departure Time",
            list(range(len(r["departure_times"]))),
            r["departure_times"],
            GREEN, False),

            ("Balking (Cumulative)", "Time", "Customers Balked",
            r["times"][:len(r["balking"])],
            r["balking"][:len(r["balking"])],
            RED_BTN, True),

            ("Arrival Times", "Customer #", "Arrival Time",
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
    MODELS = ["D/D/1/K", "M/M/1", "M/M/1/K", "M/M/C", "M/M/C/K"]

    def __init__(self):
        super().__init__()
        self.title("Queueing ModelSim")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self._selected_model = tk.StringVar(value="D/D/1/K")
        self._build_ui()

    def _build_ui(self):
        title_bar = tk.Frame(self, bg="#1a1a2e", height=32)
        title_bar.pack(fill="x")
        tk.Label(title_bar, text="  ⬡  Queueing ModelSim",
                 bg="#1a1a2e", fg=PURPLE, font=TITLE_FONT).pack(side="left", pady=4)

        outer = tk.Frame(self, bg=BG_DARK, padx=10, pady=10)
        outer.pack(fill="both", expand=True)

        # ── Models panel ──────────────────────────────────────────────
        mdl_frame = tk.LabelFrame(outer, text=" Models ",
                                  bg=BG_PANEL, fg=PURPLE, font=BTN_FONT,
                                  bd=2, relief="groove", padx=10, pady=10)
        mdl_frame.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ns")

        for m in self.MODELS:
            rb = tk.Radiobutton(mdl_frame, text=m,
                                variable=self._selected_model, value=m,
                                indicatoron=False,
                                bg=PURPLE, fg=TEXT,
                                selectcolor=PURPLE_HV,
                                activebackground=PURPLE_HV,
                                font=BTN_FONT, width=10,
                                relief="flat", bd=0, pady=8,
                                cursor="hand2",
                                command=self._on_model_change)
            rb.pack(fill="x", pady=4)

        # ── Inputs panel ──────────────────────────────────────────────
        inp_frame = tk.LabelFrame(outer, text=" Inputs ",
                                  bg=BG_PANEL, fg=PURPLE, font=BTN_FONT,
                                  bd=2, relief="groove", padx=16, pady=12)
        inp_frame.grid(row=0, column=1, sticky="nsew")

        fields = [
            ("Arrival rate (λ):",      "lam",  "1/4"),
            ("Service rate (μ):",      "mu",   "1/6"),
            ("Queue Capacity (K):",    "K",    "5"),
            ("Servers (C):",           "C",    ""),
            ("Initial Customers (M):", "M",    "0"),
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
                  cursor="hand2").pack(side="left", expand=True, fill="x", padx=(0, 8))

        tk.Button(btn_row, text="▶  Calculate",
                  command=self._calculate,
                  bg=GREEN, fg=TEXT, font=BTN_FONT,
                  activebackground=GREEN_HV, activeforeground=TEXT,
                  relief="flat", bd=0, padx=20, pady=10,
                  cursor="hand2").pack(side="left", expand=True, fill="x")

        # ── Performance Metrics panel ─────────────────────────────────
        res_frame = tk.LabelFrame(outer, text=" Performance Metrics ",
                                  bg=BG_PANEL, fg=PURPLE, font=BTN_FONT,
                                  bd=2, relief="groove", padx=16, pady=10)
        res_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky="ew")
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
                     width=10, relief="flat", pady=4).pack(fill="x", pady=(4, 0))
            self._metric_vars[key] = var

        self._on_model_change()

    def _on_model_change(self):
        model = self._selected_model.get()

        active = {
            "D/D/1/K":  {"lam", "mu", "K", "M"},
            "M/M/1":    {"lam", "mu"},
            "M/M/1/K":  {"lam", "mu", "K"},
            "M/M/C":    {"lam", "mu", "C"},
            "M/M/C/K":  {"lam", "mu", "C", "K"},
        }.get(model, {"lam", "mu"})

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

    def _parse_rate(self, s):
        s = s.strip()
        if "/" in s:
            num, den = s.split("/")
            return float(num) / float(den)
        return float(s)

    def _get_float(self, key, default=None):
        try:
            return self._parse_rate(self._entries[key].get())
        except Exception:
            return default

    def _get_int(self, key, default=None):
        try:
            return int(self._entries[key].get())
        except Exception:
            return default

    def _calculate(self):
        model = self._selected_model.get()
        lam   = self._get_float("lam")
        mu    = self._get_float("mu")

        if lam is None or lam <= 0:
            messagebox.showerror("Input Error", "Invalid Arrival rate (λ)")
            return
        if mu is None or mu <= 0:
            messagebox.showerror("Input Error", "Invalid Service rate (μ)")
            return

        try:
            if model == "D/D/1/K":
                K = self._get_int("K", 5)
                M = self._get_int("M", 0)
                if K < 1:
                    messagebox.showerror("Input Error", "K phải ≥ 1")
                    return
                results = dd1k_simulate(lam, mu, K, M)

            elif model == "M/M/1":
                results = mm1_simulate(lam, mu)

            elif model == "M/M/1/K":
                K = self._get_int("K")
                if K is None or K < 1:
                    messagebox.showerror("Input Error", "Queue Capacity K phải ≥ 1")
                    return
                results = mm1k_simulate(lam, mu, K)

            elif model == "M/M/C":
                C = self._get_int("C")
                if C is None or C < 1:
                    messagebox.showerror("Input Error", "Servers C phải ≥ 1")
                    return
                results = mmC_simulate(lam, mu, C)

            elif model == "M/M/C/K":
                C = self._get_int("C")
                K = self._get_int("K")
                if C is None or C < 1:
                    messagebox.showerror("Input Error", "Servers C phải ≥ 1")
                    return
                if K is None or K < C:
                    messagebox.showerror("Input Error", f"K phải ≥ C (= {C})")
                    return
                results = mmCk_simulate(lam, mu, C, K)

            else:
                messagebox.showerror("Error", "Unknown model")
                return

        except Exception as ex:
            messagebox.showerror("Simulation Error", str(ex))
            return

        PlotWindow(self, model, results)

        # ── Analytic metrics ──────────────────────────────────────────
        m = compute_metrics(model, lam, mu,
                            K=self._get_int("K"),
                            C=self._get_int("C"))
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
