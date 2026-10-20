"""Migration 007: Test amaçlı açılmış 8/C şubesini ve sahte öğrencilerini kaldırır.

Yalnızca adı 'TEST OGRENCI 8C' olan öğrenciler silinir; şubede gerçek öğrenci
varsa şube silinmez.
"""
VERSION = 7

_SAHTE_AD = "TEST OGRENCI 8C"


def _tablolar_sutunla(con, sutun):
    out = []
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        cols = {r[1] for r in con.execute(f'PRAGMA table_info("{t}")').fetchall()}
        if sutun in cols:
            out.append(t)
    return out


def up(con):
    row = con.execute("SELECT id FROM siniflar WHERE sinif_adi='8/C'").fetchone()
    if not row:
        return
    sid = int(row[0])
    sahte = [int(r[0]) for r in con.execute(
        "SELECT id FROM ogrenciler WHERE sinif_id=? AND ad_soyad=?", (sid, _SAHTE_AD)
    ).fetchall()]
    if sahte:
        yer = ",".join("?" * len(sahte))
        for t in _tablolar_sutunla(con, "ogrenci_id"):
            con.execute(f'DELETE FROM "{t}" WHERE ogrenci_id IN ({yer})', sahte)
        con.execute(f"DELETE FROM ogrenciler WHERE id IN ({yer})", sahte)
    kalan = con.execute("SELECT COUNT(*) FROM ogrenciler WHERE sinif_id=?", (sid,)).fetchone()[0]
    if kalan:
        con.commit()
        return
    for t in _tablolar_sutunla(con, "sinif_id"):
        if t == "ogrenciler":
            continue
        con.execute(f'DELETE FROM "{t}" WHERE sinif_id=?', (sid,))
    con.execute("DELETE FROM siniflar WHERE id=?", (sid,))
    con.commit()


def down(con):
    # Silinen sahte veriler geri getirilmez.
    pass
