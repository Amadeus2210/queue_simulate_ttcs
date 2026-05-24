"""
live_results.py – Results popup window with time-series matplotlib charts.
"""
import tkinter as tk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from theme import (
    BG, PANEL, CARD, PURPLE, CYAN, GREEN, RED, YELLOW, TEXT, MUTED, BORDER,
    F_HEAD, F_BODY, F_SMALL
)

# Matplotlib dark theme colours
_MPL_BG   = "#1a1a2e"
_MPL_AXES = "#0f3460"
_MPL_GRID = "#2c3e50"

_SERIES = [
    ("ρ  Utilisation",     "ts_rho",  "#00d4ff",  "Utilisation (ρ)"),
    ("L  Avg in System",   "ts_L",    "#2ecc71",  "Customers in System (L)"),
    ("Lq Avg in Queue",    "ts_Lq",   "#f1c40f",  "Customers in Queue (Lq)"),
    ("W  Avg System Time", "ts_W",    "#e67e22",  "System Time per Customer (W) [s]"),
    ("Wq Avg Wait Time",   "ts_Wq",   "#e74c3c",  "Queue Wait per Customer (Wq) [s]"),
]


def show_results_window(parent, snap, model):
    win = tk.Toplevel(parent)
    win.title("Simulation Results  –  Time Series")
    win.configure(bg=BG)
    win.resizable(True, True)
    win.grab_set()

    # ── header ────────────────────────────────────────────────────────
    hdr = tk.Frame(win, bg="#0d0d1a", pady=8)
    hdr.pack(fill="x")
    tk.Label(hdr, text="■  SIMULATION STOPPED  –  Performance Over Time",
             bg="#0d0d1a", fg=RED, font=("Consolas", 12, "bold")
             ).pack(side="left", padx=14)
    tk.Label(hdr, text=f"Model: {model}",
             bg="#0d0d1a", fg=MUTED, font=F_BODY
             ).pack(side="right", padx=14)

    # ── traffic summary bar ───────────────────────────────────────────
    sb = tk.Frame(win, bg=PANEL, padx=16, pady=8)
    sb.pack(fill="x")
    stats = [
        ("Customers arrived", str(snap["total_arr"]),  TEXT),
        ("Customers served",  str(snap["total_svc"]),  GREEN),
        ("Customers balked",  str(snap["total_balk"]), RED),
        ("In system at stop", str(snap["n_system"]),   YELLOW),
        ("Final  ρ (emp)",    f"{snap['rho_emp']:.3f}", CYAN),
    ]
    for col, (lbl, val, color) in enumerate(stats):
        fr = tk.Frame(sb, bg=PANEL)
        fr.grid(row=0, column=col, padx=24, sticky="w")
        sb.grid_columnconfigure(col, weight=1)
        tk.Label(fr, text=lbl, bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
        tk.Label(fr, text=val, bg=PANEL, fg=color,
                 font=("Consolas", 15, "bold")).pack(anchor="w")

    # ── chart selector tabs ───────────────────────────────────────────
    tab_bar = tk.Frame(win, bg="#0d0d1a", pady=4)
    tab_bar.pack(fill="x")

    chart_frame = tk.Frame(win, bg=BG)
    chart_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))

    ts       = snap["ts_time"]
    has_data = len(ts) >= 2

    _figures      = {}
    _active_widget = [None]

    def _make_single_chart(tab_label, ts_key, color, ylabel):
        fig = Figure(figsize=(6.5, 3.2), dpi=96, facecolor=_MPL_BG)
        ax  = fig.add_subplot(111, facecolor=_MPL_AXES)
        if has_data:
            ys = snap[ts_key]
            ax.plot(ts, ys, color=color, linewidth=1.6, alpha=0.9, zorder=3)
            ax.fill_between(ts, ys, alpha=0.18, color=color, zorder=2)
            w = max(1, len(ys) // 10)
            if len(ys) >= w * 2:
                rm = [sum(ys[max(0, i - w):i + 1]) / len(ys[max(0, i - w):i + 1])
                      for i in range(len(ys))]
                ax.plot(ts, rm, color="white", linewidth=1.0,
                        linestyle="--", alpha=0.55, label="rolling avg", zorder=4)
                ax.legend(fontsize=8, facecolor=_MPL_AXES, edgecolor=_MPL_GRID,
                          labelcolor="white", loc="upper left")
        else:
            ax.text(0.5, 0.5, "Not enough data\n(run longer or add customers)",
                    transform=ax.transAxes, ha="center", va="center",
                    color=MUTED, fontsize=11)
        ax.set_xlabel("Elapsed time (s)", color=MUTED, fontsize=9)
        ax.set_ylabel(ylabel,             color=color,  fontsize=9)
        ax.set_title(tab_label,           color=color,  fontsize=11, fontweight="bold", pad=10)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.spines[:].set_color(_MPL_GRID)
        ax.grid(True, color=_MPL_GRID, linewidth=0.5, linestyle="--", alpha=0.6)
        fig.tight_layout(pad=1.4)
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        w = canvas.get_tk_widget()
        w.configure(bg=_MPL_BG)
        return fig, w

    def _make_overview():
        fig = Figure(figsize=(9, 7.5), dpi=96, facecolor=_MPL_BG)
        fig.subplots_adjust(hspace=0.55, left=0.09, right=0.97, top=0.94, bottom=0.07)
        for idx, (tab_lbl, ts_key, color, ylabel) in enumerate(_SERIES):
            ax = fig.add_subplot(3, 2, idx + 1, facecolor=_MPL_AXES)
            if has_data:
                ys = snap[ts_key]
                ax.plot(ts, ys, color=color, linewidth=1.4, alpha=0.9, zorder=3)
                ax.fill_between(ts, ys, alpha=0.15, color=color, zorder=2)
            else:
                ax.text(0.5, 0.5, "—", transform=ax.transAxes,
                        ha="center", va="center", color=MUTED, fontsize=14)
            sym = tab_lbl.split()[0]
            ax.set_title(tab_lbl, color=color, fontsize=8, fontweight="bold", pad=4)
            ax.tick_params(colors=MUTED, labelsize=7)
            ax.spines[:].set_color(_MPL_GRID)
            ax.grid(True, color=_MPL_GRID, linewidth=0.4, linestyle="--", alpha=0.5)
            ax.set_xlabel("t (s)", color=MUTED, fontsize=7)
            ax.set_ylabel(sym,     color=color,  fontsize=8)
        fig.add_subplot(3, 2, 6).set_visible(False)
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        w = canvas.get_tk_widget()
        w.configure(bg=_MPL_BG)
        return fig, w

    def _show_tab(key):
        if _active_widget[0] is not None:
            _active_widget[0].pack_forget()
        if key not in _figures:
            if key == "__all__":
                _figures[key] = _make_overview()
            else:
                info = next(x for x in _SERIES if x[1] == key)
                _figures[key] = _make_single_chart(info[0], info[1], info[2], info[3])
        _, w = _figures[key]
        w.pack(fill="both", expand=True)
        _active_widget[0] = w
        for btn_key, btn in _tab_btns.items():
            is_active = (btn_key == key)
            btn.config(
                bg=PURPLE if is_active else CARD,
                fg=TEXT   if is_active else MUTED,
                relief="flat"
            )

    _tab_btns = {}

    ov_btn = tk.Button(tab_bar, text="⬡ Overview",
                       command=lambda: _show_tab("__all__"),
                       bg=CARD, fg=MUTED, font=F_HEAD,
                       relief="flat", bd=0, padx=10, pady=6, cursor="hand2")
    ov_btn.pack(side="left", padx=(8, 2))
    _tab_btns["__all__"] = ov_btn

    for tab_lbl, ts_key, color, ylabel in _SERIES:
        short = tab_lbl.split()[0]
        btn = tk.Button(tab_bar, text=short,
                        command=lambda k=ts_key: _show_tab(k),
                        bg=CARD, fg=MUTED, font=F_HEAD,
                        relief="flat", bd=0, padx=12, pady=6, cursor="hand2")
        btn.pack(side="left", padx=2)
        _tab_btns[ts_key] = btn

    tk.Button(win, text="✕  Close",
              command=win.destroy,
              bg=CARD, fg=TEXT, font=F_HEAD,
              activebackground=BORDER,
              relief="flat", bd=0, pady=9, cursor="hand2"
              ).pack(fill="x", padx=8, pady=(0, 8))

    _show_tab("__all__")

    # Centre on parent
    win.update_idletasks()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    px = parent.winfo_x()
    py = parent.winfo_y()
    ww = win.winfo_width()
    wh = win.winfo_height()
    win.geometry(f"960x700+{px + (pw - ww) // 2}+{py + (ph - wh) // 2}")
