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


def register_metrik(app) -> None:
    """Jinja filtrelerini ve global fonksiyonlarını kaydeder."""
    app.jinja_env.filters["yuzde"] = yuzde_filtre
    app.jinja_env.filters["net"] = net_filtre
    app.jinja_env.globals.update(
        VARSAYILAN_GOTURME=VARSAYILAN_GOTURME,
        hesap_oran=oran,
        hesap_net=net,
    )
