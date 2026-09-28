"""Kurum deneme PDF listesini (puan sıralı) öğrenci sonuçlarına çevirir."""
from __future__ import annotations

import re
from datetime import date

_TABLO = str.maketrans("ıİiIşŞğĞüÜöÖçÇ", "iIiIsSgGuUoOcC")
_DERSLER = (
    ("Türkçe", 20),
    ("Sosyal Bilgiler", 10),
    ("Din Kültürü", 10),
    ("İngilizce", 10),
    ("Matematik", 20),
    ("Fen Bilimleri", 20),
)


def _harf(metin: str) -> str:
    return re.sub(r"[^a-z]", "", (metin or "").translate(_TABLO).lower())


def kurum_pdf_oku(veri: bytes, dosya_adi: str = "") -> dict:
    from pypdf import PdfReader
    from io import BytesIO

    metin = "\n".join((sayfa.extract_text() or "") for sayfa in PdfReader(BytesIO(veri)).pages)
    ad = _sinav_adi(metin)
    tarih = _tarih(dosya_adi, metin)
    satirlar = []
    for satir in metin.splitlines():
        ogr = _satir(satir)
        if ogr:
            satirlar.append(ogr)
    return {"ad": ad, "tarih": tarih, "satirlar": satirlar}


def kurum_ogrenci_esle(satirlar: list[dict], ogrenciler: list[dict]) -> dict:
    indeks: dict[str, list[dict]] = {}
    for ogr in ogrenciler:
        indeks.setdefault(_harf(ogr["ad_soyad"]), []).append(ogr)
    eslesen = []
    kalan = []
    for satir in satirlar:
        bulunan = _bul(satir["ad"], indeks, ogrenciler)
        if len(bulunan) == 1:
            eslesen.append({**satir, "ogrenci_id": int(bulunan[0]["id"]), "ad_soyad": bulunan[0]["ad_soyad"]})
        else:
            kalan.append(satir["ad"])
    return {"eslesen": eslesen, "kalan": kalan}


def _sinav_adi(metin: str) -> str:
    seviye = re.search(r"(\d+)\.\s*SINIF", metin, re.I)
    izleme = re.search(r"İZLEME\s*--\s*(\d+)", metin, re.I)
    if seviye and "İZLEME" in metin.upper():
        no = f" {izleme.group(1)}" if izleme else ""
        return f"{seviye.group(1)}. Sınıf Süreç İzleme{no}"[:80]
    m = re.search(r"(\d+)\.\s*SINIF\s+(.+?)\s+\d{3,}", metin, re.I)
    if not m:
        return "Kurum denemesi"
    baslik = re.sub(r"\s+", " ", m.group(2).replace("--", " ")).strip()
    return f"{m.group(1)}. Sınıf {baslik}"[:80]


def _tarih(dosya_adi: str, metin: str) -> str:
    m = re.search(r"(\d{2})[-_.](\d{2})[-_.](\d{4})", dosya_adi or "")
    if m:
        gun, ay, yil = m.groups()
        try:
            return date(int(yil), int(ay), int(gun)).isoformat()
        except ValueError:
            pass
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", metin)
    if m:
        gun, ay, yil = m.groups()
        try:
            return date(int(yil), int(ay), int(gun)).isoformat()
        except ValueError:
            pass
    return date.today().isoformat()


def _satir(satir: str) -> dict | None:
    m = re.match(
        r"^\d+\s+0\s+-\s+(.+?)\s+(\d+)\s*/\s*[A-ZÇĞİÖŞÜ]\s+(.+)$",
        satir.strip(),
    )
    if not m:
        return None
    sayilar = re.findall(r"-?\d+(?:\.\d+)?", m.group(3))
    if len(sayilar) < 22:
        return None
    dersler = []
    for i, (ders, tavan) in enumerate(_DERSLER):
        dogru = int(float(sayilar[i * 3]))
        yanlis = int(float(sayilar[i * 3 + 1]))
        net = round(float(sayilar[i * 3 + 2]), 2)
        bos = max(0, tavan - dogru - yanlis)
        dersler.append({"ders": ders, "dogru": dogru, "yanlis": yanlis, "bos": bos, "net": net})
    return {
        "ad": m.group(1).strip(),
        "dersler": dersler,
        "puan": round(float(sayilar[21]), 3),
        "net": round(sum(d["net"] for d in dersler), 2),
    }


def _bul(ad: str, indeks: dict[str, list[dict]], ogrenciler: list[dict]) -> list[dict]:
    if "*" not in ad:
        tam = indeks.get(_harf(ad), [])
        if len(tam) == 1:
            return tam
    else:
        parcalar = [_harf(p) for p in re.split(r"\*+", ad) if _harf(p)]
        if sum(len(p) for p in parcalar) >= 6:
            desen = re.compile(".*".join(re.escape(p) for p in parcalar))
            tam = [ogr for ogr in ogrenciler if desen.search(_harf(ogr["ad_soyad"]))]
            if len(tam) == 1:
                return tam
        else:
            tam = []
    return _yakin(ad, ogrenciler)


def _kelime(ad: str) -> list[str]:
    return [k for k in (_harf(p) for p in re.split(r"[\s*]+", ad)) if len(k) >= 3]


def _kelime_uyar(pdf_kelime: str, ogr_kelime: str) -> bool:
    if pdf_kelime == ogr_kelime:
        return True
    if len(pdf_kelime) >= 4 and (ogr_kelime.startswith(pdf_kelime) or pdf_kelime.startswith(ogr_kelime)):
        return True
    if len(pdf_kelime) >= 3 and (ogr_kelime.endswith(pdf_kelime) or pdf_kelime.endswith(ogr_kelime)):
        return True
    return False


def _yakin(ad: str, ogrenciler: list[dict]) -> list[dict]:
    parcalar = _kelime(ad)
    if len(parcalar) < 2:
        return []
    aday = []
    for ogr in ogrenciler:
        ok = _kelime(ogr["ad_soyad"])
        if not any(_kelime_uyar(parcalar[-1], k) for k in ok):
            continue
        tutan = sum(1 for p in parcalar if any(_kelime_uyar(p, k) for k in ok))
        if tutan >= max(2, len(parcalar) - 1):
            aday.append(ogr)
    return aday if len(aday) == 1 else []
