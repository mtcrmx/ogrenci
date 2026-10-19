"""Kural tabanlı otomatik öneri motoru (Aşama 6).

Veri yoksa veya 3'ten az test varsa düşüş/yükseliş önerisi üretilmez.
Kurallar:
- Son 3 testte art arda düşüş (örn. %70 -> %60 -> %50)
- Son 3 denemede art arda yükseliş veya düşüş
- Genel veya ders başarısı sınıf ortalamasının belirgin altında (< 50 veya sınıf ortalamasından >= 10 puan düşük)
- Evde test başarısı okul testinden >= 15 puan düşük
- Bekleyen (çözülmemiş) evde test varlığı
"""
from __future__ import annotations

from metrik import goster, oran, toplu_oran


def ardisik_dusus_var_mi(degerler: list[float | None], en_az: int = 3) -> bool:
    """Son `en_az` geçerli değerin kesin olarak azaldığını (d1 > d2 > d3) kontrol eder."""
    temiz = [float(x) for x in (degerler or []) if x is not None]
    if len(temiz) < en_az:
        return False
    son = temiz[-en_az:]
    return all(son[i] > son[i + 1] for i in range(len(son) - 1))


def ardisik_yukselis_var_mi(degerler: list[float | None], en_az: int = 3) -> bool:
    """Son `en_az` geçerli değerin kesin olarak arttığını (d1 < d2 < d3) kontrol eder."""
    temiz = [float(x) for x in (degerler or []) if x is not None]
    if len(temiz) < en_az:
        return False
    son = temiz[-en_az:]
    return all(son[i] < son[i + 1] for i in range(len(son) - 1))


def ogrenci_onerileri(veri: dict) -> list[str]:
    """
    Öğrenci verisinden kural tabanlı öneri cümleleri üretir.
    Beklenen (opsiyonel) anahtarlar:
      - test_gecmisi: [{"ders": str, "konu": str, "oran": float}] veya [float]
      - deneme_netleri: [float]
      - sinif_deneme_ort: float | None
      - ogrenci_oran: float | None
      - sinif_oran: float | None
      - zayif_konular: [{"ders": str, "konu": str, "oran": float}]
      - evde_okul_fark: [{"ders": str, "evde": float, "okul": float}]
      - bekleyen_ev_testi: int
    """
    if not veri:
        return []
    oneriler: list[str] = []

    # 1. Son 3 testte düşüş kontrolü
    gecmis = veri.get("test_gecmisi") or []
    oran_listesi = [
        (g.get("oran") if isinstance(g, dict) else g)
        for g in gecmis
    ]
    oran_temiz = [float(x) for x in oran_listesi if x is not None]
    if ardisik_dusus_var_mi(oran_temiz, 3):
        s1, s2, s3 = oran_temiz[-3], oran_temiz[-2], oran_temiz[-1]
        konu_etiket = ""
        if isinstance(gecmis[-1], dict) and (gecmis[-1].get("ders") or gecmis[-1].get("konu")):
            parcalar = [p for p in (gecmis[-1].get("ders"), gecmis[-1].get("konu")) if p]
            konu_etiket = " · ".join(parcalar) + ": "
        oneriler.append(
            f"{konu_etiket}Son 3 testte düşüş (%{goster(s1)} → %{goster(s2)} → %{goster(s3)}). Tekrar testi önerilir."
        )

    # 2. Deneme netleri trendi (en az 3 deneme varsa)
    denemeler = [float(x) for x in (veri.get("deneme_netleri") or []) if x is not None]
    sinif_deneme = veri.get("sinif_deneme_ort")
    if ardisik_yukselis_var_mi(denemeler, 3):
        ilk, son = denemeler[-3], denemeler[-1]
        ek = ""
        if sinif_deneme is not None and son < float(sinif_deneme):
            fark = round(float(sinif_deneme) - son, 1)
            ek = f", sınıf ortalamasının {goster(fark)} net altında"
        oneriler.append(f"Deneme neti 3 denemedir artıyor ({goster(ilk)} → {goster(son)}){ek}.")
    elif ardisik_dusus_var_mi(denemeler, 3):
        ilk, son = denemeler[-3], denemeler[-1]
        oneriler.append(f"Deneme neti son 3 denemedir düşüyor ({goster(ilk)} → {goster(son)}). Konu eksikleri incelenmeli.")

    # 3. Zayıf konular (< %50)
    for zk in (veri.get("zayif_konular") or [])[:2]:
        k_oran = zk.get("oran")
        if k_oran is not None and float(k_oran) < 50.0:
            ders_ad = zk.get("ders") or "Ders"
            konu_ad = zk.get("konu") or "Konu"
            oneriler.append(f"{ders_ad} · {konu_ad}: başarı %{goster(k_oran)} (sınıf hedefinin altında). Kısa konu tekrarı önerilir.")

    # 4. Evde test - okul testi farkı
    for eo in (veri.get("evde_okul_fark") or []):
        ev = eo.get("evde")
        ok = eo.get("okul")
        if ev is not None and ok is not None and (float(ok) - float(ev)) >= 15.0:
            ders_ad = eo.get("ders") or "Genel"
            oneriler.append(f"Evde test başarısı okul testinden düşük ({ders_ad}: evde %{goster(ev)}, okulda %{goster(ok)}).")

    # 5. Sınıf ortalamasının altında genel başarı
    ogr_oran = veri.get("ogrenci_oran")
    snf_oran = veri.get("sinif_oran")
    if ogr_oran is not None and snf_oran is not None and (float(snf_oran) - float(ogr_oran)) >= 5.0:
        fark = round(float(snf_oran) - float(ogr_oran), 1)
        oneriler.append(f"Genel başarı (%{goster(ogr_oran)}) sınıf ortalamasının (%{goster(snf_oran)}) {goster(fark)} puan altında.")

    # 6. Bekleyen evde test
    bekleyen = int(veri.get("bekleyen_ev_testi") or 0)
    if bekleyen > 0:
        oneriler.append(f"Evde test: {bekleyen} test çözüm bekliyor → hatırlatma gönderilebilir.")

    return oneriler


