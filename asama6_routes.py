"""Aşama 6 ekranları (/ogrenci/<id>, /analiz/sinif, /veli/gelisim, /yonetici/okul-analiz) ve yönlendirmeler."""
from __future__ import annotations

from datetime import date, timedelta
from flask import abort, redirect, render_template, request, session, url_for
import database as db
import lgs_optik
import sinav_okuyucu
from metrik import goster, net as metrik_net, oran, toplu_oran
from moduller import aktif_moduller, seviye as sinif_seviye_bul
from oneriler import ogrenci_onerileri, okul_onerileri, sinif_onerileri
from student_results import course_analysis, school_courses
from yetki import yetki_gerekli, yetkili
import yonetici


def _ogrenci_analiz_paketi(oid: int) -> dict:
    con = db._conn()
    try:
        ogrenci_row = con.execute(
            "SELECT o.*, s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id WHERE o.id = ?",
            (int(oid),),
        ).fetchone()
    finally:
        con.close()
    if not ogrenci_row:
        abort(404)
    ogrenci = dict(ogrenci_row)
    sinif_id = int(ogrenci["sinif_id"])
    seviye = sinif_seviye_bul(ogrenci)
    moduller = aktif_moduller(seviye)

    sinif_ogr = db.sinif_ogrencileri(sinif_id)
    sinif_oid_set = {int(o["id"]) for o in sinif_ogr}

    ogr_satirlar = sinav_okuyucu.birlesik_sonuclar({int(oid)}, teacher=True)
    sinif_satirlar = sinav_okuyucu.birlesik_sonuclar(sinif_oid_set, teacher=True) if sinif_oid_set else []

    genel_oran = toplu_oran([(r["dogru"], r["soru_sayisi"]) for r in ogr_satirlar])
    sinif_oran = toplu_oran([(r["dogru"], r["soru_sayisi"]) for r in sinif_satirlar])
    sinif_fark = round(genel_oran - sinif_oran, 1) if (genel_oran is not None and sinif_oran is not None) else None

    denemeler = db.lgs_denemeler(int(oid), 50)
    ders_analiz = course_analysis(denemeler, include_exams=True)
    gercek_denemeler = [d for d in denemeler if d.get("tur") != "ders"]
    son_deneme_net = gercek_denemeler[0]["net"] if gercek_denemeler else (denemeler[0]["net"] if denemeler else None)
    son_deneme_ad = gercek_denemeler[0]["ad"] if gercek_denemeler else (denemeler[0]["ad"] if denemeler else None)

    # Kaynaklara göre başarı tablosu
    kaynak_tablosu = []
    for k_kod, k_etiket in [("okul", "Okulda yaprak test"), ("ev", "Evde test"), ("deneme", "Deneme")]:
        alt = [r for r in ogr_satirlar if r.get("source") == k_kod]
        d_top = sum(int(r.get("dogru") or 0) for r in alt)
        y_top = sum(int(r.get("yanlis") or 0) for r in alt)
        b_top = sum(int(r.get("bos") or 0) for r in alt)
        s_top = sum(int(r.get("soru_sayisi") or 0) for r in alt)
        n_top = round(sum(float(r.get("net") or 0) for r in alt), 2)
        kaynak_tablosu.append({
            "etiket": k_etiket,
            "dogru": d_top,
            "yanlis": y_top,
            "bos": b_top,
            "oran": oran(d_top, s_top),
            "net": n_top,
            "kalin": False,
        })
    d_all = sum(k["dogru"] for k in kaynak_tablosu)
    y_all = sum(k["yanlis"] for k in kaynak_tablosu)
    b_all = sum(k["bos"] for k in kaynak_tablosu)
    s_all = sum(int(r.get("soru_sayisi") or 0) for r in ogr_satirlar)
    n_all = round(sum(k["net"] for k in kaynak_tablosu), 2)
    kaynak_tablosu.append({
        "etiket": "Birleşik",
        "dogru": d_all,
        "yanlis": y_all,
        "bos": b_all,
        "oran": oran(d_all, s_all),
        "net": n_all,
        "kalin": True,
    })

    # Evde <-> Okul karşılaştırması
    ders_kumesi = sorted({r.get("ders") for r in ogr_satirlar if r.get("ders")})
    evde_okul_tablo = []
    for d_adi in ders_kumesi:
        ev_alt = [r for r in ogr_satirlar if r.get("ders") == d_adi and r.get("source") == "ev"]
        ok_alt = [r for r in ogr_satirlar if r.get("ders") == d_adi and r.get("source") == "okul"]
        ev_o = toplu_oran([(r["dogru"], r["soru_sayisi"]) for r in ev_alt])
        ok_o = toplu_oran([(r["dogru"], r["soru_sayisi"]) for r in ok_alt])
        fark = round(ev_o - ok_o, 1) if (ev_o is not None and ok_o is not None) else None
        evde_okul_tablo.append({"ders": d_adi, "evde": ev_o, "okul": ok_o, "fark": fark})

    # En zayıf ders/konu
    en_zayif_baslik = None
    en_zayif_oran = None
    zayif_konular = []
    for a in ders_analiz:
        yuzde = a["son"].get("yuzde")
        if yuzde is not None:
            zayif_konular.append({"ders": a["ders"], "konu": "Genel", "oran": yuzde})
            if en_zayif_oran is None or yuzde < en_zayif_oran:
                en_zayif_oran = yuzde
                en_zayif_baslik = a["ders"]

    # Bekleyen evde test sayısı
    con = db._conn()
    try:
        lgs_optik._init(con)
        bekleyen_ev = con.execute(
            """SELECT COUNT(*) FROM lgs_optik_sinav e
               LEFT JOIN lgs_optik_sonuc r ON r.sinav_id = e.id AND r.ogrenci_id = ?
               WHERE (e.silindi_at IS NULL OR e.silindi_at = '')
                 AND e.kaynak != 'kamera'
                 AND (e.sinif_id = ? OR (e.sinif_id IS NULL AND ? = 8))
                 AND r.id IS NULL""",
            (int(oid), sinif_id, seviye),
        ).fetchone()[0]
    finally:
        con.close()

    # 5-7 haftalık ödev/kitap durumu
    odev_durum = None
    kitap_durum = None
    if "haftalik_takip" in moduller:
        hafta = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        ht = db.haftalik_takip_sinif(sinif_id, hafta).get(int(oid), {})
        odev_durum = ht.get("odev_durum") or "Bekliyor"
        kitap_durum = "Okudu" if ht.get("kitap_okudu") else "Bekliyor"

    # Kural tabanlı öneriler
    test_gecmisi_oranlar = [
        {"ders": r.get("ders") or "", "konu": r.get("ad") or "", "oran": oran(r.get("dogru"), r.get("soru_sayisi"))}
        for r in reversed(ogr_satirlar[:10])
    ]
    deneme_netleri_kronolojik = [float(d["net"]) for d in reversed(gercek_denemeler[:6]) if d.get("net") is not None]
    oneriler = ogrenci_onerileri({
        "test_gecmisi": test_gecmisi_oranlar,
        "deneme_netleri": deneme_netleri_kronolojik,
        "ogrenci_oran": genel_oran,
        "sinif_oran": sinif_oran,
        "zayif_konular": zayif_konular,
        "evde_okul_fark": evde_okul_tablo,
        "bekleyen_ev_testi": bekleyen_ev,
    })

    if genel_oran is not None:
        tek_cumle_yorum = f"Genel başarı oranı %{goster(genel_oran)}."
        if en_zayif_baslik and en_zayif_oran is not None:
            tek_cumle_yorum += f" Öncelikli destek alanı: {en_zayif_baslik} (%{goster(en_zayif_oran)})."
    else:
        tek_cumle_yorum = "Henüz test sonucu girilmedi; ilk sonuçlarla birlikte başarı ve öneriler burada görünecek."

    profil = db.lgs_profil(int(oid)) if "lgs" in moduller else {}
    kpi = {
        "genel_oran": genel_oran,
        "sinif_oran": sinif_oran,
        "sinif_fark": sinif_fark,
        "son_deneme_net": son_deneme_net,
        "son_deneme_ad": son_deneme_ad,
        "siralama_metin": None,
        "odev_durum": odev_durum,
        "kitap_durum": kitap_durum,
        "en_zayif_baslik": en_zayif_baslik,
        "en_zayif_oran": en_zayif_oran,
        "bekleyen_ev_testi": int(bekleyen_ev or 0),
    }

    return {
        "ogrenci": ogrenci,
        "seviye": seviye,
        "ogrenci_modulleri": moduller,
        "aktif_moduller": moduller,
        "hedef_lise": profil.get("hedef") if isinstance(profil, dict) else "",
        "kpi": kpi,
        "tek_cumle_yorum": tek_cumle_yorum,
        "oneriler": oneriler,
        "denemeler": denemeler,
        "ders_analiz": ders_analiz,
        "kaynak_tablosu": kaynak_tablosu,
        "evde_okul_tablo": evde_okul_tablo,
    }


