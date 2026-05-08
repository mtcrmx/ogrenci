"""
database.py
-----------
Veritabani yonetimi + PDF'lerden alinan gercek okul verileri.
Tablolar: ogretmenler, siniflar, ogretmen_sinif, ogrenciler,
          tik_kayitlari, olumlu_davranis, lig
"""

import sqlite3
import os
from datetime import datetime, timedelta

_DATA_DIR = "/data" if os.path.isdir("/data") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DATA_DIR, "ogrenci_takip.db")

# ── Disiplin kriterleri (22 adet) ──────────────────────────────────────────
KRITERLER = [
    ("📚", "Esya Eksikligi"),
    ("⏰", "Gec Kalma"),
    ("🚫", "Saygisizlik"),
    ("📢", "Gurultu / Dersi Bozma"),
    ("📱", "Izinsiz Telefon Kullanimi"),
    ("📝", "Kopya Girisimi"),
    ("🗣️", "Izinsiz Konusma"),
    ("👊", "Arkadasina Zarar Verme"),
    ("📖", "Derse Hazirliksiz Gelme"),
    ("🤬", "Kufur / Uygunsuz Dil"),
    ("🚪", "Izinsiz Sinif Terk"),
    ("🏫", "Okul Esyasina Zarar"),
    ("😤", "Zorbalik / Taciz"),
    ("🤥", "Yalan Soyleme"),
    ("😴", "Derste Uyuma"),
    ("👕", "Kiyafet Yonetmeligi Ihlali"),
    ("💻", "Sosyal Medya / Internet Ihlali"),
    ("🥊", "Kavga / Tartisma"),
    ("📋", "Odev Yapmama"),
    ("✏️", "Not Tutmama"),
    ("🙅", "Dersi Engelleme"),
    ("❓", "Diger"),
]

# ── Olumlu davranis kriterleri (sinif bazli) ───────────────────────────────
OLUMLU_KRITERLER = [
    ("🏆", "Sinif Duzeni"),
    ("🤫", "Ogretmeni Sessiz Bekleme"),
    ("✋", "Soz Isteyerek Konusma"),
    ("📚", "Derse Hazirlikli Gelme"),
    ("🧹", "Sinif Temizligi"),
    ("🤝", "Dayanisma ve Yardimlasmak"),
    ("📖", "Sessiz Okuma Etkinligi"),
    ("🎯", "Gunluk Hedef Tamamlama"),
]

# ── PDF'lerden alinan ogretmen-sinif eslesmeleri ───────────────────────────
_OGRETMEN_SINIF: dict[str, list[str]] = {
    "ADEM AKGUL": ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B"],
    "AYTAC ATMACA": ["6/A", "6/B", "8/A", "8/B"],
    "CANTEKIN KURTOGLU": ["5/A", "5/B", "8/A", "8/B"],
    "CEMIL KUYUMCU": ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "ELIF DEDEOGLU": ["5/A", "6/A", "6/B", "7/B", "8/A", "8/B"],
    "EMINE KILIC": ["5/B", "7/A"],
    "FATMA CAPKULAC": ["5/B", "6/A", "6/B", "7/A"],
    "FUNDA KIRAZ": ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "HAVVA OZDEMIR": ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "IFTARIYE ARSLAN": ["5/A", "5/B", "7/A", "7/B"],
    "MERVE TURKEL": ["6/A", "6/B", "7/A"],
    "METEHAN CUCEN": ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "NESLIHAN CAKMAK": ["5/A", "7/B", "8/A", "8/B"],
    "OZGE KILIC": ["7/A", "7/B", "8/A", "8/B"],
    "SATI ERGIN": ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "YUSUF ERTURK": ["5/A", "5/B", "6/A", "6/B"],
}

_OGRENCILER: dict[str, list[tuple[str, int]]] = {
    "5/A": [
        ("YASEMIN ARDA", 4), ("ELIF NAZ COBAN", 10), ("TOPRAK CELIKEL", 13),
        ("CENNET CAKIR", 14), ("ALPASLAN ALIM", 16), ("ALI DURAN UCAR", 25),
        ("SEYMA CETIN", 30), ("ALPEREN KOROGLU", 33), ("BATUHAN KOROGLU", 46),
        ("BUSE SARIKAYA", 60), ("ELIF KASMER", 68), ("HASAN KAGAN GULEK", 83),
        ("ERDEM BUTUNER", 89), ("MELIKE KASMER", 96), ("MERT BERAT IMAL", 101),
        ("MESUT TUNA ALIM", 103), ("MUHAMMED EMIN ARSLAN", 105),
        ("MUHAMMED YIGIT HELVACI", 107), ("MUSTAFA EMIR ARSLAN", 113),
        ("SEMANUR GULER", 114), ("RECEP EREN CELEBI", 126),
        ("VEYSAL UMUT ARICI", 136), ("YAGIZ KAYRA BARILDAR", 137),
        ("ZEYNEP AZRA BOZKUS", 141), ("SUKRU EREN KIRKICI", 281),
    ],
    "5/B": [
        ("YIGIT EFE KULA", 2), ("EMIR EREN CAKIR", 6), ("AHMET YASIR GUNES", 8),
        ("BATTAL UMUT ACIKGOZ", 20), ("RABIA MEVLUDE TURA", 24),
        ("ALPER TAHA ORAL", 26), ("ALPEREN AKKAYA", 27), ("EZEL TALHA COBAN", 29),
        ("MEHMET FATIH ORUC", 32), ("ARIF EMIR DALDADURMAZ", 39),
        ("BAHRI BERAT KAYA", 44), ("BURAK ATES", 48), ("YUSUF EYMEN KARLI", 52),
        ("ELIF ADA GUNNEC", 67), ("ESLEM CORDUK", 69), ("ESMA NUR ATAK", 74),
        ("EYMEN YUCE", 77), ("HANDAN MINA GUCLU", 82), ("HIRA NUR KARAKAS", 88),
        ("MELIKE OZDIL", 97), ("MIRAY ADA KARADAGLI", 104),
        ("NIZAMETTIN UYSAL", 116), ("SEZGIN SAVAS", 132), ("UMUT VURAL", 133),
        ("VEYSAL EMRE SEN", 135), ("POYRAZ EFE KOLAY", 298),
    ],
    "6/A": [
        ("ZEHRA SARI", 7), ("SEREF CORDUK", 18), ("ADEM EMIR ACAR", 21),
        ("MUHAMMED SALIH IPEK", 34), ("ASLINUR BALCI", 40), ("AHMET SAVAS", 42),
        ("ZEYNEP KESKIN", 43), ("MUSTAFA CINAR CELIKEL", 65), ("EGE ACIKGOZ", 78),
        ("NISA IPEK CORUMLU", 84), ("SEVGI POLAT", 94), ("YUSUF AKCAN", 122),
        ("HASAN ARDA ALIM", 125), ("ONUR CAKMAK", 128), ("MEHMET ZOR", 155),
        ("BERKAY KOCA", 220), ("BEYZA NUR YAMAN", 227), ("EMIR DUMAN", 254),
        ("HACER BETUL YILDIRIM", 268), ("HAZAL NUR SAGIR", 270),
        ("HIRA BUGLEM AYDIN", 271), ("HUSEYIN CANKAL", 272),
        ("KADIR KIRATLI", 277), ("NACIYE NISA ARSLAN", 292), ("POYRAZ OZEK", 299),
    ],
    "6/B": [
        ("ENES AYKAC", 22), ("AHMET BERKAY YURDUSAY", 37), ("OZGUR CIRAK", 76),
        ("BERKAY KOSE", 86), ("YUSUF CAN MUCUK", 99), ("UTKU CAN DALKILIC", 111),
        ("ELIF YILMAZ", 120), ("YIGIT TALHA KARACA", 144), ("BERRA ERDEM", 222),
        ("EMIR EFE SAHIN", 255), ("EREN KULA", 258), ("ESLEM KARAASLAN", 260),
        ("EYMEN CIKRIK", 263), ("FEYZA SARE CAKIR", 266), ("HANIFE CURUK", 269),
        ("HUSEYIN DALKIRAN", 273), ("HUSEYIN EFE TEPEGOZ", 274),
        ("IBRAHIM ODUNCU", 276), ("KUBRA SARI", 279),
        ("MUHAMMED EMIR DALEGMEZ", 285), ("MUSA CAGLAYAN", 287),
        ("MUSTAFA YIGIT UYSAL", 289), ("PELIN NUR SARI", 297), ("RUKIYE KARACA", 301),
    ],
    "7/A": [
        ("ACELYA EMEN", 41), ("ALI BERK AKTAS", 45), ("ATAMAN SEKER", 58),
        ("BELGIN ECE DEDE", 73), ("CIHAT KARAASLAN", 81), ("DOGUKAN AKYOL", 92),
        ("EBRAR SAHIN", 100), ("ELANUR KOSE", 109), ("CINAR AYDAS", 110),
        ("ENES BUGRA ISLER", 115), ("ESMA BETUL ZOBU", 118), ("ESMA RABIA SEN", 119),
        ("EYMEN EFE ARIK", 121), ("KADER URAL", 131), ("HASAN MERT UNLU", 138),
        ("ELANUR ARDOGAN", 149), ("MUHAMMET HASAN ZEYBEK", 158),
        ("MELIKE USTUN", 163), ("MELISA SARIOGLU", 164),
        ("NEHIR NISA COPATLAMAZ", 177), ("RAMAZAN AKTAS", 194), ("ELA SAGLAM", 200),
        ("VEYSEL CAN BEKTAS", 215), ("YAREN KAPLAN", 217),
        ("ZEYNEP IPEK", 223), ("ZEYNEP KOLAY", 224),
    ],
    "7/B": [
        ("MURAT YILDIRIM", 11), ("DAMLA NAZ GENCEL", 12), ("EMINE SERRA KOLAY", 19),
        ("CINAR SAGIR", 38), ("ALI KEKEC", 57), ("AYSENUR SENA CENGELCI", 72),
        ("BERRA NUR DERE", 75), ("EGEHAN ALA", 108), ("FATMA NUR CANDAN", 123),
        ("GULBAHAR IPEKCI", 129), ("HATICE KUBRA GOKGOBEL", 139),
        ("SENA NEHIR SAGIR", 142), ("HUMEYRA SIRIN DELICAN", 143),
        ("HUSEYIN TALHA DERE", 145), ("IBRAHIM ALI DINC", 148),
        ("MUHAMMED YAGIZ KIZMAZ", 167), ("MUSAB YAMAN", 170), ("NEHIR OKUMUS", 181),
        ("OSMAN TAS", 192), ("SELDA ECE GOKCE", 208), ("SEVKET CORDUK", 209),
        ("SEVVAL OZTURK", 211), ("SUHEDA BUGLEM KARASLAN", 212),
        ("YAGMUR NISA KOCA", 216), ("ZEHRA ZEREN", 221), ("ZUMRA KARAKAYA", 225),
    ],
    "8/A": [
        ("ELIF SIMSEK", 15), ("KAYRA KEMELEK", 23), ("EMIRHAN OZDEMIR", 28),
        ("BETUL KOPAR", 51), ("BUSE NAZ KOSE", 54), ("CEYLIN SAHIN", 55),
        ("ESEDULLAH ZALIM", 59), ("MELIKE VURAL", 62), ("MELISA MIS", 63),
        ("IREM SU CORDUK", 64), ("YAREN TIRYAKI", 80), ("MUSTAFA EYMEN ALTUNDAS", 90),
        ("ALI LEKEALMAZ", 91), ("ALI EREN DASCI", 93), ("VEYSEL SEFA KUYUK", 95),
        ("YAGMUR ARICI", 98), ("KUBRA ERCAN", 102), ("CEMILE NISA KUSER", 112),
        ("MAHIR AKYOL", 146), ("ECEHAN SIMSEK", 147), ("MUHAMMED TALHA DIVAN", 162),
        ("HUMEYRA OZTURK", 176), ("ESRA OZTURK", 184), ("YUSUF SUTYEMEZ", 205),
    ],
    "8/B": [
        ("ALAALDIN ERDEN", 5), ("MIRAC ERTURK", 17), ("TUGBA VURAL", 31),
        ("ADEM KEREM MUCU", 36), ("GIZEM NUR COPATLAMAZ", 47), ("BASRI GEDIK", 49),
        ("BERAT BAYRAM", 50), ("BURCU KILIC", 53), ("DEFNE AKKAYA", 56),
        ("YUSUF FIKRET DALKIRAN", 61), ("OMER CAKAR", 70), ("SEFER AHMET ORAL", 71),
        ("ZEHRA KORPES", 85), ("ALPEREN ARMUTCU", 106), ("EBRAR CUKUR", 117),
        ("ESMA NUR CUKUR", 124), ("EFE YIGIT", 127), ("HUSEYIN INCE", 134),
        ("OZGE YILDIZ", 174), ("YUSUF YILDIRIM", 182), ("YUSUF KEMAL PEKER", 204),
        ("MUHAMMED AKTAS", 210),
    ],
}


