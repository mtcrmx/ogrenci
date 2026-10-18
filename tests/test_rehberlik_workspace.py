import unittest
from test_app_workflows import w, d
from rehberlik_workspace import query, TOPICS


class CounselorWorkspace(unittest.TestCase):
    def setUp(self):
        self.teacher=next(t for t in d.tum_ogretmenler() if t['yetki']=='rehber')
        self.student=query("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 1")[0]
        self.client=w.app.test_client()
        with self.client.session_transaction() as s:
            s.update(ogretmen_id=self.teacher['id'],ogretmen_adi=self.teacher['ad_soyad'],ogretmen_yetki='rehber')
        self.client.get('/rehberlik/takip')
        with self.client.session_transaction() as s:self.csrf=s['rehber_csrf']

    def post(self,path,**data):
        return self.client.post(path,data=dict(csrf=self.csrf,**data))

    def make_case(self):
        r=self.post('/rehberlik/takip',student_id=self.student['id'],topic=TOPICS[0],goal='PRIVATE-COUNSELOR-GOAL',priority='normal')
        self.assertEqual(r.status_code,302)
        return r.location

    def test_all_workspace_pages_render(self):
        for path in ('','/takip','/ajanda','/etkinlikler','/ozet','/lgs','/lgs/'+str(self.student['id']),'/ogretmenler','/kutuphane'):
            with self.subTest(path=path):
                r=self.client.get('/rehberlik'+path)
                self.assertEqual(r.status_code,200)
                self.assertIn('no-store',r.headers['Cache-Control'])

    def test_detailed_academic_analysis_is_read_only(self):
        import lgs_optik as optik
        exam=optik.sinav_ekle('Rehber analiz testi','2026-10-18','test.pdf',['A','B'],self.teacher['id'],'yaprak','Matematik',self.student['sinif_id'])
        optik.sonuc_kaydet(exam,self.student['id'],['A','D'])
        for path in ('/evde-analiz?test='+str(exam),'/okul-yaprak-analiz','/lgs/birlesik-analiz','/deneme-analiz','/lgs/test-analiz?kaynak=eski'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code,200)
        html=self.client.get('/evde-analiz?test='+str(exam)).get_data(as_text=True)
        self.assertIn(self.student['ad_soyad'],html)
        self.assertIn('Kazanım haritası',html)
        self.assertNotIn('id="ea-group-form"',html)
        self.assertNotIn('Açıklamayı kaydet',html)
        self.assertEqual(self.client.post('/evde-analiz',data={'test':exam,'action':'meta'}).status_code,403)
        self.assertIn('/lgs/birlesik-analiz',self.client.get('/rehberlik/lgs').get_data(as_text=True))

    def test_private_notes_and_owner_isolation(self):
        path=self.make_case()
        self.assertEqual(self.post(path,action='note',body='PRIVATE-NOTE-EXAMPLE').status_code,302)
        self.assertIn('PRIVATE-NOTE-EXAMPLE',self.client.get(path).get_data(as_text=True))
        parent=w.app.test_client()
        with parent.session_transaction() as s:s['veli_ogrenci_id']=self.student['id']
        self.assertIn(parent.get(path).status_code,(302,403))
        self.assertNotIn('PRIVATE-NOTE-EXAMPLE',parent.get('/veli/rehberlik').get_data(as_text=True))
        con=d._conn()
        with con:con.execute('UPDATE rehber_takip SET owner=-99 WHERE id=?',(int(path.rsplit('/',1)[1]),))
        con.close()
        self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.post(path,action='note',body='blocked').status_code,404)

    def test_csrf_validation_and_version_conflict(self):
        self.assertEqual(self.client.post('/rehberlik/takip',data={}).status_code,400)
        self.assertEqual(self.post('/rehberlik/takip',student_id=-1).status_code,400)
        path=self.make_case()
        data=dict(action='update',goal='Updated',next_step='',due='',state='aktif',priority='normal',version=1)
        self.assertEqual(self.post(path,**data).status_code,302)
        self.assertEqual(self.post(path,**data).status_code,400)

    def test_appointment_overlap_and_cancel(self):
        data=dict(student_id=self.student['id'],kind='ogrenci',day='2030-01-08',time='09:00',duration=30,place='Test room')
        self.assertEqual(self.post('/rehberlik/ajanda',**data).status_code,302)
        self.assertEqual(self.post('/rehberlik/ajanda',**dict(data,time='09:15')).status_code,400)
        self.assertEqual(self.post('/rehberlik/ajanda',**dict(data,time='09:30')).status_code,302)
        row=query("SELECT id FROM rehber_ajanda WHERE starts='2030-01-08 09:00' AND owner=?",(self.teacher['id'],))[0]
        self.assertEqual(self.post('/rehberlik/ajanda',action='status',id=row['id'],state='iptal').status_code,302)
        self.assertEqual(self.post('/rehberlik/ajanda',**data).status_code,302)

    def test_reports_are_aggregate_and_academic_pages_read_only(self):
        self.make_case()
        csv=self.client.get('/rehberlik/ozet?format=csv').get_data(as_text=True)
        self.assertNotIn('PRIVATE-COUNSELOR-GOAL',csv)
        self.assertNotIn(self.student['ad_soyad'],csv)
        for path in ('/rehberlik/lgs','/rehberlik/lgs/'+str(self.student['id']),'/rehberlik/ogretmenler'):
            self.assertIn(self.post(path).status_code,(403,405))
        ordinary=w.app.test_client()
        t=next(t for t in d.tum_ogretmenler() if t['yetki']=='tam')
        with ordinary.session_transaction() as s:s.update(ogretmen_id=t['id'],ogretmen_yetki='rehber')
        self.assertEqual(ordinary.get('/rehberlik/lgs').status_code,403)

    def test_teacher_filter_and_empty_search(self):
        r=self.client.get('/rehberlik/ogretmenler?sinif=8/A&baslangic=2030-01-01&bitis=2030-01-31')
        self.assertEqual(r.status_code,200)
        self.assertIn('sonuç kaydı bulunamadı',r.get_data(as_text=True))
        self.assertIn('öğrenci bulunamadı',self.client.get('/rehberlik/lgs?q=NO-SUCH-STUDENT').get_data(as_text=True))

    def test_assigned_test_answers_and_teacher_attribution(self):
        import lgs_optik as optik
        import json
        teacher=next(t for t in d.tum_ogretmenler() if t['yetki']=='tam')
        eid=optik.sinav_ekle('Counselor visible assignment','2026-10-17','demo.pdf',['A','B','C'],teacher['id'],'yaprak','Matematik',self.student['sinif_id'])
        con=d._conn()
        with con:
            con.execute('INSERT INTO lgs_optik_sonuc(sinav_id,ogrenci_id,isaretler,dogru,yanlis,bos,net,zaman) VALUES(?,?,?,?,?,?,?,?)',(eid,self.student['id'],json.dumps(['A','D','']),1,1,1,.67,'2026-10-17 10:00'))
        con.close()
        html=self.client.get('/rehberlik/lgs/'+str(self.student['id'])).get_data(as_text=True)
        self.assertIn('Counselor visible assignment',html)
        self.assertIn(teacher['ad_soyad'],html)
        self.assertIn('İşaretlenen: D',html)
        self.assertIn('Doğru: B',html)
        self.assertIn('İşaretlenen: Boş',html)
        feed=self.client.get('/rehberlik/ogretmenler?baslangic=2026-10-01&bitis=2026-10-31&ogretmen='+str(teacher['id'])).get_data(as_text=True)
        self.assertIn('Counselor visible assignment',feed)
        self.assertNotIn('Counselor visible assignment',self.client.get('/rehberlik/ogretmenler?ogretmen='+str(self.teacher['id'])).get_data(as_text=True))

    def test_class_activity_completion_enters_monthly_summary(self):
        r=self.post('/rehberlik/etkinlikler',class_id=self.student['sinif_id'],title='Test class activity',topic=TOPICS[0],goal='Weekly planning',day='2031-04-03',state='planlandi',participants=0)
        self.assertEqual(r.status_code,302)
        event=query("SELECT id FROM rehber_etkinlik WHERE title='Test class activity'")[0]
        self.assertEqual(self.post('/rehberlik/etkinlikler',action='status',id=event['id'],state='tamamlandi',participants=20).status_code,302)
        csv=self.client.get('/rehberlik/ozet?ay=2031-04&format=csv').get_data(as_text=True)
        self.assertIn('Tamamlanan sınıf çalışması,1',csv)
        self.assertIn('Etkinlik katılımı (tekil kişi değil),20',csv)
        self.assertNotIn('Weekly planning',csv)

    def test_teacher_changes_show_academic_fields_not_raw_notes(self):
        import json
        from uuid import uuid4
        action=uuid4().hex
        data=dict(ogrenci_id=self.student['id'],kitap_adi='Example book',kitap_okuma='okudu',odev_not='DO-NOT-EXPOSE-RAW-NOTE')
        con=d._conn()
        with con:
            con.execute('INSERT INTO ogretmen_islem(id,ogretmen_id,yol,zaman) VALUES(?,?,?,?)',(action,self.teacher['id'],'/test','2032-01-01 09:00'))
            con.execute('INSERT INTO ogretmen_islem_satir(islem_id,tablo,anahtar,sonraki) VALUES(?,?,?,?)',(action,'haftalik_takip','test',json.dumps(data)))
        con.close()
        html=self.client.get('/rehberlik/ogretmenler?baslangic=2032-01-01&bitis=2032-01-02').get_data(as_text=True)
        self.assertIn('Okuma: Okudu',html)
        self.assertIn(self.student['ad_soyad'],html)
        self.assertIn('Example book',html)
        self.assertNotIn('DO-NOT-EXPOSE-RAW-NOTE',html)

if __name__=='__main__':unittest.main()
