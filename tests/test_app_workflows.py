"""Run with python -m unittest discover -s tests. Uses a temporary database."""
import os
import sys
import tempfile
import unittest
import base64
from io import BytesIO
from html import unescape
from pathlib import Path
from datetime import date

_database = tempfile.TemporaryDirectory(prefix="akademipuan-tests-")
os.environ["OGR_TAKIP_DB_PATH"] = str(Path(_database.name) / "test.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_app as w
import database as d

w.app.config.update(TESTING=True)
d._veli_push_sonra = lambda *_: None
w._ODEV_FOTO_KLASORU = str(Path(_database.name) / 'photos')


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

    def test_guidance_teacher_roster(self):
        teachers=[o for o in d.tum_ogretmenler() if o['ad_soyad']=='ALPEREN MURAT LEBLEBİCİ']
        self.assertEqual(len(teachers),1)
        self.assertEqual(teachers[0]['yetki'],'rehber')
        self.assertEqual(len(d.ogretmen_siniflari(teachers[0]['id'])),8)
        client=w.app.test_client()
        r=client.post('/login',data={'ad_soyad':teachers[0]['ad_soyad'],'sifre':teachers[0]['sifre']})
        self.assertEqual(r.status_code,302)
        self.assertEqual(r.location,'/rehberlik')

    def test_book_treasure_requires_teacher_approval(self):
        con=d._conn()
        student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='5/A' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        oid,sid=student['id'],student['sinif_id']
        book='Bana Derler Küp Cadısı'
        content=w.kitap_icerigi(book)
        d.haftalik_takip_metin(sid,oid,self.week,'kitap_adi',book,self.teacher['id'])
        parent=w.app.test_client()
        with parent.session_transaction() as s:s['veli_ogrenci_id']=oid
        html=parent.get('/veli').get_data(as_text=True)
        self.assertIn('SÜRPRİZ ROZET',html)
        self.assertNotIn(content['konu'],unescape(html))
        self.assertNotIn(content['deger']+' Rozeti',html)
        self.assertNotIn(content['deger']+' rozeti',html)
        self.assertEqual(w._veli_surpriz_kitaplar(oid),[{'ad':book,'hafta':self.week}])
        parent.post('/veli/kitap-okuma/kaydet',data={'kitap_adi':book,'hafta':self.week})
        html=parent.get('/veli').get_data(as_text=True)
        self.assertNotIn(content['konu'],unescape(html))
        entry=d.kitap_okuma_ogrenci_gecmis(oid)[0]
        self.teacher_client.post('/ogretmen/kitap-okuma/'+str(entry['id'])+'/onayla',data={})
        html=parent.get('/veli').get_data(as_text=True)
        self.assertIn(content['konu'],unescape(html))
        self.assertIn(content['deger']+' rozeti kazanıldı',html)
        self.assertNotIn('SÜRPRİZ ROZET',html)
        self.assertEqual(w._veli_surpriz_kitaplar(oid),[])
        self.assertNotIn(content['konu'],self.parent.get('/veli').get_data(as_text=True))

    def test_replacement_book_needs_new_reading_decision(self):
        d.haftalik_takip_metin(self.sid,self.oid,self.week,'kitap_adi','Önceki kitap',self.teacher['id'])
        d.haftalik_takip_isaretle(self.sid,self.oid,self.week,'kitap_okuma','okudu',self.teacher['id'])
        d.haftalik_takip_metin(self.sid,self.oid,self.week,'kitap_adi','Yeni kitap',self.teacher['id'])
        self.assertEqual(d.haftalik_takip_sinif(self.sid,self.week)[self.oid]['kitap_okuma'],'')

    def test_exam_total_rounds_after_adding_courses(self):
        dersler = [dict(ders=ders,dogru=14 if tavan == 20 else 7,yanlis=2,bos=4 if tavan == 20 else 1)
                   for ders,tavan in [('Türkçe',20),('Matematik',20),('Fen Bilimleri',20),
                                     ('T.C. İnkılap Tarihi',10),('Din Kültürü',10),('İngilizce',10)]]
        self.assertTrue(d.lgs_deneme_ekle(self.oid,'Yuvarlama testi','2026-10-01',dersler)['ok'])
        self.assertEqual(d.lgs_denemeler(self.oid)[0]['net'],59)
        self.assertEqual(d._lgs_toplam_net([dict(dogru=0,yanlis=0,net=12.5)]),12.5)

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
            payload=dict(kitap_adi='Örnek kitap',yazar='',okuma_turu='sessiz',sayfa_sayisi=20,saat=0,gun=0,baslangic_tarihi='',bitis_tarihi='',veli_notu='')
            payload.update(extra)
            self.assertFalse(d.kitap_okuma_veli_kaydet(self.oid,**payload)['ok'])

    def test_reading_save_and_approve(self):
        d.haftalik_takip_metin(self.sid,self.oid,self.week,'kitap_adi','Test kitabı',self.teacher['id'])
        r=self.parent.post('/veli/kitap-okuma/kaydet',data={'kitap_adi':'Test kitabı','hafta':self.week},follow_redirects=True)
        self.assertTrue('Kitabı bitirdiğiniz öğretmeninize bildirildi' in r.get_data(as_text=True))
        entry=d.kitap_okuma_ogrenci_gecmis(self.oid)[0]
        r=self.teacher_client.post('/ogretmen/kitap-okuma/'+str(entry['id'])+'/onayla',data={})
        self.assertEqual(r.status_code,302)
        self.assertEqual(d.kitap_okuma_ogrenci_gecmis(self.oid)[0]['durum'],'onaylandi')
        self.assertEqual(d.haftalik_takip_sinif(self.sid,self.week)[self.oid]['kitap_okuma'],'okudu')

    def test_reading_completion_is_assigned_and_deduplicated(self):
        book='Tek düğme test kitabı'
        d.haftalik_takip_metin(self.sid,self.oid,self.week,'kitap_adi',book,self.teacher['id'])
        html=self.parent.get('/veli/kitap-okuma').get_data(as_text=True)
        self.assertNotIn('name="sayfa_sayisi"',html)
        self.assertNotIn('XP',html)
        self.assertIn('Kitabı bitirdik',html)
        payload={'kitap_adi':book,'hafta':self.week,'sayfa_sayisi':'9999','saat':'999','xp':'999'}
        self.assertEqual(self.parent.post('/veli/kitap-okuma/kaydet',data=payload).status_code,302)
        self.parent.post('/veli/kitap-okuma/kaydet',data=payload)
        entries=[k for k in d.kitap_okuma_ogrenci_gecmis(self.oid) if k['kitap_adi']==book]
        self.assertEqual(len(entries),1)
        self.assertEqual((entries[0]['sayfa_sayisi'],entries[0]['saat'],entries[0]['xp']),(0,0,0))
        self.assertEqual(self.parent.post('/veli/kitap-okuma/kaydet',data={**payload,'kitap_adi':'Verilmemiş kitap'}).status_code,400)
        self.assertEqual(self.parent.post('/veli/kitap-okuma/kaydet',data={**payload,'hafta':'2000-01-03'}).status_code,400)

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

    def test_meeting_history_and_status(self):
        self.parent.post('/veli/randevu',data={'mesaj':'Örnek görüşme talebi'})
        talep=d.randevu_ogrenci_listesi(self.oid)[0]
        r=self.teacher_client.post('/ogretmen/randevu/'+str(talep['id'])+'/durum',data={'durum':'gorusuldu'},follow_redirects=True)
        self.assertTrue('Randevu durumu güncellendi' in r.get_data(as_text=True))
        html=self.parent.get('/veli').get_data(as_text=True)
        self.assertTrue('Örnek görüşme talebi' in html and 'Görüşüldü' in html)

    def test_report_role_menu(self):
        with self.teacher_client.session_transaction() as s:s['ogretmen_yetki']='rapor'
        html=self.teacher_client.get('/analiz').get_data(as_text=True)
        self.assertFalse('href="/haftalik-takip' in html)
        self.assertFalse('href="/rapor/kitap-odev' in html)
        self.assertTrue('action="/analiz"' in html)

    def test_photo_upload_and_parent_access(self):
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lN8AAAAASUVORK5CYII=')
        payload={'sinif_id':self.sid,'ogrenci_id':self.oid,'hafta':self.week}
        r=self.teacher_client.post('/haftalik-takip/foto',data={**payload,'foto':(BytesIO(png),'test.png')},follow_redirects=True)
        self.assertTrue('Ödev fotoğrafı kaydedildi' in r.get_data(as_text=True))
        r=self.parent.get('/veli/odev-foto')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data,png)
        r.close()
        r=self.teacher_client.post('/haftalik-takip/foto',data={**payload,'foto':(BytesIO(b'not an image'),'test.png')},follow_redirects=True)
        self.assertTrue('Dosya geçerli bir' in r.get_data(as_text=True))
        self.assertEqual(self.teacher_client.post('/haftalik-takip/foto',data={**payload,'hafta':'../invalid'}).status_code,400)


