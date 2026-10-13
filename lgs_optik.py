"""LGS soru PDF'i ve optik formu."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import database as db

SECENEKLER = frozenset("ABCD")
AZAMI_SORU = 90
AZAMI_BOYUT = 20 * 1024 * 1024


def klasor() -> Path:
    yol = Path(db.DB_PATH).parent / "lgs-optik"
    yol.mkdir(parents=True, exist_ok=True)
    return yol


def _init(con) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS lgs_optik_sinav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            tarih TEXT NOT NULL,
            pdf_dosya TEXT NOT NULL,
            cevaplar TEXT NOT NULL,
            soru_sayisi INTEGER NOT NULL,
            ogretmen_id INTEGER,
            olusturma TEXT NOT NULL,
            tur TEXT NOT NULL DEFAULT 'deneme'
        );
        CREATE TABLE IF NOT EXISTS lgs_optik_sonuc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinav_id INTEGER NOT NULL,
            ogrenci_id INTEGER NOT NULL,
            isaretler TEXT NOT NULL,
            dogru INTEGER NOT NULL,
            yanlis INTEGER NOT NULL,
            bos INTEGER NOT NULL,
            net REAL NOT NULL,
            zaman TEXT NOT NULL,
            UNIQUE(sinav_id, ogrenci_id)
        );
        """
    )
    kolon = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
    if "tur" not in kolon:
        con.execute("ALTER TABLE lgs_optik_sinav ADD COLUMN tur TEXT NOT NULL DEFAULT 'deneme'")
    if "ders" not in kolon:
        con.execute("ALTER TABLE lgs_optik_sinav ADD COLUMN ders TEXT NOT NULL DEFAULT ''")
    if "sinif_id" not in kolon:
        con.execute("ALTER TABLE lgs_optik_sinav ADD COLUMN sinif_id INTEGER")


def anahtar_oku(metin: str) -> list[str] | None:
    harfler = re.findall(r"[A-Da-d]", metin or "")
    if not 1 <= len(harfler) <= AZAMI_SORU:
        return None
    return [h.upper() for h in harfler]


def puan_hesapla(anahtar: list[str], isaretler: list[str]) -> dict:
    dogru = yanlis = bos = 0
    satirlar = []
    for i, dogru_harf in enumerate(anahtar):
        verilen = isaretler[i] if i < len(isaretler) else ""
        if verilen not in SECENEKLER:
            verilen = ""
            bos += 1
            durum = "bos"
        elif verilen == dogru_harf:
            dogru += 1
            durum = "dogru"
        else:
            yanlis += 1
            durum = "yanlis"
        satirlar.append({"no": i + 1, "verilen": verilen, "dogru": dogru_harf, "durum": durum})
    return {
        "dogru": dogru,
        "yanlis": yanlis,
        "bos": bos,
        "net": round(dogru - yanlis / 3, 2),
        "satirlar": satirlar,
    }


