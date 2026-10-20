import unittest
from test_app_workflows import w, d
import lgs_ranking
from metrik import birlesik_sonuclar, kaynak_ozeti


class TestBirlesikSonuclar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        w.app.config["TESTING"] = True
        con = d._conn()
        d._lgs_init(con)
        try:
            cls.ogr5 = dict(con.execute(
                "SELECT o.id, o.sinif_id FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='5/B' ORDER BY o.id LIMIT 1").fetchone())
            cls.ogr8 = dict(con.execute(
                "SELECT o.id, o.sinif_id FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='8/B' ORDER BY o.id LIMIT 1").fetchone())
            cls.sinavlar = []
            for oid, sid in ((cls.ogr5["id"], cls.ogr5["sinif_id"]), (cls.ogr8["id"], cls.ogr8["sinif_id"])):
                for kaynak, tur, silindi in (("ev_yaprak", "yaprak", None), ("kamera", "yaprak", None), ("ev", "deneme", None), ("ev_yaprak", "yaprak", "2026-01-01")):
                    cur = con.execute(
                        "INSERT INTO lgs_optik_sinav (ad, tarih, pdf_dosya, cevaplar, soru_sayisi, olusturma, tur, ders, sinif_id, kaynak, silindi_at) "
                        "VALUES (?, '2026-10-01', '', '[\"A\",\"B\",\"C\",\"D\"]', 4, '2026-10-01', ?, 'Matematik', ?, ?, ?)",
                        (f"BS {kaynak} {tur}", tur, sid, kaynak, silindi),
                    )
                    cls.sinavlar.append(cur.lastrowid)
                    con.execute(
                        "INSERT INTO lgs_optik_sonuc (sinav_id, ogrenci_id, isaretler, dogru, yanlis, bos, net, zaman) "
                        "VALUES (?, ?, '[]', 3, 1, 0, 3, '2026-10-02 10:00')",
                        (cur.lastrowid, oid),
                    )
                for tur in ("ders", "deneme"):
                    cur = con.execute("INSERT INTO lgs_deneme (ogrenci_id, ad, tarih, tur) VALUES (?, ?, '2026-10-03', ?)", (oid, f"BS {tur}", tur))
                    con.execute(
                        "INSERT INTO lgs_deneme_ders (deneme_id, ders, soru_sayisi, dogru, yanlis, bos, net, yanlis_goturme) "
                        "VALUES (?, 'Türkçe', 10, 6, 2, 2, 6, 0)",
                        (cur.lastrowid,),
                    )
            con.commit()
        finally:
            con.close()

    @classmethod
    def tearDownClass(cls):
        con = d._conn()
        try:
            yer = ",".join("?" * len(cls.sinavlar))
            con.execute(f"DELETE FROM lgs_optik_sonuc WHERE sinav_id IN ({yer})", cls.sinavlar)
            con.execute(f"DELETE FROM lgs_optik_sinav WHERE id IN ({yer})", cls.sinavlar)
            con.execute("DELETE FROM lgs_deneme_ders WHERE deneme_id IN (SELECT id FROM lgs_deneme WHERE ad LIKE 'BS %')")
            con.execute("DELETE FROM lgs_deneme WHERE ad LIKE 'BS %'")
            con.commit()
        finally:
            con.close()

    def _satirlar(self, oid):
        con = d._conn()
        try:
            return [s for s in birlesik_sonuclar(con, [oid]) if s["ad"].startswith("BS ")]
        finally:
            con.close()

    def test_5_7_uc_kaynak_ve_silinen_haric(self):
        satirlar = self._satirlar(self.ogr5["id"])
        kaynaklar = sorted(s["kaynak"] for s in satirlar)
        self.assertEqual(kaynaklar, ["deneme", "deneme", "evde", "yaprak", "yaprak"])
        ozet = {k["kod"]: k for k in kaynak_ozeti(satirlar, 5)}
        self.assertEqual(set(ozet), {"evde", "deneme", "yaprak"})
        self.assertEqual(ozet["evde"]["kayit"], 1)

    def test_8_yaprak_yok_deneme_sayilir(self):
        satirlar = self._satirlar(self.ogr8["id"])
        self.assertEqual(sorted(s["kaynak"] for s in satirlar), ["deneme", "deneme", "deneme", "deneme", "evde"])
        self.assertEqual([k["kod"] for k in kaynak_ozeti(satirlar, 8)], ["evde", "deneme"])

    def test_siralama_tum_kaynaklari_sayar(self):
        con = d._conn()
        try:
            veri = lgs_ranking.build(con, {}, own_id=self.ogr5["id"])
            veri_evde = lgs_ranking.build(con, {"sr_kaynak": "evde"}, own_id=self.ogr5["id"])
        finally:
            con.close()
        self.assertEqual(veri["level"], 5)
        benim = next(r for r in veri["rows"] if r["kendi"])
        self.assertGreaterEqual(benim["test"], 5)
        self.assertIn("yaprak", veri["sources"])
        benim_evde = next(r for r in veri_evde["rows"] if r["kendi"])
        self.assertLess(benim_evde["test"], benim["test"])
        self.assertTrue(all(r["ad"].startswith("Öğrenci ") for r in veri["rows"] if not r["kendi"]))

    def test_veli_sonuc_sayfasi_evde_soruyu_gosterir(self):
        client = w.app.test_client()
        with client.session_transaction() as sess:
            sess["veli_ogrenci_id"] = self.ogr5["id"]
        html = client.get("/veli/sonuclar").get_data(as_text=True)
        self.assertIn("Sonuç özeti", html)
        self.assertIn("Evde soru · optik", html)
        self.assertIn("lgs-siralama", html)


if __name__ == "__main__":
    unittest.main()
