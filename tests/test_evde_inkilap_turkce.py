import json
import unittest
from pathlib import Path

from migrations import load_migration_module
from test_app_workflows import d

_MOD = load_migration_module(Path(__file__).resolve().parents[1] / "migrations" / "009_evde_test_birlestir.py")


def _ekle(con, ad, tur, ders, sinif_id, ogretmen, cevaplar):
    cur = con.execute(
        """
        INSERT INTO lgs_optik_sinav
            (ad, tarih, pdf_dosya, cevaplar, soru_sayisi, ogretmen_id, olusturma, tur, ders, sinif_id, yanlis_goturme, secenekler, kaynak)
        VALUES (?, '2026-10-18', 'ayir.pdf', ?, ?, ?, '2026-10-18', ?, ?, ?, 3, 'ABCD', ?)
        """,
        (ad, json.dumps(cevaplar), len(cevaplar), ogretmen, tur, ders, sinif_id, "ev" if tur == "deneme" else "ev_yaprak"),
    )
    return int(cur.lastrowid)


class FundaVeTurkce(unittest.TestCase):
    def test_funda_inkilap_olarak_kalir_turkce_birlesir(self):
        con = d._conn()
        ogretmenler = [(int(r[0]), r[1] or "") for r in con.execute("SELECT id, ad_soyad FROM ogretmenler")]
        funda = next(oid for oid, ad in ogretmenler if _MOD._funda(ad))
        diger = next(oid for oid, ad in ogretmenler if oid != funda)
        sinif_a = con.execute("SELECT id FROM siniflar WHERE sinif_adi='8/A'").fetchone()[0]
        sinif_b = con.execute("SELECT id FROM siniflar WHERE sinif_adi='8/B'").fetchone()[0]
        ogr_a = con.execute("SELECT id FROM ogrenciler WHERE sinif_id=? LIMIT 1", (sinif_a,)).fetchone()[0]
        ogr_b = con.execute("SELECT id FROM ogrenciler WHERE sinif_id=? LIMIT 1", (sinif_b,)).fetchone()[0]
        funda_id = _ekle(con, "Funda deneme kaydı", "deneme", "", sinif_a, funda, ["A", "B"])
        turkce_a = _ekle(con, "Paragraf 8/A", "yaprak", "Türkçe", sinif_a, diger, ["A", "C", "D"])
        turkce_b = _ekle(con, "Paragraf 8/B", "yaprak", "Türkçe", sinif_b, diger, ["A", "C", "D"])
        mate_a = _ekle(con, "Üslü 8/A", "yaprak", "Matematik", sinif_a, diger, ["B", "B"])
        mate_b = _ekle(con, "Üslü 8/B", "yaprak", "Matematik", sinif_b, diger, ["B", "B"])
        con.execute(
            "INSERT INTO lgs_optik_sonuc (sinav_id, ogrenci_id, isaretler, dogru, yanlis, bos, net, zaman) VALUES (?,?,?,?,?,?,?,?)",
            (turkce_a, ogr_a, '["A"]', 1, 0, 0, 1, "2026-10-18 20:00"),
        )
        con.execute(
            "INSERT INTO lgs_optik_sonuc (sinav_id, ogrenci_id, isaretler, dogru, yanlis, bos, net, zaman) VALUES (?,?,?,?,?,?,?,?)",
            (turkce_b, ogr_b, '["C"]', 0, 1, 0, 0, "2026-10-18 20:00"),
        )
        con.commit()
        try:
            _MOD.up(con)
            funda_kayit = con.execute(
                "SELECT tur, ders, sinif_id, kaynak, silindi_at FROM lgs_optik_sinav WHERE id=?",
                (funda_id,),
            ).fetchone()
            self.assertEqual(funda_kayit[0], "yaprak")
            self.assertEqual(funda_kayit[1], "T.C. İnkılap Tarihi")
            self.assertEqual(funda_kayit[2], sinif_a)
            self.assertEqual(funda_kayit[3], "ev_yaprak")
            self.assertFalse(funda_kayit[4])
            kalan = [
                dict(id=r[0], sinif_id=r[1], ders=r[2], silindi=r[3])
                for r in con.execute(
                    "SELECT id, sinif_id, ders, silindi_at FROM lgs_optik_sinav WHERE id IN (?,?)",
                    (turkce_a, turkce_b),
                )
            ]
            acik = [r for r in kalan if not r["silindi"]]
            kapali = [r for r in kalan if r["silindi"]]
            self.assertEqual(len(acik), 1)
            self.assertEqual(len(kapali), 1)
            self.assertIsNone(acik[0]["sinif_id"])
            self.assertEqual(acik[0]["ders"], "Türkçe")
            self.assertNotEqual(acik[0]["id"], funda_id)
            cozen = {
                r[0] for r in con.execute(
                    "SELECT ogrenci_id FROM lgs_optik_sonuc WHERE sinav_id=?",
                    (acik[0]["id"],),
                )
            }
            self.assertEqual(cozen, {ogr_a, ogr_b})
            mate = con.execute(
                "SELECT sinif_id, silindi_at FROM lgs_optik_sinav WHERE id IN (?,?) ORDER BY id",
                (mate_a, mate_b),
            ).fetchall()
            self.assertEqual([r[0] for r in mate], [sinif_a, sinif_b])
            self.assertFalse(mate[0][1] or mate[1][1])
        finally:
            ids = (funda_id, turkce_a, turkce_b, mate_a, mate_b)
            yer = ",".join("?" * len(ids))
            con.execute(f"DELETE FROM lgs_optik_sonuc WHERE sinav_id IN ({yer})", ids)
            con.execute(f"DELETE FROM lgs_optik_sinav WHERE id IN ({yer})", ids)
            con.commit()
            con.close()
