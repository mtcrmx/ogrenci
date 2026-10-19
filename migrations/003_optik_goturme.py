"""Migration 003: lgs_optik_sinav tablosuna yanlis_goturme ve secenekler sütunları."""
from __future__ import annotations

import sqlite3

VERSION = 3
NAME = "003_optik_goturme"


def _ensure_optik_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lgs_optik_sinav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            tarih TEXT NOT NULL,
            pdf_dosya TEXT NOT NULL,
            cevaplar TEXT NOT NULL,
            soru_sayisi INTEGER NOT NULL,
            ogretmen_id INTEGER,
            olusturma TEXT NOT NULL,
            tur TEXT NOT NULL DEFAULT 'deneme',
            ders TEXT NOT NULL DEFAULT '',
            sinif_id INTEGER,
            kaynak TEXT NOT NULL DEFAULT 'ev'
        )
        """
    )


def up(con: sqlite3.Connection) -> None:
    _ensure_optik_table(con)
    cols = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
    if "yanlis_goturme" not in cols:
        con.execute("ALTER TABLE lgs_optik_sinav ADD COLUMN yanlis_goturme INTEGER DEFAULT 3")
    if "secenekler" not in cols:
        con.execute("ALTER TABLE lgs_optik_sinav ADD COLUMN secenekler TEXT DEFAULT 'ABCD'")
    con.execute("UPDATE lgs_optik_sinav SET yanlis_goturme = 3 WHERE yanlis_goturme IS NULL")
    con.execute("UPDATE lgs_optik_sinav SET secenekler = 'ABCD' WHERE secenekler IS NULL OR secenekler = ''")


def down(con: sqlite3.Connection) -> None:
    cols = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
    if "yanlis_goturme" in cols:
        con.execute("UPDATE lgs_optik_sinav SET yanlis_goturme = NULL")
    if "secenekler" in cols:
        con.execute("UPDATE lgs_optik_sinav SET secenekler = NULL")
