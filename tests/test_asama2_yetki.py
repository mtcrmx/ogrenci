"""Aşama 2: Tek rol/yetki modeli testleri."""
import unittest
from test_app_workflows import w, d
from migrations import current_version, migrate_down, migrate_up
import lgs_optik as optik
import yetki


class Asama2YetkiTests(unittest.TestCase):
    def setUp(self):
        con = d._conn()
        try:
            migrate_up(con)
        finally:
            con.close()

    def test_migration_002_up_down_up_and_default_roles(self):
        con = d._conn()
        try:
            self.assertGreaterEqual(current_version(con), 2)
            adem = d.ogretmen_id_bul("ADEM AKGÜL")
            metehan = d.ogretmen_id_bul("METEHAN CÜCEN")
            alperen = d.ogretmen_id_bul("ALPEREN MURAT LEBLEBİCİ")

            for r in ("yonetici", "mudur", "toplu_sifirlama", "evrak_takip", "lgs_yonet"):
                self.assertTrue(yetki.yetkili(adem, r), f"Adem eksik yetki: {r}")
            self.assertFalse(yetki.yetkili(adem, "sayfa_sifirlama"))

            for r in ("yonetici", "mudur_yrd", "sayfa_sifirlama", "evrak_takip", "lgs_yonet"):
                self.assertTrue(yetki.yetkili(metehan, r), f"Metehan eksik yetki: {r}")
            self.assertFalse(yetki.yetkili(metehan, "toplu_sifirlama"))

            for r in ("lgs_yonet", "rehber"):
                self.assertTrue(yetki.yetkili(alperen, r), f"Alperen eksik yetki: {r}")
            self.assertFalse(yetki.yetkili(alperen, "yonetici"))

            # down(1) -> ogretmen_yetki tablosu silinir, tekrar up() ile geri gelir
            migrate_down(con, target=1)
            self.assertEqual(current_version(con), 1)
            migrate_up(con)
            self.assertGreaterEqual(current_version(con), 2)
            self.assertTrue(yetki.yetkili(adem, "yonetici"))
            self.assertTrue(yetki.yetkili(metehan, "sayfa_sifirlama"))
            self.assertTrue(yetki.yetkili(alperen, "lgs_yonet"))
        finally:
            con.close()

    def test_parametric_endpoints_match_previous_permissions(self):
        teachers = {t["ad_soyad"]: t for t in d.tum_ogretmenler()}
        adem = teachers["ADEM AKGÜL"]
        metehan = teachers["METEHAN CÜCEN"]
        alperen = teachers["ALPEREN MURAT LEBLEBİCİ"]
        normal = next(
            t for t in d.tum_ogretmenler()
            if t["ad_soyad"] not in ("ADEM AKGÜL", "METEHAN CÜCEN", "ALPEREN MURAT LEBLEBİCİ")
            and t.get("yetki") == "tam"
        )

        cases = [
            # (teacher, session_yetki, endpoint, method, expected_status)
            (adem, "tam", "/giris-raporu", "GET", 200),
            (metehan, "tam", "/giris-raporu", "GET", 200),
            (alperen, "rehber", "/giris-raporu", "GET", 302),
            (normal, "tam", "/giris-raporu", "GET", 403),
            (adem, "tam", "/yonetim/sinavlar", "GET", 200),
            (metehan, "tam", "/yonetim/sinavlar", "GET", 200),
            (normal, "tam", "/yonetim/sinavlar", "GET", 403),
            (adem, "tam", "/ogrenci-ara", "GET", 200),
            (metehan, "tam", "/ogrenci-ara", "GET", 200),
            (normal, "tam", "/ogrenci-ara", "GET", 403),
            (alperen, "rehber", "/rehberlik", "GET", 200),
            (normal, "tam", "/rehberlik", "GET", 403),
        ]

        for teacher, sess_yetki, url, method, expected in cases:
            with self.subTest(teacher=teacher["ad_soyad"], url=url):
                c = w.app.test_client()
                with c.session_transaction() as s:
                    s.update(
                        ogretmen_id=teacher["id"],
                        ogretmen_adi=teacher["ad_soyad"],
                        ogretmen_yetki=sess_yetki,
                    )
                resp = c.open(url, method=method)
                self.assertEqual(resp.status_code, expected)

        # Sayfa sıfırlama yalnız Metehan'a açık
        for teacher, expected in ((metehan, 200), (adem, 403), (normal, 403)):
            with self.subTest(sayfa_sifirla=teacher["ad_soyad"]):
                c = w.app.test_client()
                with c.session_transaction() as s:
                    s.update(
                        ogretmen_id=teacher["id"],
                        ogretmen_adi=teacher["ad_soyad"],
                        ogretmen_yetki="tam",
                    )
                resp = c.post(
                    "/api/sayfa-sifirla/onizle",
                    json={"sayfa": "dashboard", "kapsam": "okul"},
                )
                self.assertEqual(resp.status_code, expected)

        # Evde test sahipliği (lgs_yonet: Adem, Metehan, Alperen)
        fake_exam = {"id": 99999, "ogretmen_id": normal["id"], "kaynak": "ev"}
        for teacher, expected in ((adem, True), (metehan, True), (alperen, True)):
            with w.app.test_request_context("/lgs"):
                from flask import session
                session["ogretmen_id"] = teacher["id"]
                self.assertEqual(optik.teacher_can_view(fake_exam), expected)

    def test_titles_and_toolbar_come_from_db(self):
        self.assertEqual(yetki.ogretmen_unvani("ADEM AKGÜL"), "Müdür")
        self.assertEqual(yetki.ogretmen_unvani("METEHAN CÜCEN"), "Müdür Yardımcısı")
        self.assertEqual(yetki.ogretmen_unvani("METEHAN CÜCEN", True), "Müdür Yrd.")
        self.assertEqual(yetki.mudur_adi(), "ADEM AKGÜL")
        self.assertEqual(yetki.rehber_adi(), "Alperen Murat Leblebici")
