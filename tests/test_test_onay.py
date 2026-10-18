import unittest
from test_app_workflows import w, d
import lgs_optik as optik
from test_onay import pending, records

class TestReview(unittest.TestCase):
    def test_owner_review_revision_and_help(self):
        con=d._conn()
        child=dict(con.execute('SELECT * FROM ogrenciler LIMIT 1').fetchone())
        teachers=[dict(r) for r in con.execute("SELECT * FROM ogretmenler WHERE yetki='tam' LIMIT 2")]
        con.close()
        owner=teachers[0]
        eid=optik.sinav_ekle('Review fixture','2026-10-18','none.pdf',['A','B'],owner['id'])
        try:
            optik.sonuc_kaydet(eid,child['id'],['A','C'])
            row=next(r for r in pending(owner['id']) if r['sinav_id']==eid)
            path='/onay-kutusu/test/'+str(row['id'])
            client=w.app.test_client()
            with client.session_transaction() as s:s.update(ogretmen_id=owner['id'],ogretmen_adi=owner['ad_soyad'],ogretmen_yetki='tam')
            self.assertIn(b'Review fixture',client.get('/onay-kutusu').data)
            self.assertEqual(client.get(path).status_code,200)
            with client.session_transaction() as s:token=s['test_review_csrf']
            payload={'csrf':token,'revision':row['revision']}
            self.assertEqual(client.post(path,data={}).status_code,400)
            self.assertEqual(client.post(path,data=dict(payload,revision='stale')).status_code,409)
            self.assertEqual(client.post(path,data=payload).status_code,302)
            self.assertFalse(any(r['sinav_id']==eid for r in pending(owner['id'])))
            con=d._conn();con.execute('UPDATE lgs_optik_sinav SET cevaplar=? WHERE id=?',('["B","B"]',eid));con.commit();con.close()
            self.assertTrue(any(r['sinav_id']==eid for r in pending(owner['id'])))
            with client.session_transaction() as s:s['ogretmen_id']=teachers[1]['id']
            self.assertEqual(client.get(path).status_code,404)
            self.assertEqual(client.post(path,data=payload).status_code,404)
            with client.session_transaction() as s:s.clear();s['veli_ogrenci_id']=child['id']
            self.assertEqual(client.get(path).status_code,302)
            self.assertEqual(client.get('/yardim').status_code,200)
        finally:optik.sinav_sil(eid)
