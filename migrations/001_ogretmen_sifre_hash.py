"""
Migration 001: ogretmenler.sifre_hash
-------------------------------------
`ogretmenler.sifre_hash TEXT` sütununu ekler ve mevcut `sifre` değerlerini
`werkzeug.security.generate_password_hash` ile doldurur.
`sifre` sütununa bu aşamada dokunulmaz; `down()` yalnız `sifre_hash` değerlerini boşaltır.
"""

import sqlite3
from werkzeug.security import generate_password_hash


def _sutun_var_mi(con: sqlite3.Connection, tablo: str, sutun: str) -> bool:
    return sutun in {
        r[1] for r in con.execute(f"PRAGMA table_info({tablo})").fetchall()
    }


def up(con: sqlite3.Connection) -> None:
    if not _sutun_var_mi(con, "ogretmenler", "sifre_hash"):
        con.execute("ALTER TABLE ogretmenler ADD COLUMN sifre_hash TEXT")
        con.commit()

    rows = con.execute(
        "SELECT id, sifre, sifre_hash FROM ogretmenler"
    ).fetchall()
    for row in rows:
        oid = row[0]
        sifre = (row[1] or "").strip()
        mevcut_hash = (row[2] or "").strip()
        if sifre and not mevcut_hash:
            con.execute(
                "UPDATE ogretmenler SET sifre_hash = ? WHERE id = ?",
                (generate_password_hash(sifre), oid),
            )
    con.commit()


def down(con: sqlite3.Connection) -> None:
    if _sutun_var_mi(con, "ogretmenler", "sifre_hash"):
        con.execute("UPDATE ogretmenler SET sifre_hash = NULL")
        con.commit()
