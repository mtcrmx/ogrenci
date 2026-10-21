import unittest
from test_app_workflows import w,d

class InstitutionVisibility(unittest.TestCase):
    def test_institution_exam_visible_to_teacher_and_own_parent(self):
        con=d._conn()
        student=con.execute("SELECT o.id FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 1").fetchone()[0]
        con.close()
        result=d.lgs_deneme_ekle(student,'PDF kurum görünürlük kontrolü','2026-10-17',
            [dict(ders='Matematik',dogru=12,yanlis=3,bos=5)],puan=350.125,ogretmen_id=1,tur='kurum')
        self.assertTrue(result['ok'])
        listed=next(r for r in d.deneme_sinav_listesi() if r['ad']=='PDF kurum görünürlük kontrolü')
        self.assertEqual(listed['tur'],'kurum')
        with w.app.test_request_context('/deneme-analiz?sinav=PDF+kurum+görünürlük+kontrolü'):
            teacher=w._deneme_ekran_verisi(False)
            self.assertEqual(teacher['okul']['adet'],1)
            self.assertEqual(teacher['secili']['tarih'],'2026-10-17')
            parent=w._deneme_ekran_verisi(True,student)
            self.assertEqual(parent['birey']['id'],student)
            self.assertEqual(parent['birey']['puan'],350.125)
            self.assertEqual(parent['siralama'],[])
