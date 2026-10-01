"""School TV tests share the suite's disposable database, never the school DB."""
import unittest
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch
from test_app_workflows import w, d
import school_broadcast as tv
from broadcast_seed import duty_seed
from broadcast_timetable import timetable
from broadcast_calendar import calendar_seed


class SchoolBroadcast(unittest.TestCase):
    def setUp(self):
        self.admin = w.app.test_client()
        self.guest = w.app.test_client()
        con = d._conn()
        teacher = con.execute("SELECT id,ad_soyad FROM ogretmenler WHERE ad_soyad='ADEM AKGÜL'").fetchone()
        self.other = con.execute("SELECT id,ad_soyad FROM ogretmenler WHERE ad_soyad='FUNDA KİRAZ'").fetchone()
        for table in ('okul_yayin_icerik', 'okul_yayin_gun', 'okul_yayin_program', 'okul_yayin_takvim'):
            con.execute('DELETE FROM '+table)
        con.execute("DELETE FROM okul_yayin_ayar WHERE anahtar<>'token'")
        con.commit(); con.close()
        with self.admin.session_transaction() as s:
            s.update(ogretmen_id=teacher['id'], ogretmen_adi=teacher['ad_soyad'], ogretmen_yetki='tam')
        self.assertEqual(self.admin.get('/yayin/yonetim').status_code, 200)
        with self.admin.session_transaction() as s:
            self.csrf = s['yayin_csrf']
        self.token = tv.setting('token')

    def post(self, **fields):
        return self.admin.post('/yayin/yonetim', data=dict(csrf=self.csrf, **fields))

    def test_calendar_recurring_days_cross_month_and_year(self):
        for year, mothers, dyslexia in ((2026, '2026-05-10', '2026-10-01'), (2027, '2027-05-09', '2027-10-07')):
            items={i['id']:i for i in calendar_seed(year)}
            self.assertEqual(items[f'takvim-{year}-anneler']['baslangic'], mothers)
            self.assertEqual(items[f'takvim-{year}-disleksi-gunu']['baslangic'], dyslexia)
        on_last=tv.calendar_display('2026-11-04')['bugun']
        after=tv.calendar_display('2026-11-05')['bugun']
        self.assertIn('Kızılay Haftası',[i['baslik'] for i in on_last])
        self.assertNotIn('Kızılay Haftası',[i['baslik'] for i in after])
        self.assertTrue(all(i['baslangic'].startswith('2027') for i in tv.calendar_display('2026-12-31')['yaklasan']))
        leap=calendar_seed(2024)
        self.assertTrue(all(i['baslangic']<=i['bitis'] for i in leap))

    def test_calendar_override_hide_reset_custom_and_no_school_closure(self):
        fields=dict(islem='takvim',takvim_yil='2026',takvim_id='takvim-2026-cumhuriyet',
                    takvim_baslik='Cumhuriyet etkinliği',takvim_baslangic='2026-10-28',takvim_bitis='2026-10-29',takvim_aktif='on')
        self.assertEqual(self.post(**fields).status_code,302)
        self.assertIn('Cumhuriyet etkinliği',[i['baslik'] for i in tv.calendar_display('2026-10-28')['bugun']])
        self.assertFalse(tv.day_info('2026-10-28')['kapali'])
        hidden={k:v for k,v in fields.items() if k!='takvim_aktif'}
        self.post(**hidden)
        self.assertNotIn('Cumhuriyet etkinliği',[i['baslik'] for i in tv.calendar_display('2026-10-29')['bugun']])
        self.post(islem='takvim_sifirla',takvim_yil='2026',takvim_id=fields['takvim_id'])
        self.assertIn('Cumhuriyet Bayramı',[i['baslik'] for i in tv.calendar_display('2026-10-29')['bugun']])
        today=datetime.now(tv.ISTANBUL).date().isoformat()
        self.assertEqual(self.post(**{**fields,'takvim_yil':today[:4],'takvim_id':'','takvim_baslik':'Okul kitap şenliği',
            'takvim_baslangic':today,'takvim_bitis':today}).status_code,302)
        payload=self.guest.get('/ekran/'+self.token+'/veri').json
        self.assertIn('Okul kitap şenliği',[i['baslik'] for i in payload['takvim']['bugun']])
        before=tv.calendar_items(2026)
        self.assertEqual(self.post(**{**fields,'takvim_baslangic':'2026-10-30'}).status_code,200)
        self.assertEqual(before,tv.calendar_items(2026))

    def test_calendar_settings_restricted_to_school_managers(self):
        client=w.app.test_client()
        with client.session_transaction() as s:s.update(ogretmen_id=self.other['id'],ogretmen_adi=self.other['ad_soyad'],ogretmen_yetki='tam')
        page=client.get('/yayin/yonetim').get_data(as_text=True)
        self.assertNotIn('Okula özel etkinlik ekle',page)
        with client.session_transaction() as s:token=s['yayin_csrf']
        for action in ('takvim','takvim_sifirla'):
            self.assertEqual(client.post('/yayin/yonetim',data={'csrf':token,'islem':action}).status_code,403)

    def test_dated_pdf_duties_and_holidays(self):
        self.assertEqual(len(duty_seed()), 88)
        self.assertEqual(tv.day_info('2026-10-01')['nobet'], ['CANTEKİN KURTOĞLU', 'ELİF DEDEOĞLU', 'NESLİHAN ÇAKMAK'])
        self.assertEqual(tv.day_info('2027-01-22')['nobet'], ['AYTAÇ ATMACA', 'SATI ERGİN', 'NESLİHAN ÇAKMAK'])
        for stamp in ('2026-10-29', '2026-11-16', '2026-11-20', '2027-01-01', '2026-10-03'):
            self.assertTrue(tv.day_info(stamp)['kapali'])
        self.assertEqual(tv.day_info('2027-02-01')['nobet'], [])
        self.post(islem='gun', tarih='2026-10-01', kat1='Yedek öğretmen', kat2='', bahce='')
        self.assertEqual(tv.day_info('2026-10-01')['nobet'][0], 'Yedek öğretmen')
        self.post(islem='gun_sifirla', tarih='2026-10-01')
        self.assertEqual(tv.day_info('2026-10-01')['nobet'][0], 'CANTEKİN KURTOĞLU')

    def test_image_schedule_all_280_slots_and_merged_cells(self):
        rows = timetable()
        self.assertEqual(len(rows), 280)
        self.assertEqual(len({(r['gun'], r['ders_no'], r['sinif_adi']) for r in rows}), 280)
        self.assertEqual(len({(r['gun'], r['ders_no'], r['ogretmen_adi']) for r in rows}), 280)
        for n in (3, 4):
            row = next(r for r in rows if r['gun']==3 and r['ders_no']==n and r['sinif_adi']=='8/B')
            self.assertEqual(row['ogretmen_adi'], 'ADEM AKGÜL')
        self.assertEqual(next(r for r in rows if r['gun']==3 and r['ders_no']==7 and r['sinif_adi']=='7/A')['ogretmen_adi'], 'MERVE TÜRKEL')

    def test_display_link_is_read_only_and_revocable(self):
        self.assertEqual(self.guest.get('/ekran/'+self.token).status_code, 200)
        self.assertEqual(self.guest.post('/ekran/'+self.token).status_code, 405)
        self.assertEqual(self.guest.get('/ekran/not-a-token').status_code, 404)
        self.assertEqual(self.guest.get('/yayin/yonetim').status_code, 302)
        self.assertEqual(self.guest.get('/api/yayin/ogrenciler').status_code, 302)
        self.assertEqual(self.guest.get('/api/yayin/okul').status_code, 302)
        self.assertEqual(self.admin.post('/yayin/yonetim', data={'islem':'token'}).status_code, 400)
        self.assertEqual(self.post(islem='token').status_code, 302)
        self.assertEqual(self.guest.get('/ekran/'+self.token+'/veri').status_code, 404)

    def test_permission_resolves_database_identity(self):
        client = w.app.test_client()
        with client.session_transaction() as s:
            s.update(ogretmen_id=self.other['id'], ogretmen_adi='ADEM AKGÜL', ogretmen_yetki='tam')
        self.assertEqual(client.get('/yayin').status_code, 200)
        page=client.get('/yayin/yonetim')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(self.token,page.get_data(as_text=True))
        self.assertNotIn('Nöbet ve özel gün',page.get_data(as_text=True))
        with client.session_transaction() as s:token=s['yayin_csrf']
        self.assertEqual(client.post('/yayin/yonetim', data={'islem':'token','csrf':token}).status_code, 403)
        for name in ('METEHAN CÜCEN', 'ALPEREN MURAT LEBLEBİCİ'):
            con=d._conn(); teacher=con.execute('SELECT id,yetki FROM ogretmenler WHERE ad_soyad=?',(name,)).fetchone();con.close()
            with client.session_transaction() as s:s.update(ogretmen_id=teacher['id'],ogretmen_adi=name,ogretmen_yetki=teacher['yetki'])
            self.assertEqual(client.get('/yayin').status_code, 200)
            self.assertEqual(client.get('/api/yayin/okul').status_code, 200)
            if name.startswith('METEHAN'):
                self.assertEqual(client.get('/yayin/yonetim').status_code, 200)
            else:
                self.assertEqual(client.get('/yayin/yonetim').status_code, 200)

    def test_payload_timezone_public_fields_and_no_student_data(self):
        with w.app.test_request_context():
            data = tv.payload(now=datetime(2026,10,1,22,30,tzinfo=timezone.utc))
        self.assertEqual(data['tarih'], '2026-10-02')
        self.assertEqual(data['gun'], 4)
        self.assertTrue(data['simdi'].endswith('+03:00'))
        self.assertNotIn('ogrenciler', data)
        self.assertTrue(all(set(r)=={'gun','ders_no','ders_adi','sinif_adi','ogretmen_adi'} for r in data['program']))
        r=self.guest.get('/ekran/'+self.token+'/veri')
        self.assertIn('no-store',r.headers['Cache-Control'])
        self.assertEqual(r.headers['Referrer-Policy'],'no-referrer')

    def test_content_publication_window_edit_draft_and_media(self):
        today=datetime.now(tv.ISTANBUL).date().isoformat()
        common=dict(islem='icerik',baslik='Kitap okuma saati',metin='<script>private()</script>',baslangic=today,bitis=today,sure='18',aktif='on')
        self.assertEqual(self.post(**common).status_code,302)
        data=self.guest.get('/ekran/'+self.token+'/veri').json
        self.assertEqual(len(data['icerikler']),1)
        cid=data['icerikler'][0]['id']
        self.post(**{**common,'id':str(cid),'baslik':'Düzenlenmiş duyuru','aktif':''})
        # A checkbox is absent when unchecked, not an empty field.
        no_active={k:v for k,v in common.items() if k!='aktif'}
        self.post(**no_active,id=str(cid))
        self.assertEqual(self.guest.get('/ekran/'+self.token+'/veri').json['icerikler'],[])
        self.post(**{**common,'id':str(cid),'baslangic':'2000-01-01','bitis':'2000-01-02'})
        self.assertEqual(self.guest.get('/ekran/'+self.token+'/veri').json['icerikler'],[])
        self.assertEqual(self.guest.get(f'/ekran/{self.token}/medya/{cid}').status_code,404)
        fake={**common,'dosya':(BytesIO(b'<svg>bad</svg>'),'fake.png')}
        r=self.admin.post('/yayin/yonetim',data=dict(csrf=self.csrf,**fake),content_type='multipart/form-data')
        self.assertEqual(r.status_code,200)
        self.assertIn('Dosya içeriği',r.get_data(as_text=True))
        image=PathLogo.read_bytes()
        r=self.admin.post('/yayin/yonetim',data=dict(csrf=self.csrf,**common,dosya=(BytesIO(image),'school.png')),content_type='multipart/form-data')
        self.assertEqual(r.status_code,302)
        item=self.guest.get('/ekran/'+self.token+'/veri').json['icerikler'][0]
        media=self.guest.get(item['url'])
        self.assertEqual(media.status_code,200)
        self.assertEqual(media.content_type,'image/png')
        media.close()
        self.post(islem='sil',id=str(item['id']))
        self.assertEqual(self.guest.get(item['url']).status_code,404)

    def test_program_override_and_conflict_are_atomic(self):
        before=tv.program_for(3)
        fields={f"p_{r['ders_no']}_{r['sinif_adi']}":r['ogretmen_adi'] for r in before}
        fields['p_1_5/A']='FUNDA KİRAZ' # already at 5/B: reject the whole day.
        r=self.post(islem='program',gun='3',**fields)
        self.assertEqual(r.status_code,200)
        self.assertEqual(tv.program_for(3), before)
        fields['p_1_5/A']='NURŞEN CÜCEN'
        self.assertEqual(self.post(islem='program',gun='3',**fields).status_code,302)
        self.assertEqual(next(r for r in tv.program_for(3) if r['ders_no']==1 and r['sinif_adi']=='5/A')['ogretmen_adi'],'NURŞEN CÜCEN')
        self.post(islem='program_sifirla',gun='3')
        self.assertEqual(tv.program_for(3),before)

    def test_invalid_bell_hours_do_not_partially_update(self):
        fields={f'{key}_{p["no"]}_{edge}':p[source] for key,day in [('haftaici',0),('cuma',4)] for p in tv.slots(day) for edge,source in [('bas','baslangic'),('bit','bitis')]}
        fields['haftaici_1_bas']='08:10'
        fields['cuma_2_bas']='08:00'
        self.assertEqual(self.post(islem='saat',**fields).status_code,200)
        self.assertEqual(tv.slots(0)[0]['baslangic'],'08:15')
        fields['cuma_2_bas']='09:15'
        self.assertEqual(self.post(islem='saat',**fields).status_code,302)
        self.assertEqual(tv.slots(0)[0]['baslangic'],'08:10')

    def test_teacher_owns_content_and_cannot_edit_other_teacher(self):
        today=datetime.now(tv.ISTANBUL).date().isoformat()
        fields=dict(islem='icerik',baslik='Yönetim duyurusu',metin='Okul duyurusu',baslangic=today,bitis=today,sure='18',aktif='on')
        self.post(**fields)
        admin_id=self.guest.get('/ekran/'+self.token+'/veri').json['icerikler'][0]['id']
        client=w.app.test_client()
        with client.session_transaction() as s:s.update(ogretmen_id=self.other['id'],ogretmen_adi=self.other['ad_soyad'],ogretmen_yetki='tam')
        client.get('/yayin/yonetim')
        with client.session_transaction() as s:token=s['yayin_csrf']
        self.assertEqual(client.post('/yayin/yonetim',data={**fields,'csrf':token,'baslik':'Öğretmen duyurusu'}).status_code,302)
        page=client.get('/yayin/yonetim').get_data(as_text=True)
        self.assertIn('Öğretmen duyurusu',page)
        self.assertNotIn('Yönetim duyurusu',page)
        self.assertEqual(client.post('/yayin/yonetim',data={**fields,'csrf':token,'id':admin_id}).status_code,403)
        self.assertEqual(client.post('/yayin/yonetim',data={'csrf':token,'islem':'sil','id':admin_id}).status_code,403)
        self.assertEqual(client.get('/yayin/yonetim?duzenle='+str(admin_id)).status_code,404)
        own=next(i['id'] for i in self.guest.get('/ekran/'+self.token+'/veri').json['icerikler'] if i['baslik']=='Öğretmen duyurusu')
        self.assertEqual(client.post('/yayin/yonetim',data={**fields,'csrf':token,'id':own,'baslik':'Düzeltilmiş duyuru'}).status_code,302)
        self.assertEqual(self.post(**{**fields,'id':own}).status_code,302)
        con=d._conn();owner=con.execute('SELECT ogretmen_id FROM okul_yayin_icerik WHERE id=?',(own,)).fetchone()[0];con.close()
        self.assertEqual(owner,self.other['id'])

    def test_pdf_pptx_validation_and_media_access(self):
        from pypdf import PdfWriter
        import zipfile
        today=datetime.now(tv.ISTANBUL).date().isoformat()
        fields=dict(csrf=self.csrf,islem='icerik',baslik='PDF sunumu',metin='',baslangic=today,bitis=today,sure='8',aktif='on')
        pdf=PdfWriter();pdf.add_blank_page(width=960,height=540);pdf.add_blank_page(width=960,height=540);stream=BytesIO();pdf.write(stream);stream.seek(0)
        self.assertEqual(self.admin.post('/yayin/yonetim',data={**fields,'dosya':(stream,'slides.pdf')}).status_code,302)
        item=self.guest.get('/ekran/'+self.token+'/veri').json['icerikler'][0]
        self.assertEqual(item['tur'],'pdf');response=self.guest.get(item['url']);self.assertEqual(response.content_type,'application/pdf');response.close()
        stream=BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('[Content_Types].xml','<Types/>')
            z.writestr('ppt/presentation.xml','<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldIdLst><p:sldId id="1"/><p:sldId id="2"/></p:sldIdLst></p:presentation>')
        stream.seek(0)
        self.assertEqual(self.admin.post('/yayin/yonetim',data={**fields,'dosya':(stream,'slides.pptx')}).status_code,302)
        self.assertIn('pptx',[i['tur'] for i in self.guest.get('/ekran/'+self.token+'/veri').json['icerikler']])
        for filename,bytes_ in [('bad.pptx',b'PK broken archive'),('bad.pdf',b'%PDF-broken')]:
            r=self.admin.post('/yayin/yonetim',data={**fields,'dosya':(BytesIO(bytes_),filename)})
            self.assertEqual(r.status_code,200)
            self.assertNotIn('bad.',self.guest.get('/ekran/'+self.token+'/veri').get_data(as_text=True))


from pathlib import Path
PathLogo=Path(__file__).resolve().parents[1]/'static'/'school-broadcast-logo.png'
