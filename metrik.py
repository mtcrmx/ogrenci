"""Tek hesap modülü: oran, net, götürme ve toplam istatistikler (Aşama 3)."""
from __future__ import annotations

VARSAYILAN_GOTURME = 3


def oran(dogru: int | float | None, soru: int | float | None) -> float | None:
    """Toplam doğru ÷ toplam soru (1 ondalık). Soru 0 veya None ise None döner."""
    if not soru or soru <= 0:
        return None
    return round(100 * float(dogru or 0) / float(soru), 1)


def net(
    dogru: int | float | None,
    yanlis: int | float | None,
    goturme: int | float | None = VARSAYILAN_GOTURME,
) -> float:
    """Doğru − (yanlış / götürme). Götürme 0 ise yanlış doğruyu götürmez."""
    d = float(dogru or 0)
    y = float(yanlis or 0)
    g = VARSAYILAN_GOTURME if goturme is None else int(goturme)
    return round(d - (y / g if g else 0.0), 2)


def topla(satirlar) -> dict:
    """Satırları toplayarak ΣD, ΣY, ΣB, ΣS ve toplam üzerinden oranı hesaplar.
    Öğrenci oranlarının ortalaması ALINMAZ (her zaman ΣD / ΣS).
    """
    rows = list(satirlar or [])
    if not rows:
        return {
            "n": 0,
            "toplam_dogru": 0,
            "toplam_yanlis": 0,
            "toplam_bos": 0,
            "toplam_soru": 0,
            "toplam_net": 0.0,
            "dogru": 0,
            "yanlis": 0,
            "bos": 0,
            "net": 0,
            "rate": None,
            "oran": None,
        }
    n = len(rows)
    toplam_dogru = sum(int(r.get("dogru") or 0) for r in rows)
    toplam_yanlis = sum(int(r.get("yanlis") or 0) for r in rows)
    toplam_bos = sum(int(r.get("bos") or 0) for r in rows)
    toplam_soru = sum(
        int(r.get("soru_sayisi") or ((r.get("dogru") or 0) + (r.get("yanlis") or 0) + (r.get("bos") or 0)))
        for r in rows
    )
    toplam_net = sum(
        float(
            r["net"]
            if r.get("net") is not None
            else net(r.get("dogru"), r.get("yanlis"), r.get("yanlis_goturme", VARSAYILAN_GOTURME))
        )
        for r in rows
    )
    genel_oran = oran(toplam_dogru, toplam_soru)
    return {
        "n": n,
        "toplam_dogru": toplam_dogru,
        "toplam_yanlis": toplam_yanlis,
        "toplam_bos": toplam_bos,
        "toplam_soru": toplam_soru,
        "toplam_net": round(toplam_net, 2),
        "dogru": round(toplam_dogru / n, 1),
        "yanlis": round(toplam_yanlis / n, 1),
        "bos": round(toplam_bos / n, 1),
        "net": round(toplam_net / n, 1),
        "rate": genel_oran,
        "oran": genel_oran,
    }


def toplu_oran(ciftler) -> float | None:
    """(dogru, soru_sayisi) çiftlerinden ΣD ÷ ΣS oranını hesaplar."""
    d_top = 0.0
    s_top = 0.0
    for item in ciftler or []:
        if isinstance(item, dict):
            d_top += float(item.get("dogru") or 0)
            s_top += float(item.get("soru_sayisi") or 0)
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            d_top += float(item[0] or 0)
            s_top += float(item[1] or 0)
    return oran(d_top, s_top)


def goster(deger) -> str:
    """Sayısal değeri Türkçe ondalık virgülle ('61,4') veya None ise '—' olarak biçimlendirir."""
    if deger is None or deger == "":
        return "—"
    try:
        v = round(float(deger), 1)
        return f"{v:.1f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def yuzde_filtre(deger) -> str:
    """Jinja `|yuzde` filtresi: None -> '—', sayı -> '%75.0'."""
    if deger is None or deger == "":
        return "—"
    try:
        return f"%{round(float(deger), 1)}"
    except (TypeError, ValueError):
        return "—"


def net_filtre(deger) -> str:
    """Jinja `|net` filtresi: None -> '—', sayı -> '12.33'."""
    if deger is None or deger == "":
        return "—"
    try:
        return f"{round(float(deger), 2):g}" if float(deger).is_integer() else f"{round(float(deger), 2):.2f}"
    except (TypeError, ValueError):
        return "—"


KAYNAK_ADLARI = {"evde": "Evde soru", "deneme": "Deneme", "yaprak": "Yaprak test"}


def seviye_kaynaklari(seviye: int | None) -> tuple[str, ...]:
    """8. sınıfta yaprak test modülü yoktur; okul testleri deneme sayılır."""
    return ("evde", "deneme") if seviye == 8 else ("evde", "deneme", "yaprak")


def _seviye_sql(con) -> str:
    cols = {r[1] for r in con.execute("PRAGMA table_info(siniflar)").fetchall()}
    if "seviye" in cols:
        return "COALESCE(s.seviye, CAST(SUBSTR(s.sinif_adi, 1, 1) AS INTEGER))"
    return "CAST(SUBSTR(s.sinif_adi, 1, 1) AS INTEGER)"