def register_asama6(app, login_required, accessible):
    @app.get("/ogrenci/<int:oid>")
    def ogrenci_detay_v2(oid: int):
        if yonetici.active() or yetkili("yonetici"):
            pass
        elif session.get("ogretmen_id"):
            if not accessible(session["ogretmen_id"], oid) and not yetkili("rehber") and not yetkili("rapor"):
                abort(403)
        elif session.get("veli_ogrenci_id") == oid:
            return redirect(url_for("veli_gelisim"))
        else:
            return redirect(url_for("login"))

        paket = _ogrenci_analiz_paketi(oid)
        return render_template("ogrenci_detay_v2.html", **paket)

    @app.get("/analiz/sinif")
    @login_required
    def sinif_analiz_v2():
        tid = session.get("ogretmen_id")
        siniflar = db.ogretmen_siniflari(tid) or db.aktif_sube_siniflari() or db.tum_siniflar()
        secili_id = request.args.get("sinif", type=int) or session.get("ui_sinif_id") or (siniflar[0]["id"] if siniflar else None)
        sinif_map = {int(s["id"]): s for s in siniflar}
        if secili_id not in sinif_map and siniflar:
            secili_id = int(siniflar[0]["id"])
        secili_sinif = sinif_map.get(secili_id) if secili_id else None
        if secili_id:
            session["ui_sinif_id"] = secili_id

        seviye = sinif_seviye_bul(secili_sinif) if secili_sinif else 8
        moduller = aktif_moduller(seviye)
        secili_ders = (request.args.get("ders") or "").strip()
        secili_tur = (request.args.get("tur") or "").strip()

        ogrenciler = db.sinif_ogrencileri(secili_id) if secili_id else []
        oid_set = {int(o["id"]) for o in ogrenciler}
        tum_satirlar = sinav_okuyucu.birlesik_sonuclar(oid_set, teacher=True) if oid_set else []
        if secili_ders:
            tum_satirlar = [r for r in tum_satirlar if r.get("ders") == secili_ders]
        if secili_tur in ("okul", "ev", "deneme"):
            tum_satirlar = [r for r in tum_satirlar if r.get("source") == secili_tur]

        sinif_oran = toplu_oran([(r["dogru"], r["soru_sayisi"]) for r in tum_satirlar])
        toplam_soru = sum(int(r.get("soru_sayisi") or 0) for r in tum_satirlar)

        tablo_dersler = list(school_courses())[:6]
        ogrenci_satirlari = []
        risk_girdi = []
        bantlar = {"0–34": 0, "35–49": 0, "50–64": 0, "65–79": 0, "80–100": 0}

        for o in ogrenciler:
            oid = int(o["id"])
            o_rows = [r for r in tum_satirlar if int(r["ogrenci_id"]) == oid]
            g_oran = toplu_oran([(r["dogru"], r["soru_sayisi"]) for r in o_rows])
            if g_oran is not None:
                if g_oran < 35:
                    bantlar["0–34"] += 1
                elif g_oran < 50:
                    bantlar["35–49"] += 1
                elif g_oran < 65:
                    bantlar["50–64"] += 1
                elif g_oran < 80:
                    bantlar["65–79"] += 1
                else:
                    bantlar["80–100"] += 1

            ders_oranlari = {}
            for d_adi in tablo_dersler:
                d_rows = [r for r in o_rows if r.get("ders") == d_adi]
                ders_oranlari[d_adi] = toplu_oran([(r["dogru"], r["soru_sayisi"]) for r in d_rows])

            ogrenci_satirlari.append({
                "id": oid,
                "ad_soyad": o["ad_soyad"],
                "ogr_no": o.get("ogr_no"),
                "genel_oran": g_oran,
                "ders_oranlari": ders_oranlari,
            })
            son_oranlar = [oran(r["dogru"], r["soru_sayisi"]) for r in reversed(o_rows[:5])]
            risk_girdi.append({
                "id": oid,
                "ad_soyad": o["ad_soyad"],
                "oran": g_oran,
                "test_gecmisi": son_oranlar,
                "bekleyen_ev": 0,
                "katilmadigi_deneme": 0,
            })

        risk_listesi = sinif_onerileri({"ogrenciler": risk_girdi})
        kpi = {
            "sinif_oran": sinif_oran,
            "toplam_soru": toplam_soru,
            "son_deneme_ort": None,
            "son_deneme_ad": None,
        }

        return render_template(
            "sinif_analiz_v2.html",
            siniflar=siniflar,
            secili_sinif=secili_sinif,
            seviye=seviye,
            aktif_moduller=moduller,
            dersler=school_courses(),
            secili_ders=secili_ders,
            secili_tur=secili_tur,
            kpi=kpi,
            risk_listesi=risk_listesi,
            dagilim=list(bantlar.items()),
            tablo_dersler=tablo_dersler,
            ogrenci_satirlari=ogrenci_satirlari,
        )

    @app.get("/veli/gelisim")
    def veli_gelisim():
        oid = session.get("veli_ogrenci_id")
        if not oid:
            return redirect(url_for("veli_giris"))
        paket = _ogrenci_analiz_paketi(int(oid))
        return render_template("veli_gelisim_v2.html", **paket)

    @app.get("/yonetici/okul-analiz")
    def yonetici_okul_analiz():
        if not (yonetici.active() or yetkili("yonetici")):
            abort(403)
        siniflar = db.aktif_sube_siniflari() or db.tum_siniflar()
        tablo_dersler = list(school_courses())[:5]
        sinif_satirlari = []
        tum_ciftler = []
        ders_toplamlari = {d: [] for d in tablo_dersler}

        for s in siniflar:
            sid = int(s["id"])
            sev = sinif_seviye_bul(s)
            ogr_list = db.sinif_ogrencileri(sid)
            oid_set = {int(o["id"]) for o in ogr_list}
            satirlar = sinav_okuyucu.birlesik_sonuclar(oid_set, teacher=True) if oid_set else []
            s_ciftler = [(r["dogru"], r["soru_sayisi"]) for r in satirlar]
            tum_ciftler.extend(s_ciftler)
            s_oran = toplu_oran(s_ciftler)

            ders_oranlari = {}
            for d_adi in tablo_dersler:
                d_cift = [(r["dogru"], r["soru_sayisi"]) for r in satirlar if r.get("ders") == d_adi]
                ders_toplamlari[d_adi].extend(d_cift)
                ders_oranlari[d_adi] = toplu_oran(d_cift)

            sinif_satirlari.append({
                "id": sid,
                "sinif_adi": s["sinif_adi"],
                "seviye": sev,
                "odev_oran": None,
                "test_oran": s_oran,
                "ders_oranlari": ders_oranlari,
            })

        okul_oran = toplu_oran(tum_ciftler)
        ders_ozet = [{"ders": d, "oran": toplu_oran(ciftler)} for d, ciftler in ders_toplamlari.items()]
        oneriler = okul_onerileri({
            "siniflar": [{"sinif_adi": s["sinif_adi"], "oran": s["test_oran"]} for s in sinif_satirlari],
            "dersler": ders_ozet,
            "eksik_giris_ogretmen_sayisi": 0,
        })

        kpi = {
            "okul_oran": okul_oran,
            "odev_oran": None,
            "sekiz_deneme_ort": None,
        }
        return render_template(
            "yonetici_okul_analiz.html",
            sinif_satirlari=sinif_satirlari,
            tablo_dersler=tablo_dersler,
            kpi=kpi,
            oneriler=oneriler,
        )
