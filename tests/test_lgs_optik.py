import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("OGR_TAKIP_DB_PATH", str(Path(tempfile.gettempdir()) / "optik-unit.db"))

from lgs_optik import anahtar_oku, puan_hesapla


class OptikHesap(unittest.TestCase):
    def test_anahtar_ve_net(self):
        self.assertEqual(anahtar_oku("a b, c d"), ["A", "B", "C", "D"])
        self.assertIsNone(anahtar_oku(""))
        self.assertEqual(anahtar_oku("E"), ["E"])
        puan = puan_hesapla(["A", "B", "C", "D"], ["A", "A", "C", ""])
        self.assertEqual((puan["dogru"], puan["yanlis"], puan["bos"], puan["net"]), (2, 1, 1, 1.67))
