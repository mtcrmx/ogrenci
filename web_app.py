"""
web_app.py  —  Erenler Cumhuriyet Ortaokulu Ogrenci Takip
(Flask rotalari <int:...> ile tam; GitHub/Render senkron)
"""

import os, tempfile
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, send_file, make_response,
)
from database import (
    initialize_db, KRITERLER, OLUMLU_KRITERLER,
    tum_ogretmenler, tum_sifre_listesi,
    ogretmen_dogrula, ogretmen_id_bul, ogretmen_siniflari,
    sinif_ogrencileri, tum_okul_ogrencileri, ogrenci_tik_gecmisi,
    tik_ekle, tek_ogrenci_sifirla, sinif_sifirla, tum_tikleri_sifirla,
    olumlu_puan_ekle, lig_siralama, lig_manuel_sifirla, sinif_olumlu_gecmis,
    # Mac sistemi
    gunluk_mac_olustur, bugun_maclar, mac_detay,
    mac_sonucu_gir, mac_oy_ver, lig_puan_tablosu, lig_mac_tablo_sifirla,
    VAR_INCELEME_OGRETMENLER,
    # Kadro sistemi
    sinif_kadro_getir, sinif_kadro_olustur, MEVKILER,
    # Kart sistemi
    kart_ver, mac_kartlari, KART_NEDENLERI,
    # Gamification
    SEVIYELER, ROZET_TANIMI, SANS_CARKI_SEENEKLERI,
    MUFETTIS_YETKILILERI,
    sinif_seviye_hesapla, tum_sinif_seviyeleri,
    rozet_ver_ogrenci, son_rozetler,
    sinif_seri_guncelle, tum_seri_tablosu,
    bugun_gorev, gorev_tamamla,
    bugun_mufettis, mufettis_degerlendir, mufettis_belirle,
    alkis_ver, son_alkislar,
    sezon_puan_ekle, sezon_siralama,
    ittifak_olustur, aktif_ittifaklar, ittifak_tamamla,
    ittifak_ogrenci_talebi, ittifak_onayla, ittifak_reddet,
    bekleyen_ogrenci_talepleri,
    sans_carki_cevir,
    taktik_yukle, taktik_kaydet, taktik_kadro_guncelle,
    tum_verileri_sifirla,
    quiz_sorular_getir, quiz_sonuc_kaydet, quiz_gunluk_dersleri,
    quiz_sinif_istatistik, quiz_sorulari_yukle,
    tik_dondur,
    odev_ekle, sinif_odevleri, odev_detay, odev_tamamla,
    odev_tamamlandi_kaldir, ogrenci_odevleri,
)
from export import excel_raporu_olustur, OPENPYXL_OK

_BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(_BASE, "templates"),
            static_folder=os.path.join(_BASE, "static"))
app.secret_key = os.environ.get("SECRET_KEY", "erenler-cumhuriyet-2025-gizli")

SIFIR_PAROLA = "1234"
ADMIN_SIFRE  = "ECadmin"
OGRENCI_SIFRE = os.environ.get("OGRENCI_SIFRE", "ogrenci")
VELI_SIFRE = os.environ.get("VELI_SIFRE", "veli")

initialize_db()


