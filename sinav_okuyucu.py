"""Ortak sınav okuyucu adaptörü (Aşama 5).

Analiz ekranları (`yaprak_analiz.py`, `birlesik_analiz`, yeni sınıf/öğrenci analizleri)
sonuçları doğrudan tablo birleştirmek yerine bu adaptörden okur.
"""
from __future__ import annotations

from flask import url_for
import database as db
import lgs_optik as optik
from metrik import VARSAYILAN_GOTURME


def _silinmemis_kosul(con, tablo: str, alias: str) -> str:
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({tablo})").fetchall()}
    if "silindi_at" in cols:
        return f" AND ({alias}.silindi_at IS NULL OR {alias}.silindi_at = '')"
    return ""


def okul_yaprak_satirlari(allowed_ids: set[int]) -> list[dict]:
    """Okulda yaprak test (`lgs_deneme(tur='ders')` + `lgs_optik_sinav(kaynak='kamera')`) satırlarını döner."""
    if not allowed_ids:
        return []
    con = db._conn()
    try:
        db._lgs_init(con)
        optik._init(con)
        d_ko = _silinmemis_kosul(con, "lgs_deneme", "d")
        e_ko = _silinmemis_kosul(con, "lgs_optik_sinav", "e")
        optik_cols = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
        goturme_ifade = (
            f"COALESCE(e.yanlis_goturme, {VARSAYILAN_GOTURME})"
            if "yanlis_goturme" in optik_cols
            else str(VARSAYILAN_GOTURME)
        )
        rows = [
            dict(r)
            for r in con.execute(
                f"""SELECT d.ad, d.tarih, d.ogrenci_id, dd.*, o.ad_soyad, o.ogr_no, o.sinif_id, s.sinif_adi
                    FROM lgs_deneme d
                    JOIN lgs_deneme_ders dd ON dd.deneme_id = d.id
                    JOIN ogrenciler o ON o.id = d.ogrenci_id
                    JOIN siniflar s ON s.id = o.sinif_id
                    WHERE d.tur = 'ders'{d_ko}
                    ORDER BY dd.id"""
            )
            if r["ogrenci_id"] in allowed_ids
        ]
        rows += [
            dict(r)
            for r in con.execute(
                f"""SELECT e.id AS camera_exam, e.ad, e.tarih, e.ders, e.soru_sayisi,
                           r.ogrenci_id, r.dogru, r.yanlis, r.bos, r.net,
                           {goturme_ifade} AS yanlis_goturme,
                           o.ad_soyad, o.ogr_no, o.sinif_id, s.sinif_adi
                    FROM lgs_optik_sinav e
                    JOIN lgs_optik_sonuc r ON r.sinav_id = e.id
                    JOIN ogrenciler o ON o.id = r.ogrenci_id
                    JOIN siniflar s ON s.id = o.sinif_id
                    WHERE e.kaynak = 'kamera'{e_ko}
                    ORDER BY r.id"""
            )
            if r["ogrenci_id"] in allowed_ids
        ]
        return rows
    finally:
        con.close()


def birlesik_sonuclar(allowed_ids: set[int], teacher: int | None = None) -> list[dict]:
    """Hem `lgs_deneme` hem `lgs_optik_sinav` kayıtlarını birleşik analiz formatında döner."""
    if not allowed_ids:
        return []
    con = db._conn()
    try:
        db._lgs_init(con)
        optik._init(con)
        d_ko = _silinmemis_kosul(con, "lgs_deneme", "d")
        e_ko = _silinmemis_kosul(con, "lgs_optik_sinav", "e")
        rows: list[dict] = []
        for row in con.execute(
            f"""SELECT d.ad, d.tarih, d.tur, d.ogretmen_id, d.ogrenci_id, dd.*
                FROM lgs_deneme d
                JOIN lgs_deneme_ders dd ON dd.deneme_id = d.id
                WHERE 1=1{d_ko}
                ORDER BY dd.id"""
        ):
            r = dict(row)
            if r["ogrenci_id"] not in allowed_ids:
                continue
            r["source"] = "okul" if r["tur"] == "ders" else "deneme"
            r["exam_key"] = ("legacy", r["ogretmen_id"], r["ad"], r["tarih"], r["tur"])
            r["detail"] = (
                url_for("yaprak_analiz.index", ders=r["ders"])
                if r["source"] == "okul"
                else (url_for("deneme_analiz") if teacher else url_for("veli_lgs", bolum="deneme"))
            )
            rows.append(r)

        for row in con.execute(
            f"""SELECT e.id AS exam_id, e.ogretmen_id, e.ad, e.tarih, e.tur, e.kaynak,
                       e.ders, e.soru_sayisi, e.cevaplar, r.isaretler, r.ogrenci_id,
                       r.dogru, r.yanlis, r.bos, r.net
                FROM lgs_optik_sinav e
                JOIN lgs_optik_sonuc r ON r.sinav_id = e.id
                WHERE 1=1{e_ko}
                ORDER BY r.id"""
        ):
            r = dict(row)
            if not optik.teacher_can_view(r):
                continue
            if r["ogrenci_id"] not in allowed_ids:
                continue
            if r.get("kaynak") == "kamera":
                r["source"] = "okul"
            elif r.get("tur") == "deneme":
                r["source"] = "deneme"
            else:
                r["source"] = "ev"
            r["exam_key"] = ("optik", r["exam_id"])
            r["detail"] = url_for("ev_analiz.index", test=r["exam_id"])
            r["ders"] = r["ders"] or "Genel deneme"
            rows.append(r)
        return rows
    finally:
        con.close()
