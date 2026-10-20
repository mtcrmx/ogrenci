"""Sınıf seviyesine göre aktif modüller ve yönlendirme yardımcıları (Aşama 4)."""
from __future__ import annotations

from functools import wraps
import re
from flask import redirect, request, session, url_for

import database as db

MODULLER: dict[int | str, set[str]] = {
    8: {
        "lgs",
        "deneme",
        "optik",
        "evde_test",
        "lgs_analiz",
    },
    "diger": {
        "haftalik_takip",
        "kitap",
        "odev",
        "onay",
        "kitap_odev_rapor",
        "yaprak_test",
        "rehberlik",
        "mesaj",
        "karne",
        "rozet",
        "deneme",
        "evde_test",
        "optik",
    },
}


def _seviye_metinden(ad: str | None) -> int | None:
    if not ad:
        return None
    m = re.match(r"^\s*(\d+)", str(ad))
    return int(m.group(1)) if m else None


def seviye(sinif) -> int | None:
    """Sınıf dict'i, sınıf adı ('8/A'), sınıf id'si veya öğrenci dict'inden seviye (5, 6, 7, 8) döner."""
    if sinif is None:
        return None
    if isinstance(sinif, dict):
        if sinif.get("seviye") is not None:
            try:
                return int(sinif["seviye"])
            except (TypeError, ValueError):
                pass
        if sinif.get("sinif_adi"):
            return _seviye_metinden(sinif.get("sinif_adi"))
        if sinif.get("sinif"):
            return _seviye_metinden(sinif.get("sinif"))
        sid = sinif.get("sinif_id") or sinif.get("id")
        if sid:
            return seviye(int(sid))
        return None
    if isinstance(sinif, int) or (isinstance(sinif, str) and sinif.strip().isdigit()):
        sid = int(sinif)
        con = db._conn()
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_info(siniflar)").fetchall()}
            if "seviye" in cols:
                row = con.execute("SELECT seviye, sinif_adi FROM siniflar WHERE id = ?", (sid,)).fetchone()
            else:
                row = con.execute("SELECT NULL AS seviye, sinif_adi FROM siniflar WHERE id = ?", (sid,)).fetchone()
            if not row:
                return None
            if row["seviye"] is not None:
                return int(row["seviye"])
            return _seviye_metinden(row["sinif_adi"])
        finally:
            con.close()
    if isinstance(sinif, str):
        s = _seviye_metinden(sinif)
        if s is not None:
            return s
        con = db._conn()
        try:
            row = con.execute("SELECT id, sinif_adi FROM siniflar WHERE sinif_adi = ?", (sinif.strip(),)).fetchone()
            return _seviye_metinden(row["sinif_adi"]) if row else None
        finally:
            con.close()
    return None


def ogrenci_seviyesi(ogrenci_id: int | None) -> int | None:
    if not ogrenci_id:
        return None
    con = db._conn()
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(siniflar)").fetchall()}
        sec = "s.seviye, s.sinif_adi" if "seviye" in cols else "NULL AS seviye, s.sinif_adi"
        row = con.execute(
            f"SELECT {sec} FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id WHERE o.id = ?",
            (int(ogrenci_id),),
        ).fetchone()
        if not row:
            return None
        return int(row["seviye"]) if row["seviye"] is not None else _seviye_metinden(row["sinif_adi"])
    finally:
        con.close()


def aktif_moduller(sinif) -> set[str]:
    if isinstance(sinif, int):
        con = db._conn()
        try:
            exists = con.execute("SELECT 1 FROM siniflar WHERE id = ?", (sinif,)).fetchone()
        finally:
            con.close()
        sev = seviye(sinif) if exists else sinif
    else:
        sev = seviye(sinif)
    if sev == 8:
        return set(MODULLER[8])
    return set(MODULLER["diger"])


def modul_var_mi(sinif, modul_adi: str) -> bool:
    return modul_adi in aktif_moduller(sinif)


def _istekten_seviye_bul() -> tuple[int | None, bool]:
    """İstekten veya oturumdan (seviye, veli_mi) döner."""
    if session.get("veli_ogrenci_id") and not session.get("ogretmen_id"):
        return ogrenci_seviyesi(session.get("veli_ogrenci_id")), True
    for param in ("sinif_id", "sinif"):
        val = request.values.get(param)
        if val:
            sev = seviye(val)
            if sev is not None:
                return sev, False
    oid = request.values.get("ogrenci_id") or request.values.get("ogrenci")
    if oid and str(oid).isdigit():
        return ogrenci_seviyesi(int(oid)), False
    return None, False


def modul_gerekli(modul_adi: str):
    """Belirtilen modül ilgili sınıf seviyesinde aktif değilse uygun sayfaya yönlendirir (404 vermez)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            sev, veli_mi = _istekten_seviye_bul()
            if sev is not None:
                aktif = MODULLER[8] if sev == 8 else MODULLER["diger"]
                if modul_adi not in aktif:
                    if veli_mi:
                        return redirect(url_for("veli_lgs") if sev == 8 else url_for("veli_panel"))
                    return redirect(url_for("lgs") if sev == 8 else url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def register_moduller(app) -> None:
    app.jinja_env.globals.update(
        MODULLER=MODULLER,
        sinif_seviyesi=seviye,
        aktif_moduller=aktif_moduller,
        modul_var_mi=modul_var_mi,
    )