# ── Yardimcilar ──────────────────────────────────────────────────────────────
def giris_zorunlu(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "ogretmen_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def ogrenci_giris_zorunlu(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("ogrenci_giris"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "sebep": "Ogrenci sifresi gerekli"}), 401
            return redirect(url_for("ogrenci_giris", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


# Tik seviye sistemi: 3-Uyari / 6-Veli / 9-Tutanak / 12-Disiplin
TIK_SEVIYELERI = [
    (12, "disiplin",  "🚨", "Disiplin Cezasi"),
    (9,  "tutanak",   "📋", "Tutanak"),
    (6,  "veli",      "📱", "Veli Bilgilendirme"),
    (3,  "uyari",     "⚠️",  "Uyari"),
    (0,  "temiz",     "✅",  None),
]

def _durum(tik: int) -> dict:
    for esik, kod, emoji, etiket in TIK_SEVIYELERI:
        if tik >= esik:
            return {"kod": kod, "emoji": emoji, "etiket": etiket,
                    "basamak": esik if esik > 0 else None}
    return {"kod": "temiz", "emoji": "✅", "etiket": None, "basamak": None}


def _ogrencilere_durum_ekle(liste: list[dict]) -> list[dict]:
    for o in liste:
        d = _durum(o["tik_sayisi"])
        o["durum"]   = d["kod"]
        o["emoji"]   = d["emoji"]
        o["etiket"]  = d["etiket"]
        o["basamak"] = d["basamak"]
    return liste


def _tum_siniflar() -> list[dict]:
    from database import _conn as _db
    con = _db()
    rows = [dict(r) for r in con.execute(
        "SELECT id, sinif_adi FROM siniflar ORDER BY sinif_adi"
    ).fetchall()]
    con.close()
    return rows


def _ogrenci_bul(ogrenci_id: int) -> dict | None:
    from database import _conn as _db
    con = _db()
    row = con.execute("""
        SELECT o.id, o.ad_soyad, o.ogr_no, o.sinif_id, s.sinif_adi,
               COUNT(t.id) AS tik_sayisi
        FROM ogrenciler o
        JOIN siniflar s ON s.id = o.sinif_id
        LEFT JOIN tik_kayitlari t ON t.ogrenci_id = o.id
        WHERE o.id = ?
        GROUP BY o.id
    """, (ogrenci_id,)).fetchone()
    con.close()
    if not row:
        return None
    return _ogrencilere_durum_ekle([dict(row)])[0]


def _ogrenci_no_ile_bul(ogr_no: int) -> dict | None:
    from database import _conn as _db
    con = _db()
    row = con.execute("""
        SELECT o.id, o.ad_soyad, o.ogr_no, o.sinif_id, s.sinif_adi,
               COUNT(t.id) AS tik_sayisi
        FROM ogrenciler o
        JOIN siniflar s ON s.id = o.sinif_id
        LEFT JOIN tik_kayitlari t ON t.ogrenci_id = o.id
        WHERE o.ogr_no = ?
        GROUP BY o.id
        ORDER BY s.sinif_adi, o.ad_soyad
        LIMIT 1
    """, (ogr_no,)).fetchone()
    con.close()
    if not row:
        return None
    return _ogrencilere_durum_ekle([dict(row)])[0]


def _ogrenci_rozetleri(ogrenci_id: int) -> list[dict]:
    from database import _conn as _db
    con = _db()
    rows = []
    for r in con.execute("""
        SELECT rozet_kodu, tarih
        FROM rozet_kayitlari
        WHERE ogrenci_id = ?
        ORDER BY tarih DESC
    """, (ogrenci_id,)).fetchall():
        d = dict(r)
        emoji, ad = ROZET_TANIMI.get(d["rozet_kodu"], ("🏅", d["rozet_kodu"]))
        d["emoji"] = emoji
        d["rozet_adi"] = ad
        rows.append(d)
    con.close()
    return rows


def _avatar(ogrenci: dict) -> dict:
    palette = ["#2563eb", "#16a34a", "#9333ea", "#dc2626", "#0891b2", "#ca8a04", "#be185d"]
    ad = ogrenci.get("ad_soyad", "?")
    initials = "".join(parca[:1] for parca in ad.split()[:2]).upper() or "?"
    renk = palette[int(ogrenci.get("id", 0)) % len(palette)]
    return {"initials": initials, "renk": renk}


def _ogrenci_ozeti(ogrenci_id: int) -> dict | None:
    ogrenci = _ogrenci_bul(ogrenci_id)
    if not ogrenci:
        return None
    sinif_id = ogrenci["sinif_id"]
    sinif_liste = _ogrencilere_durum_ekle(sinif_ogrencileri(sinif_id))
    sirali = sorted(sinif_liste, key=lambda x: (x["tik_sayisi"], x["ad_soyad"]))
    disiplin_sira = next((i + 1 for i, o in enumerate(sirali) if o["id"] == ogrenci_id), None)
    kadro = sinif_kadro_getir(sinif_id)
    return {
        "ogrenci": ogrenci,
        "avatar": _avatar(ogrenci),
        "gecmis": ogrenci_tik_gecmisi(ogrenci_id),
        "rozetler": _ogrenci_rozetleri(ogrenci_id),
        "maclar": [m for m in bugun_maclar() if m.get("sinif1_id") == sinif_id or m.get("sinif2_id") == sinif_id],
        "sinif_tablo": next((r for r in lig_puan_tablosu() if r.get("sinif_id") == sinif_id), None),
        "sezon": next((r for r in sezon_siralama() if r.get("sinif_id") == sinif_id), None),
        "kadro": kadro,
        "disiplin_sira": disiplin_sira,
        "odevler": ogrenci_odevleri(ogrenci_id),
    }


def _bildirimleri_hazirla() -> list[dict]:
    bildirimler = []
    for talep in bekleyen_ogrenci_talepleri():
        bildirimler.append({
            "tur": "Ittifak",
            "renk": "cyan",
            "baslik": f"{talep['sinif1_adi']} + {talep['sinif2_adi']}",
            "detay": "Ogrencilerden gelen bekleyen ittifak talebi",
            "hedef": url_for("oduller"),
        })
    for o in _ogrencilere_durum_ekle(tum_okul_ogrencileri()):
        if o["tik_sayisi"] >= 3:
            bildirimler.append({
                "tur": "Disiplin",
                "renk": "red",
                "baslik": f"{o['ad_soyad']} ({o['sinif_adi']})",
                "detay": f"{o['tik_sayisi']} tik ile {o['etiket'] or 'izlem'} seviyesinde",
                "hedef": url_for("dashboard"),
            })
    gorev = bugun_gorev()
    if gorev:
        bildirimler.append({
            "tur": "Gorev",
            "renk": "emerald",
            "baslik": gorev.get("gorev", "Gunluk gorev"),
            "detay": f"{gorev.get('puan', 0)} puanlik gunluk sinif gorevi",
            "hedef": url_for("oduller"),
        })
    return bildirimler[:50]


# ══════════════════════════════════════════════════════════════════════════
# Giris / Cikis
# ══════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "ogretmen_id" in session else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    ogretmenler = [o["ad_soyad"] for o in tum_ogretmenler()]
    hata, secili = None, ""

    if request.method == "POST":
        ad    = request.form.get("ad_soyad", "").strip()
        sifre = request.form.get("sifre", "").strip()
        secili = ad

        if not ad:
            hata = "Lutfen adinizi secin."
        elif not sifre:
            hata = "Sifre bos birakilamaz."
        elif not ogretmen_dogrula(ad, sifre):
            hata = "Hatali sifre! Sifreniz icin okul yonetimine basvurun."
        else:
            session["ogretmen_id"]  = ogretmen_id_bul(ad)
            session["ogretmen_adi"] = ad
            return redirect(url_for("dashboard"))

    return render_template("login.html", ogretmenler=ogretmenler, hata=hata, secili=secili)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/ogrenci/giris", methods=["GET", "POST"])
def ogrenci_giris():
    hata = None
    siniflar = _tum_siniflar()
    ogrenciler = tum_okul_ogrencileri()
    next_url = request.values.get("next") or url_for("ogrenci_gorunum")
    if not next_url.startswith("/"):
        next_url = url_for("ogrenci_gorunum")

    if session.get("ogrenci_giris"):
        return redirect(next_url)

    if request.method == "POST":
        sifre = request.form.get("sifre", "").strip()
        if sifre == OGRENCI_SIFRE:
            session["ogrenci_giris"] = True
            ogrenci_id = request.form.get("ogrenci_id", type=int)
            if ogrenci_id:
                session["ogrenci_id"] = ogrenci_id
                if next_url == url_for("ogrenci_gorunum"):
                    next_url = url_for("ogrenci_ben")
            return redirect(next_url)
        hata = "Ogrenci sifresi hatali."

    return render_template("ogrenci_login.html", hata=hata, next_url=next_url,
                           siniflar=siniflar, ogrenciler=ogrenciler)


@app.route("/ogrenci/cikis")
def ogrenci_cikis():
    session.pop("ogrenci_giris", None)
    session.pop("ogrenci_id", None)
    return redirect(url_for("ogrenci_giris"))


@app.route("/ogrenci/ben")
@ogrenci_giris_zorunlu
def ogrenci_ben():
    ogrenci_id = session.get("ogrenci_id")
    if not ogrenci_id:
        return redirect(url_for("ogrenci_giris", next=url_for("ogrenci_ben")))
    ozet = _ogrenci_ozeti(int(ogrenci_id))
    if not ozet:
        session.pop("ogrenci_id", None)
        return redirect(url_for("ogrenci_giris", next=url_for("ogrenci_ben")))
    return render_template("ogrenci_ben.html", **ozet)


@app.route("/veli/giris", methods=["GET", "POST"])
def veli_giris():
    hata = None
    if request.method == "POST":
        sifre = request.form.get("sifre", "").strip()
        ogr_no = request.form.get("ogr_no", type=int)
        if sifre != VELI_SIFRE:
            hata = "Veli sifresi hatali."
        elif not ogr_no:
            hata = "Lutfen ogrenci numarasini girin."
        else:
            ogrenci = _ogrenci_no_ile_bul(ogr_no)
            if not ogrenci:
                hata = "Bu numarayla ogrenci bulunamadi."
            else:
                session["veli_ogrenci_id"] = ogrenci["id"]
                return redirect(url_for("veli_panel"))
    return render_template("veli_login.html", hata=hata)


@app.route("/veli")
def veli_panel():
    ogrenci_id = session.get("veli_ogrenci_id")
    if not ogrenci_id:
        return redirect(url_for("veli_giris"))
    ozet = _ogrenci_ozeti(int(ogrenci_id))
    if not ozet:
        session.pop("veli_ogrenci_id", None)
        return redirect(url_for("veli_giris"))
    return render_template("veli.html", **ozet)


@app.route("/veli/cikis")
def veli_cikis():
    session.pop("veli_ogrenci_id", None)
    return redirect(url_for("veli_giris"))


@app.route("/admin/sifreler", methods=["GET", "POST"])
def admin_sifreler():
    hata, liste = None, None
    if request.method == "POST":
        if request.form.get("admin_sifre") == ADMIN_SIFRE:
            liste = tum_sifre_listesi()
        else:
            hata = "Yonetici sifresi hatali."
    return render_template("admin_sifreler.html", liste=liste, hata=hata)


# ══════════════════════════════════════════════════════════════════════════
# Ana Panel
# ══════════════════════════════════════════════════════════════════════════

@app.route("/dashboard")
@giris_zorunlu
def dashboard():
    ogretmen_id  = session["ogretmen_id"]
    ogretmen_adi = session.get("ogretmen_adi", "")
    siniflar     = ogretmen_siniflari(ogretmen_id)

    if not siniflar:
        return render_template("dashboard.html", siniflar=[], aktif=None,
                               ogrenciler=[], kriterler=KRITERLER,
                               olumlu_kriterler=OLUMLU_KRITERLER,
                               yetkili_popup=False,
                               bugunki_mufettis=None,
                               bekleyen_talepler=[],
                               tum_sinif_ogrencileri_popup=[])

    try:
        aktif_id = int(request.args.get("sinif", siniflar[0]["id"]))
    except (TypeError, ValueError):
        aktif_id = siniflar[0]["id"]

    aktif      = next((s for s in siniflar if s["id"] == aktif_id), siniflar[0])
    ogrenciler = _ogrencilere_durum_ekle(sinif_ogrencileri(aktif["id"]))

    yetkili = ogretmen_adi in MUFETTIS_YETKILILERI
    bugunki_muf = bugun_mufettis() if yetkili else None
    bek_talepler = bekleyen_ogrenci_talepleri() if yetkili else []

    popup_ogrenciler = []
    if yetkili and not bugunki_muf:
        from database import _conn as _db
        _con = _db()
        _siniflar = [dict(r) for r in _con.execute(
            "SELECT id, sinif_adi FROM siniflar ORDER BY sinif_adi"
        ).fetchall()]
        _con.close()
        for s in _siniflar:
            olist = sinif_ogrencileri(s["id"])
            for o in olist:
                popup_ogrenciler.append({
                    "id": o["id"],
                    "ad_soyad": o["ad_soyad"],
                    "sinif_adi": s["sinif_adi"],
                    "sinif_id": s["id"],
                })

    return render_template("dashboard.html",
                           siniflar=siniflar, aktif=aktif,
                           ogrenciler=ogrenciler,
                           kriterler=KRITERLER,
                           olumlu_kriterler=OLUMLU_KRITERLER,
                           yetkili_popup=yetkili,
                           bugunki_mufettis=bugunki_muf,
                           bekleyen_talepler=bek_talepler,
                           tum_sinif_ogrencileri_popup=popup_ogrenciler)


@app.route("/api/sinif/<int:sinif_id>")
@giris_zorunlu
def api_sinif(sinif_id):
    return jsonify(_ogrencilere_durum_ekle(sinif_ogrencileri(sinif_id)))


@app.route("/bildirimler")
@giris_zorunlu
def bildirimler():
    return render_template("bildirimler.html", bildirimler=_bildirimleri_hazirla())


@app.route("/rapor/ozet")
@giris_zorunlu
def rapor_ozet():
    siniflar = _tum_siniflar()
    okul = _ogrencilere_durum_ekle(tum_okul_ogrencileri())
    sinif_ozetleri = []
    toplam_tik = sum(o["tik_sayisi"] for o in okul)
    heatmap = []
    for s in siniflar:
        liste = _ogrencilere_durum_ekle(sinif_ogrencileri(s["id"]))
        sinif_tik = sum(o["tik_sayisi"] for o in liste)
        ogrenci_sayisi = len(liste)
        ortalama = round(sinif_tik / ogrenci_sayisi, 2) if ogrenci_sayisi else 0
        dagilim = {
            "temiz": sum(1 for o in liste if o["tik_sayisi"] == 0),
            "uyari": sum(1 for o in liste if 1 <= o["tik_sayisi"] <= 2),
            "veli": sum(1 for o in liste if 6 <= o["tik_sayisi"] <= 8),
            "tutanak": sum(1 for o in liste if 9 <= o["tik_sayisi"] <= 11),
            "disiplin": sum(1 for o in liste if o["tik_sayisi"] >= 12),
        }
        sinif_ozetleri.append({
            "id": s["id"],
            "sinif_adi": s["sinif_adi"],
            "ogrenci": ogrenci_sayisi,
            "tik": sinif_tik,
            "idari": sum(1 for o in liste if o["tik_sayisi"] >= 3),
            "temiz": sum(1 for o in liste if o["tik_sayisi"] == 0),
            "ortalama": ortalama,
            "dagilim": dagilim,
        })
        for o in sorted(liste, key=lambda x: (-x["tik_sayisi"], x["ad_soyad"]))[:12]:
            heatmap.append({
                "ad": o["ad_soyad"],
                "sinif": s["sinif_adi"],
                "tik": o["tik_sayisi"],
                "durum": o["durum"],
                "etiket": o["etiket"] or "Temiz",
            })
    durum_dagilimi = {
        "temiz": sum(1 for o in okul if o["tik_sayisi"] == 0),
        "uyari": sum(1 for o in okul if 1 <= o["tik_sayisi"] <= 2),
        "idari": sum(1 for o in okul if 3 <= o["tik_sayisi"] <= 5),
        "veli": sum(1 for o in okul if 6 <= o["tik_sayisi"] <= 8),
        "tutanak": sum(1 for o in okul if 9 <= o["tik_sayisi"] <= 11),
        "disiplin": sum(1 for o in okul if o["tik_sayisi"] >= 12),
    }
    return render_template(
        "rapor_ozet.html",
        sinif_ozetleri=sinif_ozetleri,
        okul=okul,
        toplam_tik=toplam_tik,
        ortalama_tik=round(toplam_tik / len(okul), 2) if okul else 0,
        durum_dagilimi=durum_dagilimi,
        heatmap=heatmap,
        tablo=lig_puan_tablosu(),
        sezon=sezon_siralama(),
        rozetler=son_rozetler(12),
    )


@app.route("/rapor/ozet.csv")
@giris_zorunlu
def rapor_ozet_csv():
    satirlar = ["sinif,ogrenci,tik,idari,temiz"]
    for s in _tum_siniflar():
        liste = _ogrencilere_durum_ekle(sinif_ogrencileri(s["id"]))
        satirlar.append(
            f"{s['sinif_adi']},{len(liste)},{sum(o['tik_sayisi'] for o in liste)},"
            f"{sum(1 for o in liste if o['tik_sayisi'] >= 3)},"
            f"{sum(1 for o in liste if o['tik_sayisi'] == 0)}"
        )
    resp = make_response("\n".join(satirlar))
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=okul-ozet-raporu.csv"
    return resp


@app.route("/turnuva")
@giris_zorunlu
def turnuva():
    tablo = lig_puan_tablosu()
    sirali = sorted(tablo, key=lambda x: (-x.get("puan", 0), -x.get("ag", 0), x.get("sinif_adi", "")))
    return render_template("turnuva.html", tablo=tablo, finalistler=sirali[:4], maclar=bugun_maclar())


@app.route("/yoklama")
@giris_zorunlu
def yoklama():
    siniflar = ogretmen_siniflari(session["ogretmen_id"])
    aktif_id = request.args.get("sinif", type=int) or (siniflar[0]["id"] if siniflar else 0)
    aktif = next((s for s in siniflar if s["id"] == aktif_id), siniflar[0] if siniflar else None)
    ogrenciler = sinif_ogrencileri(aktif["id"]) if aktif else []
    odevler = sinif_odevleri(aktif["id"]) if aktif else []
    secili_odev_id = request.args.get("odev", type=int) or (odevler[0]["id"] if odevler else 0)
    secili_odev = odev_detay(secili_odev_id) if secili_odev_id else None
    if secili_odev and aktif and secili_odev["sinif_id"] != aktif["id"]:
        secili_odev = None
    return render_template("yoklama.html", siniflar=siniflar, aktif=aktif,
                           ogrenciler=ogrenciler, odevler=odevler,
                           secili_odev=secili_odev)


@app.route("/odev/ekle", methods=["POST"])
@giris_zorunlu
def odev_olustur():
    sinif_id = request.form.get("sinif_id", type=int)
    sonuc = odev_ekle(
        sinif_id=sinif_id,
        ogretmen_id=session["ogretmen_id"],
        baslik=request.form.get("baslik", ""),
        aciklama=request.form.get("aciklama", ""),
        son_tarih=request.form.get("son_tarih", ""),
        ders=request.form.get("ders", "Genel"),
    )
    if not sonuc.get("ok"):
        return redirect(url_for("yoklama", sinif=sinif_id))
    return redirect(url_for("yoklama", sinif=sinif_id, odev=sonuc["odev_id"]))


@app.route("/odev/<int:odev_id>/tamamla/<int:ogrenci_id>", methods=["POST"])
@giris_zorunlu
def odev_tamamla_route(odev_id, ogrenci_id):
    isaretli = request.form.get("tamamlandi") == "1"
    if isaretli:
        odev_tamamla(odev_id, ogrenci_id, session["ogretmen_id"])
    else:
        odev_tamamlandi_kaldir(odev_id, ogrenci_id)
    detay = odev_detay(odev_id)
    if isaretli and detay:
        tik_ekle(ogrenci_id, session["ogretmen_id"], f"Odev Tamamladi: {detay['baslik']}")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    sinif_id = detay["sinif_id"] if detay else request.form.get("sinif_id", "")
    return redirect(url_for("yoklama", sinif=sinif_id, odev=odev_id))


@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")


@app.route("/sw.js")
def service_worker():
    resp = make_response(app.send_static_file("sw.js"))
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


# ══════════════════════════════════════════════════════════════════════════
# Tik Islemleri
# ══════════════════════════════════════════════════════════════════════════

@app.route("/tik/<int:ogrenci_id>", methods=["POST"])
@giris_zorunlu
def tik_at(ogrenci_id):
    kriter   = request.form.get("kriter", "Diger")
    sinif_id = request.form.get("sinif_id", "")
    ogr_id   = session["ogretmen_id"]

    yeni  = tik_ekle(ogrenci_id, ogr_id, kriter)
    d     = _durum(yeni)

    onceki = yeni - 1
    yeni_seviye = None
    for esik, _, _, etiket in TIK_SEVIYELERI:
        if esik > 0 and onceki < esik <= yeni:
            yeni_seviye = etiket
            break

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "tik_sayisi":  yeni,
            "durum":       d["kod"],
            "emoji":       d["emoji"],
            "etiket":      d["etiket"],
            "yeni_seviye": yeni_seviye,
        })
    return redirect(url_for("dashboard", sinif=sinif_id))


@app.route("/gecmis/<int:ogrenci_id>")
@giris_zorunlu
def gecmis(ogrenci_id):
    return jsonify(ogrenci_tik_gecmisi(ogrenci_id))


# ══════════════════════════════════════════════════════════════════════════
# Sifirlama
# ══════════════════════════════════════════════════════════════════════════

@app.route("/sifirla/ogrenci/<int:ogrenci_id>", methods=["POST"])
@giris_zorunlu
def sifirla_ogrenci(ogrenci_id):
    tek_ogrenci_sifirla(ogrenci_id)
    sinif_id = request.form.get("sinif_id", "")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    return redirect(url_for("dashboard", sinif=sinif_id))


@app.route("/sifirla/sinif/<int:sinif_id>", methods=["POST"])
@giris_zorunlu
def sifirla_sinif(sinif_id):
    if request.form.get("parola") == SIFIR_PAROLA:
        sinif_sifirla(sinif_id)
    return redirect(url_for("dashboard", sinif=sinif_id))


@app.route("/sifirla/hepsi", methods=["POST"])
@giris_zorunlu
def sifirla_hepsi():
    if request.form.get("parola") == SIFIR_PAROLA:
        tum_tikleri_sifirla()
    return redirect(url_for("dashboard"))


# ══════════════════════════════════════════════════════════════════════════
# Olumlu Davranis + Super Lig
# ══════════════════════════════════════════════════════════════════════════

@app.route("/olumlu/<int:sinif_id>", methods=["POST"])
@giris_zorunlu
def olumlu_ekle(sinif_id):
    kriter   = request.form.get("kriter", "")
    ogr_id   = session["ogretmen_id"]
    puan     = olumlu_puan_ekle(sinif_id, ogr_id, kriter)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "puan": puan})
    return redirect(url_for("dashboard", sinif=sinif_id))


