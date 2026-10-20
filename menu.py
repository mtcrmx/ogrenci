"""Veri tabanlı kenar ve alt menü üretici (Aşama 6)."""
from __future__ import annotations

from flask import has_request_context, url_for
from moduller import aktif_moduller


def _guvenli_url(endpoint: str, **kwargs) -> str:
    if not has_request_context():
        return f"/{endpoint}"
    try:
        return url_for(endpoint, **kwargs)
    except Exception:
        return "#"


def ogretmen_menusu(seviye: int = 8, rol: str = "ogretmen", sinif_id: int | None = None) -> list[dict]:
    """
    Öğretmen, yönetici ve rapor rolleri için menü öğelerini döner.
    Her öğe: {"id", "label", "icon", "href", "endpoint", "grup"}
    """
    moduller = aktif_moduller(f"{seviye}/A" if isinstance(seviye, int) else seviye)
    rol = (rol or "ogretmen").strip()

    if rol == "rehber":
        return rehber_menusu(seviye=seviye)

    if rol == "rapor":
        items = [
            {"id": "siralama", "label": "Sıralama", "icon": "▥", "href": _guvenli_url("lgs", sr_olcut="test", _anchor="lgs-siralama"), "endpoint": "lgs", "grup": "Analiz ve Raporlar"},
        ]
        if "kitap_odev_rapor" in moduller:
            items.append({"id": "analiz_merkezi", "label": "Kitap/ödev analizi", "icon": "◒", "href": _guvenli_url("analiz_merkezi", sinif_id=sinif_id), "endpoint": "analiz_merkezi", "grup": "Analiz ve Raporlar"})
        items.append({"id": "okuma_rapor", "label": "Okuma raporları", "icon": "✎", "href": _guvenli_url("ogretmen_kitap_okuma"), "endpoint": "ogretmen_kitap_okuma", "grup": "Analiz ve Raporlar"})
        items.append({"id": "yayin", "label": "Okul yayın ekranı", "icon": "▣", "href": _guvenli_url("yayin"), "endpoint": "yayin", "grup": "Diğer"})
        return items

    items = [
        {"id": "bugun", "label": "Bugün", "icon": "⌂", "href": _guvenli_url("dashboard", sinif=sinif_id), "endpoint": "dashboard", "grup": "Ana"},
    ]

    lgs_var = "lgs" in moduller

    # Takip: haftalık giriş, onaylar, yaprak test (5–7), geçmiş kayıtlar
    if "haftalik_takip" in moduller:
        items.append({"id": "haftalik_takip", "label": "Kitap ve ödev", "icon": "▤", "href": _guvenli_url("haftalik_takip"), "endpoint": "haftalik_takip", "grup": "Takip"})
    if "onay" in moduller or lgs_var:
        items.append({"id": "onay_kutusu", "label": "Bekleyen onaylar", "icon": "✓", "href": _guvenli_url("onay_kutusu"), "endpoint": "onay_kutusu", "grup": "Takip"})
    items.append({"id": "hizli_giris", "label": "Hızlı giriş", "icon": "✎", "href": _guvenli_url("ort_giris", sinif_id=sinif_id), "endpoint": "ort_giris", "grup": "Takip"})
    if "yaprak_test" in moduller and not lgs_var:
        items.append({"id": "okul_yaprak", "label": "Okulda yaprak test", "icon": "▤", "href": _guvenli_url("kamera_test.index"), "endpoint": "kamera_test.index", "grup": "Takip"})
    items.append({"id": "kayitlarim", "label": "Geçmiş kayıtlar", "icon": "✎", "href": _guvenli_url("teacher_records"), "endpoint": "teacher_records", "grup": "Takip"})
    items.append({"id": "islem_gecmisi", "label": "İşlem geçmişi", "icon": "↶", "href": _guvenli_url("islem_gecmisi"), "endpoint": "islem_gecmisi", "grup": "Takip"})

    if "kitap" in moduller:
        items.append({"id": "kitap_okuma", "label": "Kitap okuma", "icon": "📚", "href": _guvenli_url("ogretmen_kitap_okuma"), "endpoint": "ogretmen_kitap_okuma", "grup": "Kitap okuma"})

    # LGS (yalnızca 8. sınıf): sayfa içinde sekmeler
    if lgs_var:
        items.append({"id": "lgs_takip", "label": "Genel bakış", "icon": "✦", "href": _guvenli_url("lgs"), "endpoint": "lgs", "grup": "LGS merkezi"})
        if "deneme" in moduller:
            items.append({"id": "deneme_analiz", "label": "Denemeler", "icon": "◈", "href": _guvenli_url("deneme_analiz"), "endpoint": "deneme_analiz", "grup": "LGS merkezi"})
        if "evde_test" in moduller:
            items.append({"id": "evde_test", "label": "Ev testleri", "icon": "✉", "href": _guvenli_url("lgs", ekran="evde"), "endpoint": "lgs", "args": {"ekran": "evde"}, "grup": "LGS merkezi"})
        if "yaprak_test" in moduller:
            items.append({"id": "okul_yaprak", "label": "Yaprak test", "icon": "▤", "href": _guvenli_url("kamera_test.index"), "endpoint": "kamera_test.index", "grup": "LGS merkezi"})
        if "lgs_analiz" in moduller:
            items.append({"id": "kazanim", "label": "Kazanımlar", "icon": "▤", "href": _guvenli_url("lgs_kazanim.index"), "endpoint": "lgs_kazanim.index", "grup": "LGS merkezi"})
        if "siralama" in moduller:
            items.append({"id": "siralama", "label": "Sıralama", "icon": "▥", "href": _guvenli_url("lgs", sekme="siralama", sr_olcut="test"), "endpoint": "lgs", "args": {"sekme": "siralama"}, "grup": "LGS merkezi"})

    # Raporlar
    items.append({"id": "sinif_analiz", "label": "Sınıf analizi", "icon": "◈", "href": _guvenli_url("sinif_analiz_v2", sinif=sinif_id), "endpoint": "sinif_analiz_v2", "grup": "Raporlar"})
    items.append({"id": "soru_sinif_analiz", "label": "Soru ve sınıf analizi", "icon": "▦", "href": _guvenli_url("ev_analiz.index"), "endpoint": "ev_analiz.index", "ek_endpointler": ("test_sinif_analiz",), "grup": "Raporlar"})
    items.append({"id": "birlesik_analiz", "label": "Birleşik analiz", "icon": "◈", "href": _guvenli_url("yaprak_analiz.combined"), "endpoint": "yaprak_analiz.combined", "grup": "Raporlar"})
    if "kitap_odev_rapor" in moduller:
        items.append({"id": "analiz_merkezi", "label": "Kitap/ödev analizi", "icon": "◒", "href": _guvenli_url("analiz_merkezi", sinif_id=sinif_id), "endpoint": "analiz_merkezi", "grup": "Raporlar"})
    items.append({"id": "karne", "label": "Dönem karnesi", "icon": "▣", "href": _guvenli_url("karne", sinif=sinif_id), "endpoint": "karne", "grup": "Raporlar"})

    # Diğer
    items.append({"id": "veli_iletisim", "label": "Veli görüşmeleri", "icon": "💬", "href": _guvenli_url("ogretmen_randevular"), "endpoint": "ogretmen_randevular", "grup": "Diğer"})
    items.append({"id": "yayin", "label": "Okul yayın ekranı", "icon": "📺", "href": _guvenli_url("yayin"), "endpoint": "yayin", "yeni_sekme": True, "grup": "Diğer"})

    if rol == "yonetici":
        items.extend([
            {"id": "okul_analiz", "label": "Okul analizi", "icon": "◈", "href": _guvenli_url("yonetici_okul_analiz"), "endpoint": "yonetici_okul_analiz", "grup": "Yönetici"},
            {"id": "bilgi_girisi", "label": "Bilgi girişi", "icon": "◷", "href": _guvenli_url("giris_raporu"), "endpoint": "giris_raporu", "grup": "Yönetici"},
            {"id": "ogrenci_ara", "label": "Öğrenci ara / önizleme", "icon": "⌕", "href": _guvenli_url("yonetici_students"), "endpoint": "yonetici_students", "grup": "Yönetici"},
            {"id": "sinav_kayitlari", "label": "Sınav kayıtları", "icon": "▦", "href": _guvenli_url("yonetim_sinavlar"), "endpoint": "yonetim_sinavlar", "grup": "Yönetici"},
            {"id": "hesaplar", "label": "Hesaplar ve roller", "icon": "⚿", "href": _guvenli_url("admin_sifreler"), "endpoint": "admin_sifreler", "grup": "Yönetici"},
        ])

    return items


