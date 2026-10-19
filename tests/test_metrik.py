"""Aşama 3 testleri: Tek hesap modülü (oran, net, götürme, topla) ve migration 003."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database as db
import lgs_optik as optik
import metrik
from migrations import current_version, migrate_down, migrate_up
from yaprak_analiz import combined_stats, summarize


class TestAsama3Metrik(unittest.TestCase):
    def test_oran_sifir_soru_none_doner(self):
        self.assertIsNone(metrik.oran(0, 0))
        self.assertIsNone(metrik.oran(5, 0))
        self.assertIsNone(metrik.oran(0, None))
        self.assertEqual(metrik.oran(15, 20), 75.0)
        self.assertEqual(metrik.oran(1, 3), 33.3)

    def test_net_kurallari(self):
        # 3 yanlış 1 doğruyu götürür (LGS varsayılan)
        self.assertEqual(metrik.net(15, 3, 3), 14.0)
        self.assertEqual(metrik.net(10, 2, 3), 9.33)
        # 4 yanlış 1 doğruyu götürür
        self.assertEqual(metrik.net(15, 4, 4), 14.0)
        self.assertEqual(metrik.net(10, 2, 4), 9.5)
        # 0: yanlış götürmez
        self.assertEqual(metrik.net(15, 5, 0), 15.0)

    def test_farkli_soru_sayili_iki_testin_birlestirilmesi(self):
        # 10 soruda 10 doğru (%100) + 100 soruda 0 doğru (%0) -> toplam 10/110 = %9.1 (oran ortalaması %50 DEĞİL!)
        satirlar = [
            {"dogru": 10, "yanlis": 0, "bos": 0, "soru_sayisi": 10, "net": 10.0, "rate": 100.0},
            {"dogru": 0, "yanlis": 0, "bos": 100, "soru_sayisi": 100, "net": 0.0, "rate": 0.0},
        ]
        ozet = metrik.topla(satirlar)
        self.assertEqual(ozet["toplam_dogru"], 10)
        self.assertEqual(ozet["toplam_soru"], 110)
        self.assertEqual(ozet["rate"], 9.1)

        yaprak_ozet = summarize(satirlar)
        self.assertEqual(yaprak_ozet["rate"], 9.1)

    def test_bos_sonuc_orani_none(self):
        self.assertIsNone(metrik.topla([])["rate"])
        self.assertIsNone(summarize([])["rate"])
        self.assertIsNone(combined_stats([])["rate"])

    def test_jinja_filtreleri(self):
        self.assertEqual(metrik.yuzde_filtre(None), "—")
        self.assertEqual(metrik.yuzde_filtre(75.0), "%75.0")
        self.assertEqual(metrik.net_filtre(None), "—")
        self.assertEqual(metrik.net_filtre(14.333), "14.33")

    def test_lgs_optik_goturme_kurali(self):
        p3 = optik.puan_hesapla(["A", "B", "C", "D"], ["A", "C", "D", "A"], goturme=3)
        self.assertEqual(p3["net"], 0.0)
        p4 = optik.puan_hesapla(["A", "B", "C", "D"], ["A", "C", "D", "A"], goturme=4)
        self.assertEqual(p4["net"], 0.25)
        p0 = optik.puan_hesapla(["A", "B", "C", "D"], ["A", "C", "D", "A"], goturme=0)
        self.assertEqual(p0["net"], 1.0)

    def test_migration_003_up_down_up(self):
        tmp = tempfile.mkdtemp(prefix="mig003-")
        try:
            copy_db = Path(tmp) / "test.db"
            shutil.copy2(db.DB_PATH, copy_db)
            con = sqlite3.connect(copy_db)
            con.row_factory = sqlite3.Row
            migrate_up(con, target=3)
            self.assertGreaterEqual(current_version(con), 3)
            cols = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
            self.assertIn("yanlis_goturme", cols)
            self.assertIn("secenekler", cols)
            migrate_down(con, target=2)
            self.assertEqual(current_version(con), 2)
            migrate_up(con, target=3)
            self.assertEqual(current_version(con), 3)
            con.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
