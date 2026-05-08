"""
main.py
-------
Erenler Cumhuriyet Ortaokulu – Öğrenci Takip ve Disiplin Uygulaması
Kurulum : pip install customtkinter
Çalıştır: python main.py
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import tkinter as tk
import math, time, datetime, os, subprocess, sys
from database import (
    initialize_db, KRITERLER,
    tum_ogretmenler, tum_sifre_listesi, ogretmen_dogrula,
    ogretmen_id_bul, ogretmen_siniflari,
    sinif_ogrencileri, tum_siniflar_ogrencileri, ogrenci_tik_gecmisi,
    tik_ekle, tek_ogrenci_sifirla, sinif_sifirla, tum_tikleri_sifirla,
)
from export import excel_raporu_olustur, OPENPYXL_OK

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ── Renk paleti ────────────────────────────────────────────────────────────
C_HEADER   = "#1a3a6b"
C_SIDEBAR  = "#eef2fb"
C_CARD_0   = "#f8faff"   # 0 tik
C_CARD_1   = "#fffbeb"   # 1-2 tik
C_CARD_3   = "#fff1f1"   # 3+ tik
C_ACCENT   = "#2563eb"
C_DANGER   = "#dc2626"
C_WARN     = "#d97706"
C_MUTED    = "#64748b"
C_BORDER_0 = "#dde5f7"
C_BORDER_1 = "#fcd34d"
C_BORDER_3 = "#fca5a5"

SIFIR_PAROLA = "1234"    # Toplu sıfırlama parolası


# ══════════════════════════════════════════════════════════════════════════
# Yardımcı: Tik badge string + renk
# ══════════════════════════════════════════════════════════════════════════

def _tik_renk(sayi: int) -> tuple[str, str, str]:
    """(kart_bg, kenar_renk, badge_renk) döndürür."""
    if sayi == 0:
        return C_CARD_0, C_BORDER_0, C_MUTED
    elif sayi <= 2:
        return C_CARD_1, C_BORDER_1, C_WARN
    else:
        return C_CARD_3, C_BORDER_3, C_DANGER


def _nokta_str(sayi: int) -> str:
    if sayi == 0:
        return "○ ○ ○"
    elif sayi == 1:
        return "● ○ ○"
    elif sayi == 2:
        return "● ● ○"
    else:
        return f"● ● ●" + (f"  +{sayi - 3}" if sayi > 3 else "")


# ══════════════════════════════════════════════════════════════════════════
# Kriter Seçim Dialogu
# ══════════════════════════════════════════════════════════════════════════

class KriterDialog(ctk.CTkToplevel):
    def __init__(self, parent, ogrenci_adi: str):
        super().__init__(parent)
        self.title("İhlal Kriteri Seç")
        self.geometry("520x560")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus()

        self.secilen = None

        # Başlık
        ctk.CTkLabel(
            self, text=f"📋  {ogrenci_adi}",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(16, 2))
        ctk.CTkLabel(
            self, text="İhlal kategorisini seçin:",
            font=ctk.CTkFont(size=12), text_color=C_MUTED
        ).pack(pady=(0, 10))

        # 2 sütunlu grid
        grid = ctk.CTkScrollableFrame(self, height=440)
        grid.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        grid.grid_columnconfigure((0, 1), weight=1)

        for i, (emoji, ad) in enumerate(KRITERLER):
            row, col = divmod(i, 2)
            ctk.CTkButton(
                grid,
                text=f"{emoji}  {ad}",
                height=40,
                font=ctk.CTkFont(size=12),
                fg_color="#f1f5fe",
                text_color="#1e3a7b",
                hover_color="#dbeafe",
                border_width=1,
                border_color="#bfdbfe",
                anchor="w",
                command=lambda k=f"{emoji} {ad}": self._sec(k)
            ).grid(row=row, column=col, padx=4, pady=3, sticky="ew")

    def _sec(self, kriter: str):
        self.secilen = kriter
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════
# Tik Geçmişi Dialogu
# ══════════════════════════════════════════════════════════════════════════

class GecmisDialog(ctk.CTkToplevel):
    def __init__(self, parent, ogrenci: dict):
        super().__init__(parent)
        self.title(f"Geçmiş – {ogrenci['ad_soyad']}")
        self.geometry("480x400")
        self.grab_set()
        self.lift()

        ctk.CTkLabel(
            self,
            text=f"📜  {ogrenci['ad_soyad']}",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=(14, 4))

        sf = ctk.CTkScrollableFrame(self, height=320)
        sf.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        kayitlar = ogrenci_tik_gecmisi(ogrenci["id"])
        if not kayitlar:
            ctk.CTkLabel(sf, text="Henüz kayıt yok.", text_color=C_MUTED).pack(pady=20)
        else:
            for i, k in enumerate(kayitlar, 1):
                txt = f"{i}.  {k['tarih']}   {k['kriter']}   (→ {k['ogretmen']})"
                ctk.CTkLabel(
                    sf, text=txt, font=ctk.CTkFont(size=11),
                    anchor="w", wraplength=420
                ).pack(fill="x", pady=2, padx=4)


# ══════════════════════════════════════════════════════════════════════════
# Yayın Modu – Animasyonlu Canlı Liderboard
# ══════════════════════════════════════════════════════════════════════════

class YayinModu(ctk.CTkToplevel):
    """
    Tam ekran, animasyonlu disiplin panosu.
    • Öğrenciler tik sayısına göre (en fazla → en az) sıralanır.
    • Durum emojisi: 🚨 3+ tik | ⚠️ 1-2 tik | ✅ 0 tik
    • Kırmızı kartlar nabız gibi titreşir (pulse).
    • Her açılışta kartlar soldan kaydırarak girer.
    • 15 saniyede bir otomatik güncellenir.
    """

    # ── Renk sabitleri ────────────────────────────────────────────────────
    BG       = "#060c1a"
    HDR_BG   = "#0a1228"
    FTR_BG   = "#080f20"

    DURUM = {
        "temiz": {
            "emoji": "✅", "card":  "#091a0e", "card2": "#091a0e",
            "text":  "#4ade80", "bar": "#22c55e", "rank": "#166534",
        },
        "uyari": {
            "emoji": "⚠️", "card":  "#1a1200", "card2": "#1a1200",
            "text":  "#fbbf24", "bar": "#f59e0b", "rank": "#92400e",
        },
        "tehlike": {
            "emoji": "🚨", "card":  "#1f0606", "card2": "#2e0808",
            "text":  "#f87171", "bar": "#ef4444", "rank": "#7f1d1d",
        },
    }

    REFRESH_MS  = 15_000   # Oto-güncelleme süresi
    PULSE_MS    = 550      # Pulse hızı
    SLIDE_STEP  = 55       # Slide piksel adımı
    SLIDE_DELAY = 12       # Slide frame gecikmesi (ms)
    CARD_DELAY  = 90       # Kartlar arası oluşum gecikmesi (ms)
    BAR_MAX     = 10       # Progress bar doluluğu için maksimum tik referansı

    def __init__(self, parent, sinif_id: int, sinif_adi: str):
        super().__init__(parent)
        self.sinif_id  = sinif_id
        self.sinif_adi = sinif_adi

        self._pulse_state   = False
        self._pulse_id      = None
        self._saat_id       = None
        self._refresh_id    = None
        self._kart_widget_listesi = []   # (frame_ref, durum_key) çiftleri

        self.title(f"📺  Yayın Modu  –  {sinif_adi}")
        self.attributes("-fullscreen", True)
        self.configure(fg_color=self.BG)
        self.bind("<Escape>", lambda e: self._kapat())
        self.bind("<F11>",    lambda e: self.attributes(
            "-fullscreen", not self.attributes("-fullscreen")))
        self.protocol("WM_DELETE_WINDOW", self._kapat)

        self._build()
        self._yukle(animasyon=True)
        self._pulse_loop()
        self._saat_guncelle()
        self._refresh_id = self.after(self.REFRESH_MS, self._oto_yenile)

    # ── Arayüz Kurulumu ───────────────────────────────────────────────────

    def _build(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Üst başlık bandı ──────────────────────────────────────────────
        hdr = tk.Frame(self, bg=self.HDR_BG, height=90)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.columnconfigure(1, weight=1)

        tk.Label(
            hdr, text="🏫  Erenler Cumhuriyet Ortaokulu",
            font=("Segoe UI", 20, "bold"),
            bg=self.HDR_BG, fg="#93c5fd"
        ).grid(row=0, column=0, columnspan=3, pady=(14, 0))

        tk.Label(
            hdr,
            text=f"CANLI DİSİPLİN PANOSU  •  {self.sinif_adi} Şubesi",
            font=("Segoe UI", 12),
            bg=self.HDR_BG, fg="#475569"
        ).grid(row=1, column=0, columnspan=3, pady=(0, 12))

        self._saat_lbl = tk.Label(
            hdr, text="", font=("Segoe UI", 13, "bold"),
            bg=self.HDR_BG, fg="#64748b"
        )
        self._saat_lbl.place(relx=0.98, rely=0.5, anchor="e")

        # ── Orta: Kaydırılabilir liste ────────────────────────────────────
        wrapper = tk.Frame(self, bg=self.BG)
        wrapper.grid(row=1, column=0, sticky="nsew")
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)

        canvas = tk.Canvas(wrapper, bg=self.BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(wrapper, orient="vertical",
                                  command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._liste_frame = tk.Frame(canvas, bg=self.BG)
        self._canvas_win  = canvas.create_window(
            (0, 0), window=self._liste_frame, anchor="nw"
        )

        def _on_resize(e):
            canvas.itemconfig(self._canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_resize)

        self._liste_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Mouse tekerleği
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._canvas = canvas

        # ── Alt bilgi çubuğu ──────────────────────────────────────────────
        ftr = tk.Frame(self, bg=self.FTR_BG, height=38)
        ftr.grid(row=2, column=0, sticky="ew")
        ftr.grid_propagate(False)
        ftr.columnconfigure(1, weight=1)

        tk.Button(
            ftr, text="✕  Kapat  [ESC]",
            font=("Segoe UI", 10), bg="#1e293b", fg="#94a3b8",
            activebackground="#334155", activeforeground="white",
            relief="flat", padx=12, pady=4,
            command=self._kapat
        ).grid(row=0, column=0, padx=10, pady=4)

        tk.Button(
            ftr, text="🔄  Yenile",
            font=("Segoe UI", 10), bg="#1e293b", fg="#94a3b8",
            activebackground="#334155", activeforeground="white",
            relief="flat", padx=12, pady=4,
            command=lambda: self._yukle(animasyon=True)
        ).grid(row=0, column=1, padx=4, pady=4, sticky="w")

        self._guncelleme_lbl = tk.Label(
            ftr, text="", font=("Segoe UI", 9),
            bg=self.FTR_BG, fg="#334155"
        )
        self._guncelleme_lbl.grid(row=0, column=2, padx=10)

        # Efsane
        efsnc = tk.Frame(ftr, bg=self.FTR_BG)
        efsnc.grid(row=0, column=3, padx=16, pady=4)
        for emoji, metin, renk in [
            ("🚨", "İdari işlem", "#f87171"),
            ("⚠️", "Uyarı",       "#fbbf24"),
            ("✅", "Temiz",       "#4ade80"),
        ]:
            tk.Label(efsnc, text=f" {emoji} {metin} ",
                     font=("Segoe UI", 9), bg=self.FTR_BG, fg=renk
                     ).pack(side="left", padx=6)

    # ── Veri Yükleme + Kart Oluşturma ─────────────────────────────────────

    def _yukle(self, animasyon: bool = False):
        # Pulse'u geçici durdur
        self._kart_widget_listesi.clear()

        # Eski kartları temizle
        for w in self._liste_frame.winfo_children():
            w.destroy()

        ogrenciler = sinif_ogrencileri(self.sinif_id)
        # Tik sayısına göre azalan sıra, eşit tiklerde isme göre artan
        ogrenciler.sort(key=lambda o: (-o["tik_sayisi"], o["ad_soyad"]))

        # Bar için en yüksek tik referansı
        maks = max((o["tik_sayisi"] for o in ogrenciler), default=0)
        bar_ref = max(maks, self.BAR_MAX)

        for i, ogr in enumerate(ogrenciler):
            kart = self._kart_olustur(ogr, i + 1, bar_ref)
            kart.pack(fill="x", padx=16, pady=4)

            if animasyon:
                # Kart başlangıçta ekran dışında (x offset ile)
                kart.place_forget()
                kart.pack_forget()
                self.after(
                    i * self.CARD_DELAY,
                    lambda k=kart, idx=i, ogr_=ogr, br=bar_ref:
                        self._slide_in(k, idx, ogr_, br)
                )

        guv = datetime.datetime.now().strftime("%H:%M:%S")
        self._guncelleme_lbl.configure(text=f"Son güncelleme: {guv}")

    def _kart_olustur(self, ogr: dict, sira: int, bar_ref: int) -> tk.Frame:
        tik  = ogr["tik_sayisi"]
        if tik == 0:   durum = self.DURUM["temiz"]
        elif tik <= 2: durum = self.DURUM["uyari"]
        else:          durum = self.DURUM["tehlike"]

        sinif_adi = ogr.get("sinif_adi", self.sinif_adi)

        kart = tk.Frame(
            self._liste_frame,
            bg=durum["card"],
            height=72,
            highlightbackground=durum["bar"],
            highlightthickness=1,
        )
        kart.pack_propagate(False)

        # ── Sol: Sıra numarası ─────────────────────────────────────────────
        rank_frame = tk.Frame(kart, bg=durum["rank"], width=80)
        rank_frame.pack(side="left", fill="y")
        rank_frame.pack_propagate(False)
        tk.Label(
            rank_frame,
            text=f"#{sira}",
            font=("Segoe UI Black", 20, "bold"),
            bg=durum["rank"], fg=durum["text"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        # ── Orta: Emoji + Ad ──────────────────────────────────────────────
        orta = tk.Frame(kart, bg=durum["card"])
        orta.pack(side="left", fill="both", expand=True, padx=(14, 8))

        isim_satiri = tk.Frame(orta, bg=durum["card"])
        isim_satiri.pack(side="top", fill="x", pady=(10, 0))

        tk.Label(
            isim_satiri,
            text=durum["emoji"],
            font=("Segoe UI Emoji", 20),
            bg=durum["card"]
        ).pack(side="left", padx=(0, 8))

        tk.Label(
            isim_satiri,
            text=ogr["ad_soyad"],
            font=("Segoe UI", 16, "bold"),
            bg=durum["card"], fg=durum["text"],
            anchor="w"
        ).pack(side="left", fill="x")

        # Progress bar (canvas)
        bar_bg   = "#0f172a"
        bar_pct  = tik / bar_ref if bar_ref > 0 else 0
        bar_c = tk.Canvas(orta, height=10, bg=durum["card"],
                          highlightthickness=0)
        bar_c.pack(side="top", fill="x", pady=(4, 0))

        def _draw_bar(canvas=bar_c, pct=bar_pct, col=durum["bar"]):
            canvas.delete("all")
            w = canvas.winfo_width()
            if w < 2:
                w = 400
            # Arka plan
            canvas.create_rectangle(0, 0, w, 10, fill=bar_bg, outline="")
            # Doluluk (animate)
            fill_w = int(w * pct)
            if fill_w > 0:
                # Gradient-benzeri: parlak baş, soluk son
                canvas.create_rectangle(0, 0, fill_w, 10,
                                        fill=col, outline="")
                canvas.create_rectangle(
                    max(0, fill_w - 20), 0, fill_w, 10,
                    fill="white", stipple="gray50", outline=""
                )

        bar_c.bind("<Configure>", lambda e: _draw_bar())
        bar_c.after(50, _draw_bar)

        # ── Sağ: Tik sayısı badge ─────────────────────────────────────────
        sag = tk.Frame(kart, bg=durum["rank"], width=80)
        sag.pack(side="right", fill="y")
        sag.pack_propagate(False)
        tk.Label(
            sag,
            text=str(tik),
            font=("Segoe UI Black", 26, "bold"),
            bg=durum["rank"], fg=durum["text"]
        ).place(relx=0.5, rely=0.38, anchor="center")
        tk.Label(
            sag, text="tik",
            font=("Segoe UI", 9),
            bg=durum["rank"], fg=durum["text"]
        ).place(relx=0.5, rely=0.72, anchor="center")

        # Pulse için ref sakla
        kart._durum_key = ("tehlike" if tik >= 3
                           else "uyari" if tik >= 1 else "temiz")
        kart._durum     = durum
        kart._rank_frame = rank_frame
        kart._sag_frame  = sag
        kart._orta       = orta

        self._kart_widget_listesi.append(kart)
        return kart

    # ── Slide-in Animasyonu ────────────────────────────────────────────────

    def _slide_in(self, kart: tk.Frame, idx: int, ogr: dict, bar_ref: int):
        """Kartı sağdan sola süzerek ekrana getirir."""
        if not self.winfo_exists():
            return
        kart.pack(fill="x", padx=16, pady=4)
        self._liste_frame.update_idletasks()
        total_w = self._liste_frame.winfo_width() or 900
        self._animate_slide(kart, total_w)

    def _animate_slide(self, kart: tk.Frame, x_pos: int):
        if not self.winfo_exists() or not kart.winfo_exists():
            return
        if x_pos > 0:
            kart.place(in_=self._liste_frame,
                       relx=0, rely=0, x=x_pos)
            self.after(self.SLIDE_DELAY,
                       lambda: self._animate_slide(kart, x_pos - self.SLIDE_STEP))
        else:
            # Animasyon bitti – normal pack düzenine dön
            try:
                kart.place_forget()
                kart.pack(fill="x", padx=16, pady=4)
            except Exception:
                pass

    # ── Pulse Animasyonu ──────────────────────────────────────────────────

    def _pulse_loop(self):
        if not self.winfo_exists():
            return
        self._pulse_state = not self._pulse_state
        for kart in self._kart_widget_listesi:
            try:
                if kart._durum_key == "tehlike":
                    renk = (self.DURUM["tehlike"]["card2"]
                            if self._pulse_state
                            else self.DURUM["tehlike"]["card"])
                    kart.configure(bg=renk)
                    kart._rank_frame.configure(bg=renk)
                    kart._sag_frame.configure(bg=renk)
                    kart._orta.configure(bg=renk)
                    for child in kart._orta.winfo_children():
                        try:
                            child.configure(bg=renk)
                        except Exception:
                            pass
                    for child in kart._rank_frame.winfo_children():
                        try:
                            child.configure(bg=renk)
                        except Exception:
                            pass
                    for child in kart._sag_frame.winfo_children():
                        try:
                            child.configure(bg=renk)
                        except Exception:
                            pass
            except Exception:
                pass
        self._pulse_id = self.after(self.PULSE_MS, self._pulse_loop)

    # ── Saat Güncellemesi ─────────────────────────────────────────────────

    def _saat_guncelle(self):
        if not self.winfo_exists():
            return
        self._saat_lbl.configure(
            text="🕐  " + datetime.datetime.now().strftime("%H:%M:%S")
        )
        self._saat_id = self.after(1000, self._saat_guncelle)

    # ── Otomatik Güncelleme ───────────────────────────────────────────────

    def _oto_yenile(self):
        if not self.winfo_exists():
            return
        self._yukle(animasyon=False)
        self._refresh_id = self.after(self.REFRESH_MS, self._oto_yenile)

    # ── Temiz Kapatma ─────────────────────────────────────────────────────

    def _kapat(self):
        for aid in [self._pulse_id, self._saat_id, self._refresh_id]:
            if aid:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════
# Excel Rapor Dialogu
# ══════════════════════════════════════════════════════════════════════════

class ExcelRaporDialog(ctk.CTkToplevel):
    """Kullanıcıya hangi sınıfları dışa aktaracağını sorar, Excel üretir."""

    def __init__(self, parent, ogretmen_adi: str,
                 sinif_listesi: list[dict], aktif_sinif: dict | None):
        super().__init__(parent)
        self.title("📊  Excel Raporu İndir")
        self.geometry("420x440")
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        self._ogretmen    = ogretmen_adi
        self._sinif_list  = sinif_listesi
        self._aktif_sinif = aktif_sinif

        self._build()

    def _build(self):
        # Başlık bandı
        ust = ctk.CTkFrame(self, fg_color=C_HEADER, corner_radius=0, height=60)
        ust.pack(fill="x")
        ust.pack_propagate(False)
        ctk.CTkLabel(
            ust, text="📊  Excel Raporu Oluştur",
            font=ctk.CTkFont(size=15, weight="bold"), text_color="white"
        ).pack(expand=True)

        # Kapsam seçimi
        ctk.CTkLabel(
            self, text="Rapor kapsamını seçin:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C_HEADER
        ).pack(pady=(18, 6))

        self._kapsam = ctk.StringVar(value="aktif")

        secenekler = []
        if self._aktif_sinif:
            secenekler.append((
                f"📚  Yalnızca {self._aktif_sinif['sinif_adi']} şubesi",
                "aktif"
            ))
        secenekler.append(("📂  Girdiğim tüm sınıflar", "tum"))

        for metin, deger in secenekler:
            ctk.CTkRadioButton(
                self, text=metin,
                variable=self._kapsam, value=deger,
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w", padx=30, pady=4)

        # Sayfa içeriği bilgisi
        ctk.CTkFrame(self, fg_color="#e2e8f0", height=1).pack(
            fill="x", padx=20, pady=(14, 10))

        bilgi_frame = ctk.CTkFrame(self, fg_color="#f8faff",
                                    corner_radius=8, border_width=1,
                                    border_color="#dde5f7")
        bilgi_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            bilgi_frame,
            text="Rapor şu sayfaları içerir:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=C_HEADER
        ).pack(anchor="w", padx=12, pady=(8, 2))

        sayfalar = [
            ("📋", "Özet Liste", "Tüm öğrenciler tik sayısına göre sıralı"),
            ("📝", "Tik Detayları", "Her ihlal kaydı + öğretmen + tarih"),
            ("📊", "İstatistikler", "Sınıf bazlı sayılar + en sık kriterler"),
        ]
        for emoji, ad, aciklama in sayfalar:
            satir = ctk.CTkFrame(bilgi_frame, fg_color="transparent")
            satir.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(satir, text=f"{emoji}  {ad}",
                          font=ctk.CTkFont(size=11, weight="bold"),
                          text_color=C_ACCENT, width=140, anchor="w"
                          ).pack(side="left")
            ctk.CTkLabel(satir, text=aciklama,
                          font=ctk.CTkFont(size=10),
                          text_color=C_MUTED, anchor="w"
                          ).pack(side="left")
        ctk.CTkLabel(bilgi_frame, text="").pack(pady=4)

        if not OPENPYXL_OK:
            ctk.CTkLabel(
                self,
                text="⚠️  openpyxl yüklü değil!\nTerminalde: pip install openpyxl",
                font=ctk.CTkFont(size=11),
                text_color=C_DANGER, justify="center"
            ).pack(pady=6)

        # Butonlar
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(4, 16))

        ctk.CTkButton(
            btn_frame, text="💾  Kaydet ve Aç", width=170, height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#16a34a", hover_color="#15803d",
            state="normal" if OPENPYXL_OK else "disabled",
            command=self._kaydet
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame, text="İptal", width=80, height=40,
            font=ctk.CTkFont(size=12),
            fg_color="#475569", hover_color="#334155",
            command=self.destroy
        ).pack(side="left", padx=6)

        if not OPENPYXL_OK:
            ctk.CTkButton(
                self, text="📦  openpyxl Kur (pip)",
                width=200, height=34,
                font=ctk.CTkFont(size=11),
                fg_color=C_ACCENT, hover_color="#1d4ed8",
                command=self._openpyxl_kur
            ).pack(pady=(0, 10))

    def _kaydet(self):
        kapsam = self._kapsam.get()
        yalnizca_id = (
            self._aktif_sinif["id"]
            if kapsam == "aktif" and self._aktif_sinif
            else None
        )

        # Varsayılan dosya adı
        zaman = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        sinif_kisa = (
            self._aktif_sinif["sinif_adi"].replace("/", "")
            if kapsam == "aktif" and self._aktif_sinif
            else "TumSiniflar"
        )
        varsayilan_ad = f"DisiplinRaporu_{sinif_kisa}_{zaman}.xlsx"

        yol = filedialog.asksaveasfilename(
            parent=self,
            title="Excel Raporunu Kaydet",
            initialfile=varsayilan_ad,
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyası", "*.xlsx"), ("Tümü", "*.*")]
        )
        if not yol:
            return

        try:
            self._durum_goster("⏳  Rapor oluşturuluyor...")
            self.update()
            excel_raporu_olustur(
                kayit_yolu=yol,
                ogretmen_adi=self._ogretmen,
                sinif_listesi=self._sinif_list,
                yalnizca_sinif_id=yalnizca_id,
            )
            self.destroy()
            # Dosyayı varsayılan uygulamada aç
            self._dosya_ac(yol)
            messagebox.showinfo(
                "Rapor Hazır",
                f"Excel raporu başarıyla oluşturuldu:\n{yol}"
            )
        except Exception as e:
            messagebox.showerror("Hata", f"Rapor oluşturulurken hata:\n{e}")

    def _durum_goster(self, metin: str):
        """Geçici durum etiketi gösterir."""
        lbl = ctk.CTkLabel(self, text=metin,
                            font=ctk.CTkFont(size=11),
                            text_color=C_ACCENT)
        lbl.pack(pady=4)

    @staticmethod
    def _dosya_ac(yol: str):
        try:
            if sys.platform.startswith("win"):
                os.startfile(yol)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", yol])
            else:
                subprocess.Popen(["xdg-open", yol])
        except Exception:
            pass

    def _openpyxl_kur(self):
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "openpyxl", "--quiet"]
            )
            messagebox.showinfo(
                "Kurulum Tamamlandı",
                "openpyxl başarıyla kuruldu.\nUygulamayı yeniden başlatın."
            )
            self.destroy()
        except Exception as e:
            messagebox.showerror("Kurulum Hatası", str(e))


# ══════════════════════════════════════════════════════════════════════════
# Parola Dialogu
# ══════════════════════════════════════════════════════════════════════════

class ParolaDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Güvenlik Doğrulaması")
        self.geometry("340x210")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.onaylandi = False

        ctk.CTkLabel(
            self, text="🔒  Toplu Sıfırlama",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(22, 4))
        ctk.CTkLabel(
            self, text="Devam etmek için parolayı girin:",
            font=ctk.CTkFont(size=12), text_color=C_MUTED
        ).pack(pady=(0, 10))

        self.ent = ctk.CTkEntry(self, show="*", width=200, height=36,
                                 font=ctk.CTkFont(size=13), placeholder_text="Parola")
        self.ent.pack(pady=(0, 12))
        self.ent.bind("<Return>", lambda e: self._kontrol())

        ctk.CTkButton(
            self, text="Onayla", width=120, height=34,
            fg_color=C_DANGER, hover_color="#b91c1c",
            command=self._kontrol
        ).pack()

    def _kontrol(self):
        if self.ent.get() == SIFIR_PAROLA:
            self.onaylandi = True
            self.destroy()
        else:
            messagebox.showerror("Hatalı Parola", "Parola yanlış!", parent=self)
            self.ent.delete(0, "end")


# ══════════════════════════════════════════════════════════════════════════
# Öğrenci Kartı
# ══════════════════════════════════════════════════════════════════════════

class OgrenciKarti(ctk.CTkFrame):
    def __init__(self, master, ogrenci: dict, ogretmen_id: int,
                 sinif_adi: str, app_ref, sira: int, **kw):
        bg, kenar, badge_renk = _tik_renk(ogrenci["tik_sayisi"])
        super().__init__(master, corner_radius=8,
                         fg_color=bg, border_width=1, border_color=kenar, **kw)
        self.ogrenci    = ogrenci
        self.ogretmen_id = ogretmen_id
        self.sinif_adi  = sinif_adi
        self.app        = app_ref
        self._build(sira, badge_renk)

    def _build(self, sira: int, badge_renk: str):
        tik = self.ogrenci["tik_sayisi"]

        # Sol: Sıra + Ad
        sol = ctk.CTkFrame(self, fg_color="transparent")
        sol.pack(side="left", fill="y", padx=(10, 0), pady=6)

        ctk.CTkLabel(
            sol,
            text=f"{sira}.",
            font=ctk.CTkFont(size=11),
            text_color=C_MUTED, width=22, anchor="e"
        ).pack(side="left", padx=(0, 4))

        isim_frame = ctk.CTkFrame(sol, fg_color="transparent")
        isim_frame.pack(side="left")

        ctk.CTkLabel(
            isim_frame,
            text=self.ogrenci["ad_soyad"],
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            isim_frame,
            text=f"No: {self.ogrenci['ogr_no']}   {self.sinif_adi}",
            font=ctk.CTkFont(size=10),
            text_color=C_MUTED, anchor="w"
        ).pack(anchor="w")

        # Orta: Tik göstergesi
        ctk.CTkLabel(
            self,
            text=_nokta_str(tik),
            font=ctk.CTkFont(size=14),
            text_color=badge_renk,
        ).pack(side="left", expand=True)

        # Tik sayısı badge
        ctk.CTkLabel(
            self,
            text=f"{tik}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=badge_renk,
            width=28
        ).pack(side="left", padx=(0, 6))

        # Sağ: Butonlar
        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.pack(side="right", padx=8, pady=6)

        ctk.CTkButton(
            btn, text="+ Tik At", width=88, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=C_ACCENT, hover_color="#1d4ed8",
            command=self._tik_at
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn, text="Geçmiş", width=68, height=30,
            font=ctk.CTkFont(size=11),
            fg_color="#475569", hover_color="#334155",
            command=self._gecmis
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn, text="↺", width=32, height=30,
            font=ctk.CTkFont(size=14),
            fg_color=C_WARN, hover_color="#b45309",
            command=self._sifirla
        ).pack(side="left", padx=2)

    # ── Eylemler ──────────────────────────────────────────────────────────

    def _tik_at(self):
        d = KriterDialog(self.app, self.ogrenci["ad_soyad"])
        self.app.wait_window(d)
        if not d.secilen:
            return

        yeni = tik_ekle(self.ogrenci["id"], self.ogretmen_id, d.secilen)

        if yeni >= 3:
            self._uyari(yeni)

        self.app.listeyi_yenile()

    def _uyari(self, tik: int):
        w = ctk.CTkToplevel(self.app)
        w.title("⚠️ DİSİPLİN UYARISI")
        w.geometry("460x220")
        w.resizable(False, False)
        w.grab_set()
        w.lift()
        w.configure(fg_color="#fff0f0")

        ctk.CTkLabel(
            w, text="⚠️  DİSİPLİN UYARISI",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=C_DANGER
        ).pack(pady=(22, 6))

        ctk.CTkLabel(
            w,
            text=(f"  {self.ogrenci['ad_soyad']}  \n"
                  f"{tik} tike ulaştı!\n"
                  "İdari işlem başlatılmalıdır."),
            font=ctk.CTkFont(size=13), text_color="#1e293b", justify="center"
        ).pack(pady=4)

        ctk.CTkButton(
            w, text="Tamam", width=120, height=34,
            fg_color=C_DANGER, hover_color="#b91c1c",
            command=w.destroy
        ).pack(pady=14)

    def _gecmis(self):
        GecmisDialog(self.app, self.ogrenci)

    def _sifirla(self):
        if messagebox.askyesno(
            "Sıfırlama Onayı",
            f"{self.ogrenci['ad_soyad']} adlı öğrencinin tikleri sıfırlansın mı?"
        ):
            tek_ogrenci_sifirla(self.ogrenci["id"])
            self.app.listeyi_yenile()


# ══════════════════════════════════════════════════════════════════════════
# Yönetici – Şifre Listesi Dialogu
# ══════════════════════════════════════════════════════════════════════════

ADMIN_SIFRE = "ECadmin"   # Yönetici şifresi

class SifreListesiDialog(ctk.CTkToplevel):
    """Tüm öğretmen şifrelerini gösteren yönetici penceresi."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔑  Öğretmen Şifre Listesi")
        self.geometry("400x560")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self._onaylandi = False
        self._build_giris()

    def _build_giris(self):
        """Yönetici şifresi doğrulama formu."""
        ctk.CTkLabel(
            self, text="🔒  Yönetici Doğrulaması",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=C_HEADER
        ).pack(pady=(28, 6))

        ctk.CTkLabel(
            self, text="Şifre listesini görüntülemek için\nyönetici şifresini girin:",
            font=ctk.CTkFont(size=12), text_color=C_MUTED, justify="center"
        ).pack(pady=(0, 14))

        self._admin_ent = ctk.CTkEntry(
            self, show="*", width=220, height=38,
            font=ctk.CTkFont(size=13), placeholder_text="Yönetici Şifresi"
        )
        self._admin_ent.pack(pady=(0, 6))
        self._admin_ent.bind("<Return>", lambda e: self._admin_dogrula())
        self._admin_ent.focus()

        self._hata = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11), text_color=C_DANGER
        )
        self._hata.pack(pady=(0, 4))

        ctk.CTkButton(
            self, text="Görüntüle", width=160, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=C_HEADER, hover_color="#0f2548",
            command=self._admin_dogrula
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            self,
            text=f"(İpucu: Yönetici şifrenizi bilmiyorsanız\nokul idaresine başvurun)",
            font=ctk.CTkFont(size=9), text_color="#94a3b8", justify="center"
        ).pack(pady=(0, 20))

    def _admin_dogrula(self):
        if self._admin_ent.get() == ADMIN_SIFRE:
            for w in self.winfo_children():
                w.destroy()
            self._build_liste()
        else:
            self._hata.configure(text="❌  Yönetici şifresi hatalı!")
            self._admin_ent.delete(0, "end")

    def _build_liste(self):
        """Şifre listesini göster."""
        # Üst bant
        ust = ctk.CTkFrame(self, fg_color=C_HEADER, corner_radius=0, height=54)
        ust.pack(fill="x")
        ust.pack_propagate(False)
        ctk.CTkLabel(
            ust, text="🔑  Öğretmen Şifre Listesi",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="white"
        ).pack(expand=True)

        ctk.CTkLabel(
            self,
            text="Bu listeyi yazdırıp öğretmenlere dağıtabilirsiniz.",
            font=ctk.CTkFont(size=10), text_color=C_MUTED
        ).pack(pady=(8, 4))

        # Tablo
        sf = ctk.CTkScrollableFrame(self, height=380)
        sf.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        sf.grid_columnconfigure((0, 1, 2), weight=1)

        # Başlıklar
        for col, metin in enumerate(["Şifre", "Ad Soyad", ""]):
            h = ctk.CTkLabel(
                sf, text=metin,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=C_HEADER
            )
            h.grid(row=0, column=col, sticky="w", padx=6, pady=(4, 6))

        liste = tum_sifre_listesi()
        for i, kayit in enumerate(liste, 1):
            alt_bg = "#f0f4ff" if i % 2 == 0 else "white"
            satir = ctk.CTkFrame(sf, fg_color=alt_bg, corner_radius=4)
            satir.grid(row=i, column=0, columnspan=3, sticky="ew",
                       padx=2, pady=1)
            satir.grid_columnconfigure(1, weight=1)

            # Şifre badge
            ctk.CTkLabel(
                satir,
                text=kayit["sifre"],
                font=ctk.CTkFont(size=12, weight="bold", family="Courier New"),
                text_color="white",
                fg_color=C_ACCENT,
                corner_radius=5,
                width=68
            ).grid(row=0, column=0, padx=(6, 10), pady=4)

            ctk.CTkLabel(
                satir,
                text=kayit["ad_soyad"],
                font=ctk.CTkFont(size=11),
                text_color="#1e293b",
                anchor="w"
            ).grid(row=0, column=1, sticky="w", pady=4)

        ctk.CTkButton(
            self, text="Kapat", width=100, height=30,
            font=ctk.CTkFont(size=11),
            fg_color="#475569", hover_color="#334155",
            command=self.destroy
        ).pack(pady=(0, 10))


