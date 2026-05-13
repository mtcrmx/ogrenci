"""
Tamamlayici web ekranlari.

Bu modul, hazir HTML sablonlarinin bekledigi quiz, lig, oduller,
ogrenci paneli ve taktik uclarini Flask uygulamasina kaydeder.
"""

from __future__ import annotations

import json
import random
import sqlite3
import uuid
from datetime import datetime
from typing import Callable

from flask import jsonify, redirect, render_template, request, session, url_for

from database import (
    DB_PATH,
    sinif_ogrencileri,
    tik_ekle,
    tum_siniflar_ogrencileri,
    tum_tikleri_sifirla,
)

try:
    from quiz_sorulari import SORULAR
except Exception:
    SORULAR = {}


DERS_EMOJI = {
    "Turkce": "📚",
    "Türkçe": "📚",
    "Matematik": "🧮",
    "Fen Bilimleri": "🔬",
    "Sosyal Bilgiler": "🌍",
    "İngilizce": "🇬🇧",
    "Din Kültürü": "🕌",
}

SANS_SECENEKLER = [
    ("+5 Lig Puanı", 5, "#16a34a"),
    ("+3 Lig Puanı", 3, "#22c55e"),
    ("+1 Lig Puanı", 1, "#84cc16"),
    ("Pas", 0, "#64748b"),
    ("-1 Lig Puanı", -1, "#f97316"),
    ("Bonus Alkış", 0, "#db2777"),
]

ROZET_TANIMI = {
    "tertemiz": ("🧹", "Tertemiz", "Düşük tik sayısı ve düzenli davranış."),
    "seri": ("⚡", "Seri Yıldız", "Üst üste başarı serisi."),
    "alkis": ("👏", "Alkış Efsanesi", "Öğretmenlerden alkış topladı."),
    "ittifak": ("🤝", "Beraberlik Madalyası", "Sınıflar arası görevi tamamladı."),
    "quiz": ("🧠", "Bilgi Ustası", "Quizlerde yüksek başarı."),
}

ROZET_TANIMI.update({
    "xp_10": ("⭐", "İlk Işık", "10 XP kazanan öğrenciye verilir."),
    "xp_25": ("🌟", "Parlayan Yıldız", "25 XP kazanan öğrenciye verilir."),
    "xp_50": ("💎", "Elmas Emek", "50 XP kazanan öğrenciye verilir."),
    "xp_100": ("👑", "XP Efsanesi", "100 XP kazanan öğrenciye verilir."),
})

XP_ROZET_ESIKLERI = [
    (10, "xp_10"),
    (25, "xp_25"),
    (50, "xp_50"),
    (100, "xp_100"),
]

SEVIYELER = [
    (0, "🥚", "Yumurta"),
    (10, "🐣", "Civciv"),
    (25, "🦅", "Kartal"),
    (50, "🦁", "Aslan"),
    (100, "👑", "Efsane"),
]

MEVKILER = [
    {"no": 1, "emoji": "🦁", "ad": "Takım Kaptanı"},
    {"no": 2, "emoji": "🦊", "ad": "Kaptan Yardımcısı"},
    {"no": 3, "emoji": "🥅", "ad": "Kaleci"},
    {"no": 4, "emoji": "🧹", "ad": "Libero (Süpürücü)"},
    {"no": 5, "emoji": "➡️", "ad": "Sağ Bek"},
    {"no": 6, "emoji": "⬅️", "ad": "Sol Bek"},
    {"no": 7, "emoji": "🛡️", "ad": "Stoper"},
    {"no": 8, "emoji": "🧭", "ad": "Oyun Kurucu (10 Numara)"},
    {"no": 9, "emoji": "⚙️", "ad": "Dinamo İstasyon Oyuncusu"},
    {"no": 10, "emoji": "↗️", "ad": "Sağ Kanat"},
    {"no": 11, "emoji": "↖️", "ad": "Sol Kanat"},
    {"no": 12, "emoji": "🎯", "ad": "Santrafor (Golcü)"},
    {"no": 13, "emoji": "🧱", "ad": "Savunma Lideri"},
    {"no": 14, "emoji": "💫", "ad": "Joker Oyuncu"},
    {"no": 15, "emoji": "⚽", "ad": "Oyuncu"},
]

GOREVLER = [
    "İki sınıf birlikte sessiz okuma yapar.",
    "Birbirlerine teşekkür notu yazar.",
    "Koridor düzeni için ortak sorumluluk alır.",
    "Ders başlangıcında 5 dakika hazırlık sessizliği yapar.",
]

KART_NEDENLERI = [
    "Maç görevini aksatma",
    "Takım arkadaşını olumsuz etkileme",
    "Kurala uymama",
    "Centilmenlik dışı davranış",
]

YEDEK_TABLOLARI = [
    "tik_kayitlari",
    "lig_puan",
    "lig_maclari",
    "lig_kartlari",
    "quiz_sonuclari",
    "taktik_kayitlari",
    "rozetler",
    "ogrenci_xp",
    "alkislar",
    "gunluk_gorev",
    "gunluk_gorev_tamamlayan",
    "mufettisler",
    "ittifaklar",
]

SIFIRLANACAK_TABLOLAR = [
    "tik_kayitlari",
    "lig_kartlari",
    "lig_maclari",
    "quiz_sonuclari",
    "taktik_kayitlari",
    "rozetler",
    "ogrenci_xp",
    "alkislar",
    "gunluk_gorev_tamamlayan",
    "gunluk_gorev",
    "mufettisler",
    "ittifaklar",
]


