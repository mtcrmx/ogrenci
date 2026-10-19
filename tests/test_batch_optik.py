import json
from io import BytesIO
import unittest
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from test_kamera_test import CameraWorkflow,marked_form,kt,optik,pdf,w
import batch_optik

class BatchImport(CameraWorkflow):
    def upload(self):
        response=self.c.get(f'/yaprak-kamera/{self.eid}/pdf-optik/formlar')
        self.assertEqual(response.status_code,200);response.close()
        con=kt.connect();token=con.execute('SELECT token FROM kamera_form WHERE sinav_id=? AND ogrenci_id=?',(self.eid,self.student['id'])).fetchone()[0];con.close()
        im=marked_form(self.exam,self.student,token,self.exam['cevaplar'],extra=1,version=2)
        out=BytesIO();c=canvas.Canvas(out,pagesize=(595.28,841.89))
        for _ in range(2):c.drawImage(ImageReader(Image.fromarray(im)),0,0,595.28,841.89);c.showPage()
        c.drawString(30,700,'Not an optical form');c.showPage();c.save()
        response=self.c.post(f'/yaprak-kamera/{self.eid}/pdf-optik/yukle',data={'csrf':self.csrf,'pdf':(BytesIO(out.getvalue()),'scanned.pdf')})
        self.assertEqual(response.status_code,302,response.data)
        self.review=response.location;self.bid=self.review.rsplit('/',1)[1]
        for n in (1,2,3):
            response=self.c.post(f'{self.review}/oku/{n}',data={'csrf':self.csrf})
            self.assertEqual(response.status_code,200,response.data)
        return self.bid

    def save_batch(self,**extra):
        data={'csrf':self.csrf,'select':'1','answers_1':''.join(self.exam['cevaplar']),'confirm_1':'yes'};data.update(extra)
        return self.c.post(f'{self.review}/kaydet',data=data)

    def test_read_review_duplicate_and_atomic_save(self):
        self.upload()
        self.assertIsNone(optik.sonuc_getir(self.eid,self.student['id']))
        response=self.c.get(self.review);self.assertEqual(response.status_code,200)
        self.assertIn('tekrar ediyor',response.text)
        self.assertIn('Kontrol gereken sorular: 1',response.text)
        self.assertEqual(self.c.get(f'{self.review}/onizleme/1').status_code,200)
        self.assertEqual(self.save_batch(confirm_1='').status_code,400)
        self.assertIsNone(optik.sonuc_getir(self.eid,self.student['id']))
        self.assertEqual(self.save_batch().status_code,302)
        self.assertEqual(optik.sonuc_getir(self.eid,self.student['id'])['dogru'],14)
        self.assertEqual(self.save_batch().status_code,409)

    def test_key_change_and_other_teacher_rejected(self):
        self.upload()
        con=kt.connect();con.execute('UPDATE lgs_optik_sinav SET cevaplar=? WHERE id=?',(json.dumps(['D']*14),self.eid));con.commit();con.close()
        self.assertEqual(self.save_batch().status_code,409)
        self.assertIsNone(optik.sonuc_getir(self.eid,self.student['id']))
        other=w.app.test_client()
        with other.session_transaction() as s:s.update(ogretmen_id=999999,ogretmen_adi='No access',ogretmen_yetki='tam')
        self.assertIn(other.get(self.review).status_code,(403,404))

    def test_invalid_pdf_and_expired_batch_rejected(self):
        response=self.c.post(f'/yaprak-kamera/{self.eid}/pdf-optik/yukle',data={'csrf':self.csrf,'pdf':(BytesIO(b'not-pdf'),'scan.pdf')})
        self.assertEqual(response.status_code,302)
        self.upload()
        self.assertEqual(self.c.post(f'{self.review}/oku/1',data={'csrf':'wrong'}).status_code,400)
        con=batch_optik.connection();con.execute('UPDATE pdf_optik_batch SET expires=0 WHERE id=?',(self.bid,));con.commit();con.close()
        self.assertEqual(self.c.get(self.review).status_code,410)
        self.assertEqual(self.save_batch().status_code,410)
        self.assertIsNone(optik.sonuc_getir(self.eid,self.student['id']))

    def test_existing_results_need_explicit_replace(self):
        optik.sonuc_kaydet(self.eid,self.student['id'],['D']*14)
        self.upload()
        self.assertEqual(self.save_batch().status_code,409)
        self.assertEqual(self.save_batch(replace_1='yes').status_code,302)
        self.assertEqual(optik.sonuc_getir(self.eid,self.student['id'])['dogru'],14)

if __name__=='__main__':unittest.main()
