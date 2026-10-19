"""Migration 002: ogretmen_yetki tablosu ve mevcut yetkilerin aktarımı."""
from __future__ import annotations

import sqlite3

VERSION = 2
NAME = "002_roller"

VARSAYILAN_YETKILER: dict[str, tuple[str, ...]] = {
    "ADEM AKGÜL": ("yonetici", "mudur", "toplu_sifirlama", "evrak_takip", "lgs_yonet"),
    "METEHAN CÜCEN": ("yonetici", "mudur_yrd", "sayfa_sifirlama", "evrak_takip", "lgs_yonet"),
    "ALPEREN MURAT LEBLEBİCİ": ("lgs_yonet", "rehber"),
}


def up(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS ogretmen_yetki (
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id) ON DELETE CASCADE,
            yetki TEXT NOT NULL,
            PRIMARY KEY (ogretmen_id, yetki)
        );
        CREATE INDEX IF NOT EXISTS idx_ogretmen_yetki_yetki ON ogretmen_yetki(yetki, ogretmen_id);
        """
    )
    rows = con.execute("SELECT id, ad_soyad, COALESCE(yetki, 'tam') AS yetki FROM ogretmenler").fetchall()
    for row in rows:
        oid = int(row["id"])
        ad = (row["ad_soyad"] or "").strip()
        mevcut_rol = (row["yetki"] or "tam").strip()
        for yetki_adi in VARSAYILAN_YETKILER.get(ad, ()):
            con.execute(
                "INSERT OR IGNORE INTO ogretmen_yetki (ogretmen_id, yetki) VALUES (?, ?)",
                (oid, yetki_adi),
            )
        if mevcut_rol in ("rehber", "rapor"):
            con.execute(
                "INSERT OR IGNORE INTO ogretmen_yetki (ogretmen_id, yetki) VALUES (?, ?)",
                (oid, mevcut_rol),
            )


def down(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS ogretmen_yetki")
