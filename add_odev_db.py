import sqlite3
import os

DB_PATH = "c:/Users/METE/OneDrive/Belgeler/GitHub/ogrenci-takip/ogrenci_takip.db"

# Create tables in the live DB
con = sqlite3.connect(DB_PATH)
con.executescript("""
    CREATE TABLE IF NOT EXISTS odevler (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sinif_id    INTEGER NOT NULL REFERENCES siniflar(id),
        ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
        ders_adi    TEXT    NOT NULL,
        tema_adi    TEXT    NOT NULL,
        tarih       TEXT    NOT NULL
    );
    CREATE TABLE IF NOT EXISTS odev_sonuclari (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        odev_id     INTEGER NOT NULL REFERENCES odevler(id),
        ogrenci_id  INTEGER NOT NULL REFERENCES ogrenciler(id),
        durum       TEXT    NOT NULL -- 'tamamladi' veya 'tamamlamadi'
    );
""")
con.commit()
con.close()
print("Tables created.")

# Append to database.py
code_to_append = """
# ══════════════════════════════════════════════════════════════════════════
# ÖDEV TAKİBİ
# ══════════════════════════════════════════════════════════════════════════

def odev_olustur(ogretmen_id: int, sinif_id: int, ders_adi: str, tema_adi: str) -> int:
    con = _conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO odevler (ogretmen_id, sinif_id, ders_adi, tema_adi, tarih) VALUES (?, ?, ?, ?, ?)",
        (ogretmen_id, sinif_id, ders_adi, tema_adi, datetime.now().isoformat())
    )
    odev_id = cur.lastrowid
    
    # Tüm sınıf öğrencilerine varsayılan olarak 'tamamlamadi' ekle
    ogrenciler = con.execute("SELECT id FROM ogrenciler WHERE sinif_id = ?", (sinif_id,)).fetchall()
    for (ogr_id,) in ogrenciler:
        cur.execute(
            "INSERT INTO odev_sonuclari (odev_id, ogrenci_id, durum) VALUES (?, ?, 'tamamlamadi')",
            (odev_id, ogr_id['id'])
        )
    con.commit()
    con.close()
    return odev_id

def odevleri_getir(ogretmen_id: int):
    con = _conn()
    rows = con.execute(
        '''SELECT o.id, s.sinif_adi, o.ders_adi, o.tema_adi, o.tarih,
                  (SELECT count(*) FROM odev_sonuclari WHERE odev_id = o.id AND durum = 'tamamladi') as tamamlayanlar,
                  (SELECT count(*) FROM odev_sonuclari WHERE odev_id = o.id) as toplam_ogrenci
           FROM odevler o
           JOIN siniflar s ON o.sinif_id = s.id
           WHERE o.ogretmen_id = ?
           ORDER BY o.id DESC''' ,
        (ogretmen_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def odev_detay_getir(odev_id: int, ogretmen_id: int):
    con = _conn()
    odev = con.execute(
        "SELECT o.*, s.sinif_adi FROM odevler o JOIN siniflar s ON o.sinif_id = s.id WHERE o.id = ? AND o.ogretmen_id = ?",
        (odev_id, ogretmen_id)
    ).fetchone()
    if not odev:
        con.close()
        return None
        
    ogrenciler = con.execute(
        '''SELECT og.id, og.ad_soyad, og.ogr_no, os.durum
           FROM odev_sonuclari os
           JOIN ogrenciler og ON os.ogrenci_id = og.id
           WHERE os.odev_id = ?
           ORDER BY og.ogr_no ASC''' ,
        (odev_id,)
    ).fetchall()
    con.close()
    return {"odev": dict(odev), "ogrenciler": [dict(r) for r in ogrenciler]}

def odev_durum_guncelle(odev_id: int, ogrenci_id: int, durum: str):
    con = _conn()
    con.execute(
        "UPDATE odev_sonuclari SET durum = ? WHERE odev_id = ? AND ogrenci_id = ?",
        (durum, odev_id, ogrenci_id)
    )
    con.commit()
    con.close()
"""

with open('c:/Users/METE/OneDrive/Belgeler/GitHub/ogrenci-takip/database.py', 'a', encoding='utf-8') as f:
    f.write(code_to_append)

print("database.py appended successfully.")