@app.route("/api/lig")
@giris_zorunlu
def api_lig():
    return jsonify(lig_siralama())


@app.route("/api/lig/sifirla", methods=["POST"])
@giris_zorunlu
def api_lig_sifirla():
    if request.form.get("parola") == SIFIR_PAROLA:
        lig_manuel_sifirla()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "hata": "Yanlis parola"}), 403


@app.route("/api/olumlu/gecmis/<int:sinif_id>")
@giris_zorunlu
def api_olumlu_gecmis(sinif_id):
    return jsonify(sinif_olumlu_gecmis(sinif_id))


# ══════════════════════════════════════════════════════════════════════════
# Yayin Modu
# ══════════════════════════════════════════════════════════════════════════

@app.route("/yayin")
@app.route("/yayin/<int:sinif_id>")
@giris_zorunlu
def yayin(sinif_id=None):
    siniflar = _tum_siniflar()
    return render_template(
        "yayin.html",
        sinif_sayisi=len(siniflar),
        liderler=lig_puan_tablosu()[:5],
        rozetler=son_rozetler(8),
        sezon=sezon_siralama()[:5],
        maclar=bugun_maclar()[:6],
    )


# ══════════════════════════════════════════════════════════════════════════
# Ogrenci Goruntulemesi (sifreli, salt okunur)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/ogrenci")
@ogrenci_giris_zorunlu
def ogrenci_gorunum():
    ogrenciler = _ogrencilere_durum_ekle(tum_okul_ogrencileri())
    mufettis_veri = bugun_mufettis()
    if mufettis_veri and not mufettis_veri.get("sonuc"):
        mufettis_veri = {"sonuc": None, "gizli": True}
    return render_template(
        "ogrenci.html",
        ogrenciler   = ogrenciler,
        tablo        = lig_puan_tablosu(),
        maclar       = bugun_maclar(),
        sezon        = sezon_siralama(),
        seviyeleri   = tum_sinif_seviyeleri(),
        rozetler     = son_rozetler(20),
        seri         = tum_seri_tablosu(),
        gorev        = bugun_gorev(),
        alkislar     = son_alkislar(15),
        mufettis     = mufettis_veri,
        rozet_tanimi = ROZET_TANIMI,
    )


