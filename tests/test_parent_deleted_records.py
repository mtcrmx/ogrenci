import unittest
from test_app_workflows import w,d


class DeletedParentRecords(unittest.TestCase):
    def setUp(self):
        con=d._conn()
        self.oid=con.execute('SELECT id FROM ogrenciler LIMIT 1').fetchone()[0]
        self.teacher=con.execute('SELECT id FROM ogretmenler LIMIT 1').fetchone()[0]
        self.sid=con.execute('SELECT sinif_id FROM ogrenciler WHERE id=?',(self.oid,)).fetchone()[0]
        con.close();self.client=w.app.test_client()
        with self.client.session_transaction() as session:session['veli_ogrenci_id']=self.oid

    def test_deleted_result_disappears_from_all_parent_reads_and_restore_works(self):
        result=d.lgs_deneme_ekle(self.oid,'Deleted fixture','2026-10-18',[dict(ders='Matematik',soru_sayisi=10,dogru=6,yanlis=3,bos=1)],tur='ders')
        d.veli_haber_ekle(self.oid,'Deleted fixture: sonuç kaydedildi. Ders analizinizi inceleyebilirsiniz.',sonuc_id=result['id'])
        d.veli_haber_ekle(self.oid,'Deleted fixture sonucu geldi. Toplam net 5.00.')
        d.veli_haber_ekle(self.oid,'Bağımsız duyuru korunur')
        self.assertIn('Deleted fixture',self.client.get('/veli').get_data(as_text=True))
        con=d._conn();row=dict(con.execute('SELECT * FROM lgs_deneme WHERE id=?',(result['id'],)).fetchone())
        con.execute('DELETE FROM lgs_deneme_ders WHERE deneme_id=?',(result['id'],));con.execute('DELETE FROM lgs_deneme WHERE id=?',(result['id'],));con.commit();con.close()
        for fn in (d.veli_haber_liste,d.veli_haber_bekleyen):
            self.assertFalse(any('Deleted fixture' in r['metin'] for r in fn(self.oid)))
        self.assertFalse(any('Deleted fixture' in r['metin'] for r in d.veli_haber_yeni(self.oid,0)))
        for path in ('/veli','/veli/akis','/veli/haber?son=0'):
            self.assertNotIn('Deleted fixture',self.client.get(path).get_data(as_text=True))
        self.assertTrue(any(r['metin']=='Bağımsız duyuru korunur' for r in d.veli_haber_liste(self.oid)))
        con=d._conn();con.execute('INSERT INTO lgs_deneme ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()));con.commit();con.close()
        self.assertTrue(any('Deleted fixture' in r['metin'] for r in d.veli_haber_liste(self.oid)))

    def test_hidden_or_deleted_note_and_deleted_homework(self):
        d.ogretmen_notu_ekle(self.oid,self.teacher,'Visibility fixture',True,'olumlu')
        homework=d.odev_ekle(self.sid,self.teacher,'Homework deletion fixture','Read pages','2026-10-20','Türkçe')
        con=d._conn();con.execute("UPDATE ogretmen_notlari SET veliye_acik=0 WHERE not_metni='Visibility fixture'")
        con.execute('DELETE FROM odevler WHERE id=?',(homework['odev_id'],));con.commit();con.close()
        payload=self.client.get('/veli/haber').get_json()
        self.assertNotIn('Visibility fixture',payload['notlar_html'])
        self.assertFalse(any('Visibility fixture' in r['metin'] or 'Homework deletion fixture' in r['metin'] for r in payload['guncel']))
