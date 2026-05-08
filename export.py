"""
export.py
---------
Excel rapor üretim modülü.
Gerekli: pip install openpyxl
"""

from __future__ import annotations
import os
from datetime import datetime
from database import sinif_ogrencileri, ogrenci_tik_gecmisi, tum_siniflar_ogrencileri

try:
    import openpyxl
    from openpyxl import Workbook
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side, numbers
    )
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, Reference
    from openpyxl.chart.series import DataPoint
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False


# ── Renk sabitlerri (ARGB formatı) ────────────────────────────────────────
RENK = {
    "baslik_bg":   "FF1A3A6B",   # Koyu lacivert
    "baslik_yaz":  "FFFFFFFF",   # Beyaz
    "sutun_bg":    "FF2563EB",   # Mavi
    "sutun_yaz":   "FFFFFFFF",
    "alt_satir":   "FFF0F4FF",   # Çok açık mavi
    "temiz_bg":    "FFDCFCE7",   # Yeşil
    "temiz_yaz":   "FF166534",
    "uyari_bg":    "FFFEF9C3",   # Sarı
    "uyari_yaz":   "FF92400E",
    "tehlike_bg":  "FFFEE2E2",   # Kırmızı
    "tehlike_yaz": "FF991B1B",
    "detay_bg":    "FFF8FAFF",
    "detay_alt":   "FFEFF6FF",
    "bilgi_bg":    "FFFAFAFA",
    "gri_yazi":    "FF64748B",
    "siyah":       "FF1E293B",
}


def _dolu_dolgu(argb: str) -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=argb)


def _ince_kenar() -> Border:
    ince = Side(style="thin", color="FFCBD5E1")
    return Border(left=ince, right=ince, top=ince, bottom=ince)


def _kalin_kenar() -> Border:
    kalin = Side(style="medium", color="FF94A3B8")
    return Border(left=kalin, right=kalin, top=kalin, bottom=kalin)


def _durum(tik: int) -> tuple[str, str, str]:
    """(emoji, bg_argb, yazi_argb) döndürür."""
    if tik == 0:
        return "✅ Temiz",        RENK["temiz_bg"],   RENK["temiz_yaz"]
    elif tik <= 2:
        return "⚠️ Uyarı",        RENK["uyari_bg"],   RENK["uyari_yaz"]
    else:
        return "🚨 İdari İşlem",  RENK["tehlike_bg"], RENK["tehlike_yaz"]


def _sutun_gen(ws, col: int, gen: float):
    ws.column_dimensions[get_column_letter(col)].width = gen


# ══════════════════════════════════════════════════════════════════════════
# Ana Dışa Aktarım Fonksiyonu
# ══════════════════════════════════════════════════════════════════════════

def excel_raporu_olustur(
    kayit_yolu: str,
    ogretmen_adi: str,
    sinif_listesi: list[dict],          # [{id, sinif_adi}, ...]
    yalnizca_sinif_id: int | None = None,  # None → tüm sınıflar
) -> str:
    """
    Excel dosyası oluşturur ve kayit_yolu'na kaydeder.
    Dönüş: kaydedilen dosya yolu.
    """
    if not OPENPYXL_OK:
        raise ImportError(
            "openpyxl kütüphanesi bulunamadı.\n"
            "Lütfen terminalde şunu çalıştırın:\n  pip install openpyxl"
        )

    wb = Workbook()
    wb.remove(wb.active)   # Boş default sayfayı kaldır

    # Hangi sınıfları işleyeceğiz?
    if yalnizca_sinif_id is not None:
        hedef_siniflar = [s for s in sinif_listesi
                          if s["id"] == yalnizca_sinif_id]
    else:
        hedef_siniflar = sinif_listesi

    tarih_str = datetime.now().strftime("%d/%m/%Y  %H:%M")

    # ── 1. Sayfa: Özet (her sınıf yan yana blok) ──────────────────────────
    _ozet_sayfasi(wb, ogretmen_adi, hedef_siniflar, tarih_str)

    # ── 2. Sayfa: Tüm Tik Detayları ───────────────────────────────────────
    _detay_sayfasi(wb, ogretmen_adi, hedef_siniflar, tarih_str)

    # ── 3. Sayfa: İstatistik Özeti ────────────────────────────────────────
    _istatistik_sayfasi(wb, ogretmen_adi, hedef_siniflar, tarih_str)

    wb.save(kayit_yolu)
    return kayit_yolu