# ══════════════════════════════════════════════════════════════════════════
# Giriş Ekranı
# ══════════════════════════════════════════════════════════════════════════

class LoginEkrani(ctk.CTkFrame):
    def __init__(self, master, on_login):
        super().__init__(master, fg_color="#f0f4ff", corner_radius=0)
        self.on_login = on_login
        self._deneme = 0        # Başarısız giriş sayacı
        self._build()

    def _build(self):
        # Arka plan degrade etkisi (üst lacivert bant)
        ust_bg = ctk.CTkFrame(self, fg_color=C_HEADER, corner_radius=0, height=220)
        ust_bg.place(relx=0, rely=0, relwidth=1)

        # Giriş kartı
        kart = ctk.CTkFrame(
            self, width=460, corner_radius=18,
            fg_color="white",
            border_width=1, border_color="#e2e8f0"
        )
        kart.place(relx=0.5, rely=0.5, anchor="center")
        kart.grid_propagate(False)

        # ── Okul logosu / başlık ─────────────────────────────────────────
        logo = ctk.CTkFrame(kart, fg_color=C_HEADER, corner_radius=0,
                             height=100, width=460)
        logo.pack(fill="x")
        logo.pack_propagate(False)

        ctk.CTkLabel(
            logo, text="🏫",
            font=ctk.CTkFont(size=36),
        ).pack(pady=(10, 0))
        ctk.CTkLabel(
            logo, text="Erenler Cumhuriyet Ortaokulu",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white"
        ).pack()
        ctk.CTkLabel(
            logo, text="Öğrenci Takip ve Disiplin Paneli",
            font=ctk.CTkFont(size=10),
            text_color="#93c5fd"
        ).pack(pady=(0, 8))

        # ── Form alanı ────────────────────────────────────────────────────
        form = ctk.CTkFrame(kart, fg_color="white")
        form.pack(fill="x", padx=30, pady=(20, 0))

        ctk.CTkLabel(
            form, text="Öğretmen Seçin",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=C_MUTED, anchor="w"
        ).pack(fill="x", pady=(0, 3))

        ogretmenler = [o["ad_soyad"] for o in tum_ogretmenler()]
        self.combo = ctk.CTkComboBox(
            form, values=ogretmenler,
            width=400, height=40,
            font=ctk.CTkFont(size=13),
            dropdown_font=ctk.CTkFont(size=12),
            state="readonly"
        )
        self.combo.pack(fill="x", pady=(0, 14))
        self.combo.set("— Öğretmen Seçiniz —")

        ctk.CTkLabel(
            form, text="Şifre",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=C_MUTED, anchor="w"
        ).pack(fill="x", pady=(0, 3))

        sifre_satir = ctk.CTkFrame(form, fg_color="transparent")
        sifre_satir.pack(fill="x", pady=(0, 6))
        sifre_satir.grid_columnconfigure(0, weight=1)

        self.sifre_ent = ctk.CTkEntry(
            sifre_satir,
            show="●",
            height=40,
            font=ctk.CTkFont(size=14, family="Courier New"),
            placeholder_text="Şifrenizi girin..."
        )
        self.sifre_ent.grid(row=0, column=0, sticky="ew")
        self.sifre_ent.bind("<Return>", lambda e: self._giris())

        # Göster/Gizle butonu
        self._goster_var = ctk.BooleanVar(value=False)
        ctk.CTkButton(
            sifre_satir, text="👁", width=40, height=40,
            font=ctk.CTkFont(size=16),
            fg_color="#e2e8f0", hover_color="#cbd5e1",
            text_color="#475569",
            command=self._sifre_goster_gizle
        ).grid(row=0, column=1, padx=(6, 0))

        # Hata etiketi
        self.hata_lbl = ctk.CTkLabel(
            form, text="",
            font=ctk.CTkFont(size=11),
            text_color=C_DANGER,
            height=16
        )
        self.hata_lbl.pack(fill="x", pady=(0, 4))

        # Giriş butonu
        self.giris_btn = ctk.CTkButton(
            form, text="Giriş Yap  →",
            width=400, height=46,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=C_ACCENT, hover_color="#1d4ed8",
            command=self._giris
        )
        self.giris_btn.pack(fill="x", pady=(2, 0))

        # ── Alt: Yönetici / şifre listesi bağlantısı ─────────────────────
        alt = ctk.CTkFrame(kart, fg_color="white")
        alt.pack(fill="x", padx=30, pady=(10, 20))

        ctk.CTkButton(
            alt, text="🔑  Şifre Listesi (Yönetici)",
            width=200, height=28,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color="#f0f4ff",
            text_color=C_MUTED,
            border_width=1,
            border_color="#e2e8f0",
            command=self._sifre_listesi_ac
        ).pack(side="left")

        ctk.CTkLabel(
            alt,
            text="2025–2026 II. Dönem",
            font=ctk.CTkFont(size=9),
            text_color="#cbd5e1"
        ).pack(side="right")

    # ── Yardımcı metodlar ─────────────────────────────────────────────────

    def _sifre_goster_gizle(self):
        self._goster_var.set(not self._goster_var.get())
        self.sifre_ent.configure(
            show="" if self._goster_var.get() else "●"
        )

    def _sifre_listesi_ac(self):
        SifreListesiDialog(self)

    def _giris(self):
        ad = self.combo.get()
        if ad.startswith("—"):
            self._hata_goster("Lütfen adınızı seçin.")
            return

        sifre = self.sifre_ent.get().strip()
        if not sifre:
            self._hata_goster("Şifre boş bırakılamaz.")
            self.sifre_ent.focus()
            return

        if not ogretmen_dogrula(ad, sifre):
            self._deneme += 1
            kalan = max(0, 5 - self._deneme)
            if self._deneme >= 5:
                self._hata_goster("Çok fazla hatalı deneme! Lütfen yöneticiyle iletişime geçin.")
                self.giris_btn.configure(state="disabled", text="Giriş Engellendi")
            else:
                self._hata_goster(
                    f"❌  Hatalı şifre!  (Kalan deneme: {kalan})"
                )
            self.sifre_ent.delete(0, "end")
            self.sifre_ent.focus()
            # Kart sallama animasyonu
            self._salla()
            return

        # Başarılı giriş
        self._deneme = 0
        ogr_id = ogretmen_id_bul(ad)
        self.on_login(ad, ogr_id)

    def _hata_goster(self, metin: str):
        self.hata_lbl.configure(text=metin)

    def _salla(self, adim: int = 0, yon: int = 1):
        """Hatalı girişte kart sallama animasyonu."""
        if adim >= 6:
            return
        offset = 8 * yon
        try:
            kart = [w for w in self.winfo_children()
                    if isinstance(w, ctk.CTkFrame) and w.winfo_width() > 300]
            if kart:
                x = kart[0].winfo_x()
                kart[0].place(relx=0.5, rely=0.5, anchor="center",
                               x=offset)
        except Exception:
            pass
        self.after(40, lambda: self._salla(adim + 1, -yon))


