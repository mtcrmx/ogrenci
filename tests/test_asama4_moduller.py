import unittest
from test_app_workflows import w, d
from migrations import migrate_down, migrate_up
from moduller import MODULLER, aktif_moduller, modul_var_mi, ogrenci_seviyesi, seviye


class TestAsama4Moduller(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        w.app.config["TESTING"] = True
        con = d._conn()
        try:
            migrate_up(con)
            con.execute(
                "INSERT OR IGNORE INTO siniflar (sinif_adi, seviye) "
                "VALUES ('8/C', 8)"
            )
            sinif_8c = con.execute("SELECT id FROM siniflar WHERE sinif_adi='8/C'").fetchone()["id"]
            con.execute(
                "INSERT OR IGNORE INTO ogrenciler (ad_soyad, sinif_id, ogr_no) "
                "VALUES ('TEST OGRENCI 8C', ?, '8888')",
                (sinif_8c,),
            )
            con.commit()
            cls.sinif_8a = dict(con.execute("SELECT * FROM siniflar WHERE sinif_adi='8/A'").fetchone())
            cls.sinif_8b = dict(con.execute("SELECT * FROM siniflar WHERE sinif_adi='8/B'").fetchone())
            cls.sinif_8c = dict(con.execute("SELECT * FROM siniflar WHERE sinif_adi='8/C'").fetchone())
            cls.sinif_7a = dict(con.execute("SELECT * FROM siniflar WHERE sinif_adi='7/A'").fetchone())
            cls.ogr_8a = dict(
                con.execute(
                    "SELECT o.*, s.sinif_adi, s.seviye FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/A' LIMIT 1"
                ).fetchone()
            )
            cls.ogr_8c = dict(
                con.execute(
                    "SELECT o.*, s.sinif_adi, s.seviye FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/C' LIMIT 1"
                ).fetchone()
            )
            cls.ogr_7a = dict(
                con.execute(
                    "SELECT o.*, s.sinif_adi, s.seviye FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='7/A' LIMIT 1"
                ).fetchone()
            )
            cls.ogretmen = dict(
                con.execute("SELECT id, ad_soyad, yetki FROM ogretmenler WHERE ad_soyad='ADEM AKGÜL'").fetchone()
            )
        finally:
            con.close()

    def test_migration_004_up_down_up(self):
        con = d._conn()
        try:
            migrate_up(con)
            row = con.execute("SELECT seviye FROM siniflar WHERE sinif_adi='8/A'").fetchone()
            self.assertEqual(row[0], 8)
            migrate_down(con, 3)
            row_down = con.execute("SELECT seviye FROM siniflar WHERE sinif_adi='8/A'").fetchone()
            self.assertIsNone(row_down[0])
            migrate_up(con)
            row_up = con.execute("SELECT seviye FROM siniflar WHERE sinif_adi='8/A'").fetchone()
            self.assertEqual(row_up[0], 8)
            con.execute("UPDATE siniflar SET seviye=8 WHERE sinif_adi='8/C'")
            con.commit()
        finally:
            con.close()

    def test_seviye_ve_aktif_moduller_8a_8b_8c(self):
        for s in (self.sinif_8a, self.sinif_8b, self.sinif_8c, "8/A", "8/B", "8/C"):
            self.assertEqual(seviye(s), 8)
            self.assertEqual(aktif_moduller(s), MODULLER[8])
            self.assertTrue(modul_var_mi(s, "lgs"))
            self.assertTrue(modul_var_mi(s, "deneme"))
            self.assertFalse(modul_var_mi(s, "kitap"))
            self.assertFalse(modul_var_mi(s, "haftalik_takip"))
        self.assertEqual(ogrenci_seviyesi(self.ogr_8c["id"]), 8)

    def test_seviye_ve_aktif_moduller_5_7(self):
        for s in (self.sinif_7a, "5/A", "6/B", "7/A"):
            self.assertIn(seviye(s), (5, 6, 7))
            self.assertEqual(aktif_moduller(s), MODULLER["diger"])
            self.assertTrue(modul_var_mi(s, "kitap"))
            self.assertTrue(modul_var_mi(s, "haftalik_takip"))
            self.assertTrue(modul_var_mi(s, "yaprak_test"))
            self.assertFalse(modul_var_mi(s, "lgs"))
            self.assertTrue(modul_var_mi(s, "deneme"))
            self.assertTrue(modul_var_mi(s, "evde_test"))

    def test_sekizinci_sinif_veli_kitap_odev_rapor_yonlendirme(self):
        client = w.app.test_client()
        with client.session_transaction() as sess:
            sess["veli_ogrenci_id"] = self.ogr_8a["id"]
        resp = client.get("/veli/kitap-odev-rapor")
        self.assertIn(resp.status_code, (301, 302))
        self.assertIn("/veli/lgs", resp.headers["Location"])

        # 8/C şubesi için de aynı davranış
        with client.session_transaction() as sess:
            sess["veli_ogrenci_id"] = self.ogr_8c["id"]
        resp_8c = client.get("/veli/kitap-odev-rapor")
        self.assertIn(resp_8c.status_code, (301, 302))
        self.assertIn("/veli/lgs", resp_8c.headers["Location"])
        resp_deneme_8c = client.get("/veli/deneme-analiz")
        self.assertEqual(resp_deneme_8c.status_code, 200)

    def test_yedinci_sinif_veli_deneme_ve_evde_soru(self):
        client = w.app.test_client()
        with client.session_transaction() as sess:
            sess["veli_ogrenci_id"] = self.ogr_7a["id"]
        resp = client.get("/veli/deneme-analiz")
        self.assertEqual(resp.status_code, 200)
        soru = client.get("/veli/lgs", query_string={"bolum": "soru"})
        self.assertEqual(soru.status_code, 200)
        self.assertIn("Sorular ve optik", soru.get_data(as_text=True))
        program = client.get("/veli/lgs", query_string={"bolum": "program"})
        self.assertIn(program.status_code, (301, 302))

        analiz_html = client.get("/veli/analizler").get_data(as_text=True)
        self.assertIn("Deneme analizini aç", analiz_html)
        self.assertIn("Okul yaprak testi", analiz_html)

    def test_ogretmen_8_sinif_analiz_ve_rapor_yonlendirme(self):
        client = w.app.test_client()
        with client.session_transaction() as sess:
            sess["ogretmen_id"] = self.ogretmen["id"]
            sess["ogretmen_adi"] = self.ogretmen["ad_soyad"]
            sess["ogretmen_yetki"] = self.ogretmen["yetki"]
        r1 = client.get(f"/kitap-odev-rapor?sinif={self.sinif_8a['id']}")
        self.assertIn(r1.status_code, (301, 302))
        self.assertIn("/lgs", r1.headers["Location"])

        r2 = client.get(f"/analiz?sinif_id={self.sinif_8c['id']}")
        self.assertIn(r2.status_code, (301, 302))
        self.assertIn("/lgs", r2.headers["Location"])


if __name__ == "__main__":
    unittest.main()
