"""Aşama 5: Ortak sınav/test giriş akışı, yumuşak silme, optik iyileştirmeler ve taslak testleri."""
import io
import json
import shutil
import sqlite3
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from unittest import mock
import pytest

import database as db
import lgs_optik
import batch_optik
import sinav_okuyucu
from hizli_giris import excel_yapistir_coz, taslak_getir, taslak_kaydet, tercih_getir, tercih_kaydet
from student_results import sinif_ders_toplu_kaydet
from web_app import app


def test_migration_005_ve_006_up_down_up(tmp_path):
    """005_sinav_kaynak ve 006_sinav_yumusak_silme migration up -> down -> up döngüsü."""
    from migrations import discover_migrations, migrate_up, migrate_down

    test_db = tmp_path / "mig56.db"
    shutil.copy2(db.DB_PATH, test_db)
    con = sqlite3.connect(str(test_db))
    con.row_factory = sqlite3.Row
    try:
        migs = {v: name for v, name, _ in discover_migrations()}
        assert 5 in migs and 6 in migs
        migrate_up(con, target=6)
        # Tablolar ve sütunlar var mı?
        cols_optik = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
        cols_deneme = {r[1] for r in con.execute("PRAGMA table_info(lgs_deneme)").fetchall()}
        assert "kaynak" in cols_optik
        assert "silindi_at" in cols_optik
        assert "silindi_at" in cols_deneme

        con.execute("UPDATE lgs_optik_sinav SET silindi_at='2026-10-19' WHERE id=(SELECT id FROM lgs_optik_sinav LIMIT 1)")
        con.commit()
        migrate_down(con, target=4)
        silinmis_sayisi = con.execute("SELECT COUNT(*) FROM lgs_optik_sinav WHERE silindi_at IS NOT NULL").fetchone()[0]
        assert silinmis_sayisi == 0

        migrate_up(con, target=6)
        cols_optik_up2 = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
        assert "silindi_at" in cols_optik_up2
    finally:
        con.close()


def test_sinav_okuyucu_adaptoru_ve_yumusak_silme():
    """Hem lgs_deneme_ders hem lgs_optik_sonuc kayıtları sinav_okuyucu ile okunur; yumuşak silinenler gizlenir ve geri alınabilir."""
    con = db._conn()
    try:
        ogr = con.execute("SELECT id, sinif_id FROM ogrenciler LIMIT 1").fetchone()
        ogretmen = con.execute("SELECT id FROM ogretmenler LIMIT 1").fetchone()
    finally:
        con.close()
    assert ogr and ogretmen
    oid = int(ogr["id"])
    sid = int(ogr["sinif_id"])
    tid = int(ogretmen["id"])

    # 1. Elle ders yaprak testi ekle
    eklenen = db.lgs_deneme_ekle(
        oid,
        "Adaptör Yaprak 1",
        "2026-10-15",
        [{"ders": "Matematik", "soru_sayisi": 20, "dogru": 16, "yanlis": 3, "bos": 1, "yanlis_goturme": 3}],
        ogretmen_id=tid,
        tur="ders",
    )
    assert eklenen["ok"]

    # 2. Optik yaprak testi ekle
    eid = lgs_optik.sinav_ekle(
        "Adaptör Optik Yaprak",
        "2026-10-16",
        "ornek.pdf",
        ["A"] * 10,
        tid,
        tur="yaprak",
        ders="Matematik",
        sinif_id=sid,
        yanlis_goturme=3,
        secenekler="ABCD",
        kaynak="kamera",
    )
    lgs_optik.sonuc_kaydet(eid, oid, ["A"] * 8 + ["B", ""])

    satirlar = sinav_okuyucu.okul_yaprak_satirlari({oid})
    adlar = {r["ad"] for r in satirlar}
    assert "Adaptör Yaprak 1" in adlar
    assert "Adaptör Optik Yaprak" in adlar

    # Yumuşak silme
    lgs_optik.sinav_sil(eid)
    db.deneme_grup_sil("Adaptör Yaprak 1", "2026-10-15", "ders")

    satirlar_silindi = sinav_okuyucu.okul_yaprak_satirlari({oid})
    adlar_silindi = {r["ad"] for r in satirlar_silindi}
    assert "Adaptör Yaprak 1" not in adlar_silindi
    assert "Adaptör Optik Yaprak" not in adlar_silindi

    # Geri yükleme (L8)
    lgs_optik.sinav_geri_al(eid)
    db.deneme_grup_geri_al("Adaptör Yaprak 1", "2026-10-15", "ders")

    satirlar_geri = sinav_okuyucu.okul_yaprak_satirlari({oid})
    adlar_geri = {r["ad"] for r in satirlar_geri}
    assert "Adaptör Yaprak 1" in adlar_geri
    assert "Adaptör Optik Yaprak" in adlar_geri