def register_feature_routes(app, giris_zorunlu: Callable, sifir_parola: str, admin_sifre: str):
    _init_feature_db()

    @app.route("/ogrenci")
    def ogrenci_panel():
        odul = _odul_verisi()
        return render_template(
            "ogrenci.html",
            ogrenciler=_tum_ogrenciler_panel(),
            tablo=_lig_tablo(),
            maclar=_maclari_getir(),
            seviyeleri=odul["seviyeleri"],
            rozetler=odul["rozetler"],
            rozet_tanimi=ROZET_TANIMI,
            seri=odul["seri"],
            sezon=odul["sezon"],
            alkislar=odul["alkislar"],
            ittifaklar=odul["ittifaklar"],
            siniflar=_siniflar(),
            gorev=odul["gorev"],
            mufettis=odul["mufettis"],
        )

    @app.route("/api/ogrenci/veri")
    def api_ogrenci_veri():
        return jsonify({"ogrenciler": _tum_ogrenciler_panel(), "tablo": _lig_tablo(), "maclar": _maclari_getir()})

    @app.route("/api/ogrenci/ittifaklar")
    def api_ogrenci_ittifaklar():
        return jsonify(_ittifaklar_getir())

    @app.route("/api/ogrenci/ittifak/talep", methods=["POST"])
    def api_ogrenci_ittifak_talep():
        return _ittifak_olustur("ogrenci_talebi", request.form.get("seans", ""))

    @app.route("/api/ogrenci/kadro/<int:sinif_id>")
    def api_ogrenci_kadro(sinif_id):
        return jsonify(_kadro_getir(sinif_id))

    @app.route("/quiz/<int:sinif_id>")
    def quiz(sinif_id):
        sinif = _sinif(sinif_id) or {"id": sinif_id, "sinif_adi": "Sınıf"}
        bugun_yapilan = [
            r["ders"] for r in _rows(
                "SELECT DISTINCT ders FROM quiz_sonuclari WHERE sinif_id=? AND tarih=?",
                (sinif_id, _today()),
            )
        ]
        istatistik = _rows("""
            SELECT ders, SUM(dogru) AS toplam_dogru, SUM(yanlis) AS toplam_yanlis,
                   SUM(puan) AS toplam_puan
            FROM quiz_sonuclari WHERE sinif_id=?
            GROUP BY ders ORDER BY ders
        """, (sinif_id,))
        quiz_dersler = {str(k): list(v.keys()) for k, v in SORULAR.items()}
        return render_template(
            "quiz.html",
            sinif_id=sinif_id,
            sinif_adi=sinif["sinif_adi"],
            bugun_yapilan=bugun_yapilan,
            quiz_dersler=quiz_dersler,
            ders_emoji=DERS_EMOJI,
            istatistik=istatistik,
        )

    @app.route("/api/quiz/sorular")
    def api_quiz_sorular():
        seviye = request.args.get("sinif_seviyesi", type=int) or 5
        ders = request.args.get("ders", "")
        banka = list(SORULAR.get(seviye, {}).get(ders, []))
        random.shuffle(banka)
        anahtar = {}
        oturum_id = uuid.uuid4().hex
        sorular = []
        for i, soru in enumerate(banka[:7], 1):
            soru_id = f"{oturum_id}:{i}:{abs(hash(soru))}"
            anahtar[soru_id] = soru[5]
            sorular.append({
                "id": soru_id,
                "soru": soru[0],
                "secenek_a": soru[1],
                "secenek_b": soru[2],
                "secenek_c": soru[3],
                "secenek_d": soru[4],
            })
        session["quiz_cevap_anahtari"] = anahtar
        session["quiz_oturum_id"] = oturum_id
        session["quiz_oturum_tamamlandi"] = False
        return jsonify({"ok": True, "sorular": sorular, "oturum_id": oturum_id})

    @app.route("/api/quiz/cevapla", methods=["POST"])
    def api_quiz_cevapla():
        data = request.get_json(silent=True) or {}
        cevaplar = data.get("cevaplar", {})
        anahtar = session.get("quiz_cevap_anahtari", {})
        oturum_id = data.get("oturum_id")
        if not anahtar or oturum_id != session.get("quiz_oturum_id"):
            return jsonify({"ok": False, "hata": "Quiz oturumu gecersiz.", "puan_degisim": 0}), 409
        dogru = yanlis = 0
        sonuclar = {}
        for soru_id, gercek in anahtar.items():
            verilen = cevaplar.get(soru_id) or cevaplar.get(str(soru_id))
            ok = verilen == gercek
            dogru += int(ok)
            yanlis += int(not ok)
            sonuclar[str(soru_id)] = {"dogru": ok, "gercek": gercek}
        puan = dogru - yanlis
        sinif_id = int(data.get("sinif_id") or 0)
        ders = data.get("ders", "")
        seviye = int(data.get("sinif_seviyesi") or 0)
        if sinif_id:
            onceki = _one("""
                SELECT dogru, yanlis, puan
                FROM quiz_sonuclari
                WHERE sinif_id=? AND ders=? AND tarih=?
                ORDER BY id DESC LIMIT 1
            """, (sinif_id, ders, _today()))
            if onceki or session.get("quiz_oturum_tamamlandi"):
                session["quiz_oturum_tamamlandi"] = True
                return jsonify({
                    "ok": True,
                    "tekrar": True,
                    "dogru": onceki["dogru"] if onceki else dogru,
                    "yanlis": onceki["yanlis"] if onceki else yanlis,
                    "puan_degisim": 0,
                    "sonuclar": sonuclar,
                })
            _execute("""
                INSERT INTO quiz_sonuclari
                (sinif_id, sinif_seviyesi, ders, dogru, yanlis, puan, tarih)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sinif_id, seviye, ders, dogru, yanlis, puan, _today()))
            _lig_puan_ekle(sinif_id, puan, ag=max(puan, 0))
            session["quiz_oturum_tamamlandi"] = True
        return jsonify({"ok": True, "dogru": dogru, "yanlis": yanlis, "puan_degisim": puan, "sonuclar": sonuclar})

    @app.route("/lig")
    @giris_zorunlu
    def lig():
        return render_template(
            "lig.html",
            aktif=None,
            maclar=_maclari_getir(),
            tablo=_lig_tablo(),
            ogretmen_id=session["ogretmen_id"],
            var_ogretmenler=[session.get("ogretmen_adi", "")],
            kart_nedenleri=KART_NEDENLERI,
            sans_secenekler=SANS_SECENEKLER,
        )

    @app.route("/lig/olustur", methods=["POST"])
    @giris_zorunlu
    def lig_olustur():
        _maclari_olustur()
        return redirect(url_for("lig"))

    @app.route("/lig/sifirla", methods=["POST"])
    @giris_zorunlu
    def lig_sifirla_mac():
        if request.form.get("parola") == sifir_parola:
            _execute("DELETE FROM lig_kartlari")
            _execute("DELETE FROM lig_maclari")
            _execute("UPDATE lig_puan SET galibiyet=0, beraberlik=0, maglubiyet=0, ag=0, puan=0")
        return redirect(url_for("lig"))

    @app.route("/lig/mac/<int:mac_id>/sonuc", methods=["POST"])
    @giris_zorunlu
    def lig_mac_sonuc(mac_id):
        mac = _one("SELECT * FROM lig_maclari WHERE id=?", (mac_id,))
        if not mac:
            return jsonify({"ok": False, "durum": "hata"}), 404
        s1_t = request.form.get("s1_tamamlayan", type=int) or 0
        s2_t = request.form.get("s2_tamamlayan", type=int) or 0
        s1_top = request.form.get("s1_toplam", type=int) or 1
        s2_top = request.form.get("s2_toplam", type=int) or 1
        p1, p2 = s1_t / max(s1_top, 1), s2_t / max(s2_top, 1)
        kazanan = mac["sinif1_id"] if p1 > p2 else mac["sinif2_id"] if p2 > p1 else None
        durum = "tamamlandi" if kazanan else "var_incelemesi"
        _execute("""
            UPDATE lig_maclari
            SET s1_tamamlayan=?, s1_toplam=?, s2_tamamlayan=?, s2_toplam=?,
                kazanan_id=?, durum=?
            WHERE id=?
        """, (s1_t, s1_top, s2_t, s2_top, kazanan, durum, mac_id))
        if kazanan:
            kaybeden = mac["sinif2_id"] if kazanan == mac["sinif1_id"] else mac["sinif1_id"]
            _lig_puan_ekle(kazanan, 3, galibiyet=1)
            _lig_puan_ekle(kaybeden, 0, maglubiyet=1)
        return jsonify({"ok": True, "durum": durum, "kazanan_id": kazanan})

    @app.route("/lig/mac/<int:mac_id>/var", methods=["POST"])
    @giris_zorunlu
    def lig_mac_var(mac_id):
        sinif_id = request.form.get("sinif_id", type=int)
        if not sinif_id:
            return jsonify({"ok": False, "durum": "bekliyor"})
        _execute("UPDATE lig_maclari SET kazanan_id=?, durum='tamamlandi' WHERE id=?", (sinif_id, mac_id))
        _lig_puan_ekle(sinif_id, 3, galibiyet=1)
        return jsonify({"ok": True, "durum": "tamamlandi", "kazanan_id": sinif_id})

    @app.route("/lig/mac/<int:mac_id>/oyla", methods=["POST"])
    @giris_zorunlu
    def lig_mac_oyla(mac_id):
        return lig_mac_var(mac_id)

    @app.route("/api/lig/maclar")
    @giris_zorunlu
    def api_lig_maclar():
        return jsonify(_maclari_getir())

    @app.route("/api/sans-carki/cevir", methods=["POST"])
    @giris_zorunlu
    def api_sans_carki_cevir():
        sinif_id = request.form.get("sinif_id", type=int)
        sonuc = random.choice(SANS_SECENEKLER)
        if sinif_id and sonuc[1]:
            _lig_puan_ekle(sinif_id, int(sonuc[1]))
        return jsonify({"ok": True, "sonuc": sonuc[0], "puan": sonuc[1]})

    @app.route("/api/sinif/<int:sinif_id>/ogrenciler")
    def api_sinif_ogrenciler(sinif_id):
        return jsonify(sinif_ogrencileri(sinif_id))

    @app.route("/lig/mac/<int:mac_id>/kart", methods=["POST"])
    @giris_zorunlu
    def lig_mac_kart(mac_id):
        ogrenci_id = request.form.get("ogrenci_id", type=int)
        sinif_id = request.form.get("sinif_id", type=int)
        kart_turu = request.form.get("kart_turu", "sari")
        neden = request.form.get("neden", "Kurala uymama")
        if not ogrenci_id or not sinif_id:
            return jsonify({"ok": False, "hata": "Öğrenci seçilmedi."})
        tik_sayisi = 1 if kart_turu == "sari" else 2
        for _ in range(tik_sayisi):
            tik_ekle(ogrenci_id, session["ogretmen_id"], f"{'🟨' if kart_turu == 'sari' else '🟥'} {neden}")
        puan_cezasi = 0
        if kart_turu == "kirmizi":
            puan_cezasi = 2
            _lig_puan_ekle(sinif_id, -puan_cezasi)
        _execute("""
            INSERT INTO lig_kartlari (mac_id, ogrenci_id, sinif_id, kart_turu, neden, tarih)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (mac_id, ogrenci_id, sinif_id, kart_turu, neden, _today()))
        return jsonify({"ok": True, "tik_eklendi": tik_sayisi, "puan_cezasi": puan_cezasi})

    @app.route("/oduller")
    @giris_zorunlu
    def oduller():
        return render_template("oduller.html", **_odul_verisi())

    @app.route("/api/gorev/tamamla", methods=["POST"])
    @giris_zorunlu
    def api_gorev_tamamla():
        gorev_id = request.form.get("gorev_id", type=int)
        sinif_id = request.form.get("sinif_id", type=int)
        gorev = _one("SELECT * FROM gunluk_gorev WHERE id=?", (gorev_id,))
        if not gorev or not sinif_id:
            return jsonify({"ok": False, "sebep": "Görev bulunamadı."})
        _execute("INSERT OR IGNORE INTO gunluk_gorev_tamamlayan (gorev_id, sinif_id) VALUES (?, ?)", (gorev_id, sinif_id))
        _lig_puan_ekle(sinif_id, gorev["puan"], ag=gorev["puan"])
        return jsonify({"ok": True, "puan": gorev["puan"]})

    @app.route("/api/mufettis/belirle", methods=["POST"])
    @giris_zorunlu
    def api_mufettis_belirle():
        ogrenci_id = request.form.get("ogrenci_id", type=int)
        ogr = _one("SELECT * FROM ogrenciler WHERE id=?", (ogrenci_id,))
        if not ogr:
            return jsonify({"ok": False, "sebep": "Öğrenci bulunamadı."})
        _execute("INSERT INTO mufettisler (ogrenci_id, sinif_id, tarih) VALUES (?, ?, ?)", (ogrenci_id, ogr["sinif_id"], _today()))
        return jsonify({"ok": True})

    @app.route("/api/mufettis/degerlendir", methods=["POST"])
    @giris_zorunlu
    def api_mufettis_degerlendir():
        mid = request.form.get("mufettis_id", type=int)
        sonuc = request.form.get("sonuc", "ortalama")
        _execute("UPDATE mufettisler SET sonuc=? WHERE id=?", (sonuc, mid))
        if sonuc == "iyi":
            muf = _one("SELECT sinif_id, ogrenci_id FROM mufettisler WHERE id=?", (mid,))
            if muf:
                _lig_puan_ekle(muf["sinif_id"], 2, ag=2)
                _ogrenci_xp_ekle(muf["ogrenci_id"], muf["sinif_id"], 10)
                _rozet_ekle(muf["sinif_id"], muf["ogrenci_id"], "quiz")
        return jsonify({"ok": True})

    @app.route("/api/ittifak/olustur", methods=["POST"])
    @giris_zorunlu
    def api_ittifak_olustur():
        return _ittifak_olustur("bekliyor", "")

    @app.route("/api/ittifak/onayla", methods=["POST"])
    @giris_zorunlu
    def api_ittifak_onayla():
        _execute("UPDATE ittifaklar SET durum='bekliyor' WHERE id=?", (request.form.get("ittifak_id", type=int),))
        return jsonify({"ok": True})

    @app.route("/api/ittifak/reddet", methods=["POST"])
    @giris_zorunlu
    def api_ittifak_reddet():
        _execute("UPDATE ittifaklar SET durum='reddedildi' WHERE id=?", (request.form.get("ittifak_id", type=int),))
        return jsonify({"ok": True})

    @app.route("/api/ittifak/tamamla", methods=["POST"])
    @giris_zorunlu
    def api_ittifak_tamamla():
        it = _one("SELECT * FROM ittifaklar WHERE id=?", (request.form.get("ittifak_id", type=int),))
        if not it:
            return jsonify({"ok": False})
        _execute("UPDATE ittifaklar SET durum='tamamlandi' WHERE id=?", (it["id"],))
        _lig_puan_ekle(it["sinif1_id"], 3, ag=3)
        _lig_puan_ekle(it["sinif2_id"], 3, ag=3)
        return jsonify({"ok": True})

    @app.route("/api/alkis/ver", methods=["POST"])
    @giris_zorunlu
    def api_alkis_ver():
        ogrenci_id = request.form.get("ogrenci_id", type=int)
        sinif_id = request.form.get("sinif_id", type=int)
        if not ogrenci_id or not sinif_id:
            return jsonify({"ok": False})
        _execute("""
            INSERT INTO alkislar (ogrenci_id, sinif_id, mesaj, veren, tarih)
            VALUES (?, ?, ?, ?, ?)
        """, (ogrenci_id, sinif_id, request.form.get("mesaj", "Harika iş!"), session.get("ogretmen_adi", "Öğretmen"), _today()))
        toplam = _one("SELECT COUNT(*) AS c FROM alkislar WHERE ogrenci_id=?", (ogrenci_id,))["c"]
        _lig_puan_ekle(sinif_id, 1, ag=1)
        _ogrenci_xp_ekle(ogrenci_id, sinif_id, 1)
        if toplam >= 5:
            _rozet_ekle(sinif_id, ogrenci_id, "alkis")
        return jsonify({"ok": True, "toplam_alkis": toplam})

    @app.route("/taktik/<int:sinif_id>")
    @giris_zorunlu
    def taktik(sinif_id):
        sinif = _sinif(sinif_id) or {"sinif_adi": "Sınıf"}
        kayit_row = _one("SELECT veri FROM taktik_kayitlari WHERE sinif_id=?", (sinif_id,))
        kayit = json.loads(kayit_row["veri"]) if kayit_row else {"renk": "#16a34a", "oyuncular": {}}
        return render_template("taktik.html", sinif_id=sinif_id, sinif_adi=sinif["sinif_adi"], kadro=_kadro_getir(sinif_id), kayit=kayit, mevkiler_json=MEVKILER)

    @app.route("/api/taktik/<int:sinif_id>/kaydet", methods=["POST"])
    @giris_zorunlu
    def api_taktik_kaydet(sinif_id):
        data = request.get_json(silent=True) or {}
        _execute("""
            INSERT INTO taktik_kayitlari (sinif_id, veri, guncellendi)
            VALUES (?, ?, ?)
            ON CONFLICT(sinif_id) DO UPDATE SET veri=excluded.veri, guncellendi=excluded.guncellendi
        """, (sinif_id, json.dumps(data, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")))
        return jsonify({"ok": True})

    @app.route("/sifirla")
    @giris_zorunlu
    def sifirla_sayfasi():
        return render_template(
            "sifirla.html",
            ogretmen_adi=session.get("ogretmen_adi", ""),
            yedekler=_yedek_listesi(),
        )

    @app.route("/api/admin/yedekle", methods=["POST"])
    @giris_zorunlu
    def api_admin_yedekle():
        hata = _admin_sifre_hatasi(admin_sifre)
        if hata:
            return hata
        yedek = _yedek_olustur(session.get("ogretmen_adi", "Öğretmen"))
        return jsonify({"ok": True, "yedek": yedek, "yedekler": _yedek_listesi()})

    @app.route("/api/admin/yedek/<int:yedek_id>/geri-yukle", methods=["POST"])
    @giris_zorunlu
    def api_admin_yedek_geri_yukle(yedek_id):
        hata = _admin_sifre_hatasi(admin_sifre)
        if hata:
            return hata
        ok, sonuc = _yedek_geri_yukle(yedek_id)
        if not ok:
            return jsonify({"ok": False, "hata": sonuc}), 404
        return jsonify({"ok": True, "geri_yuklenen": sonuc})

    @app.route("/api/admin/yedek/<int:yedek_id>/sil", methods=["POST"])
    @giris_zorunlu
    def api_admin_yedek_sil(yedek_id):
        hata = _admin_sifre_hatasi(admin_sifre)
        if hata:
            return hata
        silindi = _yedek_sil(yedek_id)
        if not silindi:
            return jsonify({"ok": False, "hata": "Yedek bulunamadı."}), 404
        return jsonify({"ok": True, "yedekler": _yedek_listesi()})

    @app.route("/api/admin/sifirla", methods=["POST"])
    @giris_zorunlu
    def api_admin_sifirla():
        if _admin_sifre_al() != admin_sifre:
            return jsonify({"ok": False, "hata": "Yönetici şifresi hatalı."}), 403
        silinen = {}
        for tablo in SIFIRLANACAK_TABLOLAR:
            silinen[tablo] = _tablo_temizle(tablo)
        _execute("UPDATE lig_puan SET galibiyet=0, beraberlik=0, maglubiyet=0, ag=0, puan=0, sezon_puan=0, guncel_seri=0, en_uzun_seri=0")
        return jsonify({"ok": True, "silinen": silinen, "yedekler_korundu": True})


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _rows(sql: str, params=()) -> list[dict]:
    con = _conn()
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows


def _one(sql: str, params=()) -> dict | None:
    rows = _rows(sql, params)
    return rows[0] if rows else None


def _execute(sql: str, params=()):
    con = _conn()
    con.execute(sql, params)
    con.commit()
    con.close()


def _admin_sifre_al() -> str:
    data = request.get_json(silent=True) or {}
    return (data.get("sifre") or request.form.get("sifre") or "").strip()


def _admin_sifre_hatasi(admin_sifre: str):
    if _admin_sifre_al() != admin_sifre:
        return jsonify({"ok": False, "hata": "Yönetici şifresi hatalı."}), 403
    return None


def _tablo_temizle(tablo: str) -> int:
    if tablo not in SIFIRLANACAK_TABLOLAR:
        raise ValueError("İzin verilmeyen tablo.")
    con = _conn()
    try:
        sayi = con.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0]
        con.execute(f"DELETE FROM {tablo}")
        con.commit()
        return int(sayi)
    finally:
        con.close()


def _yedek_listesi() -> list[dict]:
    return _rows("""
        SELECT id, ad, olusturan, tarih
        FROM sistem_yedekleri
        ORDER BY id DESC
    """)


def _yedek_olustur(olusturan: str) -> dict:
    con = _conn()
    try:
        veri = {}
        for tablo in YEDEK_TABLOLARI:
            rows = [dict(r) for r in con.execute(f"SELECT * FROM {tablo}").fetchall()]
            veri[tablo] = rows
        tarih = datetime.now().isoformat(timespec="seconds")
        ad = f"Sistem yedeği {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        con.execute(
            "INSERT INTO sistem_yedekleri (ad, veri, olusturan, tarih) VALUES (?, ?, ?, ?)",
            (ad, json.dumps(veri, ensure_ascii=False), olusturan, tarih),
        )
        yedek_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.commit()
        return {"id": yedek_id, "ad": ad, "olusturan": olusturan, "tarih": tarih}
    finally:
        con.close()


def _yedek_geri_yukle(yedek_id: int) -> tuple[bool, dict | str]:
    con = _conn()
    try:
        row = con.execute("SELECT veri FROM sistem_yedekleri WHERE id=?", (yedek_id,)).fetchone()
        if not row:
            return False, "Yedek bulunamadı."
        veri = json.loads(row["veri"] or "{}")
        con.execute("PRAGMA foreign_keys = OFF")
        for tablo in reversed(YEDEK_TABLOLARI):
            con.execute(f"DELETE FROM {tablo}")
        geri_yuklenen = {}
        for tablo in YEDEK_TABLOLARI:
            rows = veri.get(tablo, [])
            geri_yuklenen[tablo] = len(rows)
            if not rows:
                continue
            kolonlar = list(rows[0].keys())
            yer = ",".join("?" * len(kolonlar))
            kolon_sql = ",".join(kolonlar)
            for item in rows:
                con.execute(
                    f"INSERT INTO {tablo} ({kolon_sql}) VALUES ({yer})",
                    [item.get(k) for k in kolonlar],
                )
        con.commit()
        con.execute("PRAGMA foreign_keys = ON")
        return True, geri_yuklenen
    except Exception as exc:
        con.rollback()
        return False, str(exc)
    finally:
        con.close()


def _yedek_sil(yedek_id: int) -> bool:
    con = _conn()
    try:
        cur = con.execute("DELETE FROM sistem_yedekleri WHERE id=?", (yedek_id,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def _init_feature_db():
    con = _conn()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS lig_puan (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            galibiyet INTEGER NOT NULL DEFAULT 0,
            beraberlik INTEGER NOT NULL DEFAULT 0,
            maglubiyet INTEGER NOT NULL DEFAULT 0,
            ag INTEGER NOT NULL DEFAULT 0,
            puan INTEGER NOT NULL DEFAULT 0,
            sezon_puan INTEGER NOT NULL DEFAULT 0,
            guncel_seri INTEGER NOT NULL DEFAULT 0,
            en_uzun_seri INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS lig_maclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT NOT NULL,
            seans TEXT NOT NULL,
            sinif1_id INTEGER NOT NULL REFERENCES siniflar(id),
            sinif2_id INTEGER NOT NULL REFERENCES siniflar(id),
            gorev TEXT NOT NULL,
            s1_tamamlayan INTEGER,
            s1_toplam INTEGER,
            s2_tamamlayan INTEGER,
            s2_toplam INTEGER,
            kazanan_id INTEGER,
            durum TEXT NOT NULL DEFAULT 'bekliyor'
        );
        CREATE TABLE IF NOT EXISTS lig_kartlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_id INTEGER NOT NULL REFERENCES lig_maclari(id),
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            kart_turu TEXT NOT NULL,
            neden TEXT NOT NULL,
            tarih TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quiz_sonuclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            sinif_seviyesi INTEGER NOT NULL,
            ders TEXT NOT NULL,
            dogru INTEGER NOT NULL,
            yanlis INTEGER NOT NULL,
            puan INTEGER NOT NULL,
            tarih TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS taktik_kayitlari (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            veri TEXT NOT NULL,
            guncellendi TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rozetler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id INTEGER REFERENCES siniflar(id),
            ogrenci_id INTEGER REFERENCES ogrenciler(id),
            rozet_kodu TEXT NOT NULL,
            sahip TEXT NOT NULL,
            tarih TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ogrenci_xp (
            ogrenci_id INTEGER PRIMARY KEY REFERENCES ogrenciler(id),
            xp INTEGER NOT NULL DEFAULT 0,
            guncellendi TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS alkislar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            mesaj TEXT NOT NULL,
            veren TEXT NOT NULL,
            tarih TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gunluk_gorev (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gorev TEXT NOT NULL,
            puan INTEGER NOT NULL DEFAULT 3,
            tarih TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS gunluk_gorev_tamamlayan (
            gorev_id INTEGER NOT NULL REFERENCES gunluk_gorev(id),
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            PRIMARY KEY (gorev_id, sinif_id)
        );
        CREATE TABLE IF NOT EXISTS mufettisler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            tarih TEXT NOT NULL,
            sonuc TEXT
        );
        CREATE TABLE IF NOT EXISTS ittifaklar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif1_id INTEGER NOT NULL REFERENCES siniflar(id),
            sinif2_id INTEGER NOT NULL REFERENCES siniflar(id),
            gorev TEXT NOT NULL,
            seans TEXT,
            durum TEXT NOT NULL DEFAULT 'bekliyor',
            tarih TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sistem_yedekleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            veri TEXT NOT NULL,
            olusturan TEXT NOT NULL,
            tarih TEXT NOT NULL
        );
    """)
    for sinif in con.execute("SELECT id FROM siniflar").fetchall():
        con.execute("INSERT OR IGNORE INTO lig_puan (sinif_id) VALUES (?)", (sinif["id"],))
    con.commit()
    con.close()


def _siniflar() -> list[dict]:
    return _rows("SELECT id, sinif_adi FROM siniflar ORDER BY sinif_adi")


def _sinif(sinif_id: int) -> dict | None:
    return _one("SELECT id, sinif_adi FROM siniflar WHERE id=?", (sinif_id,))


def _lig_puan_ekle(sinif_id: int, puan: int, *, galibiyet=0, beraberlik=0, maglubiyet=0, ag=0):
    con = _conn()
    con.execute("INSERT OR IGNORE INTO lig_puan (sinif_id) VALUES (?)", (sinif_id,))
    con.execute("""
        UPDATE lig_puan
        SET puan=puan+?, sezon_puan=sezon_puan+?,
            galibiyet=galibiyet+?, beraberlik=beraberlik+?,
            maglubiyet=maglubiyet+?, ag=ag+?,
            guncel_seri=CASE WHEN ? > 0 THEN guncel_seri+1 ELSE guncel_seri END,
            en_uzun_seri=CASE WHEN ? > 0 AND guncel_seri+1 > en_uzun_seri THEN guncel_seri+1 ELSE en_uzun_seri END
        WHERE sinif_id=?
    """, (puan, max(puan, 0), galibiyet, beraberlik, maglubiyet, ag, puan, puan, sinif_id))
    con.commit()
    con.close()


def _lig_tablo() -> list[dict]:
    return _rows("""
        SELECT s.id AS sinif_id, s.sinif_adi,
               COALESCE(p.galibiyet,0) AS galibiyet,
               COALESCE(p.beraberlik,0) AS beraberlik,
               COALESCE(p.maglubiyet,0) AS maglubiyet,
               COALESCE(p.ag,0) AS ag,
               COALESCE(p.puan,0) AS puan,
               COALESCE(p.sezon_puan,0) AS sezon_puan,
               COALESCE(p.guncel_seri,0) AS guncel_seri,
               COALESCE(p.en_uzun_seri,0) AS en_uzun_seri
        FROM siniflar s
        LEFT JOIN lig_puan p ON p.sinif_id=s.id
        ORDER BY puan DESC, galibiyet DESC, s.sinif_adi
    """)


def _maclari_getir() -> list[dict]:
    maclar = _rows("""
        SELECT m.*, s1.sinif_adi AS sinif1_adi, s2.sinif_adi AS sinif2_adi
        FROM lig_maclari m
        JOIN siniflar s1 ON s1.id=m.sinif1_id
        JOIN siniflar s2 ON s2.id=m.sinif2_id
        WHERE m.tarih=?
        ORDER BY CASE m.seans WHEN 'sabah' THEN 0 ELSE 1 END, m.id
    """, (_today(),))
    kartlar = _rows("""
        SELECT k.*, o.ad_soyad AS ogrenci_adi, s.sinif_adi
        FROM lig_kartlari k
        JOIN ogrenciler o ON o.id=k.ogrenci_id
        JOIN siniflar s ON s.id=k.sinif_id
        WHERE k.tarih=?
        ORDER BY k.id
    """, (_today(),))
    kart_map: dict[int, list[dict]] = {}
    for kart in kartlar:
        kart_map.setdefault(kart["mac_id"], []).append(kart)
    for mac in maclar:
        mac["kartlar"] = kart_map.get(mac["id"], [])
    return maclar


def _maclari_olustur():
    siniflar = _siniflar()
    if len(siniflar) < 2 or _one("SELECT id FROM lig_maclari WHERE tarih=?", (_today(),)):
        return
    ids = [s["id"] for s in siniflar]
    pairs = [(ids[i], ids[-(i + 1)]) for i in range(len(ids) // 2)]
    con = _conn()
    for seans in ("sabah", "ogleden_sonra"):
        for i, (s1, s2) in enumerate(pairs):
            if seans == "ogleden_sonra":
                s1, s2 = s2, s1
            con.execute("""
                INSERT INTO lig_maclari
                (tarih, seans, sinif1_id, sinif2_id, gorev, s1_toplam, s2_toplam)
                VALUES (?, ?, ?, ?, ?, 25, 25)
            """, (_today(), seans, s1, s2, GOREVLER[i % len(GOREVLER)]))
    con.commit()
    con.close()


def _durum_ogrenci(tik: int):
    if tik >= 12:
        return "disiplin", "🚨", "Disiplin Cezası"
    if tik >= 9:
        return "tutanak", "📋", "Tutanak"
    if tik >= 6:
        return "veli", "📱", "Veli Bilgilendirme"
    if tik >= 3:
        return "uyari", "⚠️", "Uyarı"
    return "temiz", "✅", None


def _tum_ogrenciler_panel() -> list[dict]:
    siniflar = _siniflar()
    sinif_map = {s["id"]: s["sinif_adi"] for s in siniflar}
    sinif_id_map = {s["sinif_adi"]: s["id"] for s in siniflar}
    ogrenciler = tum_siniflar_ogrencileri([s["id"] for s in siniflar]) if siniflar else []
    for ogr in ogrenciler:
        ogr["sinif_id"] = ogr.get("sinif_id") or sinif_id_map.get(ogr.get("sinif_adi"))
        ogr["sinif_adi"] = ogr.get("sinif_adi") or sinif_map.get(ogr["sinif_id"], "")
        ogr["durum"], ogr["emoji"], ogr["etiket"] = _durum_ogrenci(ogr["tik_sayisi"])
    ogrenci_rozetleri_ekle(ogrenciler)
    ogrenciler.sort(key=lambda o: (-o["tik_sayisi"], o["sinif_adi"], o["ad_soyad"]))
    return ogrenciler


def _seviye_bilgisi() -> list[dict]:
    rows = []
    for sinif in _lig_tablo():
        puan = sinif["puan"]
        aktif = max((s for s in SEVIYELER if puan >= s[0]), key=lambda s: s[0])
        sonraki = next((s for s in SEVIYELER if s[0] > puan), SEVIYELER[-1])
        rows.append({
            "sinif_id": sinif["sinif_id"],
            "sinif_adi": sinif["sinif_adi"],
            "puan": puan,
            "esik": aktif[0],
            "emoji": aktif[1],
            "seviye_emoji": aktif[1],
            "ad": aktif[2],
            "sonraki_esik": sonraki[0],
            "sonraki_emoji": sonraki[1],
            "sonraki_ad": sonraki[2],
        })
    return rows


def _gorev_getir() -> dict:
    gorev = _one("SELECT * FROM gunluk_gorev WHERE tarih=?", (_today(),))
    if not gorev:
        _execute("INSERT INTO gunluk_gorev (gorev, puan, tarih) VALUES (?, 3, ?)", (random.choice(GOREVLER), _today()))
        gorev = _one("SELECT * FROM gunluk_gorev WHERE tarih=?", (_today(),))
    tamamlayan = _rows("SELECT sinif_id FROM gunluk_gorev_tamamlayan WHERE gorev_id=?", (gorev["id"],))
    gorev["tamamlayan_ids"] = [r["sinif_id"] for r in tamamlayan]
    return gorev


def _odul_verisi() -> dict:
    return {
        "aktif": None,
        "siniflar": _siniflar(),
        "ogretmen_adi": session.get("ogretmen_adi", "Öğretmen"),
        "seviyeleri": _seviye_bilgisi(),
        "rozetler": _rozetler_getir(),
        "rozet_tanimi": ROZET_TANIMI,
        "envanterler": _ogrenci_envanterleri(),
        "seri": _lig_tablo(),
        "gorev": _gorev_getir(),
        "mufettis": _mufettis_getir(),
        "mufettis_yetkili": True,
        "bekleyen_talepler": [it for it in _ittifaklar_getir() if it["durum"] == "ogrenci_talebi"],
        "ittifaklar": _ittifaklar_getir(),
        "sezon": _lig_tablo(),
        "alkislar": _alkislar_getir(),
        "sans_secenekler": SANS_SECENEKLER,
    }


def _mufettis_getir():
    rows = _rows("""
        SELECT m.*, o.ad_soyad, s.sinif_adi
        FROM mufettisler m
        JOIN ogrenciler o ON o.id=m.ogrenci_id
        JOIN siniflar s ON s.id=m.sinif_id
        WHERE m.tarih=?
        ORDER BY m.id DESC
    """, (_today(),))
    return rows[0] if rows else None


def _ittifaklar_getir() -> list[dict]:
    return _rows("""
        SELECT i.*, s1.sinif_adi AS sinif1_adi, s2.sinif_adi AS sinif2_adi
        FROM ittifaklar i
        JOIN siniflar s1 ON s1.id=i.sinif1_id
        JOIN siniflar s2 ON s2.id=i.sinif2_id
        WHERE i.tarih=?
        ORDER BY i.id DESC
    """, (_today(),))


def _ittifak_olustur(durum: str, seans: str):
    s1 = request.form.get("sinif1_id", type=int)
    s2 = request.form.get("sinif2_id", type=int)
    if not s1 or not s2 or s1 == s2:
        return jsonify({"ok": False, "sebep": "İki farklı sınıf seçin."})
    gorev = random.choice(GOREVLER)
    _execute("""
        INSERT INTO ittifaklar (sinif1_id, sinif2_id, gorev, seans, durum, tarih)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (s1, s2, gorev, seans, durum, _today()))
    return jsonify({"ok": True, "gorev": gorev})


def _alkislar_getir() -> list[dict]:
    return _rows("""
        SELECT a.*, o.ad_soyad, o.ad_soyad AS ogrenci,
               a.veren AS ogretmen, s.sinif_adi
        FROM alkislar a
        JOIN ogrenciler o ON o.id=a.ogrenci_id
        JOIN siniflar s ON s.id=a.sinif_id
        ORDER BY a.id DESC LIMIT 25
    """)


def _rozetler_getir() -> list[dict]:
    rozetler = _rows("""
        SELECT r.*, s.sinif_adi, COALESCE(o.ad_soyad, r.sahip) AS sahip
        FROM rozetler r
        LEFT JOIN siniflar s ON s.id=r.sinif_id
        LEFT JOIN ogrenciler o ON o.id=r.ogrenci_id
        ORDER BY r.id DESC LIMIT 30
    """)
    for rozet in rozetler:
        emoji, ad, _ = ROZET_TANIMI.get(rozet["rozet_kodu"], ("🏅", rozet["rozet_kodu"], ""))
        rozet["emoji"] = emoji
        rozet["rozet_adi"] = ad
    return rozetler


def _ogrenci_xp_haritasi(ogrenci_ids: list[int] | None = None) -> dict[int, int]:
    if ogrenci_ids is None:
        rows = _rows("SELECT ogrenci_id, xp FROM ogrenci_xp")
    elif not ogrenci_ids:
        return {}
    else:
        yer = ",".join("?" * len(ogrenci_ids))
        rows = _rows(f"SELECT ogrenci_id, xp FROM ogrenci_xp WHERE ogrenci_id IN ({yer})", ogrenci_ids)
    return {int(r["ogrenci_id"]): int(r["xp"] or 0) for r in rows}


def _ogrenci_rozet_haritasi(ogrenci_ids: list[int] | None = None) -> dict[int, list[dict]]:
    if ogrenci_ids is None:
        rows = _rows("""
            SELECT r.*, s.sinif_adi
            FROM rozetler r
            LEFT JOIN siniflar s ON s.id=r.sinif_id
            WHERE r.ogrenci_id IS NOT NULL
            ORDER BY r.id DESC
        """)
    elif not ogrenci_ids:
        return {}
    else:
        yer = ",".join("?" * len(ogrenci_ids))
        rows = _rows(f"""
            SELECT r.*, s.sinif_adi
            FROM rozetler r
            LEFT JOIN siniflar s ON s.id=r.sinif_id
            WHERE r.ogrenci_id IN ({yer})
            ORDER BY r.id DESC
        """, ogrenci_ids)

    rozet_map: dict[int, list[dict]] = {}
    gorulen: set[tuple[int, str]] = set()
    for rozet in rows:
        oid = int(rozet["ogrenci_id"])
        kod = rozet["rozet_kodu"]
        anahtar = (oid, kod)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        emoji, ad, aciklama = ROZET_TANIMI.get(kod, ("🏅", kod, ""))
        rozet["emoji"] = emoji
        rozet["rozet_adi"] = ad
        rozet["aciklama"] = aciklama
        rozet_map.setdefault(oid, []).append(rozet)
    return rozet_map


def ogrenci_rozetleri_ekle(ogrenciler: list[dict]) -> list[dict]:
    ids = [int(o["id"]) for o in ogrenciler if o.get("id")]
    if not ids:
        return ogrenciler
    try:
        xp_map = _ogrenci_xp_haritasi(ids)
        rozet_map = _ogrenci_rozet_haritasi(ids)
    except sqlite3.OperationalError:
        xp_map, rozet_map = {}, {}

    for ogr in ogrenciler:
        oid = int(ogr["id"])
        rozetler = rozet_map.get(oid, [])
        ogr["xp"] = xp_map.get(oid, 0)
        ogr["rozetler"] = rozetler
        ogr["rozet_ozet"] = "".join(r["emoji"] for r in rozetler[:4])
        ogr["rozet_sayisi"] = len(rozetler)
    return ogrenciler


def _ogrenci_envanterleri() -> list[dict]:
    envanter = []
    for ogr in _tum_ogrenciler_panel():
        if ogr.get("xp", 0) > 0 or ogr.get("rozetler"):
            envanter.append(ogr)
    envanter.sort(key=lambda o: (-o.get("xp", 0), -o.get("rozet_sayisi", 0), o["sinif_adi"], o["ad_soyad"]))
    return envanter


def _rozet_ekle(sinif_id: int, ogrenci_id: int | None, kod: str):
    if ogrenci_id is not None:
        var = _one("SELECT id FROM rozetler WHERE ogrenci_id=? AND rozet_kodu=? LIMIT 1", (ogrenci_id, kod))
        if var:
            return
    sahip = "Sınıf" if ogrenci_id is None else (_one("SELECT ad_soyad FROM ogrenciler WHERE id=?", (ogrenci_id,)) or {}).get("ad_soyad", "Öğrenci")
    _execute("""
        INSERT INTO rozetler (sinif_id, ogrenci_id, rozet_kodu, sahip, tarih)
        VALUES (?, ?, ?, ?, ?)
    """, (sinif_id, ogrenci_id, kod, sahip, _today()))


def _ogrenci_xp_ekle(ogrenci_id: int, sinif_id: int, xp: int):
    if not ogrenci_id or xp <= 0:
        return
    simdi = datetime.now().isoformat(timespec="seconds")
    con = _conn()
    con.execute("""
        INSERT INTO ogrenci_xp (ogrenci_id, xp, guncellendi)
        VALUES (?, ?, ?)
        ON CONFLICT(ogrenci_id) DO UPDATE SET
            xp=ogrenci_xp.xp+excluded.xp,
            guncellendi=excluded.guncellendi
    """, (ogrenci_id, xp, simdi))
    toplam = con.execute("SELECT xp FROM ogrenci_xp WHERE ogrenci_id=?", (ogrenci_id,)).fetchone()["xp"]
    con.commit()
    con.close()
    for esik, kod in XP_ROZET_ESIKLERI:
        if toplam >= esik:
            _rozet_ekle(sinif_id, ogrenci_id, kod)


def _kadro_getir(sinif_id: int) -> list[dict]:
    ogrenciler = sinif_ogrencileri(sinif_id)
    kayit = _one("SELECT veri FROM taktik_kayitlari WHERE sinif_id=?", (sinif_id,))
    roller = {}
    if kayit:
        try:
            data = json.loads(kayit["veri"])
            roller = {int(k): v.get("rol", "Oyuncu") for k, v in data.get("oyuncular", {}).items()}
        except Exception:
            roller = {}
    for i, ogr in enumerate(ogrenciler):
        ogr["mevki"] = roller.get(ogr["id"], MEVKILER[i % len(MEVKILER)]["ad"])
    return ogrenciler
