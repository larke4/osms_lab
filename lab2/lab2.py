# ОСМС, занятие 2 — радиопокрытие, вариант 20
# Исходные данные (см. задание):
#   Tx_BS = 46 дБм, Tx_UE = 24 дБм, 3 сектора/BS
#   Gain_BS = 21 дБи, Pen = 15 дБ, IM = 1 дБ
#   f = 1.8 ГГц, BW_DL = 20 МГц, BW_UL = 10 МГц, FDD
#   NF_BS = 2.4 дБ, NF_UE = 6 дБ, SINR_DL = 2 дБ, SINR_UL = 4 дБ
#   MIMO 2x2 (+3 дБ), фидеры есть -> 2.9 дБ
#   COST231 Hata для макросот, UMiNLOS для микро/фемто
#   Площадь макро = 100 км^2, бизнес-центры = 4 км^2
# Запуск: python osms_lab2_gui.py

import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

C = 3.0e8


# ---------------- МОДЕЛИ PL ----------------

def pl_umi_nlos(d_m, f_ghz):
    # (2.3): 26*log10(f_GHz) + 22.7 + 36.7*log10(d_m)
    return 26 * np.log10(f_ghz) + 22.7 + 36.7 * np.log10(d_m)


def pl_cost231_hata(d_m, f_mhz, hbs=30.0, hms=1.5, terrain="DU"):
    # (2.4)-(2.7) COST231 Hata. f в МГц, d в км.
    d_km = d_m / 1000.0
    if f_mhz < 1500:
        A, B = 69.55, 26.16
    else:
        A, B = 46.3, 33.9

    if terrain in ("DU", "U"):
        a = 3.2 * (math.log10(11.75 * hms)) ** 2 - 4.97
    else:
        a = ((1.1 * math.log10(f_mhz)) * hms
             - (1.56 * math.log10(f_mhz)) - 0.8)

    if d_km >= 1:
        s = 44.9 - 6.55 * math.log10(f_mhz)
    else:
        s = ((47.88 + 13.9 * math.log10(f_mhz)
              - 13.9 * math.log10(hbs)) / math.log10(50))

    clutter = {
        "DU": 3.0,
        "U": 0.0,
        "SU": -(2 * (math.log10(f_mhz / 28)) ** 2 + 5.4),
        "RURAL": -(4.78 * math.log10(f_mhz) ** 2
                   - 18.33 * math.log10(f_mhz) + 40.94),
        "ROAD": -(4.78 * math.log10(f_mhz) ** 2
                  - 18.33 * math.log10(f_mhz) + 35.94),
    }.get(terrain, 0.0)

    return (A + B * math.log10(f_mhz)
            - 13.82 * math.log10(hbs) - a
            + s * math.log10(max(d_km, 1e-3)) + clutter)


def pl_fspm(d_m, f_ghz):
    # (2.2) — для справки
    return 20 * np.log10(4 * np.pi * d_m * f_ghz * 1e9 / C)


# ---------------- БЮДЖЕТЫ ----------------

def thermal_noise(bw_hz):
    # (2.18)
    return -174 + 10 * math.log10(bw_hz)


def rx_sens(nf_db, bw_hz, sinr_db):
    # (2.17)
    return nf_db + thermal_noise(bw_hz) + sinr_db


def mapl_dl(tx_bs, feeder, gain_bs, mimo, im, pen, rx_ue):
    # (2.19)
    return tx_bs - feeder + gain_bs + mimo - im - pen - rx_ue


def mapl_ul(tx_ue, feeder, gain_bs, mimo, im, pen, rx_bs):
    # (2.20)
    return tx_ue - feeder + gain_bs + mimo - im - pen - rx_bs


def find_radius(mapl_db, pl_fn, d_max=30000.0):
    """Бинарный поиск d, где PL(d) = mapl_db. PL растёт с d."""
    lo, hi = 0.1, d_max
    if pl_fn(hi) < mapl_db:
        return float("nan")
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if pl_fn(mid) < mapl_db:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------- ГЕОМЕТРИЯ СЕТИ ----------------

