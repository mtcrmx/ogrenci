import json
from io import BytesIO
import unittest
from unittest.mock import patch
import numpy as np
import cv2
import pypdfium2 as pdfium
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from docx import Document
from test_app_workflows import w,d
import kamera_media as media
import kamera_test as kt
import lgs_optik as optik


def pdf(text='Question document'):
    out=BytesIO();c=canvas.Canvas(out);c.drawString(60,750,text);c.save();return out.getvalue()


def marked_form(exam,student,token,marks,extra=None,choices='ABCD',version=1):
    data=media.form_pdf(exam,student,token,choices,version=version)
    with pdfium.PdfDocument(data) as doc:
        im=np.array(doc[0].render(scale=3).to_pil().convert('RGB'))
    for i,a in enumerate(marks):
        if a:
            x,y=media.bubble_position(i,choices.index(a),exam['soru_sayisi'],version)
            cv2.circle(im,(round(x*im.shape[1]/210),round(y*im.shape[0]/297)),round(1.65*im.shape[1]/210),(0,0,0),-1)
    if extra is not None:
        x,y=media.bubble_position(0,extra,exam['soru_sayisi'],version)
        cv2.circle(im,(round(x*im.shape[1]/210),round(y*im.shape[0]/297)),round(1.65*im.shape[1]/210),(0,0,0),-1)
    return im


class KeyParsing(unittest.TestCase):
    def test_table_labels_vertical_cells_and_unicode_separators(self):
        for text in ['Soru No: 1 2 3 4\nCevap: A B D C',
                     '1\n2\n3\n4\nA\nB\nD\nC',
                     '1\nA\n2\nB\n3\nD\n4\nC',
                     '1–A 2—B 3:(D) 4-C']:
            self.assertEqual(media.parse_key(text,4,'ABCD')[0],list('ABDC'),text)

    def test_pdf_footer_does_not_skip_ocr(self):
        with patch.object(media,'ocr_image',return_value='1 A 2 B 3 C 4 D') as ocr:
            text,used=media.extract_key_text(pdf('2026 - Page 1'),'.pdf')
            self.assertTrue(used)
            ocr.assert_called_once()
            self.assertEqual(media.parse_key(text,4,'ABCD')[0],list('ABCD'))

    def test_numbered_table_missing_duplicate_invalid(self):
        self.assertEqual(media.parse_key('CEVAP ANAHTARI\n1-C 2.A 3: D 4 B',4,'ABCD')[0],list('CADB'))
        self.assertEqual(media.parse_key('1 2 3 4\nA B D C',4,'ABCD')[0],list('ABDC'))
        a,warnings=media.parse_key('1 A\n1 B\n2 E\n4 C',3,'ABCD')
        self.assertEqual(a,['','','']);self.assertTrue(warnings)
        self.assertEqual(media.parse_key('ABC eğitim 2026',3,'ABCD')[0],['','',''])
        self.assertEqual(media.parse_key('1 A/B 2 C',2,'ABCD')[0],['','C'])

    def test_docx_key_keeps_cells_once(self):
        doc=Document();doc.add_paragraph('Cevap anahtarı');table=doc.add_table(rows=2,cols=3)
        for i in range(3):table.cell(0,i).text=str(i+1);table.cell(1,i).text='ABC'[i]
        out=BytesIO();doc.save(out)
        text,_=media.extract_key_text(out.getvalue(),'.docx')
        self.assertEqual(media.parse_key(text,3,'ABCD')[0],list('ABC'))

    def test_text_pdf_key(self):
        text,ocr=media.extract_key_text(pdf('1 A 2 B 3 C 4 D'),'.pdf')
        self.assertFalse(ocr);self.assertEqual(media.parse_key(text,4,'ABCD')[0],list('ABCD'))

    def test_word_converter_failure_is_explicit(self):
        doc=Document();doc.add_paragraph('Soru');out=BytesIO();doc.save(out)
        with patch('broadcast_presentations.office_command',return_value=None):
            with self.assertRaisesRegex(ValueError,'dönüştürücü'):media.convert_document(out.getvalue(),'.docx')

class CameraWorkflow(unittest.TestCase):
    def setUp(self):
        self.t=next(t for t in d.tum_ogretmenler() if t['yetki']=='tam')
        self.c=w.app.test_client()
        with self.c.session_transaction() as s:s.update(ogretmen_id=self.t['id'],ogretmen_adi=self.t['ad_soyad'],ogretmen_yetki='tam')
        con=d._conn();self.student=dict(con.execute("SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 1").fetchone());con.close()
        self.assertEqual(self.c.get('/yaprak-kamera').status_code,200)
        with self.c.session_transaction() as s:self.csrf=s['kamera_csrf']
        self.before_ids={e['id'] for e in optik.sinavlari_listele()}
        self.eid=optik.sinav_ekle('Camera test','2026-10-17','camera-source.pdf',list('ABCDABCDABCDAB'),self.t['id'],'yaprak','Fen Bilimleri',self.student['sinif_id'])
        (optik.klasor()/'camera-source.pdf').write_bytes(pdf())
        con=kt.connect();con.execute('INSERT INTO kamera_sinav(sinav_id,choices) VALUES(?,?)',(self.eid,'ABCD'));con.commit();con.close()
        con=kt.connect();con.execute("UPDATE lgs_optik_sinav SET kaynak='kamera' WHERE id=?",(self.eid,));con.commit();con.close()
        self.exam=optik.sinav_getir(self.eid)

    def tearDown(self):
        con=kt.connect()
        for exam in optik.sinavlari_listele():
            if exam['id'] not in self.before_ids:
                for table in ('kamera_form','kamera_sinav','kamera_islem','lgs_optik_sonuc'):
                    con.execute(f'DELETE FROM {table} WHERE sinav_id=?',(exam['id'],))
                con.execute('DELETE FROM lgs_optik_sinav WHERE id=?',(exam['id'],))
        con.commit();con.close()

    def test_scanning_removed_results_and_printing_remain(self):
        for action in ('tara','telefonda-oku','kaydet'):
            response=self.c.post(f'/yaprak-kamera/{self.eid}/{action}',data={'csrf':self.csrf})
            self.assertEqual(response.status_code,410)
        detail=self.c.get(f'/yaprak-kamera/{self.eid}')
        self.assertEqual(detail.status_code,200)
        self.assertNotIn('camera-app',detail.text)
        self.assertNotIn('Kamerayı aç',detail.text)
        self.assertNotIn('Yeni optikleri yazdır',detail.text)
        printed=self.c.get(f'/yaprak-kamera/{self.eid}/yazdir?student={self.student["id"]}')
        self.assertEqual(printed.status_code,200)
        self.assertEqual(len(PdfReader(BytesIO(printed.data)).pages),1)
        self.assertEqual(self.c.get(f'/yaprak-kamera/{self.eid}/yazdir?only=optik').status_code,410)
        self.assertIsNotNone(optik.sinav_getir(self.eid))

if __name__=='__main__':unittest.main()
