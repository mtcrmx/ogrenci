import os
import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from test_app_workflows import w,d

_TEST_YONETICI_HASH = generate_password_hash('EC200')


class AdministratorPreview(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {'YONETICI_PASSWORD_HASH': _TEST_YONETICI_HASH})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.client=w.app.test_client()
        self.client.get('/yonetici/giris')
        with self.client.session_transaction() as s:self.csrf=s['yonetici_csrf']
        con=d._conn()
        self.students=[dict(r) for r in con.execute('SELECT id,ad_soyad FROM ogrenciler ORDER BY sinif_id LIMIT 2')]
        con.close()

    def test_admin_login_preview_and_write_rejection(self):
        self.assertEqual(self.client.get('/yonetici').status_code,302)
        self.assertEqual(self.client.post('/yonetici/giris',data={'username':'yonetici','password':'EC200'}).status_code,400)
        result=self.client.post('/yonetici/giris',data={'username':'yonetici','password':'EC200','csrf':self.csrf})
        self.assertEqual(result.location,'/yonetici')
        html=self.client.get('/yonetici').get_data(as_text=True)
        for student in self.students:self.assertIn(student['ad_soyad'],html)
        with self.client.session_transaction() as s:csrf=s['yonetici_csrf']
        with patch.dict(os.environ,{'VELI_KISISEL_SIFRE':'1'}):
            for student in self.students:
                self.assertEqual(self.client.post('/yonetici/ogrenci/'+str(student['id']),data={'csrf':csrf}).location,'/veli')
                response=self.client.get('/veli')
                self.assertEqual(response.status_code,200)
                self.assertIn(student['ad_soyad'],response.get_data(as_text=True))
                self.assertIn('Yalnızca görüntüleme',response.get_data(as_text=True))
            self.assertEqual(self.client.get('/lgs/birlesik-analiz').status_code,200)
            self.assertEqual(self.client.post('/veli/haber/goruldu',json={}).status_code,403)
            self.assertEqual(self.client.post('/evde-analiz',data={'action':'help'}).status_code,403)
            self.assertEqual(self.client.get('/veli/sifre-belirle').status_code,403)
        self.assertEqual(self.client.post('/yonetici/ogrenci/99999999',data={'csrf':csrf}).status_code,404)
        self.assertEqual(self.client.post('/yonetici/ogrenci/'+str(self.students[0]['id']),data={}).status_code,400)
        with self.client.session_transaction() as s:s['yonetici_until']=1
        self.assertEqual(self.client.get('/veli').location,'/yonetici/giris')

    def test_parent_cannot_select_another_student(self):
        with self.client.session_transaction() as s:s['veli_ogrenci_id']=self.students[0]['id']
        response=self.client.post('/yonetici/ogrenci/'+str(self.students[1]['id']),data={'csrf':self.csrf})
        self.assertEqual(response.status_code,302)
        with self.client.session_transaction() as s:self.assertNotEqual(s.get('veli_ogrenci_id'),self.students[1]['id'])
