import unittest
from test_app_workflows import w,d
from flask import render_template


class HomeTestListing(unittest.TestCase):
    def test_both_types_and_attendance_without_scores(self):
        groups=[{'sinif':{'id':7,'sinif_adi':'8/A'},'ogrenciler':[{'id':1,'ad_soyad':'Tamamlayan öğrenci'},{'id':2,'ad_soyad':'Bekleyen öğrenci'}]},
                {'sinif':{'id':8,'sinif_adi':'8/B'},'ogrenciler':[{'id':3,'ad_soyad':'Diğer sınıf'}]}]
        exams=[dict(id=i,ad=name,tur=kind,kaynak=source,sinif_id=7,sinif_adi='8/A',tarih='2026-10-21',soru_sayisi=20,ogretmen_id=999,cevaplar=['A'],sonuclar=[{'ogrenci_id':1,'dogru':18,'yanlis':1,'bos':1,'net':19.67}])
               for i,name,kind,source in [(1,'Ev denemesi','deneme','ev'),(2,'Ev yaprak testi','yaprak','ev_yaprak'),(3,'Okul kamera testi','yaprak','kamera')]]
        w._evde_katilim_ekle(exams,groups)
        self.assertEqual(exams[0]['tamamlayan'],1)
        self.assertEqual(len(exams[0]['katilim']),2)
        with w.app.test_request_context('/lgs?ekran=evde'):
            html=render_template('_evde_sorular_ogretmen.html',optik_sinavlar=exams,gruplar=groups,lgs_dersler=[],bugun='2026-10-21')
        for text in ('Yayınlanan testler','Ev denemesi','Ev yaprak testi','1 / 2 tamamladı','Tamamlayan öğrenci','Bekleyen öğrenci','Henüz tamamlamadı','19.67','<th>Net</th>'):
            self.assertIn(text,html)
        for text in ('Okul kamera testi','Diğer sınıf','Öğrenci sonuçları','<details open>'):
            self.assertNotIn(text,html)
