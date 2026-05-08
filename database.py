"""
database.py
-----------
Veritabanı yönetimi + PDF'lerden alınan gerçek okul verileri.
Tablolar: ogretmenler, siniflar, ogretmen_sinif, ogrenciler, tik_kayitlari
"""

import sqlite3
import os
from datetime import datetime

# Render.com gibi bulut ortamlarında /data klasörü kalıcıdır;
# yoksa uygulama klasörü kullanılır.
_DATA_DIR = "/data" if os.path.isdir("/data") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DATA_DIR, "ogrenci_takip.db")

# ── Disiplin kriterleri (22 adet) ──────────────────────────────────────────
KRITERLER = [
    ("📚", "Eşya Eksikliği"),
    ("⏰", "Geç Kalma"),
    ("🚫", "Saygısızlık"),
    ("📢", "Gürültü / Dersi Bozma"),
    ("📱", "İzinsiz Telefon Kullanımı"),
    ("📝", "Kopya Girişimi"),
    ("🗣️", "İzinsiz Konuşma"),
    ("👊", "Arkadaşa Zarar Verme"),
    ("📖", "Derse Hazırlıksız Gelme"),
    ("🤬", "Küfür / Uygunsuz Dil"),
    ("🚪", "İzinsiz Sınıf Terk"),
    ("🏫", "Okul Eşyasına Zarar"),
    ("😤", "Zorbalık / Taciz"),
    ("🤥", "Yalan Söyleme"),
    ("😴", "Derste Uyuma"),
    ("👕", "Kıyafet Yönetmeliği İhlali"),
    ("💻", "Sosyal Medya / İnternet İhlali"),
    ("🥊", "Kavga / Tartışma"),
    ("📋", "Ödev Yapmama"),
    ("✏️",  "Not Tutmama"),
    ("🙅", "Dersi Engelleme"),
    ("❓", "Diğer"),
]

# ── PDF'lerden alınan öğretmen–sınıf eşleşmeleri ──────────────────────────
_OGRETMEN_SINIF: dict[str, list[str]] = {
    "ADEM AKGÜL":       ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B"],
    "AYTAÇ ATMACA":     ["6/A", "6/B", "8/A", "8/B"],
    "CANTEKİN KURTOĞLU":["5/A", "5/B", "8/A", "8/B"],
    "CEMİL KUYUMCU":    ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "ELİF DEDEOĞLU":    ["5/A", "6/A", "6/B", "7/B", "8/A", "8/B"],
    "EMİNE KILIÇ":      ["5/B", "7/A"],
    "FATMA ÇAPKULAÇ":   ["5/B", "6/A", "6/B", "7/A"],
    "FUNDA KİRAZ":      ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "HAVVA ÖZDEMİR":    ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "İFTARİYE ARSLAN":  ["5/A", "5/B", "7/A", "7/B"],
    "MERVE TÜRKEL":     ["6/A", "6/B", "7/A"],
    "METEHAN CÜCEN":    ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "NESLİHAN ÇAKMAK":  ["5/A", "7/B", "8/A", "8/B"],
    "ÖZGE KILIÇ":       ["7/A", "7/B", "8/A", "8/B"],
    "SATI ERGİN":       ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
    "YUSUF ERTÜRK":     ["5/A", "5/B", "6/A", "6/B"],
}

