"""Metehan Cücen'e özel sayfa bazlı veri sıfırlama: önce yedek, sonra kapsamlı silme."""
from __future__ import annotations

import json
from datetime import datetime

from flask import abort, g, jsonify, request, session

import database as db

YETKILI_AD_SOYAD = "METEHAN CÜCEN"
ONAY_METNI = "SIFIRLA"

# tablo, sınıf filtresi, hafta sütunu. Filtre: "sinif" → sinif_id sütunu,
# "ogrenci" → ogrenci_id üzerinden, ("ebeveyn", fk, tablo, filtre) → üst kayıt üzerinden.
# Alt tablolar üst tablodan önce yazılır; silme bu sırayla yapılır.
SAYFALAR = {
    "dashboard": {
        "ad": "Ana sayfa · veliye giden notlar",
        "tablolar": [("ogretmen_notlari", "ogrenci", None)],
    },
    "haftalik_takip": {
        "ad": "Kitap ve ödev takibi",
        "tablolar": [
            ("haftalik_takip", "sinif", "hafta_basi"),
            ("haftalik_odev_bilgi", "sinif", "hafta_basi"),
        ],
    },
    "sonuclar": {
        "ad": "Ders / deneme sonuçları",
        "tablolar": [
            ("lgs_deneme_ders", ("ebeveyn", "deneme_id", "lgs_deneme", "ogrenci"), None),
            ("lgs_deneme", "ogrenci", None),
        ],
    },
    "lgs": {
        "ad": "LGS takibi",
        "tablolar": [
            ("lgs_gorev", "ogrenci", "hafta_basi"),
            ("lgs_gunluk", "ogrenci", None),
            ("lgs_defter_hucre", "ogrenci", "hafta_basi"),
            ("lgs_defter_ruh", "ogrenci", "hafta_basi"),
            ("lgs_defter", "ogrenci", "hafta_basi"),
            ("lgs_program_isaret", "ogrenci", None),
            ("lgs_program_isaret_arsiv", "ogrenci", None),
            ("lgs_program_ozel", "ogrenci", None),
            ("lgs_ay", "ogrenci", None),
            ("lgs_profil", "ogrenci", None),
        ],
    },
    "ogretmen_kitap_okuma": {
        "ad": "Okuma kayıtları",
        "tablolar": [("kitap_okuma_kayitlari", "sinif", None)],
    },
    "ogretmen_randevular": {
        "ad": "Veli görüşme talepleri",
        "tablolar": [("randevu_talebi", "sinif", None)],
    },
}


def yetkili_mi() -> bool:
    oid = session.get("ogretmen_id")
    if not oid or session.get("ogretmen_yetki") in ("rapor", "rehber"):
        return False
    beklenen = db.ogretmen_id_bul(YETKILI_AD_SOYAD)
    return beklenen is not None and int(beklenen) == int(oid)


