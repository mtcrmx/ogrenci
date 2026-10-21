import sqlite3
import unittest
from datetime import date
from unittest.mock import patch
from test_app_workflows import w
from lgs_ranking import build
from menu import ogretmen_menusu

class LgsHub(unittest.TestCase):
    def test_class_subject_and_home_test_filters_intersect(self):
        con=sqlite3.connect(':memory:'); con.row_factory=sqlite3.Row
        self.addCleanup(con.close)
        con.executescript('''CREATE TABLE siniflar(id,sinif_adi);
            INSERT INTO siniflar VALUES(7,'8/A'),(8,'8/B'),(1,'5/A');
            CREATE TABLE ogrenciler(id,ad_soyad,sinif_id);
            INSERT INTO ogrenciler VALUES(1,'A öğrenci',7),(2,'B öğrenci',8),(3,'Küçük öğrenci',1);
            CREATE TABLE lgs_optik_sinav(id,ad,tarih,ders,sinif_id,kaynak,silindi_at);
            INSERT INTO lgs_optik_sinav VALUES(10,'Fen testi','2026-10-20','Fen Bilimleri',NULL,'ev',NULL),
              (11,'Türkçe testi','2026-10-20','Türkçe',NULL,'ev_yaprak',NULL),
              (12,'Silinen','2026-10-20','Türkçe',NULL,'ev_yaprak','2026-10-21');''')
        rows=[dict(ogrenci_id=oid,kayit=key,ders=subject,kaynak='evde',tarih='2026-10-20',dogru=score,yanlis=0,bos=0,net=score)
              for oid,key,subject,score in [(1,'optik-10','Fen Bilimleri',10),(1,'optik-11','Türkçe',20),
                                           (2,'optik-10','Fen Bilimleri',15),(2,'optik-11','Türkçe',18)]]
        with patch('lgs_ranking.birlesik_sonuclar',return_value=rows):
            shared=build(con,{},today=date(2026,10,21))
            self.assertEqual(shared['metric'],'net')
            self.assertEqual([(r['ad'],r['net']) for r in shared['rows']],[('B öğrenci',33),('A öğrenci',30)])
            self.assertNotIn('optik-12',shared['tests'])
            one=build(con,{'sr_sinif':'8/A','sr_ders':'Türkçe','sr_test':'optik-11'},today=date(2026,10,21))
            self.assertEqual(len(one['rows']),1)
            self.assertEqual(one['rows'][0]['net'],20)
            self.assertEqual(one['course_stats'][0]['net'],20)
            all_home=build(con,{'sr_test':'ev-tumu'},today=date(2026,10,21))
            self.assertEqual([r['net'] for r in all_home['rows']],[33,30])

    def test_lgs_link_exists_with_lower_class_selected_and_hub_renders(self):
        with w.app.test_request_context('/'):
            link=next(i for i in ogretmen_menusu(5,'ogretmen',1) if i['id']=='lgs_takip')
            self.assertIn('ekran=analiz',link['href'])
            self.assertIn('sr_seviye=8',link['href'])
        client=w.app.test_client()
        with client.session_transaction() as session:
            session.update(ogretmen_id=1,ogretmen_adi='Test',ogretmen_yetki='tam',ui_sinif_id=1)
        response=client.get('/lgs?ekran=analiz')
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        for text in ('8/A + 8/B ortak','Derslere göre analiz','Evde soruların tümü','Tüm dersler'):
            self.assertIn(text,html)
