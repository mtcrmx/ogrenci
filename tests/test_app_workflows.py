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
        con=d._conn()
        student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='6/A' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        payload = dict(sinif_id=student['sinif_id'],ogrenci_id=student['id'],hafta=self.week,alan='odev_durum',deger='eksik')
        r=self.teacher_client.post('/haftalik-takip/isaret',json=payload)
        self.assertTrue(r.json['ok'])
        self.assertEqual(d.haftalik_takip_sinif(student['sinif_id'],self.week)[student['id']]['odev_durum'],'eksik')
        self.assertTrue(d.veli_haber_yeni(student['id'],0))
        blocked=self.teacher_client.post('/haftalik-takip/isaret',json=dict(sinif_id=self.sid,ogrenci_id=self.oid,hafta=self.week,alan='odev_durum',deger='eksik'))
        self.assertEqual(blocked.status_code,403)

    def _latest_action(self, client=None):
        con=d._conn()
        row=con.execute('SELECT id FROM ogretmen_islem WHERE ogretmen_id=? ORDER BY rowid DESC LIMIT 1',(self.teacher['id'],)).fetchone()
        con.close()
        return row[0]

    def test_student_search_by_number_and_turkish_name(self):
        from student_results import normalize
        found=self.teacher_client.get('/api/ogrenci-ara',query_string={'q':self.student['ogr_no'],'kapsam':'lgs'})
        self.assertEqual(found.status_code,200)
        self.assertIn(self.oid,[r['id'] for r in found.json['ogrenciler']])
        found=self.teacher_client.get('/api/ogrenci-ara',query_string={'q':normalize(self.student['ad_soyad'])})
        self.assertIn(self.oid,[r['id'] for r in found.json['ogrenciler']])
        self.assertEqual(self.parent.get('/api/ogrenci-ara?q=a').status_code,302)
        self.assertEqual(w.app.test_client().get('/api/ogrenci-ara?q=a').status_code,302)
        self.assertTrue(all(r['sinif'].startswith('8/') for r in self.teacher_client.get('/api/ogrenci-ara?q=a&kapsam=lgs').json['ogrenciler']))

    def test_institution_upload_has_named_server_permission(self):
        teachers=d.tum_ogretmenler()
        for name in ('ADEM AKGÜL','METEHAN CÜCEN'):
            t=next(r for r in teachers if r['ad_soyad']==name)
            c=w.app.test_client()
            with c.session_transaction() as s:s.update(ogretmen_id=t['id'],ogretmen_adi=name,ogretmen_yetki='tam')
            self.assertIn('/lgs/kurum-pdf',c.get('/lgs').get_data(as_text=True))
            self.assertEqual(c.post('/lgs/kurum-pdf').status_code,302)
        other=next(r for r in teachers if r['ad_soyad'] not in ('ADEM AKGÜL','METEHAN CÜCEN') and r['yetki']=='tam')
        c=w.app.test_client()
        with c.session_transaction() as s:s.update(ogretmen_id=other['id'],ogretmen_adi='ADEM AKGÜL',ogretmen_yetki='tam')
        self.assertNotIn('/lgs/kurum-pdf',c.get('/lgs').get_data(as_text=True))
        self.assertEqual(c.post('/lgs/kurum-pdf').status_code,403)

    def test_course_result_edit_undo_and_parent_analysis(self):
        payload=dict(ogrenci=self.oid,tur='ders',ad='35 soruluk matematik testi',tarih='2026-10-01',ders='Matematik',soru_sayisi='35',dogru='26',yanlis='4',yanlis_goturme='0')
        self.assertEqual(self.teacher_client.post('/sonuclar',data=payload).status_code,302)
        creation=self._latest_action()
        record=next(r for r in d.lgs_denemeler(self.oid,200) if r['ad']==payload['ad'])
        self.assertEqual(record['net'],26)
        self.assertEqual(record['dersler'][0]['bos'],5)
        self.assertIn('74.3%',self.parent.get('/veli/sonuclar').get_data(as_text=True))
        self.assertIn('35 soruluk matematik testi',self.parent.get('/veli/lgs?bolum=deneme').get_data(as_text=True))
        from flask import template_rendered
        contexts=[]
        def capture(sender,template,context,**extra):contexts.append(context)
        with template_rendered.connected_to(capture,w.app):
            self.parent.get('/veli/lgs?bolum=deneme')
        context=next(c for c in contexts if 'kocluk' in c)
        self.assertNotIn(record['id'],[r['id'] for r in context['denemeler']])
        payload.update(duzenle=record['id'],surum=record['surum'],dogru='30')
        self.assertEqual(self.teacher_client.post('/sonuclar',data=payload).status_code,302)
        edit=self._latest_action()
        revised=next(r for r in d.lgs_denemeler(self.oid,200) if r['id']==record['id'])
        self.assertEqual(revised['net'],30)
        self.assertEqual(revised['surum'],2)
        self.assertEqual(self.teacher_client.post('/sonuclar',data=payload).status_code,200)
        self.assertEqual(next(r for r in d.lgs_denemeler(self.oid,200) if r['id']==record['id'])['surum'],2)
        self.teacher_client.post('/islem-gecmisi/'+edit+'/geri-al')
        restored=next(r for r in d.lgs_denemeler(self.oid,200) if r['id']==record['id'])
        self.assertEqual(restored['net'],26)
        self.assertEqual(restored['surum'],1)
        self.teacher_client.post('/islem-gecmisi/'+creation+'/geri-al')
        self.assertNotIn(record['id'],[r['id'] for r in d.lgs_denemeler(self.oid,200)])

    def test_course_result_rejects_invalid_totals_and_foreign_edit(self):
        payload=dict(ogrenci=self.oid,tur='ders',ad='Geçersiz toplam',tarih='2026-10-01',ders='Türkçe',soru_sayisi='10',dogru='9',yanlis='3',yanlis_goturme='3')
        self.assertEqual(self.teacher_client.post('/sonuclar',data=payload).status_code,200)
        self.assertFalse(any(r['ad']==payload['ad'] for r in d.lgs_denemeler(self.oid,200)))
        other=next(r for r in d.tum_ogretmenler() if r['id']!=self.teacher['id'] and r['yetki']=='tam')
        saved=d.lgs_deneme_ekle(self.oid,'Başka öğretmenin testi','2026-10-01',[dict(ders='Türkçe',dogru=8,yanlis=1,bos=1,soru_sayisi=10)],ogretmen_id=other['id'],tur='ders')
        self.assertEqual(self.teacher_client.get('/sonuclar',query_string={'ogrenci':self.oid,'duzenle':saved['id']}).status_code,403)

    def test_school_branch_result_outside_lgs_courses(self):
        payload=dict(ogrenci=self.oid,tur='ders',ad='Bilişim testi',tarih='2026-10-01',ders='Bilişim Teknolojileri',soru_sayisi='25',dogru='18',yanlis='2',yanlis_goturme='0')
        self.assertEqual(self.teacher_client.post('/sonuclar',data=payload).status_code,302)
        record=next(r for r in d.lgs_denemeler(self.oid,200) if r['ad']==payload['ad'])
        self.assertEqual(record['dersler'][0]['soru_sayisi'],25)
        self.assertEqual(record['dersler'][0]['bos'],5)
        self.assertIn('Bilişim Teknolojileri',self.parent.get('/veli/sonuclar').get_data(as_text=True))

    def test_class_course_exam_writes_only_filled_scores(self):
        con=d._conn()
        students=[dict(r) for r in con.execute("SELECT o.id,o.ad_soyad FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' ORDER BY o.id LIMIT 3")]
        con.close()
        self.assertGreaterEqual(len(students),3)
        a,b,c=students
        payload={'islem':'sinif_ders','sinif_id':self.sid,'ad':'Sınıf matematik denemesi','tarih':'2026-10-13','ders':'Matematik','soru_sayisi':'20','yanlis_goturme':'3',f'dogru_{a["id"]}':'12',f'yanlis_{a["id"]}':'3',f'dogru_{b["id"]}':'0',f'yanlis_{b["id"]}':'0'}
        page=self.teacher_client.post('/sonuclar',data=payload,follow_redirects=True).get_data(as_text=True)
        self.assertIn('2 öğrenciye yazıldı',page)
        rec=next(r for r in d.lgs_denemeler(a['id'],20) if r['ad']==payload['ad'])
        self.assertEqual((rec['dersler'][0]['dogru'],rec['dersler'][0]['yanlis'],rec['dersler'][0]['bos'],rec['dersler'][0]['net']),(12,3,5,11))
        bos=next(r for r in d.lgs_denemeler(b['id'],20) if r['ad']==payload['ad'])
        self.assertEqual(bos['dersler'][0]['bos'],20)
        self.assertFalse(any(r['ad']==payload['ad'] for r in d.lgs_denemeler(c['id'],20)))
        bad=dict(payload,ad='Geçersiz sınıf denemesi')
        bad[f'dogru_{a["id"]}']='19'
        bad[f'yanlis_{a["id"]}']='5'
        self.assertEqual(self.teacher_client.post('/sonuclar',data=bad).status_code,200)
        self.assertFalse(any(r['ad']=='Geçersiz sınıf denemesi' for r in d.lgs_denemeler(a['id'],20)))
        liste=self.teacher_client.get('/sonuclar',query_string={'sinif':self.sid}).get_data(as_text=True)
        self.assertIn(f'name="dogru_{a["id"]}"',liste)
        birey=self.teacher_client.get('/sonuclar',query_string={'ogrenci':self.oid}).get_data(as_text=True)
        self.assertIn('Bireysel sonuç',birey)
        self.assertIn('name="dogru"',birey)

    def test_class_exam_with_answer_key_shows_each_question(self):
        others=[s for s in d.sinif_ogrencileri(self.sid) if s['id']!=self.oid][:2]
        self.assertEqual(len(others),2)
        b,c=others
        payload={'islem':'sinif_ders','sinif_id':self.sid,'ad':'Cevaplı yaprak','tarih':'2026-10-14','ders':'Matematik',
                 'soru_sayisi':'20','yanlis_goturme':'0','anahtar':'abcde',
                 f'cevap_{self.oid}':'AB-DA',f'cevap_{b["id"]}':'ba',f'dogru_{c["id"]}':'2',f'yanlis_{c["id"]}':'1'}
        bad=dict(payload,ad='Hatalı cevaplı yaprak',**{f'cevap_{b["id"]}':'AB?'})
        self.assertIn('tanınmadı',self.teacher_client.post('/sonuclar',data=bad).get_data(as_text=True))
        self.assertFalse(any(r['ad']=='Hatalı cevaplı yaprak' for r in d.lgs_denemeler(self.oid,200)))
        self.assertIn('3 öğrenciye yazıldı',self.teacher_client.post('/sonuclar',data=payload,follow_redirects=True).get_data(as_text=True))
        ben=next(r for r in d.lgs_denemeler(self.oid,200) if r['ad']=='Cevaplı yaprak')['dersler'][0]
        self.assertEqual((ben['soru_sayisi'],ben['dogru'],ben['yanlis'],ben['bos']),(5,3,1,1))
        self.assertEqual([s['durum'] for s in ben['sorular']],['dogru','dogru','bos','dogru','yanlis'])
        self.assertEqual(ben['sorular'][4]['verilen'],'A')
        diger=next(r for r in d.lgs_denemeler(b['id'],200) if r['ad']=='Cevaplı yaprak')['dersler'][0]
        self.assertEqual((diger['dogru'],diger['yanlis'],diger['bos']),(0,2,3))
        sayisal=next(r for r in d.lgs_denemeler(c['id'],200) if r['ad']=='Cevaplı yaprak')['dersler'][0]
        self.assertEqual((sayisal['soru_sayisi'],sayisal['sorular']),(5,[]))
        sorgu={'ad':'Cevaplı yaprak','tarih':'2026-10-14','tur':'ders'}
        sayfa=self.teacher_client.get('/lgs/test-analiz',query_string=sorgu).get_data(as_text=True)
        self.assertIn('Öğrenci öğrenci: hangi soruda ne yaptı',sayfa)
        self.assertIn('cevapları girilen 2 öğrenciden',sayfa)
        self.assertIn('yanlış: A işaretledi, doğrusu E',sayfa)
        self.assertIn(b['ad_soyad'],sayfa)
        self.assertNotIn('Ders başına ortalama',sayfa)
        veli=self.parent.get('/veli/lgs',query_string={**sorgu,'bolum':'deneme'}).get_data(as_text=True)
        self.assertIn('Hangi soruda ne yaptın',veli)
        self.assertNotIn(b['ad_soyad'],veli)
        birey=self.teacher_client.get('/sonuclar',query_string={'ogrenci':self.oid}).get_data(as_text=True)
        self.assertIn('class="q-strip"',birey)
        liste=self.teacher_client.get('/sonuclar',query_string={'sinif':self.sid}).get_data(as_text=True)
        self.assertNotIn('Cevap anahtarı',liste)
        self.assertNotIn('data-key-slots',liste)

    def test_exam_analysis_stays_under_lgs_and_skips_leaf_tests(self):
        d.lgs_deneme_ekle(self.oid, 'Yaprak karışmasın', '2026-10-14', [dict(ders='Matematik', dogru=5, yanlis=1, bos=4)], ogretmen_id=self.teacher['id'], tur='ders')
        d.lgs_deneme_ekle(self.oid, 'Gerçek deneme', '2026-10-14', [dict(ders='Matematik', dogru=8, yanlis=2, bos=10)], ogretmen_id=self.teacher['id'], tur='deneme')
        sayfa = self.teacher_client.get('/deneme-analiz').get_data(as_text=True)
        self.assertIn('Gerçek deneme', sayfa)
        self.assertNotIn('Yaprak karışmasın', sayfa)
        menu = self.teacher_client.get('/lgs').get_data(as_text=True)
        self.assertLess(menu.index('</span>LGS</a>'), menu.index('Deneme analizi'))
        self.assertLess(menu.index('Deneme analizi'), menu.index('>Raporlar<'))
        self.assertIn('Test ve sınıf analizi', menu[menu.index('</span>LGS</a>'):menu.index('>Raporlar<')])
        ogr = self.teacher_client.get('/lgs', query_string={'ogrenci': self.oid}).get_data(as_text=True)
        self.assertNotIn('Ders ve deneme sonucu', ogr)
        evde = self.teacher_client.get('/lgs', query_string={'ekran': 'evde'}).get_data(as_text=True)
        self.assertIn('data-key-slots', evde)
        self.assertNotIn('textarea name="anahtar"', evde)
        soru = self.parent.get('/veli/lgs', query_string={'bolum': 'soru'}).get_data(as_text=True).split('<main', 1)[-1]
        self.assertIn('<h1>Sorular</h1>', soru)
        self.assertNotIn('<h1>Analiz</h1>', soru)
        self.assertNotIn('grid-cols-3', soru)
        analiz = self.parent.get('/veli/lgs', query_string={'bolum': 'deneme'}).get_data(as_text=True).split('<main', 1)[-1]
        self.assertIn('<h1>Analiz</h1>', analiz)
        self.assertNotIn('hedefin duruyor', analiz)
        self.assertNotIn('Ders ve deneme sonuçlarına geç', analiz)
        self.assertNotIn('Sorular ve optik', analiz)
        sonuc = self.parent.get('/veli/lgs', query_string={'bolum': 'sonuc'}).get_data(as_text=True).split('<main', 1)[-1]
        self.assertIn('<h1>Sonuçlar</h1>', sonuc)
        self.assertNotIn('Sorular ve optik', sonuc)

    def test_only_two_admins_can_delete_entered_exams(self):
        d.lgs_deneme_ekle(self.oid, 'Silinecek yönetici denemesi', '2026-10-15', [dict(ders='Matematik', dogru=4, yanlis=1, bos=5)], ogretmen_id=self.teacher['id'], tur='deneme')
        yasak = {'adem akgül', 'metehan cücen'}
        yabanci = None
        for aday in d.tum_ogretmenler():
            if aday['ad_soyad'].casefold() in yasak or aday['yetki'] != 'tam':
                continue
            deneme = w.app.test_client()
            with deneme.session_transaction() as s:
                s.update(ogretmen_id=aday['id'], ogretmen_adi=aday['ad_soyad'], ogretmen_yetki='tam')
            if deneme.get('/dashboard').status_code == 200:
                yabanci = deneme
                break
        self.assertIsNotNone(yabanci)
        self.assertEqual(yabanci.get('/yonetim/sinavlar').status_code, 403)
        admin = next(r for r in d.tum_ogretmenler() if r['ad_soyad'] == 'METEHAN CÜCEN')
        client = w.app.test_client()
        with client.session_transaction() as s:
            s.update(ogretmen_id=admin['id'], ogretmen_adi=admin['ad_soyad'], ogretmen_yetki='tam')
        sayfa = client.get('/yonetim/sinavlar').get_data(as_text=True)
        self.assertIn('Silinecek yönetici denemesi', sayfa)
        self.assertIn('Yönetici paneli', sayfa)
        client.post('/yonetim/sinavlar', data={'islem': 'deneme', 'ad': 'Silinecek yönetici denemesi', 'tarih': '2026-10-15', 'tur': 'deneme', 'sinif': '8/A'})
        self.assertFalse(any(r['ad'] == 'Silinecek yönetici denemesi' for r in d.lgs_denemeler(self.oid, 50)))
        d.lgs_deneme_ekle(self.oid, 'Toplu sekiz', '2026-10-15', [dict(ders='Türkçe', dogru=3, yanlis=1, bos=6)], ogretmen_id=self.teacher['id'], tur='ders')
        client.post('/yonetim/sinavlar', data={'islem': 'sekiz', 'onay': 'SIL'})
        self.assertFalse(any(r['ad'] == 'Toplu sekiz' for r in d.lgs_denemeler(self.oid, 50)))

    def test_teacher_can_delete_and_restore_exam_results(self):
        students=d.sinif_ogrencileri(self.sid)[:2]
        self.assertGreaterEqual(len(students),2)
        a,b=students[0],students[1]
        payload={'islem':'sinif_ders','sinif_id':self.sid,'ad':'Silinecek sınıf denemesi','tarih':'2026-10-13','ders':'Türkçe','soru_sayisi':'10','yanlis_goturme':'0',f'dogru_{a["id"]}':'8',f'yanlis_{a["id"]}':'1',f'dogru_{b["id"]}':'4',f'yanlis_{b["id"]}':'2'}
        self.teacher_client.post('/sonuclar',data=payload)
        liste=self.teacher_client.get('/sonuclar',query_string={'sinif':self.sid}).get_data(as_text=True)
        self.assertIn('sinif_ders_sil',liste)
        self.assertIn('Silinecek sınıf denemesi',liste)
        deleted=self.teacher_client.post('/sonuclar',data={'islem':'sinif_ders_sil','sinif_id':self.sid,'ad':payload['ad'],'tarih':payload['tarih'],'tur':'ders'},follow_redirects=True).get_data(as_text=True)
        self.assertIn('2 öğrencinin kaydı silindi',deleted)
        self.assertFalse(any(r['ad']==payload['ad'] for r in d.lgs_denemeler(a['id'],30)))
        self.teacher_client.post('/islem-gecmisi/'+self._latest_action()+'/geri-al')
        restored=next(r for r in d.lgs_denemeler(a['id'],30) if r['ad']==payload['ad'])
        self.assertEqual((restored['dersler'][0]['dogru'],restored['dersler'][0]['yanlis'],restored['dersler'][0]['bos']),(8,1,1))
        self.assertTrue(any(r['ad']==payload['ad'] for r in d.lgs_denemeler(b['id'],30)))
        self.teacher_client.post('/sonuclar',data={'ogrenci':self.oid,'tur':'ders','ad':'Tek silinecek','tarih':'2026-10-13','ders':'Matematik','soru_sayisi':'10','dogru':'7','yanlis':'1','yanlis_goturme':'0'})
        rec=next(r for r in d.lgs_denemeler(self.oid,30) if r['ad']=='Tek silinecek')
        card=self.teacher_client.get('/sonuclar',query_string={'ogrenci':self.oid}).get_data(as_text=True)
        self.assertIn(f'name="deneme" value="{rec["id"]}"',card)
        self.teacher_client.post('/sonuclar',data={'ogrenci':self.oid,'islem':'sil','deneme':rec['id']})
        self.assertFalse(any(r['ad']=='Tek silinecek' for r in d.lgs_denemeler(self.oid,30)))
        self.teacher_client.post('/islem-gecmisi/'+self._latest_action()+'/geri-al')
        back=next(r for r in d.lgs_denemeler(self.oid,30) if r['ad']=='Tek silinecek')
        self.assertEqual((back['dersler'][0]['dogru'],back['dersler'][0]['yanlis']),(7,1))
        other=next(r for r in d.tum_ogretmenler() if r['id']!=self.teacher['id'] and r['yetki']=='tam')
        client=w.app.test_client()
        with client.session_transaction() as s:s.update(ogretmen_id=other['id'],ogretmen_adi=other['ad_soyad'],ogretmen_yetki='tam')
        self.assertEqual(client.post('/sonuclar',data={'ogrenci':self.oid,'islem':'sil','deneme':back['id']}).status_code,403)

    def test_undo_blocks_foreign_actor_and_intervening_change(self):
        con=d._conn()
        student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='6/B' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        payload=dict(sinif_id=student['sinif_id'],ogrenci_id=student['id'],hafta=self.week,alan='odev_not',deger='İlk not')
        self.teacher_client.post('/haftalik-takip/metin',json=payload)
        action=self._latest_action()
        other=next(r for r in d.tum_ogretmenler() if r['id']!=self.teacher['id'] and r['yetki']=='tam')
        client=w.app.test_client()
        with client.session_transaction() as s:s.update(ogretmen_id=other['id'],ogretmen_adi=other['ad_soyad'],ogretmen_yetki='tam')
        self.assertEqual(client.post('/islem-gecmisi/'+action+'/geri-al').status_code,403)
        client.post('/haftalik-takip/metin',json={**payload,'deger':'Son not'})
        response=self.teacher_client.post('/islem-gecmisi/'+action+'/geri-al',follow_redirects=True)
        self.assertIn('daha sonra başka bir değişiklik',response.get_data(as_text=True))
        self.assertEqual(d.haftalik_takip_sinif(student['sinif_id'],self.week)[student['id']]['odev_not'],'Son not')

    def test_book_approval_undo_restores_points_and_treasure(self):
        con=d._conn()
        student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='5/B' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        oid,sid=student['id'],student['sinif_id']
        book='Bana Derler Küp Cadısı'
        d.haftalik_takip_metin(sid,oid,self.week,'kitap_adi',book,self.teacher['id'])
        p=w.app.test_client()
        with p.session_transaction() as s:s['veli_ogrenci_id']=oid
        p.post('/veli/kitap-okuma/kaydet',data={'kitap_adi':book,'hafta':self.week})
        entry=d.kitap_okuma_ogrenci_gecmis(oid)[0]
        con=d._conn()
        before=con.execute('SELECT * FROM gelisim_puan WHERE ogrenci_id=?',(oid,)).fetchone()
        before=dict(before) if before else None
        con.close()
        self.teacher_client.post('/ogretmen/kitap-okuma/'+str(entry['id'])+'/onayla',data={})
        action=self._latest_action()
        self.teacher_client.post('/islem-gecmisi/'+action+'/geri-al')
        self.assertEqual(d.kitap_okuma_ogrenci_gecmis(oid)[0]['durum'],'onay_bekliyor')
        con=d._conn()
        after=con.execute('SELECT * FROM gelisim_puan WHERE ogrenci_id=?',(oid,)).fetchone()
        after=dict(after) if after else None
        con.close()
        self.assertEqual(before,after)
        self.assertIn('SÜRPRİZ ROZET',p.get('/veli').get_data(as_text=True))

    def test_institution_replacement_undo_restores_deleted_results(self):
        from unittest.mock import patch
        teacher=next(r for r in d.tum_ogretmenler() if r['ad_soyad']=='ADEM AKGÜL')
        client=w.app.test_client()
        with client.session_transaction() as s:s.update(ogretmen_id=teacher['id'],ogretmen_adi=teacher['ad_soyad'],ogretmen_yetki='tam')
        title='Kurum geri alma testi'
        earlier=d.lgs_deneme_ekle(self.oid,title,'2026-09-25',[dict(ders='Matematik',dogru=10,yanlis=5,bos=5)])
        original=d.lgs_deneme_ekle(self.oid,title,'2026-10-01',[dict(ders='Matematik',dogru=12,yanlis=5,bos=3)])
        before=next(r for r in d.lgs_denemeler(self.oid,200) if r['id']==original['id'])
        parsed={'ad':title,'tarih':'2026-10-01','satirlar':[{}]}
        matched={'eslesen':[{'ogrenci_id':self.oid,'dersler':[dict(ders='Matematik',dogru=16,yanlis=2,bos=2)],'net':15.33}], 'kalan':[]}
        with patch('deneme_kurum.kurum_pdf_oku',return_value=parsed),patch('deneme_kurum.kurum_ogrenci_esle',return_value=matched):
            self.assertEqual(client.post('/lgs/kurum-pdf',data={'pdf':(BytesIO(b'%PDF-fixture'),'fixture.pdf')}).status_code,302)
        con=d._conn()
        action=con.execute('SELECT id FROM ogretmen_islem WHERE ogretmen_id=? ORDER BY rowid DESC LIMIT 1',(teacher['id'],)).fetchone()[0]
        con.close()
        self.assertNotIn(original['id'],[r['id'] for r in d.lgs_denemeler(self.oid,200)])
        self.assertIn(earlier['id'],[r['id'] for r in d.lgs_denemeler(self.oid,200)])
        client.post('/islem-gecmisi/'+action+'/geri-al')
        after=next(r for r in d.lgs_denemeler(self.oid,200) if r['id']==original['id'])
        self.assertEqual(before,after)
        self.assertEqual(sum(r['ad']==title for r in d.lgs_denemeler(self.oid,200)),2)

    def test_edesıs_lgs_listesi_kurum_formundan_yazilir(self):
        pdf = Path(r'C:\Users\METE\OneDrive\Desktop\ERENLER CUMHURİYET VİP LGS-1.pdf')
        if not pdf.exists():
            self.skipTest('masaüstü listesi yok')
        teacher = next(r for r in d.tum_ogretmenler() if r['ad_soyad'] == 'ADEM AKGÜL')
        client = w.app.test_client()
        with client.session_transaction() as s:
            s.update(ogretmen_id=teacher['id'], ogretmen_adi=teacher['ad_soyad'], ogretmen_yetki='tam')
        response = client.post(
            '/lgs/kurum-pdf',
            data={'pdf': (BytesIO(pdf.read_bytes()), pdf.name)},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)
        self.assertIn('VİP LGS-1: 25 öğrenci yazıldı', html)
        self.assertIn('AYŞE EBRARK ULA', html)
        con = d._conn()
        oid = con.execute("SELECT id FROM ogrenciler WHERE ad_soyad='YAĞMUR NİSA KOCA'").fetchone()[0]
        con.close()
        deneme = next(r for r in d.lgs_denemeler(oid, 20) if r['ad'] == 'VİP LGS-1')
        self.assertEqual(deneme['tarih'], '2026-10-04')
        self.assertEqual(deneme['puan'], 449.5)
        turkce = next(ders for ders in deneme['dersler'] if ders['ders'] == 'Türkçe')
        inkılap = next(ders for ders in deneme['dersler'] if ders['ders'] == 'T.C. İnkılap Tarihi')
        self.assertEqual((turkce['dogru'], turkce['yanlis'], turkce['net']), (16, 4, 14.67))
        self.assertEqual((inkılap['dogru'], inkılap['net']), (10, 10.0))

    def test_published_homework_edit_and_undo(self):
        import re
        self.teacher_client.post('/odev/ekle',data=dict(sinif_id=self.sid,baslik='Ödev düzenleme testi',aciklama='İlk açıklama',ders='Matematik',son_tarih='2026-10-02'))
        homework=next(r for r in d.sinif_odevleri(self.sid) if r['baslik']=='Ödev düzenleme testi')
        html=self.teacher_client.get('/odev/'+str(homework['id'])+'/duzenle').get_data(as_text=True)
        version=unescape(re.search(r'name="surum" value="([^"]+)"',html).group(1))
        self.teacher_client.post('/odev/'+str(homework['id'])+'/duzenle',data=dict(surum=version,baslik='Düzeltilmiş ödev',aciklama='Yeni açıklama',ders='Matematik',son_tarih='2026-10-03'))
        self.assertEqual(d.odev_detay(homework['id'])['baslik'],'Düzeltilmiş ödev')
        action=self._latest_action()
        self.teacher_client.post('/islem-gecmisi/'+action+'/geri-al')
        restored=d.odev_detay(homework['id'])
        self.assertEqual(restored['baslik'],homework['baslik'])
        self.assertEqual(restored['aciklama'],'İlk açıklama')

    def test_tracking_malformed_request(self):
        for url in ['/haftalik-takip/isaret','/haftalik-takip/metin','/haftalik-takip/toplu']:
            for payload in [{'sinif_id':'abc'},['wrong shape']]:
                with self.subTest(url=url,payload=payload):
                    self.assertEqual(self.teacher_client.post(url,json=payload).status_code,400)

    def test_tracking_invalid_week(self):
        r=self.teacher_client.post('/haftalik-takip/isaret',json=dict(sinif_id=self.sid,ogrenci_id=self.oid,hafta='not-a-date',alan='odev_durum',deger='tam'))
        self.assertEqual(r.status_code,400)

    def test_parent_menu_has_reading_entry(self):
        html=self.parent.get('/veli').get_data(as_text=True)
        self.assertNotIn('data-parent-nav="hafta"', html)
        self.assertIn('Sorular ve optik', html)
        self.assertIn('bolum=sonuc', html)
        self.assertIn('Ders ve deneme sonuçları', html)
        self.assertLess(html.find('>LGS<'), html.find('Ders ve deneme sonuçları'))
        con=d._conn()
        student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='5/A' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        parent=w.app.test_client()
        with parent.session_transaction() as s:s['veli_ogrenci_id']=student['id']
        bes=parent.get('/veli').get_data(as_text=True)
        self.assertIn('/veli/kitap-okuma', bes)
        self.assertIn('/veli/sonuclar', bes)
        self.assertNotIn('bolum=sonuc', bes)

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
        saved=d.lgs_deneme_ekle(self.oid,'Yuvarlama testi','2026-10-01',dersler)
        self.assertTrue(saved['ok'])
        self.assertEqual(next(r for r in d.lgs_denemeler(self.oid,200) if r['id']==saved['id'])['net'],59)
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
        con=d._conn()
        student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='5/A' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        oid,sid=student['id'],student['sinif_id']
        d.haftalik_takip_metin(sid,oid,self.week,'kitap_adi','Test kitabı',self.teacher['id'])
        parent=w.app.test_client()
        with parent.session_transaction() as s:s['veli_ogrenci_id']=oid
        r=parent.post('/veli/kitap-okuma/kaydet',data={'kitap_adi':'Test kitabı','hafta':self.week},follow_redirects=True)
        self.assertTrue('Kitabı bitirdiğiniz öğretmeninize bildirildi' in r.get_data(as_text=True))
        entry=d.kitap_okuma_ogrenci_gecmis(oid)[0]
        r=self.teacher_client.post('/ogretmen/kitap-okuma/'+str(entry['id'])+'/onayla',data={})
        self.assertEqual(r.status_code,302)
        self.assertEqual(d.kitap_okuma_ogrenci_gecmis(oid)[0]['durum'],'onaylandi')
        self.assertEqual(d.haftalik_takip_sinif(sid,self.week)[oid]['kitap_okuma'],'okudu')

    def test_reading_completion_is_assigned_and_deduplicated(self):
        con=d._conn()
        student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='5/B' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        oid,sid=student['id'],student['sinif_id']
        book='Tek düğme test kitabı'
        d.haftalik_takip_metin(sid,oid,self.week,'kitap_adi',book,self.teacher['id'])
        parent=w.app.test_client()
        with parent.session_transaction() as s:s['veli_ogrenci_id']=oid
        html=parent.get('/veli/kitap-okuma').get_data(as_text=True)
        self.assertNotIn('name="sayfa_sayisi"',html)
        self.assertNotIn('XP',html)
        self.assertIn('Kitabı bitirdik',html)
        payload={'kitap_adi':book,'hafta':self.week,'sayfa_sayisi':'9999','saat':'999','xp':'999'}
        self.assertEqual(parent.post('/veli/kitap-okuma/kaydet',data=payload).status_code,302)
        parent.post('/veli/kitap-okuma/kaydet',data=payload)
        entries=[k for k in d.kitap_okuma_ogrenci_gecmis(oid) if k['kitap_adi']==book]
        self.assertEqual(len(entries),1)
        self.assertEqual((entries[0]['sayfa_sayisi'],entries[0]['saat'],entries[0]['xp']),(0,0,0))
        self.assertEqual(parent.post('/veli/kitap-okuma/kaydet',data={**payload,'kitap_adi':'Verilmemiş kitap'}).status_code,400)
        self.assertEqual(parent.post('/veli/kitap-okuma/kaydet',data={**payload,'hafta':'2000-01-03'}).status_code,400)

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
        sayfa = self.parent.get('/veli/lgs').get_data(as_text=True).split('<main', 1)[-1]
        self.assertIn('<h1>Sorular</h1>', sayfa)
        self.assertNotIn('>Özet<', sayfa)
        self.assertNotIn('>Program<', sayfa)

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
        con=d._conn()
        student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='7/A' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lN8AAAAASUVORK5CYII=')
        payload={'sinif_id':student['sinif_id'],'ogrenci_id':student['id'],'hafta':self.week}
        r=self.teacher_client.post('/haftalik-takip/foto',data={**payload,'foto':(BytesIO(png),'test.png')},follow_redirects=True)
        self.assertTrue('Ödev fotoğrafı kaydedildi' in r.get_data(as_text=True))
        parent=w.app.test_client()
        with parent.session_transaction() as s:s['veli_ogrenci_id']=student['id']
        r=parent.get('/veli/odev-foto')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data,png)
        r.close()
        r=self.teacher_client.post('/haftalik-takip/foto',data={**payload,'foto':(BytesIO(b'not an image'),'test.png')},follow_redirects=True)
        self.assertTrue('Dosya geçerli bir' in r.get_data(as_text=True))
        self.assertEqual(self.teacher_client.post('/haftalik-takip/foto',data={**payload,'hafta':'../invalid'}).status_code,400)

    def test_lgs_optik_veli_bitirince_ogretmen_listesinde(self):
        import lgs_optik
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
        response = self.teacher_client.post(
            '/lgs',
            data={
                'islem': 'optik_ekle',
                'ad': 'Optik deneme',
                'tarih': '2026-10-08',
                'anahtar': 'A B C D',
                'pdf': (BytesIO(pdf), 'soru.pdf'),
            },
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)
        self.assertIn('4 soruluk deneme açıldı', html)
        self.assertIn('Henüz optik bitirilmedi', html)
        sinav = next(s for s in lgs_optik.sinavlari_listele() if s['ad'] == 'Optik deneme')
        soru = self.parent.get('/veli/lgs?bolum=soru&sinav=' + str(sinav['id']))
        sayfa = soru.get_data(as_text=True)
        self.assertIn('name="c0"', sayfa)
        self.assertNotIn('>Defter<', sayfa)
        pdf_yanit = self.parent.get('/lgs/optik/%s/pdf' % sinav['id'])
        self.assertEqual(pdf_yanit.data[:5], b'%PDF-')
        pdf_yanit.close()
        bitirdi = self.parent.post('/veli/lgs', data={
            'islem': 'optik_bitir', 'bolum': 'soru', 'sinav_id': sinav['id'],
            'c0': 'A', 'c1': 'A', 'c2': 'C', 'c3': '',
        }, follow_redirects=True)
        sonuc = bitirdi.get_data(as_text=True)
        self.assertIn('Net 1.67', sonuc)
        self.assertIn('Doğru 2', sonuc)
        self.assertIn('is-yanlis', sonuc)
        self.assertIn('is-bos', sonuc)
        self.assertIn('2. soru yanlış', sonuc)
        self.assertIn('4. soru boş', sonuc)
        self.assertIn('Yapılan testler', sonuc)
        self.assertLess(sonuc.index('Yapılan testler'), sonuc.index('Optik deneme'))
        analiz = self.parent.get('/veli/lgs?bolum=deneme').get_data(as_text=True)
        self.assertIn('Soru analizi', analiz)
        self.assertIn('Optik deneme', analiz)
        self.assertIn('2. soru yanlış', analiz)
        tekrar = self.parent.post('/veli/lgs', data={
            'islem': 'optik_bitir', 'sinav_id': sinav['id'], 'c0': 'A',
        }, follow_redirects=True)
        self.assertIn('daha önce bitirilmiş', tekrar.get_data(as_text=True))
        pano = self.teacher_client.get('/lgs', query_string={'ekran': 'evde'}).get_data(as_text=True)
        self.assertIn(self.student['ad_soyad'], pano)
        self.assertIn('1.67', pano)
        takip = self.teacher_client.get('/haftalik-takip?sinif=' + str(self.sid)).get_data(as_text=True)
        self.assertIn('LGS soru optiğinde', takip)
        self.assertNotIn('tracking-table', takip)

    def test_leaf_and_exam_charts_on_parent_analysis(self):
        import lgs_optik
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
        self.teacher_client.post('/lgs', data={
            'islem': 'optik_ekle', 'ad': 'Yaprak üslü', 'tarih': '2026-10-13', 'tur': 'yaprak',
            'ders': 'Matematik', 'sinif_id': str(self.sid),
            'anahtar': 'AB', 'pdf': (BytesIO(pdf), 'yaprak.pdf'),
        }, content_type='multipart/form-data')
        sinav = next(s for s in lgs_optik.sinavlari_listele() if s['ad'] == 'Yaprak üslü')
        self.assertEqual(sinav['tur'], 'yaprak')
        self.parent.post('/veli/lgs', data={
            'islem': 'optik_bitir', 'bolum': 'soru', 'sinav_id': sinav['id'], 'c0': 'A', 'c1': '',
        })
        self.teacher_client.post('/sonuclar', data={
            'ogrenci': self.oid, 'tur': 'ders', 'ad': 'Yaprak matematik', 'tarih': '2026-10-12',
            'ders': 'Matematik', 'soru_sayisi': '10', 'dogru': '6', 'yanlis': '2', 'yanlis_goturme': '0',
        })
        self.teacher_client.post('/sonuclar', data={
            'ogrenci': self.oid, 'tur': 'deneme', 'ad': 'Ekim denemesi', 'tarih': '2026-10-11',
            'ders': ['Türkçe', 'Matematik'], 'soru_sayisi': ['10', '10'],
            'dogru': ['7', '5'], 'yanlis': ['1', '3'], 'yanlis_goturme': ['3', '3'],
        })
        sayfa = self.parent.get('/veli/lgs?bolum=deneme').get_data(as_text=True)
        self.assertIn('Yaprak testler', sayfa)
        self.assertIn('Yaprak üslü', sayfa)
        self.assertIn('2. soru boş', sayfa)
        self.assertIn('Yaprak matematik', sayfa)
        self.assertIn('Ekim denemesi', sayfa)
        self.assertIn('class="soru-cubuk"', sayfa)
        self.assertIn('Gelişim grafiği', sayfa)
        self.assertIn('id="yaprak-net"', sayfa)
        self.assertIn('<summary>Yaprak testler</summary>', sayfa)
        kart = self.parent.get('/veli/sonuclar').get_data(as_text=True)
        self.assertIn('Yaprak matematik', kart)
        self.assertIn('class="soru-cubuk"', kart)
        self.assertIn('Ekim denemesi', kart)

    def test_leaf_tests_list_by_class_and_course(self):
        import lgs_optik
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
        eksik = self.teacher_client.post('/lgs', data={
            'islem': 'optik_ekle', 'ad': 'Eksik yaprak', 'tarih': '2026-10-01', 'tur': 'yaprak',
            'anahtar': 'AB', 'pdf': (BytesIO(pdf), 'eksik.pdf'),
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn('sınıf ve ders seçin', eksik.get_data(as_text=True))
        self.assertFalse(any(s['ad'] == 'Eksik yaprak' for s in lgs_optik.sinavlari_listele()))
        con = d._conn()
        diger_sinif = con.execute("SELECT id FROM siniflar WHERE sinif_adi='8/B'").fetchone()[0]
        con.close()

        def yukle(ad, tarih, ders, sinif_id):
            self.teacher_client.post('/lgs', data={
                'islem': 'optik_ekle', 'ad': ad, 'tarih': tarih, 'tur': 'yaprak',
                'ders': ders, 'sinif_id': str(sinif_id), 'anahtar': 'AB',
                'pdf': (BytesIO(pdf), 'yaprak.pdf'),
            }, content_type='multipart/form-data', follow_redirects=True)

        yukle('Eski Türkçe', '2026-09-01', 'Türkçe', self.sid)
        yukle('Yeni Türkçe', '2026-10-12', 'Türkçe', self.sid)
        yukle('Sınıf matematiği', '2026-10-10', 'Matematik', self.sid)
        yukle('Diğer sınıf Türkçe', '2026-10-11', 'Türkçe', diger_sinif)
        ana = self.teacher_client.get('/lgs').get_data(as_text=True)
        self.assertNotIn('bg-white p-4" open', ana)
        self.assertNotIn('Koçluk çizelgesi', ana)
        self.assertNotIn('Yaprak testler', ana)
        self.assertIn('Evde Soru Testleri', ana)
        self.assertIn('Okulda Yaprak Test', ana)
        evde = self.teacher_client.get('/lgs', query_string={'ekran': 'evde'}).get_data(as_text=True)
        self.assertIn('Soruları gönder', evde)
        self.assertNotIn('Yaprak testler', evde)
        self.assertNotIn('Yeni Türkçe', evde)
        self.assertNotIn('8/A ·', evde)
        students = d.sinif_ogrencileri(self.sid)[:1]
        self.teacher_client.post('/sonuclar', data={
            'islem': 'sinif_ders', 'sinif_id': self.sid, 'ad': 'Ekim Türkçe yaprağı', 'tarih': '2026-10-02',
            'ders': 'Türkçe', 'soru_sayisi': '10', 'yanlis_goturme': '0',
            f'dogru_{students[0]["id"]}': '6', f'yanlis_{students[0]["id"]}': '1',
        }, follow_redirects=True)
        self.teacher_client.post('/sonuclar', data={
            'islem': 'sinif_ders', 'sinif_id': self.sid, 'ad': 'Ekim matematik yaprağı', 'tarih': '2026-10-03',
            'ders': 'Matematik', 'soru_sayisi': '10', 'yanlis_goturme': '0',
            f'dogru_{students[0]["id"]}': '7', f'yanlis_{students[0]["id"]}': '1',
        }, follow_redirects=True)
        liste = self.teacher_client.get('/sonuclar', query_string={'sinif': self.sid}).get_data(as_text=True)
        self.assertIn('data-yaprak="Türkçe"', liste)
        self.assertIn('data-yaprak="Matematik"', liste)
        self.assertLess(liste.index('Ekim matematik yaprağı'), liste.index('Ekim Türkçe yaprağı'))
        sinav = next(s for s in lgs_optik.sinavlari_listele() if s['ad'] == 'Yeni Türkçe')
        analiz = self.teacher_client.get('/lgs/test-analiz', query_string={'sinif': '8/A', 'ders': 'Türkçe', 'sinav': sinav['id']}).get_data(as_text=True)
        self.assertIn('Yeni Türkçe', analiz)
        self.assertIn('Eski Türkçe', analiz)
        self.assertNotIn('Sınıf matematiği', analiz)

    def test_teacher_class_analysis_charts_questions_and_scores(self):
        import lgs_optik
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
        self.teacher_client.post('/lgs', data={
            'islem': 'optik_ekle', 'ad': 'Sınıf analiz denemesi', 'tarih': '2026-10-13', 'tur': 'deneme',
            'anahtar': 'ABCD', 'pdf': (BytesIO(pdf), 'sinif.pdf'),
        }, content_type='multipart/form-data')
        sinav = next(s for s in lgs_optik.sinavlari_listele() if s['ad'] == 'Sınıf analiz denemesi')
        self.parent.post('/veli/lgs', data={
            'islem': 'optik_bitir', 'bolum': 'soru', 'sinav_id': sinav['id'],
            'c0': 'A', 'c1': 'A', 'c2': 'C', 'c3': '',
        })
        con = d._conn()
        diger = dict(con.execute("SELECT o.id, o.ad_soyad FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/B' ORDER BY o.id LIMIT 1").fetchone())
        con.close()
        lgs_optik.sonuc_kaydet(sinav['id'], diger['id'], ['A', 'A', 'A', 'A'])
        sayfa = self.teacher_client.get('/lgs/test-analiz', query_string={'sinav': sinav['id']}).get_data(as_text=True)
        self.assertIn('Soru soru başarı', sayfa)
        self.assertIn('En çok zorlayan sorular', sayfa)
        self.assertIn('2. soru', sayfa)
        self.assertIn('en çok işaret A', sayfa)
        self.assertIn('8/A', sayfa)
        self.assertIn('8/B', sayfa)
        self.assertIn('id="soru-dyb"', sayfa)
        self.assertIn('id="sinif-net"', sayfa)
        sinif = self.teacher_client.get('/lgs/test-analiz', query_string={'sinav': sinav['id'], 'sinif': '8/A'}).get_data(as_text=True)
        self.assertIn(self.student['ad_soyad'], sinif)
        self.assertNotIn(diger['ad_soyad'], sinif)
        self.teacher_client.post('/sonuclar', data={
            'ogrenci': self.oid, 'tur': 'ders', 'ad': 'Sınıf yaprak testi', 'tarih': '2026-10-13',
            'ders': 'Matematik', 'soru_sayisi': '20', 'dogru': '14', 'yanlis': '4', 'yanlis_goturme': '0',
        })
        yaprak = self.teacher_client.get('/lgs/test-analiz', query_string={'ad': 'Sınıf yaprak testi', 'tarih': '2026-10-13', 'tur': 'ders'}).get_data(as_text=True)
        self.assertIn('Ders başına ortalama', yaprak)
        self.assertIn('<summary>Ders başına ortalama doğru, yanlış, boş</summary>', yaprak)
        self.assertIn('Gelişim grafiği', yaprak)
        self.assertIn('id="ta-gelisim"', yaprak)
        self.assertIn('Matematik', yaprak)
        self.assertIn(self.student['ad_soyad'], yaprak)
        self.assertEqual(self.parent.get('/lgs/test-analiz').status_code, 302)
        pano = self.teacher_client.get('/lgs', query_string={'ekran': 'evde'}).get_data(as_text=True)
        self.assertIn('Sınıf analizi', pano)
        self.assertNotIn('Sınıfın temposunu kaydet', pano)
        self.assertNotIn('sinif_tempo', pano)
        veli = self.parent.get('/veli/lgs', query_string={'bolum': 'deneme', 'sinav': sinav['id']}).get_data(as_text=True)
        self.assertIn('Soru soru başarı', veli)
        self.assertIn('En çok zorlayan sorular', veli)
        self.assertIn('sıradasın', veli)
        self.assertIn('id="soru-dyb"', veli)
        self.assertIn('id="sinif-net"', veli)
        self.assertNotIn(diger['ad_soyad'], veli)
        yaprak_veli = self.parent.get('/veli/lgs', query_string={'bolum': 'deneme', 'ad': 'Sınıf yaprak testi', 'tarih': '2026-10-13', 'tur': 'ders'}).get_data(as_text=True)
        self.assertIn('Ders başına ortalama', yaprak_veli)
        self.assertNotIn(diger['ad_soyad'], yaprak_veli)


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
