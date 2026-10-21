import sqlite3
import unittest
from test_app_workflows import w
from school_broadcast import net_leaders

class NetLeaders(unittest.TestCase):
    def test_home_totals_exclude_school_exams_deleted_and_future_results(self):
        con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
        self.addCleanup(con.close)
        con.executescript("""CREATE TABLE siniflar(id,sinif_adi);
          INSERT INTO siniflar VALUES(1,'8/A');
          CREATE TABLE ogrenciler(id,ad_soyad,sinif_id);
          CREATE TABLE lgs_optik_sinav(id,tarih,tur,kaynak,silindi_at);
          CREATE TABLE lgs_optik_sonuc(id,sinav_id,ogrenci_id,net);
          INSERT INTO lgs_optik_sinav VALUES(1,'2026-10-20','yaprak','ev_yaprak',NULL),
          (2,'2026-10-21','deneme','ev',NULL),(3,'2026-10-20','yaprak','kamera',NULL),
          (4,'2026-10-20','deneme','ev','2026-10-21'),(5,'2026-10-30','yaprak','ev',NULL);""")
        self.assertEqual(net_leaders(con,'2026-10-21')['ogrenciler'],[])
        for i in range(1,8):
            con.execute('INSERT INTO ogrenciler VALUES(?,?,1)',(i,f'Öğrenci {i}'))
            con.execute('INSERT INTO lgs_optik_sonuc VALUES(?,1,?,?)',(i,i,i))
        con.execute('INSERT INTO lgs_optik_sonuc VALUES(8,2,1,7)')
        for eid in (3,4,5,99):
            con.execute('INSERT INTO lgs_optik_sonuc VALUES(?, ?,2,100)',(eid+10,eid))
        result=net_leaders(con,'2026-10-21')['ogrenciler']
        self.assertEqual(len(result),5)
        self.assertEqual(result[0]['ad'],'Öğrenci 1')
        self.assertEqual(result[0]['net'],8)
        self.assertEqual(result[0]['test_sayisi'],2)
        self.assertEqual(result[1]['net'],7)
        self.assertEqual(set(result[0]),{'ad','sinif','sira','net','test_sayisi'})
        con.execute("UPDATE lgs_optik_sinav SET silindi_at='2026-10-21' WHERE id=2")
        self.assertEqual(net_leaders(con,'2026-10-21')['ogrenciler'][0]['ad'],'Öğrenci 7')
        con.execute('UPDATE lgs_optik_sonuc SET net=7 WHERE id=6')
        self.assertEqual([r['sira'] for r in net_leaders(con,'2026-10-21')['ogrenciler']],[1,1,3,4,5])