# ══════════════════════════════════════════════════════════════════════════
# Sayfa 1 – Öğrenci Özet Listesi
# ══════════════════════════════════════════════════════════════════════════

def _ozet_sayfasi(wb: Workbook, ogretmen: str,
                  siniflar: list[dict], tarih: str):
    ws = wb.create_sheet("📋 Özet Liste")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A6"

    # Başlık bloğu
    ws.merge_cells("A1:I1")
    h1 = ws["A1"]
    h1.value = "🏫  Erenler Cumhuriyet Ortaokulu – Öğrenci Disiplin Raporu"
    h1.font      = Font(bold=True, size=15, color=RENK["baslik_yaz"])
    h1.fill      = _dolu_dolgu(RENK["baslik_bg"])
    h1.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 34

    ws.merge_cells("A2:I2")
    h2 = ws["A2"]
    h2.value = (f"Öğretmen: {ogretmen}   |   "
                f"Rapor Tarihi: {tarih}   |   "
                f"Sınıf(lar): {', '.join(s['sinif_adi'] for s in siniflar)}")
    h2.font      = Font(size=10, color=RENK["gri_yazi"])
    h2.fill      = _dolu_dolgu("FFF0F4FF")
    h2.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # Boşluk satırı
    ws.row_dimensions[3].height = 6

    # Renk açıklaması
    ws.merge_cells("A4:I4")
    aciklama = ws["A4"]
    aciklama.value = ("✅ 0 tik = Temiz   |   "
                      "⚠️ 1-2 tik = Uyarı   |   "
                      "🚨 3+ tik = İdari İşlem Gerektirir")
    aciklama.font      = Font(size=9, italic=True, color=RENK["gri_yazi"])
    aciklama.alignment = Alignment(horizontal="center")
    ws.row_dimensions[4].height = 16

    # Başlık satırı
    basliklar = ["#", "Sınıf", "Öğrenci No", "Ad Soyad",
                 "Tik Sayısı", "Durum", "Son Tik Tarihi", "İhlal Özeti", ""]
    for col, b in enumerate(basliklar, 1):
        h = ws.cell(row=5, column=col, value=b)
        h.font      = Font(bold=True, size=10, color=RENK["sutun_yaz"])
        h.fill      = _dolu_dolgu(RENK["sutun_bg"])
        h.alignment = Alignment(horizontal="center", vertical="center",
                                 wrap_text=True)
        h.border    = _ince_kenar()
    ws.row_dimensions[5].height = 22

    # Genişlikler
    for col, gen in enumerate([5, 8, 11, 26, 10, 18, 18, 30, 3], 1):
        _sutun_gen(ws, col, gen)

    # Tüm sınıfların öğrencilerini topla
    tum_ogrenciler = []
    for sinif in siniflar:
        for ogr in sinif_ogrencileri(sinif["id"]):
            ogr["sinif_adi"] = sinif["sinif_adi"]
            tum_ogrenciler.append(ogr)

    # Tik sayısına göre sırala (azalan)
    tum_ogrenciler.sort(key=lambda o: (-o["tik_sayisi"], o["sinif_adi"],
                                        o["ad_soyad"]))

    for sira, ogr in enumerate(tum_ogrenciler, 1):
        satir = sira + 5
        tik = ogr["tik_sayisi"]
        durum_yazi, bg, fg = _durum(tik)

        # Tik geçmişinden özet bilgiler
        gecmis = ogrenci_tik_gecmisi(ogr["id"])
        son_tarih = gecmis[0]["tarih"] if gecmis else "-"
        kriterler = {}
        for k in gecmis:
            k_ad = k["kriter"]
            kriterler[k_ad] = kriterler.get(k_ad, 0) + 1
        ihtal_ozet = ",  ".join(
            f"{ad} ({sayi}x)" for ad, sayi in
            sorted(kriterler.items(), key=lambda x: -x[1])[:3]
        ) or "-"

        degerler = [sira, ogr["sinif_adi"], ogr["ogr_no"],
                    ogr["ad_soyad"], tik, durum_yazi, son_tarih, ihtal_ozet, ""]

        alt_bg = RENK["alt_satir"] if sira % 2 == 0 else "FFFFFFFF"

        for col, val in enumerate(degerler, 1):
            h = ws.cell(row=satir, column=col, value=val)
            h.border    = _ince_kenar()
            h.alignment = Alignment(vertical="center",
                                     horizontal="center" if col in (1, 2, 3, 5) else "left",
                                     wrap_text=True)
            h.font      = Font(size=10, color=RENK["siyah"])

            # Durum sütunu ve tik sütununa özel renk
            if col == 6:
                h.fill = _dolu_dolgu(bg)
                h.font = Font(size=10, bold=True, color=fg)
            elif col == 5:
                h.fill = _dolu_dolgu(bg)
                h.font = Font(size=11, bold=True, color=fg)
            else:
                h.fill = _dolu_dolgu(alt_bg)

        ws.row_dimensions[satir].height = 18

    # Filtre ekle
    ws.auto_filter.ref = f"A5:H{5 + len(tum_ogrenciler)}"