# ══════════════════════════════════════════════════════════════════════════
# Yardimcilar
# ══════════════════════════════════════════════════════════════════════════

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _bu_hafta_pazartesi() -> str:
    """
    Lig periyodunun baslangic tarihini verir.
    Pazartesi 08:15'ten sonra = bu hafta Pazartesi
    Daha once = gecen hafta Pazartesi
    """
    now = datetime.now()
    gun = now.weekday()  # 0=Pzt
    pzt = now - timedelta(days=gun)
    if gun == 0 and (now.hour, now.minute) < (8, 15):
        pzt -= timedelta(days=7)
    return pzt.strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════════════════
# Baslama + Seed
# ══════════════════════════════════════════════════════════════════════════

def initialize_db():
    con = _conn()
    cur = con.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS ogretmenler (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL UNIQUE,
            sifre    TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS siniflar (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_adi TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS ogretmen_sinif (
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            sinif_id    INTEGER NOT NULL REFERENCES siniflar(id),
            PRIMARY KEY (ogretmen_id, sinif_id)
        );
        CREATE TABLE IF NOT EXISTS ogrenciler (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            ogr_no   INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tik_kayitlari (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id  INTEGER NOT NULL REFERENCES ogrenciler(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            kriter      TEXT NOT NULL,
            tarih       TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS olumlu_davranis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id    INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            kriter      TEXT NOT NULL,
            tarih       TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lig (
            sinif_id   INTEGER PRIMARY KEY REFERENCES siniflar(id),
            puan       INTEGER NOT NULL DEFAULT 0,
            hafta_basi TEXT NOT NULL
        );
    """)
    con.commit()

    # Migration: sifre sutunu
    sutunlar = [r[1] for r in con.execute("PRAGMA table_info(ogretmenler)").fetchall()]
    if "sifre" not in sutunlar:
        con.execute("ALTER TABLE ogretmenler ADD COLUMN sifre TEXT NOT NULL DEFAULT ''")
        con.commit()

    if cur.execute("SELECT COUNT(*) FROM ogretmenler").fetchone()[0] == 0:
        _seed(con)
    else:
        bos = cur.execute("SELECT COUNT(*) FROM ogretmenler WHERE sifre=''").fetchone()[0]
        if bos > 0:
            _sifreleri_ata(con)

    # Kadro ve kart tablolarini baslangicta olustur
    _kadro_tablosu_olustur(con)
    _kart_tablosu_olustur(con)

    con.close()


def _sifre_uret() -> dict[str, str]:
    sirali = sorted(_OGRETMEN_SINIF.keys())
    return {ad: f"EC{100 + i}" for i, ad in enumerate(sirali)}


def _sifreleri_ata(con):
    sm = _sifre_uret()
    for ad, sifre in sm.items():
        con.execute("UPDATE ogretmenler SET sifre=? WHERE ad_soyad=?", (sifre, ad))
    con.commit()


def _seed(con):
    cur = con.cursor()
    sm = _sifre_uret()
    sinif_ids: dict[str, int] = {}
    for s in ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"]:
        cur.execute("INSERT INTO siniflar (sinif_adi) VALUES (?)", (s,))
        sinif_ids[s] = cur.lastrowid

    ogretmen_ids: dict[str, int] = {}
    for ogr in sorted(_OGRETMEN_SINIF.keys()):
        cur.execute("INSERT INTO ogretmenler (ad_soyad, sifre) VALUES (?, ?)",
                    (ogr, sm[ogr]))
        ogretmen_ids[ogr] = cur.lastrowid

    for ogr, siniflar in _OGRETMEN_SINIF.items():
        for s in siniflar:
            cur.execute("INSERT OR IGNORE INTO ogretmen_sinif VALUES (?, ?)",
                        (ogretmen_ids[ogr], sinif_ids[s]))

    for sinif_adi, liste in _OGRENCILER.items():
        sid = sinif_ids[sinif_adi]
        for ad_soyad, ogr_no in liste:
            cur.execute("INSERT INTO ogrenciler (ad_soyad, sinif_id, ogr_no) VALUES (?, ?, ?)",
                        (ad_soyad, sid, ogr_no))
    con.commit()


# ══════════════════════════════════════════════════════════════════════════
# Ogretmen Sorgu / Auth
# ══════════════════════════════════════════════════════════════════════════

def tum_ogretmenler() -> list[dict]:
    con = _conn()
    rows = [dict(r) for r in con.execute(
        "SELECT id, ad_soyad, sifre FROM ogretmenler ORDER BY ad_soyad"
    ).fetchall()]
    con.close()
    return rows


def tum_sifre_listesi() -> list[dict]:
    con = _conn()
    rows = [dict(r) for r in con.execute(
        "SELECT ad_soyad, sifre FROM ogretmenler ORDER BY sifre"
    ).fetchall()]
    con.close()
    return rows


def ogretmen_dogrula(ad_soyad: str, sifre: str) -> bool:
    con = _conn()
    row = con.execute(
        "SELECT id FROM ogretmenler WHERE ad_soyad=? AND sifre=?",
        (ad_soyad, sifre)
    ).fetchone()
    con.close()
    return row is not None


def ogretmen_id_bul(ad_soyad: str):
    con = _conn()
    row = con.execute("SELECT id FROM ogretmenler WHERE ad_soyad=?", (ad_soyad,)).fetchone()
    con.close()
    return row["id"] if row else None


def ogretmen_siniflari(ogretmen_id: int) -> list[dict]:
    con = _conn()
    rows = [dict(r) for r in con.execute("""
        SELECT s.id, s.sinif_adi
        FROM siniflar s
        JOIN ogretmen_sinif os ON os.sinif_id = s.id
        WHERE os.ogretmen_id = ?
        ORDER BY s.sinif_adi
    """, (ogretmen_id,)).fetchall()]
    con.close()
    return rows


# ══════════════════════════════════════════════════════════════════════════
# Ogrenci Sorgulari
# ══════════════════════════════════════════════════════════════════════════

def sinif_ogrencileri(sinif_id: int) -> list[dict]:
    con = _conn()
    rows = [dict(r) for r in con.execute("""
        SELECT o.id, o.ad_soyad, o.ogr_no, s.sinif_adi,
               COUNT(t.id) AS tik_sayisi
        FROM ogrenciler o
        JOIN siniflar s ON s.id = o.sinif_id
        LEFT JOIN tik_kayitlari t ON t.ogrenci_id = o.id
        WHERE o.sinif_id = ?
        GROUP BY o.id
        ORDER BY o.ad_soyad
    """, (sinif_id,)).fetchall()]
    con.close()
    return rows


def tum_okul_ogrencileri() -> list[dict]:
    """Tum siniflardan tum ogrencileri tik sayisina gore sirali getirir."""
    con = _conn()
    rows = [dict(r) for r in con.execute("""
        SELECT o.id, o.ad_soyad, o.ogr_no, s.sinif_adi,
               COUNT(t.id) AS tik_sayisi
        FROM ogrenciler o
        JOIN siniflar s ON s.id = o.sinif_id
        LEFT JOIN tik_kayitlari t ON t.ogrenci_id = o.id
        GROUP BY o.id
        ORDER BY COUNT(t.id) DESC, o.ad_soyad
    """).fetchall()]
    con.close()
    return rows


def ogrenci_tik_gecmisi(ogrenci_id: int) -> list[dict]:
    con = _conn()
    rows = [dict(r) for r in con.execute("""
        SELECT t.kriter, t.tarih, og.ad_soyad AS ogretmen
        FROM tik_kayitlari t
        JOIN ogretmenler og ON og.id = t.ogretmen_id
        WHERE t.ogrenci_id = ?
        ORDER BY t.tarih DESC
    """, (ogrenci_id,)).fetchall()]
    con.close()
    return rows


# ══════════════════════════════════════════════════════════════════════════
# Tik Yazma
# ══════════════════════════════════════════════════════════════════════════

def tik_ekle(ogrenci_id: int, ogretmen_id: int, kriter: str) -> int:
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    con = _conn()
    con.execute(
        "INSERT INTO tik_kayitlari (ogrenci_id, ogretmen_id, kriter, tarih) VALUES (?,?,?,?)",
        (ogrenci_id, ogretmen_id, kriter, tarih)
    )
    con.commit()
    sayi = con.execute(
        "SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id=?", (ogrenci_id,)
    ).fetchone()[0]
    con.close()
    return sayi


def tek_ogrenci_sifirla(ogrenci_id: int):
    con = _conn()
    con.execute("DELETE FROM tik_kayitlari WHERE ogrenci_id=?", (ogrenci_id,))
    con.commit()
    con.close()


def sinif_sifirla(sinif_id: int):
    con = _conn()
    con.execute("""
        DELETE FROM tik_kayitlari
        WHERE ogrenci_id IN (SELECT id FROM ogrenciler WHERE sinif_id=?)
    """, (sinif_id,))
    con.commit()
    con.close()


def tum_tikleri_sifirla():
    con = _conn()
    con.execute("DELETE FROM tik_kayitlari")
    con.commit()
    con.close()


# ══════════════════════════════════════════════════════════════════════════
# Olumlu Davranis + Super Lig
# ══════════════════════════════════════════════════════════════════════════

def olumlu_puan_ekle(sinif_id: int, ogretmen_id: int, kriter: str) -> int:
    """
    Sinifa olumlu davranis puani ekler; haftalik lig tablosunu gunceller.
    Guncel puan dondurulur.
    """
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    hafta = _bu_hafta_pazartesi()
    con = _conn()

    # Gecmis kaydini sakla
    con.execute(
        "INSERT INTO olumlu_davranis (sinif_id, ogretmen_id, kriter, tarih) VALUES (?,?,?,?)",
        (sinif_id, ogretmen_id, kriter, tarih)
    )

    # Lig satiri var mi?
    mevcut = con.execute("SELECT puan, hafta_basi FROM lig WHERE sinif_id=?",
                         (sinif_id,)).fetchone()
    if not mevcut:
        con.execute("INSERT INTO lig (sinif_id, puan, hafta_basi) VALUES (?,1,?)",
                    (sinif_id, hafta))
        puan = 1
    elif mevcut["hafta_basi"] != hafta:
        # Yeni hafta — sifirdan baslat
        con.execute("UPDATE lig SET puan=1, hafta_basi=? WHERE sinif_id=?",
                    (hafta, sinif_id))
        puan = 1
    else:
        con.execute("UPDATE lig SET puan=puan+1 WHERE sinif_id=?", (sinif_id,))
        puan = mevcut["puan"] + 1

    # Olumlu davranis puani ayni zamanda mac puan tablosuna da 1 puan ekler
    tablo_var = con.execute(
        "SELECT sinif_id FROM lig_mac_tablo WHERE sinif_id=?", (sinif_id,)
    ).fetchone()
    if tablo_var:
        con.execute(
            "UPDATE lig_mac_tablo SET puan = puan + 1, ag = ag + 1 WHERE sinif_id=?",
            (sinif_id,)
        )
    else:
        con.execute(
            "INSERT INTO lig_mac_tablo (sinif_id, galibiyet, beraberlik, maglubiyet, puan, ag) "
            "VALUES (?, 0, 0, 0, 1, 1)",
            (sinif_id,)
        )

    con.commit()
    con.close()
    return puan


def lig_siralama() -> list[dict]:
    """
    Tum siniflari bu haftalik olumlu puana gore sirali dondurur.
    Yeni hafta kontrolu yapar; eskimis kayitlari sifirlar.
    """
    hafta = _bu_hafta_pazartesi()
    con = _conn()

    # Eskimis satir varsa sifirla
    con.execute("UPDATE lig SET puan=0, hafta_basi=? WHERE hafta_basi != ?",
                (hafta, hafta))
    con.commit()

    rows = [dict(r) for r in con.execute("""
        SELECT s.id AS sinif_id, s.sinif_adi,
               COALESCE(l.puan, 0) AS puan,
               COALESCE(l.hafta_basi, ?) AS hafta_basi
        FROM siniflar s
        LEFT JOIN lig l ON l.sinif_id = s.id
        ORDER BY COALESCE(l.puan, 0) DESC, s.sinif_adi
    """, (hafta,)).fetchall()]
    con.close()
    return rows


def lig_manuel_sifirla():
    """Tum siniflarin lig puanini sifirlar."""
    hafta = _bu_hafta_pazartesi()
    con = _conn()
    con.execute("UPDATE lig SET puan=0, hafta_basi=?", (hafta,))
    con.commit()
    con.close()


# ══════════════════════════════════════════════════════════════════════════
# Super Lig Mac Sistemi
# ══════════════════════════════════════════════════════════════════════════

LIG_GOREVLER = [
    "Siradaki Dersin Odevleri Tam Yapilmasi",
    "Derse Hazirlikli Gelme (Kitap, Defter, Kalem)",
    "Sinif Duzeni ve Tam Sessizlik",
    "Soz Isteyerek Konusma",
    "Tum Materyallerin Eksiksiz Olmasi",
    "Derse Aktif Katilim ve Soru Sorma",
    "Sorulara Dogru Cevap Verme",
    "Sinif Temizligi ve Duzeni",
    "Ogretmeni Sessizce ve Saygili Dinleme",
    "Zamaninda ve Hazir Sinifa Girme",
    "Grup Calismasi ve Uyum",
    "Gunluk Odev Eksiksiz Tamamlama",
    "Kiyafet Yonetmeligi Tam Uyumu",
    "Performans Gorevi Basariyla Tamamlama",
    "Akran Ogretimi Basarisi",
    "Gunun Ozeti Duzgun Yazilmasi",
]

# Var incelemesi hakemi ogretmenler (alfabetik siraya gore ID bulunur)
VAR_INCELEME_OGRETMENLER = ["ADEM AKGUL", "YUSUF ERTURK"]


def _mac_tablosu_olustur(con):
    """Lig mac tablolari yoksa olusturur."""
    con.executescript("""
        CREATE TABLE IF NOT EXISTS lig_maclar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif1_id   INTEGER NOT NULL REFERENCES siniflar(id),
            sinif2_id   INTEGER NOT NULL REFERENCES siniflar(id),
            gorev       TEXT NOT NULL,
            tarih       TEXT NOT NULL,
            seans       TEXT NOT NULL DEFAULT 'sabah',
            s1_tamamlayan INTEGER DEFAULT NULL,
            s1_toplam     INTEGER DEFAULT NULL,
            s2_tamamlayan INTEGER DEFAULT NULL,
            s2_toplam     INTEGER DEFAULT NULL,
            kazanan_id  INTEGER DEFAULT NULL REFERENCES siniflar(id),
            durum       TEXT NOT NULL DEFAULT 'bekliyor'
        );
        CREATE TABLE IF NOT EXISTS lig_oylari (
            mac_id      INTEGER NOT NULL REFERENCES lig_maclar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            secilen_id  INTEGER NOT NULL REFERENCES siniflar(id),
            PRIMARY KEY (mac_id, ogretmen_id)
        );
        CREATE TABLE IF NOT EXISTS lig_mac_tablo (
            sinif_id    INTEGER PRIMARY KEY REFERENCES siniflar(id),
            galibiyet   INTEGER DEFAULT 0,
            beraberlik  INTEGER DEFAULT 0,
            maglubiyet  INTEGER DEFAULT 0,
            puan        INTEGER DEFAULT 0,
            ag          INTEGER DEFAULT 0
        );
    """)
    con.commit()


def gunluk_mac_olustur() -> list[dict]:
    """
    Bugunun maclarini olusturur (yoksa).
    4 sabah + 4 ogleden sonra revans = 8 mac.
    Dondurur: bugunun tum maclarini.
    """
    import random
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn()
    _mac_tablosu_olustur(con)

    # Zaten olusturulmus mu?
    mevcut = con.execute(
        "SELECT COUNT(*) FROM lig_maclar WHERE tarih=?", (bugun,)
    ).fetchone()[0]
    if mevcut > 0:
        con.close()
        return bugun_maclar()

    # Tum siniflari al ve karistir
    siniflar = [dict(r) for r in con.execute(
        "SELECT id, sinif_adi FROM siniflar ORDER BY sinif_adi"
    ).fetchall()]
    random.shuffle(siniflar)

    # Cift sayida sinif garanti et
    if len(siniflar) % 2 != 0:
        siniflar = siniflar[:-1]

    esler = [(siniflar[i], siniflar[i+1]) for i in range(0, len(siniflar), 2)]

    gorevler = random.sample(LIG_GOREVLER, min(len(esler), len(LIG_GOREVLER)))
    while len(gorevler) < len(esler):
        gorevler += random.sample(LIG_GOREVLER, min(len(esler)-len(gorevler), len(LIG_GOREVLER)))

    # Sabah maclari
    for i, (s1, s2) in enumerate(esler):
        con.execute("""
            INSERT INTO lig_maclar
            (sinif1_id, sinif2_id, gorev, tarih, seans)
            VALUES (?, ?, ?, ?, 'sabah')
        """, (s1["id"], s2["id"], gorevler[i], bugun))

    # Ogleden sonra revans (ekipler tersine, yeni gorev)
    gorevler2 = random.sample(LIG_GOREVLER, min(len(esler), len(LIG_GOREVLER)))
    while len(gorevler2) < len(esler):
        gorevler2 += random.sample(LIG_GOREVLER, min(len(esler)-len(gorevler2), len(LIG_GOREVLER)))

    for i, (s1, s2) in enumerate(esler):
        con.execute("""
            INSERT INTO lig_maclar
            (sinif1_id, sinif2_id, gorev, tarih, seans)
            VALUES (?, ?, ?, ?, 'ogleden_sonra')
        """, (s2["id"], s1["id"], gorevler2[i], bugun))  # Revans: ekipler yer degisti

    con.commit()
    con.close()
    return bugun_maclar()


def bugun_maclar() -> list[dict]:
    """Bugunku maclari sinif adlariyla ve kart ozeti ile dondurur."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn()
    _mac_tablosu_olustur(con)
    _kart_tablosu_olustur(con)
    rows  = [dict(r) for r in con.execute("""
        SELECT m.*,
               s1.sinif_adi AS sinif1_adi,
               s2.sinif_adi AS sinif2_adi,
               kz.sinif_adi AS kazanan_adi
        FROM lig_maclar m
        JOIN siniflar s1 ON s1.id = m.sinif1_id
        JOIN siniflar s2 ON s2.id = m.sinif2_id
        LEFT JOIN siniflar kz ON kz.id = m.kazanan_id
        WHERE m.tarih = ?
        ORDER BY m.seans DESC, m.id
    """, (bugun,)).fetchall()]

    # Her mac icin kart ozetini ekle
    for row in rows:
        kartlar = [dict(r) for r in con.execute("""
            SELECT k.kart_turu, o.ad_soyad AS ogrenci_adi, s.sinif_adi
            FROM kart_kayitlari k
            JOIN ogrenciler o ON o.id = k.ogrenci_id
            JOIN siniflar s ON s.id = k.sinif_id
            WHERE k.mac_id = ?
            ORDER BY k.tarih
        """, (row["id"],)).fetchall()]
        row["kartlar"] = kartlar

    con.close()
    return rows


def mac_detay(mac_id: int) -> dict | None:
    con  = _conn()
    _mac_tablosu_olustur(con)
    row  = con.execute("""
        SELECT m.*,
               s1.sinif_adi AS sinif1_adi,
               s2.sinif_adi AS sinif2_adi,
               kz.sinif_adi AS kazanan_adi
        FROM lig_maclar m
        JOIN siniflar s1 ON s1.id = m.sinif1_id
        JOIN siniflar s2 ON s2.id = m.sinif2_id
        LEFT JOIN siniflar kz ON kz.id = m.kazanan_id
        WHERE m.id = ?
    """, (mac_id,)).fetchone()
    if not row:
        con.close()
        return None
    d = dict(row)

    # Oylar
    oylar = [dict(r) for r in con.execute("""
        SELECT oy.secilen_id, og.ad_soyad AS ogretmen, s.sinif_adi
        FROM lig_oylari oy
        JOIN ogretmenler og ON og.id = oy.ogretmen_id
        JOIN siniflar s ON s.id = oy.secilen_id
        WHERE oy.mac_id = ?
    """, (mac_id,)).fetchall()]
    d["oylar"] = oylar

    # Hakem ogretmenler
    hakemler = []
    for ad in VAR_INCELEME_OGRETMENLER:
        r = con.execute("SELECT id FROM ogretmenler WHERE ad_soyad=?", (ad,)).fetchone()
        if r:
            oy = con.execute(
                "SELECT secilen_id FROM lig_oylari WHERE mac_id=? AND ogretmen_id=?",
                (mac_id, r["id"])
            ).fetchone()
            hakemler.append({"ad": ad, "id": r["id"],
                              "oy_verildi": oy["secilen_id"] if oy else None})
    d["hakemler"] = hakemler
    con.close()
    return d


def mac_sonucu_gir(mac_id: int,
                   s1_tamamlayan: int, s1_toplam: int,
                   s2_tamamlayan: int, s2_toplam: int) -> dict:
    """
    Mac sonucunu girer, kazanani belirler.
    Dondurur: {"durum": ..., "kazanan_id": ...}
    """
    con = _conn()
    _mac_tablosu_olustur(con)
    mac = dict(con.execute("SELECT * FROM lig_maclar WHERE id=?", (mac_id,)).fetchone())

    oran1 = s1_tamamlayan / s1_toplam if s1_toplam > 0 else 0
    oran2 = s2_tamamlayan / s2_toplam if s2_toplam > 0 else 0

    if oran1 > oran2:
        durum     = "tamamlandi"
        kazanan   = mac["sinif1_id"]
        kaybeden  = mac["sinif2_id"]
    elif oran2 > oran1:
        durum     = "tamamlandi"
        kazanan   = mac["sinif2_id"]
        kaybeden  = mac["sinif1_id"]
    else:
        durum     = "var_incelemesi"
        kazanan   = None
        kaybeden  = None

    con.execute("""
        UPDATE lig_maclar SET
            s1_tamamlayan=?, s1_toplam=?,
            s2_tamamlayan=?, s2_toplam=?,
            kazanan_id=?, durum=?
        WHERE id=?
    """, (s1_tamamlayan, s1_toplam, s2_tamamlayan, s2_toplam,
          kazanan, durum, mac_id))

    if durum == "tamamlandi":
        _puan_guncelle(con, kazanan, kaybeden)

    con.commit()
    con.close()
    return {"durum": durum, "kazanan_id": kazanan}


def mac_oy_ver(mac_id: int, ogretmen_id: int, secilen_sinif_id: int) -> dict:
    """
    Var incelemesinde oy kullanir.
    Her iki hakem oyunu verince kazanani belirler.
    """
    con = _conn()
    _mac_tablosu_olustur(con)

    con.execute("""
        INSERT OR REPLACE INTO lig_oylari (mac_id, ogretmen_id, secilen_id)
        VALUES (?, ?, ?)
    """, (mac_id, ogretmen_id, secilen_sinif_id))
    con.commit()

    # Tum hakemler oy verdi mi?
    hakem_idler = []
    for ad in VAR_INCELEME_OGRETMENLER:
        r = con.execute("SELECT id FROM ogretmenler WHERE ad_soyad=?", (ad,)).fetchone()
        if r:
            hakem_idler.append(r["id"])

    oylar = [dict(r) for r in con.execute(
        "SELECT ogretmen_id, secilen_id FROM lig_oylari WHERE mac_id=?", (mac_id,)
    ).fetchall()]

    verilen_ids = {o["ogretmen_id"] for o in oylar}
    sonuc = {"durum": "bekleniyor", "kazanan_id": None}

    if all(h in verilen_ids for h in hakem_idler):
        mac = dict(con.execute("SELECT * FROM lig_maclar WHERE id=?", (mac_id,)).fetchone())
        # Oy sayimı
        s1_oy = sum(1 for o in oylar if o["secilen_id"] == mac["sinif1_id"])
        s2_oy = sum(1 for o in oylar if o["secilen_id"] == mac["sinif2_id"])

        if s1_oy > s2_oy:
            kazanan = mac["sinif1_id"]; kaybeden = mac["sinif2_id"]
        elif s2_oy > s1_oy:
            kazanan = mac["sinif2_id"]; kaybeden = mac["sinif1_id"]
        else:
            # Hala beraberlik → ilk hakem (ADEM AKGUL) karar verir
            ilk_hakem = hakem_idler[0] if hakem_idler else None
            ilk_oy    = next((o["secilen_id"] for o in oylar
                              if o["ogretmen_id"] == ilk_hakem), None)
            kazanan   = ilk_oy or mac["sinif1_id"]
            kaybeden  = mac["sinif2_id"] if kazanan == mac["sinif1_id"] else mac["sinif1_id"]

        con.execute("""
            UPDATE lig_maclar SET kazanan_id=?, durum='tamamlandi' WHERE id=?
        """, (kazanan, mac_id))
        _puan_guncelle(con, kazanan, kaybeden)
        con.commit()
        sonuc = {"durum": "tamamlandi", "kazanan_id": kazanan}

    con.close()
    return sonuc


def _puan_guncelle(con, kazanan_id, kaybeden_id):
    """Kazanana 3 puan, kaybedenin kayibini gunceller."""
    for sid in [kazanan_id, kaybeden_id]:
        if not con.execute("SELECT 1 FROM lig_mac_tablo WHERE sinif_id=?", (sid,)).fetchone():
            con.execute("INSERT INTO lig_mac_tablo (sinif_id) VALUES (?)", (sid,))

    con.execute("""
        UPDATE lig_mac_tablo SET galibiyet=galibiyet+1, puan=puan+3, ag=ag+1
        WHERE sinif_id=?
    """, (kazanan_id,))
    con.execute("""
        UPDATE lig_mac_tablo SET maglubiyet=maglubiyet+1
        WHERE sinif_id=?
    """, (kaybeden_id,))


def lig_puan_tablosu() -> list[dict]:
    """Puan tablosunu dondurur."""
    con  = _conn()
    _mac_tablosu_olustur(con)
    rows = [dict(r) for r in con.execute("""
        SELECT s.id AS sinif_id, s.sinif_adi,
               COALESCE(t.galibiyet,0) AS galibiyet,
               COALESCE(t.beraberlik,0) AS beraberlik,
               COALESCE(t.maglubiyet,0) AS maglubiyet,
               COALESCE(t.puan,0) AS puan,
               COALESCE(t.ag,0) AS ag
        FROM siniflar s
        LEFT JOIN lig_mac_tablo t ON t.sinif_id = s.id
        ORDER BY COALESCE(t.puan,0) DESC, COALESCE(t.ag,0) DESC, s.sinif_adi
    """).fetchall()]
    con.close()
    return rows


def lig_mac_tablo_sifirla():
    """Mac puan tablosunu ve maclarini sifirlar (sezon basi)."""
    con = _conn()
    _mac_tablosu_olustur(con)
    con.execute("DELETE FROM lig_oylari")
    con.execute("DELETE FROM lig_maclar")
    con.execute("DELETE FROM lig_mac_tablo")
    con.commit()
    con.close()


# ══════════════════════════════════════════════════════════════════════════
# Kadro Sistemi
# ══════════════════════════════════════════════════════════════════════════

MEVKILER = [
    (1,  "⭐", "Takim Kaptani"),
    (2,  "🎖️", "Kaptan Yardimcisi"),
    (3,  "🧤", "Kaleci"),
    (4,  "🧹", "Libero (Supurucu)"),
    (5,  "➡️", "Sag Bek"),
    (6,  "⬅️", "Sol Bek"),
    (7,  "🛡️", "Stoper"),
    (8,  "🔒", "Sigorta Oyuncusu"),
    (9,  "⚡", "On Libero"),
    (10, "🎩", "Oyun Kurucu (10 Numara)"),
    (11, "🏃", "Sag Kanat"),
    (12, "💨", "Sol Kanat"),
    (13, "⚙️", "Dinamo"),
    (14, "🚂", "Istasyon Oyuncusu"),
    (15, "🎯", "Santrafor (Golcu)"),
    (16, "🦊", "Gizli Forvet"),
    (17, "🐆", "Firsatci Golcu"),
    (18, "🌪️", "Kanat Forvet"),
    (19, "💪", "Kondisyoner"),
    (20, "📊", "Analiz Uzmani"),
    (21, "🎙️", "Basin Sozcusu"),
    (22, "🎒", "Malzemeci"),
    (23, "🕊️", "Fair-Play Elcisi"),
]


def _kadro_tablosu_olustur(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS kadro_ogrenci (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id   INTEGER NOT NULL REFERENCES siniflar(id),
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            mevki_no   INTEGER NOT NULL,
            UNIQUE(sinif_id, ogrenci_id)
        )
    """)
    con.commit()


def sinif_kadro_olustur(sinif_id: int) -> list[dict]:
    """
    Sinifin kadrosunu rastgele olusturur (yoksa).
    Her ogrenciye bir mevki atanir.
    Dondurur: kadro listesi.
    """
    import random
    con = _conn()
    _kadro_tablosu_olustur(con)

    # Zaten varsa sil ve yeniden olustur (yenile butonu icin)
    con.execute("DELETE FROM kadro_ogrenci WHERE sinif_id=?", (sinif_id,))

    ogrenciler = [dict(r) for r in con.execute(
        "SELECT id, ad_soyad, ogr_no FROM ogrenciler WHERE sinif_id=? ORDER BY ogr_no",
        (sinif_id,)
    ).fetchall()]

    # Mevkileri karistir ve ogrenci sayisina gore kes/uzat
    mevki_liste = list(MEVKILER)
    random.shuffle(mevki_liste)

    # Ogrenci sayisi > mevki sayisi olabilir, dongu yap
    for i, ogr in enumerate(ogrenciler):
        mevki = mevki_liste[i % len(mevki_liste)]
        con.execute("""
            INSERT OR IGNORE INTO kadro_ogrenci (sinif_id, ogrenci_id, mevki_no)
            VALUES (?, ?, ?)
        """, (sinif_id, ogr["id"], mevki[0]))

    con.commit()
    con.close()
    return sinif_kadro_getir(sinif_id)


def sinif_kadro_getir(sinif_id: int) -> list[dict]:
    """Sinifin kadrosunu mevki siraliyla dondurur."""
    con = _conn()
    _kadro_tablosu_olustur(con)

    # Yoksa otomatik olustur
    sayi = con.execute(
        "SELECT COUNT(*) FROM kadro_ogrenci WHERE sinif_id=?", (sinif_id,)
    ).fetchone()[0]
    if sayi == 0:
        con.close()
        return sinif_kadro_olustur(sinif_id)

    rows = [dict(r) for r in con.execute("""
        SELECT k.mevki_no, o.ad_soyad, o.ogr_no
        FROM kadro_ogrenci k
        JOIN ogrenciler o ON o.id = k.ogrenci_id
        WHERE k.sinif_id = ?
        ORDER BY k.mevki_no
    """, (sinif_id,)).fetchall()]
    con.close()

    # Mevki bilgisini ekle
    mevki_map = {m[0]: (m[1], m[2]) for m in MEVKILER}
    for r in rows:
        m = mevki_map.get(r["mevki_no"], ("❓", "Bilinmeyen Mevki"))
        r["emoji"]  = m[0]
        r["mevki"]  = m[1]
    return rows


def tum_siniflar_kadro() -> dict[int, list[dict]]:
    """Tum siniflarin kadrolarini dondurur. {sinif_id: [kadro]}"""
    con = _conn()
    siniflar = [dict(r) for r in con.execute(
        "SELECT id FROM siniflar"
    ).fetchall()]
    con.close()
    return {s["id"]: sinif_kadro_getir(s["id"]) for s in siniflar}


# ══════════════════════════════════════════════════════════════════════════
# Kart Sistemi (Sari / Kirmizi)
# ══════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════
# Gamification Sabitleri
# ══════════════════════════════════════════════════════════════════════════

SEVIYELER = [
    (0,   "🥚", "Yumurta"),
    (10,  "🐣", "Civciv"),
    (25,  "🦅", "Kartal"),
    (50,  "🦁", "Aslan"),
    (100, "👑", "Efsane"),
]

# Sadece bu öğretmenler gizli müfettiş öğrencisini belirleyebilir
MUFETTIS_YETKILILERI = ["Adem Akgül", "Yusuf Ertürk"]

ROZET_TANIMI = {
    "temizlik_7":     ("🧹", "Tertemiz",          "7 gun hic tik almadi"),
    "sinif_yildizi":  ("⭐", "Sinif Yildizi",      "Haftanin en cok olumlu puanli ogrencisi"),
    "seri_yildiz":    ("⚡", "Seri Yildiz",        "3 mac ust uste kazanildi"),
    "donusum":        ("🦋", "Donusum",             "Kirmizi karttan sonra 5 gun temiz kalindi"),
    "mufettis_iyisi": ("🕵️","Muazzam Performans", "Gizli mufettis degerlendirmesi: Mukemmel"),
    "alkis_efsane":   ("👏", "Alkis Efsanesi",     "5 alkis kuponu kazanildi"),
    "streak_10":      ("🔥", "Alevli Seri",        "10 gun kesintisiz temiz"),
    "sezon_zirvesi":  ("🏆", "Sezon Zirvesi",      "Sezon birincisi"),
}

GUNLUK_GOREV_LISTESI = [
    ("Ogretmen sinifa girdiginde herkes oturuyorsa", 3),
    ("Bugun hic gec kalan yoksa", 5),
    ("Teneffuste koridor temiz birakilirsa", 3),
    ("Ders zili caldiktan 30 sn icinde herkes yerine gecerse", 4),
    ("Tum odevler tamamlanmissa", 5),
    ("Giris ve cikista duzgun sirada yururlerse", 3),
    ("Ogretmene gunu boyunca hic soz kesilmezse", 4),
    ("Sinif temizligini gonullulukle yaparlarsa", 4),
    ("Yoklamada herkes sesini net duyurursa", 2),
    ("Bir arkadasa yardim edenine tanik olunursa", 3),
    ("Herkes kitabini/defterini getirmisse", 3),
    ("Lavabo ziyaretleri duzenliyse", 2),
    ("Teneffuste hic kavga/itisma olmadiysa", 5),
    ("Sinif temsilcisi gorevini eksiksiz yaparsa", 3),
    ("Geri donusume katki saglanirsa", 4),
]

ITTIFAK_GOREV_LISTESI = [
    "Birbirlerine birer konu anlatiyor — ortak ogrenme",
    "Ortak koridoru birlikte temizliyor",
    "Birbirlerinin derslerine misafir ogrenci gonderiyor",
    "Ortak kitap okuma suresi duzenleniyor",
    "Birbirlerine tesvik notu yaziyor",
    "Okulun bir alanini birlikte duzenliyor",
    "Ortak proje hazirlayip sergiliyor",
]

SANS_CARKI_SEENEKLERI = [
    ("+1 Bonus Puan",         1,  "#22c55e"),
    ("+3 Bonus Puan",         3,  "#16a34a"),
    ("+5 SUPER Puan!",        5,  "#f59e0b"),
    ("Rakipten 1 Puan Al",   -1,  "#ef4444"),
    ("Sifir — Iyi Sanslar!",  0,  "#64748b"),
    ("+2 Bonus Puan",         2,  "#3b82f6"),
    ("JACKPOT +10!",         10,  "#fbbf24"),
    ("-1 Puan — Kader!",     -1,  "#dc2626"),
]

KART_NEDENLERI = [
    "Rakip takimi manipule etme",
    "Hakaret veya kaba dil",
    "Oyunu bozma / sabotaj",
    "Kurallari ihlal etme",
    "Hakeme saygisizlik",
    "Hileli davranis",
    "Kopya / hile",
    "Diger kuralihlali",
]


def _kart_tablosu_olustur(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS kart_kayitlari (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_id      INTEGER NOT NULL REFERENCES lig_maclar(id),
            ogrenci_id  INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id    INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            kart_turu   TEXT NOT NULL CHECK(kart_turu IN ('sari','kirmizi')),
            neden       TEXT NOT NULL DEFAULT 'Kural ihlali',
            tarih       TEXT NOT NULL
        )
    """)
    con.commit()


def kart_ver(mac_id: int, ogrenci_id: int, sinif_id: int,
             ogretmen_id: int, kart_turu: str, neden: str = "Kural ihlali") -> dict:
    """
    Oyuncuya kart gosterir.
    - Sari  kart : 3 olumsuz tik
    - Kirmizi kart: 6 olumsuz tik + takima -3 puan
    """
    con = _conn()
    _kart_tablosu_olustur(con)
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")

    con.execute("""
        INSERT INTO kart_kayitlari
            (mac_id, ogrenci_id, sinif_id, ogretmen_id, kart_turu, neden, tarih)
        VALUES (?,?,?,?,?,?,?)
    """, (mac_id, ogrenci_id, sinif_id, ogretmen_id, kart_turu, neden, tarih))
    con.commit()
    con.close()

    # Tik ekle
    kriter     = f"{'Sari' if kart_turu == 'sari' else 'Kirmizi'} Kart - {neden}"
    tik_sayisi = 3 if kart_turu == "sari" else 6
    for _ in range(tik_sayisi):
        tik_ekle(ogrenci_id, ogretmen_id, kriter)

    sonuc = {"kart_turu": kart_turu, "tik_eklendi": tik_sayisi, "puan_cezasi": 0}

    # Kirmizi kart: takima -3 puan (sifirin altina dusmez)
    if kart_turu == "kirmizi":
        con = _conn()
        _mac_tablosu_olustur(con)
        con.execute("""
            UPDATE lig_mac_tablo
            SET puan = MAX(0, puan - 3),
                ag   = ag - 3
            WHERE sinif_id = ?
        """, (sinif_id,))
        # Satir yoksa olustur (sifirdan baslat, ceza dogal olarak gosterilmez)
        var = con.execute(
            "SELECT sinif_id FROM lig_mac_tablo WHERE sinif_id=?", (sinif_id,)
        ).fetchone()
        if not var:
            con.execute(
                "INSERT INTO lig_mac_tablo (sinif_id, puan, ag) VALUES (?,0,-3)",
                (sinif_id,)
            )
        con.commit()
        con.close()
        sonuc["puan_cezasi"] = 3

    return sonuc


def mac_kartlari(mac_id: int) -> list[dict]:
    """Bir mactaki tum kart kayitlarini dondurur."""
    con = _conn()
    _kart_tablosu_olustur(con)
    rows = [dict(r) for r in con.execute("""
        SELECT k.id, k.kart_turu, k.neden, k.tarih,
               o.ad_soyad AS ogrenci_adi,
               s.sinif_adi,
               og.ad_soyad AS ogretmen_adi
        FROM kart_kayitlari k
        JOIN ogrenciler o  ON o.id  = k.ogrenci_id
        JOIN siniflar s    ON s.id  = k.sinif_id
        JOIN ogretmenler og ON og.id = k.ogretmen_id
        WHERE k.mac_id = ?
        ORDER BY k.tarih
    """, (mac_id,)).fetchall()]
    con.close()
    return rows


def sinif_olumlu_gecmis(sinif_id: int) -> list[dict]:
    con = _conn()
    rows = [dict(r) for r in con.execute("""
        SELECT od.kriter, od.tarih, og.ad_soyad AS ogretmen
        FROM olumlu_davranis od
        JOIN ogretmenler og ON og.id = od.ogretmen_id
        WHERE od.sinif_id = ?
        ORDER BY od.tarih DESC
        LIMIT 30
    """, (sinif_id,)).fetchall()]
    con.close()
    return rows


# ══════════════════════════════════════════════════════════════════════════
# Gamification — Yardimci
# ══════════════════════════════════════════════════════════════════════════

def _gami_init(con):
    """Tum gamification tablolarini olusturur."""
    con.executescript("""
        CREATE TABLE IF NOT EXISTS rozet_kayitlari (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER REFERENCES ogrenciler(id),
            sinif_id   INTEGER REFERENCES siniflar(id),
            rozet_kodu TEXT NOT NULL,
            tarih      TEXT NOT NULL,
            UNIQUE(ogrenci_id, rozet_kodu)
        );
        CREATE TABLE IF NOT EXISTS sinif_rozet (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id   INTEGER REFERENCES siniflar(id),
            rozet_kodu TEXT NOT NULL,
            tarih      TEXT NOT NULL,
            UNIQUE(sinif_id, rozet_kodu)
        );
        CREATE TABLE IF NOT EXISTS sinif_seri (
            sinif_id      INTEGER PRIMARY KEY REFERENCES siniflar(id),
            guncel_seri   INTEGER DEFAULT 0,
            en_uzun_seri  INTEGER DEFAULT 0,
            son_guncelleme TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS gunluk_gorev (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih           TEXT NOT NULL UNIQUE,
            gorev           TEXT NOT NULL,
            puan            INTEGER NOT NULL DEFAULT 3,
            tamamlayan_ids  TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS gizli_mufettis (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih      TEXT NOT NULL UNIQUE,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id   INTEGER NOT NULL REFERENCES siniflar(id),
            sonuc      TEXT DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS alkis_kuponu (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id  INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id    INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            mesaj       TEXT DEFAULT 'Harika is!',
            tarih       TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sezon_puan (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            puan     INTEGER DEFAULT 0,
            sezon    TEXT NOT NULL DEFAULT '2025-2026'
        );
        CREATE TABLE IF NOT EXISTS ittifak_gorev (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih     TEXT NOT NULL,
            sinif1_id INTEGER NOT NULL REFERENCES siniflar(id),
            sinif2_id INTEGER NOT NULL REFERENCES siniflar(id),
            gorev     TEXT NOT NULL,
            durum     TEXT NOT NULL DEFAULT 'bekliyor',
            puan      INTEGER NOT NULL DEFAULT 5
        );
        CREATE TABLE IF NOT EXISTS sans_carki (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_id    INTEGER REFERENCES lig_maclar(id),
            sinif_id  INTEGER NOT NULL REFERENCES siniflar(id),
            sonuc     TEXT NOT NULL,
            puan_deg  INTEGER DEFAULT 0,
            tarih     TEXT NOT NULL
        );
    """)
    con.commit()


# ── Seviye ────────────────────────────────────────────────────────────────

def sinif_seviye_hesapla(puan: int) -> dict:
    seviye = SEVIYELER[0]
    for s in SEVIYELER:
        if puan >= s[0]:
            seviye = s
    sonraki = None
    for s in SEVIYELER:
        if s[0] > puan:
            sonraki = s
            break
    return {
        "emoji": seviye[1], "ad": seviye[2], "esik": seviye[0],
        "sonraki_emoji": sonraki[1] if sonraki else "✅",
        "sonraki_ad":    sonraki[2] if sonraki else "Zirve",
        "sonraki_esik":  sonraki[0] if sonraki else puan,
    }


def tum_sinif_seviyeleri() -> list[dict]:
    tablo = lig_puan_tablosu()
    result = []
    for s in tablo:
        sev = sinif_seviye_hesapla(s["puan"])
        result.append({**s, **sev})
    return result


# ── Rozet ────────────────────────────────────────────────────────────────

def rozet_ver_ogrenci(ogrenci_id: int, sinif_id: int, rozet_kodu: str) -> bool:
    con = _conn(); _gami_init(con)
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    con.execute("INSERT OR IGNORE INTO rozet_kayitlari (ogrenci_id,sinif_id,rozet_kodu,tarih) VALUES(?,?,?,?)",
                (ogrenci_id, sinif_id, rozet_kodu, tarih))
    yeni = con.total_changes > 0
    con.commit(); con.close()
    return yeni


def rozet_ver_sinif(sinif_id: int, rozet_kodu: str) -> bool:
    con = _conn(); _gami_init(con)
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    con.execute("INSERT OR IGNORE INTO sinif_rozet (sinif_id,rozet_kodu,tarih) VALUES(?,?,?)",
                (sinif_id, rozet_kodu, tarih))
    yeni = con.total_changes > 0
    con.commit(); con.close()
    return yeni


def son_rozetler(limit: int = 30) -> list[dict]:
    con = _conn(); _gami_init(con)
    rows = []
    # Ogrenci rozetleri
    for r in con.execute("""
        SELECT rk.rozet_kodu, rk.tarih, o.ad_soyad AS sahip, s.sinif_adi, 'ogrenci' AS tip
        FROM rozet_kayitlari rk
        JOIN ogrenciler o ON o.id = rk.ogrenci_id
        JOIN siniflar s ON s.id = rk.sinif_id
        ORDER BY rk.tarih DESC LIMIT ?
    """, (limit,)).fetchall():
        d = dict(r)
        kod = d["rozet_kodu"]
        if kod in ROZET_TANIMI:
            d["emoji"] = ROZET_TANIMI[kod][0]
            d["rozet_adi"] = ROZET_TANIMI[kod][1]
        rows.append(d)
    # Sinif rozetleri
    for r in con.execute("""
        SELECT sr.rozet_kodu, sr.tarih, s.sinif_adi AS sahip, s.sinif_adi, 'sinif' AS tip
        FROM sinif_rozet sr
        JOIN siniflar s ON s.id = sr.sinif_id
        ORDER BY sr.tarih DESC LIMIT ?
    """, (limit,)).fetchall():
        d = dict(r)
        kod = d["rozet_kodu"]
        if kod in ROZET_TANIMI:
            d["emoji"] = ROZET_TANIMI[kod][0]
            d["rozet_adi"] = ROZET_TANIMI[kod][1]
        rows.append(d)
    con.close()
    rows.sort(key=lambda x: x["tarih"], reverse=True)
    return rows[:limit]


# ── Seri (Streak) ────────────────────────────────────────────────────────

def sinif_seri_guncelle(sinif_id: int, temiz_mi: bool):
    """Bugün sınıfın tik durumuna göre seriyi günceller."""
    con = _conn(); _gami_init(con)
    bugun = datetime.now().strftime("%Y-%m-%d")
    mevcut = con.execute("SELECT * FROM sinif_seri WHERE sinif_id=?", (sinif_id,)).fetchone()
    if not mevcut:
        con.execute("INSERT INTO sinif_seri (sinif_id,guncel_seri,en_uzun_seri,son_guncelleme) VALUES(?,?,0,?)",
                    (sinif_id, 1 if temiz_mi else 0, bugun))
    elif mevcut["son_guncelleme"] == bugun:
        con.close(); return  # Zaten güncellendi
    else:
        yeni_seri = (mevcut["guncel_seri"] + 1) if temiz_mi else 0
        en_uzun   = max(mevcut["en_uzun_seri"], yeni_seri)
        con.execute("UPDATE sinif_seri SET guncel_seri=?,en_uzun_seri=?,son_guncelleme=? WHERE sinif_id=?",
                    (yeni_seri, en_uzun, bugun, sinif_id))
        # Rozet kontrolleri
        if yeni_seri >= 10:
            con.commit(); con.close()
            rozet_ver_sinif(sinif_id, "streak_10")
            return
    con.commit(); con.close()


def tum_seri_tablosu() -> list[dict]:
    con = _conn(); _gami_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT s.sinif_adi, ss.guncel_seri, ss.en_uzun_seri
        FROM sinif_seri ss JOIN siniflar s ON s.id = ss.sinif_id
        ORDER BY ss.guncel_seri DESC, ss.en_uzun_seri DESC
    """).fetchall()]
    con.close()
    return rows


# ── Günlük Görev ─────────────────────────────────────────────────────────

def bugun_gorev() -> dict:
    """Bugünün görevini döndürür, yoksa rastgele oluşturur."""
    import random
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn(); _gami_init(con)
    row   = con.execute("SELECT * FROM gunluk_gorev WHERE tarih=?", (bugun,)).fetchone()
    if not row:
        gorev, puan = random.choice(GUNLUK_GOREV_LISTESI)
        con.execute("INSERT INTO gunluk_gorev (tarih,gorev,puan,tamamlayan_ids) VALUES(?,?,?,'[]')",
                    (bugun, gorev, puan))
        con.commit()
        row = con.execute("SELECT * FROM gunluk_gorev WHERE tarih=?", (bugun,)).fetchone()
    d = dict(row)
    import json
    d["tamamlayan_ids"] = json.loads(d.get("tamamlayan_ids") or "[]")
    con.close()
    return d


def gorev_tamamla(gorev_id: int, sinif_id: int) -> dict:
    """Sınıfı görevi tamamlamış olarak işaretler ve puan ekler."""
    import json
    con = _conn(); _gami_init(con)
    row = con.execute("SELECT * FROM gunluk_gorev WHERE id=?", (gorev_id,)).fetchone()
    if not row:
        con.close(); return {"ok": False}
    ids = json.loads(row["tamamlayan_ids"] or "[]")
    if sinif_id in ids:
        con.close(); return {"ok": False, "sebep": "Zaten tamamlandi"}
    ids.append(sinif_id)
    con.execute("UPDATE gunluk_gorev SET tamamlayan_ids=? WHERE id=?",
                (json.dumps(ids), gorev_id))
    con.commit(); con.close()
    # Puan ekle
    olumlu_puan_ekle(sinif_id, 1, f"Gunluk Gorev: {row['gorev']}")
    return {"ok": True, "puan": row["puan"]}


# ── Gizli Müfettiş ────────────────────────────────────────────────────────

def _ittifak_migrate(con) -> None:
    """ittifak_gorev tablosuna seans ve kaynak sütunlarını ekler (lazy migration)."""
    cols = {r["name"] for r in con.execute("PRAGMA table_info(ittifak_gorev)")}
    if "seans" not in cols:
        try:
            con.execute("ALTER TABLE ittifak_gorev ADD COLUMN seans TEXT DEFAULT 'sabah'")
        except Exception:
            pass
    if "kaynak" not in cols:
        try:
            con.execute("ALTER TABLE ittifak_gorev ADD COLUMN kaynak TEXT DEFAULT 'ogretmen'")
        except Exception:
            pass
    con.commit()


def bugun_mufettis() -> dict | None:
    """Bugünün gizli müfettişini döndürür. Artık otomatik atama YAPMAZ."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn(); _gami_init(con)
    row   = con.execute("SELECT m.*,o.ad_soyad,s.sinif_adi FROM gizli_mufettis m "
                        "JOIN ogrenciler o ON o.id=m.ogrenci_id "
                        "JOIN siniflar s ON s.id=m.sinif_id "
                        "WHERE m.tarih=?", (bugun,)).fetchone()
    con.close()
    return dict(row) if row else None


def mufettis_belirle(ogrenci_id: int) -> dict:
    """Sadece yetkili öğretmenler çağırabilir — bugünün gizli müfettişini belirler."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn(); _gami_init(con)
    mevcut = con.execute("SELECT id FROM gizli_mufettis WHERE tarih=?", (bugun,)).fetchone()
    if mevcut:
        con.close(); return {"ok": False, "sebep": "Bugün zaten belirlendi"}
    ogr = con.execute("SELECT id, sinif_id FROM ogrenciler WHERE id=?", (ogrenci_id,)).fetchone()
    if not ogr:
        con.close(); return {"ok": False, "sebep": "Öğrenci bulunamadı"}
    con.execute("INSERT INTO gizli_mufettis (tarih,ogrenci_id,sinif_id) VALUES(?,?,?)",
                (bugun, ogrenci_id, ogr["sinif_id"]))
    con.commit(); con.close()
    return {"ok": True}


def mufettis_degerlendir(mufettis_id: int, sonuc: str) -> dict:
    """'iyi' veya 'kotu' sonucu kaydeder; iyi ise puan ve rozet verir."""
    con = _conn(); _gami_init(con)
    row = con.execute("SELECT * FROM gizli_mufettis WHERE id=?", (mufettis_id,)).fetchone()
    if not row or row["sonuc"]:
        con.close(); return {"ok": False}
    con.execute("UPDATE gizli_mufettis SET sonuc=? WHERE id=?", (sonuc, mufettis_id))
    con.commit(); con.close()
    if sonuc == "iyi":
        olumlu_puan_ekle(row["sinif_id"], 1, "Gizli Mufettis: Mukemmel davranis")
        rozet_ver_ogrenci(row["ogrenci_id"], row["sinif_id"], "mufettis_iyisi")
    return {"ok": True}


# ── Alkış Kuponu ─────────────────────────────────────────────────────────

def alkis_ver(ogrenci_id: int, sinif_id: int, ogretmen_id: int, mesaj: str = "Harika is!") -> dict:
    con = _conn(); _gami_init(con)
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    con.execute("INSERT INTO alkis_kuponu (ogrenci_id,sinif_id,ogretmen_id,mesaj,tarih) VALUES(?,?,?,?,?)",
                (ogrenci_id, sinif_id, ogretmen_id, mesaj, tarih))
    con.commit()
    sayi = con.execute("SELECT COUNT(*) FROM alkis_kuponu WHERE ogrenci_id=?", (ogrenci_id,)).fetchone()[0]
    con.close()
    if sayi >= 5:
        rozet_ver_ogrenci(ogrenci_id, sinif_id, "alkis_efsane")
    return {"ok": True, "toplam_alkis": sayi}


def son_alkislar(limit: int = 20) -> list[dict]:
    con = _conn(); _gami_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT ak.mesaj, ak.tarih, o.ad_soyad AS ogrenci, s.sinif_adi, og.ad_soyad AS ogretmen
        FROM alkis_kuponu ak
        JOIN ogrenciler o ON o.id=ak.ogrenci_id
        JOIN siniflar s ON s.id=ak.sinif_id
        JOIN ogretmenler og ON og.id=ak.ogretmen_id
        ORDER BY ak.tarih DESC LIMIT ?
    """, (limit,)).fetchall()]
    con.close()
    return rows


# ── Sezon Şampiyonluğu ───────────────────────────────────────────────────

def sezon_puan_ekle(sinif_id: int, ekle: int = 3):
    con = _conn(); _gami_init(con)
    var = con.execute("SELECT sinif_id FROM sezon_puan WHERE sinif_id=?", (sinif_id,)).fetchone()
    if var:
        con.execute("UPDATE sezon_puan SET puan=puan+? WHERE sinif_id=?", (ekle, sinif_id))
    else:
        con.execute("INSERT INTO sezon_puan (sinif_id,puan) VALUES(?,?)", (sinif_id, ekle))
    con.commit(); con.close()


def sezon_siralama() -> list[dict]:
    con = _conn(); _gami_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT s.id AS sinif_id, s.sinif_adi,
               COALESCE(sp.puan,0) AS sezon_puan
        FROM siniflar s
        LEFT JOIN sezon_puan sp ON sp.sinif_id=s.id
        ORDER BY COALESCE(sp.puan,0) DESC, s.sinif_adi
    """).fetchall()]
    con.close()
    return rows


# ── İttifak Görevi ────────────────────────────────────────────────────────

def ittifak_olustur(sinif1_id: int, sinif2_id: int) -> dict:
    import random
    con = _conn(); _gami_init(con)
    tarih = datetime.now().strftime("%Y-%m-%d")
    # Zaten var mi?
    var = con.execute("SELECT id FROM ittifak_gorev WHERE tarih=? AND ((sinif1_id=? AND sinif2_id=?) OR (sinif1_id=? AND sinif2_id=?))",
                      (tarih, sinif1_id, sinif2_id, sinif2_id, sinif1_id)).fetchone()
    if var:
        con.close(); return {"ok": False, "sebep": "Zaten ittifak var"}
    gorev = random.choice(ITTIFAK_GOREV_LISTESI)
    con.execute("INSERT INTO ittifak_gorev (tarih,sinif1_id,sinif2_id,gorev,durum,puan) VALUES(?,?,?,?,'bekliyor',5)",
                (tarih, sinif1_id, sinif2_id, gorev))
    con.commit()
    ittifak_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.close()
    return {"ok": True, "ittifak_id": ittifak_id, "gorev": gorev}


def aktif_ittifaklar() -> list[dict]:
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn(); _gami_init(con); _ittifak_migrate(con)
    rows  = [dict(r) for r in con.execute("""
        SELECT ig.*, s1.sinif_adi AS sinif1_adi, s2.sinif_adi AS sinif2_adi
        FROM ittifak_gorev ig
        JOIN siniflar s1 ON s1.id=ig.sinif1_id
        JOIN siniflar s2 ON s2.id=ig.sinif2_id
        WHERE ig.tarih=?
        ORDER BY ig.id DESC
    """, (bugun,)).fetchall()]
    con.close()
    return rows


def ittifak_tamamla(ittifak_id: int) -> dict:
    con = _conn(); _gami_init(con)
    row = con.execute("SELECT * FROM ittifak_gorev WHERE id=?", (ittifak_id,)).fetchone()
    if not row or row["durum"] != "bekliyor":
        con.close(); return {"ok": False}
    con.execute("UPDATE ittifak_gorev SET durum='tamamlandi' WHERE id=?", (ittifak_id,))
    con.commit(); con.close()
    olumlu_puan_ekle(row["sinif1_id"], 1, "Ittifak Gorevi Tamamlandi")
    olumlu_puan_ekle(row["sinif2_id"], 1, "Ittifak Gorevi Tamamlandi")
    sezon_puan_ekle(row["sinif1_id"], row["puan"])
    sezon_puan_ekle(row["sinif2_id"], row["puan"])
    return {"ok": True}


def ittifak_ogrenci_talebi(sinif1_id: int, sinif2_id: int, seans: str) -> dict:
    """Öğrenci kaynaklı ittifak talebi — öğretmen onayı bekleniyor."""
    import random
    if seans not in ("sabah", "ogleden_sonra"):
        return {"ok": False, "sebep": "Geçersiz seans"}
    con = _conn(); _gami_init(con); _ittifak_migrate(con)
    tarih = datetime.now().strftime("%Y-%m-%d")
    var = con.execute(
        "SELECT id FROM ittifak_gorev WHERE tarih=? AND seans=? "
        "AND ((sinif1_id=? AND sinif2_id=?) OR (sinif1_id=? AND sinif2_id=?))",
        (tarih, seans, sinif1_id, sinif2_id, sinif2_id, sinif1_id)
    ).fetchone()
    if var:
        con.close(); return {"ok": False, "sebep": "Bu seans için zaten talep var"}
    gorev = random.choice(ITTIFAK_GOREV_LISTESI)
    con.execute(
        "INSERT INTO ittifak_gorev (tarih,sinif1_id,sinif2_id,gorev,durum,puan,seans,kaynak) "
        "VALUES(?,?,?,?,'ogrenci_talebi',5,?,'ogrenci')",
        (tarih, sinif1_id, sinif2_id, gorev, seans)
    )
    con.commit()
    ittifak_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.close()
    return {"ok": True, "ittifak_id": ittifak_id, "gorev": gorev}


def ittifak_onayla(ittifak_id: int) -> dict:
    """Öğretmen, öğrenci talebini onaylar → durum 'bekliyor' olur."""
    con = _conn(); _gami_init(con)
    row = con.execute("SELECT * FROM ittifak_gorev WHERE id=?", (ittifak_id,)).fetchone()
    if not row or row["durum"] != "ogrenci_talebi":
        con.close(); return {"ok": False, "sebep": "Talep bulunamadı ya da zaten işlendi"}
    con.execute("UPDATE ittifak_gorev SET durum='bekliyor' WHERE id=?", (ittifak_id,))
    con.commit(); con.close()
    return {"ok": True}


def ittifak_reddet(ittifak_id: int) -> dict:
    """Öğretmen, öğrenci talebini reddeder."""
    con = _conn(); _gami_init(con)
    row = con.execute("SELECT * FROM ittifak_gorev WHERE id=?", (ittifak_id,)).fetchone()
    if not row or row["durum"] != "ogrenci_talebi":
        con.close(); return {"ok": False}
    con.execute("UPDATE ittifak_gorev SET durum='reddedildi' WHERE id=?", (ittifak_id,))
    con.commit(); con.close()
    return {"ok": True}


def bekleyen_ogrenci_talepleri() -> list[dict]:
    """Öğrencilerin gönderip öğretmen onayı bekleyen ittifak talepleri."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn(); _gami_init(con); _ittifak_migrate(con)
    rows  = [dict(r) for r in con.execute("""
        SELECT ig.*, s1.sinif_adi AS sinif1_adi, s2.sinif_adi AS sinif2_adi
        FROM ittifak_gorev ig
        JOIN siniflar s1 ON s1.id=ig.sinif1_id
        JOIN siniflar s2 ON s2.id=ig.sinif2_id
        WHERE ig.tarih=? AND ig.durum='ogrenci_talebi'
        ORDER BY ig.id DESC
    """, (bugun,)).fetchall()]
    con.close()
    return rows


# ── Şans Çarkı ────────────────────────────────────────────────────────────

def sans_carki_cevir(mac_id: int, sinif_id: int) -> dict:
    import random
    con = _conn(); _gami_init(con)
    _mac_tablosu_olustur(con)
    # Zaten cevrildi mi?
    var = con.execute("SELECT id FROM sans_carki WHERE mac_id=? AND sinif_id=?", (mac_id, sinif_id)).fetchone()
    if var:
        con.close(); return {"ok": False, "sebep": "Bu mac icin cark zaten cevirildi"}
    sonuc_text, puan_deg, renk = random.choice(SANS_CARKI_SEENEKLERI)
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    con.execute("INSERT INTO sans_carki (mac_id,sinif_id,sonuc,puan_deg,tarih) VALUES(?,?,?,?,?)",
                (mac_id, sinif_id, sonuc_text, puan_deg, tarih))
    con.commit()
    if puan_deg != 0:
        var2 = con.execute("SELECT sinif_id FROM lig_mac_tablo WHERE sinif_id=?", (sinif_id,)).fetchone()
        if var2:
            con.execute("UPDATE lig_mac_tablo SET puan=MAX(0,puan+?),ag=ag+? WHERE sinif_id=?",
                        (puan_deg, puan_deg, sinif_id))
        else:
            con.execute("INSERT INTO lig_mac_tablo (sinif_id,puan,ag) VALUES(?,MAX(0,?),?)",
                        (sinif_id, puan_deg, puan_deg))
        con.commit()
    con.close()
    return {"ok": True, "sonuc": sonuc_text, "puan_deg": puan_deg, "renk": renk}


# ── Tik Dondurma (Af Hakki) ──────────────────────────────────────────────

def tik_dondur(ogrenci_id: int, ogretmen_id: int) -> dict:
    """
    Ogrencinin son 3 gunuk temiz gecmisini kontrol eder.
    Temizse en son 1 tikini siler (af hakki).
    """
    bugun = datetime.now().date()
    con   = _conn()
    # Son 3 gunde tik var mi?
    son3 = con.execute("""
        SELECT COUNT(*) FROM tik_kayitlari
        WHERE ogrenci_id=? AND tarih >= ?
    """, (ogrenci_id, str(bugun - __import__('datetime').timedelta(days=3)))).fetchone()[0]
    if son3 > 0:
        con.close()
        return {"ok": False, "sebep": "Son 3 gunde tik var, af hakki kazanilmadi"}
    # Toplam tik var mi?
    toplam = con.execute("SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id=?", (ogrenci_id,)).fetchone()[0]
    if toplam == 0:
        con.close()
        return {"ok": False, "sebep": "Zaten hic tik yok"}
    # En son tiki sil
    son_tik = con.execute("SELECT id FROM tik_kayitlari WHERE ogrenci_id=? ORDER BY tarih DESC LIMIT 1",
                          (ogrenci_id,)).fetchone()
    con.execute("DELETE FROM tik_kayitlari WHERE id=?", (son_tik["id"],))
    con.commit(); con.close()
    return {"ok": True, "silinen_tik": 1}


# ══════════════════════════════════════════════════════════════════════════
# Taktik Tahtası
# ══════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════
# Veri Sıfırlama
# ══════════════════════════════════════════════════════════════════════════

# Silinecek tablolar (yapısal tablolar ve soru bankası KORUNUR)
_SIFIRLANACAK_TABLOLAR = [
    "tik_kayitlari",
    "olumlu_davranis",
    "lig",
    "lig_maclar",
    "lig_oylari",
    "lig_mac_tablo",
    "kadro_ogrenci",
    "kart_kayitlari",
    "rozet_kayitlari",
    "sinif_rozet",
    "sinif_seri",
    "gunluk_gorev",
    "gizli_mufettis",
    "alkis_kuponu",
    "sezon_puan",
    "ittifak_gorev",
    "sans_carki",
    "taktik_formasyonu",
    "quiz_sonuclari",
]

# Korunan tablolar: ogretmenler, siniflar, ogrenciler, ogretmen_sinif, quiz_sorulari


def tum_verileri_sifirla() -> dict:
    """
    Tüm veri girişlerini (tikler, maçlar, puanlar, gamifikasyon vb.) siler.
    Yapısal tablolar (öğretmen/sınıf/öğrenci) ve soru bankası KORUNUR.
    """
    con = _conn()
    silinen = {}
    for tablo in _SIFIRLANACAK_TABLOLAR:
        try:
            sayi = con.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0]
            con.execute(f"DELETE FROM {tablo}")
            silinen[tablo] = sayi
        except Exception:
            silinen[tablo] = "tablo yok"
    con.commit()
    con.close()
    return {"ok": True, "silinen": silinen}


def _taktik_tablosu_olustur(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS taktik_formasyonu (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            veri     TEXT NOT NULL DEFAULT '{}',
            tarih    TEXT NOT NULL
        )
    """)
    con.commit()


def taktik_yukle(sinif_id: int) -> dict:
    """Sınıfın kayıtlı taktik formasyonunu döner."""
    import json
    con = _conn()
    _taktik_tablosu_olustur(con)
    row = con.execute("SELECT veri FROM taktik_formasyonu WHERE sinif_id=?",
                      (sinif_id,)).fetchone()
    con.close()
    if row:
        try:
            return json.loads(row["veri"])
        except Exception:
            return {}
    return {}


# ══════════════════════════════════════════════════════════════════════════
# Quiz / Bilgi Yarışması
# ══════════════════════════════════════════════════════════════════════════

def _quiz_init(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS quiz_sorulari (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_seviyesi  INTEGER NOT NULL,
            ders            TEXT NOT NULL,
            soru            TEXT NOT NULL,
            secenek_a       TEXT NOT NULL,
            secenek_b       TEXT NOT NULL,
            secenek_c       TEXT NOT NULL,
            secenek_d       TEXT NOT NULL,
            dogru_cevap     TEXT NOT NULL,
            sira            INTEGER NOT NULL DEFAULT 1
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS quiz_sonuclari (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id        INTEGER REFERENCES siniflar(id),
            tarih           TEXT NOT NULL,
            ders            TEXT NOT NULL,
            sinif_seviyesi  INTEGER NOT NULL,
            dogru           INTEGER NOT NULL DEFAULT 0,
            yanlis          INTEGER NOT NULL DEFAULT 0,
            puan_degisim    INTEGER NOT NULL DEFAULT 0
        )
    """)
    con.commit()


def quiz_sorulari_yukle() -> None:
    """İlk çalıştırmada soru bankasını DB'ye yükler (sadece bir kez)."""
    import json as _json
    from quiz_sorulari import tum_sorular_as_list
    con = _conn()
    _quiz_init(con)
    mevcut = con.execute("SELECT COUNT(*) FROM quiz_sorulari").fetchone()[0]
    if mevcut == 0:
        rows = tum_sorular_as_list()
        con.executemany("""
            INSERT INTO quiz_sorulari
                (sinif_seviyesi, ders, soru, secenek_a, secenek_b, secenek_c, secenek_d, dogru_cevap, sira)
            VALUES (:sinif_seviyesi,:ders,:soru,:secenek_a,:secenek_b,:secenek_c,:secenek_d,:dogru_cevap,:sira)
        """, rows)
        con.commit()
    con.close()


def quiz_sorular_getir(sinif_seviyesi: int, ders: str, sayi: int = 7) -> list[dict]:
    """Bugünün tarihine göre deterministik 7 soru seçer (her gün farklı)."""
    import hashlib
    con = _conn()
    _quiz_init(con)
    tumSorular = con.execute(
        "SELECT * FROM quiz_sorulari WHERE sinif_seviyesi=? AND ders=? ORDER BY id",
        (sinif_seviyesi, ders)
    ).fetchall()
    con.close()
    if not tumSorular:
        return []
    tumSorular = [dict(r) for r in tumSorular]
    n = len(tumSorular)
    bugun = datetime.now().strftime("%Y%m%d")
    seed_str = f"{bugun}{sinif_seviyesi}{ders}"
    offset = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % n
    # Döngüsel seçim
    secilen = []
    for i in range(sayi):
        secilen.append(tumSorular[(offset + i * 3) % n])
    return secilen


def quiz_sonuc_kaydet(sinif_id: int, ders: str,
                      sinif_seviyesi: int, dogru: int, yanlis: int) -> dict:
    """Quiz sonucunu kaydeder ve sınıfa lig puanı ekler."""
    puan_degisim = dogru - yanlis
    tarih = datetime.now().strftime("%Y-%m-%d")
    con = _conn()
    _quiz_init(con)
    con.execute("""
        INSERT INTO quiz_sonuclari
            (sinif_id, tarih, ders, sinif_seviyesi, dogru, yanlis, puan_degisim)
        VALUES (?,?,?,?,?,?,?)
    """, (sinif_id, tarih, ders, sinif_seviyesi, dogru, yanlis, puan_degisim))
    # Lig puanı güncelle (olumlu davranış olarak ekle)
    if puan_degisim != 0 and sinif_id:
        try:
            con.execute("""
                UPDATE sinif_lig_puanlari
                SET puan = puan + ?
                WHERE sinif_id = ?
            """, (puan_degisim, sinif_id))
            if con.execute("SELECT changes()").fetchone()[0] == 0:
                con.execute("""
                    INSERT INTO sinif_lig_puanlari (sinif_id, puan)
                    VALUES (?, ?)
                """, (sinif_id, max(0, puan_degisim)))
        except Exception:
            pass
    con.commit(); con.close()
    return {"ok": True, "puan_degisim": puan_degisim}


def quiz_gunluk_dersleri(sinif_id: int, tarih: str = None) -> list[str]:
    """Bugün hangi derslerin quiz'inin yapıldığını listeler."""
    tarih = tarih or datetime.now().strftime("%Y-%m-%d")
    con = _conn()
    _quiz_init(con)
    rows = con.execute(
        "SELECT ders FROM quiz_sonuclari WHERE sinif_id=? AND tarih=?",
        (sinif_id, tarih)
    ).fetchall()
    con.close()
    return [r["ders"] for r in rows]


def quiz_sinif_istatistik(sinif_id: int) -> list[dict]:
    """Sınıfın tüm quiz geçmişi ve istatistiği."""
    con = _conn()
    _quiz_init(con)
    rows = con.execute("""
        SELECT ders, SUM(dogru) as toplam_dogru, SUM(yanlis) as toplam_yanlis,
               SUM(puan_degisim) as toplam_puan, COUNT(*) as oynanma
        FROM quiz_sonuclari WHERE sinif_id=?
        GROUP BY ders ORDER BY toplam_puan DESC
    """, (sinif_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def taktik_kaydet(sinif_id: int, veri_str: str) -> dict:
    """Sınıfın taktik formasyonunu kaydeder (JSON string)."""
    import json
    try:
        json.loads(veri_str)   # geçerli JSON mi?
    except Exception:
        return {"ok": False, "sebep": "Geçersiz veri"}
    con = _conn()
    _taktik_tablosu_olustur(con)
    con.execute(
        "INSERT OR REPLACE INTO taktik_formasyonu (sinif_id, veri, tarih) VALUES(?,?,?)",
        (sinif_id, veri_str, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    con.commit(); con.close()
    return {"ok": True}


def _rol_adi_normalize(s: str) -> str:
    """Türkçe aksan ve boşlukları kaldırır, küçük harfe çevirir."""
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace(" ", "").replace("(", "").replace(")", "")


def taktik_kadro_guncelle(sinif_id: int, oyuncular: dict) -> None:
    """
    Taktik tahtasında seçilen rolleri kadro_ogrenci tablosuna yazar.
    oyuncular: {str(ogrenci_id): {"x":…, "y":…, "rol": "Stoper"}}
    """
    import json

    # Rol adı → mevki_no reverse haritası (normalize edilmiş)
    rol_to_no = {_rol_adi_normalize(m[2]): m[0] for m in MEVKILER}
    varsayilan_no = 15   # Santrafor

    con = _conn()
    _kadro_tablosu_olustur(con)

    for ogr_id_str, veri in oyuncular.items():
        try:
            ogr_id = int(ogr_id_str)
        except ValueError:
            continue
        rol     = veri.get("rol", "")
        mevki_no = rol_to_no.get(_rol_adi_normalize(rol), varsayilan_no)

        mevcut = con.execute(
            "SELECT id FROM kadro_ogrenci WHERE sinif_id=? AND ogrenci_id=?",
            (sinif_id, ogr_id)
        ).fetchone()
        if mevcut:
            con.execute(
                "UPDATE kadro_ogrenci SET mevki_no=? WHERE sinif_id=? AND ogrenci_id=?",
                (mevki_no, sinif_id, ogr_id)
            )
        else:
            con.execute(
                "INSERT INTO kadro_ogrenci (sinif_id, ogrenci_id, mevki_no) VALUES (?,?,?)",
                (sinif_id, ogr_id, mevki_no)
            )

    con.commit()
    con.close()
