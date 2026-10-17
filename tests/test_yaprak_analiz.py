import os,tempfile,unittest
from pathlib import Path
sandbox=tempfile.TemporaryDirectory(prefix='yaprak-analysis-')
os.environ['OGR_TAKIP_DB_PATH']=str(Path(sandbox.name)/'school.db')
import web_app as w
import database as db
from yaprak_analiz import group_records,summarize

class LeafAnalysis(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  w.app.config['TESTING']=True
  con=db._conn();db._lgs_init(con)
  cls.teacher=dict(con.execute('SELECT * FROM ogretmenler ORDER BY id LIMIT 1').fetchone())
  cls.students=[dict(r) for r in con.execute("SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 3")]
  cls.other=dict(con.execute("SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/B' LIMIT 1").fetchone())
  con.execute('DELETE FROM lgs_deneme_ders');con.execute('DELETE FROM lgs_deneme')
  def add(oid,name,day,total,correct,wrong,tur='ders',course='Matematik'):
   cur=con.execute('INSERT INTO lgs_deneme(ogrenci_id,ad,tarih,tur) VALUES(?,?,?,?)',(oid,name,day,tur))
   con.execute('INSERT INTO lgs_deneme_ders(deneme_id,ders,dogru,yanlis,bos,net,soru_sayisi,yanlis_goturme) VALUES(?,?,?,?,?,?,?,?)',(cur.lastrowid,course,correct,wrong,total-correct-wrong,correct-wrong/3,total,3))
  add(cls.students[0]['id'],'İlk test','2026-10-01',10,5,3)
  add(cls.students[0]['id'],'Son test','2026-10-10',20,15,3)
  add(cls.students[1]['id'],'Son test','2026-10-10',20,5,10)
  add(cls.other['id'],'Son test','2026-10-10',20,20,0)
  add(cls.students[0]['id'],'Deneme dahil olmamalı','2026-10-12',20,20,0,'deneme')
  con.commit();con.close()
 def client(self,parent=False):
  c=w.app.test_client()
  with c.session_transaction() as s:
   if parent:s['veli_ogrenci_id']=self.students[0]['id']
   else:s.update(ogretmen_id=self.teacher['id'],ogretmen_adi=self.teacher['ad_soyad'],ogretmen_yetki='tam')
  return c
 def test_parent_privacy_and_correct_denominator(self):
  r=self.client(True).get('/okul-yaprak-analiz');self.assertEqual(r.status_code,200)
  text=r.get_data(as_text=True)
  self.assertIn('%75.0',text);self.assertIn('+25.0',text);self.assertIn('%50.0',text)
  self.assertNotIn(self.students[1]['ad_soyad'],text);self.assertNotIn(self.other['ad_soyad'],text)
  self.assertNotIn('Deneme dahil olmamalı',text)
 def test_teacher_missing_and_distribution(self):
  r=self.client().get('/okul-yaprak-analiz?sinif=8/A');self.assertEqual(r.status_code,200)
  text=r.get_data(as_text=True);self.assertIn(self.students[2]['ad_soyad'],text)
  self.assertIn('sonuç kaydı yok',text);self.assertIn('Sınıf doğru yüzdesi',text)
 def test_date_filters_and_empty(self):
  c=self.client();r=c.get('/okul-yaprak-analiz?bitis=2026-10-02');text=r.get_data(as_text=True)
  self.assertIn('İlk test',text);self.assertNotIn('Son test',text)
  self.assertIn('Bu filtrelere uyan yaprak test sonucu yok',c.get('/okul-yaprak-analiz?baslangic=2030-01-01').get_data(as_text=True))
  self.assertEqual(c.get('/okul-yaprak-analiz?baslangic=bozuk').status_code,400)
  self.assertEqual(c.get('/okul-yaprak-analiz?baslangic=2030-01-01&bitis=2020-01-01').status_code,400)
 def test_parent_cannot_choose_other_child(self):
  text=self.client(True).get('/okul-yaprak-analiz',query_string={'ogrenci':self.other['id'],'sinif':'8/B'}).get_data(as_text=True)
  self.assertNotIn(self.other['ad_soyad'],text);self.assertIn(self.students[0]['ad_soyad'],text)
 def test_grouping_distinguishes_question_counts(self):
  base=dict(ad='Aynı isim',tarih='2026-10-01',ders='Matematik',yanlis_goturme=3,dogru=5,yanlis=2,bos=3,net=4.33,ogrenci_id=1)
  groups=group_records([dict(base,soru_sayisi=10),dict(base,soru_sayisi=20,ogrenci_id=2)])
  self.assertEqual(len(groups),2)
  self.assertEqual(summarize([dict(base,rate=50)])['rate'],50)
 def test_anonymous(self):
  self.assertEqual(w.app.test_client().get('/okul-yaprak-analiz').status_code,302)
if __name__=='__main__':unittest.main()
