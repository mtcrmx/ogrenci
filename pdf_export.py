"""
pdf_export.py
-------------
Disiplin analiz PDF üretimi + rapor anlık görüntüsü (snapshot).
Gerekli: pip install reportlab
"""

from __future__ import annotations

import io
import json
import os
import platform
from datetime import datetime
from html import escape as html_escape
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Paragraph,
        PageBreak,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing

    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    Drawing = Pie = VerticalBarChart = None  # type: ignore[misc, assignment]

from database import (
    gelisim_ozeti,
    ogrenci_odevleri,
    ogrenci_tik_gecmisi,
    sinif_ogrencileri,
    tik_kayitlari_siniflarda,
)
from export import _ihlal_ozeti_yazisi, _kriter_saf_metin
from rapor_analiz import (
    aylik_tik_sayilari,
    ogrenci_satirlarindan_durum,
    oneriler_snapshot_icinden,
)

_FONT_NAME = "RaporFont"
_FONT_READY = False


def _pdf_paragraph(metin: str, st: ParagraphStyle) -> Paragraph:
    """Tablo hücreleri için güvenli satır kaydırmalı metin (ReportLab mini-HTML)."""
    t = html_escape(str(metin or "").strip())
    if not t:
        t = "—"
    return Paragraph(t.replace("\n", "<br/>"), st)


def _durum_etiket(tik: int) -> str:
    if tik >= 12:
        return "Disiplin"
    if tik >= 9:
        return "Tutanak"
    if tik >= 6:
        return "Veli bilgilendirme"
    if tik >= 3:
        return "Uyarı"
    return "Temiz"


def _register_font() -> str:
    global _FONT_READY
    if _FONT_READY:
        return _FONT_NAME
    candidates = []
    if platform.system() == "Windows":
        w = os.environ.get("WINDIR", r"C:\Windows")
        candidates.extend(
            [
                os.path.join(w, "Fonts", "arial.ttf"),
                os.path.join(w, "Fonts", "calibri.ttf"),
            ]
        )
    candidates.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
    )
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                pdfmetrics.registerFont(TTFont(_FONT_NAME, path))
                _FONT_READY = True
                return _FONT_NAME
            except Exception:
                continue
    _FONT_READY = True
    return "Helvetica"


def _odev_durum_pie_drawing(tam_s: int, yap_mad: int, font_name: str, w_cell: float) -> Drawing:
    """Sınıf içi yapan/yapmayan pasta grafiği."""
    h = w_cell * 0.92
    d = Drawing(w_cell, h)
    pie = Pie()
    pie.x = w_cell * 0.02
    pie.y = h * 0.06
    side = min(w_cell * 0.55, h * 0.88)
    pie.width = side
    pie.height = side
    pie.data = [float(tam_s), float(yap_mad)]
    pie.labels = [f"Yaptı ({tam_s})", f"Yapmadı ({yap_mad})"]
    pie.slices[0].fillColor = colors.HexColor("#16a34a")
    pie.slices[1].fillColor = colors.HexColor("#dc2626")
    for i in range(2):
        pie.slices[i].strokeColor = colors.white
        pie.slices[i].strokeWidth = 0.75
        pie.slices[i].fontName = font_name
        pie.slices[i].fontSize = 7
    pie.slices.fontName = font_name
    d.add(pie)
    return d


def _odev_durum_bar_drawing(tam_s: int, yap_mad: int, font_name: str, w_cell: float) -> Drawing:
    """Aynı verinin sütun grafiği (özet görünüm)."""
    h = w_cell * 0.92
    d = Drawing(w_cell, h)
    bc = VerticalBarChart()
    bc.x = w_cell * 0.08
    bc.y = h * 0.14
    bc.height = h * 0.58
    bc.width = w_cell * 0.84
    bc.data = [[float(tam_s), float(yap_mad)]]
    bc.categoryAxis.categoryNames = ["Yaptı", "Yapmadı"]
    bc.categoryAxis.labels.fontName = font_name
    bc.categoryAxis.labels.fontSize = 8
    bc.valueAxis.labels.fontName = font_name
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.strokeColor = colors.HexColor("#94a3b8")
    bc.categoryAxis.strokeColor = colors.HexColor("#94a3b8")
    m = float(max(tam_s, yap_mad, 1))
    bc.valueAxis.valueMax = m * 1.2
    bc.valueAxis.valueMin = 0
    bc.bars.strokeColor = colors.HexColor("#1e293b")
    bc.bars.strokeWidth = 0.5
    try:
        bc.bars[(0, 0)].fillColor = colors.HexColor("#16a34a")
        bc.bars[(0, 1)].fillColor = colors.HexColor("#dc2626")
    except Exception:
        bc.bars[0].fillColor = colors.HexColor("#2563eb")
    d.add(bc)
    return d


def _odev_durum_grafik_tablosu(
    tam_s: int,
    yap_mad: int,
    font_name: str,
    usable_w: float,
    small: ParagraphStyle,
) -> Table:
    """Yan yana pasta ve sütun grafiği + kısa açıklama."""
    w = usable_w * 0.48
    pie_d = _odev_durum_pie_drawing(tam_s, yap_mad, font_name, w)
    bar_d = _odev_durum_bar_drawing(tam_s, yap_mad, font_name, w)
    cap1 = Paragraph(
        '<font size="7" color="#64748b">Pasta: yapan / yapmayan öğrenci dağılımı</font>',
        small,
    )
    cap2 = Paragraph(
        '<font size="7" color="#64748b">Sütun: aynı verinin sayısal görünümü '
        "(finansal “mum” grafiği bu özet veriye uygun değildir)</font>",
        small,
    )
    gt = Table([[pie_d, bar_d], [cap1, cap2]], colWidths=[w, w], hAlign="CENTER")
    gt.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
            ]
        )
    )
    return gt


