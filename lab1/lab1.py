# ОСМС, занятие 1, вариант 20
# y(t) = 7*cos(2*pi*20*t + pi/3)
# pip install numpy matplotlib
# pip install pygame          # опционально, для mp3

import os
import re
import sys
import tkinter as tk
import wave
from tkinter import ttk, filedialog, messagebox
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

A = 7.0
F0 = 20.0
PHI = np.pi / 3

# mp3 кладём рядом с .py и называем max_verstappen.mp3
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEM_MP3 = os.path.join(BASE_DIR, "max_verstappen.mp3")


def signal(t):
    return A * np.cos(2 * np.pi * F0 * t + PHI)


def dft(x):
    x = np.asarray(x, dtype=complex)
    n = x.size
    if n == 0:
        return np.array([], dtype=complex)
    k = np.arange(n)
    W = np.exp(-2j * np.pi * np.outer(k, k) / n)
    return W @ x


def idft(X):
    X = np.asarray(X, dtype=complex)
    n = X.size
    if n == 0:
        return np.array([], dtype=complex)
    k = np.arange(n)
    W = np.exp(-2j * np.pi * np.outer(k, k) / n)
    return (W.conj().T @ X) / n


def spectrum(x, fs, max_n=None):
    x = np.asarray(x, dtype=complex)
    if max_n is not None and x.size > max_n:
        x = x[:max_n]
    n = x.size
    if n == 0:
        return np.array([]), np.array([])
    X = dft(x)
    freqs = np.arange(n // 2 + 1) * (fs / n)
    amps = 2.0 * np.abs(X[: n // 2 + 1]) / n
    amps[0] /= 2
    if n % 2 == 0:
        amps[-1] /= 2
    return freqs, amps


PRESETS = {
    "Кузнечик":
        "G4 G4 C5 C5 C5 C5 D5 C5 B4 A4 A4 A4 A4 B4 A4 G4 "
        "G4 G4 C5 C5 C5 C5 D5 C5 B4 A4 A4 A4 A4 G4 G4 - "
        "G4 G4 C5 C5 C5 C5 D5 C5 B4 A4 A4 A4 A4 B4 A4 G4 "
        "G4 G4 C5 C5 C5 C5 D5 C5 B4 A4 A4 A4 A4 G4 G4 -",
    "Ёлочка":
        "C4 C4 C4 E4 E4 D4 D4 C4 D4 E4 F4 F4 E4 "
        "E4 E4 D4 D4 E4 E4 D4 C4 C4 C4 E4 E4 D4 D4 C4",
    "Собачий вальс":
        "A4 B4 C5 B4 A4 B4 C5 A4 "
        "B4 C5 D5 C5 B4 A4 B4 A4 "
        "A4 B4 C5 B4 A4 B4 C5 A4 "
        "D5 C5 B4 A4 G4 A4 B4 A4",
    "Max Verstappen (bass)":
        "A2 A2 A2 E3 E3 E3 C3 B2 "
        "A2 A2 A2 E3 E3 E3 C3 B2",

    # Мелодия "du du du du" — подбор на слух, не официальная партитура.
    # Если найдёте точные ноты — замените строку.
    "Max Verstappen (melody)":
        "A4 A4 A4 A4 G4 A4 - A4 G4 F4 E4",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Лаба 1 ОСМС - вариант 20")
        self.geometry("1180x800")
        self.minsize(900, 650)
        self.configure(padx=10, pady=10)

        self.fs_mult = tk.StringVar(value="1x")
        self.bits = tk.IntVar(value=3)
        self.dur = tk.DoubleVar(value=1.0)
        self.status = tk.StringVar(value="готово")
        self.build()
        self.draw()
        self.recalc()

    def build(self):
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 8))
        ttk.Label(head, text="Лаба 1, вариант 20",
                  font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(head, text="y(t) = 7*cos(2*pi*20*t + pi/3)").pack(anchor="w")

        ctrl = ttk.LabelFrame(self, text="Параметры", padding=10)
        ctrl.pack(fill="x", pady=(0, 8))

        ttk.Label(ctrl, text="Fs:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        cb = ttk.Combobox(ctrl, textvariable=self.fs_mult, values=["1x", "2x", "4x", "10x"],
                          state="readonly", width=8)
        cb.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.draw())

        ttk.Label(ctrl, text="Длительность, с:").grid(row=0, column=2, sticky="w", padx=(18, 5), pady=4)
        sp = ttk.Spinbox(ctrl, from_=0.1, to=5.0, increment=0.1,
                         textvariable=self.dur, width=8, command=self.draw)
        sp.grid(row=0, column=3, sticky="w", padx=5, pady=4)
        sp.bind("<Return>", lambda e: self.draw())

        ttk.Label(ctrl, text="Биты АЦП:").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        bcb = ttk.Combobox(ctrl, textvariable=self.bits, values=[3, 4, 5, 6],
                           state="readonly", width=8)
        bcb.grid(row=1, column=1, sticky="w", padx=5, pady=4)
        bcb.bind("<<ComboboxSelected>>", lambda e: self.draw_quant())

        ttk.Button(ctrl, text="Построить", command=self.draw).grid(row=0, column=4, padx=(18, 5), pady=4)
        ttk.Button(ctrl, text="Квантование", command=self.draw_quant).grid(row=1, column=4, padx=(18, 5), pady=4)
        ttk.Button(ctrl, text="Сохранить", command=self.save_fig).grid(row=0, column=5, rowspan=2, padx=5, pady=4)

        self.info = tk.StringVar()
        info = ttk.LabelFrame(self, text="Параметры сигнала", padding=8)
        info.pack(fill="x", pady=(0, 8))
        ttk.Label(info, textvariable=self.info, justify="left").pack(anchor="w")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self.figs = {}
        self.cv = {}
        self.tabs = {}
        for key, title in [
            ("time", "Время"),
            ("spec", "Спектр"),
            ("rec", "Восстановление"),
            ("quant", "Квантование"),
            ("song", "Мелодия"),
        ]:
            fr = ttk.Frame(self.nb)
            self.nb.add(fr, text=title)
            self.tabs[key] = fr
            fig = Figure(figsize=(8, 4.6), dpi=100, constrained_layout=True)
            canvas = FigureCanvasTkAgg(fig, master=fr)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            tb = ttk.Frame(fr)
            tb.pack(fill="x")
            NavigationToolbar2Tk(canvas, tb, pack_toolbar=False).update()
            self.figs[key] = fig
            self.cv[key] = canvas

        # панель мелодии
        sf = ttk.Frame(self.tabs["song"])
        sf.pack(fill="x", padx=8, pady=6, before=self.cv["song"].get_tk_widget())
        ttk.Label(sf, text="Ноты:").grid(row=0, column=0, sticky="w")
        self.notes = tk.StringVar(
            value="C4 D4 E4 G4 E4 D4 C4 - E4 E4 G4 G4 A4 A4 G4")
        ttk.Entry(sf, textvariable=self.notes, width=60).grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Label(sf, text="BPM:").grid(row=1, column=0, sticky="w", pady=4)
        self.bpm = tk.IntVar(value=120)
        ttk.Spinbox(sf, from_=40, to=240, increment=5, textvariable=self.bpm,
                    width=8).grid(row=1, column=1, sticky="w", padx=5, pady=4)
        ttk.Button(sf, text="Синтез", command=self.synth).grid(row=1, column=1, sticky="w", padx=(100, 0), pady=4)
        ttk.Button(sf, text="Играть", command=self.play).grid(row=1, column=1, sticky="w", padx=(180, 0), pady=4)
        ttk.Button(sf, text="WAV", command=self.save_wav).grid(row=1, column=1, sticky="w", padx=(260, 0), pady=4)
        ttk.Button(sf, text="MP3", command=self.play_mp3).grid(row=1, column=1, sticky="w", padx=(330, 0), pady=4)
        ttk.Button(sf, text="Стоп", command=self.stop_mp3).grid(row=1, column=1, sticky="w", padx=(410, 0), pady=4)
        sf.columnconfigure(1, weight=1)

        pf = ttk.LabelFrame(self.tabs["song"], text="Готовые", padding=6)
        pf.pack(fill="x", padx=8, pady=(0, 6), before=self.cv["song"].get_tk_widget())
        for name in PRESETS:
            ttk.Button(pf, text=name, command=lambda n=name: self.load(n)).pack(side="left", padx=4, pady=2)

        self.audio = np.array([], dtype=np.float32)
        self.song_fs = 22050

        # вкладка расчётов
        cf = ttk.Frame(self.nb)
        self.nb.add(cf, text="Расчёты")
        ctop = ttk.Frame(cf)
        ctop.pack(fill="x", padx=8, pady=6)
        ttk.Button(ctop, text="Пересчитать", command=self.recalc).pack(side="left")
        ttk.Button(ctop, text="Сохранить", command=self.save_calc).pack(side="left", padx=8)
        self.txt = tk.Text(cf, wrap="word", font=("Consolas", 10), height=25)
        scr = ttk.Scrollbar(cf, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=scr.set, state="disabled")
        scr.pack(side="right", fill="y", pady=(0, 8))
        self.txt.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))

        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", pady=(8, 0))

    def load(self, name):
        text = PRESETS[name]
        if not text.strip():
            self.status.set(f"«{name}»: нот нет, играю mp3")
            self.play_mp3()
            return
        self.notes.set(text)
        self.synth()

    def get_fs(self):
        m = self.fs_mult.get()
        k = 1 if m.startswith("1") else int(m.rstrip("x"))
        return 2 * F0 * k

    def data(self):
        d = float(self.dur.get())
        if d <= 0:
            raise ValueError("длительность > 0")
        fs = self.get_fs()
        n = max(2, int(round(fs * d)))
        t = np.arange(n) / fs
        y = signal(t)
        tf = np.linspace(0, d, max(2000, int(d * 2000)), endpoint=False)
        return d, fs, t, y, tf, signal(tf)

    def draw(self):
        try:
            d, fs, t, y, tf, yf = self.data()
        except Exception as e:
            messagebox.showerror("ошибка", str(e))
            return
        n = len(y)
        self.info.set(
            f"Fs = {fs:g} Гц, Ts = {1/fs:.5f} с, N = {n}, "
            f"порог Котельникова = {2*F0:g} Гц, память = {y.nbytes} байт"
        )

        fig = self.figs["time"]
        fig.clear()
        ax = fig.add_subplot(111)
        ax.plot(tf, yf, label="сигнал")
        ax.stem(t, y, linefmt="C1-", markerfmt="C1o", basefmt=" ", label="отсчёты")
        ax.set(xlabel="t, с", ylabel="y")
        ax.grid(alpha=.3)
        ax.legend()
        self.cv["time"].draw()

        fig = self.figs["spec"]
        fig.clear()
        ax = fig.add_subplot(111)
        fr, sp = spectrum(y, fs)
        ax.plot(fr, sp)
        ax.set(xlabel="f, Гц", ylabel="|Y|")
        ax.set_xlim(0, min(fs / 2, max(100, F0 * 3)))
        ax.grid(alpha=.3)
        self.cv["spec"].draw()

        fig = self.figs["rec"]
        fig.clear()
        ax = fig.add_subplot(111)
        ax.plot(tf, yf, label="исходный")
        ax.plot(t, y, "o-", ms=3, lw=1, label="по отсчётам")
        ax.set(xlabel="t, с", ylabel="y")
        ax.grid(alpha=.3)
        ax.legend()
        self.cv["rec"].draw()

        self.draw_quant()
        self.status.set(f"Fs={fs:g} Гц, N={n}")

    def draw_quant(self):
        try:
            _, fs, t, y, tf, yf = self.data()
        except Exception as e:
            messagebox.showerror("ошибка", str(e))
            return
        b = int(self.bits.get())
        L = 2 ** b
        step = 2 * A / (L - 1)
        q = np.clip(np.round((y + A) / step) * step - A, -A, A)
        err = q - y
        mae = float(np.mean(np.abs(err)))
        mse = float(np.mean(err ** 2))

        fig = self.figs["quant"]
        fig.clear()
        ax = fig.add_subplot(211)
        ax.plot(t, y, label="до")
        ax.step(t, q, where="mid", label=f"{b} бит")
        ax.set(ylabel="y")
        ax.grid(alpha=.3)
        ax.legend()

        ax2 = fig.add_subplot(212)
        fr, o = spectrum(y, fs)
        _, qq = spectrum(q, fs)
        ax2.plot(fr, o, label="до")
        ax2.plot(fr, qq, label="после")
        ax2.set(title=f"MAE={mae:.4f}  MSE={mse:.5f}", xlabel="f, Гц", ylabel="|Y|")
        ax2.set_xlim(0, min(fs / 2, 150))
        ax2.grid(alpha=.3)
        ax2.legend()
        self.cv["quant"].draw()
        self.recalc()

    @staticmethod
    def note_freq(n):
        if n == "-":
            return 0.0
        m = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d+)", n.strip())
        if not m:
            raise ValueError(f"нота «{n}»?")
        letter, acc, octv = m.groups()
        semis = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        midi = (int(octv) + 1) * 12 + semis[letter.upper()]
        if acc == "#":
            midi += 1
        elif acc == "b":
            midi -= 1
        return 440.0 * (2.0 ** ((midi - 69) / 12.0))

    def synth(self):
        try:
            toks = self.notes.get().replace(",", " ").split()
            if not toks:
                raise ValueError("пусто")
            bpm = int(self.bpm.get())
            fs = self.song_fs
            dur = 60.0 / bpm
            chunks = []
            for tok in toks:
                f = self.note_freq(tok)
                cnt = int(fs * dur)
                tt = np.arange(cnt) / fs
                s = np.sin(2 * np.pi * f * tt) if f else np.zeros(cnt)
                k = min(int(0.012 * fs), cnt // 2)
                if k > 0:
                    w = np.linspace(0, 1, k)
                    s[:k] *= w
                    s[-k:] *= w[::-1]
                chunks.append(s)
            a = np.concatenate(chunks)
            p = np.max(np.abs(a)) if len(a) else 1.0
            if p > 0:
                a = 0.8 * a / p
            self.audio = a.astype(np.float32)

            fig = self.figs["song"]
            fig.clear()
            tt = np.arange(len(self.audio)) / fs

            ax = fig.add_subplot(311)
            ax.plot(tt, self.audio, lw=0.65)
            ax.set(title="мелодия", xlabel="t, с", ylabel="y")
            ax.grid(alpha=.3)

            axz = fig.add_subplot(312)
            ze = min(0.025, len(self.audio) / fs)
            zc = max(2, int(ze * fs))
            axz.plot(tt[:zc], self.audio[:zc], lw=1.1)
            axz.set(title="фрагмент", xlabel="t, с", ylabel="y")
            axz.grid(alpha=.3)

            axs = fig.add_subplot(313)
            fr, sp = spectrum(self.audio, fs, max_n=4096)
            axs.plot(fr, sp, lw=0.8)
            axs.set(title="спектр", xlabel="f, Гц", ylabel="|Y|")
            axs.set_xlim(0, 1200)
            axs.grid(alpha=.3)
            fig.set_size_inches(8, 7.5, forward=True)
            fig.tight_layout()
            self.cv["song"].draw()
            self.nb.select(self.tabs["song"])
            self.recalc()
            self.status.set(f"{len(toks)} нот, {len(a)/fs:.2f} с")
        except Exception as e:
            messagebox.showerror("синтез", str(e))

    def play(self):
        if not len(self.audio):
            self.synth()
        if not len(self.audio):
            return
        try:
            import sounddevice as sd
            sd.play(self.audio, self.song_fs)
            self.status.set("играю")
        except ImportError:
            messagebox.showerror("нет sounddevice", "pip install sounddevice")
        except Exception as e:
            messagebox.showerror("play", str(e))

    def play_mp3(self):
        """Сначала pygame, потом системный плеер."""
        if not os.path.isfile(MEM_MP3):
            messagebox.showerror(
                "нет файла",
                f"Не найден:\n{MEM_MP3}\n\n"
                "Положите mp3 рядом с .py и назовите max_verstappen.mp3"
            )
            return
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(MEM_MP3)
            pygame.mixer.music.play()
            self.status.set("mp3 играет")
            return
        except ImportError:
            pass
        except Exception as e:
            messagebox.showerror("pygame", str(e))
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(MEM_MP3)
            elif sys.platform == "darwin":
                os.system(f'open "{MEM_MP3}"')
            else:
                os.system(f'xdg-open "{MEM_MP3}"')
            self.status.set("mp3 в системном плеере")
        except Exception as e:
            messagebox.showerror("mp3", str(e))

    def stop_mp3(self):
        try:
            import pygame
            pygame.mixer.music.stop()
            self.status.set("mp3 стоп")
        except Exception:
            pass

    def save_wav(self):
        if not len(self.audio):
            self.synth()
        if not len(self.audio):
            return
        p = filedialog.asksaveasfilename(defaultextension=".wav",
                                         filetypes=[("WAV", "*.wav")])
        if not p:
            return
        try:
            pcm = np.int16(np.clip(self.audio, -1, 1) * 32767)
            with wave.open(p, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.song_fs)
                w.writeframes(pcm.tobytes())
            self.status.set("ok")
        except Exception as e:
            messagebox.showerror("wav", str(e))

    def recalc(self):
        try:
            d, fs, t, y, tf, yf = self.data()
            n = len(y)
            b = int(self.bits.get())
            L = 2 ** b
            step = 2 * A / (L - 1)
            q = np.clip(np.round((y + A) / step) * step - A, -A, A)
            err = q - y
            mae = float(np.mean(np.abs(err)))
            mse = float(np.mean(err ** 2))

            fr, sp = spectrum(y, fs)
            if sp.size > 1:
                pi_ = int(np.argmax(sp[1:]) + 1)
                pf = float(fr[pi_])
                pa = float(sp[pi_])
            else:
                pf, pa = 0.0, 0.0

            rec = idft(dft(y)).real
            rerr = float(np.max(np.abs(rec - y)))

            lines = [
                "РАСЧЁТЫ, вариант 20",
                "",
                "1. Сигнал",
                f"   y(t) = {A:g}*cos(2*pi*{F0:g}*t + pi/3)",
                f"   omega = {2*np.pi*F0:.4f} рад/с, T = {1/F0:.4f} с",
                f"   y(0) = {signal(np.array([0.0]))[0]:.4f} (ожидается 3.5)",
                "",
                "2. Дискретизация",
                f"   Fs = {fs:g} Гц, Ts = {1/fs:.6f} с",
                f"   N = {n}, dF = {fs/n:.4f} Гц",
                f"   Котельников: Fs >= {2*F0:g} -> {'ok' if fs >= 2*F0 else 'НЕТ'}",
                "",
                "3. Первые 10 отсчётов",
            ]
            for i in range(min(10, n)):
                lines.append(f"   {i:2d}  {t[i]:.6f}  {y[i]: .6f}")

            lines += [
                "",
                "4. Спектр (ручное ДПФ)",
                f"   пик: {pf:.3f} Гц, амплитуда {pa:.4f}",
                f"   ожидание: {F0:g} Гц, ошибка {abs(pf - F0):.4f} Гц",
                "",
                "5. Квантование (метрики не из методички, стандартные из ЦОС)",
                f"   {b} бит -> {L} уровней, шаг Delta = 2A/(L-1) = {step:.6f}",
                f"   MAE = mean(|q-y|) = {mae:.6f}",
                f"   MSE = mean((q-y)^2) = {mse:.6f}",
                "",
                "6. Проверка ОПФ",
                f"   max|idft(dft(y)) - y| = {rerr:.2e}",
                "",
                "7. Мелодия",
            ]
            toks = self.notes.get().replace(",", " ").split()
            bpm = max(1, int(self.bpm.get()))
            lines.append(f"   {len(toks)} нот, BPM = {bpm}, одна нота = {60/bpm:.4f} с")
            for tok in toks[:8]:
                try:
                    f = self.note_freq(tok)
                    lines.append(f"   {tok}: {'пауза' if f == 0 else f'{f:.2f} Гц'}")
                except ValueError:
                    lines.append(f"   {tok}: ???")
            if len(toks) > 8:
                lines.append("   ...")

            self.txt.configure(state="normal")
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", "\n".join(lines))
            self.txt.configure(state="disabled")
        except Exception as e:
            self.txt.configure(state="normal")
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", f"ошибка: {e}")
            self.txt.configure(state="disabled")

    def save_calc(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt",
                                         filetypes=[("TXT", "*.txt")])
        if not p:
            return
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.txt.get("1.0", "end-1c"))
            self.status.set("ok")
        except Exception as e:
            messagebox.showerror("txt", str(e))

    def save_fig(self):
        i = self.nb.index(self.nb.select())
        if i == len(self.figs):
            self.save_calc()
            return
        key = ["time", "spec", "rec", "quant", "song"][i]
        p = filedialog.asksaveasfilename(defaultextension=".png",
                                         filetypes=[("PNG", "*.png"), ("PDF", "*.pdf")])
        if not p:
            return
        try:
            self.figs[key].savefig(p, dpi=180, bbox_inches="tight")
            self.status.set("ok")
        except Exception as e:
            messagebox.showerror("png", str(e))


if __name__ == "__main__":
    App().mainloop()