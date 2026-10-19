"""
scripts/db_yedek.py
-------------------
Canlı veya yerel SQLite veritabanının online yedeğini alır ve doğrular.
Kullanım:
    python scripts/db_yedek.py [hedef_dosya_yolu]
"""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import database as db


def yedek_al(hedef_yol: str | None = None) -> str:
    kaynak_yol = db._resolve_db_path()
    if not os.path.exists(kaynak_yol):
        raise FileNotFoundError(f"Veritabanı dosyası bulunamadı: {kaynak_yol}")

    tarih = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not hedef_yol:
        yedek_klasor = os.environ.get("OGR_TAKIP_DATA_DIR") or str(ROOT_DIR / "backups")
        os.makedirs(yedek_klasor, exist_ok=True)
        hedef_yol = os.path.join(yedek_klasor, f"yedek_{tarih}.db")
    else:
        parent = os.path.dirname(os.path.abspath(hedef_yol))
        if parent:
            os.makedirs(parent, exist_ok=True)

    src_con = sqlite3.connect(kaynak_yol)
    dst_con = sqlite3.connect(hedef_yol)
    try:
        with dst_con:
            src_con.backup(dst_con)
    finally:
        dst_con.close()
        src_con.close()

    # Yedeğin açılabildiğini ve bütünlüğünü doğrula
    kontrol_con = sqlite3.connect(hedef_yol)
    try:
        integrity = kontrol_con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Yedek bütünlük kontrolü başarısız: {integrity}")
        tablo_sayisi = kontrol_con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    finally:
        kontrol_con.close()

    print(f"OK: Yedek alindi: {hedef_yol} ({tablo_sayisi} tablo, integrity=ok)")
    return os.path.abspath(hedef_yol)


if __name__ == "__main__":
    hedef = sys.argv[1] if len(sys.argv) > 1 else None
    yedek_al(hedef)
