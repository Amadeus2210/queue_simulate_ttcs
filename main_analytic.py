"""
main_analytic.py – Analytic queueing calculator with discrete-event simulation plots.
Run:  python main_analytic.py
"""
import math
import tkinter as tk
from tkinter import messagebox

from theme import (
    BG_DARK, BG_PANEL, PURPLE_A, PURPLE_AH, GREEN, GREEN_HV,
    RED_BTN, RED_HV, TEXT, BORDER, LABEL_FG,
    BTN_FONT, TITLE_FONT, LBL_FONT, ENTRY_FONT
)
from metrics import compute_metrics
from utils import parse_float, parse_int
from simulations import mm1_simulate, mmc_simulate, mm1k_simulate, mg1_simulate, md1_simulate
from plot_window import PlotWindow


class QueueApp(tk.Tk):
    MODELS = ["M/M/1", "M/M/C", "M/M/1/K", "M/G/1", "M/D/1"]

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
                 bg="#1a1a2e", fg=PURPLE_A, font=TITLE_FONT
                 ).pack(side="left", pady=4)

        outer = tk.Frame(self, bg=BG_DARK, padx=10, pady=10)
        outer.pack(fill="both", expand=True)

        # ── Models panel ──────────────────────────────────────────────
        mdl_frame = tk.LabelFrame(outer, text=" Models ",
                                  bg=BG_PANEL, fg=PURPLE_A, font=BTN_FONT,
                                  bd=2, relief="groove", padx=10, pady=10)
        mdl_frame.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ns")

        self._model_buttons = {}
        for m in self.MODELS:
            rb = tk.Radiobutton(
                mdl_frame,
                text=m,
                variable=self._selected_model,
                value=m,
                indicatoron=False,
                bg=PURPLE_A, fg=TEXT,
                selectcolor=PURPLE_AH,
                activebackground=PURPLE_AH, activeforeground=TEXT,
                font=("Consolas", 10, "normal"),
                width=10, relief="flat", bd=0, pady=8,
                cursor="hand2",
                command=self._on_model_change
            )
            rb.pack(fill="x", pady=4)
            self._model_buttons[m] = rb

        # ── Inputs panel ──────────────────────────────────────────────
        inp_frame = tk.LabelFrame(outer, text=" Inputs ",
                                  bg=BG_PANEL, fg=PURPLE_A, font=BTN_FONT,
                                  bd=2, relief="groove", padx=16, pady=12)
        inp_frame.grid(row=0, column=1, sticky="nsew")

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
                         highlightthickness=1, highlightcolor=PURPLE_A,
                         highlightbackground=BORDER)
            e.insert(0, default)
            e.grid(row=i, column=1, sticky="ew", pady=5)
            self._entries[key] = e
        inp_frame.grid_columnconfigure(1, weight=1)

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
                                  bg=BG_PANEL, fg=PURPLE_A, font=BTN_FONT,
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
            tk.Label(cell, text=sym, bg=BG_PANEL, fg=PURPLE_A,
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

    # ── model change ──────────────────────────────────────────────────

    def _on_model_change(self):
        model  = self._selected_model.get()
        active = self._ACTIVE.get(model, {"lam", "mu"})

        for m, rb in self._model_buttons.items():
            if m == model:
                rb.config(bg="#d16eff", fg="white",
                          activebackground="#e08cff", activeforeground="white",
                          relief="raised", bd=2)
            else:
                rb.config(bg=PURPLE_A, fg=TEXT,
                          activebackground=PURPLE_AH, activeforeground=TEXT,
                          relief="flat", bd=0)

        for key, entry in self._entries.items():
            lbl = self._labels[key]
            if key in active:
                lbl.grid(); entry.grid(); entry.config(state="normal")
            else:
                entry.config(state="normal"); entry.delete(0, "end")
                entry.grid_remove(); lbl.grid_remove()

        if hasattr(self, "_metric_vars"):
            for var in self._metric_vars.values():
                var.set("—")

    # ── parse helpers ─────────────────────────────────────────────────

    def _pf(self, key, default=None):
        return parse_float(self._entries[key], default)

    def _pi(self, key, default=None):
        return parse_int(self._entries[key], default)

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

        PlotWindow(self, model, results)

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
