"""
Okul / sınıf raporları için ortak metrik ve öneri metinleri.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from export import _kriter_saf_metin


def kriter_dagilimi_satirlardan(tik_rows: list[dict]) -> list[tuple[str, int]]:
    cnt: dict[str, int] = {}
    for row in tik_rows:
        kt = _kriter_saf_metin(row.get("kriter") or "")
        key = kt or ((row.get("kriter") or "")[:120])
        if key:
            cnt[key] = cnt.get(key, 0) + 1
    return sorted(cnt.items(), key=lambda x: (-x[1], x[0]))


def aylik_tik_sayilari(tik_rows: list[dict]) -> list[dict[str, Any]]:
    """Tarih alanı YYYY-MM-DD veya benzeri ISO biçiminde olmalı."""
    by_m: dict[str, int] = defaultdict(int)
    for r in tik_rows:
        t = (r.get("tarih") or "").strip()
        if len(t) >= 7:
            by_m[t[:7]] += 1
    return [{"ay": k, "adet": v, "etiket": k.replace("-", ".")} for k, v in sorted(by_m.items())]


def durum_dagilimi_hesapla(okul: list[dict]) -> dict[str, int]:
    """Web raporu ile aynı tik bantları."""
    return {
        "temiz": sum(1 for o in okul if o["tik_sayisi"] == 0),
        "uyari": sum(1 for o in okul if 1 <= o["tik_sayisi"] <= 2),
        "idari": sum(1 for o in okul if 3 <= o["tik_sayisi"] <= 5),
        "veli": sum(1 for o in okul if 6 <= o["tik_sayisi"] <= 8),
        "tutanak": sum(1 for o in okul if 9 <= o["tik_sayisi"] <= 11),
        "disiplin": sum(1 for o in okul if o["tik_sayisi"] >= 12),
    }


def oneriler_derle(
    ogrenci_sayisi: int,
    toplam_tik: int,
    ortalama_tik: float,
    durum_dagilimi: dict[str, int],
    kriter_en_cok: list[tuple[str, int]],
    sinif_en_yuksek_ortalama: tuple[str, float] | None,
) -> dict[str, Any]:
    """Veli / öğrenci / öğretmen için veriye dayalı kısa öneri maddeleri."""
    n = max(ogrenci_sayisi, 1)
    idari_toplam = (
        durum_dagilimi.get("idari", 0)
        + durum_dagilimi.get("veli", 0)
        + durum_dagilimi.get("tutanak", 0)
        + durum_dagilimi.get("disiplin", 0)
    )
    idari_oran = round(100 * idari_toplam / n, 1)
    risk_sayisi = (
        durum_dagilimi.get("veli", 0)
        + durum_dagilimi.get("tutanak", 0)
        + durum_dagilimi.get("disiplin", 0)
    )
    top1 = kriter_en_cok[0][0] if kriter_en_cok else ""
    top1_n = kriter_en_cok[0][1] if kriter_en_cok else 0

    veli: list[str] = []
    ogrenci: list[str] = []
    ogretmen: list[str] = []

    veli.append(
        "Çocuğunuzun davranış gelişimini desteklemek için okul kurallarını evde de hatırlatın; "
        "ödüllendirme ve net sınırlar birlikte kullanıldığında daha sürdürülebilir olur."
    )
    if risk_sayisi > 0:
        veli.append(
            f"Yüksek risk bandında ({risk_sayisi} öğrenci) öğrenciler için veli görüşmeleri ve "
            "yazılı geri bildirim takibi önemlidir; okul ile düzenli iletişim kurun."
        )
    if top1 and top1_n:
        veli.append(
            f"En sık tekrarlanan davranış alanı «{top1}» ({top1_n} kayıt). "
            "Bu konuda evde kısa hedefler (ör. ders arası, sıra beklerken) belirleyip haftalık değerlendirin."
        )
    if ortalama_tik >= 2.5:
        veli.append(
            "Sınıf ortalaması tik açısından yüksek; çocuğunuzun günlük özetini takip edin ve "
            "olumlu davranışları küçük ödüllerle pekiştirin."
        )

    ogrenci.append(
        "Sınıfta sıranızda oturma, izin alma ve arkadaşlarına saygı gösterme kurallarına uyun; "
        "her olumlu gün gelişim XP’nize katkı sağlar."
    )
    ogrenci.append(
        "Zorlandığınız bir durum olduğunda önce öğretmeninize, gerekiyorsa rehber öğretmene başvurun; "
        "erken yardım davranışın düzelmesini kolaylaştırır."
    )
    if top1:
        ogrenci.append(
            f"Okulda en çok hatırlanan konulardan biri «{top1}». "
            "Bu konuda kendinize küçük bir hatırlatıcı (not defteri köşesi) kullanabilirsiniz."
        )

    ogretmen.append(
        "Tehdit içermeyen net talimat, rutin ve pozitif pekiştirme (ör. olumlu davranışa anında geri bildirim) "
        "davranış iyileştirmede etkilidir."
    )
    if idari_oran >= 25:
        ogretmen.append(
            f"Öğrencilerin yaklaşık %{idari_oran}’i uyarı bandının üzerinde; "
            "sınıf içi kuralları görsel olarak hatırlatın ve küçük grup çalışmalarında rol dağılımı yapın."
        )
    else:
        ogretmen.append(
            "Genel tablo dengeli görünüyor; olumlu davranışları sınıfça görünür kılın (ör. haftanın örneği)."
        )
    if sinif_en_yuksek_ortalama:
        sad, ort = sinif_en_yuksek_ortalama
        ogretmen.append(
            f"En yüksek ortalama tik «{sad}» sınıfında ({ort}). Bu sınıfta ara sıra işbirlikli öğrenme ve "
            "kısa ara dinlendirme molaları davranış yoğunluğunu azaltabilir."
        )
    if top1 and top1_n >= 3:
        ogretmen.append(
            f"«{top1}» kayıtları öne çıkıyor; bu başlık için 2 haftalık hedefli sınıf içi hatırlatma "
            "ve peer örnekleme planlayın."
        )

    ozet = (
        f"Özet: {ogrenci_sayisi} öğrenci, öğrenci başına ortalama {ortalama_tik} tik; "
        f"idari ve üzeri bantta yaklaşık %{idari_oran}."
    )
    return {
        "veli": veli,
        "ogrenci": ogrenci,
        "ogretmen": ogretmen,
        "ozet_cumle": ozet,
        "metrik": {
            "idari_yuzde": idari_oran,
            "risk_ogrenci": risk_sayisi,
            "birinci_kriter": top1,
            "birinci_kriter_adet": top1_n,
        },
    }


def ogrenci_satirlarindan_durum(ogrenciler: list[dict]) -> dict[str, int]:
    """PDF snapshot öğrenci satırlarından (tik_sayisi) okul dağılımı."""
    dd = {"temiz": 0, "uyari": 0, "idari": 0, "veli": 0, "tutanak": 0, "disiplin": 0}
    for r in ogrenciler:
        t = int(r.get("tik_sayisi") or 0)
        if t == 0:
            dd["temiz"] += 1
        elif t <= 2:
            dd["uyari"] += 1
        elif t <= 5:
            dd["idari"] += 1
        elif t <= 8:
            dd["veli"] += 1
        elif t <= 11:
            dd["tutanak"] += 1
        else:
            dd["disiplin"] += 1
    return dd


def sinif_en_yuksek_ortalama_bul(sinif_ozetleri: list[dict]) -> tuple[str, float] | None:
    if not sinif_ozetleri:
        return None
    best = max(sinif_ozetleri, key=lambda x: float(x.get("ortalama") or 0))
    o = float(best.get("ortalama") or 0)
    if o <= 0:
        return None
    return (str(best.get("sinif_adi", "")), o)


def oneriler_snapshot_icinden(snapshot: dict[str, Any]) -> dict[str, Any]:
    oz = snapshot.get("ozet") or {}
    og = snapshot.get("ogrenciler") or []
    so = snapshot.get("sinif_ozet") or []
    kd_items = list((snapshot.get("kriter_dagilim") or {}).items())
    kd_sorted = sorted(kd_items, key=lambda x: (-x[1], x[0]))
    dd = ogrenci_satirlarindan_durum(og)
    sinif_list = []
    for s in so:
        oc = int(s.get("ogrenci") or 0) or 1
        tt = int(s.get("toplam_tik") or 0)
        sinif_list.append(
            {"sinif_adi": s.get("sinif_adi"), "ortalama": round(tt / oc, 2)}
        )
    sey = sinif_en_yuksek_ortalama_bul(sinif_list)
    return oneriler_derle(
        int(oz.get("ogrenci_sayisi") or 0),
        int(oz.get("toplam_tik") or 0),
        float(oz.get("ortalama_tik") or 0),
        dd,
        kd_sorted[:12],
        sey,
    )
