"""Countdown to the selected LGS target day, in Turkey time.

Override with LGS_SINAV_TARIHI=YYYY-MM-DD (empty means awaiting a date).
Set LGS_SINAV_TARIHI_KESIN=1 only after the official date is confirmed.
"""
import os
from datetime import date, datetime, timedelta, timezone

ISTANBUL = timezone(timedelta(hours=3))
PLANLAMA_HEDEFI = "2027-06-13"
AYLAR = ("", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


def lgs_sayac_verisi(now=None):
    now = (now or datetime.now(ISTANBUL)).astimezone(ISTANBUL)
    raw = os.environ.get("LGS_SINAV_TARIHI", PLANLAMA_HEDEFI).strip()
    kesin = os.environ.get("LGS_SINAV_TARIHI_KESIN", "0") == "1"
    try:
        hedef = date.fromisoformat(raw)
    except ValueError:
        return {"durum": "bekleniyor", "yil": now.year + (now.month >= 7)}
    baslangic = datetime.combine(hedef, datetime.min.time(), tzinfo=ISTANBUL)
    kalan = max(0, int((baslangic - now).total_seconds()))
    durum = "bugun" if now.date() == hedef else ("gecti" if now.date() > hedef else "sayiyor")
    return {"durum": durum, "yil": hedef.year, "kesin": kesin,
            "tarih": f"{hedef.day} {AYLAR[hedef.month]} {hedef.year}",
            "hedef": baslangic.isoformat(), "simdi": now.isoformat(),
            "gun": kalan // 86400, "saat": kalan % 86400 // 3600,
            "dakika": kalan % 3600 // 60}