def veli_menusu(seviye: int = 8) -> list[dict]:
    """Veli menüsünü sınıf seviyesine göre döner."""
    moduller = aktif_moduller(f"{seviye}/A" if isinstance(seviye, int) else seviye)
    items = [
        {"id": "ana_sayfa", "label": "Ana sayfa", "icon": "⌂", "href": _guvenli_url("veli_panel") + "#genel", "endpoint": "veli_panel", "parent_nav": "genel"},
    ]
    if "lgs" in moduller:
        items.append({"id": "sorular_optik", "label": "Sorular ve optik", "icon": "✦", "href": _guvenli_url("veli_lgs", bolum="soru"), "endpoint": "veli_lgs"})
    elif "odev" in moduller or "kitap" in moduller:
        items.append({"id": "odev_kitap", "label": "Ödev ve kitap", "icon": "▤", "href": _guvenli_url("veli_panel") + "#hafta", "endpoint": "veli_panel", "parent_nav": "hafta"})
        items.append({"id": "kitap_okuma", "label": "Kitap okuma ve özet", "icon": "✎", "href": _guvenli_url("veli_kitap_okuma"), "endpoint": "veli_kitap_okuma"})

    items.append({"id": "gelisim_sonuclar", "label": "Gelişim ve sonuçlar", "icon": "◈", "href": _guvenli_url("veli_gelisim"), "endpoint": "veli_gelisim"})
    items.append({"id": "mesajlar", "label": "Mesajlar", "icon": "✉", "href": _guvenli_url("veli_panel") + "#mesajlar", "endpoint": "veli_panel", "parent_nav": "mesajlar"})
    items.append({"id": "rehberlik", "label": "Rehberlik", "icon": "❋", "href": _guvenli_url("veli_rehberlik"), "endpoint": "veli_rehberlik"})
    items.append({"id": "raporlar", "label": "Raporlar", "icon": "◒", "href": _guvenli_url("veli_panel") + "#raporlar", "endpoint": "veli_panel", "parent_nav": "raporlar"})

    if "lgs" in moduller:
        items.append({
            "id": "lgs_grup",
            "grup": "LGS",
            "alt": [
                {"id": "lgs_sonuc", "label": "Ders ve deneme sonuçları", "icon": "◈", "href": _guvenli_url("veli_lgs", bolum="sonuc"), "endpoint": "veli_lgs"},
                {"id": "lgs_siralama", "label": "Sıralama", "icon": "▥", "href": _guvenli_url("veli_lgs", sr_olcut="test", _anchor="lgs-siralama"), "endpoint": "veli_lgs"},
            ],
        })
    else:
        items.append({"id": "veli_sonuclar", "label": "Ders ve deneme sonuçları", "icon": "◈", "href": _guvenli_url("veli_sonuclar"), "endpoint": "veli_sonuclar"})

    return items