def derle_analiz_snapshot(
    siniflar: list[dict],
    yalnizca_sinif_id: int | None,
) -> dict[str, Any]:
    """Mevcut veritabanından PDF ve kalıcı JSON arşivi için anlık görüntü."""
    if yalnizca_sinif_id is not None:
        hedef = [s for s in siniflar if s["id"] == yalnizca_sinif_id]
    else:
        hedef = siniflar
    sinif_ids = [s["id"] for s in hedef]
    kapsam_metin = ", ".join(s["sinif_adi"] for s in hedef) if hedef else "(sınıf yok)"

    tum_ogr: list[dict] = []
    for s in hedef:
        for o in sinif_ogrencileri(s["id"]):
            o = dict(o)
            o["sinif_adi"] = s["sinif_adi"]
            tum_ogr.append(o)
    tum_ogr.sort(key=lambda x: (x.get("sinif_adi") or "", int(x.get("ogr_no") or 0)))

    tik_rows = tik_kayitlari_siniflarda(sinif_ids)
    kriter_cnt: dict[str, int] = {}
    for row in tik_rows:
        kt = _kriter_saf_metin(row.get("kriter") or "")
        key = kt or ((row.get("kriter") or "")[:120])
        if key:
            kriter_cnt[key] = kriter_cnt.get(key, 0) + 1

    tik_archive: list[dict] = []
    for r in tik_rows:
        rr = dict(r)
        rr["kriter_temiz"] = _kriter_saf_metin(r.get("kriter") or "") or (r.get("kriter") or "")[:120]
        tik_archive.append(rr)

    ogrenci_satirlari: list[dict] = []
    sinif_ozet_map: dict[str, dict] = {}
    toplam_tik = 0
    for o in tum_ogr:
        oid = o["id"]
        gecmis = ogrenci_tik_gecmisi(oid)
        tik_n = int(o.get("tik_sayisi") or 0)
        toplam_tik += tik_n
        odevler = ogrenci_odevleri(oid, 80)
        tam = sum(1 for x in odevler if x.get("tamamlandi"))
        odev_oran = round(tam * 100 / len(odevler)) if odevler else 0
        try:
            gel = gelisim_ozeti(oid)
            xp = int(gel["puan"].get("xp") or 0)
        except Exception:
            xp = 0
        son_tik = gecmis[0]["tarih"] if gecmis else "-"
        oz = _ihlal_ozeti_yazisi(gecmis)
        ogrenci_satirlari.append(
            {
                "ogr_no": o.get("ogr_no"),
                "ad_soyad": o.get("ad_soyad"),
                "sinif_adi": o.get("sinif_adi"),
                "tik_sayisi": tik_n,
                "durum": _durum_etiket(tik_n),
                "ihlal_ozet": oz,
                "son_tik": son_tik,
                "odev_oran": odev_oran,
                "gelisim_xp": xp,
            }
        )
        sad = o["sinif_adi"]
        sa = sinif_ozet_map.setdefault(
            sad,
            {
                "sinif_adi": sad,
                "ogrenci": 0,
                "toplam_tik": 0,
                "temiz": 0,
                "uyari": 0,
                "idari": 0,
            },
        )
        sa["ogrenci"] += 1
        sa["toplam_tik"] += tik_n
        if tik_n == 0:
            sa["temiz"] += 1
        elif tik_n <= 2:
            sa["uyari"] += 1
        else:
            sa["idari"] += 1

    n = len(ogrenci_satirlari)
    meta = {
        "olusturma": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kapsam_metin": kapsam_metin,
        "sinif_ids": sinif_ids,
    }
    ozet = {
        "ogrenci_sayisi": n,
        "toplam_tik": toplam_tik,
        "tik_kayit_adedi": len(tik_rows),
        "ortalama_tik": round(toplam_tik / n, 2) if n else 0,
    }
    risk_sorted = sorted(
        ogrenci_satirlari,
        key=lambda x: (-int(x.get("tik_sayisi") or 0), (x.get("ad_soyad") or "")),
    )[:28]
    risk_ozet = [
        {
            "ad_soyad": r.get("ad_soyad"),
            "sinif_adi": r.get("sinif_adi"),
            "tik": int(r.get("tik_sayisi") or 0),
            "durum": r.get("durum"),
        }
        for r in risk_sorted
    ]
    base: dict[str, Any] = {
        "meta": meta,
        "ozet": ozet,
        "sinif_ozet": sorted(sinif_ozet_map.values(), key=lambda x: x["sinif_adi"]),
        "ogrenciler": ogrenci_satirlari,
        "kriter_dagilim": dict(sorted(kriter_cnt.items(), key=lambda x: (-x[1], x[0]))),
        "tik_satirlari": tik_archive,
        "durum_dagilimi": ogrenci_satirlarindan_durum(ogrenci_satirlari),
        "aylik_trend": aylik_tik_sayilari(tik_rows),
        "risk_ozet": risk_ozet,
    }
    base["oneriler"] = oneriler_snapshot_icinden(base)
    return base


