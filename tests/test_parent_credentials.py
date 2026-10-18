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
