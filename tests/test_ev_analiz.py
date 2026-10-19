"""Integration checks with an isolated database; no live records are modified."""
import os
import tempfile
import unittest
from pathlib import Path
from datetime import date
sandbox=tempfile.TemporaryDirectory(prefix='ev-analiz-tests-')
os.environ.setdefault('OGR_TAKIP_DB_PATH',str(Path(sandbox.name)/'school.db'))
import web_app as w
import database as db
import lgs_optik as optik
import ev_analiz as ea

class HomeAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        w.app.config.update(TESTING=True)
        con=db._conn()
        cls.teacher=dict(con.execute('SELECT * FROM ogretmenler ORDER BY id LIMIT 1').fetchone())
        cls.students=[dict(r) for r in con.execute("SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 2")]
        cls.other=dict(con.execute("SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/B' LIMIT 1").fetchone())
        con.close()
        cls.exam=optik.sinav_ekle('Analiz test kaydı',date.today().isoformat(),'test.pdf',['A','B','C'],cls.teacher['id'],'yaprak','Matematik',cls.students[0]['sinif_id'])
        optik.sonuc_kaydet(cls.exam,cls.students[0]['id'],['A','D',''])
        optik.sonuc_kaydet(cls.exam,cls.students[1]['id'],['B','B','C'])
    def client(self,student=None,teacher=False):
        client=w.app.test_client()
        with client.session_transaction() as s:
            if teacher:s.update(ogretmen_id=self.teacher['id'],ogretmen_adi=self.teacher['ad_soyad'],ogretmen_yetki='tam')
            else:s['veli_ogrenci_id']=(student or self.students[0])['id']
            s['ev_csrf']='test-token'
        return client
    def post(self,c,action,**kw):
        return c.post('/evde-analiz',data=dict(csrf='test-token',test=self.exam,action=action,**kw))
    def test_01_render_privacy_and_totals(self):
        teacher=self.client(teacher=True).get('/evde-analiz',query_string={'test':self.exam})
        self.assertEqual(teacher.status_code,200)
        parent=self.client().get('/evde-analiz',query_string={'test':self.exam})
        self.assertEqual(parent.status_code,200)
        html=parent.get_data(as_text=True)
        self.assertIn(self.students[0]['ad_soyad'],html)
        self.assertNotIn(self.students[1]['ad_soyad'],html)
        q=ea.aggregate(optik.sinav_getir(self.exam),optik.cozen_ogrenciler(self.exam),{})
        self.assertEqual(q[1]['counts']['D'],1)
        self.assertEqual(q[2]['blank'],[self.students[0]['id']])
    def test_02_help_reply_and_scope(self):
        parent=self.client();teacher=self.client(teacher=True)
        self.assertEqual(self.post(parent,'help',no=2,note='İkinci adımı anlamadım').status_code,302)
        con=ea.connection();hid=con.execute('SELECT id FROM ev_yardim WHERE sinav_id=?',(self.exam,)).fetchone()[0];con.close()
        self.assertEqual(self.post(parent,'reply',help_id=hid,reply='forbidden').status_code,403)
        self.assertEqual(self.post(teacher,'reply',help_id=hid,reply='Paydaları eşitleyelim.').status_code,302)
        self.assertIn('Paydaları eşitleyelim.',parent.get('/evde-analiz',query_string={'test':self.exam}).get_data(as_text=True))
        self.assertEqual(self.post(parent,'help',no=99).status_code,400)
        self.assertEqual(parent.post('/evde-analiz',data={'test':self.exam,'action':'help','no':1}).status_code,400)
    def test_03_group_assignment(self):
        teacher=self.client(teacher=True)
        self.assertEqual(self.post(teacher,'group',name='Kesirler',member=[s['id'] for s in self.students]).status_code,302)
        con=ea.connection();gid=con.execute('SELECT max(id) FROM ev_grup').fetchone()[0];con.close()
        self.assertEqual(self.post(teacher,'assign',group=gid,target=self.exam).status_code,302)
        self.assertIn('Kesirler',self.client().get('/evde-analiz',query_string={'test':self.exam}).get_data(as_text=True))
    def test_04_other_class_and_unsubmitted(self):
        outsider=self.client(self.other)
        self.assertEqual(outsider.get('/evde-analiz',query_string={'test':self.exam}).status_code,404)
        self.assertEqual(outsider.post('/veli/lgs',data={'islem':'optik_bitir','sinav_id':self.exam}).status_code,403)
        fresh=optik.sinav_ekle('Henüz çözülmedi',date.today().isoformat(),'test.pdf',['E','D'],self.teacher['id'],'yaprak','Matematik',self.students[0]['sinif_id'])
        html=self.client().get('/evde-analiz',query_string={'test':fresh}).get_data(as_text=True)
        self.assertNotIn('Doğru cevap:',html)
        self.assertIn('Bu testi henüz tamamlamadınız.',html)
    def test_05_metadata_weekly(self):
        teacher=self.client(teacher=True)
        self.assertEqual(self.post(teacher,'meta',no=1,topic='Kesirler',solution='Açıklamalı çözüm').status_code,302)
        html=self.client().get('/evde-analiz',query_string={'test':self.exam,'tab':'weekly'}).get_data(as_text=True)
        self.assertIn('Haftalık veli özeti',html)
        self.assertIn('Açıklamalı çözüm',html)
        self.assertIn('Kesirler',html)
    def test_06_legacy_route(self):
        c=self.client(teacher=True)
        self.assertEqual(c.get('/lgs/test-analiz').status_code,302)
        self.assertEqual(c.get('/lgs/test-analiz?kaynak=eski').status_code,200)

if __name__=='__main__': unittest.main()
