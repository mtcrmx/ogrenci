import unittest

from deneme_kurum import kurum_metin_oku, kurum_ogrenci_esle, _satir


_LGS = """
EDESİS · VİP LGS-1 LGS PUAN SIRALI LİSTE
Sınav Tarihi: 04.10.2026
1 YAĞMUR NİSA KOCA 8-B 16 4 14,67 10 0 10,00 10 0 10,00 9 1 8,67 17 3 16,00 19 1 18,67 81 9 78,01 449,50 953 1 1 1 6,59 4,29 3,73
13 ŞÜHEDABUĞLEMKARASL
ŞÜHEDABUĞLEMKARASL 8-B 10 9 7,00 5 4 3,67 8 2 7,33 5 2 4,33 7 7 4,67 6 12 2,00 41 36 29,00 268,23 4.764 29 13 9 51,29 50,18 40,91
24 NİSA ÇÖPATLAMAZ 7 13 2,67 3 7 0,67 6 4 4,67 2 8 -0,67 6 14 1,33 6 14 1,33 30 60 10,00 210,71 5.380 49 24 82,92 83,76 67,67
1 YAĞMUR NİSA KOCA 8-B 16 4 14,67 10 0 10,00 10 0 10,00 9 1 8,67 17 3 16,00 19 1 18,67 81 9 78,01 449,50 953 1 1 1 6,59 4,29 3,73
"""


class DenemeKurum(unittest.TestCase):
    def test_lgs_sirali_liste(self):
        liste = kurum_metin_oku(_LGS, "liste.pdf")
        self.assertEqual(liste["ad"], "VİP LGS-1")
        self.assertEqual(liste["tarih"], "2026-10-04")
        self.assertEqual([s["ad"] for s in liste["satirlar"]], [
            "YAĞMUR NİSA KOCA", "ŞÜHEDABUĞLEMKARASL", "NİSA ÇÖPATLAMAZ",
        ])
        yagmur = liste["satirlar"][0]
        self.assertEqual(yagmur["puan"], 449.5)
        self.assertEqual(yagmur["net"], 78.01)
        self.assertEqual(yagmur["dersler"][0], {
            "ders": "Türkçe", "dogru": 16, "yanlis": 4, "bos": 0, "net": 14.67,
        })
        self.assertEqual(yagmur["dersler"][1]["ders"], "T.C. İnkılap Tarihi")
        self.assertEqual(liste["satirlar"][2]["dersler"][3]["net"], -0.67)

    def test_eski_satir_duruyor(self):
        satir = (
            "1 0 - ALİ YILMAZ 12 / A "
            "10 2 9.33 5 1 4.67 5 1 4.67 5 1 4.67 10 2 9.33 10 2 9.33 45 9 40 350.125"
        )
        ogr = _satir(satir)
        self.assertEqual(ogr["ad"], "ALİ YILMAZ")
        self.assertEqual(ogr["dersler"][0]["ders"], "Türkçe")
        self.assertEqual(ogr["dersler"][1]["ders"], "Sosyal Bilgiler")
        self.assertEqual(ogr["puan"], 350.125)

    def test_yapisan_ad_eslesir(self):
        liste = kurum_metin_oku(_LGS)
        ogrenciler = [
            {"id": 1, "ad_soyad": "YAĞMUR NİSA KOCA"},
            {"id": 2, "ad_soyad": "ŞÜHEDA BUĞLEM KARASLAN"},
            {"id": 3, "ad_soyad": "NEHİR NİSA ÇÖPATLAMAZ"},
            {"id": 4, "ad_soyad": "ŞÜHEDA BUĞLEM KARASOY"},
        ]
        sonuc = kurum_ogrenci_esle(liste["satirlar"], ogrenciler)
        self.assertEqual(sonuc["eslesen"][1]["ogrenci_id"], 2)
        self.assertEqual(sonuc["eslesen"][2]["ad_soyad"], "NEHİR NİSA ÇÖPATLAMAZ")
        self.assertEqual(sonuc["kalan"], [])


if __name__ == "__main__":
    unittest.main()
