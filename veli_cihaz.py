"""Active parent-phone tokens used by the Android notification listener."""

import hashlib
from datetime import datetime

from database import _conn


def _hazirla(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS veli_cihaz (
            token_hash TEXT PRIMARY KEY,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            zaman TEXT NOT NULL
        )
    """)


def veli_cihaz_kaydet(ogrenci_id: int, token: str) -> None:
    con = _conn()
    _hazirla(con)
    con.execute(
        "INSERT OR REPLACE INTO veli_cihaz (token_hash, ogrenci_id, zaman) VALUES (?, ?, ?)",
        (hashlib.sha256(token.encode("utf-8")).hexdigest(), int(ogrenci_id),
         datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    con.commit()
    con.close()


def veli_cihaz_ogrenci(token: str) -> int | None:
    if not token or len(token) > 256:
        return None
    con = _conn()
    _hazirla(con)
    row = con.execute(
        "SELECT ogrenci_id FROM veli_cihaz WHERE token_hash = ?",
        (hashlib.sha256(token.encode("utf-8")).hexdigest(),),
    ).fetchone()
    con.close()
    return int(row["ogrenci_id"]) if row else None


def veli_cihaz_sil(token: str) -> None:
    if not token:
        return
    con = _conn()
    _hazirla(con)
    con.execute(
        "DELETE FROM veli_cihaz WHERE token_hash = ?",
        (hashlib.sha256(token.encode("utf-8")).hexdigest(),),
    )
    con.commit()
    con.close()
