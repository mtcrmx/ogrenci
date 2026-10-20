"""Aşama 6: Ortak tasarım sistemi, menü üretici, kural tabanlı öneriler ve yeni ekran testleri."""
from pathlib import Path
import database as db
from menu import ogretmen_menusu, rehber_menusu, veli_menusu
from oneriler import ardisik_dusus_var_mi, ardisik_yukselis_var_mi, ogrenci_onerileri, okul_onerileri, sinif_onerileri
from web_app import app


def test_tasarim_css_ve_olu_kod_kontrolu():
    """tasarim.css mevcut ve base.html içinde bağlı; ölü veli_ozet.html şablonu kaldırılmış olmalı."""
    root = Path(__file__).resolve().parent.parent
    css_path = root / "static" / "tasarim.css"
    assert css_path.is_file()
    css_text = css_path.read_text(encoding="utf-8")
    assert "--brand" in css_text
    assert 'html[data-renk="leylak"]' in css_text

    base_html = (root / "templates" / "base.html").read_text(encoding="utf-8")
    assert "tasarim.css" in base_html

    # Ölü şablon silinmiş olmalı
    assert not (root / "templates" / "veli_ozet.html").exists()


def test_menu_uretici_ve_tek_siralama_kurali():
    """Menü üretici 8. ve 7. sınıf farkını gözetir; 'Sıralama' menüde yalnız 1 kez geçer."""
    with app.test_request_context("/"):
        m8 = ogretmen_menusu(seviye=8, rol="ogretmen", sinif_id=1)
        m7 = ogretmen_menusu(seviye=7, rol="ogretmen", sinif_id=2)
        m_yon = ogretmen_menusu(seviye=8, rol="yonetici", sinif_id=1)
        m_reh = rehber_menusu(seviye=8)
        v8 = veli_menusu(seviye=8)
        v6 = veli_menusu(seviye=6)

    # 8. sınıfta yalnız evde sorular, denemeler ve analizler; Sıralama yok
    assert not any(x["label"] == "Sıralama" for x in m8)
    assert {"evde_test", "deneme_analiz"} <= {x["id"] for x in m8}
    assert any(x.get("grup") == "Analizler" for x in m8)
    assert not any(x["id"] == "haftalik_takip" for x in m8)

    # 7. sınıfta haftalık takip var, LGS sıralama yok
    assert any(x["id"] == "haftalik_takip" for x in m7)
    assert not any(x["label"] == "Sıralama" for x in m7)

    # Yöneticide okul analizi ve sınav kayıtları var
    assert any(x["id"] == "okul_analiz" for x in m_yon)
    assert any(x["id"] == "sinav_kayitlari" for x in m_yon)

    # Rehberde Sıralama 1 kez var
    assert len([x for x in m_reh if x["label"] == "Sıralama"]) == 1

    # Veli menüsünde 8. sınıfta "Sorular ve optik", 6. sınıfta "Ödev ve kitap"
    assert any(x["id"] == "sorular_optik" for x in v8)
    assert not any(x["id"] == "odev_kitap" for x in v8)
    assert any(x["id"] == "odev_kitap" for x in v6)
    assert {"sorular_optik", "deneme_sonuc"} <= {x["id"] for x in v6}

    # Kazanımlar 8. sınıf menüsünden kaldırıldı; 5-7 öğretmeninde deneme ve evde soru var
    assert not any(x["id"] == "kazanim" for x in m8 + m_yon)
    assert {"evde_test", "deneme_analiz", "haftalik_takip"} <= {x["id"] for x in m7}