def cells_required(total_area_km2, cell_radius_m, sectors=3):
    """
    Площадь одной секторной соты = (pi*d^2) / sectors.
    Число БС = ceil(total_area / (sectors * cell_area)).
    """
    if not math.isfinite(cell_radius_m) or cell_radius_m <= 0:
        return float("inf"), 0.0
    cell_area_km2 = math.pi * (cell_radius_m / 1000.0) ** 2 / sectors
    n = math.ceil(total_area_km2 / cell_area_km2)
    return cell_area_km2, n


# ---------------- GUI ----------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Лаба 2 ОСМС — радиопокрытие, вариант 20")
        self.geometry("1280x860")
        self.minsize(980, 680)
        self.configure(padx=8, pady=8)

        # Всё, что ниже — из задания, кроме FeederLoss.
        # FeederLoss = 2.0 + 0.4 + 0.5 = 2.9 дБ по рис. 2.4 методички (БС с фидером).
        self.v = {
            "f_ghz":     tk.DoubleVar(value=1.8),
            "bw_dl_mhz": tk.DoubleVar(value=20.0),
            "bw_ul_mhz": tk.DoubleVar(value=10.0),
            "nf_bs":     tk.DoubleVar(value=2.4),
            "nf_ue":     tk.DoubleVar(value=6.0),
            "sinr_dl":   tk.DoubleVar(value=2.0),
            "sinr_ul":   tk.DoubleVar(value=4.0),

            "tx_bs":     tk.DoubleVar(value=46.0),
            "tx_ue":     tk.DoubleVar(value=24.0),
            "gain_bs":   tk.DoubleVar(value=21.0),
            "mimo":      tk.DoubleVar(value=3.0),
            "im":        tk.DoubleVar(value=1.0),
            "pen":       tk.DoubleVar(value=15.0),
            "feeder":    tk.DoubleVar(value=2.9),
            "sectors":   tk.IntVar(value=3),

            "hbs_macro": tk.DoubleVar(value=30.0),
            "hms":       tk.DoubleVar(value=1.5),
            "terrain_macro": tk.StringVar(value="DU"),

            "area_macro_km2": tk.DoubleVar(value=100.0),
            "area_femto_km2": tk.DoubleVar(value=4.0),
        }
        self.status = tk.StringVar(value="готово")
        self.build()
        self.calc()

    def build(self):
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 6))
        ttk.Label(head, text="Лаба 2, вариант 20 — радиопокрытие",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(head, text="COST231 Hata для макросот, UMiNLOS для микро/фемто").pack(anchor="w")

        row = ttk.Frame(self)
        row.pack(fill="x", pady=(0, 6))

        g1 = ttk.LabelFrame(row, text="Радио", padding=8)
        g1.pack(side="left", fill="y", padx=(0, 6))
        self._row(g1, 0, "f, ГГц:", self.v["f_ghz"])
        self._row(g1, 1, "BW DL, МГц:", self.v["bw_dl_mhz"])
        self._row(g1, 2, "BW UL, МГц:", self.v["bw_ul_mhz"])
        self._row(g1, 3, "NF BS, дБ:", self.v["nf_bs"])
        self._row(g1, 4, "NF UE, дБ:", self.v["nf_ue"])
        self._row(g1, 5, "SINR DL, дБ:", self.v["sinr_dl"])
        self._row(g1, 6, "SINR UL, дБ:", self.v["sinr_ul"])

        g2 = ttk.LabelFrame(row, text="Бюджет", padding=8)
        g2.pack(side="left", fill="y", padx=(0, 6))
        self._row(g2, 0, "TxPower BS, дБм:", self.v["tx_bs"])
        self._row(g2, 1, "TxPower UE, дБм:", self.v["tx_ue"])
        self._row(g2, 2, "AntGain BS, дБи:", self.v["gain_bs"])
        self._row(g2, 3, "MIMOGain, дБ:", self.v["mimo"])
        self._row(g2, 4, "FeederLoss, дБ:", self.v["feeder"])
        self._row(g2, 5, "IM, дБ:", self.v["im"])
        self._row(g2, 6, "PenetrationM, дБ:", self.v["pen"])
        self._row(g2, 7, "Секторов на BS:", self.v["sectors"])

        g3 = ttk.LabelFrame(row, text="Макросоты (Hata)", padding=8)
        g3.pack(side="left", fill="y", padx=(0, 6))
        self._row(g3, 0, "hBS, м:", self.v["hbs_macro"])
        self._row(g3, 1, "hMS, м:", self.v["hms"])
        self._row(g3, 2, "Terrain:", self.v["terrain_macro"],
                  values=["DU", "U", "SU", "RURAL", "ROAD"])
        self._row(g3, 3, "Площадь, км²:", self.v["area_macro_km2"])

        g4 = ttk.LabelFrame(row, text="Микро/фемто (UMiNLOS)", padding=8)
        g4.pack(side="left", fill="y")
        self._row(g4, 0, "Площадь, км²:", self.v["area_femto_km2"])

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Пересчитать", command=self.calc).pack(side="left")
        ttk.Button(btns, text="Сохранить графики…", command=self.save_fig).pack(side="left", padx=6)
        ttk.Button(btns, text="Сохранить расчёты…", command=self.save_calc).pack(side="left")

        self.info = tk.StringVar()
        inf = ttk.LabelFrame(self, text="Результат", padding=8)
        inf.pack(fill="x", pady=(0, 6))
        ttk.Label(inf, textvariable=self.info, justify="left",
                  font=("Consolas", 10)).pack(anchor="w")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self.figs = {}
        self.cv = {}
        for key, title in [
            ("macro", "Макросоты: PL(d) и MAPL"),
            ("femto", "Микро/фемто: PL(d) и MAPL"),
            ("map",   "Планирование сети"),
            ("calc",  "Расчёты"),
        ]:
            fr = ttk.Frame(self.nb)
            self.nb.add(fr, text=title)
            if key == "calc":
                self.txt = tk.Text(fr, wrap="word", font=("Consolas", 10))
                scr = ttk.Scrollbar(fr, orient="vertical", command=self.txt.yview)
                self.txt.configure(yscrollcommand=scr.set, state="disabled")
                scr.pack(side="right", fill="y")
                self.txt.pack(side="left", fill="both", expand=True)
            else:
                fig = Figure(figsize=(8, 5), dpi=100, constrained_layout=True)
                canvas = FigureCanvasTkAgg(fig, master=fr)
                canvas.get_tk_widget().pack(fill="both", expand=True)
                tb = ttk.Frame(fr)
                tb.pack(fill="x")
                NavigationToolbar2Tk(canvas, tb, pack_toolbar=False).update()
                self.figs[key] = fig
                self.cv[key] = canvas

        ttk.Label(self, textvariable=self.status, relief="sunken",
                  anchor="w").pack(fill="x", pady=(6, 0))

    @staticmethod
    def _row(parent, row, label, var, values=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
        if values:
            ttk.Combobox(parent, textvariable=var, values=values,
                         state="readonly", width=10).grid(row=row, column=1, sticky="w", padx=4, pady=2)
        else:
            ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=1, sticky="w", padx=4, pady=2)

    def _params(self):
        g = lambda k: self.v[k].get()
        return dict(
            f_ghz=float(g("f_ghz")),
            bw_dl_hz=float(g("bw_dl_mhz")) * 1e6,
            bw_ul_hz=float(g("bw_ul_mhz")) * 1e6,
            nf_bs=float(g("nf_bs")), nf_ue=float(g("nf_ue")),
            sinr_dl=float(g("sinr_dl")), sinr_ul=float(g("sinr_ul")),
            tx_bs=float(g("tx_bs")), tx_ue=float(g("tx_ue")),
            gain_bs=float(g("gain_bs")), mimo=float(g("mimo")),
            im=float(g("im")), pen=float(g("pen")),
            feeder=float(g("feeder")), sectors=int(g("sectors")),
            hbs=float(g("hbs_macro")), hms=float(g("hms")),
            terrain=g("terrain_macro"),
            area_macro=float(g("area_macro_km2")),
            area_femto=float(g("area_femto_km2")),
        )

    def calc(self):
        try:
            p = self._params()
        except Exception as e:
            messagebox.showerror("ошибка", str(e))
            return

        # --- Бюджеты ---
        rx_ue = rx_sens(p["nf_ue"], p["bw_dl_hz"], p["sinr_dl"])   # DL
        rx_bs = rx_sens(p["nf_bs"], p["bw_ul_hz"], p["sinr_ul"])   # UL

        mapl_dl_db = mapl_dl(p["tx_bs"], p["feeder"], p["gain_bs"],
                             p["mimo"], p["im"], p["pen"], rx_ue)
        mapl_ul_db = mapl_ul(p["tx_ue"], p["feeder"], p["gain_bs"],
                             p["mimo"], p["im"], p["pen"], rx_bs)

        # --- Радиусы ---
        # макросота (COST231 Hata): PL(d) с f в МГц
        f_mhz = p["f_ghz"] * 1000.0
        hata = lambda d: pl_cost231_hata(d, f_mhz, p["hbs"], p["hms"], p["terrain"])
        d_ul_macro = find_radius(mapl_ul_db, hata)
        d_dl_macro = find_radius(mapl_dl_db, hata)
        d_cell_macro = min(d_ul_macro, d_dl_macro)

        # микро/фемто (UMiNLOS): PL(d) с f в ГГц
        umi = lambda d: pl_umi_nlos(d, p["f_ghz"])
        d_ul_femto = find_radius(mapl_ul_db, umi)
        d_dl_femto = find_radius(mapl_dl_db, umi)
        d_cell_femto = min(d_ul_femto, d_dl_femto)

        # --- Планирование ---
        area_macro_cell, n_bs_macro = cells_required(
            p["area_macro"], d_cell_macro, p["sectors"])
        area_femto_cell, n_bs_femto = cells_required(
            p["area_femto"], d_cell_femto, p["sectors"])

        def fmt_d(x):
            return "нет покрытия" if math.isnan(x) else f"{x:.1f} м ({x/1000:.3f} км)"

        self.info.set(
            f"RxSens DL (UE) = {rx_ue:.2f} дБм | RxSens UL (BS) = {rx_bs:.2f} дБм\n"
            f"MAPL_DL = {mapl_dl_db:.2f} дБ | MAPL_UL = {mapl_ul_db:.2f} дБ\n"
            f"МАКРО:  d_DL = {fmt_d(d_dl_macro)},  d_UL = {fmt_d(d_ul_macro)},  "
            f"радиус = {fmt_d(d_cell_macro)}\n"
            f"        S_соты = {area_macro_cell:.3f} км²,  БС = {n_bs_macro} (3 сектора)\n"
            f"ФЕМТО:  d_DL = {fmt_d(d_dl_femto)},  d_UL = {fmt_d(d_ul_femto)},  "
            f"радиус = {fmt_d(d_cell_femto)}\n"
            f"        S_соты = {area_femto_cell:.4f} км²,  БС = {n_bs_femto} (3 сектора)"
        )

        self._plot_macro(p, hata, mapl_dl_db, mapl_ul_db, d_dl_macro, d_ul_macro)
        self._plot_femto(p, umi, mapl_dl_db, mapl_ul_db, d_dl_femto, d_ul_femto)
        self._plot_map(p, n_bs_macro, n_bs_femto, d_cell_macro, d_cell_femto)
        self._fill_calc(p, rx_ue, rx_bs, mapl_dl_db, mapl_ul_db,
                        d_dl_macro, d_ul_macro, d_cell_macro,
                        d_dl_femto, d_ul_femto, d_cell_femto,
                        area_macro_cell, n_bs_macro,
                        area_femto_cell, n_bs_femto)
        self.status.set("пересчитано")

    def _plot_curve(self, key, p, pl_fn, mapl_dl_db, mapl_ul_db, d_dl, d_ul, title):
        fig = self.figs[key]
        fig.clear()
        ax = fig.add_subplot(111)
        d = np.logspace(-1, math.log10(30000), 400)
        pl = np.array([pl_fn(x) for x in d])
        ax.semilogx(d, pl, label="PL(d)", lw=1.6)
        ax.axhline(mapl_dl_db, color="C1", ls="--", label=f"MAPL_DL = {mapl_dl_db:.1f} дБ")
        ax.axhline(mapl_ul_db, color="C2", ls=":", label=f"MAPL_UL = {mapl_ul_db:.1f} дБ")
        if not math.isnan(d_dl):
            ax.axvline(d_dl, color="C1", alpha=.4)
        if not math.isnan(d_ul):
            ax.axvline(d_ul, color="C2", alpha=.4)
        ax.set(xlabel="d, м", ylabel="PL, дБ", title=title)
        ax.set_xlim(1, 30000)
        ax.grid(True, which="both", alpha=.3)
        ax.legend(fontsize=8)
        self.cv[key].draw()

    def _plot_macro(self, p, pl_fn, mapl_dl_db, mapl_ul_db, d_dl, d_ul):
        self._plot_curve("macro", p, pl_fn, mapl_dl_db, mapl_ul_db, d_dl, d_ul,
                         f"COST231 Hata, f={p['f_ghz']:g} ГГц")

    def _plot_femto(self, p, pl_fn, mapl_dl_db, mapl_ul_db, d_dl, d_ul):
        self._plot_curve("femto", p, pl_fn, mapl_dl_db, mapl_ul_db, d_dl, d_ul,
                         f"UMiNLOS, f={p['f_ghz']:g} ГГц")

    def _plot_map(self, p, n_macro, n_femto, d_macro, d_femto):
        fig = self.figs["map"]
        fig.clear()
        ax = fig.add_subplot(111)
        labels = ["Макро БС\n(100 км²)", "Микро/фемто БС\n(4 км²)"]
        counts = [n_macro, n_femto]
        bars = ax.bar(labels, counts, color=["C0", "C3"])
        for b, v in zip(bars, counts):
            ax.text(b.get_x() + b.get_width() / 2, v,
                    f"{v}", ha="center", va="bottom", fontsize=12)
        ax.set(ylabel="Число БС", title="Планирование сети: число базовых станций")
        ax.grid(True, axis="y", alpha=.3)
        ax.text(0.02, 0.98,
                f"Радиус макро: {d_macro:.1f} м\n"
                f"Радиус фемто: {d_femto:.1f} м\n"
                f"Секторов на БС: {p['sectors']}",
                transform=ax.transAxes, va="top", fontsize=9,
                bbox=dict(boxstyle="round", fc="white", ec="gray"))
        self.cv["map"].draw()

    def _fill_calc(self, p, rx_ue, rx_bs, mapl_dl_db, mapl_ul_db,
                   d_dl_macro, d_ul_macro, d_cell_macro,
                   d_dl_femto, d_ul_femto, d_cell_femto,
                   area_macro_cell, n_bs_macro,
                   area_femto_cell, n_bs_femto):
        tn_dl = thermal_noise(p["bw_dl_hz"])
        tn_ul = thermal_noise(p["bw_ul_hz"])

        def s(x):
            return "нет покрытия" if math.isnan(x) else f"{x:.2f}"

        lines = [
            "ПОШАГОВЫЕ РАСЧЁТЫ, вариант 20",
            "=" * 60,
            "1. Исходные данные",
            f"   f = {p['f_ghz']:g} ГГц, FDD: BW_DL = {p['bw_dl_hz']/1e6:g} МГц, "
            f"BW_UL = {p['bw_ul_hz']/1e6:g} МГц",
            f"   Tx_BS = {p['tx_bs']:g} дБм, Tx_UE = {p['tx_ue']:g} дБм",
            f"   Gain_BS = {p['gain_bs']:g} дБи, MIMO = {p['mimo']:g} дБ (2x2)",
            f"   FeederLoss = {p['feeder']:g} дБ (фидер 2.0 + МШУ 0.4 + джампер 0.5)",
            f"   IM = {p['im']:g} дБ, Pen = {p['pen']:g} дБ",
            f"   NF_BS = {p['nf_bs']:g} дБ, NF_UE = {p['nf_ue']:g} дБ",
            f"   SINR_DL = {p['sinr_dl']:g} дБ, SINR_UL = {p['sinr_ul']:g} дБ",
            "",
            "2. Тепловой шум (2.18)",
            f"   DL: ThermalNoise = -174 + 10*log10({p['bw_dl_hz']:.3e}) = {tn_dl:.2f} дБм",
            f"   UL: ThermalNoise = -174 + 10*log10({p['bw_ul_hz']:.3e}) = {tn_ul:.2f} дБм",
            "",
            "3. Чувствительность приёмников (2.17)",
            f"   DL (приёмник UE): RxSens = NF_UE + TN_DL + SINR_DL = "
            f"{p['nf_ue']:g} + {tn_dl:.2f} + {p['sinr_dl']:g} = {rx_ue:.2f} дБм",
            f"   UL (приёмник BS): RxSens = NF_BS + TN_UL + SINR_UL = "
            f"{p['nf_bs']:g} + {tn_ul:.2f} + {p['sinr_ul']:g} = {rx_bs:.2f} дБм",
            "",
            "4. MAPL_DL (2.19)",
            "   Tx_BS - Feeder + Gain + MIMO - MAPL_DL - IM - Pen = RxSens_UE",
            f"   MAPL_DL = {p['tx_bs']:g} - {p['feeder']:g} + {p['gain_bs']:g} + "
            f"{p['mimo']:g} - {p['im']:g} - {p['pen']:g} - {rx_ue:.2f} = "
            f"{mapl_dl_db:.2f} дБ",
            "",
            "5. MAPL_UL (2.20)",
            "   Tx_UE - Feeder + Gain + MIMO - MAPL_UL - IM - Pen = RxSens_BS",
            f"   MAPL_UL = {p['tx_ue']:g} - {p['feeder']:g} + {p['gain_bs']:g} + "
            f"{p['mimo']:g} - {p['im']:g} - {p['pen']:g} - {rx_bs:.2f} = "
            f"{mapl_ul_db:.2f} дБ",
            "",
            "6. Макросоты — COST231 Hata (2.4)-(2.7)",
            f"   f = {p['f_ghz']*1000:g} МГц, hBS = {p['hbs']:g} м, hMS = {p['hms']:g} м, "
            f"terrain = {p['terrain']}",
            f"   A = 46.3, B = 33.9 (1500-2000 МГц)",
            f"   d_DL = {s(d_dl_macro)} м, d_UL = {s(d_ul_macro)} м",
            f"   d_cell = min(d_UL, d_DL) = {s(d_cell_macro)} м",
            "",
            "7. Микро/фемто — UMiNLOS (2.3)",
            f"   PL(d) = 26*log10(f_ГГц) + 22.7 + 36.7*log10(d)",
            f"   d_DL = {s(d_dl_femto)} м, d_UL = {s(d_ul_femto)} м",
            f"   d_cell = min(d_UL, d_DL) = {s(d_cell_femto)} м",
            "",
            "8. Планирование сети",
            f"   Формула: n_BS = ceil( S_территории / (π*d_cell² / sectors) )",
            f"   sectors = {p['sectors']}",
            "",
            f"   МАКРО (S = {p['area_macro']:g} км²):",
            f"     площадь сектора = π*({s(d_cell_macro)}/1000)² / {p['sectors']} = "
            f"{area_macro_cell:.4f} км²",
            f"     n_BS = ceil({p['area_macro']:g} / {area_macro_cell:.4f}) = {n_bs_macro}",
            "",
            f"   МИКРО/ФЕМТО (S = {p['area_femto']:g} км²):",
            f"     площадь сектора = π*({s(d_cell_femto)}/1000)² / {p['sectors']} = "
            f"{area_femto_cell:.6f} км²",
            f"     n_BS = ceil({p['area_femto']:g} / {area_femto_cell:.6f}) = {n_bs_femto}",
            "",
            "9. Примечания",
            "   Формулы (2.3)-(2.7), (2.17)-(2.20) — из методички.",
            "   FeederLoss = 2.0 + 0.4 + 0.5 = 2.9 дБ — по рис. 2.4 (БС с фидером).",
            "   MIMOGain = +3 дБ для 2x2 — методичка, стр. 7.",
            "   Бинарный поиск d при PL(d)=MAPL — численный метод;",
            "   в методичке (рис. 2.6) то же самое находилось графически.",
            "   Число БС округляется вверх: ceil(...).",
        ]
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(lines))
        self.txt.configure(state="disabled")

    def save_fig(self):
        i = self.nb.index(self.nb.select())
        keys = ["macro", "femto", "map"]
        if i >= len(keys):
            self.save_calc()
            return
        key = keys[i]
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf")])
        if not path:
            return
        try:
            self.figs[key].savefig(path, dpi=180, bbox_inches="tight")
            self.status.set("график сохранён")
        except Exception as e:
            messagebox.showerror("ошибка", str(e))

    def save_calc(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("TXT", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.txt.get("1.0", "end-1c"))
            self.status.set("расчёты сохранены")
        except Exception as e:
            messagebox.showerror("ошибка", str(e))


if __name__ == "__main__":
    App().mainloop()