def rehber_menusu(seviye: int = 8) -> list[dict]:
    """Rehber öğretmen menüsünü döner."""
    return [
        {"id": "rehberlik_panel", "label": "Genel bakış", "icon": "⌂", "href": _guvenli_url("rehberlik_panel"), "endpoint": "rehberlik_panel", "grup": "Rehberlik"},
        {"id": "rehberlik_ajanda", "label": "Görüşme ajandası", "icon": "◷", "href": _guvenli_url("rehberlik_ajanda"), "endpoint": "rehberlik_ajanda", "grup": "Rehberlik"},
        {"id": "rehberlik_takip", "label": "Öğrenci takibi", "icon": "◎", "href": _guvenli_url("rehberlik_takip"), "endpoint": "rehberlik_takip", "grup": "Rehberlik"},
        {"id": "rehberlik_lgs", "label": "LGS takip merkezi", "icon": "◈", "href": _guvenli_url("rehberlik_lgs"), "endpoint": "rehberlik_lgs", "grup": "Rehberlik"},
        {"id": "siralama", "label": "Sıralama", "icon": "▥", "href": _guvenli_url("rehberlik_lgs", sr_olcut="test", _anchor="lgs-siralama"), "endpoint": "rehberlik_lgs", "grup": "Rehberlik"},
        {"id": "rehberlik_ogretmenler", "label": "Öğretmen çalışmaları", "icon": "▤", "href": _guvenli_url("rehberlik_ogretmenler"), "endpoint": "rehberlik_ogretmenler", "grup": "Rehberlik"},
        {"id": "rehberlik_gorusmeler", "label": "Veli talepleri", "icon": "✉", "href": _guvenli_url("rehberlik_gorusmeler"), "endpoint": "rehberlik_gorusmeler", "grup": "Rehberlik"},
        {"id": "rehberlik_etkinlikler", "label": "Sınıf çalışmaları", "icon": "◇", "href": _guvenli_url("rehberlik_etkinlikler"), "endpoint": "rehberlik_etkinlikler", "grup": "Rehberlik"},
        {"id": "rehberlik_kutuphane", "label": "İçerik kütüphanesi", "icon": "▧", "href": _guvenli_url("rehberlik_kutuphane"), "endpoint": "rehberlik_kutuphane", "grup": "Rehberlik"},
        {"id": "rehberlik_yeni", "label": "İçerik paylaş", "icon": "＋", "href": _guvenli_url("rehberlik_yeni"), "endpoint": "rehberlik_yeni", "grup": "Rehberlik"},
        {"id": "rehberlik_ozet", "label": "Hizmet özeti", "icon": "▥", "href": _guvenli_url("rehberlik_ozet"), "endpoint": "rehberlik_ozet", "grup": "Rehberlik"},
        {"id": "kayitlarim", "label": "Kayıtlarım · Düzenle / Sil", "icon": "✎", "href": _guvenli_url("teacher_records"), "endpoint": "teacher_records", "grup": "Kayıt yönetimi"},
    ]


