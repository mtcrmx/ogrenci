"""Ortak sınav/test giriş ekranı (/giris), Excel yapıştırma ayrıştırıcısı ve taslak API'si."""
from __future__ import annotations

from datetime import date, datetime
import json
import unicodedata
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
import database as db
import lgs_optik
from moduller import aktif_moduller, seviye as sinif_seviye_bul
from student_results import school_courses, sinif_ders_toplu_kaydet, answer_letters

bp = Blueprint("hizli_giris", __name__)


def _norm(text: str) -> str:
    text = str(text or "").replace("ı", "i").replace("İ", "I").casefold()
    return " ".join(
        "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).split()
    )


def excel_yapistir_coz(metin: str, ogrenciler: list[dict]) -> dict:
    """
    Excel'den kopyalanan (sekmeyle veya noktalı virgülle ayrılmış) metni ayrıştırır.
    Desteklenen sütun düzenleri:
      - ogr_no  dogru  yanlis
      - ad_soyad  dogru  yanlis
      - ogr_no  ad_soyad  dogru  yanlis
      - ogr_no  K (katılmadı)
    Döner:
      {
        "eslesen": [{"ogrenci_id": int, "ogr_no": str, "ad_soyad": str, "dogru": int|None, "yanlis": int|None, "katilmadi": bool}],
        "eslesmeyen": [{"satir": int, "ham": str, "neden": str}]
      }
    """
    no_harita = {}
    ad_harita = {}
    for o in ogrenciler or []:
        oid = int(o["id"])
        ogr_no = str(o.get("ogr_no") or "").strip()
        if ogr_no:
            no_harita[ogr_no] = o
        ad = _norm(o.get("ad_soyad") or "")
        if ad:
            ad_harita[ad] = o

    eslesen = []
    eslesmeyen = []
    for idx, raw_line in enumerate((metin or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if "\t" in line:
            parcalar = [p.strip() for p in line.split("\t") if p.strip() != ""]
        elif ";" in line:
            parcalar = [p.strip() for p in line.split(";") if p.strip() != ""]
        else:
            parcalar = [p.strip() for p in line.split(",") if p.strip() != ""]
            if len(parcalar) < 2:
                parcalar = line.split()

        if len(parcalar) < 2:
            eslesmeyen.append({"satir": idx, "ham": raw_line, "neden": "Yetersiz sütun"})
            continue

        # Başlık satırı kontrolü
        ilk_norm = _norm(parcalar[0])
        if ilk_norm in ("no", "ogrenci no", "numara", "ad soyad", "ogrenci"):
            continue

        ogrenci = no_harita.get(parcalar[0]) or ad_harita.get(ilk_norm)
        if not ogrenci and len(parcalar) >= 3:
            ogrenci = ad_harita.get(_norm(parcalar[1]))
            kalan = parcalar[2:]
        else:
            kalan = parcalar[1:]
            # Eğer 2. sütun da isimse ve 4 sütun varsa (No | Ad | D | Y)
            if ogrenci and len(kalan) >= 3 and not kalan[0].lstrip("-").isdigit() and kalan[0].upper() not in ("K", "KATILMADI"):
                kalan = kalan[1:]

        if not ogrenci:
            eslesmeyen.append({"satir": idx, "ham": raw_line, "neden": "Öğrenci bulunamadı"})
            continue

        if not kalan:
            eslesmeyen.append({"satir": idx, "ham": raw_line, "neden": "Doğru/yanlış değeri yok"})
            continue

        if kalan[0].upper() in ("K", "KATILMADI", "-"):
            eslesen.append({
                "ogrenci_id": int(ogrenci["id"]),
                "ogr_no": str(ogrenci.get("ogr_no") or ""),
                "ad_soyad": ogrenci.get("ad_soyad") or "",
                "dogru": None,
                "yanlis": None,
                "katilmadi": True,
            })
            continue

        try:
            dogru = int(kalan[0])
            yanlis = int(kalan[1]) if len(kalan) >= 2 else 0
        except ValueError:
            eslesmeyen.append({"satir": idx, "ham": raw_line, "neden": "Doğru/yanlış sayı değil"})
            continue

        eslesen.append({
            "ogrenci_id": int(ogrenci["id"]),
            "ogr_no": str(ogrenci.get("ogr_no") or ""),
            "ad_soyad": ogrenci.get("ad_soyad") or "",
            "dogru": dogru,
            "yanlis": yanlis,
            "katilmadi": False,
        })

    return {"eslesen": eslesen, "eslesmeyen": eslesmeyen}


def _ensure_tables(con) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS giris_taslak (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogretmen_id INTEGER NOT NULL,
            anahtar TEXT NOT NULL DEFAULT 'varsayilan',
            veri TEXT NOT NULL DEFAULT '{}',
            guncelleme TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ogretmen_id, anahtar)
        );
        CREATE TABLE IF NOT EXISTS ogretmen_giris_tercih (
            ogretmen_id INTEGER PRIMARY KEY,
            sinif_id INTEGER,
            ders TEXT DEFAULT '',
            tarih TEXT DEFAULT '',
            soru_sayisi INTEGER DEFAULT 20,
            yanlis_goturme INTEGER DEFAULT 3,
            tur TEXT DEFAULT 'okul_yaprak',
            guncelleme TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    t_cols = {r[1] for r in con.execute("PRAGMA table_info(giris_taslak)").fetchall()}
    if "anahtar" not in t_cols:
        con.execute("DROP TABLE IF EXISTS giris_taslak")
        con.execute(
            """CREATE TABLE giris_taslak (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogretmen_id INTEGER NOT NULL,
                anahtar TEXT NOT NULL DEFAULT 'varsayilan',
                veri TEXT NOT NULL DEFAULT '{}',
                guncelleme TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ogretmen_id, anahtar)
            )"""
        )
    p_cols = {r[1] for r in con.execute("PRAGMA table_info(ogretmen_giris_tercih)").fetchall()}
    if "soru_sayisi" not in p_cols:
        con.execute("ALTER TABLE ogretmen_giris_tercih ADD COLUMN soru_sayisi INTEGER DEFAULT 20")


def tercih_getir(ogretmen_id: int) -> dict:
    con = db._conn()
    try:
        _ensure_tables(con)
        row = con.execute(
            "SELECT sinif_id, ders, tur, soru_sayisi, yanlis_goturme FROM ogretmen_giris_tercih WHERE ogretmen_id = ?",
            (int(ogretmen_id),),
        ).fetchone()
        return dict(row) if row else {}
    except Exception:
        return {}
    finally:
        con.close()


def tercih_kaydet(
    ogretmen_id: int,
    sinif_id: int | None = None,
    ders: str | None = None,
    tur: str | None = None,
    soru_sayisi: int | None = None,
    yanlis_goturme: int | None = None,
) -> None:
    if not ogretmen_id:
        return
    mevcut = tercih_getir(ogretmen_id)
    yeni_sinif = sinif_id if sinif_id is not None else mevcut.get("sinif_id")
    yeni_ders = ders if ders is not None else (mevcut.get("ders") or "Matematik")
    yeni_tur = tur if tur is not None else (mevcut.get("tur") or "okul_yaprak")
    yeni_soru = soru_sayisi if soru_sayisi is not None else (mevcut.get("soru_sayisi") or 20)
    yeni_goturme = yanlis_goturme if yanlis_goturme is not None else (mevcut.get("yanlis_goturme") if mevcut.get("yanlis_goturme") is not None else 3)
    con = db._conn()
    try:
        _ensure_tables(con)
        con.execute(
            """INSERT INTO ogretmen_giris_tercih
               (ogretmen_id, sinif_id, ders, tur, soru_sayisi, yanlis_goturme, guncelleme)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ogretmen_id) DO UPDATE SET
                 sinif_id=excluded.sinif_id,
                 ders=excluded.ders,
                 tur=excluded.tur,
                 soru_sayisi=excluded.soru_sayisi,
                 yanlis_goturme=excluded.yanlis_goturme,
                 guncelleme=excluded.guncelleme""",
            (
                int(ogretmen_id),
                yeni_sinif,
                yeni_ders,
                yeni_tur,
                int(yeni_soru),
                int(yeni_goturme),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        con.commit()
    finally:
        con.close()


def taslak_kaydet(ogretmen_id: int, anahtar: str, veri: dict) -> str:
    simdi = datetime.now().isoformat(timespec="seconds")
    con = db._conn()
    try:
        _ensure_tables(con)
        con.execute(
            """INSERT INTO giris_taslak (ogretmen_id, anahtar, veri, guncelleme)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(ogretmen_id, anahtar) DO UPDATE SET
                 veri=excluded.veri,
                 guncelleme=excluded.guncelleme""",
            (int(ogretmen_id), str(anahtar)[:120], json.dumps(veri, ensure_ascii=False), simdi),
        )
        con.commit()
    finally:
        con.close()
    return simdi


def taslak_getir(ogretmen_id: int, anahtar: str) -> dict | None:
    con = db._conn()
    try:
        _ensure_tables(con)
        row = con.execute(
            "SELECT veri, guncelleme FROM giris_taslak WHERE ogretmen_id = ? AND anahtar = ?",
            (int(ogretmen_id), str(anahtar)[:120]),
        ).fetchone()
        if not row:
            return None
        return {"veri": json.loads(row["veri"] or "{}"), "guncelleme": row["guncelleme"]}
    finally:
        con.close()


def register_hizli_giris(app, login_required):
    @app.route("/giris", methods=["GET", "POST"])
    @login_required
    def ort_giris():
        oid = session.get("ogretmen_id")
        siniflar = db.ogretmen_siniflari(oid) or db.aktif_sube_siniflari()
        if not siniflar:
            siniflar = db.tum_siniflar()
        tercih = tercih_getir(oid)

        secili_sinif_id = (
            request.values.get("sinif_id", type=int)
            or request.values.get("sinif", type=int)
            or session.get("ui_sinif_id")
            or tercih.get("sinif_id")
            or (siniflar[0]["id"] if siniflar else None)
        )
        sinif_map = {int(s["id"]): s for s in siniflar}
        if secili_sinif_id not in sinif_map and siniflar:
            secili_sinif_id = int(siniflar[0]["id"])
        secili_sinif = sinif_map.get(secili_sinif_id) if secili_sinif_id else None
        if secili_sinif_id:
            session["ui_sinif_id"] = secili_sinif_id

        seviye = sinif_seviye_bul(secili_sinif) if secili_sinif else 8
        moduller = aktif_moduller(seviye)
        tur = (request.values.get("tur") or tercih.get("tur") or "okul_yaprak").strip()
        if tur == "deneme" and "deneme" not in moduller:
            tur = "okul_yaprak"
        if tur not in ("okul_yaprak", "evde_test", "deneme"):
            tur = "okul_yaprak"

        dersler = school_courses()
        secili_ders = (request.values.get("ders") or tercih.get("ders") or (dersler[0] if dersler else "Matematik")).strip()
        soru_sayisi = request.values.get("soru_sayisi", type=int) or tercih.get("soru_sayisi") or 20
        yanlis_goturme = request.values.get("yanlis_goturme", type=int)
        if yanlis_goturme not in (0, 3, 4):
            yanlis_goturme = tercih.get("yanlis_goturme") if tercih.get("yanlis_goturme") in (0, 3, 4) else (3 if seviye == 8 else 0)

        ogrenciler = db.sinif_ogrencileri(secili_sinif_id) if secili_sinif_id else []
        bekleyen_satirlar = []
        kaydedilen_satirlar = []

        if request.method == "POST":
            islem = (request.form.get("islem") or "elle_dy").strip()
            tercih_kaydet(
                oid,
                sinif_id=secili_sinif_id,
                ders=secili_ders,
                tur=tur,
                soru_sayisi=soru_sayisi,
                yanlis_goturme=yanlis_goturme,
            )
            if islem == "elle_dy" and secili_sinif_id:
                ad = (request.form.get("ad") or f"{secili_ders} Yaprak Testi").strip()
                tarih = (request.form.get("tarih") or date.today().isoformat()).strip()
                anahtar_ham = (request.form.get("anahtar") or "").strip()
                try:
                    key = answer_letters(anahtar_ham, key=True) if anahtar_ham else None
                    res = sinif_ders_toplu_kaydet(
                        sinif_id=secili_sinif_id,
                        title=ad,
                        when=tarih,
                        course=secili_ders,
                        count=len(key) if key else soru_sayisi,
                        penalty=yanlis_goturme,
                        form_data=request.form,
                        ogretmen_id=oid,
                        key=key,
                        satir_bazli=True,
                    )
                    kaydedilen_satirlar = res["kaydedilen"]
                    bekleyen_satirlar = res["bekleyen"]
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.form.get("format") == "json":
                        return jsonify(ok=res["ok"], kaydedilen=kaydedilen_satirlar, bekleyen=bekleyen_satirlar)
                    if kaydedilen_satirlar:
                        flash(f"{ad}: {len(kaydedilen_satirlar)} öğrencinin sonucu kaydedildi ve velilere bildirildi.", "success")
                    if bekleyen_satirlar:
                        flash(f"{len(bekleyen_satirlar)} satırda hata olduğu için bekletildi.", "warning")
                except (ValueError, TypeError) as exc:
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.form.get("format") == "json":
                        return jsonify(ok=False, error=str(exc), kaydedilen=[], bekleyen=[]), 422
                    flash(str(exc), "warning")
        else:
            if request.args.get("sinif_id") or request.args.get("ders") or request.args.get("tur"):
                tercih_kaydet(
                    oid,
                    sinif_id=secili_sinif_id,
                    ders=secili_ders,
                    tur=tur,
                    soru_sayisi=soru_sayisi,
                    yanlis_goturme=yanlis_goturme,
                )

        # Seçili sınıftaki optik testler
        con = db._conn()
        try:
            optik_testler = [
                dict(r)
                for r in con.execute(
                    """SELECT e.* FROM lgs_optik_sinav e
                       WHERE (e.silindi_at IS NULL OR e.silindi_at='')
                         AND (e.sinif_id = ? OR e.sinif_id IS NULL)
                       ORDER BY e.id DESC LIMIT 30""",
                    (secili_sinif_id,),
                ).fetchall()
            ]
        finally:
            con.close()

        taslak_anahtar = f"giris:{secili_sinif_id}:{secili_ders}:{tur}"
        taslak = taslak_getir(oid, taslak_anahtar)

        return render_template(
            "hizli_giris.html",
            siniflar=siniflar,
            secili_sinif=secili_sinif,
            secili_sinif_id=secili_sinif_id,
            seviye=seviye,
            aktif_moduller=moduller,
            tur=tur,
            dersler=dersler,
            secili_ders=secili_ders,
            soru_sayisi=soru_sayisi,
            yanlis_goturme=yanlis_goturme,
            ogrenciler=ogrenciler,
            optik_testler=optik_testler,
            bugun=date.today().isoformat(),
            taslak=taslak,
            taslak_anahtar=taslak_anahtar,
            bekleyen_satirlar=bekleyen_satirlar,
            kaydedilen_satirlar=kaydedilen_satirlar,
        )

    @app.post("/api/giris/excel-coz")
    @login_required
    def api_giris_excel_coz():
        sinif_id = request.form.get("sinif_id", type=int) or (request.json.get("sinif_id") if request.is_json else None)
        metin = request.form.get("metin") if not request.is_json else (request.json.get("metin") or "")
        ogrenciler = db.sinif_ogrencileri(int(sinif_id)) if sinif_id else []
        sonuc = excel_yapistir_coz(metin or "", ogrenciler)
        return jsonify(ok=True, **sonuc)

    @app.route("/api/giris/taslak", methods=["GET", "POST"])
    @login_required
    def api_giris_taslak():
        oid = session.get("ogretmen_id")
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            anahtar = payload.get("anahtar") or request.form.get("anahtar") or "varsayilan"
            veri = payload.get("veri")
            if veri is None:
                raw_veri = request.form.get("veri") or "{}"
                try:
                    veri = json.loads(raw_veri)
                except Exception:
                    veri = {"ham": raw_veri}
            zaman = taslak_kaydet(oid, anahtar, veri if isinstance(veri, dict) else {"deger": veri})
            return jsonify(ok=True, anahtar=anahtar, guncelleme=zaman)
        anahtar = request.args.get("anahtar") or "varsayilan"
        kayit = taslak_getir(oid, anahtar)
        return jsonify(ok=True, anahtar=anahtar, taslak=kayit)