def sinav_ekle(ad: str, tarih: str, pdf_adi: str, anahtar: list[str], ogretmen_id: int | None, tur: str = "deneme", ders: str = "", sinif_id: int | None = None) -> int:
    if tur not in ("yaprak", "deneme"):
        tur = "deneme"
    con = db._conn()
    _init(con)
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur = con.execute(
        """
        INSERT INTO lgs_optik_sinav (ad, tarih, pdf_dosya, cevaplar, soru_sayisi, ogretmen_id, olusturma, tur, ders, sinif_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ((ad or "LGS soruları")[:80], (tarih or "")[:10], pdf_adi, json.dumps(anahtar), len(anahtar), ogretmen_id, simdi, tur, (ders or "")[:40], sinif_id),
    )
    con.commit()
    sinav_id = int(cur.lastrowid)
    con.close()
    return sinav_id


def sinavlari_listele() -> list[dict]:
    con = db._conn()
    _init(con)
    rows = [dict(r) for r in con.execute(
        """
        SELECT o.*, s.sinif_adi
        FROM lgs_optik_sinav o
        LEFT JOIN siniflar s ON s.id = o.sinif_id
        ORDER BY o.tarih DESC, o.id DESC
        """
    )]
    con.close()
    for row in rows:
        row["cevaplar"] = json.loads(row["cevaplar"])
    return rows


def sinav_getir(sinav_id: int) -> dict | None:
    con = db._conn()
    _init(con)
    row = con.execute("SELECT * FROM lgs_optik_sinav WHERE id=?", (int(sinav_id),)).fetchone()
    con.close()
    if not row:
        return None
    kayit = dict(row)
    kayit["cevaplar"] = json.loads(kayit["cevaplar"])
    return kayit


def pdf_yolu(sinav: dict) -> Path | None:
    ad = Path(sinav.get("pdf_dosya") or "").name
    if not ad or ad != sinav.get("pdf_dosya"):
        return None
    yol = klasor() / ad
    return yol if yol.is_file() else None


def sonuc_getir(sinav_id: int, ogrenci_id: int) -> dict | None:
    con = db._conn()
    _init(con)
    row = con.execute(
        "SELECT * FROM lgs_optik_sonuc WHERE sinav_id=? AND ogrenci_id=?",
        (int(sinav_id), int(ogrenci_id)),
    ).fetchone()
    con.close()
    if not row:
        return None
    kayit = dict(row)
    kayit["isaretler"] = json.loads(kayit["isaretler"])
    return kayit


def sonuc_kaydet(sinav_id: int, ogrenci_id: int, isaretler: list[str]) -> dict:
    sinav = sinav_getir(sinav_id)
    if not sinav:
        return {"ok": False, "hata": "Sınav bulunamadı."}
    if sonuc_getir(sinav_id, ogrenci_id):
        return {"ok": False, "hata": "Bu optik daha önce bitirilmiş."}
    temiz = [(h if h in SECENEKLER else "") for h in isaretler]
    if len(temiz) < len(sinav["cevaplar"]):
        temiz += [""] * (len(sinav["cevaplar"]) - len(temiz))
    temiz = temiz[: len(sinav["cevaplar"])]
    puan = puan_hesapla(sinav["cevaplar"], temiz)
    con = db._conn()
    _init(con)
    con.execute(
        """
        INSERT INTO lgs_optik_sonuc (sinav_id, ogrenci_id, isaretler, dogru, yanlis, bos, net, zaman)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(sinav_id),
            int(ogrenci_id),
            json.dumps(temiz),
            puan["dogru"],
            puan["yanlis"],
            puan["bos"],
            puan["net"],
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )
    con.commit()
    con.close()
    return {"ok": True, **puan}


def cozen_ogrenciler(sinav_id: int) -> list[dict]:
    """Her bitiren öğrencinin soru soru doğru, yanlış ve boş dökümü."""
    sinav = sinav_getir(sinav_id)
    if not sinav:
        return []
    cikti = []
    for row in sinav_sonuclari(sinav_id):
        isaret = row["isaretler"]
        if isinstance(isaret, str):
            isaret = json.loads(isaret)
        puan = puan_hesapla(sinav["cevaplar"], isaret)
        cikti.append({
            "id": row["ogrenci_id"],
            "ad": row["ad_soyad"],
            "no": row["ogr_no"],
            "sinif": row["sinif_adi"],
            "dogru": puan["dogru"],
            "yanlis": puan["yanlis"],
            "bos": puan["bos"],
            "net": puan["net"],
            "satirlar": puan["satirlar"],
        })
    return cikti


def sinav_sonuclari(sinav_id: int) -> list[dict]:
    con = db._conn()
    _init(con)
    rows = [
        dict(r)
        for r in con.execute(
            """
            SELECT r.*, o.ad_soyad, o.ogr_no, s.sinif_adi
            FROM lgs_optik_sonuc r
            JOIN ogrenciler o ON o.id = r.ogrenci_id
            JOIN siniflar s ON s.id = o.sinif_id
            WHERE r.sinav_id=?
            ORDER BY r.net DESC, o.ad_soyad
            """,
            (int(sinav_id),),
        )
    ]
    con.close()
    return rows
