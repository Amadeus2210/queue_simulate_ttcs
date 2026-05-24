"""
main_live.py – Live real-time queueing simulator.
Run:  python main_live.py
"""
import tkinter as tk
from tkinter import messagebox

from theme import (
    BG, PANEL, CARD, PURPLE, PURPLE_HV, CYAN, GREEN, GREEN_HV,
    RED, RED_HV, ORANGE, TEXT, MUTED, BORDER,
    F_TITLE, F_HEAD, F_BODY, F_MONO, F_SMALL
)
from metrics import compute_metrics
from utils import fmt, parse_float, parse_int
from live_engine import Customer, QueueEngine
from live_results import show_results_window


class App(tk.Tk):
    MODELS = ["M/M/1", "M/M/C", "M/G/1", "M/G/C", "M/M/1/K"]

    def __init__(self):
        super().__init__()
        self.title("Queueing ModelSim  –  Live")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 600)

        self._engine   = None
        self._running  = False
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

        # ── left panel ────────────────────────────────────────────────
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

        # ── metrics ───────────────────────────────────────────────────
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
        self._m_emp = {}
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

        # ── live queue panel ──────────────────────────────────────────
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

        # ── info bar ──────────────────────────────────────────────────
        ib = tk.Frame(root, bg=PANEL, padx=10, pady=8)
        ib.grid(row=2, column=1, sticky="ew")

        self._info_vars = {}
        info_defs = [
            ("Arrived",               "arr",    TEXT),
            ("Served",                "svc",    GREEN),
            ("Balked",                "balk",   RED),
            ("In System",             "nsys",   ORANGE),
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

    # ── model change ──────────────────────────────────────────────────

    def _on_model_change(self):
        model = self._selected.get()
        vis = {
            "M/M/1":   {"mu"},
            "M/M/C":   {"mu", "C"},
            "M/G/1":   {"mu", "sigma"},
            "M/G/C":   {"mu", "C", "sigma"},
            "M/M/1/K": {"mu", "K"},
        }.get(model, {"mu"})
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

    # ── simulation control ────────────────────────────────────────────

    def _pf(self, key, default=None):
        return parse_float(self._entries[key], default)

    def _pi(self, key, default=None):
        return parse_int(self._entries[key], default)

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

    # ── polling / UI update ───────────────────────────────────────────

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
            cust_lbl = tk.Label(row, bg="#0d1520", fg=TEXT,   font=F_MONO, width=14)
            cust_lbl.pack(side="left")
            wait_lbl = tk.Label(row, bg="#0d1520", fg=ORANGE, font=F_MONO, width=14)
            wait_lbl.pack(side="left")
            est_lbl  = tk.Label(row, bg="#0d1520", fg=ORANGE, font=F_MONO, width=18)
            est_lbl.pack(side="left")
            done_lbl = tk.Label(row, bg="#0d1520", fg=CYAN,   font=F_MONO)
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
            waited    = now - c.arrival
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