def test_oneriler_kural_tabanli_birim():
    """Kural tabanlı öneri motoru birim testleri: veri yoksa veya <3 test varsa düşüş önerisi üretmez."""
    assert ogrenci_onerileri({}) == []
    assert ardisik_dusus_var_mi([70, 60], 3) is False
    assert ardisik_dusus_var_mi([70, 60, 50], 3) is True
    assert ardisik_yukselis_var_mi([38, 45.3, 49.0], 3) is True

    # Yalnız 2 test varken düşüş önerisi üretilmemeli
    o_iki = ogrenci_onerileri({"test_gecmisi": [{"ders": "Matematik", "konu": "Üslü", "oran": 70}, {"ders": "Matematik", "konu": "Üslü", "oran": 60}]})
    assert not any("düşüş" in s for s in o_iki)

    # 3 test üst üste düşüş, deneme yükselişi, evde-okul farkı ve bekleyen evde test
    o_tam = ogrenci_onerileri({
        "test_gecmisi": [
            {"ders": "Matematik", "konu": "Üslü ifadeler", "oran": 70.0},
            {"ders": "Matematik", "konu": "Üslü ifadeler", "oran": 60.0},
            {"ders": "Matematik", "konu": "Üslü ifadeler", "oran": 50.0},
        ],
        "deneme_netleri": [38.0, 45.3, 49.0],
        "sinif_deneme_ort": 51.7,
        "ogrenci_oran": 61.4,
        "sinif_oran": 67.4,
        "zayif_konular": [{"ders": "Matematik", "konu": "Üslü ifadeler", "oran": 40.0}],
        "evde_okul_fark": [{"ders": "Matematik", "evde": 45.0, "okul": 80.0}],
        "bekleyen_ev_testi": 2,
    })
    birlesik = " | ".join(o_tam)
    assert "Son 3 testte düşüş (%70,0 → %60,0 → %50,0)" in birlesik
    assert "3 denemedir artıyor (38,0 → 49,0)" in birlesik
    assert "Evde test başarısı okul testinden düşük" in birlesik
    assert "2 test çözüm bekliyor" in birlesik

    # Sınıf risk listesi
    risk = sinif_onerileri({
        "ogrenciler": [
            {"id": 1, "ad_soyad": "Riskli Öğrenci", "oran": 45.0, "test_gecmisi": [70, 60, 50], "bekleyen_ev": 1},
            {"id": 2, "ad_soyad": "Başarılı Öğrenci", "oran": 85.0, "test_gecmisi": [80, 85, 90], "bekleyen_ev": 0},
        ]
    })
    assert len(risk) == 1
    assert risk[0]["ogrenci_id"] == 1
    assert risk[0]["seviye"] == "bad"

    # Okul önerileri
    okul = okul_onerileri({
        "siniflar": [{"sinif_adi": "8/A", "oran": 67.8}, {"sinif_adi": "5/A", "oran": None}],
        "dersler": [{"ders": "Türkçe", "oran": 69.4}, {"ders": "Matematik", "oran": 51.3}],
        "eksik_giris_ogretmen_sayisi": 4,
    })
    okul_metin = " | ".join(okul)
    assert "Matematik" in okul_metin
    assert "5/A" in okul_metin
    assert "4 öğretmen" in okul_metin


def test_yeni_ekranlar_ve_eski_url_yonlendirmeleri():
    """Yeni ekranlar (/ogrenci/<id>, /analiz/sinif, /veli/gelisim, /yonetici/okul-analiz) ve eski URL'ler 200/301/302 döner."""
    from yetki import yetkili_idleri

    con = db._conn()
    try:
        yon_ids = yetkili_idleri("yonetici")
        if yon_ids:
            yonetici_ogr = con.execute("SELECT id, ad_soyad FROM ogretmenler WHERE id=?", (next(iter(yon_ids)),)).fetchone()
        else:
            yonetici_ogr = con.execute("SELECT id, ad_soyad FROM ogretmenler LIMIT 1").fetchone()
            con.execute("INSERT OR IGNORE INTO ogretmen_yetki(ogretmen_id, yetki) VALUES (?, 'yonetici')", (yonetici_ogr["id"],))
            con.commit()
        ogrenci_8 = con.execute(
            "SELECT o.id, o.sinif_id FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi LIKE '8/%' LIMIT 1"
        ).fetchone()
    finally:
        con.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["ogretmen_id"] = int(yonetici_ogr["id"])
        sess["ogretmen_adi"] = yonetici_ogr["ad_soyad"]
        sess["ogretmen_yetki"] = "tam"

    # Öğretmen ve Yönetici yeni ekranları
    for url in [
        f"/ogrenci/{ogrenci_8['id']}",
        f"/analiz/sinif?sinif={ogrenci_8['sinif_id']}",
        "/yonetici/okul-analiz",
        "/giris",
        "/",
        "/lgs",
        "/yaprak-kamera",
        "/lgs/birlesik-analiz",
        "/yonetim/sinavlar",
    ]:
        r = client.get(url)
        assert r.status_code in (200, 301, 302), f"{url} -> {r.status_code}"

    # Veli oturumuyla ekranlar ve eski /veli/ozet (301)
    veli_client = app.test_client()
    with veli_client.session_transaction() as vs:
        vs["veli_ogrenci_id"] = int(ogrenci_8["id"])

    r_gelisim = veli_client.get("/veli/gelisim")
    assert r_gelisim.status_code == 200
    assert "Gelişim ve Sonuçlar" in r_gelisim.get_data(as_text=True)

    r_ozet = veli_client.get("/veli/ozet")
    assert r_ozet.status_code in (301, 302)
