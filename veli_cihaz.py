"""Active parent-phone tokens used by the Android notification listener."""

import hashlib
from datetime import datetime, timedelta

from database import _conn


def _hazirla(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS veli_cihaz (
            token_hash TEXT PRIMARY KEY,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            zaman TEXT NOT NULL
        )
    """)
    columns = {r[1] for r in con.execute('PRAGMA table_info(veli_cihaz)')}
    if 'auth_version' not in columns:
        con.execute("ALTER TABLE veli_cihaz ADD COLUMN auth_version TEXT NOT NULL DEFAULT ''")
        con.commit()


def veli_cihaz_kaydet(ogrenci_id: int, token: str) -> None:
    from account_security import parent_credential
    credential = parent_credential(ogrenci_id)
    if not credential:
        return
    con = _conn()
    _hazirla(con)
    con.execute(
        "INSERT OR REPLACE INTO veli_cihaz (token_hash, ogrenci_id, zaman, auth_version) VALUES (?, ?, ?, ?)",
        (hashlib.sha256(token.encode("utf-8")).hexdigest(), int(ogrenci_id),
         datetime.now().strftime("%Y-%m-%d %H:%M"), credential['version']),
    )
    con.commit()
    con.close()


def veli_cihaz_ogrenci(token: str) -> int | None:
    if not token or len(token) > 256:
        return None
    con = _conn()
    _hazirla(con)
    aktif_sinir = (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M")
    row = con.execute(
        "SELECT v.ogrenci_id FROM veli_cihaz v JOIN parent_credentials p ON p.student_id=v.ogrenci_id AND p.version=v.auth_version WHERE token_hash = ? AND zaman >= ?",
        (hashlib.sha256(token.encode("utf-8")).hexdigest(), aktif_sinir),
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
