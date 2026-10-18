import unittest
from unittest.mock import patch
from test_app_workflows import w, d


class InternalParentNotifications(unittest.TestCase):
    def test_operations_are_hidden_and_never_inserted_or_pushed(self):
        con = d._conn()
        student = con.execute('SELECT id,sinif_id FROM ogrenciler LIMIT 1').fetchone()
        oid, sid = student['id'], student['sinif_id']
        messages = [
            'Öğretmen önceki kaydını geri aldı. Öğrenci ekranındaki bilgiler güncellendi.',
            'Öğretmen bugünkü LGS programını onayladı.',
            'Öğretmen çalışma defterini gördü.',
            'İşlem testi: sonuç silindi.',
            'İşlem testi: sonuç güncellendi. Ders analizinizi inceleyebilirsiniz.',
            'Ödev güncellendi: İşlem testi',
        ]
        before = con.execute('SELECT count(*) FROM veli_haber').fetchone()[0]
        con.close()
        with patch.object(d, '_veli_push_sonra') as push:
            for message in messages:
                d.veli_haber_ekle(oid, message)
                d.veli_haber_sinifa(sid, message)
            push.assert_not_called()
        con = d._conn()
        self.assertEqual(before, con.execute('SELECT count(*) FROM veli_haber').fetchone()[0])
        # Simulate already delivered history from an earlier release.
        for message in messages:
            con.execute("INSERT INTO veli_haber (ogrenci_id,metin,zaman,tur,goruldu) VALUES (?,?,'2026-10-18 12:00','duyuru',0)", (oid, message))
        con.commit()
        con.close()
        client = w.app.test_client()
        with client.session_transaction() as session:
            session['veli_ogrenci_id'] = oid
        for rows in (d.veli_haber_liste(oid), d.veli_haber_bekleyen(oid), d.veli_haber_yeni(oid, 0)):
            self.assertFalse(any(row['metin'] in messages for row in rows))
        for path in ('/veli', '/veli/akis'):
            html = client.get(path).get_data(as_text=True)
            for message in messages:
                self.assertNotIn(message, html)
        payload = client.get('/veli/haber?son=0').get_json()
        self.assertFalse(any(row['metin'] in messages for row in payload['guncel'] + payload['haber']))
        with patch.object(d, '_veli_push_sonra') as push:
            d.veli_haber_ekle(oid, 'Yarın kitabınızı getiriniz.')
            push.assert_called_once()
        self.assertTrue(any(row['metin'] == 'Yarın kitabınızı getiriniz.' for row in d.veli_haber_liste(oid)))
