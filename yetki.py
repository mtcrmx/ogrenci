"""Tek rol ve yetki modeli (Aşama 2).

Tüm yetki kontrolleri `ogretmen_yetki(ogretmen_id, yetki)` tablosu üzerinden yapılır.
"""
from __future__ import annotations

from functools import wraps
from flask import abort, has_request_context, redirect, session, url_for
import database as db

TUM_YETKILER = (
    "yonetici",
    "mudur",
    "mudur_yrd",
    "lgs_yonet",
    "toplu_sifirlama",
    "sayfa_sifirlama",
    "evrak_takip",
    "rehber",
    "rapor",
)


def _tablo_var_mi(con) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ogretmen_yetki'"
    ).fetchone()
    return row is not None


def yetkili(*args) -> bool:
    """Öğretmenin belirtilen yetkiye sahip olup olmadığını döndürür.

    Kullanım:
      - `yetkili(oid, 'yonetici')`
      - `yetkili('yonetici')` (aktif oturumdaki `session['ogretmen_id']` için)
    """
    if len(args) == 1:
        oid = session.get("ogretmen_id") if has_request_context() else None
        yetki_adi = args[0]
    elif len(args) >= 2:
        oid, yetki_adi = args[0], args[1]
    else:
        return False

    if not oid or not yetki_adi:
        return False
    try:
        oid_int = int(oid)
    except (TypeError, ValueError):
        return False

    yetki_str = str(yetki_adi).strip()
    if not yetki_str:
        return False

    # Rapor/rehber oturum modundayken yönetim/sıfırlama yetkileri kapalıdır
    if has_request_context() and session.get("ogretmen_id") == oid_int:
        oturum_yetki = session.get("ogretmen_yetki")
        if oturum_yetki in ("rapor", "rehber") and yetki_str in (
            "yonetici",
            "mudur",
            "mudur_yrd",
            "toplu_sifirlama",
            "sayfa_sifirlama",
            "evrak_takip",
        ):
            return False

    con = db._conn()
    try:
        if _tablo_var_mi(con):
            row = con.execute(
                "SELECT 1 FROM ogretmen_yetki WHERE ogretmen_id = ? AND yetki = ?",
                (oid_int, yetki_str),
            ).fetchone()
            if row:
                if yetki_str in ("yonetici", "toplu_sifirlama", "sayfa_sifirlama", "evrak_takip"):
                    ogr = con.execute(
                        "SELECT COALESCE(yetki, 'tam') AS yetki FROM ogretmenler WHERE id = ?",
                        (oid_int,),
                    ).fetchone()
                    if ogr and ogr["yetki"] in ("rapor", "rehber"):
                        return False
                return True
        if yetki_str in ("rehber", "rapor"):
            ogr = con.execute(
                "SELECT 1 FROM ogretmenler WHERE id = ? AND yetki = ?",
                (oid_int, yetki_str),
            ).fetchone()
            return bool(ogr)
        return False
    finally:
        con.close()


def yetkili_idleri(yetki_adi: str) -> list[int]:
    """Belirtilen yetkiye sahip öğretmen ID listesini döndürür."""
    con = db._conn()
    try:
        if not _tablo_var_mi(con):
            return []
        rows = con.execute(
            "SELECT ogretmen_id FROM ogretmen_yetki WHERE yetki = ? ORDER BY ogretmen_id",
            (str(yetki_adi).strip(),),
        ).fetchall()
        return [int(r["ogretmen_id"]) for r in rows]
    finally:
        con.close()


def yetkili_ogretmenler(yetki_adi: str) -> list[dict]:
    """Belirtilen yetkiye sahip öğretmenlerin `{id, ad_soyad}` kayıtlarını döndürür."""
    con = db._conn()
    try:
        if not _tablo_var_mi(con):
            return []
        rows = con.execute(
            """
            SELECT o.id, o.ad_soyad
            FROM ogretmen_yetki y
            JOIN ogretmenler o ON o.id = y.ogretmen_id
            WHERE y.yetki = ?
            ORDER BY o.id
            """,
            (str(yetki_adi).strip(),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def ogretmen_unvani(oid_veya_ad, kisa: bool = False) -> str:
    """Öğretmenin DB'deki rolüne göre unvanını ('Müdür', 'Müdür Yardımcısı' vb.) döndürür."""
    if not oid_veya_ad:
        return ""
    con = db._conn()
    try:
        if not _tablo_var_mi(con):
            return ""
        if isinstance(oid_veya_ad, int) or str(oid_veya_ad).isdigit():
            oid = int(oid_veya_ad)
        else:
            row = con.execute(
                "SELECT id FROM ogretmenler WHERE ad_soyad = ?",
                (str(oid_veya_ad).strip(),),
            ).fetchone()
            if not row:
                return ""
            oid = int(row["id"])
        roller = {
            r["yetki"]
            for r in con.execute(
                "SELECT yetki FROM ogretmen_yetki WHERE ogretmen_id = ?",
                (oid,),
            ).fetchall()
        }
        if "mudur" in roller:
            return "Müdür"
        if "mudur_yrd" in roller:
            return "Müdür Yrd." if kisa else "Müdür Yardımcısı"
        if "rehber" in roller:
            return "Rehber" if kisa else "Rehber Öğretmen"
        return ""
    finally:
        con.close()


def mudur_adi() -> str:
    """Okul müdürünün adını DB'den döndürür."""
    liste = yetkili_ogretmenler("mudur")
    return liste[0]["ad_soyad"] if liste else ""


def _tr_title(ad: str) -> str:
    parcalar = []
    for k in str(ad or "").strip().split():
        if not k:
            continue
        ilk = k[0]
        kalan = k[1:].replace("İ", "i").replace("I", "ı").lower()
        parcalar.append(ilk + kalan)
    return " ".join(parcalar)


def rehber_adi() -> str:
    """Aktif rehber öğretmenin adını DB'den (veya oturumdan) döndürür."""
    if has_request_context() and session.get("ogretmen_yetki") == "rehber" and session.get("ogretmen_adi"):
        return _tr_title(session.get("ogretmen_adi"))
    liste = yetkili_ogretmenler("rehber")
    return _tr_title(liste[0]["ad_soyad"]) if liste else ""


def yetki_gerekli(yetki_adi: str):
    """Belirtilen yetkiye sahip olmayan öğretmenlere 403 döndüren dekoratör."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "ogretmen_id" not in session:
                return redirect(url_for("login"))
            if not yetkili(session.get("ogretmen_id"), yetki_adi):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def register_yetki(app) -> None:
    """Jinja global fonksiyonlarını uygulamaya kaydeder."""
    app.jinja_env.globals.update(
        yetkili=yetkili,
        ogretmen_unvani=ogretmen_unvani,
        mudur_adi=mudur_adi,
        rehber_adi=rehber_adi,
    )
