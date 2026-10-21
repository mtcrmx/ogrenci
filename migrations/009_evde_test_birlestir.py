"""Migration 009: Funda hocanın ev denemesini İnkılap testine çevirir, Türkçe kopyalarını birleştirir.

Funda Kiraz'ın evde deneme diye girdiği kayıt yaprak test olur ve dersi
T.C. İnkılap Tarihi kalır. Türkçe testiyle birleştirilmez.
Türkçe dersinde 8/A ve 8/B'ye ayrı ayrı verilmiş aynı test tek kayda iner.
Okulda okutulan kamera denemelerine dokunulmaz.
"""
import re
from datetime import datetime

VERSION = 9
NAME = "009_evde_test_birlestir"


def _norm(ad: str) -> str:
    s = (ad or "").casefold().replace("i\u0307", "i")
    s = re.sub(r"8\s*/\s*[ab]", " ", s)
    s = re.sub(r"\b8\s*[ab]\b", " ", s)
    s = re.sub(r"[^a-z0-9çğıöşü]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_INKILAP = "T.C. İnkılap Tarihi"


def _sekiz(sinif_adi: str | None) -> bool:
    return str(sinif_adi or "").startswith("8/")


def _funda(ad: str) -> bool:
    n = _norm(ad)
    return "funda" in n and "kiraz" in n


def _turkce(ders: str) -> bool:
    n = _norm(ders)
    return n == "türkçe" or n == "turkce"


def _tasi(con, tablo: str, tutulan: int, kopya: int, anahtar: str):
    var = con.execute(
        f"SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tablo,)
    ).fetchone()
    if not var:
        return
    kolon = {r[1] for r in con.execute(f"PRAGMA table_info({tablo})").fetchall()}
    if "sinav_id" not in kolon or anahtar not in kolon:
        return
    olan = {r[0] for r in con.execute(f"SELECT {anahtar} FROM {tablo} WHERE sinav_id=?", (tutulan,))}
    for (deger,) in con.execute(f"SELECT {anahtar} FROM {tablo} WHERE sinav_id=?", (kopya,)):
        if deger in olan:
            continue
        con.execute(
            f"UPDATE {tablo} SET sinav_id=? WHERE sinav_id=? AND {anahtar}=?",
            (tutulan, kopya, deger),
        )
        olan.add(deger)


def _yardim_tasi(con, tutulan: int, kopya: int):
    var = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ev_yardim'"
    ).fetchone()
    if not var:
        return
    kolon = {r[1] for r in con.execute("PRAGMA table_info(ev_yardim)").fetchall()}
    if "id" not in kolon:
        return
    for rid, oid, no in con.execute(
        "SELECT id, ogrenci_id, no FROM ev_yardim WHERE sinav_id=?", (kopya,)
    ):
        cakisma = con.execute(
            "SELECT 1 FROM ev_yardim WHERE sinav_id=? AND ogrenci_id=? AND no=?",
            (tutulan, oid, no),
        ).fetchone()
        if cakisma:
            continue
        con.execute("UPDATE ev_yardim SET sinav_id=? WHERE id=?", (tutulan, rid))


def up(con):
    var = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lgs_optik_sinav'"
    ).fetchone()
    if not var:
        return
    kolon = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
    if "tur" not in kolon or "kaynak" not in kolon:
        return
    funda = [
        int(r[0]) for r in con.execute("SELECT id, ad_soyad FROM ogretmenler")
        if _funda(r[1] or "")
    ]
    if funda:
        yer = ",".join("?" * len(funda))
        con.execute(
            f"""
            UPDATE lgs_optik_sinav
            SET tur='yaprak', kaynak='ev_yaprak', ders=?
            WHERE tur='deneme'
              AND COALESCE(kaynak, 'ev') IN ('ev', 'ev_yaprak')
              AND ogretmen_id IN ({yer})
            """,
            (_INKILAP, *funda),
        )
    con.execute(
        """
        UPDATE lgs_optik_sinav
        SET tur='yaprak', kaynak='ev_yaprak'
        WHERE tur='deneme'
          AND COALESCE(kaynak, 'ev') IN ('ev', 'ev_yaprak')
          AND COALESCE(ders, '') != ?
        """,
        (_INKILAP,),
    )
    if "sinif_id" not in kolon or "silindi_at" not in kolon:
        con.commit()
        return
    rows = con.execute(
        """
        SELECT o.id, o.ad, o.tarih, o.ders, o.cevaplar, o.ogretmen_id, o.sinif_id, s.sinif_adi
        FROM lgs_optik_sinav o
        JOIN siniflar s ON s.id = o.sinif_id
        WHERE COALESCE(o.kaynak, 'ev') IN ('ev', 'ev_yaprak')
          AND (o.silindi_at IS NULL OR o.silindi_at = '')
        """
    ).fetchall()
    gruplar: dict[tuple, list] = {}
    for row in rows:
        if not _sekiz(row[7]) or not _turkce(row[3] or ""):
            continue
        if int(row[5] or 0) in funda:
            continue
        anahtar = (row[5], row[2], row[4], _norm(row[1]))
        gruplar.setdefault(anahtar, []).append(row)
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for grup in gruplar.values():
        siniflar = {int(r[6]) for r in grup}
        if len(siniflar) < 2:
            continue
        tutulan = min(grup, key=lambda r: int(r[0]))
        for kopya in grup:
            if int(kopya[0]) == int(tutulan[0]):
                continue
            _tasi(con, "lgs_optik_sonuc", int(tutulan[0]), int(kopya[0]), "ogrenci_id")
            _tasi(con, "ev_soru_meta", int(tutulan[0]), int(kopya[0]), "no")
            _tasi(con, "lgs_soru_kazanim", int(tutulan[0]), int(kopya[0]), "no")
            _tasi(con, "ev_grup_test", int(tutulan[0]), int(kopya[0]), "grup_id")
            _yardim_tasi(con, int(tutulan[0]), int(kopya[0]))
            con.execute(
                "UPDATE lgs_optik_sinav SET silindi_at=? WHERE id=?",
                (simdi, int(kopya[0])),
            )
        con.execute(
            """
            UPDATE lgs_optik_sinav
            SET sinif_id=NULL, tur='yaprak', kaynak='ev_yaprak'
            WHERE id=?
            """,
            (int(tutulan[0]),),
        )
    con.commit()


def down(con):
    """Birleştirilen kopyalar geri ayrılmaz; okul denemeleri zaten değişmedi."""
    return