def sinif_onerileri(veri: dict) -> list[dict]:
    """
    Sınıf analizi için risk altındaki öğrencileri ve sınıf önerilerini döner.
    Beklenen anahtar:
      - ogrenciler: [{"id": int, "ad_soyad": str, "oran": float|None, "test_gecmisi": [float], "bekleyen_ev": int, "katilmadigi_deneme": int}]
    Döner:
      [{"ogrenci_id": int, "ad_soyad": str, "oran": float|None, "neden": str, "seviye": "bad"|"warn"}]
    """
    if not veri:
        return []
    risk_listesi: list[dict] = []
    for o in veri.get("ogrenciler") or []:
        nedenler = []
        seviye = "warn"
        ogr_oran = o.get("oran")
        gecmis = [float(x) for x in (o.get("test_gecmisi") or []) if x is not None]
        bekleyen_ev = int(o.get("bekleyen_ev") or 0)
        katilmadigi = int(o.get("katilmadigi_deneme") or 0)

        if ogr_oran is not None and float(ogr_oran) < 50.0:
            nedenler.append(f"Genel oran düşük (%{goster(ogr_oran)})")
            seviye = "bad"
        if ardisik_dusus_var_mi(gecmis, 3):
            nedenler.append("Son 3 testte düşüş")
            seviye = "bad"
        if bekleyen_ev > 0:
            nedenler.append(f"Evde test bekliyor ({bekleyen_ev} adet)")
        if katilmadigi > 0:
            nedenler.append(f"Son denemeye katılmadı ({katilmadigi})")

        if nedenler:
            risk_listesi.append({
                "ogrenci_id": o.get("id"),
                "ad_soyad": o.get("ad_soyad") or "",
                "oran": ogr_oran,
                "neden": " · ".join(nedenler),
                "seviye": seviye,
            })
    return risk_listesi


def okul_onerileri(veri: dict) -> list[str]:
    """
    Yönetici okul analizi için özet öneriler üretir.
    Beklenen anahtarlar:
      - siniflar: [{"sinif_adi": str, "oran": float|None}]
      - dersler: [{"ders": str, "oran": float|None}]
      - eksik_giris_ogretmen_sayisi: int
    """
    if not veri:
        return []
    out: list[str] = []
    dersler = [d for d in (veri.get("dersler") or []) if d.get("oran") is not None]
    if dersler:
        en_dusuk_ders = min(dersler, key=lambda d: float(d["oran"]))
        out.append(f"Okul genelinde en düşük başarı {en_dusuk_ders['ders']} dersinde (%{goster(en_dusuk_ders['oran'])}).")

    siniflar = veri.get("siniflar") or []
    veri_olmayan = [s["sinif_adi"] for s in siniflar if s.get("oran") is None and s.get("sinif_adi")]
    if veri_olmayan:
        out.append(f"{', '.join(veri_olmayan)} sınıflarında henüz test verisi girilmemiş.")

    eksik_ogr = int(veri.get("eksik_giris_ogretmen_sayisi") or 0)
    if eksik_ogr > 0:
        out.append(f"Bu hafta bilgi girişi eksik olan {eksik_ogr} öğretmen var.")

    return out
