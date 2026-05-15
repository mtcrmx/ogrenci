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
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

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


def pdf_odev_raporu_bytes(detay: dict[str, Any], ogretmen_adi: str) -> bytes:
    """Yeni oluşturulan veya mevcut ödev için ayrıntılı PDF rapor (TYMM / öğrenci listesi)."""
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
    top = len(ogrenciler)
    pct = round((tam_s / top * 100) if top else 0)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=margin_x,
        leftMargin=margin_x,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"OdevRaporu_{odev.get('id', '')}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="OdevTtl",
        parent=styles["Heading1"],
        fontName=fn,
        fontSize=15,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        name="OdevH2",
        parent=styles["Heading2"],
        fontName=fn,
        fontSize=11,
        spaceAfter=5,
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
    th_w = ParagraphStyle("odev_th", parent=td8, textColor=colors.whitesmoke)

    def tbl_pad():
        return [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]

    story: list = []
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
    story.append(Paragraph("Erenler Cumhuriyet Ortaokulu", title_style))
    story.append(Paragraph("Ödev / tema takibi — Detaylı rapor", title_style))
    story.append(
        Paragraph(
            f"Öğretmen: {html_escape(str(ogretmen_adi or '—'))}<br/>"
            f"Rapor tarihi: {html_escape(now_s)}<br/>"
            f"Ödev kayıt no: {html_escape(str(odev.get('id', '—')))}",
            body,
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    meta_lines = [
        f"<b>Sınıf:</b> {html_escape(str(odev.get('sinif_adi', '—')))}",
        f"<b>Ders (branş):</b> {html_escape(str(odev.get('ders_adi', '—')))}",
        f"<b>Tema / ünite / öğrenme alanı:</b> {html_escape(str(odev.get('tema_adi', '—')))}",
    ]
    konu = (odev.get("konu_adi") or "").strip()
    if konu:
        meta_lines.append(f"<b>Öğrenme kanıtları:</b> {html_escape(konu)}")
    if 5 <= sev <= 8:
        meta_lines.append(f"<b>TYMM sınıf düzeyi:</b> {sev}")
    meta_lines.append(
        f"<b>Ödev oluşturma (kayıt tarihi):</b> {html_escape(str(odev.get('tarih', '—'))[:19])}"
    )
    story.append(Paragraph("<br/>".join(meta_lines), body))
    story.append(Spacer(1, 0.4 * cm))

    if kodlar:
        story.append(Paragraph("Öğrenme çıktısı kodları (varsa)", h2))
        story.append(
            Paragraph(
                html_escape(", ".join(str(k) for k in kodlar)),
                body,
            )
        )
        story.append(Spacer(1, 0.25 * cm))

    if ciktilar:
        story.append(Paragraph("Seçilen öğrenme çıktıları / ölçme-değerlendirme öğeleri", h2))
        for i, sat in enumerate(ciktilar, 1):
            t = html_escape(str(sat).strip()) or "—"
            story.append(Paragraph(f"{i}. {t}", body))
        story.append(Spacer(1, 0.35 * cm))
    else:
        story.append(
            Paragraph(
                "<i>Formda öğrenme çıktısı / kanıt seçilmediyse bu bölüm boştur.</i>",
                small,
            )
        )
        story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("Özet (anlık durum)", h2))
    oz_txt = (
        f"Toplam öğrenci: <b>{top}</b> · "
        f"Tamamlayan (Yaptı): <b>{tam_s}</b> · "
        f"Tamamlamayan (Yapmadı): <b>{top - tam_s}</b> · "
        f"Oran: <b>%{pct}</b>"
    )
    story.append(Paragraph(oz_txt, body))
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Sınıf listesi — öğrenci bazında durum", h2))
    rows_tbl = [
        [
            _pdf_paragraph("#", th_w),
            _pdf_paragraph("Öğr. no", th_w),
            _pdf_paragraph("Ad Soyad", th_w),
            _pdf_paragraph("Ödev durumu", th_w),
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
    if len(rows_tbl) == 1:
        rows_tbl.append(
            [
                _pdf_paragraph("—", td8),
                _pdf_paragraph("—", td8),
                _pdf_paragraph("Öğrenci kaydı yok", td8),
                _pdf_paragraph("—", td8),
            ]
        )
    wn = usable_w * 0.07
    wo = usable_w * 0.11
    wa = usable_w * 0.48
    wd = usable_w * 0.34
    t = Table(rows_tbl, colWidths=[wn, wo, wa, wd], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                ("GRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
            ]
            + tbl_pad()
        )
    )
    story.append(t)

    story.append(Spacer(1, 0.55 * cm))
    story.append(
        Paragraph(
            "Bu PDF, ödev kaydı için özet ve sınıf listesini içerir. Öğrenci işaretlemelerini "
            "güncelledikten sonra raporu tekrar indirerek güncel tabloyu alabilirsiniz.",
            small,
        )
    )

    doc.build(story)
    return buf.getvalue()


PDF_OK = REPORTLAB_OK