def pdf_analiz_uret_bytes(snapshot: dict[str, Any], ogretmen_adi: str) -> bytes:
    if not REPORTLAB_OK:
        raise ImportError("reportlab kurulu degil (pip install reportlab)")
    fn = _register_font()
    margin_x = 1.5 * cm
    usable_w = A4[0] - 2 * margin_x

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=margin_x,
        leftMargin=margin_x,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Disiplin Analiz Raporu",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="Ttl",
        parent=styles["Heading1"],
        fontName=fn,
        fontSize=16,
        spaceAfter=10,
    )
    h2 = ParagraphStyle(
        name="H2",
        parent=styles["Heading2"],
        fontName=fn,
        fontSize=12,
        spaceAfter=6,
    )
    body = ParagraphStyle(name="Bd", parent=styles["Normal"], fontName=fn, fontSize=9)
    small = ParagraphStyle(name="Sm", parent=styles["Normal"], fontName=fn, fontSize=7)

    # Tablo hücreleri: sabit leading ile çok satır düzgün görünsün
    td8 = ParagraphStyle(
        "td8", parent=styles["Normal"], fontName=fn, fontSize=8, leading=10,
        spaceBefore=0, spaceAfter=0,
    )
    td7 = ParagraphStyle(
        "td7", parent=styles["Normal"], fontName=fn, fontSize=7, leading=9,
        spaceBefore=0, spaceAfter=0,
    )
    td65 = ParagraphStyle(
        "td65", parent=styles["Normal"], fontName=fn, fontSize=6.5, leading=8,
        spaceBefore=0, spaceAfter=0,
    )
    th_w = ParagraphStyle(
        "thw", parent=td8, textColor=colors.whitesmoke,
    )
    th_w7 = ParagraphStyle(
        "thw7", parent=td7, textColor=colors.whitesmoke,
    )
    th_w65 = ParagraphStyle(
        "thw65", parent=td65, textColor=colors.whitesmoke,
    )

    def tbl_pad():
        return [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]

    story: list = []
    meta = snapshot.get("meta") or {}
    ozet = snapshot.get("ozet") or {}

    story.append(Paragraph("Erenler Cumhuriyet Ortaokulu", title_style))
    story.append(Paragraph("Disiplin — Detaylı Analiz Raporu", title_style))
    story.append(
        Paragraph(
            f"Öğretmen: {html_escape(str(ogretmen_adi))}<br/>"
            f"Tarih: {html_escape(str(meta.get('olusturma', '-')))}<br/>"
            f"Kapsam: {html_escape(str(meta.get('kapsam_metin', '-')))}",
            body,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    oz_txt = (
        f"Öğrenci sayısı: {ozet.get('ogrenci_sayisi', 0)} · "
        f"Toplam tik (öğrenci üzerinden): {ozet.get('toplam_tik', 0)} · "
        f"Tik kayıt satırı: {ozet.get('tik_kayit_adedi', 0)} · "
        f"Öğrenci başına ortalama tik: {ozet.get('ortalama_tik', 0)}"
    )
    story.append(Paragraph(oz_txt, body))
    oner = snapshot.get("oneriler") or {}
    if oner.get("ozet_cumle"):
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(html_escape(str(oner["ozet_cumle"])), body))
    story.append(Spacer(1, 0.5 * cm))

    dd = snapshot.get("durum_dagilimi") or {}
    if dd:
        story.append(Paragraph("Öğrenci durum bantları (tik sayısına göre)", h2))
        ddt = [
            [
                _pdf_paragraph("Bant", th_w),
                _pdf_paragraph("Öğrenci", th_w),
            ]
        ]
        for label, key in [
            ("Temiz (0 tik)", "temiz"),
            ("Uyarı (1–2)", "uyari"),
            ("İdari izlem (3–5)", "idari"),
            ("Veli bilgilendirme (6–8)", "veli"),
            ("Tutanak (9–11)", "tutanak"),
            ("Disiplin (12+)", "disiplin"),
        ]:
            ddt.append([
                _pdf_paragraph(label, td8),
                _pdf_paragraph(str(dd.get(key, 0)), td8),
            ])
        w1, w2 = usable_w * 0.72, usable_w * 0.28
        tdd = Table(ddt, colWidths=[w1, w2])
        tdd.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
                + tbl_pad()
            )
        )
        story.append(tdd)
        story.append(Spacer(1, 0.4 * cm))

    trend = snapshot.get("aylik_trend") or []
    if trend:
        story.append(Paragraph("Aylık tik kayıt sayısı (trend)", h2))
        tr = [
            [_pdf_paragraph("Ay (Yıl.Ay)", th_w), _pdf_paragraph("Kayıt adedi", th_w)],
        ]
        for row in trend[-18:]:
            tr.append([
                _pdf_paragraph(str(row.get("ay", "")), td8),
                _pdf_paragraph(str(row.get("adet", 0)), td8),
            ])
        wt = usable_w * 0.55, usable_w * 0.45
        ttrend = Table(tr, colWidths=list(wt))
        ttrend.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
                + tbl_pad()
            )
        )
        story.append(ttrend)
        story.append(Spacer(1, 0.4 * cm))

    if oner.get("veli") or oner.get("ogrenci") or oner.get("ogretmen"):
        story.append(Paragraph("Davranış iyileştirme — paydaş önerileri", h2))
        if oner.get("veli"):
            story.append(Paragraph("<b>Veli için öneriler</b>", body))
            for line in oner["veli"]:
                story.append(Paragraph(f"• {html_escape(str(line))}", body))
            story.append(Spacer(1, 0.15 * cm))
        if oner.get("ogrenci"):
            story.append(Paragraph("<b>Öğrenci için öneriler</b>", body))
            for line in oner["ogrenci"]:
                story.append(Paragraph(f"• {html_escape(str(line))}", body))
            story.append(Spacer(1, 0.15 * cm))
        if oner.get("ogretmen"):
            story.append(Paragraph("<b>Öğretmen için öneriler</b>", body))
            for line in oner["ogretmen"]:
                story.append(Paragraph(f"• {html_escape(str(line))}", body))
        story.append(Spacer(1, 0.45 * cm))

    ro = snapshot.get("risk_ozet") or []
    if ro:
        story.append(Paragraph("Risk özeti (okul genelinde en yüksek tik)", h2))
        rt = [
            [
                _pdf_paragraph("Sınıf", th_w7),
                _pdf_paragraph("Öğrenci", th_w7),
                _pdf_paragraph("Tik", th_w7),
                _pdf_paragraph("Durum", th_w7),
            ]
        ]
        for r in ro[:22]:
            rt.append([
                _pdf_paragraph(str(r.get("sinif_adi", "")), td7),
                _pdf_paragraph(str(r.get("ad_soyad", "")), td7),
                _pdf_paragraph(str(r.get("tik", 0)), td7),
                _pdf_paragraph(str(r.get("durum", "")), td7),
            ])
        wr = usable_w * 0.22, usable_w * 0.40, usable_w * 0.12, usable_w * 0.26
        trisk = Table(rt, colWidths=list(wr))
        trisk.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#991b1b")),
                    ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
                ]
                + tbl_pad()
            )
        )
        story.append(trisk)
        story.append(Spacer(1, 0.45 * cm))

    story.append(Paragraph("Sınıf özeti", h2))
    so = [
        [
            _pdf_paragraph("Sınıf", th_w),
            _pdf_paragraph("Öğr.", th_w),
            _pdf_paragraph("Σ Tik", th_w),
            _pdf_paragraph("Temiz", th_w),
            _pdf_paragraph("Uyarı", th_w),
            _pdf_paragraph("İdari", th_w),
        ]
    ]
    for s in snapshot.get("sinif_ozet") or []:
        so.append([
            _pdf_paragraph(str(s.get("sinif_adi", "")), td8),
            _pdf_paragraph(str(s.get("ogrenci", 0)), td8),
            _pdf_paragraph(str(s.get("toplam_tik", 0)), td8),
            _pdf_paragraph(str(s.get("temiz", 0)), td8),
            _pdf_paragraph(str(s.get("uyari", 0)), td8),
            _pdf_paragraph(str(s.get("idari", 0)), td8),
        ])
    ws = [
        usable_w * 0.30,
        usable_w * 0.12,
        usable_w * 0.14,
        usable_w * 0.14,
        usable_w * 0.14,
        usable_w * 0.16,
    ]
    t1 = Table(so, colWidths=ws)
    t1.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ]
            + tbl_pad()
        )
    )
    story.append(t1)
    story.append(PageBreak())

    story.append(Paragraph("Öğrenci bazlı özet", h2))
    og_t = [
        [
            _pdf_paragraph("No", th_w7),
            _pdf_paragraph("Ad Soyad", th_w7),
            _pdf_paragraph("Sınıf", th_w7),
            _pdf_paragraph("Tik", th_w7),
            _pdf_paragraph("Durum", th_w7),
            _pdf_paragraph("Özet ihlaller", th_w7),
            _pdf_paragraph("Ödev%", th_w7),
            _pdf_paragraph("XP", th_w7),
        ]
    ]
    for r in snapshot.get("ogrenciler") or []:
        oz_full = r.get("ihlal_ozet") or ""
        og_t.append([
            _pdf_paragraph(str(r.get("ogr_no", "")), td7),
            _pdf_paragraph(str(r.get("ad_soyad", "")), td7),
            _pdf_paragraph(str(r.get("sinif_adi", "")), td7),
            _pdf_paragraph(str(r.get("tik_sayisi", 0)), td7),
            _pdf_paragraph(str(r.get("durum", "")), td7),
            _pdf_paragraph(str(oz_full), td7),
            _pdf_paragraph(str(r.get("odev_oran", 0)), td7),
            _pdf_paragraph(str(r.get("gelisim_xp", 0)), td7),
        ])
    wo = [
        usable_w * 0.055,
        usable_w * 0.195,
        usable_w * 0.125,
        usable_w * 0.055,
        usable_w * 0.115,
        usable_w * 0.285,
        usable_w * 0.085,
        usable_w * 0.085,
    ]
    ot = Table(og_t, colWidths=wo, repeatRows=1)
    ot.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
            ]
            + tbl_pad()
        )
    )
    story.append(ot)
    story.append(PageBreak())

    story.append(Paragraph("İhlal türü dağılımı (temiz metin)", h2))
    kd = [[_pdf_paragraph("İhlal türü", th_w), _pdf_paragraph("Adet", th_w)]]
    for k, v in (snapshot.get("kriter_dagilim") or {}).items():
        kd.append([
            _pdf_paragraph(str(k), td8),
            _pdf_paragraph(str(v), td8),
        ])
    if len(kd) == 1:
        kd.append([_pdf_paragraph("Kayıt yok", td8), _pdf_paragraph("0", td8)])
    wk = usable_w * 0.78, usable_w * 0.22
    tk = Table(kd, colWidths=list(wk))
    tk.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
            + tbl_pad()
        )
    )
    story.append(tk)
    story.append(PageBreak())

    story.append(Paragraph("Tik kayıtları (arşiv anlık görüntüsü)", h2))
    story.append(
        Paragraph(
            "Bu bölüm üretim anındaki her tik satırını içerir; veritabanından silinse bile "
            "PDF ve JSON arşivinde kalır.",
            body,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    det = [
        [
            _pdf_paragraph("Tarih", th_w65),
            _pdf_paragraph("Sınıf", th_w65),
            _pdf_paragraph("No", th_w65),
            _pdf_paragraph("Öğrenci", th_w65),
            _pdf_paragraph("İhlal", th_w65),
            _pdf_paragraph("Öğretmen", th_w65),
        ]
    ]
    rows = snapshot.get("tik_satirlari") or []
    for r in rows:
        det.append([
            _pdf_paragraph(str(r.get("tarih", "")), td65),
            _pdf_paragraph(str(r.get("sinif_adi", "")), td65),
            _pdf_paragraph(str(r.get("ogr_no", "")), td65),
            _pdf_paragraph(str(r.get("ad_soyad", "")), td65),
            _pdf_paragraph(str(r.get("kriter_temiz", "") or r.get("kriter", "")), td65),
            _pdf_paragraph(str(r.get("ogretmen", "")), td65),
        ])
    if len(det) == 1:
        det.append([
            _pdf_paragraph("-", td65),
            _pdf_paragraph("-", td65),
            _pdf_paragraph("-", td65),
            _pdf_paragraph("-", td65),
            _pdf_paragraph("Kayıt yok", td65),
            _pdf_paragraph("-", td65),
        ])

    wd = [
        usable_w * 0.13,
        usable_w * 0.11,
        usable_w * 0.065,
        usable_w * 0.185,
        usable_w * 0.335,
        usable_w * 0.175,
    ]
    dt = Table(det, colWidths=wd, repeatRows=1)
    dt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("GRID", (0, 0), (-1, -1), 0.15, colors.lightgrey),
            ]
            + tbl_pad()
        )
    )
    story.append(dt)

    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            "Sunum ve paylaşım için bu rapor üretildi. Arşiv menüsünden geçmiş PDF’lere "
            "yeniden ulaşabilirsiniz.",
            small,
        )
    )

    doc.build(story)
    return buf.getvalue()


