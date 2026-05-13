"""
web_app.py
----------
Flask tabanlı web uygulaması.
Tüm telefon / PC / akıllı tahta aynı anda senkron kullanır.

Kurulum : pip install flask openpyxl
Başlatma: python web_app.py
Erişim  : http://SUNUCU_IP:5000  (okul Wi-Fi'ından)
"""

import os, tempfile, json
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, send_file, abort,
)
from database import (
    initialize_db, KRITERLER,
    tum_ogretmenler, tum_sifre_listesi,
    ogretmen_dogrula, ogretmen_id_bul, ogretmen_siniflari,
    sinif_ogrencileri, ogrenci_tik_gecmisi,
    tik_ekle, tek_ogrenci_sifirla, sinif_sifirla, tum_tikleri_sifirla,
)
from export import excel_raporu_olustur, OPENPYXL_OK
from web_features import ogrenci_rozetleri_ekle, register_feature_routes

# ── Uygulama ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "erenler-cumhuriyet-ortaokulu-2025-gizli"

SIFIR_PAROLA = "1234"
ADMIN_SIFRE  = "ECadmin"

initialize_db()


# ── Yardımcı ────────────────────────────────────────────────────────────────
def giris_zorunlu(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "ogretmen_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def _durum(tik: int):
    if tik == 0:   return "temiz",   "✅"
    elif tik <= 2: return "uyari",   "⚠️"
    else:          return "tehlike", "🚨"


# ══════════════════════════════════════════════════════════════════════════
# Giriş / Çıkış
# ══════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "ogretmen_id" in session
                    else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    ogretmenler = [o["ad_soyad"] for o in tum_ogretmenler()]
    hata = None
    secili = ""

    if request.method == "POST":
        ad    = request.form.get("ad_soyad", "").strip()
        sifre = request.form.get("sifre", "").strip()
        secili = ad

        if not ad:
            hata = "Lütfen adınızı seçin."
        elif not sifre:
            hata = "Şifre boş bırakılamaz."
        elif not ogretmen_dogrula(ad, sifre):
            hata = "Hatalı şifre! Şifreniz için okul yönetimine başvurun."
        else:
            session["ogretmen_id"]  = ogretmen_id_bul(ad)
            session["ogretmen_adi"] = ad
            return redirect(url_for("dashboard"))

    return render_template("login.html",
                           ogretmenler=ogretmenler,
                           hata=hata, secili=secili)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Yönetici: şifre listesi ───────────────────────────────────────────────
@app.route("/admin/sifreler", methods=["GET", "POST"])
def admin_sifreler():
    hata = None
    liste = None
    if request.method == "POST":
        if request.form.get("admin_sifre") == ADMIN_SIFRE:
            liste = tum_sifre_listesi()
        else:
            hata = "Yönetici şifresi hatalı."
    return render_template("admin_sifreler.html", liste=liste, hata=hata)


# ══════════════════════════════════════════════════════════════════════════
# Ana Panel
# ══════════════════════════════════════════════════════════════════════════

@app.route("/dashboard")
@giris_zorunlu
def dashboard():
    ogretmen_id = session["ogretmen_id"]
    siniflar    = ogretmen_siniflari(ogretmen_id)

    if not siniflar:
        return render_template("dashboard.html",
                               siniflar=[], aktif=None, ogrenciler=[],
                               kriterler=KRITERLER)

    try:
        aktif_id = int(request.args.get("sinif", siniflar[0]["id"]))
    except (TypeError, ValueError):
        aktif_id = siniflar[0]["id"]

    aktif = next((s for s in siniflar if s["id"] == aktif_id), siniflar[0])
    ogrenciler = sinif_ogrencileri(aktif["id"])

    # Durumu ve emojiyi ekle
    for o in ogrenciler:
        durum, emoji = _durum(o["tik_sayisi"])
        o["durum"]  = durum
        o["emoji"]  = emoji
    ogrenci_rozetleri_ekle(ogrenciler)

    return render_template("dashboard.html",
                           siniflar=siniflar,
                           aktif=aktif,
                           ogrenciler=ogrenciler,
                           kriterler=KRITERLER)


# ── Canlı güncelleme: öğrenci listesi JSON ────────────────────────────────
@app.route("/api/sinif/<int:sinif_id>")
@giris_zorunlu
def api_sinif(sinif_id):
    ogrenciler = sinif_ogrencileri(sinif_id)
    for o in ogrenciler:
        durum, emoji = _durum(o["tik_sayisi"])
        o["durum"] = durum
        o["emoji"] = emoji
    ogrenci_rozetleri_ekle(ogrenciler)
    return jsonify(ogrenciler)


# ══════════════════════════════════════════════════════════════════════════
# Tik İşlemleri
# ══════════════════════════════════════════════════════════════════════════

@app.route("/tik/<int:ogrenci_id>", methods=["POST"])
@giris_zorunlu
def tik_at(ogrenci_id):
    kriter    = request.form.get("kriter", "❓ Diğer")
    sinif_id  = request.form.get("sinif_id", "")
    ogr_id    = session["ogretmen_id"]

    yeni = tik_ekle(ogrenci_id, ogr_id, kriter)

    # AJAX isteği mi yoksa form gönderimi mi?
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        durum, emoji = _durum(yeni)
        return jsonify({"tik_sayisi": yeni, "durum": durum, "emoji": emoji,
                        "uyari": yeni >= 3})
    return redirect(url_for("dashboard", sinif=sinif_id))


@app.route("/gecmis/<int:ogrenci_id>")
@giris_zorunlu
def gecmis(ogrenci_id):
    return jsonify(ogrenci_tik_gecmisi(ogrenci_id))


# ══════════════════════════════════════════════════════════════════════════
# Sıfırlama
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
# Yayın Modu
# ══════════════════════════════════════════════════════════════════════════

@app.route("/yayin/<int:sinif_id>")
@giris_zorunlu
def yayin(sinif_id):
    siniflar = ogretmen_siniflari(session["ogretmen_id"])
    aktif    = next((s for s in siniflar if s["id"] == sinif_id), None)
    if not aktif:
        return redirect(url_for("dashboard"))
    return render_template("yayin.html", sinif_id=sinif_id,
                           sinif_adi=aktif["sinif_adi"])


@app.route("/api/yayin/<int:sinif_id>")
@giris_zorunlu
def api_yayin(sinif_id):
    ogrenciler = sinif_ogrencileri(sinif_id)
    ogrenciler.sort(key=lambda o: (-o["tik_sayisi"], o["ad_soyad"]))
    for o in ogrenciler:
        _, emoji = _durum(o["tik_sayisi"])
        o["emoji"] = emoji
    ogrenci_rozetleri_ekle(ogrenciler)
    return jsonify(ogrenciler)


# ══════════════════════════════════════════════════════════════════════════
# Excel Raporu
# ══════════════════════════════════════════════════════════════════════════

@app.route("/rapor/excel")
@giris_zorunlu
def rapor_excel():
    if not OPENPYXL_OK:
        return "openpyxl kurulu değil. pip install openpyxl", 500

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

    return send_file(
        tmp_path, as_attachment=True,
        download_name=dosya_adi,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ══════════════════════════════════════════════════════════════════════════
# Başlatma
# ══════════════════════════════════════════════════════════════════════════

register_feature_routes(app, giris_zorunlu, SIFIR_PAROLA, ADMIN_SIFRE)


if __name__ == "__main__":
    import socket

    # Bulut ortamında PORT env var kullanılır (Render, Railway, vb.)
    port = int(os.environ.get("PORT", 5000))

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"

    print("\n" + "="*55)
    print("  Erenler Cumhuriyet Ortaokulu - Web Uygulamasi")
    print("="*55)
    print(f"  Yerel erisim : http://localhost:{port}")
    print(f"  Ag erisimi   : http://{ip}:{port}")
    print("="*55 + "\n")

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
