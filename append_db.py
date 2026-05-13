import sqlite3

code = """
def ogrenci_ozellikleri_getir(ogrenci_id: int, tik_sayisi: int = 0) -> dict:
    con = _conn()
    row = con.execute("SELECT * FROM ogrenci_ozellikler WHERE ogrenci_id = ?", (ogrenci_id,)).fetchone()
    
    # Kalan puan hesabı: 1 tik = 1 puan. Puanlar temel 50 üzerine eklenir.
    toplam_harcanan = 0
    if row:
        toplam_harcanan = (row['hiz'] - 50) + (row['sut'] - 50) + (row['pas'] - 50) + (row['defans'] - 50) + (row['kaleci'] - 50)
        kalan = max(0, tik_sayisi - toplam_harcanan)
        if kalan != row['kalan_puan']:
            con.execute("UPDATE ogrenci_ozellikler SET kalan_puan = ? WHERE ogrenci_id = ?", (kalan, ogrenci_id))
            con.commit()
            row = con.execute("SELECT * FROM ogrenci_ozellikler WHERE ogrenci_id = ?", (ogrenci_id,)).fetchone()
    else:
        con.execute("INSERT INTO ogrenci_ozellikler (ogrenci_id, kalan_puan) VALUES (?, ?)", (ogrenci_id, tik_sayisi))
        con.commit()
        row = con.execute("SELECT * FROM ogrenci_ozellikler WHERE ogrenci_id = ?", (ogrenci_id,)).fetchone()
        
    con.close()
    return dict(row)

def ogrenci_ozellik_artir(ogrenci_id: int, ozellik: str, tik_sayisi: int) -> dict:
    gecerli = ['hiz', 'sut', 'pas', 'defans', 'kaleci']
    if ozellik not in gecerli: return {'ok': False, 'sebep': 'Geçersiz özellik'}
    
    con = _conn()
    row = con.execute("SELECT * FROM ogrenci_ozellikler WHERE ogrenci_id = ?", (ogrenci_id,)).fetchone()
    if not row:
        con.close()
        return {'ok': False, 'sebep': 'Özellik kaydı bulunamadı'}
        
    # Recalculate correctly to avoid async exploits
    toplam_harcanan = (row['hiz'] - 50) + (row['sut'] - 50) + (row['pas'] - 50) + (row['defans'] - 50) + (row['kaleci'] - 50)
    kalan = tik_sayisi - toplam_harcanan
    
    if kalan <= 0:
        con.close()
        return {'ok': False, 'sebep': 'Geliştirme puanınız kalmadı'}
        
    if row[ozellik] >= 99:
        con.close()
        return {'ok': False, 'sebep': 'Bu özellik maksimum seviyede'}
        
    con.execute(f"UPDATE ogrenci_ozellikler SET {ozellik} = {ozellik} + 1, kalan_puan = ? WHERE ogrenci_id = ?", (kalan - 1, ogrenci_id))
    con.commit()
    con.close()
    return {'ok': True, 'kalan': kalan - 1}
"""

with open('c:\\Users\\METE\\OneDrive\\Belgeler\\GitHub\\ogrenci-takip\\database.py', 'a', encoding='utf-8') as f:
    f.write(code)

print("Appended successfully.")