# ── PDF'lerden alınan öğrenci listeleri (ad_soyad, öğrenci_no) ─────────────
_OGRENCILER: dict[str, list[tuple[str, int]]] = {
    "5/A": [
        ("YASEMİN ARDA", 4), ("ELİF NAZ ÇOBAN", 10), ("TOPRAK ÇELİKEL", 13),
        ("CENNET ÇAKIR", 14), ("ALPASLAN ALİM", 16), ("ALİ DURAN UÇAR", 25),
        ("ŞEYMA ÇETİN", 30), ("ALPEREN KÖROĞLU", 33), ("BATUHAN KÖROĞLU", 46),
        ("BUSE SARIKAYA", 60), ("ELİF KAŞMER", 68), ("HASAN KAĞAN GÜLEK", 83),
        ("ERDEM BÜTÜNER", 89), ("MELİKE KAŞMER", 96), ("MERT BERAT İMAL", 101),
        ("MESUT TUNA ALİM", 103), ("MUHAMMED EMİN ARSLAN", 105),
        ("MUHAMMED YİĞİT HELVACI", 107), ("MUSTAFA EMİR ARSLAN", 113),
        ("SEMANUR GÜLER", 114), ("RECEP EREN ÇELEBİ", 126),
        ("VEYSAL UMUT ARICI", 136), ("YAĞIZ KAYRA BARILDAR", 137),
        ("ZEYNEP AZRA BOZKUŞ", 141), ("ŞÜKRÜ EREN KIRKICI", 281),
    ],
    "5/B": [
        ("YİĞİT EFE KULA", 2), ("EMİR EREN ÇAKIR", 6), ("AHMET YASİR GÜNEŞ", 8),
        ("BATTAL UMUT AÇIKGÖZ", 20), ("RABİA MEVLÜDE TURA", 24),
        ("ALPER TAHA ORAL", 26), ("ALPEREN AKKAYA", 27), ("EZEL TALHA ÇOBAN", 29),
        ("MEHMET FATİH ORUÇ", 32), ("ARİF EMİR DALDADURMAZ", 39),
        ("BAHRİ BERAT KAYA", 44), ("BURAK ATEŞ", 48), ("YUSUF EYMEN KARLI", 52),
        ("ELİF ADA GÜNNEÇ", 67), ("ESLEM ÇÖRDÜK", 69), ("ESMA NUR ATAK", 74),
        ("EYMEN YÜCE", 77), ("HANDAN MİNA GÜÇLÜ", 82), ("HİRA NUR KARAKAŞ", 88),
        ("MELİKE ÖZDİL", 97), ("MİRAY ADA KARADAĞLI", 104),
        ("NİZAMETTİN UYSAL", 116), ("SEZGİN SAVAŞ", 132), ("UMUT VURAL", 133),
        ("VEYSAL EMRE ŞEN", 135), ("POYRAZ EFE KOLAY", 298),
    ],
    "6/A": [
        ("ZEHRA SARI", 7), ("ŞEREF ÇÖRDÜK", 18), ("ADEM EMİR ACAR", 21),
        ("MUHAMMED SALİH İPEK", 34), ("ASLINUR BALCI", 40), ("AHMET SAVAŞ", 42),
        ("ZEYNEP KESKİN", 43), ("MUSTAFA ÇINAR ÇELİKEL", 65), ("EGE AÇIKGÖZ", 78),
        ("NİSA İPEK ÇORUMLU", 84), ("SEVGİ POLAT", 94), ("YUSUF AKCAN", 122),
        ("HASAN ARDA ALİM", 125), ("ONUR ÇAKMAK", 128), ("MEHMET ZOR", 155),
        ("BERKAY KOCA", 220), ("BEYZA NUR YAMAN", 227), ("EMİR DUMAN", 254),
        ("HACER BETÜL YILDIRIM", 268), ("HAZAL NUR SAĞIR", 270),
        ("HİRA BUĞLEM AYDIN", 271), ("HÜSEYİN ÇANKAL", 272),
        ("KADİR KIRATLI", 277), ("NACİYE NİSA ARSLAN", 292), ("POYRAZ ÖZEK", 299),
    ],
    "6/B": [
        ("ENES AYKAÇ", 22), ("AHMET BERKAY YURDUSAY", 37), ("ÖZGÜR ÇIRAK", 76),
        ("BERKAY KÖSE", 86), ("YUSUF CAN MUCUK", 99), ("UTKU CAN DALKILIÇ", 111),
        ("ELİF YILMAZ", 120), ("YİĞİT TALHA KARACA", 144), ("BERRA ERDEM", 222),
        ("EMİR EFE ŞAHİN", 255), ("EREN KULA", 258), ("ESLEM KARAASLAN", 260),
        ("EYMEN ÇIKRIK", 263), ("FEYZA SARE ÇAKIR", 266), ("HANİFE ÇÜRÜK", 269),
        ("HÜSEYİN DALKIRAN", 273), ("HÜSEYİN EFE TEPEGÖZ", 274),
        ("İBRAHİM ODUNCU", 276), ("KÜBRA SARI", 279),
        ("MUHAMMED EMİR DALEĞMEZ", 285), ("MUSA ÇAĞLAYAN", 287),
        ("MUSTAFA YİĞİT UYSAL", 289), ("PELİN NUR SARI", 297), ("RUKİYE KARACA", 301),
    ],
    "7/A": [
        ("AÇELYA EMEN", 41), ("ALİ BERK AKTAŞ", 45), ("ATAMAN ŞEKER", 58),
        ("BELGİN ECE DEDE", 73), ("CİHAT KARAASLAN", 81), ("DOĞUKAN AKYOL", 92),
        ("EBRAR ŞAHİN", 100), ("ELANUR KÖSE", 109), ("ÇINAR AYDAŞ", 110),
        ("ENES BUĞRA İŞLER", 115), ("ESMA BETÜL ZOBU", 118), ("ESMA RABİA ŞEN", 119),
        ("EYMEN EFE ARIK", 121), ("KADER URAL", 131), ("HASAN MERT ÜNLÜ", 138),
        ("ELANUR ARDOĞAN", 149), ("MUHAMMET HASAN ZEYBEK", 158),
        ("MELİKE ÜSTÜN", 163), ("MELİSA SARIOĞLU", 164),
        ("NEHİR NİSA ÇÖPATLAMAZ", 177), ("RAMAZAN AKTAŞ", 194), ("ELA SAĞLAM", 200),
        ("VEYSEL CAN BEKTAŞ", 215), ("YAREN KAPLAN", 217),
        ("ZEYNEP İPEK", 223), ("ZEYNEP KOLAY", 224),
    ],
    "7/B": [
        ("MURAT YILDIRIM", 11), ("DAMLA NAZ GENCEL", 12), ("EMİNE SERRA KOLAY", 19),
        ("ÇINAR SAĞIR", 38), ("ALİ KEKEÇ", 57), ("AYŞENUR SENA ÇENGELCİ", 72),
        ("BERRA NUR DERE", 75), ("EGEHAN ALA", 108), ("FATMA NUR CANDAN", 123),
        ("GÜLBAHAR İPEKCİ", 129), ("HATİCE KÜBRA GÖKGÖBEL", 139),
        ("SENA NEHİR SAĞIR", 142), ("HÜMEYRA ŞİRİN DELİCAN", 143),
        ("HÜSEYİN TALHA DERE", 145), ("İBRAHİM ALİ DİNÇ", 148),
        ("MUHAMMED YAĞIZ KIZMAZ", 167), ("MUSAB YAMAN", 170), ("NEHİR OKUMUŞ", 181),
        ("OSMAN TAŞ", 192), ("SELDA ECE GÖKÇE", 208), ("ŞEVKET ÇÖRDÜK", 209),
        ("ŞEVVAL ÖZTÜRK", 211), ("ŞÜHEDA BUĞLEM KARASLAN", 212),
        ("YAĞMUR NİSA KOCA", 216), ("ZEHRA ZEREN", 221), ("ZÜMRA KARAKAYA", 225),
    ],
    "8/A": [
        ("ELİF ŞİMŞEK", 15), ("KAYRA KEMELEK", 23), ("EMİRHAN ÖZDEMİR", 28),
        ("BETÜL KOPAR", 51), ("BUSE NAZ KÖSE", 54), ("CEYLİN ŞAHİN", 55),
        ("ESEDULLAH ZALİM", 59), ("MELİKE VURAL", 62), ("MELİSA MİS", 63),
        ("İREM SU ÇÖRDÜK", 64), ("YAREN TİRYAKİ", 80), ("MUSTAFA EYMEN ALTUNDAŞ", 90),
        ("ALİ LEKEALMAZ", 91), ("ALİ EREN DAŞCI", 93), ("VEYSEL SEFA KÜYÜK", 95),
        ("YAĞMUR ARICI", 98), ("KÜBRA ERCAN", 102), ("CEMİLE NİSA KÜSER", 112),
        ("MAHİR AKYOL", 146), ("ECEHAN ŞİMŞEK", 147), ("MUHAMMED TALHA DİVAN", 162),
        ("HÜMEYRA ÖZTÜRK", 176), ("ESRA ÖZTÜRK", 184), ("YUSUF SÜTYEMEZ", 205),
    ],
    "8/B": [
        ("ALAADDİN ERDEN", 5), ("MİRAÇ ERTÜRK", 17), ("TUĞBA VURAL", 31),
        ("ADEM KEREM MUCU", 36), ("GİZEM NUR ÇÖPATLAMAZ", 47), ("BASRİ GEDİK", 49),
        ("BERAT BAYRAM", 50), ("BURCU KILIÇ", 53), ("DEFNE AKKAYA", 56),
        ("YUSUF FİKRET DALKIRAN", 61), ("ÖMER ÇAKAR", 70), ("SEFER AHMET ORAL", 71),
        ("ZEHRA KÖRPEŞ", 85), ("ALPEREN ARMUTCU", 106), ("EBRAR ÇUKUR", 117),
        ("ESMA NUR ÇUKUR", 124), ("EFE YİĞİT", 127), ("HÜSEYİN İNCE", 134),
        ("ÖZGE YILDIZ", 174), ("YUSUF YILDIRIM", 182), ("YUSUF KEMAL PEKER", 204),
        ("MUHAMMED AKTAŞ", 210),
    ],
}


