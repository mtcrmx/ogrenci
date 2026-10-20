"""Migration 008: Alperen Murat Leblebici yönetici yetkili öğretmen ekranına geçer.

Rol 'tam' olur (öğretmen ekranı); 'rehber' yetki satırı unvan ve rehber_adi()
için korunur.
"""
VERSION = 8
NAME = "008_alperen_yonetici"

_AD = "ALPEREN MURAT LEBLEBİCİ"
_EK_YETKILER = ("yonetici", "evrak_takip", "lgs_yonet")


def _ogretmen_id(con):
    row = con.execute("SELECT id FROM ogretmenler WHERE ad_soyad = ?", (_AD,)).fetchone()
    return int(row[0]) if row else None


def up(con):
    oid = _ogretmen_id(con)
    if oid is None:
        return
    con.execute("UPDATE ogretmenler SET yetki = 'tam' WHERE id = ?", (oid,))
    for yetki in _EK_YETKILER + ("rehber",):
        con.execute(
            "INSERT OR IGNORE INTO ogretmen_yetki (ogretmen_id, yetki) VALUES (?, ?)",
            (oid, yetki),
        )
    con.commit()


def down(con):
    oid = _ogretmen_id(con)
    if oid is None:
        return
    con.execute("UPDATE ogretmenler SET yetki = 'rehber' WHERE id = ?", (oid,))
    con.execute(
        "DELETE FROM ogretmen_yetki WHERE ogretmen_id = ? AND yetki IN ('yonetici', 'evrak_takip')",
        (oid,),
    )
    con.execute(
        "INSERT OR IGNORE INTO ogretmen_yetki (ogretmen_id, yetki) VALUES (?, 'rehber')", (oid,)
    )
    con.commit()
