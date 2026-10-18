from io import BytesIO
import unittest
from unittest.mock import patch
from reportlab.pdfgen import canvas
from test_app_workflows import w,d

def pdf(text):
    out=BytesIO();c=canvas.Canvas(out);c.drawString(50,750,text);c.save();return out.getvalue()

class HomeKeyUpload(unittest.TestCase):
    def test_pdf_import_partial_auth_and_failure(self):
        teacher=next(t for t in d.tum_ogretmenler() if t['yetki']=='tam')
        client=w.app.test_client()
        with client.session_transaction() as s:s.update(ogretmen_id=teacher['id'],ogretmen_adi=teacher['ad_soyad'],ogretmen_yetki='tam')
        page=client.get('/lgs?ekran=evde')
        self.assertEqual(page.status_code,200)
        self.assertIn('Cevap anahtarı belgesi',page.get_data(as_text=True))
        with client.session_transaction() as s:token=s['kamera_csrf']
        def upload(text,**extra):
            return client.post('/yaprak-kamera/anahtar-oku',data=dict(csrf=token,count='4',key=(BytesIO(pdf(text)),'key.pdf'),**extra))
        response=upload('1-A 2-C 3-D 4-B')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['answers'],list('ACDB'))
        self.assertEqual(response.json['read'],4)
        response=upload('1-A 2-C 4-B')
        self.assertEqual(response.json['answers'],['A','C','','B'])
        self.assertTrue(response.json['warnings'])
        self.assertEqual(client.post('/yaprak-kamera/anahtar-oku',data={'count':4}).status_code,400)
        with patch('kamera_media.extract_key_text',side_effect=RuntimeError('OCR unavailable')):
            response=upload('1-A 2-C 3-D 4-B')
            self.assertEqual(response.status_code,422)
            self.assertIn('error',response.json)
        with client.session_transaction() as s:s.clear();s['veli_ogrenci_id']=58
        self.assertEqual(upload('1-A 2-C 3-D 4-B').status_code,302)
