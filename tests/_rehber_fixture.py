"""Rehber rolündeki geçici öğretmen (testlerde oluşturulur, sonra silinir)."""
import database as d

REHBER_TEST_ADI = "TEST REHBER ÖĞRETMEN"


def rehber_ogretmen_olustur() -> dict:
    con = d._conn()
    try:
        con.execute("DELETE FROM ogretmenler WHERE ad_soyad = ?", (REHBER_TEST_ADI,))
        oid = con.execute(
            "INSERT INTO ogretmenler (ad_soyad, sifre, yetki) VALUES (?, ?, 'rehber')",
            (REHBER_TEST_ADI, "rehber-test-9137"),
        ).lastrowid
        con.execute(
            "INSERT OR IGNORE INTO ogretmen_yetki (ogretmen_id, yetki) VALUES (?, 'rehber')", (oid,)
        )
        con.commit()
        return dict(con.execute("SELECT * FROM ogretmenler WHERE id = ?", (oid,)).fetchone())
    finally:
        con.close()


def rehber_ogretmen_sil(ogretmen_id: int) -> None:
    con = d._conn()
    try:
        con.execute("PRAGMA foreign_keys = OFF")
        tablolar = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tablolar:
            for fk in con.execute(f'PRAGMA foreign_key_list("{t}")').fetchall():
                if fk[2] == "ogretmenler":
                    con.execute(f'DELETE FROM "{t}" WHERE "{fk[3]}" = ?', (ogretmen_id,))
        con.execute("DELETE FROM ogretmenler WHERE id = ?", (ogretmen_id,))
        con.commit()
    finally:
        con.close()
