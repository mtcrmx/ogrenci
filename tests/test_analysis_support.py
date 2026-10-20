import unittest
from flask import template_rendered
from test_app_workflows import w,d
import lgs_optik as optik
import ev_analiz as ea
from lgs_kazanim import connect,catalog

class SupportAnalysis(unittest.TestCase):
    def test_matrix_assignment_progress_and_privacy(self):
        con=d._conn()
        teacher=next(t for t in d.tum_ogretmenler() if t['yetki']=='tam')
        students=[dict(r) for r in con.execute("SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 3")]
        con.close()
        outcome=catalog()['items'][0]['id']; ids=[]
        client=w.app.test_client()
        with client.session_transaction() as s:s.update(ogretmen_id=teacher['id'],ogretmen_adi=teacher['ad_soyad'],ogretmen_yetki='tam',ev_csrf='token')
        contexts=[]
        def capture(sender,template,context,**extra):contexts.append(context)
        template_rendered.connect(capture,w.app)
        try:
            for name in ['Support source','Support target']:
                eid=optik.sinav_ekle(name,'2026-10-18','none.pdf',['A','B'],teacher['id'],'yaprak','Türkçe',students[0]['sinif_id']);ids.append(eid)
                con=connect();con.executemany('INSERT INTO lgs_soru_kazanim VALUES(?,?,?,?)',[(eid,n,outcome,catalog()['year']) for n in [1,2]]);con.commit();con.close()
            source,target=ids
            for child in students[:2]:optik.sonuc_kaydet(source,child['id'],['A','D'])
            page=client.get('/evde-analiz',query_string={'test':source,'tab':'outcomes','class':'8/A'})
            self.assertEqual(page.status_code,200)
            self.assertNotIn('outcome_matrix',contexts[-1])
            self.assertEqual({p['id'] for p in contexts[-1]['questions'][1]['options'][3]['members']},{p['id'] for p in students[:2]})
            payload=dict(csrf='token',test=source,action='option_note',no=2,option='D',note='İşlem hatası olabilir',tab='questions')
            self.assertEqual(client.post('/evde-analiz',data=payload).status_code,302)
            self.assertIn('İşlem hatası olabilir',client.get('/evde-analiz?test='+str(source)).get_data(as_text=True))
            payload=dict(csrf='token',test=source,action='support',name='Support group',member=[students[0]['id']],outcome=outcome,target=target,tab='groups')
            self.assertEqual(client.post('/evde-analiz',data=payload).status_code,403)
            with client.session_transaction() as s:s.clear();s.update(veli_ogrenci_id=students[0]['id'],ev_csrf='token')
            page=client.get('/evde-analiz?test='+str(source))
            self.assertEqual(page.status_code,200)
            self.assertNotIn(students[1]['ad_soyad'],page.get_data(as_text=True))
            self.assertEqual(client.post('/evde-analiz',data=payload).status_code,403)
        finally:
            template_rendered.disconnect(capture,w.app)
            for eid in ids:optik.sinav_sil(eid)
