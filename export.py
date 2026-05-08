"""
export.py
---------
Excel rapor uretim modulu.
Gerekli: pip install openpyxl
"""

from __future__ import annotations
from datetime import datetime
from database import sinif_ogrencileri, ogrenci_tik_gecmisi

try:
    import openpyxl
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

RENK = {
    "baslik_bg":   "FF1A3A6B",
    "baslik_yaz":  "FFFFFFFF",
    "sutun_bg":    "FF2563EB",
    "sutun_yaz":   "FFFFFFFF",
    "alt_satir":   "FFF0F4FF",
    "temiz_bg":    "FFDCFCE7", "temiz_yaz":   "FF166534",
    "uyari_bg":    "FFFEF9C3", "uyari_yaz":   "FF92400E",
    "tehlike_bg":  "FFFEE2E2", "tehlike_yaz": "FF991B1B",
    "detay_bg":    "FFF8FAFF", "detay_alt":   "FFEFF6FF",
    "gri_yazi":    "FF64748B", "siyah":       "FF1E293B",
}

def _dolu(argb):
    return PatternFill(fill_type="solid", fgColor=argb)

def _kenar():
    s = Side(style="thin", color="FFCBD5E1")
    return Border(left=s, right=s, top=s, bottom=s)

def _sutun_gen(ws, col, gen):
    ws.column_dimensions[get_column_letter(col)].width = gen

def _durum(tik):
    if tik == 0:      return "Temiz",        RENK["temiz_bg"],   RENK["temiz_yaz"]
    elif tik <= 2:    return "Uyari",        RENK["uyari_bg"],   RENK["uyari_yaz"]
    elif tik <= 5:    return "Uyari",        RENK["uyari_bg"],   RENK["uyari_yaz"]
    elif tik <= 8:    return "Veli Bildir.", RENK["tehlike_bg"], RENK["tehlike_yaz"]
    elif tik <= 11:   return "Tutanak",      RENK["tehlike_bg"], RENK["tehlike_yaz"]
    else:             return "Disiplin",     RENK["tehlike_bg"], RENK["tehlike_yaz"]


def excel_raporu_olustur(
    kayit_yolu: str,
    ogretmen_adi: str,
    sinif_listesi: list[dict],
    yalnizca_sinif_id: int | None = None,
) -> str:
    if not OPENPYXL_OK:
        raise ImportError("pip install openpyxl")

    wb = Workbook()
    wb.remove(wb.active)

    hedef = ([s for s in sinif_listesi if s["id"] == yalnizca_sinif_id]
             if yalnizca_sinif_id else sinif_listesi)

    tarih = datetime.now().strftime("%d/%m/%Y %H:%M")
    _ozet(wb, ogretmen_adi, hedef, tarih)
    _detay(wb, ogretmen_adi, hedef, tarih)
    _istatistik(wb, ogretmen_adi, hedef, tarih)
    wb.save(kayit_yolu)
    return kayit_yolu


def _baslik_satiri(ws, row, cols, text, bg, fg, yukseklik=28):
    ws.merge_cells(f"A{row}:{get_column_letter(cols)}{row}")
    c = ws[f"A{row}"]
    c.value = text
    c.font = Font(bold=True, size=13, color=fg)
    c.fill = _dolu(bg)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = yukseklik