def menu_gruplari(items: list[dict]) -> list[tuple[str, list[dict]]]:
    """Jinja groupby alfabetik sıralar; menü grupları tanımlandığı sırada kalmalı."""
    gruplar: dict[str, list[dict]] = {}
    for item in items:
        gruplar.setdefault(item.get("grup") or "", []).append(item)
    return list(gruplar.items())


def _args_uyar(item: dict, args) -> bool:
    if item.get("id") == "siralama":
        return args.get("sekme") == "siralama" or bool(args.get("sr_olcut"))
    beklenen = item.get("args") or {}
    return bool(beklenen) and all(args.get(k) == v for k, v in beklenen.items())


def aktif_bolum(items: list[dict], endpoint: str | None, args) -> dict | None:
    """Açık sayfanın menü bölümü: {"grup", "items", "secili"}; bölüm dışıysa None."""
    adaylar = [i for i in items if endpoint and (i.get("endpoint") == endpoint or endpoint in i.get("ek_endpointler", ()))]
    if not adaylar:
        return None
    secili = (
        next((i for i in adaylar if _args_uyar(i, args)), None)
        or next((i for i in adaylar if not i.get("args")), None)
        or adaylar[0]
    )
    grup = secili.get("grup") or ""
    return {"grup": grup, "items": [i for i in items if (i.get("grup") or "") == grup], "secili": secili["id"]}


def register_menu(app) -> None:
    @app.context_processor
    def _menu_context():
        return {
            "aktif_bolum": aktif_bolum,
            "menu_gruplari": menu_gruplari,
            "ogretmen_menusu": ogretmen_menusu,
            "veli_menusu": veli_menusu,
            "rehber_menusu": rehber_menusu,
        }
