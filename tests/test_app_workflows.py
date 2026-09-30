"""Run with python -m unittest discover -s tests. Uses a temporary database."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import date

_database = tempfile.TemporaryDirectory(prefix="akademipuan-tests-")
os.environ["OGR_TAKIP_DB_PATH"] = str(Path(_database.name) / "test.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_app as w
import database as d

w.app.config.update(TESTING=True)
d._veli_push_sonra = lambda *_: None


class Workflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        con = d._conn()
        cls.teacher = dict(con.execute("SELECT * FROM ogretmenler ORDER BY id LIMIT 1").fetchone())
        cls.student = dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        cls.sid = cls.student['sinif_id']
        cls.oid = cls.student['id']
        cls.week = w._lgs_hafta()

    def setUp(self):
        self.teacher_client = w.app.test_client()
        self.parent = w.app.test_client()
        with self.teacher_client.session_transaction() as s:
            s.update(ogretmen_id=self.teacher['id'], ogretmen_adi=self.teacher['ad_soyad'], ogretmen_yetki='tam')
        with self.parent.session_transaction() as s:
            s['veli_ogrenci_id'] = self.oid

    def test_tracking_and_notification(self):
        payload = dict(sinif_id=self.sid,ogrenci_id=self.oid,hafta=self.week,alan='odev_durum',deger='eksik')
        r=self.teacher_client.post('/haftalik-takip/isaret',json=payload)
        self.assertTrue(r.json['ok'])
        self.assertEqual(d.haftalik_takip_sinif(self.sid,self.week)[self.oid]['odev_durum'],'eksik')
        self.assertTrue(d.veli_haber_yeni(self.oid,0))

    def test_tracking_malformed_request(self):
        for url in ['/haftalik-takip/isaret','/haftalik-takip/metin','/haftalik-takip/toplu']:
            for payload in [{'sinif_id':'abc'},['wrong shape']]:
                with self.subTest(url=url,payload=payload):
                    self.assertEqual(self.teacher_client.post(url,json=payload).status_code,400)

    def test_tracking_invalid_week(self):
        r=self.teacher_client.post('/haftalik-takip/isaret',json=dict(sinif_id=self.sid,ogrenci_id=self.oid,hafta='not-a-date',alan='odev_durum',deger='tam'))
        self.assertEqual(r.status_code,400)

    def test_parent_menu_has_reading_entry(self):
        self.assertTrue('/veli/kitap-okuma' in self.parent.get('/veli').get_data(as_text=True))

    def test_meeting_confirmation_and_empty_message(self):
        r=self.parent.post('/veli/randevu',data={'mesaj':'Haftalık planı görüşmek istiyorum.'},follow_redirects=True)
        self.assertTrue('Görüşme talebiniz kaydedildi' in r.get_data(as_text=True))
        self.assertTrue(r.history[0].location.endswith('#mesajlar'))
        con=d._conn()
        before=con.execute('SELECT COUNT(*) FROM randevu_talebi').fetchone()[0]
        con.close()
        r=self.parent.post('/veli/randevu',data={'mesaj':'   '},follow_redirects=True)
        self.assertTrue('Görüşme konusunu yazın' in r.get_data(as_text=True))
        con=d._conn()
        self.assertEqual(con.execute('SELECT COUNT(*) FROM randevu_talebi').fetchone()[0],before)
        con.close()

    def test_reading_validation(self):
        for extra in [{'sayfa_sayisi':'0'}, {'sayfa_sayisi':'20','baslangic_tarihi':'2026-10-10','bitis_tarihi':'2026-10-01'}, {'sayfa_sayisi':'20','saat':'nan'}]:
            r=self.parent.post('/veli/kitap-okuma/kaydet',data={'kitap_adi':'Örnek kitap',**extra},follow_redirects=True)
            self.assertFalse('Okuma kaydı öğretmen onayına gönderildi' in r.get_data(as_text=True))

    def test_reading_save_and_approve(self):
        r=self.parent.post('/veli/kitap-okuma/kaydet',data={'kitap_adi':'Test kitabı','sayfa_sayisi':'32','saat':'0.5','gun':'1'},follow_redirects=True)
        self.assertTrue('Okuma kaydı öğretmen onayına gönderildi' in r.get_data(as_text=True))
        entry=d.kitap_okuma_ogrenci_gecmis(self.oid)[0]
        r=self.teacher_client.post('/ogretmen/kitap-okuma/'+str(entry['id'])+'/onayla',data={})
        self.assertEqual(r.status_code,302)
        self.assertEqual(d.kitap_okuma_ogrenci_gecmis(self.oid)[0]['durum'],'onaylandi')

    def test_teacher_secondary_tools_reachable(self):
        html=self.teacher_client.get('/dashboard').get_data(as_text=True)
        for url in ['/ogretmen/kitap-okuma','/ogretmen/randevular']:
            self.assertTrue(url in html,url)

    def test_lgs_custom_program_and_approval(self):
        today=date.today()
        self.teacher_client.post('/lgs',data={'ogrenci':self.oid,'islem':'ozel_program','gun':today.weekday(),'gorevler':'Matematik: 15 soru'})
        self.parent.post('/veli/lgs',data={'islem':'program_bildir','tarih':today.isoformat(),'sira':'0'})
        record=d.lgs_program_isaretler(self.oid,today.isoformat(),today.isoformat())[(today.isoformat(),0)]
        self.assertFalse(record.get('tamamlandi'))
        self.teacher_client.post('/lgs',data={'ogrenci':self.oid,'islem':'program_onay','tarih':today.isoformat(),'sira':'0','karar':'onay'})
        record=d.lgs_program_isaretler(self.oid,today.isoformat(),today.isoformat())[(today.isoformat(),0)]
        self.assertTrue(record.get('tamamlandi'))
        self.assertTrue('Matematik: 15 soru' in self.parent.get('/veli/lgs?bolum=program').get_data(as_text=True))

    def test_exports(self):
        for url in ['/karne.xlsx?sinif='+str(self.sid), '/veli/karne.xlsx','/veli/karne.pdf']:
            client=self.parent if url.startswith('/veli') else self.teacher_client
            r=client.get(url)
            self.assertEqual(r.status_code,200,url)
            self.assertTrue(r.data.startswith(b'%PDF') if url.endswith('.pdf') else r.data.startswith(b'PK'),url)

    def test_login_role_switch(self):
        r=self.teacher_client.post('/veli/giris',data={'ogr_no':self.student['ogr_no'],'sifre':w.VELI_SIFRE})
        self.assertEqual(r.status_code,302)
        with self.teacher_client.session_transaction() as s:
            self.assertEqual(s['veli_ogrenci_id'],self.oid)
            self.assertNotIn('ogretmen_id',s)
        r=self.teacher_client.post('/login',data={'ad_soyad':self.teacher['ad_soyad'],'sifre':self.teacher['sifre']})
        self.assertEqual(r.status_code,302)
        with self.teacher_client.session_transaction() as s:
            self.assertEqual(s['ogretmen_id'],self.teacher['id'])
            self.assertNotIn('veli_ogrenci_id',s)


if __name__=='__main__':unittest.main()