def _ozet(wb, ogretmen, siniflar, tarih):
    ws = wb.create_sheet("Ozet Liste")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A5"
    _baslik_satiri(ws, 1, 7, "Erenler Cumhuriyet Ortaokulu - Disiplin Raporu",
                   RENK["baslik_bg"], RENK["baslik_yaz"])

    ws.merge_cells("A2:G2")
    c = ws["A2"]
    c.value = f"Ogretmen: {ogretmen}  |  Tarih: {tarih}"
    c.font = Font(size=9, color=RENK["gri_yazi"])
    c.fill = _dolu("FFF0F4FF")
    c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 16

    basliklar = ["#", "Sinif", "No", "Ad Soyad", "Tik", "Durum", "Son Tik"]
    for col, b in enumerate(basliklar, 1):
        c = ws.cell(row=4, column=col, value=b)
        c.font = Font(bold=True, size=10, color=RENK["sutun_yaz"])
        c.fill = _dolu(RENK["sutun_bg"])
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _kenar()
    ws.row_dimensions[4].height = 20

    for col, gen in enumerate([5, 8, 9, 28, 8, 16, 18], 1):
        _sutun_gen(ws, col, gen)

    tum = []
    for s in siniflar:
        for o in sinif_ogrencileri(s["id"]):
            o["sinif_adi"] = s["sinif_adi"]
            tum.append(o)
    tum.sort(key=lambda o: (-o["tik_sayisi"], o["sinif_adi"], o["ad_soyad"]))

    for sira, o in enumerate(tum, 1):
        satir = sira + 4
        tik = o["tik_sayisi"]
        durum_yazi, bg, fg = _durum(tik)
        gecmis = ogrenci_tik_gecmisi(o["id"])
        son_tarih = gecmis[0]["tarih"] if gecmis else "-"
        alt_bg = RENK["alt_satir"] if sira % 2 == 0 else "FFFFFFFF"
        vals = [sira, o["sinif_adi"], o["ogr_no"], o["ad_soyad"], tik, durum_yazi, son_tarih]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=satir, column=col, value=val)
            c.border = _kenar()
            c.alignment = Alignment(vertical="center",
                                    horizontal="center" if col in (1,2,3,5) else "left")
            c.font = Font(size=10, color=RENK["siyah"])
            if col in (5, 6):
                c.fill = _dolu(bg)
                c.font = Font(size=10, bold=True, color=fg)
            else:
                c.fill = _dolu(alt_bg)
        ws.row_dimensions[satir].height = 17

    ws.auto_filter.ref = f"A4:G{4 + len(tum)}"


def _detay(wb, ogretmen, siniflar, tarih):
    ws = wb.create_sheet("Tik Detaylari")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"
    _baslik_satiri(ws, 1, 6, "Tik Kayit Detaylari", RENK["baslik_bg"], RENK["baslik_yaz"])

    ws.merge_cells("A2:F2")
    c = ws["A2"]
    c.value = f"Ogretmen: {ogretmen}  |  {tarih}"
    c.font = Font(size=9, color=RENK["gri_yazi"])
    c.fill = _dolu("FFF0F4FF")
    c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 16

    basliklar = ["Sinif", "No", "Ad Soyad", "Ihlal Kriteri", "Tiki Atan", "Tarih"]
    for col, b in enumerate(basliklar, 1):
        c = ws.cell(row=3, column=col, value=b)
        c.font = Font(bold=True, size=10, color=RENK["sutun_yaz"])
        c.fill = _dolu(RENK["sutun_bg"])
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _kenar()
    ws.row_dimensions[3].height = 20
    for col, gen in enumerate([8, 9, 26, 32, 24, 18], 1):
        _sutun_gen(ws, col, gen)

    satir = 4
    for s in siniflar:
        for o in sinif_ogrencileri(s["id"]):
            for k in ogrenci_tik_gecmisi(o["id"]):
                alt_bg = RENK["detay_alt"] if satir % 2 == 0 else RENK["detay_bg"]
                vals = [s["sinif_adi"], o["ogr_no"], o["ad_soyad"],
                        k["kriter"], k["ogretmen"], k["tarih"]]
                for col, val in enumerate(vals, 1):
                    c = ws.cell(row=satir, column=col, value=val)
                    c.fill = _dolu(alt_bg)
                    c.border = _kenar()
                    c.alignment = Alignment(vertical="center",
                                            horizontal="center" if col in (1,2) else "left")
                    c.font = Font(size=9, color=RENK["siyah"])
                ws.row_dimensions[satir].height = 15
                satir += 1

    if satir == 4:
        ws.cell(row=4, column=1, value="Tik kaydi bulunmamaktadir.")
    ws.auto_filter.ref = f"A3:F{max(satir-1, 3)}"