def birlesik_sonuclar(con, ogrenci_idler=None) -> list[dict]:
    """Evde soru, deneme ve yaprak test sonuçlarını tek biçimde döner.

    Her satır bir öğrencinin bir kayıttaki bir ders sonucudur:
    {ogrenci_id, seviye, kaynak, kayit, ad, tarih, ders, dogru, yanlis, bos, soru_sayisi, net}.
    Silinmiş sınav ve sonuçlar dahil edilmez.
    """
    tablolar = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    sev = _seviye_sql(con)
    filtre, params = "", []
    if ogrenci_idler is not None:
        ids = [int(i) for i in ogrenci_idler]
        if not ids:
            return []
        filtre = f" AND o.id IN ({','.join('?' * len(ids))})"
        params = ids
    satirlar: list[dict] = []

    if {"lgs_optik_sinav", "lgs_optik_sonuc"} <= tablolar:
        e_cols = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
        silinme = " AND (e.silindi_at IS NULL OR e.silindi_at = '')" if "silindi_at" in e_cols else ""
        kaynak = "COALESCE(e.kaynak, '')" if "kaynak" in e_cols else "''"
        goturme = "e.yanlis_goturme" if "yanlis_goturme" in e_cols else "0"
        for r in con.execute(
            f"""SELECT r.ogrenci_id, {sev} AS seviye, e.id AS sinav_id, e.ad, e.tur, {kaynak} AS kaynak,
                       COALESCE(e.ders, '') AS ders, r.dogru, r.yanlis, r.bos, r.net, r.zaman, e.tarih,
                       e.soru_sayisi, {goturme} AS goturme
                FROM lgs_optik_sonuc r
                JOIN lgs_optik_sinav e ON e.id = r.sinav_id
                JOIN ogrenciler o ON o.id = r.ogrenci_id
                JOIN siniflar s ON s.id = o.sinif_id
                WHERE 1=1{silinme}{filtre}""",
            params,
        ):
            seviye = int(r["seviye"] or 0)
            if r["tur"] == "deneme":
                tur = "deneme"
            elif str(r["kaynak"]).startswith("ev"):
                tur = "evde"
            else:
                tur = "yaprak"
            if tur not in seviye_kaynaklari(seviye):
                tur = "deneme"
            dogru, yanlis, bos = int(r["dogru"] or 0), int(r["yanlis"] or 0), int(r["bos"] or 0)
            satirlar.append({
                "ogrenci_id": int(r["ogrenci_id"]), "seviye": seviye, "kaynak": tur,
                "kayit": f"optik-{r['sinav_id']}", "ad": r["ad"] or "",
                "tarih": str(r["zaman"] or r["tarih"] or "")[:10], "ders": r["ders"] or "",
                "dogru": dogru, "yanlis": yanlis, "bos": bos,
                "soru_sayisi": int(r["soru_sayisi"] or (dogru + yanlis + bos)),
                "net": float(r["net"]) if r["net"] is not None else net(dogru, yanlis, r["goturme"]),
            })

    if {"lgs_deneme", "lgs_deneme_ders"} <= tablolar:
        d_cols = {r[1] for r in con.execute("PRAGMA table_info(lgs_deneme)").fetchall()}
        silinme = " AND (d.silindi_at IS NULL OR d.silindi_at = '')" if "silindi_at" in d_cols else ""
        for r in con.execute(
            f"""SELECT d.ogrenci_id, {sev} AS seviye, d.id AS deneme_id, d.ad, d.tarih, d.tur,
                       dd.ders, dd.dogru, dd.yanlis, dd.bos, dd.net, dd.soru_sayisi, dd.yanlis_goturme
                FROM lgs_deneme d
                JOIN lgs_deneme_ders dd ON dd.deneme_id = d.id
                JOIN ogrenciler o ON o.id = d.ogrenci_id
                JOIN siniflar s ON s.id = o.sinif_id
                WHERE 1=1{silinme}{filtre}""",
            params,
        ):
            seviye = int(r["seviye"] or 0)
            tur = "yaprak" if r["tur"] == "ders" else "deneme"
            if tur not in seviye_kaynaklari(seviye):
                tur = "deneme"
            dogru, yanlis, bos = int(r["dogru"] or 0), int(r["yanlis"] or 0), int(r["bos"] or 0)
            satirlar.append({
                "ogrenci_id": int(r["ogrenci_id"]), "seviye": seviye, "kaynak": tur,
                "kayit": f"deneme-{r['deneme_id']}", "ad": r["ad"] or "",
                "tarih": str(r["tarih"] or "")[:10], "ders": r["ders"] or "",
                "dogru": dogru, "yanlis": yanlis, "bos": bos,
                "soru_sayisi": int(r["soru_sayisi"] or (dogru + yanlis + bos)),
                "net": float(r["net"]) if r["net"] is not None else net(dogru, yanlis, r["yanlis_goturme"]),
            })
    return satirlar


def kaynak_ozeti(satirlar, seviye: int | None = None) -> list[dict]:
    """Kaynak başına kayıt sayısı, D/Y/B, net ve başarı oranı."""
    satirlar = list(satirlar or [])
    out = []
    for kod in seviye_kaynaklari(seviye):
        grup = [s for s in satirlar if s["kaynak"] == kod]
        t = topla(grup)
        out.append({
            "kod": kod, "ad": KAYNAK_ADLARI[kod], "kayit": len({s["kayit"] for s in grup}),
            "dogru": t["toplam_dogru"], "yanlis": t["toplam_yanlis"], "bos": t["toplam_bos"],
            "soru": t["toplam_soru"], "net": t["toplam_net"], "oran": t["oran"],
        })
    return out


def register_metrik(app) -> None:
    """Jinja filtrelerini ve global fonksiyonlarını kaydeder."""
    app.jinja_env.filters["yuzde"] = yuzde_filtre
    app.jinja_env.filters["net"] = net_filtre
    app.jinja_env.globals.update(
        VARSAYILAN_GOTURME=VARSAYILAN_GOTURME,
        hesap_oran=oran,
        hesap_net=net,
        toplu_oran=toplu_oran,
        goster=goster,
    )