# ══════════════════════════════════════════════════════════════════════════
# Bağlantı
# ══════════════════════════════════════════════════════════════════════════

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


# ══════════════════════════════════════════════════════════════════════════
# Başlatma + Seed
# ══════════════════════════════════════════════════════════════════════════

def initialize_db():
    """Tabloları oluşturur; ilk çalıştırmada gerçek verilerle doldurur."""
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
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad  TEXT    NOT NULL,
            sinif_id  INTEGER NOT NULL REFERENCES siniflar(id),
            ogr_no    INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tik_kayitlari (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id  INTEGER NOT NULL REFERENCES ogrenciler(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            kriter      TEXT    NOT NULL,
            tarih       TEXT    NOT NULL
        );
    """)
    con.commit()

    # Migration: eski DB'de sifre sütunu yoksa ekle
    sutunlar = [r[1] for r in con.execute(
        "PRAGMA table_info(ogretmenler)").fetchall()]
    if "sifre" not in sutunlar:
        con.execute("ALTER TABLE ogretmenler ADD COLUMN sifre TEXT NOT NULL DEFAULT ''")
        con.commit()

    # Sadece ilk çalıştırmada seed et
    if cur.execute("SELECT COUNT(*) FROM ogretmenler").fetchone()[0] == 0:
        _seed(con)
    else:
        # Var olan kayıtlara şifre yoksa ata
        bos = cur.execute(
            "SELECT COUNT(*) FROM ogretmenler WHERE sifre = ''"
        ).fetchone()[0]
        if bos > 0:
            _sifreleri_ata(con)

    con.close()


def _sifre_uret() -> dict[str, str]:
    """Alfabetik sırayla EC100'den başlayan şifre haritası döndürür."""
    sirali = sorted(_OGRETMEN_SINIF.keys())
    return {ad: f"EC{100 + i}" for i, ad in enumerate(sirali)}


def _sifreleri_ata(con: sqlite3.Connection):
    """Mevcut öğretmen kayıtlarına şifrelerini atar."""
    sifre_map = _sifre_uret()
    cur = con.cursor()
    for ad, sifre in sifre_map.items():
        cur.execute(
            "UPDATE ogretmenler SET sifre = ? WHERE ad_soyad = ?",
            (sifre, ad)
        )
    con.commit()


def _seed(con: sqlite3.Connection):
    """Öğretmen, sınıf ve öğrenci verilerini ekler."""
    cur = con.cursor()
    sifre_map = _sifre_uret()

    # Sınıflar
    sinif_ids: dict[str, int] = {}
    for s in ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"]:
        cur.execute("INSERT INTO siniflar (sinif_adi) VALUES (?)", (s,))
        sinif_ids[s] = cur.lastrowid

    # Öğretmenler
    ogretmen_ids: dict[str, int] = {}
    for ogr in sorted(_OGRETMEN_SINIF.keys()):
        sifre = sifre_map[ogr]
        cur.execute(
            "INSERT INTO ogretmenler (ad_soyad, sifre) VALUES (?, ?)",
            (ogr, sifre)
        )
        ogretmen_ids[ogr] = cur.lastrowid

    # Öğretmen–Sınıf bağlantıları
    for ogr, siniflar in _OGRETMEN_SINIF.items():
        for s in siniflar:
            cur.execute(
                "INSERT OR IGNORE INTO ogretmen_sinif VALUES (?, ?)",
                (ogretmen_ids[ogr], sinif_ids[s])
            )

    # Öğrenciler
    for sinif_adi, liste in _OGRENCILER.items():
        sid = sinif_ids[sinif_adi]
        for ad_soyad, ogr_no in liste:
            cur.execute(
                "INSERT INTO ogrenciler (ad_soyad, sinif_id, ogr_no) VALUES (?, ?, ?)",
                (ad_soyad, sid, ogr_no)
            )

    con.commit()


# ══════════════════════════════════════════════════════════════════════════
# Sorgular
# ══════════════════════════════════════════════════════════════════════════

def tum_ogretmenler() -> list[dict]:
    """Tüm öğretmenleri alfabetik sırayla döndürür."""
    con = _conn()
    rows = [dict(r) for r in con.execute(
        "SELECT id, ad_soyad, sifre FROM ogretmenler ORDER BY ad_soyad"
    ).fetchall()]
    con.close()
    return rows


def tum_sifre_listesi() -> list[dict]:
    """Tüm öğretmen adlarını ve şifrelerini döndürür (yönetici listesi)."""
    con = _conn()
    rows = [dict(r) for r in con.execute(
        "SELECT ad_soyad, sifre FROM ogretmenler ORDER BY sifre"
    ).fetchall()]
    con.close()
    return rows


def ogretmen_dogrula(ad_soyad: str, sifre: str) -> bool:
    """Ad ve şifre eşleşiyorsa True döndürür."""
    con = _conn()
    row = con.execute(
        "SELECT id FROM ogretmenler WHERE ad_soyad = ? AND sifre = ?",
        (ad_soyad, sifre)
    ).fetchone()
    con.close()
    return row is not None


def ogretmen_id_bul(ad_soyad: str):
    con = _conn()
    row = con.execute(
        "SELECT id FROM ogretmenler WHERE ad_soyad = ?", (ad_soyad,)
    ).fetchone()
    con.close()
    return row["id"] if row else None


def ogretmen_siniflari(ogretmen_id: int) -> list[dict]:
    """Öğretmenin girdiği sınıfları döndürür."""
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


def sinif_ogrencileri(sinif_id: int) -> list[dict]:
    """
    Sınıftaki öğrencileri tik sayısıyla birlikte döndürür.
    Her satır: id, ad_soyad, ogr_no, tik_sayisi
    """
    con = _conn()
    rows = [dict(r) for r in con.execute("""
        SELECT o.id, o.ad_soyad, o.ogr_no,
               COUNT(t.id) AS tik_sayisi
        FROM ogrenciler o
        LEFT JOIN tik_kayitlari t ON t.ogrenci_id = o.id
        WHERE o.sinif_id = ?
        GROUP BY o.id
        ORDER BY o.ad_soyad
    """, (sinif_id,)).fetchall()]
    con.close()
    return rows


def tum_siniflar_ogrencileri(sinif_id_listesi: list[int]) -> list[dict]:
    """
    Birden fazla sınıfın öğrencilerini tek sorgu ile getirir (global arama).
    """
    if not sinif_id_listesi:
        return []
    yer_tutucu = ",".join("?" * len(sinif_id_listesi))
    con = _conn()
    rows = [dict(r) for r in con.execute(f"""
        SELECT o.id, o.ad_soyad, o.ogr_no, s.sinif_adi,
               COUNT(t.id) AS tik_sayisi
        FROM ogrenciler o
        JOIN siniflar s ON s.id = o.sinif_id
        LEFT JOIN tik_kayitlari t ON t.ogrenci_id = o.id
        WHERE o.sinif_id IN ({yer_tutucu})
        GROUP BY o.id
        ORDER BY s.sinif_adi, o.ad_soyad
    """, sinif_id_listesi).fetchall()]
    con.close()
    return rows


def ogrenci_tik_gecmisi(ogrenci_id: int) -> list[dict]:
    """Öğrencinin tüm tik geçmişini öğretmen adıyla döndürür."""
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
# Yazma İşlemleri
# ══════════════════════════════════════════════════════════════════════════

def tik_ekle(ogrenci_id: int, ogretmen_id: int, kriter: str) -> int:
    """Tik kaydeder; güncel toplam tik sayısını döndürür."""
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    con = _conn()
    con.execute(
        "INSERT INTO tik_kayitlari (ogrenci_id, ogretmen_id, kriter, tarih) VALUES (?, ?, ?, ?)",
        (ogrenci_id, ogretmen_id, kriter, tarih)
    )
    con.commit()
    sayi = con.execute(
        "SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id = ?", (ogrenci_id,)
    ).fetchone()[0]
    con.close()
    return sayi


def tek_ogrenci_sifirla(ogrenci_id: int):
    con = _conn()
    con.execute("DELETE FROM tik_kayitlari WHERE ogrenci_id = ?", (ogrenci_id,))
    con.commit()
    con.close()


def sinif_sifirla(sinif_id: int):
    """Bir sınıfın tüm tiklerini sıfırlar."""
    con = _conn()
    con.execute("""
        DELETE FROM tik_kayitlari
        WHERE ogrenci_id IN (SELECT id FROM ogrenciler WHERE sinif_id = ?)
    """, (sinif_id,))
    con.commit()
    con.close()


def tum_tikleri_sifirla():
    con = _conn()
    con.execute("DELETE FROM tik_kayitlari")
    con.commit()
    con.close()