def _istatistik(wb, ogretmen, siniflar, tarih):
    ws = wb.create_sheet("Istatistikler")
    ws.sheet_view.showGridLines = False
    _baslik_satiri(ws, 1, 6, "Sinif Istatistikleri", RENK["baslik_bg"], RENK["baslik_yaz"])

    ws.merge_cells("A2:F2")
    c = ws["A2"]
    c.value = f"Ogretmen: {ogretmen}  |  {tarih}"
    c.font = Font(size=9, color=RENK["gri_yazi"])
    c.fill = _dolu("FFF0F4FF")
    c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 16

    basliklar = ["Sinif", "Ogrenci", "Toplam Tik", "Temiz", "Uyari+", "Kritik"]
    for col, b in enumerate(basliklar, 1):
        c = ws.cell(row=4, column=col, value=b)
        c.font = Font(bold=True, size=10, color=RENK["sutun_yaz"])
        c.fill = _dolu(RENK["sutun_bg"])
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _kenar()
    ws.row_dimensions[4].height = 20
    for col, gen in enumerate([9, 10, 12, 10, 10, 10], 1):
        _sutun_gen(ws, col, gen)

    kriterler_say: dict[str, int] = {}
    for idx, s in enumerate(siniflar, 5):
        ogrenciler = sinif_ogrencileri(s["id"])
        toplam_tik = sum(o["tik_sayisi"] for o in ogrenciler)
        temiz = sum(1 for o in ogrenciler if o["tik_sayisi"] == 0)
        uyari = sum(1 for o in ogrenciler if 1 <= o["tik_sayisi"] <= 5)
        kritik = sum(1 for o in ogrenciler if o["tik_sayisi"] >= 6)
        for o in ogrenciler:
            for k in ogrenci_tik_gecmisi(o["id"]):
                kr = k["kriter"]
                kriterler_say[kr] = kriterler_say.get(kr, 0) + 1

        alt_bg = RENK["alt_satir"] if idx % 2 == 0 else "FFFFFFFF"
        vals = [s["sinif_adi"], len(ogrenciler), toplam_tik, temiz, uyari, kritik]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=idx, column=col, value=val)
            c.border = _kenar()
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = Font(size=10, color=RENK["siyah"])
            if col == 6 and kritik > 0:
                c.fill = _dolu(RENK["tehlike_bg"])
                c.font = Font(size=10, bold=True, color=RENK["tehlike_yaz"])
            elif col == 4:
                c.fill = _dolu(RENK["temiz_bg"])
                c.font = Font(size=10, color=RENK["temiz_yaz"])
            else:
                c.fill = _dolu(alt_bg)
        ws.row_dimensions[idx].height = 18

    # En sik kriterler
    bos = 5 + len(siniflar) + 2
    _baslik_satiri(ws, bos, 6, "En Sik Ihlal Edilen Kriterler",
                   RENK["sutun_bg"], RENK["sutun_yaz"], 22)
    for col, b in enumerate(["Sira", "Ihlal Kriteri", "Sayi", "", "", ""], 1):
        c = ws.cell(row=bos+1, column=col, value=b)
        c.font = Font(bold=True, size=9, color=RENK["sutun_yaz"])
        c.fill = _dolu("FF475569")
        c.alignment = Alignment(horizontal="center")
        c.border = _kenar()

    for i, (kr, sayi) in enumerate(sorted(kriterler_say.items(), key=lambda x: -x[1])[:15], 1):
        s = bos + 1 + i
        alt_bg = RENK["alt_satir"] if i % 2 == 0 else "FFFFFFFF"
        for col, val in enumerate([i, kr, sayi, "", "", ""], 1):
            c = ws.cell(row=s, column=col, value=val)
            c.border = _kenar()
            c.alignment = Alignment(horizontal="center" if col != 2 else "left",
                                    vertical="center")
            c.font = Font(size=9, color=RENK["siyah"])
            c.fill = _dolu(
                RENK["tehlike_bg"] if col == 3 and sayi > 5 else
                RENK["uyari_bg"]   if col == 3 and sayi > 2 else
                alt_bg
            )
        ws.row_dimensions[s].height = 15
