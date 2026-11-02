import os
import unittest
from unittest.mock import patch
from test_app_workflows import w, d
import veli_auth as auth


class ParentCredentials(unittest.TestCase):
    def setUp(self):
        con=auth.connect()
        self.student=dict(con.execute('SELECT * FROM ogrenciler LIMIT 1').fetchone())
        con.execute('DELETE FROM veli_credentials');con.commit();con.close()
        self.flag=patch.dict(os.environ, {'VELI_KISISEL_SIFRE':'1'})
        self.flag.start();self.addCleanup(self.flag.stop)
        self.code=auth.issue_code(self.student['id'])
        self.client=w.app.test_client()

    def login(self, password):
        return self.client.post('/veli/giris',data={'ogr_no':self.student['ogr_no'],'sifre':password})

    def test_setup_required_then_code_consumed(self):
        self.assertIn('/veli/sifre-belirle',self.login(self.code).location)
        with self.client.session_transaction() as s:self.assertNotIn('veli_ogrenci_id',s)
        self.assertEqual(self.client.get('/veli').status_code,302)
        self.assertEqual(self.client.get('/veli/sifre-belirle').status_code,200)
        with self.client.session_transaction() as s:csrf=s['veli_setup_csrf']
        self.assertEqual(self.client.post('/veli/sifre-belirle',data={'password':'test'}).status_code,400)
        password='Benim yeni şifrem 2026'
        payload={'csrf':csrf,'password':password,'confirm':'different'}
        self.assertIn('aynı değil',self.client.post('/veli/sifre-belirle',data=payload).get_data(as_text=True))
        payload['confirm']=password
        self.assertEqual(self.client.post('/veli/sifre-belirle',data=payload).location,'/veli')
        self.assertEqual(auth.authenticate(self.student['id'],self.code),(None,None))
        self.assertEqual(auth.authenticate(self.student['id'],password)[0],'login')
        self.assertEqual(auth.authenticate(self.student['id'],w.VELI_SIFRE),(None,None))
        con=auth.connect();row=dict(con.execute('SELECT * FROM veli_credentials').fetchone());con.close()
        self.assertIsNone(row['code_hash']);self.assertIsNone(row['ticket_hash'])
        self.assertNotEqual(row['password_hash'],password)

    def test_block_expiry_and_rollout(self):
        for _ in range(5):auth.authenticate(self.student['id'],'wrong')
        self.assertEqual(auth.authenticate(self.student['id'],self.code),(None,None))
        with patch.dict(os.environ,{'VELI_KISISEL_SIFRE':'0'}):
            self.assertEqual(self.login(w.VELI_SIFRE).location,'/veli')
        code=auth.issue_code(self.student['id'])
        self.login(code)
        self.client.get('/veli/sifre-belirle')
        with self.client.session_transaction() as s:csrf=s['veli_setup_csrf']
        auth.issue_code(self.student['id'])
        self.assertEqual(self.client.post('/veli/sifre-belirle',data={'csrf':csrf,'password':'long enough password','confirm':'long enough password'}).location,'/veli/giris')

    def test_shared_password_only_enrolls_once_and_old_sessions_are_rejected(self):
        oid=self.student['id']
        old=w.app.test_client()
        with old.session_transaction() as s:s['veli_ogrenci_id']=oid
        self.assertEqual(old.get('/veli').location,'/veli/giris')
        self.assertEqual(self.login(w.VELI_SIFRE).location,'/veli/sifre-belirle')
        self.client.get('/veli/sifre-belirle')
        with self.client.session_transaction() as s:csrf=s['veli_setup_csrf']
        password='Velinin kişisel şifresi'
        response=self.client.post('/veli/sifre-belirle',data={'csrf':csrf,'password':password,'confirm':password})
        self.assertEqual(response.location,'/veli')
        self.assertEqual(self.client.get('/veli').status_code,200)
        with self.client.session_transaction() as s:s.clear()
        self.assertEqual(self.login(w.VELI_SIFRE).status_code,200)
        with self.client.session_transaction() as s:self.assertNotIn('veli_setup',s)
        self.assertEqual(self.login(password).location,'/veli')
        self.assertEqual(self.client.get('/veli').status_code,200)

    def test_expired_setup_and_device_tokens(self):
        from veli_cihaz import veli_cihaz_kaydet,veli_cihaz_ogrenci
        oid=self.student['id']
        veli_cihaz_kaydet(oid,'old-device-fixture')
        self.assertIsNone(veli_cihaz_ogrenci('old-device-fixture'))
        self.login(w.VELI_SIFRE)
        con=auth.connect()
        con.execute('UPDATE veli_credentials SET ticket_until=0 WHERE ogrenci_id=?',(oid,));con.commit();con.close()
        self.assertEqual(self.client.get('/veli/sifre-belirle').location,'/veli/giris')

    def enroll(self, password='Velinin kişisel şifresi'):
        self.login(w.VELI_SIFRE)
        self.client.get('/veli/sifre-belirle')
        with self.client.session_transaction() as s:
            csrf = s['veli_setup_csrf']
        self.client.post('/veli/sifre-belirle', data={'csrf': csrf, 'password': password, 'confirm': password})
        return password

    def test_parent_can_change_password_and_other_sessions_end(self):
        old = self.enroll()
        page = self.client.get('/veli/sifre')
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('Şifre değiştir', html)
        self.assertIn('href="/veli/sifre"', html)
        with self.client.session_transaction() as s:
            csrf = s['veli_sifre_csrf']
        self.assertEqual(self.client.post('/veli/sifre', data={'password': 'x'}).status_code, 400)
        new = 'Yeni veli şifresi 2026'
        self.assertIn('Mevcut şifre hatalı', self.client.post('/veli/sifre', data={'csrf': csrf, 'current': 'yanlis', 'password': new, 'confirm': new}).get_data(as_text=True))
        self.assertIn('12–128', self.client.post('/veli/sifre', data={'csrf': csrf, 'current': old, 'password': 'kisa', 'confirm': 'kisa'}).get_data(as_text=True))
        self.assertIn('aynı değil', self.client.post('/veli/sifre', data={'csrf': csrf, 'current': old, 'password': new, 'confirm': 'farkli uzun sifre'}).get_data(as_text=True))
        self.assertIn('farklı olmalı', self.client.post('/veli/sifre', data={'csrf': csrf, 'current': old, 'password': old, 'confirm': old}).get_data(as_text=True))
        other = w.app.test_client()
        self.assertEqual(other.post('/veli/giris', data={'ogr_no': self.student['ogr_no'], 'sifre': old}).location, '/veli')
        self.assertEqual(self.client.post('/veli/sifre', data={'csrf': csrf, 'current': old, 'password': new, 'confirm': new}).location, '/veli')
        self.assertIn('Şifreniz güncellendi', self.client.get('/veli').get_data(as_text=True))
        self.assertEqual(auth.authenticate(self.student['id'], old), (None, None))
        self.assertEqual(auth.authenticate(self.student['id'], new)[0], 'login')
        self.assertEqual(other.get('/veli').location, '/veli/giris')
        self.assertEqual(self.client.get('/veli').status_code, 200)

    def test_change_password_requires_parent_session(self):
        self.assertEqual(self.client.get('/veli/sifre').location, '/veli/giris')