def test_l5_l6_evde_test_dogrulama_form_koruma_ve_5_secenek():
    """L5 & L6: Doğrulama hatasında 422 döner, form verileri ve geçici PDF korunur; 5 seçenek (E) kabul edilir."""
    assert lgs_optik.anahtar_oku("ABCDE", secenekler="ABCDE") == ["A", "B", "C", "D", "E"]
    assert lgs_optik.anahtar_oku("ABCDE", secenekler="ABCD") is None

    con = db._conn()
    try:
        ogretmen = con.execute("SELECT id, ad_soyad FROM ogretmenler LIMIT 1").fetchone()
    finally:
        con.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["ogretmen_id"] = int(ogretmen["id"])
        sess["ogretmen_adi"] = ogretmen["ad_soyad"]

    yarin = (date.today() + timedelta(days=1)).isoformat()
    sahte_pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    resp = client.post(
        "/lgs",
        data={
            "islem": "optik_ekle",
            "ad": "Korunan Sınav Adı",
            "tur": "deneme",
            "tarih": yarin,
            "soru_sayisi": "10",
            "secenekler": "ABCDE",
            "anahtar": "ABCDE",  # 10 yerine 5 cevap -> doğrulama hatası
            "pdf": (io.BytesIO(sahte_pdf), "sorular.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 422
    html = resp.get_data(as_text=True)
    assert "Korunan Sınav Adı" in html
    assert "Seçilen PDF korundu" in html
    assert "Cevap sayısı soru sayısıyla aynı olmalı" in html


def test_satir_bazli_kayit_ve_atomik_rollback():
    """Geçerli satırlar kaydedilir, hatalı satır (D+Y > soru) bekleyen listesinde döner; DB hatasında tümü rollback olur."""
    con = db._conn()
    try:
        sinif = con.execute("SELECT id FROM siniflar LIMIT 1").fetchone()
        ogrenciler = con.execute("SELECT id, ad_soyad FROM ogrenciler WHERE sinif_id=? LIMIT 2", (sinif["id"],)).fetchall()
        ogretmen = con.execute("SELECT id FROM ogretmenler LIMIT 1").fetchone()
    finally:
        con.close()
    assert len(ogrenciler) >= 2
    o1, o2 = ogrenciler[0], ogrenciler[1]

    form = {
        f"dogru_{o1['id']}": "15",
        f"yanlis_{o1['id']}": "3",
        f"dogru_{o2['id']}": "18",
        f"yanlis_{o2['id']}": "5",  # 18+5=23 > 20 soru -> hatalı satır
    }
    res = sinif_ders_toplu_kaydet(
        sinif_id=int(sinif["id"]),
        title="Satır Bazlı Test",
        when="2026-10-18",
        course="Matematik",
        count=20,
        penalty=3,
        form_data=form,
        ogretmen_id=int(ogretmen["id"]),
        satir_bazli=True,
    )
    assert res["ok"] is True
    assert len(res["kaydedilen"]) == 1
    assert res["kaydedilen"][0]["ogrenci_id"] == int(o1["id"])
    assert len(res["bekleyen"]) == 1
    assert res["bekleyen"][0]["ogrenci_id"] == int(o2["id"])

    # Atomik rollback testi: 2. satırda beklenmedik veritabanı hatası simüle et
    con_check = db._conn()
    onceki_sayi = con_check.execute("SELECT COUNT(*) FROM lgs_deneme WHERE ad='Atomik Rollback Testi'").fetchone()[0]
    con_check.close()
    assert onceki_sayi == 0

    real_conn = db._conn

    class FailingConn:
        def __init__(self, wrapped):
            self._w = wrapped
            self.inserts = 0

        def __enter__(self):
            self._w.__enter__()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return self._w.__exit__(exc_type, exc_val, exc_tb)

        def execute(self, sql, params=()):
            if "INSERT INTO lgs_deneme_ders" in sql:
                self.inserts += 1
                if self.inserts == 2:
                    raise sqlite3.IntegrityError("Simüle edilen DB hatası")
            return self._w.execute(sql, params)

        def close(self):
            self._w.close()

        def __getattr__(self, name):
            return getattr(self._w, name)

    with mock.patch("database._conn", side_effect=lambda: FailingConn(real_conn())):
        with pytest.raises(sqlite3.IntegrityError):
            sinif_ders_toplu_kaydet(
                sinif_id=int(sinif["id"]),
                title="Atomik Rollback Testi",
                when="2026-10-18",
                course="Matematik",
                count=20,
                penalty=3,
                form_data={
                    f"dogru_{o1['id']}": "10",
                    f"yanlis_{o1['id']}": "2",
                    f"dogru_{o2['id']}": "12",
                    f"yanlis_{o2['id']}": "1",
                },
                ogretmen_id=int(ogretmen["id"]),
                satir_bazli=True,
            )

    con_after = db._conn()
    sonraki_sayi = con_after.execute("SELECT COUNT(*) FROM lgs_deneme WHERE ad='Atomik Rollback Testi'").fetchone()[0]
    con_after.close()
    assert sonraki_sayi == 0


def test_excel_yapistir_coz_birim():
    """Excel yapıştırma ayrıştırıcısı birim testi."""
    ogrenciler = [
        {"id": 10, "ogr_no": "112", "ad_soyad": "Ahmet Yılmaz"},
        {"id": 11, "ogr_no": "87", "ad_soyad": "Ayşe Demir"},
        {"id": 12, "ogr_no": "95", "ad_soyad": "Mehmet Kaya"},
    ]
    metin = "No\tDoğru\tYanlış\n112\t18\t2\nAyşe Demir\t15\t3\n95\tK\n999\t10\t2\n"
    sonuc = excel_yapistir_coz(metin, ogrenciler)
    assert len(sonuc["eslesen"]) == 3
    assert sonuc["eslesen"][0]["ogrenci_id"] == 10
    assert sonuc["eslesen"][0]["dogru"] == 18
    assert sonuc["eslesen"][0]["yanlis"] == 2
    assert sonuc["eslesen"][1]["ogrenci_id"] == 11
    assert sonuc["eslesen"][1]["dogru"] == 15
    assert sonuc["eslesen"][2]["ogrenci_id"] == 12
    assert sonuc["eslesen"][2]["katilmadi"] is True
    assert len(sonuc["eslesmeyen"]) == 1
    assert "999" in sonuc["eslesmeyen"][0]["ham"]


def test_optik_iyilestirmeler_o1_o13():
    """O1-O13: yanlis_goturme hesabı, 60 sayfa sınırı, süresi dolan batch temizliği, öğrenci atama ve satır bazlı kayıt."""
    assert batch_optik.OPTIK_AZAMI_SAYFA == 60

    con = db._conn()
    try:
        sinif = con.execute("SELECT id FROM siniflar LIMIT 1").fetchone()
        ogrenciler = con.execute("SELECT id, ad_soyad, ogr_no FROM ogrenciler WHERE sinif_id=? LIMIT 2", (sinif["id"],)).fetchall()
        ogretmen = con.execute("SELECT id, ad_soyad FROM ogretmenler LIMIT 1").fetchone()
    finally:
        con.close()
    tid = int(ogretmen["id"])
    sid = int(sinif["id"])
    o1, o2 = ogrenciler[0], ogrenciler[1]

    # O10: Süresi dolan batch temizliği
    bcon = batch_optik.connection()
    bcon.execute(
        "INSERT OR REPLACE INTO pdf_optik_batch(id,owner,eid,pdf,pages,key_hash,expires,saved) VALUES(?,?,?,?,?,?,?,0)",
        ("eski_batch_test", tid, 1, b"%PDF-", 1, "hash", time.time() - 100),
    )
    bcon.commit()
    bcon.close()
    batch_optik.cleanup_expired_batches(force=True)
    bcon = batch_optik.connection()
    assert bcon.execute("SELECT 1 FROM pdf_optik_batch WHERE id='eski_batch_test'").fetchone() is None
    bcon.close()

    # O1 (yanlis_goturme=4 ile sınav), O5 (öğrenci atama), O2 & O3 (satır bazlı kayıt)
    import kamera_test as kt
    eid = lgs_optik.sinav_ekle(
        "Optik 4 Götürme Testi",
        date.today().isoformat(),
        "test.pdf",
        ["A", "A", "A", "A", "A"],
        tid,
        tur="yaprak",
        ders="Fen Bilimleri",
        sinif_id=sid,
        yanlis_goturme=4,
        secenekler="ABCD",
    )
    kcon = kt.connect()
    kcon.execute("INSERT OR REPLACE INTO kamera_sinav(sinav_id,choices) VALUES(?,?)", (eid, "ABCD"))
    bid = "aktif_batch_test"
    exam = kt.exam_owned.__wrapped__(eid) if hasattr(kt.exam_owned, "__wrapped__") else None
    key_hash = kt.fingerprint(["A", "A", "A", "A", "A"])
    kcon.execute(
        "INSERT OR REPLACE INTO pdf_optik_batch(id,owner,eid,pdf,pages,key_hash,expires,saved) VALUES(?,?,?,?,?,?,?,0)",
        (bid, tid, eid, b"%PDF-", 2, key_hash, time.time() + 3600),
    )
    # 1. sayfa okunamadı (oid=None), 2. sayfa şüpheli (?)
    kcon.execute(
        "INSERT OR REPLACE INTO pdf_optik_page(batch_id,no,oid,data,preview) VALUES(?,?,?,?,?)",
        (bid, 1, None, json.dumps({"error": "QR okunamadı", "answers": "AAAAB"}), b"jpg"),
    )
    kcon.execute(
        "INSERT OR REPLACE INTO pdf_optik_page(batch_id,no,oid,data,preview) VALUES(?,?,?,?,?)",
        (bid, 2, int(o2["id"]), json.dumps({"name": o2["ad_soyad"], "number": o2["ogr_no"], "answers": "AAA?B", "uncertain": [4], "existing": False, "before": kt.fingerprint(None), "error": ""}), b"jpg"),
    )
    kcon.commit()
    kcon.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["ogretmen_id"] = tid
        sess["ogretmen_adi"] = ogretmen["ad_soyad"]
        sess["kamera_csrf"] = "test_csrf"

    # O5: 1. sayfaya o1 öğrencisini ata
    assign_resp = client.post(
        f"/yaprak-kamera/pdf-optik/{bid}/ata/1",
        data={"csrf": "test_csrf", "oid": str(o1["id"])},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.get_json()["ok"] is True

    # O4 & O8: Satırlar JSON uç noktası
    rows_resp = client.get(f"/yaprak-kamera/pdf-optik/{bid}/satirlar")
    assert rows_resp.status_code == 200
    rj = rows_resp.get_json()
    assert rj["ok"] is True
    assert len(rj["rows"]) == 2

    # O2 & O3: Her iki sayfayı seçerek JSON modunda kaydet -> 1. sayfa kaydedilir (4 doğru, 1 yanlış -> 4 götürmeyle net 3.75), 2. sayfa '?' içerdiği için bekleyen'de döner!
    save_resp = client.post(
        f"/yaprak-kamera/pdf-optik/{bid}/kaydet",
        data={
            "csrf": "test_csrf",
            "format": "json",
            "select": ["1", "2"],
            "confirm_1": "yes",
            "answers_1": "AAAAB",
            "confirm_2": "yes",
            "answers_2": "AAA?B",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert save_resp.status_code == 200
    sj = save_resp.get_json()
    assert sj["ok"] is True
    assert len(sj["kaydedilen"]) == 1
    assert sj["kaydedilen"][0]["no"] == 1
    assert sj["kaydedilen"][0]["net"] == 3.75  # O1: 4 yanlış 1 doğru götürür: 4 - 1/4 = 3.75
    assert len(sj["bekleyen"]) == 1
    assert sj["bekleyen"][0]["no"] == 2


def test_giris_ekrani_taslak_ve_tercih():
    """Ortak giriş ekranı (/giris), tercih hatırlama ve otomatik taslak API testi."""
    con = db._conn()
    try:
        ogretmen = con.execute("SELECT id, ad_soyad FROM ogretmenler LIMIT 1").fetchone()
        sinif = con.execute("SELECT id FROM siniflar LIMIT 1").fetchone()
    finally:
        con.close()
    tid = int(ogretmen["id"])
    sid = int(sinif["id"])

    tercih_kaydet(tid, sinif_id=sid, ders="Fen Bilimleri", tur="okul_yaprak", soru_sayisi=25, yanlis_goturme=3)
    t = tercih_getir(tid)
    assert t["sinif_id"] == sid
    assert t["ders"] == "Fen Bilimleri"
    assert t["soru_sayisi"] == 25

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["ogretmen_id"] = tid
        sess["ogretmen_adi"] = ogretmen["ad_soyad"]

    # Taslak kaydet & oku
    post_t = client.post("/api/giris/taslak", json={"anahtar": "test_taslak", "veri": {"satirlar": {"1": {"d": "14", "y": "2"}}}})
    assert post_t.status_code == 200
    assert post_t.get_json()["ok"] is True

    get_t = client.get("/api/giris/taslak?anahtar=test_taslak")
    assert get_t.status_code == 200
    assert get_t.get_json()["taslak"]["veri"]["satirlar"]["1"]["d"] == "14"

    # /giris ekranı açılıyor mu?
    giris_resp = client.get("/giris")
    assert giris_resp.status_code == 200
    assert "Hızlı Giriş" in giris_resp.get_data(as_text=True)

    # /yaprak-optik alias yönlendirmesi (O11)
    alias_resp = client.get("/yaprak-optik")
    assert alias_resp.status_code in (301, 302)


def test_deneme_optik_karti_secili_sinif_ve_derse_baglanir():
    """Deneme optik kartı başka teste gitmez; yoksa sınıf ve dersi taşıyarak oluşturma ekranını açar."""
    import kamera_test as kt

    con = db._conn()
    try:
        ogretmen = con.execute(
            "SELECT id, ad_soyad FROM ogretmenler WHERE COALESCE(yetki,'tam')='tam' LIMIT 1"
        ).fetchone()
        sinif = con.execute("SELECT id, sinif_adi FROM siniflar ORDER BY id LIMIT 1").fetchone()
    finally:
        con.close()
    tid, sid = int(ogretmen["id"]), int(sinif["id"])
    ders = "Fen Bilimleri"
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.update(ogretmen_id=tid, ogretmen_adi=ogretmen["ad_soyad"], ogretmen_yetki="tam")

    bos = client.get(f"/giris?sinif_id={sid}&ders={ders}&tur=deneme")
    html = bos.get_data(as_text=True)
    assert bos.status_code == 200
    assert "Optik test oluştur" in html
    assert f"sinif_id={sid}" in html
    assert "tur=deneme" in html
    assert "/pdf-optik/formlar" not in html

    hazir = client.get(f"/yaprak-kamera?sinif_id={sid}&ders={ders}&tur=deneme")
    hazir_html = hazir.get_data(as_text=True)
    assert hazir.status_code == 200
    assert 'name="tur" value="deneme"' in hazir_html
    assert f'value="{sid}" selected' in hazir_html or f'value="{sid}"  selected' in hazir_html

    eid = lgs_optik.sinav_ekle(
        "Fen deneme optik", "2026-10-21", "fen-deneme.pdf", ["A"], tid,
        tur="deneme", ders=ders, sinif_id=sid, kaynak="kamera",
    )
    kcon = kt.connect()
    try:
        kcon.execute("INSERT INTO kamera_sinav(sinav_id, choices) VALUES(?, ?)", (eid, "ABCD"))
        kcon.commit()
    finally:
        kcon.close()
    try:
        dolu = client.get(f"/giris?sinif_id={sid}&ders={ders}&tur=deneme")
        dolu_html = dolu.get_data(as_text=True)
        assert f"/yaprak-kamera/{eid}/pdf-optik/formlar" in dolu_html
        assert f"/yaprak-kamera/{eid}#optik-yukle" in dolu_html
        yaprak = client.get(f"/giris?sinif_id={sid}&ders={ders}&tur=okul_yaprak")
        assert f"/yaprak-kamera/{eid}/pdf-optik/formlar" not in yaprak.get_data(as_text=True)
    finally:
        kcon = kt.connect()
        try:
            kcon.execute("DELETE FROM kamera_sinav WHERE sinav_id=?", (eid,))
            kcon.execute("DELETE FROM lgs_optik_sinav WHERE id=?", (eid,))
            kcon.commit()
        finally:
            kcon.close()