class GuidanceService(unittest.TestCase):
    def setUp(self):
        import rehberlik as rh
        self.rh = rh
        rh.FILE_DIR = Path(_database.name) / 'guidance-files'
        con = d._conn()
        con.execute('DELETE FROM rehber_gorusme')
        con.execute('DELETE FROM rehber_alici')
        con.execute('DELETE FROM rehber_icerik')
        self.teacher = dict(con.execute("SELECT * FROM ogretmenler WHERE yetki='rehber' LIMIT 1").fetchone())
        self.roster = rh.students()
        self.oid, self.other = self.roster[0]['id'], self.roster[-1]['id']
        con.commit();con.close()
        self.counselor = w.app.test_client()
        self.parent = w.app.test_client()
        self.outsider = w.app.test_client()
        with self.counselor.session_transaction() as s:
            s.update(ogretmen_id=self.teacher['id'],ogretmen_adi=self.teacher['ad_soyad'],ogretmen_yetki='rapor')
        with self.parent.session_transaction() as s:s['veli_ogrenci_id']=self.oid
        with self.outsider.session_transaction() as s:s['veli_ogrenci_id']=self.other
        self.counselor.get('/rehberlik/yeni')
        self.parent.get('/veli/rehberlik')
        self.outsider.get('/veli/rehberlik')

    def token(self, client):
        with client.session_transaction() as s:return s['rehber_csrf']

    def create(self, **overrides):
        data=dict(csrf=self.token(self.counselor),baslik='Deneme rehberi',ozet='Aileler için örnek açıklama',
                  kategori='Ders çalışma',metin='Günde küçük bir adım.',etkinlik='Bir çalışma köşesi seçin.',
                  hedef='ogrenci',ogrenciler=str(self.oid))
        data.update(overrides)
        r=self.counselor.post('/rehberlik/yeni',data=data)
        self.assertEqual(r.status_code,302,r.get_data(as_text=True))
        return int(r.location.rsplit('/',1)[-1])

    def publish(self,cid):
        r=self.counselor.post(f'/rehberlik/icerik/{cid}/yayinla',data={'csrf':self.token(self.counselor)})
        self.assertEqual(r.status_code,302)

    def test_targeting_draft_privacy_and_idempotent_notifications(self):
        cid=self.create()
        self.assertEqual(self.parent.get(f'/veli/rehberlik/icerik/{cid}').status_code,404)
        self.assertNotIn('Deneme rehberi',self.parent.get('/veli/rehberlik').get_data(as_text=True))
        con=d._conn()
        before=con.execute('SELECT COUNT(*) FROM veli_haber WHERE ogrenci_id=?',(self.oid,)).fetchone()[0]
        con.close()
        self.publish(cid);self.publish(cid)
        self.assertEqual(self.parent.get(f'/veli/rehberlik/icerik/{cid}').status_code,200)
        self.assertEqual(self.outsider.get(f'/veli/rehberlik/icerik/{cid}').status_code,404)
        html=self.parent.get('/veli/rehberlik').get_data(as_text=True)
        self.assertIn('Size özel',html)
        self.assertNotIn(self.roster[-1]['ad_soyad'],html)
        con=d._conn()
        self.assertEqual(con.execute('SELECT COUNT(*) FROM veli_haber WHERE ogrenci_id=?',(self.oid,)).fetchone()[0],before+1)
        self.assertEqual(con.execute('SELECT acildi,incelendi,uygulandi FROM rehber_alici WHERE icerik_id=?',(cid,)).fetchone()[1:],('',''))
        con.close()
        self.assertIn('Deneme rehberi',self.parent.get('/veli').get_data(as_text=True))

    def test_feedback_and_counselor_meeting_reply(self):
        cid=self.create();self.publish(cid)
        for action in ('incelendi','uygulandi'):
            for _ in range(2):
                self.assertEqual(self.parent.post(f'/veli/rehberlik/icerik/{cid}',data={'csrf':self.token(self.parent),'islem':action}).status_code,302)
        stats=next(i for i in self.rh.library() if i['id']==cid)
        self.assertEqual((stats['inceleyen'],stats['uygulayan']),(1,1))
        body={'csrf':self.token(self.parent),'icerik_id':str(cid),'mesaj':'Çalışma planı için görüşmek istiyorum.'}
        self.parent.post('/veli/rehberlik/gorusme',data=body)
        self.parent.post('/veli/rehberlik/gorusme',data=body)
        requests=self.rh.meetings(self.oid)
        self.assertEqual(len(requests),1)
        self.assertEqual(self.outsider.post('/veli/rehberlik/gorusme',data={**body,'csrf':self.token(self.outsider)}).status_code,404)
        self.counselor.post('/rehberlik/gorusmeler',data={'csrf':self.token(self.counselor),'id':requests[0]['id'],'durum':'planlandi','yanit':'Salı 14.00, rehberlik servisi.'})
        self.assertIn('Salı 14.00',self.parent.get('/veli/rehberlik').get_data(as_text=True))
        self.assertNotIn('Salı 14.00',self.outsider.get('/veli/rehberlik').get_data(as_text=True))

    def test_file_auth_range_and_archive(self):
        cid=self.create(dosya=(BytesIO(b'%PDF-1.4\n' + b'x'*200 + b'\n%%EOF'), '../../private.pdf'))
        file_url=f'/rehberlik/dosya/{cid}?veli=1'
        self.assertEqual(self.parent.get(file_url).status_code,404)
        self.publish(cid)
        r=self.parent.get(file_url,headers={'Range':'bytes=0-15'})
        self.assertEqual(r.status_code,206)
        self.assertEqual(len(r.data),16)
        self.assertEqual(r.headers['Cache-Control'],'private, no-store')
        r.close()
        self.assertEqual(self.outsider.get(file_url).status_code,404)
        self.assertEqual(w.app.test_client().get(file_url).status_code,403)
        item=self.rh.content(cid)
        self.assertEqual(item['dosya_adi'],'private.pdf')
        self.assertEqual(Path(item['dosya']).name,item['dosya'])
        self.counselor.post(f'/rehberlik/icerik/{cid}/arsivle',data={'csrf':self.token(self.counselor)})
        self.assertEqual(self.parent.get(file_url).status_code,404)
        self.assertEqual(self.parent.get(f'/veli/rehberlik/icerik/{cid}').status_code,404)
        self.assertEqual(self.counselor.post(f'/rehberlik/icerik/{cid}/yayinla',data={'csrf':self.token(self.counselor)}).status_code,409)

    def test_role_and_csrf_boundaries(self):
        cid=self.create()
        self.assertEqual(self.counselor.post(f'/rehberlik/icerik/{cid}/yayinla',data={}).status_code,400)
        self.assertEqual(self.parent.post(f'/veli/rehberlik/icerik/{cid}',data={'islem':'incelendi'}).status_code,400)
        teacher=w.app.test_client()
        con=d._conn();tid=con.execute("SELECT id FROM ogretmenler WHERE yetki='tam' LIMIT 1").fetchone()[0];con.close()
        with teacher.session_transaction() as s:s.update(ogretmen_id=tid,ogretmen_yetki='tam')
        self.assertEqual(teacher.get('/rehberlik').status_code,403)
        self.assertEqual(teacher.get('/rehberlik/yeni').status_code,403)
        self.assertEqual(teacher.get(f'/rehberlik/dosya/{cid}').status_code,403)
        self.assertEqual(self.counselor.post('/haftalik-takip/isaret',json={}).status_code,403)
        self.assertEqual(self.counselor.get('/dashboard').location,'/rehberlik')
        self.assertEqual(self.counselor.get('/analiz').status_code,200)
        self.assertEqual(self.counselor.get('/ogretmen/randevular').location,'/rehberlik')

    def test_draft_edit_keeps_file_and_replaces_audience(self):
        cid=self.create(dosya=(BytesIO(b'%PDF-1.4\n%%EOF'), 'slides.pdf'))
        original=self.rh.content(cid)['dosya']
        r=self.counselor.post(f'/rehberlik/icerik/{cid}/duzenle',data={'csrf':self.token(self.counselor),'baslik':'Düzenlenen başlık','kategori':'Ders çalışma','ozet':'Yeni açıklama','metin':'Yeni yazı','hedef':'ogrenci','ogrenciler':str(self.other)})
        self.assertEqual(r.status_code,302)
        self.assertEqual(self.rh.content(cid)['dosya'],original)
        self.assertEqual([p['ogrenci_id'] for p in self.rh.recipients(cid)],[self.other])
        self.publish(cid)
        self.assertEqual(self.counselor.get(f'/rehberlik/icerik/{cid}/duzenle').status_code,409)
        self.assertEqual(self.parent.get(f'/veli/rehberlik/icerik/{cid}').status_code,404)
        self.assertEqual(self.outsider.get(f'/veli/rehberlik/icerik/{cid}').status_code,200)

    def test_class_and_school_audiences(self):
        cid=self.create(hedef='sinif',siniflar=str(self.roster[0]['sinif_id']))
        self.assertEqual({p['sinif_adi'] for p in self.rh.recipients(cid)},{self.roster[0]['sinif_adi']})
        cid=self.create(hedef='tum')
        self.assertEqual(len(self.rh.recipients(cid)),len(self.roster))

    def test_invalid_files_and_audiences_do_not_create_content(self):
        for overrides in ({'dosya':(BytesIO(b'<script>bad</script>'),'fake.pdf')},
                          {'dosya':(BytesIO(b'<html>bad</html>'),'script.html')},
                          {'ogrenciler':'999999'}, {'hedef':'sinif','siniflar':'bad'}, {'metin':''}):
            data=dict(csrf=self.token(self.counselor),baslik='Invalid test',ozet='Test',kategori='Ders çalışma',metin='Test',hedef='ogrenci',ogrenciler=str(self.oid))
            data.update(overrides)
            self.assertEqual(self.counselor.post('/rehberlik/yeni',data=data).status_code,400)
        self.assertEqual(self.rh.library(),[])

    def test_pdf_module_content_type(self):
        for asset in ('pdf.min.mjs','pdf.worker.min.mjs'):
            r=w.app.test_client().get('/static/vendor/pdfjs/build/'+asset)
            self.assertEqual(r.status_code,200)
            self.assertIn(r.mimetype,('text/javascript','application/javascript'))
            r.close()

    def test_parallel_publish_creates_one_notification_per_parent(self):
        from concurrent.futures import ThreadPoolExecutor
        cid=self.create()
        con=d._conn()
        before=con.execute('SELECT COUNT(*) FROM veli_haber WHERE ogrenci_id=?',(self.oid,)).fetchone()[0]
        con.close()
        def publish_once(_):
            client=w.app.test_client()
            with client.session_transaction() as s:
                s.update(ogretmen_id=self.teacher['id'],ogretmen_yetki='rehber',rehber_csrf='parallel-publish-token')
            return client.post(f'/rehberlik/icerik/{cid}/yayinla',data={'csrf':'parallel-publish-token'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(publish_once,range(2))),[302,302])
        con=d._conn()
        self.assertEqual(con.execute('SELECT COUNT(*) FROM veli_haber WHERE ogrenci_id=?',(self.oid,)).fetchone()[0],before+1)
        con.close()


if __name__=='__main__':unittest.main()
