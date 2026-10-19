"""Aşama 1: Güvenlik testleri (hash geçişi, /admin/sifreler, fail-closed, deneme sınırı)."""
import os
import unittest
from unittest.mock import patch
from werkzeug.security import check_password_hash, generate_password_hash

from test_app_workflows import w, d
from migrations import current_version, migrate_down, migrate_up


class Asama1GuvenlikTests(unittest.TestCase):
    def tearDown(self):
        con = d._conn()
        try:
            con.execute("DELETE FROM yonetici_login_attempt")
            con.commit()
        except Exception:
            pass
        finally:
            con.close()

    def test_migration_001_up_down_up_and_existing_passwords(self):
        con = d._conn()
        try:
            migrate_up(con)
            self.assertGreaterEqual(current_version(con), 1)
            all_rows = con.execute("SELECT id, ad_soyad, sifre, sifre_hash FROM ogretmenler WHERE sifre != ''").fetchall()
            rows = [r for r in all_rows if r["ad_soyad"] not in d._AYRILAN_OGRETMENLER]
            self.assertGreater(len(rows), 0)
            for r in rows:
                self.assertTrue((r["sifre_hash"] or "").strip())
                self.assertTrue(check_password_hash(r["sifre_hash"], r["sifre"]))

            # down() yalnız sifre_hash'i boşaltır, sifre sütununa dokunmaz
            migrate_down(con, target=0)
            self.assertEqual(current_version(con), 0)
            rows_after_down = [
                r for r in con.execute("SELECT id, ad_soyad, sifre, sifre_hash FROM ogretmenler WHERE sifre != ''").fetchall()
                if r["ad_soyad"] not in d._AYRILAN_OGRETMENLER
            ]
            self.assertEqual(len(rows_after_down), len(rows))
            for r in rows_after_down:
                self.assertFalse((r["sifre_hash"] or "").strip())
                self.assertTrue((r["sifre"] or "").strip())

            # Eski şifreyle ilk girişte otomatik hash'e geçiş (geçiş dönemi)
            ornek = rows_after_down[0]
            self.assertTrue(d.ogretmen_dogrula(ornek["ad_soyad"], ornek["sifre"]))
            guncel = con.execute("SELECT sifre_hash FROM ogretmenler WHERE id = ?", (ornek["id"],)).fetchone()
            self.assertTrue((guncel["sifre_hash"] or "").strip())
            self.assertTrue(check_password_hash(guncel["sifre_hash"], ornek["sifre"]))

            # Tekrar up() çalıştırıldığında tüm öğretmenler hash ile girebilir
            migrate_up(con)
            self.assertGreaterEqual(current_version(con), 1)
            for r in rows:
                self.assertTrue(d.ogretmen_dogrula(r["ad_soyad"], r["sifre"]))
                self.assertFalse(d.ogretmen_dogrula(r["ad_soyad"], r["sifre"] + "-yanlis"))
        finally:
            con.close()

    def test_admin_forms_fail_closed_when_env_missing(self):
        client = w.app.test_client()
        env_clear = {
            "ADMIN_SIFRE_HASH": "",
            "YONETICI_PASSWORD_HASH": "",
        }
        with patch.dict(os.environ, env_clear, clear=False):
            self.assertEqual(client.get("/admin/sifreler").status_code, 403)
            self.assertEqual(client.post("/admin/sifreler", data={"admin_sifre": "ECadmin"}).status_code, 403)
            self.assertEqual(client.post("/admin/yedek-onay", data={"admin_sifre": "ECadmin"}).status_code, 403)
            self.assertEqual(client.get("/yonetici/giris").status_code, 403)
            self.assertEqual(client.post("/yonetici/giris", data={"username": "yonetici", "password": "EC200"}).status_code, 403)

    def test_admin_sifreler_never_exposes_passwords_and_resets_once(self):
        con = d._conn()
        try:
            teachers = [dict(r) for r in con.execute("SELECT id, ad_soyad, sifre FROM ogretmenler WHERE sifre != ''").fetchall()]
            target = teachers[-1]
            eski_sifre = target["sifre"]
        finally:
            con.close()

        # tum_sifre_listesi() hiçbir zaman sifre alanı döndürmemeli
        for item in d.tum_sifre_listesi():
            self.assertNotIn("sifre", item)

        admin_parola = "GucluAdminParolasi2026!"
        admin_hash = generate_password_hash(admin_parola)
        client = w.app.test_client()
        with patch.dict(os.environ, {"ADMIN_SIFRE_HASH": admin_hash}):
            resp = client.post("/admin/sifreler", data={"admin_sifre": admin_parola})
            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)
            for t in teachers:
                if t["sifre"]:
                    self.assertNotIn(f">{t['sifre']}<", html)

            # Öğretmen şifresini sıfırla: yeni geçici şifre bir kez gösterilir, sadece hash saklanır
            reset_resp = client.post(
                "/admin/sifreler",
                data={"admin_sifre": admin_parola, "ogretmen_id": target["id"]},
            )
            self.assertEqual(reset_resp.status_code, 200)
            reset_html = reset_resp.get_data(as_text=True)
            self.assertIn(target["ad_soyad"], reset_html)

            con = d._conn()
            try:
                row = con.execute(
                    "SELECT sifre, sifre_hash FROM ogretmenler WHERE id = ?",
                    (target["id"],),
                ).fetchone()
                # Veritabanında düz metin şifre boşaltılmış, yalnız hash saklanmış olmalı
                self.assertEqual(row["sifre"], "")
                self.assertTrue((row["sifre_hash"] or "").strip())
                # Eski şifre artık geçersiz
                self.assertFalse(d.ogretmen_dogrula(target["ad_soyad"], eski_sifre))

                # Testin diğer testleri etkilememesi için eski şifreyi geri yükle
                con.execute(
                    "UPDATE ogretmenler SET sifre = ?, sifre_hash = ? WHERE id = ?",
                    (eski_sifre, generate_password_hash(eski_sifre), target["id"]),
                )
                con.commit()
            finally:
                con.close()

    def test_admin_sifreler_rate_limit(self):
        admin_parola = "DogruAdminParola!"
        admin_hash = generate_password_hash(admin_parola)
        client = w.app.test_client()
        with patch.dict(os.environ, {"ADMIN_SIFRE_HASH": admin_hash}):
            for _ in range(5):
                r = client.post("/admin/sifreler", data={"admin_sifre": "yanlis-parola"})
                self.assertEqual(r.status_code, 200)
                self.assertIn("hatalı", r.get_data(as_text=True))
            # 5 hatalı denemeden sonra doğru şifre de blok süresi boyunca reddedilir
            blocked_resp = client.post("/admin/sifreler", data={"admin_sifre": admin_parola})
            self.assertIn("hatalı", blocked_resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