def _odev_ogrenci_sayfasi_flowables(
    detay: dict[str, Any],
    ogr: dict[str, Any],
    ogretmen_adi: str,
    fn: str,
    usable_w: float,
    *,
    tam_s: int,
    yap_mad: int,
    top: int,
    pct: int,
) -> list:
    """Tek öğrenci için bir PDF sayfası (Flowable listesi)."""
    odev = detay.get("odev") or {}
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
    styles = getSampleStyleSheet()
    h_okul = colors.HexColor("#0f172a")
    title_style = ParagraphStyle(
        name="OgrTtl",
        parent=styles["Heading1"],
        fontName=fn,
        fontSize=13,
        spaceAfter=4,
    )
    h2 = ParagraphStyle(
        name="OgrH2",
        parent=styles["Heading2"],
        fontName=fn,
        fontSize=10,
        spaceBefore=4,
        spaceAfter=4,
        textColor=h_okul,
    )
    body = ParagraphStyle(name="OgrBd", parent=styles["Normal"], fontName=fn, fontSize=9)
    small = ParagraphStyle(name="OgrSm", parent=styles["Normal"], fontName=fn, fontSize=7.5)
    td8 = ParagraphStyle(
        "ogr_td8",
        parent=styles["Normal"],
        fontName=fn,
        fontSize=8,
        leading=10,
        spaceBefore=0,
        spaceAfter=0,
    )
    th_acc = ParagraphStyle(
        "ogr_tha",
        parent=td8,
        textColor=colors.white,
        fontName=fn,
    )

    def tbl_pad():
        return [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]

    sev = int(odev.get("sinif_seviyesi") or 0)
    konu = (odev.get("konu_adi") or "").strip()
    yap = (ogr.get("durum") or "tamamlamadi") == "tamamladi"
    etik = "Yaptı" if yap else "Yapmadı"

    sf: list = []
    sf.append(Paragraph("Erenler Cumhuriyet Ortaokulu", title_style))
    sf.append(
        Paragraph(
            "<b>Bireysel ödev / tema raporu</b>",
            ParagraphStyle(
                "ogr_sub",
                parent=title_style,
                fontSize=10,
                textColor=h_okul,
                spaceAfter=8,
            ),
        )
    )
    ad = html_escape(str(ogr.get("ad_soyad") or "—").strip())
    ono = html_escape(str(ogr.get("ogr_no") or "—").strip())
    sf.append(
        Paragraph(
            f"<b>{ad}</b> · öğr. no {ono}",
            h2,
        )
    )

    oz_rows = [
        [_pdf_paragraph("Öğretmen", th_acc), _pdf_paragraph(str(ogretmen_adi or "—"), td8)],
        [_pdf_paragraph("Rapor", th_acc), _pdf_paragraph(now_s, td8)],
        [_pdf_paragraph("Ödev no", th_acc), _pdf_paragraph(str(odev.get("id", "—")), td8)],
        [_pdf_paragraph("Sınıf", th_acc), _pdf_paragraph(str(odev.get("sinif_adi", "—")), td8)],
        [_pdf_paragraph("Ders", th_acc), _pdf_paragraph(str(odev.get("ders_adi", "—")), td8)],
        [_pdf_paragraph("Tema", th_acc), _pdf_paragraph(str(odev.get("tema_adi", "—")), td8)],
    ]
    if konu:
        oz_rows.append(
            [_pdf_paragraph("Öğrenme kanıtları", th_acc), _pdf_paragraph(konu[:900], td8)]
        )
    if 5 <= sev <= 8:
        oz_rows.append([_pdf_paragraph("TYMM düzeyi", th_acc), _pdf_paragraph(str(sev), td8)])

    t_oz = Table(oz_rows, colWidths=[usable_w * 0.28, usable_w * 0.72])
    t_oz.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.whitesmoke),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, -1), fn),
            ]
            + tbl_pad()
        )
    )
    sf.append(t_oz)
    sf.append(Spacer(1, 0.35 * cm))

    dur_bg = colors.HexColor("#dcfce7") if yap else colors.HexColor("#fee2e2")
    dur_tx = colors.HexColor("#14532d") if yap else colors.HexColor("#7f1d1d")
    pst = ParagraphStyle(
        "durum_big",
        parent=body,
        fontName=fn,
        fontSize=14,
        leading=18,
        textColor=dur_tx,
        alignment=1,
    )
    dur_tab = Table([[Paragraph(f"<b>{etik}</b>", pst)]], colWidths=[usable_w])
    dur_tab.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), dur_bg),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    sf.append(dur_tab)
    sf.append(Spacer(1, 0.3 * cm))

    kiy = (
        f"Sınıf özeti (aynı ödev): <b>{tam_s}</b> yaptı, <b>{yap_mad}</b> yapmadı; "
        f"genel tamamlanma <b>%{pct}</b>. Bu öğrenci kaydı, rapor anına göre "
        f"<b>{etik.lower()}</b> olarak işaretlenmiştir."
    )
    sf.append(Paragraph(kiy, body))
    sf.append(Spacer(1, 0.35 * cm))

    if top > 0:
        sf.append(_odev_durum_grafik_tablosu(tam_s, yap_mad, fn, usable_w, small))
        sf.append(Spacer(1, 0.35 * cm))

    try:
        kodlar = json.loads(odev.get("ogrenme_cikti_kodlari_json") or "[]")
        if not isinstance(kodlar, list):
            kodlar = []
    except Exception:
        kodlar = []
    if kodlar:
        sf.append(Paragraph("<b>Öğrenme çıktısı kodları</b>", h2))
        kr = [[_pdf_paragraph("#", th_acc), _pdf_paragraph("Kod", th_acc)]]
        for i, k in enumerate(kodlar[:30], 1):
            kr.append([_pdf_paragraph(str(i), td8), _pdf_paragraph(str(k), td8)])
        tk = Table(kr, colWidths=[usable_w * 0.1, usable_w * 0.9], repeatRows=1)
        tk.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b45309")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ]
                + tbl_pad()
            )
        )
        sf.append(tk)
        sf.append(Spacer(1, 0.25 * cm))

    try:
        cik = json.loads(odev.get("ogrenme_ciktilari_json") or "[]")
        if not isinstance(cik, list):
            cik = []
    except Exception:
        cik = []
    if cik:
        sf.append(Paragraph("<b>Seçilen öğrenme çıktıları</b>", h2))
        for i, sat in enumerate(cik[:35], 1):
            sf.append(
                Paragraph(f"{i}. {html_escape(str(sat)[:480])}", td8)
            )

    sf.append(Spacer(1, 0.4 * cm))
    sf.append(
        Paragraph(
            "Bu sayfa yalnızca ilgili öğrenci ve bu ödev kaydı için üretilmiştir.",
            small,
        )
    )
    return sf


