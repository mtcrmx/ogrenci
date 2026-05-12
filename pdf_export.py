"""
pdf_export.py
-------------
Disiplin analiz PDF üretimi + rapor anlık görüntüsü (snapshot).
Gerekli: pip install reportlab
"""

from __future__ import annotations

import io
import os
import platform
from datetime import datetime
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

_FONT_NAME = "RaporFont"
_FONT_READY = False


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
    return {
        "meta": meta,
        "ozet": ozet,
        "sinif_ozet": sorted(sinif_ozet_map.values(), key=lambda x: x["sinif_adi"]),
        "ogrenciler": ogrenci_satirlari,
        "kriter_dagilim": dict(sorted(kriter_cnt.items(), key=lambda x: (-x[1], x[0]))),
        "tik_satirlari": tik_archive,
    }


def pdf_analiz_uret_bytes(snapshot: dict[str, Any], ogretmen_adi: str) -> bytes:
    if not REPORTLAB_OK:
        raise ImportError("reportlab kurulu degil (pip install reportlab)")
    fn = _register_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
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

    story: list = []
    meta = snapshot.get("meta") or {}
    ozet = snapshot.get("ozet") or {}

    story.append(Paragraph("Erenler Cumhuriyet Ortaokulu", title_style))
    story.append(Paragraph("Disiplin — Detaylı Analiz Raporu", title_style))
    story.append(
        Paragraph(
            f"Öğretmen: {ogretmen_adi}<br/>"
            f"Tarih: {meta.get('olusturma', '-')}"
            f"<br/>Kapsam: {meta.get('kapsam_metin', '-')}",
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
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Sınıf özeti", h2))
    so = [["Sınıf", "Öğr.", "Σ Tik", "Temiz", "Uyarı", "İdari"]]
    for s in snapshot.get("sinif_ozet") or []:
        so.append(
            [
                str(s.get("sinif_adi", "")),
                str(s.get("ogrenci", 0)),
                str(s.get("toplam_tik", 0)),
                str(s.get("temiz", 0)),
                str(s.get("uyari", 0)),
                str(s.get("idari", 0)),
            ]
        )
    t1 = Table(so, colWidths=[4 * cm, 1.3 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm])
    t1.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, -1), fn),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ]
        )
    )
    story.append(t1)
    story.append(PageBreak())

    story.append(Paragraph("Öğrenci bazlı özet", h2))
    og_t = [["No", "Ad Soyad", "Sınıf", "Tik", "Durum", "Özet ihlaller", "Ödev%", "XP"]]
    for r in snapshot.get("ogrenciler") or []:
        oz = (r.get("ihlal_ozet") or "")[:55]
        if len((r.get("ihlal_ozet") or "")) > 55:
            oz += "…"
        og_t.append(
            [
                str(r.get("ogr_no", "")),
                str(r.get("ad_soyad", ""))[:28],
                str(r.get("sinif_adi", ""))[:10],
                str(r.get("tik_sayisi", 0)),
                str(r.get("durum", ""))[:14],
                oz,
                str(r.get("odev_oran", 0)),
                str(r.get("gelisim_xp", 0)),
            ]
        )
    ot = Table(
        og_t,
        colWidths=[1 * cm, 3.6 * cm, 1.8 * cm, 1 * cm, 2 * cm, 4.2 * cm, 1 * cm, 1 * cm],
        repeatRows=1,
    )
    ot.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, -1), fn),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(ot)
    story.append(PageBreak())

    story.append(Paragraph("İhlal türü dağılımı (temiz metin)", h2))
    kd = [["İhlal türü", "Adet"]]
    for k, v in (snapshot.get("kriter_dagilim") or {}).items():
        kd.append([str(k)[:70], str(v)])
    if len(kd) == 1:
        kd.append(["Kayıt yok", "0"])
    tk = Table(kd, colWidths=[12 * cm, 3 * cm])
    tk.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, -1), fn),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
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

    det = [["Tarih", "Sınıf", "No", "Öğrenci", "İhlal", "Öğretmen"]]
    rows = snapshot.get("tik_satirlari") or []
    for r in rows:
        det.append(
            [
                str(r.get("tarih", ""))[:16],
                str(r.get("sinif_adi", ""))[:10],
                str(r.get("ogr_no", "")),
                str(r.get("ad_soyad", ""))[:22],
                str(r.get("kriter_temiz", ""))[:35],
                str(r.get("ogretmen", ""))[:18],
            ]
        )
    if len(det) == 1:
        det.append(["-", "-", "-", "-", "Kayıt yok", "-"])

    dt = Table(
        det,
        colWidths=[3 * cm, 2 * cm, 1 * cm, 3 * cm, 4.5 * cm, 2.8 * cm],
        repeatRows=1,
    )
    dt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, -1), fn),
                ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                ("GRID", (0, 0), (-1, -1), 0.15, colors.lightgrey),
            ]
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


PDF_OK = REPORTLAB_OK