@app.route("/api/ogrenci/veri")
@ogrenci_giris_zorunlu
def api_ogrenci_veri():
    ogrenciler = _ogrencilere_durum_ekle(tum_okul_ogrencileri())
    muf = bugun_mufettis()
    if muf and not muf.get("sonuc"):
        muf = {"sonuc": None, "gizli": True}
    return jsonify({
        "ogrenciler": ogrenciler,
        "tablo":      lig_puan_tablosu(),
        "maclar":     bugun_maclar(),
        "gorev":      bugun_gorev(),
        "alkislar":   son_alkislar(10),
        "mufettis":   muf,
        "rozetler":   son_rozetler(10),
        "seri":       tum_seri_tablosu(),
        "sezon":      sezon_siralama(),
    })


@app.route("/api/yayin/ogrenciler")
@giris_zorunlu
def api_yayin_ogrenciler():
    ogrenciler = _ogrencilere_durum_ekle(tum_okul_ogrencileri())
    for o in ogrenciler:
        o["risk_yuzde"] = min(100, o["tik_sayisi"] * 8)
    ogrenciler.sort(key=lambda o: (-o["tik_sayisi"], o["sinif_adi"], o["ad_soyad"]))
    siniflar = {}
    for o in ogrenciler:
        s = siniflar.setdefault(o["sinif_adi"], {"sinif_adi": o["sinif_adi"], "ogrenci": 0, "tik": 0, "temiz": 0, "idari": 0})
        s["ogrenci"] += 1
        s["tik"] += o["tik_sayisi"]
        s["temiz"] += 1 if o["tik_sayisi"] == 0 else 0
        s["idari"] += 1 if o["tik_sayisi"] >= 3 else 0
    return jsonify({
        "ogrenciler": ogrenciler,
        "siniflar": sorted(siniflar.values(), key=lambda s: (-s["tik"], s["sinif_adi"])),
        "ozet": {
            "ogrenci": len(ogrenciler),
            "sinif": len(siniflar),
            "tik": sum(o["tik_sayisi"] for o in ogrenciler),
            "temiz": sum(1 for o in ogrenciler if o["tik_sayisi"] == 0),
            "uyari": sum(1 for o in ogrenciler if 1 <= o["tik_sayisi"] <= 2),
            "idari": sum(1 for o in ogrenciler if o["tik_sayisi"] >= 3),
            "veli": sum(1 for o in ogrenciler if 6 <= o["tik_sayisi"] <= 8),
            "tutanak": sum(1 for o in ogrenciler if 9 <= o["tik_sayisi"] <= 11),
            "disiplin": sum(1 for o in ogrenciler if o["tik_sayisi"] >= 12),
        }
    })