def _pdf_odev_tek_ogrenci_bytes(
    detay: dict[str, Any],
    ogretmen_adi: str,
    tek_ogr: dict[str, Any],
    fn: str,
    margin_x: float,
) -> bytes:
    usable_w = A4[0] - 2 * margin_x
    ogrenciler = detay.get("ogrenciler") or []
    tam_s = sum(1 for o in ogrenciler if (o.get("durum") or "") == "tamamladi")
    yap_mad = max(0, len(ogrenciler) - tam_s)
    top = len(ogrenciler)
    pct = round((tam_s / top * 100) if top else 0)
    buf = io.BytesIO()
    odev = detay.get("odev") or {}
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=margin_x,
        leftMargin=margin_x,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f"OdevOgr_{odev.get('id', '')}_{tek_ogr.get('id', '')}",
    )
    story = _odev_ogrenci_sayfasi_flowables(
        detay,
        tek_ogr,
        ogretmen_adi,
        fn,
        usable_w,
        tam_s=tam_s,
        yap_mad=yap_mad,
        top=top,
        pct=pct,
    )
    doc.build(story)
    return buf.getvalue()


def pdf_odev_raporu_bytes(
    detay: dict[str, Any],
    ogretmen_adi: str,
    *,
    rapor_turu: str = "sinif",
    ogrenci_id: int | None = None,
) -> bytes:
    """Ödev / tema kaydı için PDF: tablolar, pasta ve sütun grafikleri; isteğe bağlı öğrenci sayfaları.

    ``rapor_turu``: ``sinif`` (varsayılan), ``hepsi`` / ``tum_ogrenciler`` (sınıf özeti + her öğrenci sayfası),
    ``ogrenci`` / ``tek_ogrenci`` (yalnızca ``ogrenci_id`` ile).
    """
    if not REPORTLAB_OK:
        raise ImportError("reportlab kurulu degil (pip install reportlab)")
    fn = _register_font()
    margin_x = 1.5 * cm
    usable_w = A4[0] - 2 * margin_x

    odev = detay.get("odev") or {}
    ogrenciler = detay.get("ogrenciler") or []

    try:
        ciktilar = json.loads(odev.get("ogrenme_ciktilari_json") or "[]")
        if not isinstance(ciktilar, list):
            ciktilar = []
    except Exception:
        ciktilar = []
    try:
        kodlar = json.loads(odev.get("ogrenme_cikti_kodlari_json") or "[]")
        if not isinstance(kodlar, list):
            kodlar = []
    except Exception:
        kodlar = []

    sev = int(odev.get("sinif_seviyesi") or 0)
    tam_s = sum(
        1 for o in ogrenciler if (o.get("durum") or "") == "tamamladi"
    )
    yap_mad = max(0, len(ogrenciler) - tam_s)
    top = len(ogrenciler)
    pct = round((tam_s / top * 100) if top else 0)
    pct_y = round((yap_mad / top * 100) if top else 0)

    rt = (rapor_turu or "sinif").strip().lower()
    if rt in ("tek", "tek_ogrenci", "ogrenci"):
        rt = "tek_ogrenci"
    elif rt in ("hepsi", "tum", "tum_ogrenciler", "ogrenciler"):
        rt = "tum_ogrenciler"
    else:
        rt = "sinif"

    if rt == "tek_ogrenci":
        if ogrenci_id is None:
            raise ValueError("PDF için öğrenci seçilmedi (ogr parametresi).")
        tek: dict | None = None
        for o in ogrenciler:
            if int(o.get("id", -1)) == int(ogrenci_id):
                tek = o
                break
        if not tek:
            raise ValueError("Bu ödev kaydında seçilen öğrenci bulunamadı.")
        return _pdf_odev_tek_ogrenci_bytes(detay, ogretmen_adi, tek, fn, margin_x)

    sinif_ogrenci_tablosu = rt == "sinif"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=margin_x,
        leftMargin=margin_x,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f"OdevRaporu_{odev.get('id', '')}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="OdevTtl",
        parent=styles["Heading1"],
        fontName=fn,
        fontSize=14,
        spaceAfter=6,
    )
    h2 = ParagraphStyle(
        name="OdevH2",
        parent=styles["Heading2"],
        fontName=fn,
        fontSize=10.5,
        spaceBefore=8,
        spaceAfter=5,
        textColor=colors.HexColor("#0f172a"),
    )
    body = ParagraphStyle(name="OdevBd", parent=styles["Normal"], fontName=fn, fontSize=9)
    small = ParagraphStyle(name="OdevSm", parent=styles["Normal"], fontName=fn, fontSize=7.5)

    td8 = ParagraphStyle(
        "odev_td8",
        parent=styles["Normal"],
        fontName=fn,
        fontSize=8,
        leading=10,
        spaceBefore=0,
        spaceAfter=0,
    )
    td8b = ParagraphStyle(
        "odev_td8b",
        parent=td8,
        fontName=fn,
        fontSize=8,
    )
    th_st = ParagraphStyle(
        "odev_th",
        parent=td8,
        textColor=colors.whitesmoke,
        fontName=fn,
    )
    th_st_acc = ParagraphStyle(
        "odev_th_acc",
        parent=td8,
        textColor=colors.white,
        fontName=fn,
    )

    def tbl_base():
        return [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]

    story: list = []
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
    h_okul = colors.HexColor("#0f172a")
    story.append(Paragraph("Erenler Cumhuriyet Ortaokulu", title_style))
    story.append(
        Paragraph(
            "<b>Ödev ve tema takibi — Rapor</b>",
            ParagraphStyle(
                "subttl",
                parent=title_style,
                fontSize=11,
                textColor=h_okul,
                spaceAfter=10,
            ),
        )
    )

    # — Bölüm numarası: koşullu tablolar arasında sıralı ilerler
    bolum = 1

    # — Tablo 1: Rapor üst bilgileri
    story.append(Paragraph(f"{bolum}. Rapor üst bilgileri", h2))
    bolum += 1
    t1_data = [
        [
            _pdf_paragraph("Öğretmen", th_st),
            _pdf_paragraph(str(ogretmen_adi or "—"), td8),
        ],
        [
            _pdf_paragraph("Rapor tarihi / saati", th_st),
            _pdf_paragraph(now_s, td8),
        ],
        [
            _pdf_paragraph("Ödev kayıt numarası", th_st),
            _pdf_paragraph(str(odev.get("id", "—")), td8),
        ],
    ]
    w_kv = [usable_w * 0.32, usable_w * 0.68]
    tt1 = Table(t1_data, colWidths=w_kv)
    tt1.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#334155")),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, -1), fn),
            ]
            + tbl_base()
        )
    )
    story.append(tt1)
    story.append(Spacer(1, 0.35 * cm))

    # — Tablo 2: Ödev tanımı
    story.append(
        Paragraph(f"{bolum}. Ödev tanımı ve müfredat bağlantısı", h2)
    )
    bolum += 1
    konu = (odev.get("konu_adi") or "").strip()
    t2_data = [
        [
            _pdf_paragraph("Alan", th_st_acc),
            _pdf_paragraph("İçerik", th_st_acc),
        ],
        [
            _pdf_paragraph("Sınıf", td8b),
            _pdf_paragraph(str(odev.get("sinif_adi", "—")), td8),
        ],
        [
            _pdf_paragraph("Ders (branş)", td8b),
            _pdf_paragraph(str(odev.get("ders_adi", "—")), td8),
        ],
        [
            _pdf_paragraph("Tema / ünite / öğrenme alanı", td8b),
            _pdf_paragraph(str(odev.get("tema_adi", "—")), td8),
        ],
    ]
    if konu:
        t2_data.append(
            [
                _pdf_paragraph("Öğrenme kanıtları", td8b),
                _pdf_paragraph(konu, td8),
            ]
        )
    if 5 <= sev <= 8:
        t2_data.append(
            [
                _pdf_paragraph("TYMM sınıf düzeyi", td8b),
                _pdf_paragraph(str(sev), td8),
            ]
        )
    t2_data.append(
        [
            _pdf_paragraph("Kayıt tarihi", td8b),
            _pdf_paragraph(str(odev.get("tarih", "—"))[:19], td8),
        ]
    )
    w_def = [usable_w * 0.30, usable_w * 0.70]
    tt2 = Table(t2_data, colWidths=w_def, repeatRows=1)
    tt2.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), fn),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
            + tbl_base()
        )
    )
    story.append(tt2)
    story.append(Spacer(1, 0.35 * cm))

    # — Tablo 3: Tamamlanma özeti
    story.append(Paragraph(f"{bolum}. Tamamlanma özeti", h2))
    bolum += 1
    t3_data = [
        [
            _pdf_paragraph("Gösterge", th_st_acc),
            _pdf_paragraph("Değer", th_st_acc),
            _pdf_paragraph("Açıklama", th_st_acc),
        ],
        [
            _pdf_paragraph("Toplam öğrenci", td8b),
            _pdf_paragraph(str(top), td8),
            _pdf_paragraph("Sınıfa kayıtlı öğrenci sayısı", td8),
        ],
        [
            _pdf_paragraph("Ödevi yapan", td8b),
            _pdf_paragraph(str(tam_s), td8),
            _pdf_paragraph("“Yaptı” işaretli öğrenciler (rapor anı)", td8),
        ],
        [
            _pdf_paragraph("Ödevi yapmayan", td8b),
            _pdf_paragraph(str(yap_mad), td8),
            _pdf_paragraph("“Yapmadı” işaretli öğrenciler (rapor anı)", td8),
        ],
        [
            _pdf_paragraph("Tamamlanma oranı", td8b),
            _pdf_paragraph(f"%{pct}", td8),
            _pdf_paragraph(f"Yapanların sınıf içindeki payı ({tam_s}/{top})", td8),
        ],
    ]
    w3 = [usable_w * 0.28, usable_w * 0.14, usable_w * 0.58]
    tt3 = Table(t3_data, colWidths=w3, repeatRows=1)
    tt3.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), fn),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eff6ff")]),
            ]
            + tbl_base()
        )
    )
    story.append(tt3)
    story.append(Spacer(1, 0.35 * cm))

    # — Tablo 4: Durum dağılımı (yüzde)
    if top > 0:
        story.append(
            Paragraph(f"{bolum}. Durum dağılımı (grafik ve tablo)", h2)
        )
        bolum += 1
        story.append(_odev_durum_grafik_tablosu(tam_s, yap_mad, fn, usable_w, small))
        story.append(Spacer(1, 0.3 * cm))
        t4_data = [
            [
                _pdf_paragraph("Durum", th_st_acc),
                _pdf_paragraph("Öğrenci", th_st_acc),
                _pdf_paragraph("Oran (%)", th_st_acc),
            ],
            [
                _pdf_paragraph("Yaptı", td8),
                _pdf_paragraph(str(tam_s), td8),
                _pdf_paragraph(str(round(tam_s / top * 100)) if top else "0", td8),
            ],
            [
                _pdf_paragraph("Yapmadı", td8),
                _pdf_paragraph(str(yap_mad), td8),
                _pdf_paragraph(str(pct_y), td8),
            ],
        ]
        w4 = [usable_w * 0.34, usable_w * 0.18, usable_w * 0.48]
        tt4 = Table(t4_data, colWidths=w4, repeatRows=1)
        tt4.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c3aed")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf5ff")]),
                ]
                + tbl_base()
            )
        )
        story.append(tt4)
        story.append(Spacer(1, 0.35 * cm))

    # — Tablo 5: Öğrenme çıktısı kodları
    if kodlar:
        story.append(Paragraph(f"{bolum}. Öğrenme çıktısı kodları", h2))
        bolum += 1
        t5 = [[_pdf_paragraph("#", th_st_acc), _pdf_paragraph("Kod", th_st_acc)]]
        for i, k in enumerate(kodlar, 1):
            t5.append(
                [
                    _pdf_paragraph(str(i), td8),
                    _pdf_paragraph(str(k), td8),
                ]
            )
        w5 = [usable_w * 0.12, usable_w * 0.88]
        tt5 = Table(t5, colWidths=w5, repeatRows=1)
        tt5.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b45309")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fffbeb")]),
                ]
                + tbl_base()
            )
        )
        story.append(tt5)
        story.append(Spacer(1, 0.35 * cm))

    # — Tablo 6: Seçilen öğrenme çıktıları / maddeler
    if ciktilar:
        story.append(
            Paragraph(
                f"{bolum}. Seçilen öğrenme çıktıları ve ölçme-değerlendirme maddeleri",
                h2,
            )
        )
        bolum += 1
        t6 = [
            [
                _pdf_paragraph("Sıra", th_st_acc),
                _pdf_paragraph("Madde", th_st_acc),
            ]
        ]
        for i, sat in enumerate(ciktilar, 1):
            t6.append(
                [
                    _pdf_paragraph(str(i), td8),
                    _pdf_paragraph(str(sat).strip() or "—", td8),
                ]
            )
        w6 = [usable_w * 0.10, usable_w * 0.90]
        tt6 = Table(t6, colWidths=w6, repeatRows=1)
        tt6.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#047857")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecfdf5")]),
                ]
                + tbl_base()
            )
        )
        story.append(tt6)
        story.append(Spacer(1, 0.35 * cm))
    else:
        story.append(
            Paragraph(
                f"{bolum}. Seçilen öğrenme çıktıları",
                h2,
            )
        )
        bolum += 1
        t_bos = Table(
            [
                [
                    _pdf_paragraph("Not", th_st_acc),
                    _pdf_paragraph("Kayıtta işaretlenen madde yok.", td8),
                ],
            ],
            colWidths=[usable_w * 0.22, usable_w * 0.78],
        )
        t_bos.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#64748b")),
                    ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                    ("BACKGROUND", (1, 0), (1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (-1, -1), fn),
                ]
                + tbl_base()
            )
        )
        story.append(t_bos)
        story.append(Spacer(1, 0.3 * cm))

    # — Tablo 7: Öğrenci listesi (yalnızca sınıf raporu)
    if sinif_ogrenci_tablosu:
        story.append(Paragraph(f"{bolum}. Öğrenci listesi — bireysel durum", h2))

        rows_tbl = [
            [
                _pdf_paragraph("Sıra", th_st_acc),
                _pdf_paragraph("Öğr. no", th_st_acc),
                _pdf_paragraph("Ad Soyad", th_st_acc),
                _pdf_paragraph("Ödev durumu", th_st_acc),
            ]
        ]
        for i, ogr in enumerate(ogrenciler, 1):
            d = (ogr.get("durum") or "tamamlamadi") == "tamamladi"
            durum_etik = "Yaptı" if d else "Yapmadı"
            rows_tbl.append(
                [
                    _pdf_paragraph(str(i), td8),
                    _pdf_paragraph(str(ogr.get("ogr_no", "")), td8),
                    _pdf_paragraph(str(ogr.get("ad_soyad", "")), td8),
                    _pdf_paragraph(durum_etik, td8),
                ]
            )
        foot_i: int | None = None
        if len(rows_tbl) == 1:
            rows_tbl.append(
                [
                    _pdf_paragraph("—", td8),
                    _pdf_paragraph("—", td8),
                    _pdf_paragraph("Öğrenci kaydı bulunamadı", td8),
                    _pdf_paragraph("—", td8),
                ]
            )
        else:
            rows_tbl.append(
                [
                    _pdf_paragraph("TOPLAM", td8b),
                    Paragraph("", td8),
                    _pdf_paragraph(
                        f"{tam_s} yaptı · {yap_mad} yapmadı ({top} öğr.)",
                        td8,
                    ),
                    _pdf_paragraph(f"%{pct}", td8),
                ]
            )
            foot_i = len(rows_tbl) - 1

        wn = usable_w * 0.09
        wo = usable_w * 0.11
        wa = usable_w * 0.50
        wd = usable_w * 0.30
        t_ogr = Table(rows_tbl, colWidths=[wn, wo, wa, wd], repeatRows=1)
        last_zebra = (foot_i - 1) if foot_i is not None else len(rows_tbl) - 1
        st_ogr = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), fn),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94a3b8")),
        ]
        if last_zebra >= 1:
            st_ogr.append(
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, last_zebra),
                    [colors.white, colors.HexColor("#f8fafc")],
                )
            )
        if foot_i is not None:
            st_ogr.append(
                ("BACKGROUND", (0, foot_i), (-1, foot_i), colors.HexColor("#cbd5e1"))
            )
            st_ogr.append(("SPAN", (0, foot_i), (1, foot_i)))
            st_ogr.append(("ALIGN", (0, foot_i), (0, foot_i), "LEFT"))
            st_ogr.append(("FONTNAME", (0, foot_i), (-1, foot_i), fn))
        st_ogr.extend(tbl_base())
        t_ogr.setStyle(TableStyle(st_ogr))
        story.append(t_ogr)
    else:
        story.append(Paragraph(f"{bolum}. Bireysel rapor sayfaları", h2))
        story.append(
            Paragraph(
                "Bu PDF’nin devamında her öğrenci için bu ödev özelinde ayrı bir sayfa oluşturulmuştur. "
                "Özet sınıf tablosu yalnızca “PDF raporu (sınıf)” indirmesinde yer alır.",
                small,
            )
        )
        if rt == "tum_ogrenciler" and ogrenciler:
            for ogr in ogrenciler:
                story.append(PageBreak())
                story.extend(
                    _odev_ogrenci_sayfasi_flowables(
                        detay,
                        ogr,
                        ogretmen_adi,
                        fn,
                        usable_w,
                        tam_s=tam_s,
                        yap_mad=yap_mad,
                        top=top,
                        pct=pct,
                    )
                )

    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "Bu belge, sistemdeki ödev kaydının rapor anındaki görünümünü tablolar halinde özetler. "
            + (
                "Öğrenci işaretlemelerini güncelledikten sonra PDF’yi yeniden oluşturduğunuzda sayılar güncellenir."
                if sinif_ogrenci_tablosu
                else "Öğrenci işaretlemelerini güncelledikten sonra PDF’yi yeniden oluşturduğunuzda tüm sayfalar güncellenir."
            ),
            small,
        )
    )

    doc.build(story)
    return buf.getvalue()


PDF_OK = REPORTLAB_OK
