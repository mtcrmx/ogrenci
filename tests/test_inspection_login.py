import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

tmp = tempfile.TemporaryDirectory()
os.environ['OGR_TAKIP_DB_PATH'] = str(Path(tmp.name) / 'test.db')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_app as w

class InspectionLoginTests(unittest.TestCase):
    def setUp(self):
        w.app.config['TESTING'] = True
        self.client = w.app.test_client()
        with self.client.session_transaction() as s:
            s['yonetici_until'] = time.time() + 3600
            s['veli_ogrenci_id'] = 1

    def test_valid_teacher_login_leaves_preview(self):
        with patch.object(w, 'ogretmen_dogrula', return_value=True), patch.object(w, 'ogretmen_id_bul', return_value=1), patch.object(w, 'ogretmen_yetki_al', return_value='tam'), patch.object(w, '_veli_oturumu_kapat'):
            response = self.client.post('/login', data={'ad_soyad':'METEHAN CÜCEN', 'sifre':'test-only'})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as s:
            self.assertEqual(s['ogretmen_adi'], 'METEHAN CÜCEN')
            self.assertNotIn('yonetici_until', s)
            self.assertNotIn('veli_ogrenci_id', s)

    def test_invalid_login_does_not_grant_teacher_access(self):
        with patch.object(w, 'ogretmen_dogrula', return_value=False):
            response = self.client.post('/login', data={'ad_soyad':'METEHAN CÜCEN', 'sifre':'wrong'})
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as s:
            self.assertNotIn('ogretmen_id', s)
            self.assertIn('yonetici_until', s)
        self.assertEqual(self.client.post('/giris-raporu').status_code, 403)

    def test_expired_preview_can_reach_login(self):
        with self.client.session_transaction() as s:
            s['yonetici_until'] = time.time() - 1
        self.assertEqual(self.client.get('/login').status_code, 200)

if __name__ == '__main__':
    unittest.main()
