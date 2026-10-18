import unittest
from test_app_workflows import w, d
import lgs_optik


class ParentActivity(unittest.TestCase):
    def setUp(self):
        con=d._conn()
        self.student=dict(con.execute("SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 1").fetchone())
        self.other=dict(con.execute("SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/B' LIMIT 1").fetchone())
        self.teacher=con.execute('SELECT id FROM ogretmenler LIMIT 1').fetchone()[0];con.close()
        self.c=w.app.test_client()
        with self.c.session_transaction() as s:s['veli_ogrenci_id']=self.student['id']

    def test_teacher_create_edit_delete_and_student_scoping(self):
        self.assertEqual(w.app.test_client().get('/veli/akis').status_code,401)
        eid=lgs_optik.sinav_ekle('Feed own test','2026-10-18','fixture.pdf',list('ABCD'),self.teacher,'yaprak','Fen',self.student['sinif_id'])
        other=lgs_optik.sinav_ekle('Feed other class','2026-10-18','fixture.pdf',list('ABCD'),self.teacher,'yaprak','Fen',self.other['sinif_id'])
        d.ogretmen_notu_ekle(self.student['id'],self.teacher,'Feed visible note',True)
        d.ogretmen_notu_ekle(self.student['id'],self.teacher,'Feed private note',False)
        d.ogretmen_notu_ekle(self.other['id'],self.teacher,'Feed other student note',True)
        response=self.c.get('/veli/akis');html=response.get_data(as_text=True)
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertIn('Feed own test',html);self.assertIn('Feed visible note',html)
        for private in ('Feed other class','Feed private note','Feed other student note'):self.assertNotIn(private,html)
        con=d._conn();con.execute('UPDATE lgs_optik_sinav SET ad=? WHERE id=?',('Feed edited test',eid));con.commit();con.close()
        self.assertIn('Feed edited test',self.c.get('/veli/akis').get_data(as_text=True))
        lgs_optik.sonuc_kaydet(eid,self.student['id'],list('ABCD'))
        html=self.c.get('/veli/akis').get_data(as_text=True)
        self.assertIn('4 doğru, 0 yanlış, 0 boş',html)
        self.assertIn('Sonucu incele',html)
        lgs_optik.sinav_sil(eid);lgs_optik.sinav_sil(other)
        self.assertNotIn('Feed edited test',self.c.get('/veli/akis').get_data(as_text=True))

    def test_homework_content_and_escaped_notes(self):
        result=d.odev_ekle(self.student['sinif_id'],self.teacher,'Feed homework','Kitap sayfa 12–15','2026-10-20','Türkçe')
        d.ogretmen_notu_ekle(self.student['id'],self.teacher,'<script>alert(1)</script>',True)
        html=self.c.get('/veli/akis').get_data(as_text=True)
        self.assertIn('Kitap sayfa 12–15',html)
        self.assertEqual(html.count('Feed homework'),1)
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertEqual(self.c.get('/veli').status_code,200)
