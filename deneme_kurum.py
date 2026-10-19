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
_LGS_DERSLER = (
    ("Türkçe", 20),
    ("T.C. İnkılap Tarihi", 10),
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
    return kurum_metin_oku(metin, dosya_adi)


def kurum_metin_oku(metin: str, dosya_adi: str = "") -> dict:
    if _lgs_sirali_mi(metin):
        return {
            "ad": _lgs_sirali_ad(metin),
            "tarih": _tarih(dosya_adi, metin),
            "satirlar": _lgs_sirali_satirlar(metin),
        }
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


def _lgs_sirali_mi(metin: str) -> bool:
    buyuk = metin.upper()
    return "LGS-" in buyuk and ("PUAN SIRALI" in buyuk or "İSİM SIRALI" in buyuk or "ISIM SIRALI" in buyuk)


def _lgs_sirali_ad(metin: str) -> str:
    m = re.search(r"(V[İI]P\s+LGS-\d+)", metin)
    if not m:
        return "LGS denemesi"
    return re.sub(r"\s+", " ", m.group(1)).strip()[:80]


def _lgs_sayi(token: str) -> float:
    t = token.strip()
    if "," in t:
        return float(t.replace(".", "").replace(",", "."))
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", t):
        return float(t.replace(".", ""))
    return float(t)


def _lgs_ad_temizle(ad: str) -> str:
    parca = re.sub(r"\s+", " ", ad).strip().split()
    if len(parca) >= 2 and len(parca) % 2 == 0:
        yari = len(parca) // 2
        if parca[:yari] == parca[yari:]:
            parca = parca[:yari]
    return " ".join(parca)


def _lgs_satir_birlestir(satirlar: list[str]) -> list[str]:
    birlesik = []
    i = 0
    while i < len(satirlar):
        satir = satirlar[i]
        sayi = len(re.findall(r"-?\d+(?:[.,]\d+)?", satir))
        if re.match(r"^\d+\s+", satir) and sayi < 22 and i + 1 < len(satirlar):
            devam = satirlar[i + 1]
            if not re.match(r"^\d+\s+", devam):
                satir = f"{satir} {devam}"
                i += 1
        birlesik.append(satir)
        i += 1
    return birlesik


def _lgs_ogrenci(satir: str) -> dict | None:
    m = re.match(
        r"^\d+\s+([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜa-zçğıöşü\s]*?)\s+(?:\d-[A-ZÇĞİÖŞÜ]\s+)?(?=\d)",
        satir.strip(),
    )
    if not m:
        return None
    ham = re.findall(r"-?\d+(?:[.,]\d+)?", satir[m.end():])
    if len(ham) < 22:
        return None
    sayilar = [_lgs_sayi(t) for t in ham]
    dersler = []
    for i, (ders, tavan) in enumerate(_LGS_DERSLER):
        dogru_f, yanlis_f, net = sayilar[i * 3], sayilar[i * 3 + 1], round(sayilar[i * 3 + 2], 2)
        if abs(dogru_f - round(dogru_f)) > 0.001 or abs(yanlis_f - round(yanlis_f)) > 0.001:
            return None
        dogru, yanlis = int(round(dogru_f)), int(round(yanlis_f))
        if dogru < 0 or yanlis < 0 or dogru + yanlis > tavan:
            return None
        from metrik import net as metrik_net
        if abs(metrik_net(dogru, yanlis) - net) > 0.05:
            return None
        dersler.append({
            "ders": ders,
            "dogru": dogru,
            "yanlis": yanlis,
            "bos": tavan - dogru - yanlis,
            "net": net,
        })
    toplam = round(sum(d["net"] for d in dersler), 2)
    if abs(toplam - round(sayilar[20], 2)) > 0.15:
        return None
    puan = round(sayilar[21], 3)
    if not 100 <= puan <= 500:
        return None
    return {"ad": _lgs_ad_temizle(m.group(1)), "dersler": dersler, "puan": puan, "net": toplam}


def _lgs_sirali_satirlar(metin: str) -> list[dict]:
    ham = [s.strip() for s in metin.splitlines() if s.strip()]
    gorulen: set[str] = set()
    satirlar = []
    for satir in _lgs_satir_birlestir(ham):
        ogr = _lgs_ogrenci(satir)
        if not ogr:
            continue
        anahtar = _harf(ogr["ad"])
        if not anahtar or anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        satirlar.append(ogr)
    return satirlar


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
    bulunan = _yakin(ad, ogrenciler)
    if bulunan:
        return bulunan
    return _yapisan(ad, ogrenciler)


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


def _yapisan(ad: str, ogrenciler: list[dict]) -> list[dict]:
    hedef = _harf(ad)
    if len(hedef) < 12:
        return []
    aday = []
    for ogr in ogrenciler:
        kayit = _harf(ogr["ad_soyad"])
        if len(kayit) < 12:
            continue
        kisa, uzun = (hedef, kayit) if len(hedef) <= len(kayit) else (kayit, hedef)
        if uzun.startswith(kisa) and len(uzun) - len(kisa) <= 6:
            aday.append(ogr)
    return aday if len(aday) == 1 else []