@app.route("/api/yayin/<int:sinif_id>")
@giris_zorunlu
def api_yayin_sinif(sinif_id):
    return jsonify(_ogrencilere_durum_ekle(sinif_ogrencileri(sinif_id)))


@app.route("/api/yayin/lig")
@giris_zorunlu
def api_yayin_lig():
    return jsonify(lig_siralama())


# ══════════════════════════════════════════════════════════════════════════
# Excel Raporu
# ══════════════════════════════════════════════════════════════════════════

@app.route("/rapor/excel")
@giris_zorunlu
def rapor_excel():
    if not OPENPYXL_OK:
        return "openpyxl kurulu degil", 500

    ogretmen_id  = session["ogretmen_id"]
    ogretmen_adi = session["ogretmen_adi"]
    siniflar     = ogretmen_siniflari(ogretmen_id)
    sinif_id_str = request.args.get("sinif_id")
    yalnizca_id  = int(sinif_id_str) if sinif_id_str else None

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    excel_raporu_olustur(tmp_path, ogretmen_adi, siniflar, yalnizca_id)
    tarih     = datetime.now().strftime("%Y%m%d_%H%M")
    dosya_adi = f"DisiplinRaporu_{tarih}.xlsx"

    return send_file(tmp_path, as_attachment=True, download_name=dosya_adi,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ══════════════════════════════════════════════════════════════════════════
# Super Lig Mac Sistemi
# ══════════════════════════════════════════════════════════════════════════

@app.route("/lig")
@giris_zorunlu
def lig():
    maclar = bugun_maclar()
    tablo  = lig_puan_tablosu()
    return render_template("lig.html", maclar=maclar, tablo=tablo,
                           ogretmen_adi=session["ogretmen_adi"],
                           ogretmen_id=session["ogretmen_id"],
                           var_ogretmenler=VAR_INCELEME_OGRETMENLER,
                           kart_nedenleri=KART_NEDENLERI)


@app.route("/lig/olustur", methods=["POST"])
@giris_zorunlu
def lig_olustur():
    gunluk_mac_olustur()
    return redirect(url_for("lig"))


@app.route("/api/lig/maclar")
@giris_zorunlu
def api_lig_maclar():
    return jsonify(bugun_maclar())


@app.route("/api/lig/tablo")
@giris_zorunlu
def api_lig_tablo():
    return jsonify(lig_puan_tablosu())


@app.route("/lig/mac/<int:mac_id>")
@giris_zorunlu
def lig_mac_detay(mac_id):
    mac = mac_detay(mac_id)
    if not mac:
        return redirect(url_for("lig"))
    return render_template("mac_detay.html", mac=mac,
                           ogretmen_id=session["ogretmen_id"],
                           var_ogretmenler=VAR_INCELEME_OGRETMENLER)


@app.route("/lig/mac/<int:mac_id>/sonuc", methods=["POST"])
@giris_zorunlu
def lig_mac_sonuc(mac_id):
    try:
        s1_tam  = int(request.form.get("s1_tamamlayan", 0))
        s1_top  = int(request.form.get("s1_toplam", 1))
        s2_tam  = int(request.form.get("s2_tamamlayan", 0))
        s2_top  = int(request.form.get("s2_toplam", 1))
    except (ValueError, ZeroDivisionError):
        return redirect(url_for("lig_mac_detay", mac_id=mac_id))

    sonuc = mac_sonucu_gir(mac_id, s1_tam, s1_top, s2_tam, s2_top)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(sonuc)
    return redirect(url_for("lig_mac_detay", mac_id=mac_id))


@app.route("/lig/mac/<int:mac_id>/oyla", methods=["POST"])
@giris_zorunlu
def lig_mac_oyla(mac_id):
    ogretmen_id  = session["ogretmen_id"]
    secilen_id   = int(request.form.get("sinif_id", 0))

    ogretmen_adi = session["ogretmen_adi"]
    if ogretmen_adi not in VAR_INCELEME_OGRETMENLER:
        return jsonify({"hata": "Bu islemi yapmaya yetkiniz yok"}), 403

    sonuc = mac_oy_ver(mac_id, ogretmen_id, secilen_id)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(sonuc)
    return redirect(url_for("lig_mac_detay", mac_id=mac_id))


@app.route("/lig/sifirla", methods=["POST"])
@giris_zorunlu
def lig_sifirla_mac():
    if request.form.get("parola") == SIFIR_PAROLA:
        lig_mac_tablo_sifirla()
    return redirect(url_for("lig"))


# ══════════════════════════════════════════════════════════════════════════
# Kadro Sistemi
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/kadro/<int:sinif_id>")
@giris_zorunlu
def api_kadro(sinif_id):
    kadro = sinif_kadro_getir(sinif_id)
    return jsonify(kadro)


@app.route("/api/ogrenci/kadro/<int:sinif_id>")
@ogrenci_giris_zorunlu
def api_ogrenci_kadro(sinif_id):
    return jsonify(sinif_kadro_getir(sinif_id))


@app.route("/api/ogrenci/ittifaklar")
@ogrenci_giris_zorunlu
def api_ogrenci_ittifaklar():
    return jsonify(aktif_ittifaklar())


@app.route("/api/kadro/<int:sinif_id>/yenile", methods=["POST"])
@giris_zorunlu
def api_kadro_yenile(sinif_id):
    kadro = sinif_kadro_olustur(sinif_id)
    return jsonify({"ok": True, "kadro": kadro})


@app.route("/api/sinif/<int:sinif_id>/ogrenciler")
@giris_zorunlu
def api_sinif_ogrencileri_json(sinif_id):
    return jsonify(sinif_ogrencileri(sinif_id))


@app.route("/lig/mac/<int:mac_id>/kart", methods=["POST"])
@giris_zorunlu
def lig_mac_kart(mac_id):
    try:
        ogrenci_id  = int(request.form["ogrenci_id"])
        sinif_id    = int(request.form["sinif_id"])
        kart_turu   = request.form["kart_turu"]
        neden       = request.form.get("neden", "Kural ihlali")
        ogretmen_id = session["ogretmen_id"]
        if kart_turu not in ("sari", "kirmizi"):
            return jsonify({"ok": False, "hata": "Gecersiz kart turu"}), 400
        sonuc = kart_ver(mac_id, ogrenci_id, sinif_id, ogretmen_id, kart_turu, neden)
        return jsonify({"ok": True, **sonuc})
    except Exception as e:
        return jsonify({"ok": False, "hata": str(e)}), 500


@app.route("/api/lig/mac/<int:mac_id>/kartlar")
@giris_zorunlu
def api_mac_kartlari(mac_id):
    return jsonify(mac_kartlari(mac_id))


@app.route("/api/lig/maclar_ve_tablo")
@giris_zorunlu
def api_lig_maclar_ve_tablo():
    maclar = bugun_maclar()
    tablo  = lig_puan_tablosu()

    sinif_id_seti = set()
    for m in maclar:
        sinif_id_seti.add(m["sinif1_id"])
        sinif_id_seti.add(m["sinif2_id"])

    kadrolar = {}
    for sid in sinif_id_seti:
        kadrolar[str(sid)] = sinif_kadro_getir(sid)

    return jsonify({
        "maclar": maclar,
        "tablo":  tablo,
        "kadrolar": kadrolar,
    })


# ══════════════════════════════════════════════════════════════════════════
# Gamification Rotalar
# ══════════════════════════════════════════════════════════════════════════

@app.route("/oduller")
@giris_zorunlu
def oduller():
    ogretmen_adi = session["ogretmen_adi"]
    return render_template("oduller.html",
        ogretmen_adi    = ogretmen_adi,
        ogretmen_id     = session["ogretmen_id"],
        mufettis_yetkili = ogretmen_adi in MUFETTIS_YETKILILERI,
        sezon           = sezon_siralama(),
        seviyeleri      = tum_sinif_seviyeleri(),
        rozetler        = son_rozetler(30),
        seri            = tum_seri_tablosu(),
        gorev           = bugun_gorev(),
        mufettis        = bugun_mufettis(),
        ittifaklar      = aktif_ittifaklar(),
        bekleyen_talepler = bekleyen_ogrenci_talepleri(),
        alkislar        = son_alkislar(15),
        rozet_tanimi    = ROZET_TANIMI,
        sans_secenekler = SANS_CARKI_SEENEKLERI,
    )


@app.route("/api/oduller/veri")
@giris_zorunlu
def api_oduller_veri():
    return jsonify({
        "sezon":    sezon_siralama(),
        "seviye":   tum_sinif_seviyeleri(),
        "rozetler": son_rozetler(20),
        "seri":     tum_seri_tablosu(),
        "gorev":    bugun_gorev(),
        "alkislar": son_alkislar(10),
        "ittifaklar": aktif_ittifaklar(),
    })


@app.route("/api/gorev/tamamla", methods=["POST"])
@giris_zorunlu
def api_gorev_tamamla():
    gorev_id = int(request.form["gorev_id"])
    sinif_id = int(request.form["sinif_id"])
    return jsonify(gorev_tamamla(gorev_id, sinif_id))


@app.route("/api/mufettis/degerlendir", methods=["POST"])
@giris_zorunlu
def api_mufettis_degerlendir():
    mufettis_id = int(request.form["mufettis_id"])
    sonuc       = request.form["sonuc"]
    if sonuc not in ("iyi", "kotu"):
        return jsonify({"ok": False}), 400
    return jsonify(mufettis_degerlendir(mufettis_id, sonuc))


@app.route("/api/alkis/ver", methods=["POST"])
@giris_zorunlu
def api_alkis_ver():
    ogrenci_id  = int(request.form["ogrenci_id"])
    sinif_id    = int(request.form["sinif_id"])
    mesaj       = request.form.get("mesaj", "Harika is!")
    ogretmen_id = session["ogretmen_id"]
    return jsonify(alkis_ver(ogrenci_id, sinif_id, ogretmen_id, mesaj))


@app.route("/api/ittifak/olustur", methods=["POST"])
@giris_zorunlu
def api_ittifak_olustur():
    sinif1_id = int(request.form["sinif1_id"])
    sinif2_id = int(request.form["sinif2_id"])
    return jsonify(ittifak_olustur(sinif1_id, sinif2_id))


@app.route("/api/ittifak/tamamla", methods=["POST"])
@giris_zorunlu
def api_ittifak_tamamla():
    ittifak_id = int(request.form["ittifak_id"])
    return jsonify(ittifak_tamamla(ittifak_id))


@app.route("/api/ittifak/onayla", methods=["POST"])
@giris_zorunlu
def api_ittifak_onayla():
    ittifak_id = int(request.form["ittifak_id"])
    return jsonify(ittifak_onayla(ittifak_id))


@app.route("/api/ittifak/reddet", methods=["POST"])
@giris_zorunlu
def api_ittifak_reddet():
    ittifak_id = int(request.form["ittifak_id"])
    return jsonify(ittifak_reddet(ittifak_id))


@app.route("/api/ogrenci/ittifak/talep", methods=["POST"])
@ogrenci_giris_zorunlu
def api_ogrenci_ittifak_talep():
    try:
        sinif1_id = int(request.form["sinif1_id"])
        sinif2_id = int(request.form["sinif2_id"])
        seans     = request.form.get("seans", "sabah")
    except (KeyError, ValueError):
        return jsonify({"ok": False, "sebep": "Eksik bilgi"}), 400
    if sinif1_id == sinif2_id:
        return jsonify({"ok": False, "sebep": "Ayni sinif secilemez"})
    return jsonify(ittifak_ogrenci_talebi(sinif1_id, sinif2_id, seans))


@app.route("/api/mufettis/belirle", methods=["POST"])
@giris_zorunlu
def api_mufettis_belirle():
    if session.get("ogretmen_adi") not in MUFETTIS_YETKILILERI:
        return jsonify({"ok": False, "sebep": "Yetkiniz yok"}), 403
    ogrenci_id = int(request.form["ogrenci_id"])
    return jsonify(mufettis_belirle(ogrenci_id))


@app.route("/api/sans-carki/cevir", methods=["POST"])
@giris_zorunlu
def api_sans_carki():
    mac_id   = int(request.form["mac_id"])
    sinif_id = int(request.form["sinif_id"])
    return jsonify(sans_carki_cevir(mac_id, sinif_id))


@app.route("/api/tik/dondur", methods=["POST"])
@giris_zorunlu
def api_tik_dondur():
    ogrenci_id  = int(request.form["ogrenci_id"])
    ogretmen_id = session["ogretmen_id"]
    return jsonify(tik_dondur(ogrenci_id, ogretmen_id))


# ══════════════════════════════════════════════════════════════════════════
# Quiz — Bilgi Yarisması (sifresiz)
# ══════════════════════════════════════════════════════════════════════════

QUIZ_DERSLER = {
    5: ["Türkçe", "Matematik", "Fen Bilimleri", "Sosyal Bilgiler", "İngilizce", "Din Kültürü"],
    6: ["Türkçe", "Matematik", "Fen Bilimleri", "Sosyal Bilgiler", "İngilizce", "Din Kültürü"],
    7: ["Türkçe", "Matematik", "Fen Bilimleri", "Sosyal Bilgiler", "İngilizce", "Din Kültürü"],
    8: ["Türkçe", "Matematik", "Fen Bilimleri", "T.C. İnkılap Tarihi", "İngilizce", "Din Kültürü"],
}

DERS_EMOJI = {
    "Türkçe": "📚", "Matematik": "🔢", "Fen Bilimleri": "🔬",
    "Sosyal Bilgiler": "🌍", "T.C. İnkılap Tarihi": "🏛️",
    "İngilizce": "🇬🇧", "Din Kültürü": "🕌",
}


@app.route("/quiz/<int:sinif_id>")
def quiz(sinif_id):
    quiz_sorulari_yukle()
    from database import _conn as _db_conn
    con = _db_conn()
    row = con.execute("SELECT sinif_adi FROM siniflar WHERE id=?", (sinif_id,)).fetchone()
    con.close()
    sinif_adi = row["sinif_adi"] if row else f"Sinif {sinif_id}"
    bugun_yapilan = quiz_gunluk_dersleri(sinif_id)
    istatistik = quiz_sinif_istatistik(sinif_id)
    return render_template("quiz.html",
        sinif_id=sinif_id, sinif_adi=sinif_adi,
        quiz_dersler=QUIZ_DERSLER,
        ders_emoji=DERS_EMOJI,
        bugun_yapilan=bugun_yapilan,
        istatistik=istatistik,
    )


@app.route("/api/quiz/sorular")
def api_quiz_sorular():
    sinif_seviyesi = request.args.get("sinif_seviyesi", type=int)
    ders = request.args.get("ders", "")
    if not sinif_seviyesi or not ders:
        return jsonify({"ok": False, "sebep": "Eksik parametre"}), 400
    sorular = quiz_sorular_getir(sinif_seviyesi, ders)
    for s in sorular:
        s.pop("dogru_cevap", None)
    return jsonify({"ok": True, "sorular": sorular})


@app.route("/api/quiz/cevapla", methods=["POST"])
def api_quiz_cevapla():
    veri = request.json or {}
    sinif_id = veri.get("sinif_id")
    sinif_seviyesi = veri.get("sinif_seviyesi")
    ders = veri.get("ders")
    cevaplar = veri.get("cevaplar", {})
    if not (sinif_id and sinif_seviyesi and ders and cevaplar):
        return jsonify({"ok": False, "sebep": "Eksik veri"}), 400
    from database import _conn as _dbc
    from database import _quiz_init as _qi
    con = _dbc()
    _qi(con)
    dogru = yanlis = 0
    sonuclar = {}
    for soru_id_str, verilen in cevaplar.items():
        row = con.execute("SELECT dogru_cevap FROM quiz_sorulari WHERE id=?",
                          (int(soru_id_str),)).fetchone()
        if row:
            gercek = row["dogru_cevap"]
            ok = verilen.upper() == gercek.upper()
            sonuclar[soru_id_str] = {"dogru": ok, "gercek": gercek}
            if ok: dogru += 1
            else:  yanlis += 1
    con.close()
    sonuc = quiz_sonuc_kaydet(sinif_id, ders, sinif_seviyesi, dogru, yanlis)
    sonuc["dogru"] = dogru
    sonuc["yanlis"] = yanlis
    sonuc["sonuclar"] = sonuclar
    return jsonify(sonuc)


@app.route("/api/quiz/istatistik/<int:sinif_id>")
def api_quiz_istatistik(sinif_id):
    return jsonify(quiz_sinif_istatistik(sinif_id))


@app.route("/taktik/<int:sinif_id>")
def taktik(sinif_id):
    kayit = taktik_yukle(sinif_id)
    from database import _conn, _kadro_tablosu_olustur
    con = _conn()
    sinif_row = con.execute("SELECT sinif_adi FROM siniflar WHERE id=?",
                            (sinif_id,)).fetchone()
    sinif_adi = sinif_row["sinif_adi"] if sinif_row else f"Sinif {sinif_id}"

    try:
        _kadro_tablosu_olustur(con)
        kadro = [dict(r) for r in con.execute("""
            SELECT o.id, o.ad_soyad, o.ogr_no,
                   COALESCE(k.mevki_no, 1) AS mevki_no
            FROM ogrenciler o
            LEFT JOIN kadro_ogrenci k
                   ON k.ogrenci_id = o.id AND k.sinif_id = ?
            WHERE o.sinif_id = ?
            ORDER BY o.ad_soyad
        """, (sinif_id, sinif_id)).fetchall()]
    except Exception:
        kadro = [dict(r) for r in con.execute(
            "SELECT id, ad_soyad, ogr_no FROM ogrenciler WHERE sinif_id=? ORDER BY ad_soyad",
            (sinif_id,)
        ).fetchall()]

    con.close()

    mevki_map = {m[0]: m[2] for m in MEVKILER}
    for o in kadro:
        o["mevki"] = mevki_map.get(o.get("mevki_no", 1), "Santrafor (Golcu)")

    mevkiler_json = [{"no": m[0], "emoji": m[1], "ad": m[2]} for m in MEVKILER]

    return render_template("taktik.html",
        sinif_id     = sinif_id,
        sinif_adi    = sinif_adi,
        kadro        = kadro,
        kayit        = kayit,
        mevkiler_json = mevkiler_json,
    )


@app.route("/api/taktik/<int:sinif_id>")
def api_taktik_yukle(sinif_id):
    return jsonify(taktik_yukle(sinif_id))


@app.route("/api/taktik/<int:sinif_id>/kaydet", methods=["POST"])
def api_taktik_kaydet(sinif_id):
    import json as _json
    veri_str = request.get_data(as_text=True)
    sonuc = taktik_kaydet(sinif_id, veri_str)
    if sonuc.get("ok"):
        try:
            veri = _json.loads(veri_str)
            taktik_kadro_guncelle(sinif_id, veri.get("oyuncular", {}))
        except Exception:
            pass
    return jsonify(sonuc)


# ══════════════════════════════════════════════════════════════════════════
# Veri Sifirlama — Admin
# ══════════════════════════════════════════════════════════════════════════

SIFIRLAMA_SIFRESI = "ERENLER2024"

@app.route("/admin/sifirla", methods=["GET"])
@giris_zorunlu
def admin_sifirla_sayfa():
    return render_template("sifirla.html",
        ogretmen_adi=session.get("ogretmen_adi",""))

@app.route("/api/admin/sifirla", methods=["POST"])
@giris_zorunlu
def api_admin_sifirla():
    veri = request.json or {}
    girilen = veri.get("sifre", "").strip()
    if girilen != SIFIRLAMA_SIFRESI:
        return jsonify({"ok": False, "sebep": "Sifre yanlis!"}), 403
    sonuc = tum_verileri_sifirla()
    return jsonify(sonuc)


# ══════════════════════════════════════════════════════════════════════════
# Baslama
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import socket
    port = int(os.environ.get("PORT", 5000))
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
    except Exception:
        ip = "127.0.0.1"

    print(f"\n  http://localhost:{port}  |  http://{ip}:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
