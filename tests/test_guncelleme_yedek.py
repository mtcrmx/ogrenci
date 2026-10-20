import os
import shutil
import sqlite3

import database


def test_bekleyen_migration_varsa_once_yedek_alinir(tmp_path, monkeypatch):
    db = tmp_path / "ogrenci_takip.db"
    shutil.copy(database.DB_PATH, db)
    con = sqlite3.connect(db)
    con.execute("DELETE FROM schema_version WHERE version = (SELECT MAX(version) FROM schema_version)")
    ogrenci = con.execute("SELECT COUNT(*) FROM ogrenciler").fetchone()[0]
    con.commit()
    con.close()
    monkeypatch.setattr(database, "DB_PATH", str(db))

    yol = database._guncelleme_oncesi_yedek()

    assert yol and os.path.exists(yol)
    yedek = sqlite3.connect(yol)
    assert yedek.execute("SELECT COUNT(*) FROM ogrenciler").fetchone()[0] == ogrenci
    yedek.close()


def test_guncel_veritabaninda_yedek_alinmaz(tmp_path, monkeypatch):
    db = tmp_path / "ogrenci_takip.db"
    shutil.copy(database.DB_PATH, db)
    monkeypatch.setattr(database, "DB_PATH", str(db))
    assert database._guncelleme_oncesi_yedek() is None
