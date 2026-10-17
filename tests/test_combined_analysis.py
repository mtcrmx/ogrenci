import unittest
from flask import template_rendered
from test_app_workflows import w,d
import lgs_optik as optik
from yaprak_analiz import combined_stats

class CombinedAnalysis(unittest.TestCase):
    def test_sources_totals_parent_scope_and_navigation(self):
        con=d._conn()
        children=[dict(r) for r in con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 2")]
        teacher=next(t for t in d.tum_ogretmenler() if t['yetki']=='tam')
        con.close(); ids=[]
        try:
            for source,count,correct in [('ev',4,2),('okul',6,6),('deneme',10,2)]:
                eid=optik.sinav_ekle('Combined fixture '+source,'2026-10-18','none.pdf',['A']*count,teacher['id'],'deneme' if source=='deneme' else 'yaprak','Fixture Course',children[0]['sinif_id']);ids.append(eid)
                if source=='okul':
                    con=d._conn();con.execute("UPDATE lgs_optik_sinav SET kaynak='kamera' WHERE id=?",(eid,));con.commit();con.close()
                for child in children:optik.sonuc_kaydet(eid,child['id'],['A']*correct+['B']*(count-correct))
            client=w.app.test_client()
            with client.session_transaction() as s:s['veli_ogrenci_id']=children[0]['id']
            contexts=[]
            def capture(sender,template,context,**extra):contexts.append(context)
            template_rendered.connect(capture,w.app)
            try:
                response=client.get('/lgs/birlesik-analiz?ders=Fixture+Course')
                self.assertEqual(response.status_code,200)
                self.assertEqual(contexts[-1]['stats']['total'],20)
                self.assertEqual(contexts[-1]['stats']['rate'],50)
                self.assertNotIn(children[1]['ad_soyad'],response.get_data(as_text=True))
                for source,count in [('ev',4),('okul',6),('deneme',10)]:
                    self.assertEqual(client.get('/lgs/birlesik-analiz?ders=Fixture+Course&tur='+source).status_code,200)
                    self.assertEqual(contexts[-1]['stats']['total'],count)
                self.assertEqual(client.get('/lgs/birlesik-analiz?baslangic=invalid').status_code,400)
                with client.session_transaction() as s:s.clear();s.update(ogretmen_id=teacher['id'],ogretmen_adi=teacher['ad_soyad'],ogretmen_yetki='tam')
                self.assertEqual(client.get('/sonuclar').location,'/yaprak-kamera')
                page=client.get('/yaprak-kamera').get_data(as_text=True)
                self.assertIn('Okulda Yaprak Test',page)
                self.assertNotIn('Yaprak test · Kamera',page)
                self.assertEqual(client.get('/lgs/birlesik-analiz?ders=Fixture+Course').status_code,200)
                self.assertEqual(contexts[-1]['stats']['total'],40)
            finally:template_rendered.disconnect(capture,w.app)
        finally:
            for eid in ids:optik.sinav_sil(eid)