# ══════════════════════════════════════════════════════════════════════════
# Ana Panel
# ══════════════════════════════════════════════════════════════════════════

class AnaPaneli(ctk.CTkFrame):
    """Öğretmen giriş yaptıktan sonra görüntülenen panel."""

    def __init__(self, master, ogretmen_adi: str, ogretmen_id: int, on_cikis):
        super().__init__(master, fg_color="white", corner_radius=0)
        self.ogretmen_adi = ogretmen_adi
        self.ogretmen_id  = ogretmen_id
        self.on_cikis     = on_cikis
        self.aktif_sinif  = None   # {id, sinif_adi}

        self._siniflar = ogretmen_siniflari(ogretmen_id)
        self._build()
        if self._siniflar:
            self._sinif_sec(self._siniflar[0])

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Üst bar ────────────────────────────────────────────────────────
        bar = ctk.CTkFrame(self, fg_color=C_HEADER, corner_radius=0, height=56)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            bar,
            text="🏫  Erenler Cumhuriyet Ortaokulu  |  Öğrenci Takip Paneli",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="white"
        ).grid(row=0, column=0, padx=14, pady=10)

        sag = ctk.CTkFrame(bar, fg_color="transparent")
        sag.grid(row=0, column=1, sticky="e", padx=10)

        ctk.CTkLabel(
            sag, text=f"👤  {self.ogretmen_adi}",
            font=ctk.CTkFont(size=12),
            text_color="#93c5fd"
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            sag, text="📊  Excel Raporu", width=130, height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#16a34a", hover_color="#15803d",
            command=self._excel_raporu
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            sag, text="📺  Yayın Modu", width=130, height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#7c3aed", hover_color="#6d28d9",
            command=self._yayin_ac
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            sag, text="Çıkış", width=70, height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#334155", hover_color="#475569",
            command=self.on_cikis
        ).pack(side="left")

        # ── Sol sidebar (sınıflar) ──────────────────────────────────────────
        self.sidebar = ctk.CTkScrollableFrame(
            self, width=130, fg_color=C_SIDEBAR, corner_radius=0
        )
        self.sidebar.grid(row=1, column=0, sticky="ns", padx=0, pady=0)

        ctk.CTkLabel(
            self.sidebar, text="SINIFLARIM",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=C_MUTED
        ).pack(pady=(12, 6))

        self._sinif_butonlar: list[ctk.CTkButton] = []
        for s in self._siniflar:
            btn = ctk.CTkButton(
                self.sidebar,
                text=s["sinif_adi"],
                width=110, height=38,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="white",
                text_color=C_HEADER,
                hover_color="#dbeafe",
                border_width=1,
                border_color=C_BORDER_0,
                command=lambda x=s: self._sinif_sec(x)
            )
            btn.pack(pady=3)
            self._sinif_butonlar.append(btn)

        # Sınıf sıfırlama + toplu sıfırlama
        ctk.CTkFrame(self.sidebar, fg_color="#cbd5e1", height=1).pack(
            fill="x", padx=8, pady=(14, 6))

        ctk.CTkButton(
            self.sidebar, text="Sınıfı Sıfırla", width=110, height=32,
            font=ctk.CTkFont(size=11),
            fg_color=C_WARN, hover_color="#b45309",
            command=self._sinif_sifirla
        ).pack(pady=2)

        ctk.CTkButton(
            self.sidebar, text="Tümünü Sıfırla", width=110, height=32,
            font=ctk.CTkFont(size=11),
            fg_color=C_DANGER, hover_color="#b91c1c",
            command=self._toplu_sifirla
        ).pack(pady=2)

        # ── Sağ: Öğrenci alanı ─────────────────────────────────────────────
        sag_alan = ctk.CTkFrame(self, fg_color="white", corner_radius=0)
        sag_alan.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        sag_alan.grid_columnconfigure(0, weight=1)
        sag_alan.grid_rowconfigure(1, weight=1)

        # Arama + başlık
        ust2 = ctk.CTkFrame(sag_alan, fg_color="white", corner_radius=0)
        ust2.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        ust2.grid_columnconfigure(1, weight=1)

        self.baslik_lbl = ctk.CTkLabel(
            ust2, text="",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=C_HEADER
        )
        self.baslik_lbl.grid(row=0, column=0, sticky="w", padx=(4, 12))

        self.ara_ent = ctk.CTkEntry(
            ust2, placeholder_text="🔍  Öğrenci ara...",
            height=32, font=ctk.CTkFont(size=12)
        )
        self.ara_ent.grid(row=0, column=1, sticky="ew")
        self.ara_ent.bind("<KeyRelease>", lambda e: self.listeyi_yenile())

        # Öğrenci listesi (kaydırılabilir)
        self.liste_sf = ctk.CTkScrollableFrame(sag_alan, fg_color="#f8faff")
        self.liste_sf.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.liste_sf.grid_columnconfigure(0, weight=1)

        # Alt durum çubuğu
        self.durum_lbl = ctk.CTkLabel(
            sag_alan, text="", font=ctk.CTkFont(size=11), text_color=C_MUTED
        )
        self.durum_lbl.grid(row=2, column=0, pady=(0, 4))

    # ── Sınıf Seçimi ──────────────────────────────────────────────────────

    def _sinif_sec(self, sinif: dict):
        self.aktif_sinif = sinif
        # Aktif butonu vurgula
        for btn in self._sinif_butonlar:
            if btn.cget("text") == sinif["sinif_adi"]:
                btn.configure(fg_color=C_ACCENT, text_color="white",
                              border_color=C_ACCENT)
            else:
                btn.configure(fg_color="white", text_color=C_HEADER,
                              border_color=C_BORDER_0)
        self.ara_ent.delete(0, "end")
        self.listeyi_yenile()

    # ── Liste Yenileme ─────────────────────────────────────────────────────

    def listeyi_yenile(self):
        for w in self.liste_sf.winfo_children():
            w.destroy()

        if not self.aktif_sinif:
            return

        filtre = self.ara_ent.get().strip().lower()
        ogrenciler = sinif_ogrencileri(self.aktif_sinif["id"])
        sinif_adi  = self.aktif_sinif["sinif_adi"]

        if filtre:
            ogrenciler = [o for o in ogrenciler
                          if filtre in o["ad_soyad"].lower()]

        # Başlık
        toplam   = len(sinif_ogrencileri(self.aktif_sinif["id"]))
        uyari_s  = sum(1 for o in sinif_ogrencileri(self.aktif_sinif["id"])
                       if o["tik_sayisi"] >= 3)
        self.baslik_lbl.configure(
            text=f"📚  {sinif_adi}  –  {toplam} öğrenci"
        )
        self.durum_lbl.configure(
            text=f"{'Arama sonucu: ' + str(len(ogrenciler)) + ' öğrenci   |   ' if filtre else ''}"
                 f"⚠️ {uyari_s} öğrenci idari işlem gerektirir"
        )

        if not ogrenciler:
            ctk.CTkLabel(
                self.liste_sf,
                text="Öğrenci bulunamadı." if filtre else "Bu sınıfta öğrenci yok.",
                font=ctk.CTkFont(size=13), text_color=C_MUTED
            ).pack(pady=30)
            return

        for i, ogr in enumerate(ogrenciler, 1):
            kart = OgrenciKarti(
                self.liste_sf, ogr, self.ogretmen_id,
                sinif_adi, self, i
            )
            kart.grid(row=i - 1, column=0, sticky="ew", padx=4, pady=2)

    # ── Sıfırlama ─────────────────────────────────────────────────────────

    def _sinif_sifirla(self):
        if not self.aktif_sinif:
            messagebox.showinfo("Bilgi", "Önce bir sınıf seçin.")
            return
        d = ParolaDialog(self)
        self.wait_window(d)
        if d.onaylandi:
            sinif_sifirla(self.aktif_sinif["id"])
            self.listeyi_yenile()
            messagebox.showinfo("Başarılı",
                f"{self.aktif_sinif['sinif_adi']} sınıfının tüm tikleri sıfırlandı.")

    def _toplu_sifirla(self):
        d = ParolaDialog(self)
        self.wait_window(d)
        if d.onaylandi:
            tum_tikleri_sifirla()
            self.listeyi_yenile()
            messagebox.showinfo("Başarılı", "Tüm sınıfların tikleri sıfırlandı.")

    def _yayin_ac(self):
        if not self.aktif_sinif:
            messagebox.showinfo("Bilgi", "Lütfen önce bir sınıf seçin.")
            return
        YayinModu(self, self.aktif_sinif["id"], self.aktif_sinif["sinif_adi"])

    def _excel_raporu(self):
        ExcelRaporDialog(
            parent=self,
            ogretmen_adi=self.ogretmen_adi,
            sinif_listesi=self._siniflar,
            aktif_sinif=self.aktif_sinif,
        )


# ══════════════════════════════════════════════════════════════════════════
# Ana Uygulama
# ══════════════════════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        initialize_db()

        self.title("Öğrenci Takip ve Disiplin Paneli")
        self.geometry("980x680")
        self.minsize(760, 500)

        self._aktif_frame = None
        self._login_goster()

    def _login_goster(self):
        if self._aktif_frame:
            self._aktif_frame.destroy()
        frame = LoginEkrani(self, on_login=self._giris_yap)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._aktif_frame = frame

    def _giris_yap(self, adi: str, ogr_id: int):
        if self._aktif_frame:
            self._aktif_frame.destroy()
        frame = AnaPaneli(
            self, adi, ogr_id, on_cikis=self._login_goster
        )
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._aktif_frame = frame

    # listeyi_yenile: AnaPaneli'nden çağrılabilmesi için iletici
    def listeyi_yenile(self):
        if isinstance(self._aktif_frame, AnaPaneli):
            self._aktif_frame.listeyi_yenile()


if __name__ == "__main__":
    app = App()
    app.mainloop()
