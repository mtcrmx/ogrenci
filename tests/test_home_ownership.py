import unittest
from flask import session
from test_app_workflows import w,d
import lgs_optik as optik
from reportlab.pdfgen.canvas import Canvas

class HomeOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.managers=[x for x in d.tum_ogretmenler() if x['ad_soyad'] in {'ADEM AKGÜL','METEHAN CÜCEN','ALPEREN MURAT LEBLEBİCİ'}]
        cls.teachers=[x for x in d.tum_ogretmenler() if x['yetki']=='tam' and x not in cls.managers][:2]
        cls.owner,cls.other=cls.teachers
        p=optik.klasor()/'ownership.pdf';c=Canvas(str(p));c.drawString(20,700,'OWNERSHIP');c.save()
        cls.eid=optik.sinav_ekle('PRIVATE FUNDA TEST','2026-10-19','ownership.pdf',['A'],cls.owner['id'],'yaprak','Matematik',None)

    def client(self,teacher):
        c=w.app.test_client()
        with c.session_transaction() as s:s.update(ogretmen_id=teacher['id'],ogretmen_adi=teacher['ad_soyad'],ogretmen_yetki=teacher['yetki'])
        return c

    def test_other_teacher_cannot_list_or_fetch(self):
        with w.app.test_request_context('/'):
            session.update(ogretmen_id=self.other['id'],ogretmen_adi='METEHAN CÜCEN')
            self.assertNotIn(self.eid,[e['id'] for e in optik.sinavlari_listele()])
            self.assertIsNone(optik.sinav_getir(self.eid))
            self.assertEqual(optik.sinav_sonuclari(self.eid),[])
        c=self.client(self.other)
        for suffix in ('pdf','goruntule','sayfa/0'):
            self.assertEqual(c.get(f'/lgs/optik/{self.eid}/{suffix}').status_code,404)
        self.assertEqual(c.get(f'/evde-analiz?test={self.eid}').status_code,404)
        self.assertNotIn('PRIVATE FUNDA TEST',c.get('/lgs?ekran=evde').text)

    def test_owner_and_three_managers_can_view(self):
        self.assertEqual(len(self.managers),3)
        for teacher in [self.owner,*self.managers]:
            with self.subTest(teacher=teacher['ad_soyad']):
                with w.app.test_request_context('/'):
                    session.update(ogretmen_id=teacher['id'])
                    self.assertIn(self.eid,[e['id'] for e in optik.sinavlari_listele()])
                    self.assertIsNotNone(optik.sinav_getir(self.eid))
                response=self.client(teacher).get(f'/lgs/optik/{self.eid}/pdf')
                self.assertEqual(response.status_code,200)
                response.close()

    def test_parent_rules_are_not_replaced_by_teacher_filter(self):
        with w.app.test_request_context('/'):
            session['veli_ogrenci_id']=1
            self.assertIsNotNone(optik.sinav_getir(self.eid))

if __name__=='__main__':unittest.main()
