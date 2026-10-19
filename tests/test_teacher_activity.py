import os,sys,tempfile,unittest
from pathlib import Path
tmp=tempfile.TemporaryDirectory(prefix='teacher-work-test-')
os.environ.setdefault('OGR_TAKIP_DB_PATH',str(Path(tmp.name)/'test.db'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import web_app as w
import database as db
import teacher_activity as ta

class ActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        w.app.config['TESTING']=True
        if 'test_request' not in w.app.view_functions:
            w.app._got_first_request = False
            @w.app.post('/test-work-request')
            def test_request():return 'ok'
        con=db._conn()
        con.execute("DELETE FROM teacher_work_request")
        con.execute("DELETE FROM ogretmen_islem_satir WHERE islem_id='fixture-work'")
        con.execute("DELETE FROM ogretmen_islem WHERE id='fixture-work'")
        cls.admins=[dict(r) for r in con.execute("SELECT * FROM ogretmenler WHERE ad_soyad IN ('METEHAN CÜCEN','ADEM AKGÜL')")]
        cls.teacher=dict(con.execute("SELECT * FROM ogretmenler WHERE COALESCE(yetki,'tam')='tam' AND ad_soyad NOT IN ('METEHAN CÜCEN','ADEM AKGÜL') LIMIT 1").fetchone())
        con.execute("INSERT INTO ogretmen_islem(id,ogretmen_id,yol,zaman) VALUES('fixture-work',?,'/test-edit','2026-10-19 23:59:59')",(cls.teacher['id'],))
        con.execute('INSERT INTO ogretmen_islem_satir(islem_id,tablo,anahtar,onceki,sonraki) VALUES(?,?,?,?,?)',('fixture-work','odevler','{"id":999999}',None,'{"baslik":"Örnek işlem kaydı"}'))
        con.commit();con.close()

    def client(self,t):
        c=w.app.test_client()
        with c.session_transaction() as s:s.update(ogretmen_id=t['id'],ogretmen_adi=t['ad_soyad'],ogretmen_yetki='tam')
        return c

    def test_both_admins_can_view_all(self):
        self.assertEqual(len(self.admins),2)
        for admin in self.admins:
            response=self.client(admin).get('/giris-raporu?is_baslangic=2026-10-19&is_bitis=2026-10-19')
            self.assertEqual(response.status_code,200)
            self.assertIn('Örnek işlem kaydı',response.text)
            self.assertIn(self.teacher['ad_soyad'],response.text)

    def test_other_teacher_cannot_read(self):
        c=self.client(self.teacher)
        self.assertEqual(c.get('/giris-raporu').status_code,403)
        with c.session_transaction() as s:s['ogretmen_adi']='METEHAN CÜCEN'
        self.assertEqual(c.get('/giris-raporu').status_code,403)
        self.assertEqual(w.app.test_client().get('/giris-raporu').status_code,302)

    def test_filter_and_validation(self):
        c=self.client(self.admins[0])
        response=c.get('/giris-raporu',query_string={'is_ogretmen':self.admins[0]['id']})
        self.assertNotIn('Örnek işlem kaydı',response.text)
        self.assertEqual(c.get('/giris-raporu?is_baslangic=wrong').status_code,400)
        self.assertEqual(c.get('/giris-raporu?is_baslangic=2026-12-01&is_bitis=2026-01-01').status_code,400)

    def test_requests_never_store_form_content(self):
        self.client(self.teacher).post('/test-work-request',data={'password':'must-not-store','not_metni':'private-test-text'})
        con=db._conn();row=dict(con.execute('SELECT * FROM teacher_work_request ORDER BY id DESC LIMIT 1').fetchone());con.close()
        self.assertEqual(row['teacher_id'],self.teacher['id'])
        self.assertEqual(row['path'],'/test-work-request')
        self.assertNotIn('must-not-store',str(row));self.assertNotIn('private-test-text',str(row))

if __name__=='__main__':unittest.main()
