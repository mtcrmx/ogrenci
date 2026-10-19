"""Migration 004: siniflar.seviye INTEGER sütunu ekler ve sinif_adi'ndan doldurur."""
from __future__ import annotations

import re
import sqlite3

VERSION = 4
NAME = "004_sinif_seviye"


def sinif_seviyesi_coz(sinif_adi: str | None) -> int | None:
    if not sinif_adi:
        return None
    m = re.match(r"^\s*(\d+)", str(sinif_adi))
    return int(m.group(1)) if m else None


def up(con: sqlite3.Connection) -> None:
    cols = {r[1] for r in con.execute("PRAGMA table_info(siniflar)").fetchall()}
    if "seviye" not in cols:
        con.execute("ALTER TABLE siniflar ADD COLUMN seviye INTEGER")
    rows = con.execute("SELECT id, sinif_adi FROM siniflar").fetchall()
    for r in rows:
        sev = sinif_seviyesi_coz(r["sinif_adi"] if isinstance(r, sqlite3.Row) else r[1])
        rid = r["id"] if isinstance(r, sqlite3.Row) else r[0]
        con.execute("UPDATE siniflar SET seviye = ? WHERE id = ?", (sev, rid))


def down(con: sqlite3.Connection) -> None:
    cols = {r[1] for r in con.execute("PRAGMA table_info(siniflar)").fetchall()}
    if "seviye" in cols:
        con.execute("UPDATE siniflar SET seviye = NULL")
