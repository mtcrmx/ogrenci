import os,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch

sandbox=tempfile.TemporaryDirectory(prefix='home-window-')
os.environ.setdefault('OGR_TAKIP_DB_PATH',str(Path(sandbox.name)/'school.db'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import web_app as w
import database as db
import lgs_optik as optik
import home_test_window as window
import veli_auth
from reportlab.pdfgen.canvas import Canvas

class HomeWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        w.app.config['TESTING']=True
        con=db._conn()
        cls.teacher=dict(con.execute("SELECT * FROM ogretmenler WHERE COALESCE(yetki,'tam')='tam' ORDER BY id LIMIT 1").fetchone())
        cls.student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 1").fetchone())
        con.close()
        con=veli_auth.connect()
        con.execute("INSERT INTO veli_credentials(ogrenci_id,password_hash,auth_version) VALUES(?,?,?) ON CONFLICT(ogrenci_id) DO UPDATE SET password_hash=excluded.password_hash,auth_version=excluded.auth_version",(cls.student['id'],'test-only','test-version'))
        con.commit();con.close()
        path=optik.klasor()/'window-test.pdf'
        canvas=Canvas(str(path));canvas.drawString(30,700,'TEST QUESTION DOCUMENT');canvas.save()

    @classmethod
    def tearDownClass(cls):
        con=veli_auth.connect()
        con.execute("DELETE FROM veli_credentials WHERE ogrenci_id=?",(cls.student['id'],))
        con.commit();con.close()

    def setUp(self):
        self.exam=optik.sinav_ekle('Saat kontrollü test','2026-10-19','window-test.pdf',['A','B','C','D'],self.teacher['id'],'yaprak','Matematik',self.student['sinif_id'])
        self.client=w.app.test_client()
        with self.client.session_transaction() as s:s.update(veli_ogrenci_id=self.student['id'],veli_auth_version='test-version')

    def at(self,time):
        return patch.object(window,'now',return_value=datetime.fromisoformat('2026-10-19T'+time+'+03:00'))

    def submit(self):
        return self.client.post('/veli/lgs',data=dict(islem='optik_bitir',bolum='soru',sinav_id=self.exam,c0='A',c1='A',c2='C',c3=''))

    def test_explicit_solve_date_required(self):
        with self.at('17:33:00'):
            for value in (None, '', 'bad', '2026-10-18', '2026-10-19junk'):
                with self.assertRaises(ValueError):window.validate_schedule_date(value)
            self.assertEqual(window.validate_schedule_date('2026-10-19'),'2026-10-19')
            self.assertEqual(window.validate_schedule_date('2026-10-20'),'2026-10-20')
            for value in ('', '2026-10-18'):
                with w.app.test_request_context('/lgs',method='POST',data={'tarih':value}):
                    with patch.object(optik,'sinav_ekle') as create:
                        self.assertEqual(w._lgs_optik_ekle().status_code,302)
                        create.assert_not_called()
        with self.at('21:00:00'):
            with self.assertRaises(ValueError):window.validate_schedule_date('2026-10-19')

    def test_reschedule_hides_previously_released_key(self):
        con=db._conn()
        con.execute('UPDATE lgs_optik_sinav SET tarih=? WHERE id=?',('2026-10-18',self.exam));con.commit();con.close()
        with self.at('17:33:00'):
            page=self.client.get(f'/veli/lgs?sinav={self.exam}').text
            self.assertIn('<summary>Cevap anahtarı</summary>',page)
            con=db._conn()
            con.execute('UPDATE lgs_optik_sinav SET tarih=? WHERE id=?',('2026-10-19',self.exam));con.commit();con.close()
            page=self.client.get(f'/veli/lgs?sinav={self.exam}').text
            self.assertNotIn('<summary>Cevap anahtarı</summary>',page)
            self.assertEqual(self.client.get(f'/evde-analiz?test={self.exam}').status_code,404)
            self.assertEqual(self.client.get(f'/lgs/optik/{self.exam}/pdf').status_code,403)

    def test_boundaries_and_timezone(self):
        e=optik.sinav_getir(self.exam)
        for time,opened,released in [('18:59:59',False,False),('19:00:00',True,False),('20:59:59',True,False),('21:00:00',False,True)]:
            with self.at(time):
                state=window.state(e);self.assertEqual((state['open'],state['released']),(opened,released))
        self.assertTrue(window.state(e,datetime(2026,10,19,16,tzinfo=timezone.utc))['open'])
        self.assertFalse(window.state(e,datetime(2026,10,20,19,tzinfo=window.TURKEY))['open'])
        self.assertFalse(window.state({'tarih':'bad'})['open'])
        self.assertTrue(window.state({'kaynak':'kamera'})['open'])

    def test_question_routes_are_gated(self):
        for time,expected in [('18:59:59',403),('19:00:00',200),('21:00:00',403)]:
            with self.at(time):
                for suffix in ('pdf','goruntule','sayfa/1'):
                    response=self.client.get(f'/lgs/optik/{self.exam}/{suffix}')
                    self.assertEqual(response.status_code,expected,(time,suffix))
                    if expected==200:self.assertIn('no-store',response.headers.get('Cache-Control',''))

    def test_submission_window_and_immediate_totals(self):
        with self.at('18:59:59'):
            self.submit();self.assertIsNone(optik.sonuc_getir(self.exam,self.student['id']))
        with self.at('19:30:00'):
            self.assertEqual(self.submit().status_code,302)
            result=optik.sonuc_getir(self.exam,self.student['id'])
            self.assertEqual((result['dogru'],result['yanlis'],result['bos']),(2,1,1))
            page=self.client.get(f'/veli/lgs?sinav={self.exam}').text
            self.assertIn('Doğru 2',page)
            self.assertNotIn('soru-hucre',page)
            self.assertNotIn('<summary>Cevap anahtarı</summary>',page)
            self.assertEqual(self.client.get(f'/evde-analiz?test={self.exam}').status_code,404)
            with w.app.test_request_context('/veli/lgs'):
                w.session['veli_ogrenci_id']=self.student['id']
                exams,_,_=w._lgs_optik_paketi(self.student['id'])
                e=next(e for e in exams if e['id']==self.exam)
                self.assertEqual(e['cevaplar'],[])
                self.assertNotIn('analiz',e)
                self.assertNotIn('isaretler',e['sonuc'])
        with self.at('21:00:00'):
            page=self.client.get(f'/veli/lgs?sinav={self.exam}').text
            self.assertIn('<summary>Cevap anahtarı</summary>',page)
            self.assertIn('soru-hucre',page)
            self.assertNotIn(f'/lgs/optik/{self.exam}/goruntule',page)
            self.assertEqual(self.client.get(f'/evde-analiz?test={self.exam}').status_code,200)

    def test_late_submission_and_teacher_access(self):
        with self.at('21:00:00'):
            self.submit();self.assertIsNone(optik.sonuc_getir(self.exam,self.student['id']))
            page=self.client.get(f'/veli/lgs?sinav={self.exam}').text
            self.assertNotIn('data-home-test',page)
            self.assertIn('<summary>Cevap anahtarı</summary>',page)
        client=w.app.test_client()
        with client.session_transaction() as s:s.update(ogretmen_id=self.teacher['id'],ogretmen_yetki='tam')
        with self.at('10:00:00'):
            self.assertEqual(client.get(f'/lgs/optik/{self.exam}/pdf').status_code,200)

    def test_unsubmitted_and_old_date(self):
        with self.at('18:00:00'):
            page=self.client.get(f'/veli/lgs?sinav={self.exam}').text
            self.assertNotIn('data-home-test',page)
            self.assertNotIn(f'/lgs/optik/{self.exam}/goruntule',page)
            self.assertIn('19.00–21.00',page)
            self.assertEqual(self.client.get('/lgs/birlesik-analiz').status_code,200)

if __name__=='__main__':unittest.main()
