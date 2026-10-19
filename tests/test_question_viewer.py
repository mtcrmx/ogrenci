import unittest
from datetime import datetime
from io import BytesIO
from unittest.mock import patch
from reportlab.pdfgen import canvas
from test_app_workflows import w,d
import home_test_window
import lgs_optik


class QuestionViewer(unittest.TestCase):
    def setUp(self):
        self._now = patch.object(home_test_window, 'now', return_value=datetime.fromisoformat('2026-10-18T19:30:00+03:00'))
        self._now.start()
        self.addCleanup(self._now.stop)
        con=d._conn()
        self.oid,self.sid=con.execute("SELECT o.id,o.sinif_id FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 1").fetchone()
        self.other=con.execute("SELECT o.id FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/B' LIMIT 1").fetchone()[0]
        con.close()
        out=BytesIO();pdf=canvas.Canvas(out);pdf.drawString(40,700,'Page one question');pdf.showPage();pdf.drawString(40,700,'Page two question');pdf.save()
        self.path=lgs_optik.klasor()/'viewer-fixture.pdf';self.path.write_bytes(out.getvalue())
        self.eid=lgs_optik.sinav_ekle('Viewer fixture','2026-10-18',self.path.name,list('AB'),None,'yaprak','Fen',self.sid)
        self.c=w.app.test_client()
        with self.c.session_transaction() as s:s['veli_ogrenci_id']=self.oid

    def tearDown(self):
        lgs_optik.sinav_sil(self.eid)

    def test_html_pages_and_image_without_download(self):
        base=f'/lgs/optik/{self.eid}'
        view=self.c.get(base+'/goruntule');self.assertEqual(view.status_code,200)
        self.assertEqual(view.mimetype,'text/html');self.assertNotIn('attachment',view.headers.get('Content-Disposition',''))
        self.assertIn('Sayfa 1 / 2',view.get_data(as_text=True))
        self.assertIn('Sayfa 2 / 2',self.c.get(base+'/goruntule?page=2').get_data(as_text=True))
        image=self.c.get(base+'/sayfa/1');self.assertEqual(image.status_code,200)
        self.assertEqual(image.mimetype,'image/png');self.assertTrue(image.data.startswith(b'\x89PNG'))
        self.assertEqual(self.c.get(base+'/sayfa/3').status_code,404)
        self.assertEqual(w.app.test_client().get(base+'/sayfa/1').status_code,403)
        with self.c.session_transaction() as s:s['veli_ogrenci_id']=self.other
        self.assertEqual(self.c.get(base+'/goruntule').status_code,403)
        self.assertEqual(self.c.get(base+'/sayfa/1').status_code,403)
