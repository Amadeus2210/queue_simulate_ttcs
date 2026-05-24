"""
plot_window.py – PlotWindow: 6-subplot chart popup for simulation results.
"""
import tkinter as tk
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from theme import (
    BG_DARK, PURPLE, PURPLE_AH, GREEN, RED_BTN, TEXT, BORDER,
    TITLE_FONT
)


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
            ("Entities in System",       "Time",       "# Entities",
             r["times"][:len(r["entities_sys"])], r["entities_sys"],
             PURPLE, True),

            ("Waiting in Queue",         "Time",       "# Waiting",
             r["times"][:len(r["waiting_q"])], r["waiting_q"],
             "#3498db", True),

            ("Waiting Time per Customer","Customer #", "Wait (time units)",
             list(range(len(waits))), waits,
             "#e67e22", False),

            ("Departure Times",          "Customer #", "Departure Time",
             list(range(len(r["departure_times"]))), r["departure_times"],
             GREEN, False),

            ("Balking (Cumulative)",     "Time",       "Customers Balked",
             r["times"][:len(r["balking"])], r["balking"],
             RED_BTN, True),

            ("Arrival Times",            "Customer #", "Arrival Time",
             list(range(len(r["arrival_times"]))), r["arrival_times"],
             "#1abc9c", False),
        ]

        fig, axes = plt.subplots(3, 2, figsize=(8, 6))
        fig.patch.set_facecolor("#1e1e1e")

        for ax, (title, xlabel, ylabel, x, y, color, step) in zip(axes.flat, plots):
            ax.set_facecolor("#252526")
            ax.tick_params(colors=TEXT, labelsize=8)
            ax.xaxis.label.set_color(TEXT)
            ax.yaxis.label.set_color(TEXT)
            ax.title.set_color(PURPLE_AH)
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
            ax.set_title(title,   fontsize=9, pad=6, fontweight="bold")

        fig.tight_layout(pad=2.0)

        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