# ══════════════════════════════════════════════════════════════════════════
# Sayfa 2 – Tik Kayıt Detayları
# ══════════════════════════════════════════════════════════════════════════

def _detay_sayfasi(wb: Workbook, ogretmen: str,
                   siniflar: list[dict], tarih: str):
    ws = wb.create_sheet("📝 Tik Detayları")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"

    # Başlık
    ws.merge_cells("A1:G1")
    h = ws["A1"]
    h.value = "📝  Tik Kayıt Detayları"
    h.font  = Font(bold=True, size=13, color=RENK["baslik_yaz"])
    h.fill  = _dolu_dolgu(RENK["baslik_bg"])
    h.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:G2")
    s = ws["A2"]
    s.value = f"Öğretmen: {ogretmen}   |   Tarih: {tarih}"
    s.font  = Font(size=9, color=RENK["gri_yazi"])
    s.fill  = _dolu_dolgu("FFF0F4FF")
    s.alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 16

    # Kolon başlıkları
    basliklar = ["Sınıf", "Öğrenci No", "Ad Soyad",
                 "İhlal Kriteri", "Tiki Atan Öğretmen", "Tarih / Saat", ""]
    for col, b in enumerate(basliklar, 1):
        h2 = ws.cell(row=3, column=col, value=b)
        h2.font      = Font(bold=True, size=10, color=RENK["sutun_yaz"])
        h2.fill      = _dolu_dolgu(RENK["sutun_bg"])
        h2.alignment = Alignment(horizontal="center", vertical="center")
        h2.border    = _ince_kenar()
    ws.row_dimensions[3].height = 20

    for col, gen in enumerate([8, 11, 26, 32, 24, 20, 3], 1):
        _sutun_gen(ws, col, gen)

    satir = 4
    for sinif in siniflar:
        for ogr in sinif_ogrencileri(sinif["id"]):
            gecmis = ogrenci_tik_gecmisi(ogr["id"])
            for k in gecmis:
                alt_bg = RENK["detay_alt"] if satir % 2 == 0 else RENK["detay_bg"]
                vals = [sinif["sinif_adi"], ogr["ogr_no"], ogr["ad_soyad"],
                        k["kriter"], k["ogretmen"], k["tarih"], ""]
                for col, val in enumerate(vals, 1):
                    c = ws.cell(row=satir, column=col, value=val)
                    c.fill      = _dolu_dolgu(alt_bg)
                    c.border    = _ince_kenar()
                    c.alignment = Alignment(
                        vertical="center",
                        horizontal="center" if col in (1, 2) else "left"
                    )
                    c.font      = Font(size=9, color=RENK["siyah"])
                ws.row_dimensions[satir].height = 16
                satir += 1

    if satir == 4:
        ws.cell(row=4, column=1, value="Henüz tik kaydı bulunmamaktadır.")

    ws.auto_filter.ref = f"A3:F{satir - 1}"