def _init(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS sayfa_sifirlama_yedekleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            olusturma TEXT NOT NULL,
            ogretmen_id INTEGER NOT NULL,
            sayfa TEXT NOT NULL,
            kapsam TEXT NOT NULL,
            sinif_id INTEGER,
            hafta_basi TEXT,
            kayit_sayisi INTEGER NOT NULL,
            json_yedek TEXT NOT NULL,
            geri_yuklendi TEXT
        )
    """)
    con.commit()


def _filtre(filtre, sinif_id):
    if filtre == "sinif":
        return "sinif_id = ?", [sinif_id]
    if filtre == "ogrenci":
        return "ogrenci_id IN (SELECT id FROM ogrenciler WHERE sinif_id = ?)", [sinif_id]
    _, fk, ust_tablo, ust_filtre = filtre
    kosul, params = _filtre(ust_filtre, sinif_id)
    return f'"{fk}" IN (SELECT id FROM "{ust_tablo}" WHERE {kosul})', params


def _where(con, tablo, filtre, hafta_sutun, sinif_id, hafta_basi):
    sutunlar = {r[1] for r in con.execute(f'PRAGMA table_info("{tablo}")')}
    if not sutunlar:
        return None
    kosullar, params = [], []
    if sinif_id is not None:
        kosul, p = _filtre(filtre, sinif_id)
        kosullar.append(kosul)
        params += p
    if hafta_basi and hafta_sutun in sutunlar:
        kosullar.append(f'"{hafta_sutun}" = ?')
        params.append(hafta_basi)
    return (" WHERE " + " AND ".join(kosullar)) if kosullar else "", params


def _hedefler(con, sayfa, sinif_id, hafta_basi):
    for tablo, filtre, hafta_sutun in SAYFALAR[sayfa]["tablolar"]:
        w = _where(con, tablo, filtre, hafta_sutun, sinif_id, hafta_basi)
        if w is not None:
            yield tablo, w[0], w[1]


def _kapsam_oku(veri):
    sayfa = str(veri.get("sayfa") or "")
    if sayfa not in SAYFALAR:
        abort(400)
    kapsam = veri.get("kapsam")
    if kapsam not in ("sinif", "okul"):
        abort(400)
    sinif_id = None
    if kapsam == "sinif":
        try:
            sinif_id = int(veri.get("sinif_id"))
        except (TypeError, ValueError):
            abort(400)
    hafta_basi = str(veri.get("hafta_basi") or "").strip()[:10] or None
    if hafta_basi and not any(t[2] for t in SAYFALAR[sayfa]["tablolar"]):
        hafta_basi = None
    return sayfa, kapsam, sinif_id, hafta_basi


def onizle(sayfa, sinif_id, hafta_basi):
    con = db._conn()
    try:
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"{w}', p).fetchone()[0]
                for t, w, p in _hedefler(con, sayfa, sinif_id, hafta_basi)}
    finally:
        con.close()


def sifirla(sayfa, kapsam, sinif_id, hafta_basi, ogretmen_id):
    con = db._conn()
    try:
        _init(con)
        con.execute("BEGIN IMMEDIATE")
        yedek, toplam = {}, 0
        hedefler = list(_hedefler(con, sayfa, sinif_id, hafta_basi))
        for tablo, w, p in hedefler:
            satirlar = [dict(r) for r in con.execute(f'SELECT * FROM "{tablo}"{w}', p)]
            yedek[tablo] = satirlar
            toplam += len(satirlar)
        cur = con.execute(
            "INSERT INTO sayfa_sifirlama_yedekleri (olusturma, ogretmen_id, sayfa, kapsam, sinif_id, hafta_basi, kayit_sayisi, json_yedek) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), ogretmen_id, sayfa, kapsam, sinif_id, hafta_basi,
             toplam, json.dumps(yedek, ensure_ascii=False)),
        )
        for tablo, w, p in hedefler:
            con.execute(f'DELETE FROM "{tablo}"{w}', p)
        con.commit()
        return {"yedek_id": cur.lastrowid, "silinen": {t: len(r) for t, r in yedek.items()}, "toplam": toplam}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def yedekler(sayfa):
    con = db._conn()
    try:
        _init(con)
        return [dict(r) for r in con.execute(
            "SELECT y.id, y.olusturma, y.kapsam, y.hafta_basi, y.kayit_sayisi, y.geri_yuklendi, s.sinif_adi "
            "FROM sayfa_sifirlama_yedekleri y LEFT JOIN siniflar s ON s.id = y.sinif_id "
            "WHERE y.sayfa = ? ORDER BY y.id DESC LIMIT 10", (sayfa,))]
    finally:
        con.close()


def geri_yukle(yedek_id):
    con = db._conn()
    try:
        _init(con)
        con.execute("BEGIN IMMEDIATE")
        kayit = con.execute("SELECT * FROM sayfa_sifirlama_yedekleri WHERE id = ?", (yedek_id,)).fetchone()
        if not kayit:
            raise LookupError("Yedek bulunamadı.")
        if kayit["geri_yuklendi"]:
            raise ValueError("Bu yedek zaten geri yüklendi.")
        veri = json.loads(kayit["json_yedek"])
        izinli = {t[0] for t in SAYFALAR.get(kayit["sayfa"], {}).get("tablolar", [])}
        eklenen = 0
        # Üst tablolar önce eklenir (silme sırasının tersi).
        for tablo in reversed(list(veri)):
            if tablo not in izinli:
                continue
            sutunlar = {r[1] for r in con.execute(f'PRAGMA table_info("{tablo}")')}
            for satir in veri[tablo]:
                alanlar = [k for k in satir if k in sutunlar]
                if not alanlar:
                    continue
                cur = con.execute(
                    f'INSERT OR IGNORE INTO "{tablo}" ({",".join(chr(34) + a + chr(34) for a in alanlar)}) '
                    f'VALUES ({",".join("?" for _ in alanlar)})',
                    [satir[a] for a in alanlar],
                )
                eklenen += cur.rowcount
        con.execute("UPDATE sayfa_sifirlama_yedekleri SET geri_yuklendi = ? WHERE id = ?",
                    (datetime.now().isoformat(timespec="seconds"), yedek_id))
        con.commit()
        return eklenen
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def register_sayfa_sifirlama(app, login_required):
    con = db._conn()
    _init(con)
    con.close()

    @app.context_processor
    def _sayfa_sifirlama_context():
        if not yetkili_mi() or request.endpoint not in SAYFALAR:
            return {"sayfa_sifirlama": None}
        sayfa = SAYFALAR[request.endpoint]
        hafta = session.get("ui_takip_hafta") if any(t[2] for t in sayfa["tablolar"]) and request.endpoint == "haftalik_takip" else None
        return {"sayfa_sifirlama": {"sayfa": request.endpoint, "ad": sayfa["ad"], "hafta_basi": hafta or ""}}

    def _json_istek():
        if not yetkili_mi():
            abort(403)
        if not request.is_json:
            abort(415)
        return request.get_json(silent=True) or {}

    @app.post("/api/sayfa-sifirla/onizle")
    @login_required
    def api_sayfa_sifirla_onizle():
        sayfa, kapsam, sinif_id, hafta_basi = _kapsam_oku(_json_istek())
        sayilar = onizle(sayfa, sinif_id, hafta_basi)
        return jsonify(ok=True, sayilar=sayilar, toplam=sum(sayilar.values()), yedekler=yedekler(sayfa))

    @app.post("/api/sayfa-sifirla")
    @login_required
    def api_sayfa_sifirla():
        veri = _json_istek()
        sayfa, kapsam, sinif_id, hafta_basi = _kapsam_oku(veri)
        if str(veri.get("onay") or "").strip() != ONAY_METNI:
            return jsonify(ok=False, hata=f'Onay için "{ONAY_METNI}" yazın.'), 400
        g.history_disabled = True
        sonuc = sifirla(sayfa, kapsam, sinif_id, hafta_basi, session["ogretmen_id"])
        return jsonify(ok=True, **sonuc)

    @app.post("/api/sayfa-sifirla/geri-yukle/<int:yedek_id>")
    @login_required
    def api_sayfa_sifirla_geri_yukle(yedek_id):
        _json_istek()
        g.history_disabled = True
        try:
            eklenen = geri_yukle(yedek_id)
        except (LookupError, ValueError) as hata:
            return jsonify(ok=False, hata=str(hata)), 400
        return jsonify(ok=True, eklenen=eklenen)