# ══════════════════════════════════════════════════════════════════════════
# Sayfa 3 – İstatistik Özeti
# ══════════════════════════════════════════════════════════════════════════

def _istatistik_sayfasi(wb: Workbook, ogretmen: str,
                         siniflar: list[dict], tarih: str):
    ws = wb.create_sheet("📊 İstatistikler")
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:F1")
    h = ws["A1"]
    h.value = "📊  Sınıf İstatistik Raporu"
    h.font  = Font(bold=True, size=13, color=RENK["baslik_yaz"])
    h.fill  = _dolu_dolgu(RENK["baslik_bg"])
    h.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:F2")
    s = ws["A2"]
    s.value = f"Öğretmen: {ogretmen}   |   {tarih}"
    s.font  = Font(size=9, color=RENK["gri_yazi"])
    s.fill  = _dolu_dolgu("FFF0F4FF")
    s.alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 16

    # Sınıf istatistik tablosu
    basliklar = ["Sınıf", "Öğrenci", "Toplam Tik",
                 "✅ Temiz", "⚠️ Uyarı", "🚨 İdari İşlem"]
    for col, b in enumerate(basliklar, 1):
        h2 = ws.cell(row=4, column=col, value=b)
        h2.font      = Font(bold=True, size=10, color=RENK["sutun_yaz"])
        h2.fill      = _dolu_dolgu(RENK["sutun_bg"])
        h2.alignment = Alignment(horizontal="center", vertical="center")
        h2.border    = _ince_kenar()
    ws.row_dimensions[4].height = 20

    for col, gen in enumerate([9, 10, 11, 10, 10, 14], 1):
        _sutun_gen(ws, col, gen)

    # Her sınıf için istatistik hesapla
    kriterler_say: dict[str, int] = {}
    genel_toplam_tik = 0
    genel_ogrenci    = 0

    for satir_idx, sinif in enumerate(siniflar, 5):
        ogrenciler = sinif_ogrencileri(sinif["id"])
        toplam_ogrenci = len(ogrenciler)
        toplam_tik     = sum(o["tik_sayisi"] for o in ogrenciler)
        temiz          = sum(1 for o in ogrenciler if o["tik_sayisi"] == 0)
        uyari          = sum(1 for o in ogrenciler if 1 <= o["tik_sayisi"] <= 2)
        idari          = sum(1 for o in ogrenciler if o["tik_sayisi"] >= 3)

        genel_toplam_tik += toplam_tik
        genel_ogrenci    += toplam_ogrenci

        for o in ogrenciler:
            for k in ogrenci_tik_gecmisi(o["id"]):
                kriter_ad = k["kriter"]
                kriterler_say[kriter_ad] = kriterler_say.get(kriter_ad, 0) + 1

        alt_bg = RENK["alt_satir"] if satir_idx % 2 == 0 else "FFFFFFFF"
        vals = [sinif["sinif_adi"], toplam_ogrenci, toplam_tik,
                temiz, uyari, idari]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=satir_idx, column=col, value=val)
            c.border    = _ince_kenar()
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font      = Font(size=10, color=RENK["siyah"])
            if col == 6 and idari > 0:
                c.fill = _dolu_dolgu(RENK["tehlike_bg"])
                c.font = Font(size=10, bold=True, color=RENK["tehlike_yaz"])
            elif col == 5 and uyari > 0:
                c.fill = _dolu_dolgu(RENK["uyari_bg"])
                c.font = Font(size=10, bold=True, color=RENK["uyari_yaz"])
            elif col == 4:
                c.fill = _dolu_dolgu(RENK["temiz_bg"])
                c.font = Font(size=10, color=RENK["temiz_yaz"])
            else:
                c.fill = _dolu_dolgu(alt_bg)
        ws.row_dimensions[satir_idx].height = 18

    # Genel toplam satırı
    toplam_satir = 5 + len(siniflar)
    ws.cell(row=toplam_satir, column=1, value="GENEL TOPLAM").font = Font(
        bold=True, size=10, color=RENK["baslik_yaz"])
    ws.cell(row=toplam_satir, column=1).fill = _dolu_dolgu(RENK["baslik_bg"])
    ws.cell(row=toplam_satir, column=1).alignment = Alignment(horizontal="center")
    ws.cell(row=toplam_satir, column=2, value=genel_ogrenci)
    ws.cell(row=toplam_satir, column=3, value=genel_toplam_tik)
    for col in range(1, 7):
        c = ws.cell(row=toplam_satir, column=col)
        c.border = _ince_kenar()
        if col > 1:
            c.fill = _dolu_dolgu(RENK["baslik_bg"])
            c.font = Font(bold=True, size=10, color=RENK["baslik_yaz"])
        c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[toplam_satir].height = 22

    # ── En sık ihlal edilen kriterler ─────────────────────────────────────
    bos_satir = toplam_satir + 2
    ws.merge_cells(f"A{bos_satir}:F{bos_satir}")
    kh = ws.cell(row=bos_satir, column=1,
                  value="📌  En Sık İhlal Edilen Kriterler")
    kh.font      = Font(bold=True, size=11, color=RENK["baslik_yaz"])
    kh.fill      = _dolu_dolgu(RENK["sutun_bg"])
    kh.alignment = Alignment(horizontal="left", vertical="center",
                              indent=1)
    ws.row_dimensions[bos_satir].height = 22

    k_baslik_satir = bos_satir + 1
    for col, b in enumerate(["Sıra", "İhlal Kriteri", "Toplam Sayı", "", "", ""], 1):
        c = ws.cell(row=k_baslik_satir, column=col, value=b)
        c.font      = Font(bold=True, size=9, color=RENK["sutun_yaz"])
        c.fill      = _dolu_dolgu("FF475569")
        c.alignment = Alignment(horizontal="center")
        c.border    = _ince_kenar()

    sirali_kriterler = sorted(kriterler_say.items(),
                               key=lambda x: -x[1])[:15]
    for i, (kriter, sayi) in enumerate(sirali_kriterler, 1):
        s = k_baslik_satir + i
        alt_bg = RENK["alt_satir"] if i % 2 == 0 else "FFFFFFFF"

        ws.cell(row=s, column=1, value=i).fill      = _dolu_dolgu(alt_bg)
        ws.cell(row=s, column=1).font               = Font(size=9)
        ws.cell(row=s, column=1).alignment          = Alignment(horizontal="center")
        ws.cell(row=s, column=2, value=kriter).fill = _dolu_dolgu(alt_bg)
        ws.cell(row=s, column=2).font               = Font(size=9)
        ws.cell(row=s, column=3, value=sayi).fill   = _dolu_dolgu(
            RENK["tehlike_bg"] if sayi > 5 else
            RENK["uyari_bg"]   if sayi > 2 else
            RENK["temiz_bg"]
        )
        ws.cell(row=s, column=3).font = Font(size=9, bold=True)
        ws.cell(row=s, column=3).alignment = Alignment(horizontal="center")

        for col in range(1, 7):
            ws.cell(row=s, column=col).border = _ince_kenar()
        ws.row_dimensions[s].height = 16
