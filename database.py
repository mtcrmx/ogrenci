"""
database.py
-----------
Veritabanı yönetimi + PDF'lerden alınan gerçek okul verileri.
Tablolar: ogretmenler, siniflar, ogretmen_sinif, ogrenciler, tik_kayitlari
"""

import sqlite3
import os
import uuid
import json
import re
from datetime import datetime, timedelta

# Render.com gibi bulut ortamlarında /data klasörü kalıcıdır;
# yoksa uygulama klasörü kullanılır.
_DATA_DIR = "/data" if os.path.isdir("/data") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DATA_DIR, "ogrenci_takip.db")


def _bu_hafta_pazartesi() -> str:
    bugun = datetime.now().date()
    pazartesi = bugun - timedelta(days=bugun.weekday())
    return pazartesi.isoformat()

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

# ── Olumlu davranış kriterleri (sınıf bazlı Süper Lig) ──────────────────────
OLUMLU_KRITERLER = [
    ("🏆", "Sınıf Düzeni"),
    ("🤫", "Öğretmeni Sessiz Bekleme"),
    ("✋", "Söz İsteyerek Konuşma"),
    ("📚", "Derse Hazırlıklı Gelme"),
    ("🧹", "Sınıf Temizliği"),
    ("🤝", "Dayanışma ve Yardımlaşmak"),
    ("📖", "Sessiz Okuma Etkinliği"),
    ("🎯", "Günlük Hedef Tamamlama"),
]

# ── PDF'lerden alınan öğretmen–sınıf eşleşmeleri ──────────────────────────
_OGRETMEN_SINIF: dict[str, list[str]] = {
    "ADEM AKGÜL":       ["5/A", "5/B", "6/A", "6/B", "7/A", "7/B", "8/A", "8/B"],
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
        CREATE TABLE IF NOT EXISTS olumlu_davranis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id    INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            kriter      TEXT    NOT NULL,
            tarih       TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS odevler (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id    INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            ders_adi    TEXT    NOT NULL,
            tema_adi    TEXT    NOT NULL,
            tarih       TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS odev_sonuclari (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            odev_id     INTEGER NOT NULL REFERENCES odevler(id),
            ogrenci_id  INTEGER NOT NULL REFERENCES ogrenciler(id),
            durum       TEXT    NOT NULL -- 'tamamladi' veya 'tamamlamadi'
        );
    """)
    con.commit()

    # Migration: eski DB'de sifre sütunu yoksa ekle
    sutunlar = [r[1] for r in con.execute(
        "PRAGMA table_info(ogretmenler)").fetchall()]
    if "sifre" not in sutunlar:
        con.execute("ALTER TABLE ogretmenler ADD COLUMN sifre TEXT NOT NULL DEFAULT ''")
        con.commit()

    sutunlar2 = [r[1] for r in con.execute("PRAGMA table_info(ogretmenler)").fetchall()]
    if "yetki" not in sutunlar2:
        con.execute(
            "ALTER TABLE ogretmenler ADD COLUMN yetki TEXT NOT NULL DEFAULT 'tam'"
        )
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
        _ogretmen_sinif_eslesmelerini_tamamla(con)

    _yardimci_tablolar_init(con)
    _rapor_arsiv_init(con)
    con.close()


def _yardimci_tablolar_init(con: sqlite3.Connection) -> None:
    """Davranış hedefi, veli randevusu, günlük yansıma, denetim günlüğü, admin_meta."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS davranis_hedefi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            ogrenci_id INTEGER REFERENCES ogrenciler(id),
            hedef_tik_max INTEGER NOT NULL DEFAULT 3,
            baslangic TEXT NOT NULL,
            bitis TEXT NOT NULL,
            aciklama TEXT,
            aktif INTEGER NOT NULL DEFAULT 1
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS randevu_talebi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            mesaj TEXT,
            talep_tarihi TEXT NOT NULL,
            durum TEXT NOT NULL DEFAULT 'bekliyor'
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS gunluk_yansima (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            metin TEXT NOT NULL,
            tarih TEXT NOT NULL,
            durum TEXT NOT NULL DEFAULT 'bekliyor',
            ogretmen_notu TEXT,
            degerlendiren_id INTEGER REFERENCES ogretmenler(id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS denetim_gunlugu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zaman TEXT NOT NULL,
            ogretmen_id INTEGER REFERENCES ogretmenler(id),
            islem TEXT NOT NULL,
            detay TEXT,
            ogrenci_id INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS admin_meta (
            anahtar TEXT PRIMARY KEY,
            deger TEXT NOT NULL
        )
    """)
    con.commit()


def _rapor_arsiv_yedek_init(con: sqlite3.Connection) -> None:
    """PDF arşivi manuel silindiğinde kayıtlar buraya taşınır; geri yükleme ile ana arşive dönülür."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS rapor_arsiv_yedek (
            yid INTEGER PRIMARY KEY AUTOINCREMENT,
            grup_id TEXT NOT NULL,
            silinme TEXT NOT NULL,
            kaynak_id INTEGER,
            olusturma TEXT NOT NULL,
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            ogretmen_adi TEXT NOT NULL,
            kapsam TEXT NOT NULL,
            sinif_id INTEGER,
            json_snapshot TEXT NOT NULL,
            pdf_blob BLOB NOT NULL,
            dosya_adi TEXT NOT NULL
        )
    """)
    con.commit()


def _rapor_arsiv_init(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS rapor_arsiv (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            olusturma TEXT NOT NULL,
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            ogretmen_adi TEXT NOT NULL,
            kapsam TEXT NOT NULL,
            sinif_id INTEGER,
            json_snapshot TEXT NOT NULL,
            pdf_blob BLOB NOT NULL,
            dosya_adi TEXT NOT NULL
        )
    """)
    con.commit()
    _rapor_arsiv_yedek_init(con)


def _bilgilendirme_init(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS bilgilendirmeler (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik      TEXT NOT NULL,
            metin       TEXT NOT NULL,
            hedef       TEXT NOT NULL DEFAULT 'herkes',
            yayinlayan  TEXT NOT NULL,
            tarih       TEXT NOT NULL,
            aktif       INTEGER NOT NULL DEFAULT 1
        )
    """)
    con.commit()


def bilgilendirme_ekle(baslik: str, metin: str, hedef: str, yayinlayan: str) -> dict:
    hedefler = {"herkes", "ogretmen", "ogrenci", "veli"}
    hedef = hedef if hedef in hedefler else "herkes"
    con = _conn()
    _bilgilendirme_init(con)
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = con.execute("""
        INSERT INTO bilgilendirmeler (baslik, metin, hedef, yayinlayan, tarih)
        VALUES (?, ?, ?, ?, ?)
    """, (baslik.strip(), metin.strip(), hedef, yayinlayan.strip(), tarih))
    con.commit()
    row = con.execute(
        "SELECT * FROM bilgilendirmeler WHERE id = ?",
        (cur.lastrowid,)
    ).fetchone()
    con.close()
    return dict(row)


def bilgilendirme_listesi(limit: int = 20) -> list[dict]:
    con = _conn()
    _bilgilendirme_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT *
        FROM bilgilendirmeler
        WHERE aktif = 1
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()]
    con.close()
    return rows


def bilgilendirme_yayinlayan_icin_sil(bilgi_id: int, yayinlayan: str) -> dict:
    """Yalnızca yayınlayan adı eşleşen kaydı pasifleştirir (aktif=0)."""
    yayinlayan = (yayinlayan or "").strip()
    con = _conn()
    _bilgilendirme_init(con)
    row = con.execute(
        "SELECT id, yayinlayan, aktif FROM bilgilendirmeler WHERE id = ?",
        (bilgi_id,),
    ).fetchone()
    if not row:
        con.close()
        return {"ok": False, "sebep": "bulunamadi"}
    r = dict(row)
    if r["yayinlayan"] != yayinlayan:
        con.close()
        return {"ok": False, "sebep": "yetkisiz"}
    if int(r.get("aktif") or 0) != 1:
        con.close()
        return {"ok": False, "sebep": "zaten_kaldirilmis"}
    con.execute(
        "UPDATE bilgilendirmeler SET aktif = 0 WHERE id = ? AND yayinlayan = ?",
        (bilgi_id, yayinlayan),
    )
    con.commit()
    con.close()
    return {"ok": True}


def son_bilgilendirme(hedef: str | None) -> dict | None:
    hedefler = {"ogretmen", "ogrenci", "veli"}
    hedef = hedef if hedef in hedefler else None
    if hedef is None:
        return None
    con = _conn()
    _bilgilendirme_init(con)
    row = con.execute("""
        SELECT *
        FROM bilgilendirmeler
        WHERE aktif = 1 AND hedef IN ('herkes', ?)
        ORDER BY id DESC
        LIMIT 1
    """, (hedef,)).fetchone()
    con.close()
    return dict(row) if row else None


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


def _ogretmen_sinif_eslesmelerini_tamamla(con: sqlite3.Connection) -> None:
    """Kodda güncellenen öğretmen-sınıf eşleşmelerini mevcut DB'ye ekler."""
    for ogretmen_adi, siniflar in _OGRETMEN_SINIF.items():
        og = con.execute(
            "SELECT id FROM ogretmenler WHERE ad_soyad = ?",
            (ogretmen_adi,),
        ).fetchone()
        if not og:
            continue
        for sinif_adi in siniflar:
            sinif = con.execute(
                "SELECT id FROM siniflar WHERE sinif_adi = ?",
                (sinif_adi,),
            ).fetchone()
            if not sinif:
                continue
            con.execute(
                "INSERT OR IGNORE INTO ogretmen_sinif (ogretmen_id, sinif_id) VALUES (?, ?)",
                (og["id"], sinif["id"]),
            )
    con.commit()


# ══════════════════════════════════════════════════════════════════════════
# Sorgular
# ══════════════════════════════════════════════════════════════════════════

def tum_ogretmenler() -> list[dict]:
    """Tüm öğretmenleri alfabetik sırayla döndürür."""
    con = _conn()
    _yardimci_tablolar_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT id, ad_soyad, sifre, COALESCE(yetki, 'tam') AS yetki
        FROM ogretmenler ORDER BY ad_soyad
    """).fetchall()]
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


def ogretmen_yetki_al(ogretmen_id: int) -> str:
    con = _conn()
    _yardimci_tablolar_init(con)
    row = con.execute(
        "SELECT COALESCE(yetki, 'tam') AS y FROM ogretmenler WHERE id = ?",
        (ogretmen_id,),
    ).fetchone()
    con.close()
    return str(row["y"]) if row else "tam"


def ogretmen_yetki_guncelle(ogretmen_id: int, yetki: str) -> None:
    if yetki not in ("tam", "rapor"):
        yetki = "tam"
    con = _conn()
    _yardimci_tablolar_init(con)
    con.execute("UPDATE ogretmenler SET yetki = ? WHERE id = ?", (yetki, ogretmen_id))
    con.commit()
    con.close()


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


def sinif_adi_tymm_seviyesi(sinif_adi: str) -> int | None:
    """5/A, 8-B vb. adların başındaki TYMM (5–8) düzeyini döndürür; yoksa None."""
    if not sinif_adi:
        return None
    s = sinif_adi.strip()
    m = re.match(r"^([5-8])(?:\s*[/\-.]|$)", s)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d{1,2})\b", s)
    if m:
        n = int(m.group(1))
        if 5 <= n <= 8:
            return n
    return None


def sinif_tymm_seviyesi(sinif_id: int) -> int | None:
    con = _conn()
    row = con.execute(
        "SELECT sinif_adi FROM siniflar WHERE id = ?", (sinif_id,)
    ).fetchone()
    con.close()
    if not row:
        return None
    return sinif_adi_tymm_seviyesi(row[0])


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


def tum_okul_ogrencileri() -> list[dict]:
    """Tüm sınıflardaki öğrencileri tik sayısına göre azalan sırada döndürür."""
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
    mevcut = int(
        con.execute(
            "SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id = ?",
            (ogrenci_id,),
        ).fetchone()[0]
    )
    if mevcut >= OLUMSUZ_TIK_LIMIT:
        con.close()
        return mevcut
    con.execute(
        "INSERT INTO tik_kayitlari (ogrenci_id, ogretmen_id, kriter, tarih) VALUES (?, ?, ?, ?)",
        (ogrenci_id, ogretmen_id, kriter, tarih)
    )
    con.commit()
    sayi = con.execute(
        "SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id = ?", (ogrenci_id,)
    ).fetchone()[0]
    con.close()
    try:
        denetim_kaydet(
            "tik_ekle",
            (kriter or "")[:300],
            ogretmen_id=ogretmen_id,
            ogrenci_id=ogrenci_id,
        )
    except Exception:
        pass
    return sayi


def ogrenci_tik_sayisi(ogrenci_id: int) -> int:
    con = _conn()
    sayi = int(
        con.execute(
            "SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id = ?",
            (ogrenci_id,),
        ).fetchone()[0]
    )
    con.close()
    return sayi


def tek_ogrenci_sifirla(ogrenci_id: int):
    con = _conn()
    _olumlu_davranis_migrate(con)
    con.execute("DELETE FROM tik_kayitlari WHERE ogrenci_id = ?", (ogrenci_id,))
    con.execute("DELETE FROM olumlu_davranis WHERE ogrenci_id = ?", (ogrenci_id,))
    con.commit()
    con.close()


def sinif_sifirla(sinif_id: int):
    """Bir sınıfın tüm tiklerini sıfırlar."""
    con = _conn()
    _olumlu_davranis_migrate(con)
    con.execute("""
        DELETE FROM tik_kayitlari
        WHERE ogrenci_id IN (SELECT id FROM ogrenciler WHERE sinif_id = ?)
    """, (sinif_id,))
    con.execute("DELETE FROM olumlu_davranis WHERE sinif_id = ?", (sinif_id,))
    con.commit()
    con.close()


def tum_tikleri_sifirla():
    con = _conn()
    con.execute("DELETE FROM tik_kayitlari")
    _olumlu_davranis_migrate(con)
    con.execute("DELETE FROM olumlu_davranis")
    con.commit()
    con.close()


def ogretmenin_ogrenci_tiklerini_sifirla(ogrenci_id: int, ogretmen_id: int) -> dict:
    """Öğretmenin verdiği olumsuz ve olumlu kayıtları tek öğrenci için temizler."""
    con = _conn()
    _olumlu_davranis_migrate(con)
    olumsuz = con.execute(
        "SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id = ? AND ogretmen_id = ?",
        (ogrenci_id, ogretmen_id),
    ).fetchone()[0]
    olumlu = con.execute(
        "SELECT COUNT(*) FROM olumlu_davranis WHERE ogrenci_id = ? AND ogretmen_id = ?",
        (ogrenci_id, ogretmen_id),
    ).fetchone()[0]
    con.execute(
        "DELETE FROM tik_kayitlari WHERE ogrenci_id = ? AND ogretmen_id = ?",
        (ogrenci_id, ogretmen_id),
    )
    con.execute(
        "DELETE FROM olumlu_davranis WHERE ogrenci_id = ? AND ogretmen_id = ?",
        (ogrenci_id, ogretmen_id),
    )
    con.commit()
    con.close()
    return {"olumsuz": int(olumsuz), "olumlu": int(olumlu)}


def ogretmenin_sinif_tiklerini_sifirla(sinif_id: int, ogretmen_id: int) -> dict:
    """Öğretmenin sınıfta verdiği olumsuz ve olumlu tikleri temizler."""
    con = _conn()
    _olumlu_davranis_migrate(con)
    olumsuz = con.execute(
        """
        SELECT COUNT(*) FROM tik_kayitlari
        WHERE ogretmen_id = ?
          AND ogrenci_id IN (SELECT id FROM ogrenciler WHERE sinif_id = ?)
        """,
        (ogretmen_id, sinif_id),
    ).fetchone()[0]
    olumlu = con.execute(
        "SELECT COUNT(*) FROM olumlu_davranis WHERE ogretmen_id = ? AND sinif_id = ?",
        (ogretmen_id, sinif_id),
    ).fetchone()[0]
    con.execute(
        """
        DELETE FROM tik_kayitlari
        WHERE ogretmen_id = ?
          AND ogrenci_id IN (SELECT id FROM ogrenciler WHERE sinif_id = ?)
        """,
        (ogretmen_id, sinif_id),
    )
    con.execute(
        "DELETE FROM olumlu_davranis WHERE ogretmen_id = ? AND sinif_id = ?",
        (ogretmen_id, sinif_id),
    )
    con.commit()
    con.close()
    return {"olumsuz": int(olumsuz), "olumlu": int(olumlu)}


# ══════════════════════════════════════════════════════════════════════════
# Olumlu Davranis + Super Lig
# ══════════════════════════════════════════════════════════════════════════

OLUMLU_TIK_XP = 5
OLUMSUZ_TIK_LIMIT = 12
OLUMLU_TIK_LIMIT = 36


def _olumlu_davranis_migrate(con: sqlite3.Connection) -> None:
    """Eski veritabanlarında tablo/sütun yoksa oluşturur (500 hatalarını önler)."""
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS olumlu_davranis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id    INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            kriter      TEXT NOT NULL,
            tarih       TEXT NOT NULL,
            ogrenci_id  INTEGER REFERENCES ogrenciler(id)
        )
        """
    )
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(olumlu_davranis)").fetchall()}
    except Exception:
        cols = set()
    if "ogrenci_id" not in cols:
        try:
            con.execute(
                "ALTER TABLE olumlu_davranis ADD COLUMN ogrenci_id INTEGER REFERENCES ogrenciler(id)"
            )
        except Exception:
            pass
    con.commit()


def olumlu_sinif_etkinlik_ekle(sinif_id: int, ogretmen_id: int, kriter: str) -> int:
    """Sınıf düzeyi olumlu (öğrenci yok): haftalık lig +1, XP yok."""
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    con = _conn()
    _olumlu_davranis_migrate(con)
    con.execute(
        """
        INSERT INTO olumlu_davranis (sinif_id, ogretmen_id, kriter, tarih, ogrenci_id)
        VALUES (?,?,?,?,NULL)
        """,
        (sinif_id, ogretmen_id, kriter.strip(), tarih),
    )
    puan = _lig_haftalik_puan_artir(con, sinif_id)
    con.commit()
    con.close()
    return puan


def olumlu_tik_ekle(ogrenci_id: int, sinif_id: int, ogretmen_id: int, kriter: str) -> dict:
    """Öğrenciye olumlu tik: XP + sınıf ligine katkı; her 3. olumlu tikte 1 olumsuz tik silinir."""
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    con = _conn()
    _olumlu_davranis_migrate(con)
    _gelisim_init(con)
    mevcut_olumlu = int(
        con.execute(
            "SELECT COUNT(*) FROM olumlu_davranis WHERE ogrenci_id=?",
            (ogrenci_id,),
        ).fetchone()[0]
    )
    if mevcut_olumlu >= OLUMLU_TIK_LIMIT:
        con.close()
        return {
            "ok": False,
            "sebep": f"Olumlu tik limiti doldu ({OLUMLU_TIK_LIMIT}/36).",
            "limit": OLUMLU_TIK_LIMIT,
            "olumlu_sira": mevcut_olumlu,
        }
    con.execute(
        """
        INSERT INTO olumlu_davranis (sinif_id, ogretmen_id, kriter, tarih, ogrenci_id)
        VALUES (?,?,?,?,?)
        """,
        (sinif_id, ogretmen_id, kriter.strip(), tarih, ogrenci_id),
    )
    gp = _gelisim_puan_ekle(con, ogrenci_id, OLUMLU_TIK_XP)
    lig_puan = _lig_haftalik_puan_artir(con, sinif_id)
    n = mevcut_olumlu + 1
    olumsuz_silindi = False
    if n > 0 and n % 3 == 0:
        eski = con.execute(
            """
            SELECT id FROM tik_kayitlari
            WHERE ogrenci_id=? ORDER BY tarih ASC LIMIT 1
            """,
            (ogrenci_id,),
        ).fetchone()
        if eski:
            con.execute("DELETE FROM tik_kayitlari WHERE id=?", (eski["id"],))
            olumsuz_silindi = True
    con.commit()
    tik_sayisi = int(
        con.execute(
            "SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id=?",
            (ogrenci_id,),
        ).fetchone()[0]
    )
    con.close()
    return {
        "lig_puan": lig_puan,
        "xp": int(gp["xp"]),
        "olumsuz_silindi": olumsuz_silindi,
        "tik_sayisi": tik_sayisi,
        "olumlu_sira": n,
    }


def ogrenci_olumlu_tik_sayisi(ogrenci_id: int) -> int:
    con = _conn()
    _olumlu_davranis_migrate(con)
    n = con.execute(
        "SELECT COUNT(*) FROM olumlu_davranis WHERE ogrenci_id=?",
        (ogrenci_id,),
    ).fetchone()[0]
    con.close()
    return int(n)


def ogrenci_olumlu_tik_sayilari(ogrenci_ids: list[int]) -> dict[int, int]:
    """Birden fazla öğrenci için olumlu tik sayıları (id -> sayı)."""
    if not ogrenci_ids:
        return {}
    con = _conn()
    _olumlu_davranis_migrate(con)
    benzersiz = list(dict.fromkeys(int(i) for i in ogrenci_ids))
    placeholders = ",".join("?" * len(benzersiz))
    rows = con.execute(
        f"""
        SELECT ogrenci_id, COUNT(*) AS n
        FROM olumlu_davranis
        WHERE ogrenci_id IN ({placeholders})
        GROUP BY ogrenci_id
        """,
        benzersiz,
    ).fetchall()
    con.close()
    return {int(r["ogrenci_id"]): int(r["n"]) for r in rows}


def lig_siralama() -> list[dict]:
    hafta = _bu_hafta_pazartesi()
    con = _conn()
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
    hafta = _bu_hafta_pazartesi()
    con = _conn()
    con.execute("UPDATE lig SET puan=0, hafta_basi=?", (hafta,))
    con.commit()
    con.close()


def sinif_olumlu_gecmis(sinif_id: int) -> list[dict]:
    con = _conn()
    _olumlu_davranis_migrate(con)
    rows = [dict(r) for r in con.execute("""
        SELECT od.kriter, od.tarih, og.ad_soyad AS ogretmen,
               o.ad_soyad AS ogrenci
        FROM olumlu_davranis od
        JOIN ogretmenler og ON og.id = od.ogretmen_id
        LEFT JOIN ogrenciler o ON o.id = od.ogrenci_id
        WHERE od.sinif_id = ?
        ORDER BY od.tarih DESC
        LIMIT 30
    """, (sinif_id,)).fetchall()]
    con.close()
    return rows


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

VAR_INCELEME_OGRETMENLER = ["ADEM AKGÜL", "YUSUF ERTÜRK"]


def _mac_tablosu_olustur(con):
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


def _lig_mac_tablo_eksik_sutunlar(con: sqlite3.Connection) -> None:
    """Eski DB'lerde lig / lig_mac_tablo sütun eksikse ALTER (ör. `ag` yokken 500)."""
    try:
        lig_cols = {r[1] for r in con.execute("PRAGMA table_info(lig)").fetchall()}
    except Exception:
        lig_cols = set()
    if lig_cols and "hafta_basi" not in lig_cols:
        try:
            con.execute("ALTER TABLE lig ADD COLUMN hafta_basi TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass
    try:
        mt_cols = {r[1] for r in con.execute("PRAGMA table_info(lig_mac_tablo)").fetchall()}
    except Exception:
        mt_cols = set()
    if not mt_cols:
        return
    eksik = [
        ("galibiyet", "INTEGER NOT NULL DEFAULT 0"),
        ("beraberlik", "INTEGER NOT NULL DEFAULT 0"),
        ("maglubiyet", "INTEGER NOT NULL DEFAULT 0"),
        ("puan", "INTEGER NOT NULL DEFAULT 0"),
        ("ag", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for ad, decl in eksik:
        if ad not in mt_cols:
            try:
                con.execute(f"ALTER TABLE lig_mac_tablo ADD COLUMN {ad} {decl}")
            except Exception:
                pass
            mt_cols.add(ad)


def _ensure_lig_tablolari(con) -> None:
    """İlk kullanımda `lig` ve `lig_mac_tablo` yoksa oluşturur (commit gerektirmez)."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS lig (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            puan INTEGER NOT NULL DEFAULT 0,
            hafta_basi TEXT NOT NULL DEFAULT ''
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS lig_mac_tablo (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            galibiyet INTEGER DEFAULT 0,
            beraberlik INTEGER DEFAULT 0,
            maglubiyet INTEGER DEFAULT 0,
            puan INTEGER DEFAULT 0,
            ag INTEGER DEFAULT 0
        )
    """)
    _lig_mac_tablo_eksik_sutunlar(con)


def _lig_haftalik_puan_artir(con, sinif_id: int) -> int:
    """Haftalık Süper Lig (`lig`) ve yayın tablosu (`lig_mac_tablo`) puanını +1 artırır."""
    _ensure_lig_tablolari(con)
    hafta = _bu_hafta_pazartesi()
    mevcut = con.execute(
        "SELECT puan, hafta_basi FROM lig WHERE sinif_id=?", (sinif_id,)
    ).fetchone()
    if not mevcut:
        con.execute(
            "INSERT INTO lig (sinif_id, puan, hafta_basi) VALUES (?,1,?)",
            (sinif_id, hafta),
        )
        puan = 1
    elif mevcut["hafta_basi"] != hafta:
        con.execute(
            "UPDATE lig SET puan=1, hafta_basi=? WHERE sinif_id=?",
            (hafta, sinif_id),
        )
        puan = 1
    else:
        con.execute("UPDATE lig SET puan=puan+1 WHERE sinif_id=?", (sinif_id,))
        puan = mevcut["puan"] + 1
    tablo_var = con.execute(
        "SELECT sinif_id FROM lig_mac_tablo WHERE sinif_id=?", (sinif_id,)
    ).fetchone()
    if tablo_var:
        con.execute(
            "UPDATE lig_mac_tablo SET puan = puan + 1, ag = ag + 1 WHERE sinif_id=?",
            (sinif_id,),
        )
    else:
        con.execute(
            "INSERT INTO lig_mac_tablo (sinif_id, galibiyet, beraberlik, maglubiyet, puan, ag) "
            "VALUES (?, 0, 0, 0, 1, 1)",
            (sinif_id,),
        )
    return puan


def _lig_puan_artir_miktar(con, sinif_id: int, miktar: int) -> int:
    """Lig tablosunda bir sinifa verilen miktar kadar normal puan ekler."""
    miktar = max(0, int(miktar or 0))
    _ensure_lig_tablolari(con)
    hafta = _bu_hafta_pazartesi()
    mevcut = con.execute(
        "SELECT puan, hafta_basi FROM lig WHERE sinif_id=?", (sinif_id,)
    ).fetchone()
    if not mevcut:
        con.execute(
            "INSERT INTO lig (sinif_id, puan, hafta_basi) VALUES (?,?,?)",
            (sinif_id, miktar, hafta),
        )
        puan = miktar
    elif mevcut["hafta_basi"] != hafta:
        con.execute(
            "UPDATE lig SET puan=?, hafta_basi=? WHERE sinif_id=?",
            (miktar, hafta, sinif_id),
        )
        puan = miktar
    else:
        con.execute("UPDATE lig SET puan=puan+? WHERE sinif_id=?", (miktar, sinif_id))
        puan = mevcut["puan"] + miktar
    tablo_var = con.execute(
        "SELECT sinif_id FROM lig_mac_tablo WHERE sinif_id=?", (sinif_id,)
    ).fetchone()
    if tablo_var:
        con.execute(
            "UPDATE lig_mac_tablo SET puan=puan+?, ag=ag+1 WHERE sinif_id=?",
            (miktar, sinif_id),
        )
    else:
        con.execute(
            "INSERT INTO lig_mac_tablo (sinif_id, galibiyet, beraberlik, maglubiyet, puan, ag) "
            "VALUES (?, 0, 0, 0, ?, 1)",
            (sinif_id, miktar),
        )
    return puan


def lig_puan_artir(sinif_id: int, miktar: int = 3) -> dict:
    con = _conn()
    try:
        puan = _lig_puan_artir_miktar(con, sinif_id, miktar)
        con.commit()
        return {"ok": True, "puan": puan}
    finally:
        con.close()


def gunluk_mac_olustur() -> list[dict]:
    import random
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn()
    _mac_tablosu_olustur(con)
    mevcut = con.execute(
        "SELECT COUNT(*) FROM lig_maclar WHERE tarih=?", (bugun,)
    ).fetchone()[0]
    if mevcut > 0:
        con.close()
        return bugun_maclar()
    siniflar = [dict(r) for r in con.execute(
        "SELECT id, sinif_adi FROM siniflar ORDER BY sinif_adi"
    ).fetchall()]
    random.shuffle(siniflar)
    if len(siniflar) % 2 != 0:
        siniflar = siniflar[:-1]
    esler = [(siniflar[i], siniflar[i+1]) for i in range(0, len(siniflar), 2)]
    gorevler = random.sample(LIG_GOREVLER, min(len(esler), len(LIG_GOREVLER)))
    while len(gorevler) < len(esler):
        gorevler += random.sample(LIG_GOREVLER, min(len(esler)-len(gorevler), len(LIG_GOREVLER)))
    for i, (s1, s2) in enumerate(esler):
        con.execute("""
            INSERT INTO lig_maclar (sinif1_id, sinif2_id, gorev, tarih, seans)
            VALUES (?, ?, ?, ?, 'sabah')
        """, (s1["id"], s2["id"], gorevler[i], bugun))
    gorevler2 = random.sample(LIG_GOREVLER, min(len(esler), len(LIG_GOREVLER)))
    while len(gorevler2) < len(esler):
        gorevler2 += random.sample(LIG_GOREVLER, min(len(esler)-len(gorevler2), len(LIG_GOREVLER)))
    for i, (s1, s2) in enumerate(esler):
        con.execute("""
            INSERT INTO lig_maclar (sinif1_id, sinif2_id, gorev, tarih, seans)
            VALUES (?, ?, ?, ?, 'ogleden_sonra')
        """, (s2["id"], s1["id"], gorevler2[i], bugun))
    con.commit()
    con.close()
    return bugun_maclar()


def bugun_maclar() -> list[dict]:
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
    oylar = [dict(r) for r in con.execute("""
        SELECT oy.secilen_id, og.ad_soyad AS ogretmen, s.sinif_adi
        FROM lig_oylari oy
        JOIN ogretmenler og ON og.id = oy.ogretmen_id
        JOIN siniflar s ON s.id = oy.secilen_id
        WHERE oy.mac_id = ?
    """, (mac_id,)).fetchall()]
    d["oylar"] = oylar
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


def mac_sonucu_gir(mac_id: int, s1_tamamlayan: int, s1_toplam: int,
                   s2_tamamlayan: int, s2_toplam: int) -> dict:
    con = _conn()
    _mac_tablosu_olustur(con)
    mac = dict(con.execute("SELECT * FROM lig_maclar WHERE id=?", (mac_id,)).fetchone())
    oran1 = s1_tamamlayan / s1_toplam if s1_toplam > 0 else 0
    oran2 = s2_tamamlayan / s2_toplam if s2_toplam > 0 else 0
    if oran1 > oran2:
        durum = "tamamlandi"; kazanan = mac["sinif1_id"]; kaybeden = mac["sinif2_id"]
    elif oran2 > oran1:
        durum = "tamamlandi"; kazanan = mac["sinif2_id"]; kaybeden = mac["sinif1_id"]
    else:
        durum = "var_incelemesi"; kazanan = None; kaybeden = None
    con.execute("""
        UPDATE lig_maclar SET s1_tamamlayan=?, s1_toplam=?,
            s2_tamamlayan=?, s2_toplam=?, kazanan_id=?, durum=? WHERE id=?
    """, (s1_tamamlayan, s1_toplam, s2_tamamlayan, s2_toplam, kazanan, durum, mac_id))
    if durum == "tamamlandi":
        _puan_guncelle(con, kazanan, kaybeden)
    con.commit()
    con.close()
    return {"durum": durum, "kazanan_id": kazanan}


def mac_oy_ver(mac_id: int, ogretmen_id: int, secilen_sinif_id: int) -> dict:
    con = _conn()
    _mac_tablosu_olustur(con)
    con.execute("""
        INSERT OR REPLACE INTO lig_oylari (mac_id, ogretmen_id, secilen_id)
        VALUES (?, ?, ?)
    """, (mac_id, ogretmen_id, secilen_sinif_id))
    con.commit()
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
        s1_oy = sum(1 for o in oylar if o["secilen_id"] == mac["sinif1_id"])
        s2_oy = sum(1 for o in oylar if o["secilen_id"] == mac["sinif2_id"])
        if s1_oy > s2_oy:
            kazanan = mac["sinif1_id"]; kaybeden = mac["sinif2_id"]
        elif s2_oy > s1_oy:
            kazanan = mac["sinif2_id"]; kaybeden = mac["sinif1_id"]
        else:
            ilk_hakem = hakem_idler[0] if hakem_idler else None
            ilk_oy = next((o["secilen_id"] for o in oylar if o["ogretmen_id"] == ilk_hakem), None)
            kazanan = ilk_oy or mac["sinif1_id"]
            kaybeden = mac["sinif2_id"] if kazanan == mac["sinif1_id"] else mac["sinif1_id"]
        con.execute("UPDATE lig_maclar SET kazanan_id=?, durum='tamamlandi' WHERE id=?",
                    (kazanan, mac_id))
        _puan_guncelle(con, kazanan, kaybeden)
        con.commit()
        sonuc = {"durum": "tamamlandi", "kazanan_id": kazanan}
    con.close()
    return sonuc


def _puan_guncelle(con, kazanan_id, kaybeden_id):
    for sid in [kazanan_id, kaybeden_id]:
        if not con.execute("SELECT 1 FROM lig_mac_tablo WHERE sinif_id=?", (sid,)).fetchone():
            con.execute("INSERT INTO lig_mac_tablo (sinif_id) VALUES (?)", (sid,))
    con.execute("""
        UPDATE lig_mac_tablo SET galibiyet=galibiyet+1, puan=puan+3, ag=ag+1
        WHERE sinif_id=?
    """, (kazanan_id,))
    con.execute("""
        UPDATE lig_mac_tablo SET maglubiyet=maglubiyet+1 WHERE sinif_id=?
    """, (kaybeden_id,))


def lig_puan_tablosu() -> list[dict]:
    con  = _conn()
    _ensure_lig_tablolari(con)
    _gelisim_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT s.id AS sinif_id, s.sinif_adi,
               COALESCE(l.puan,0) AS puan,
               COALESCE(SUM(gp.xp),0) AS toplam_xp,
               COALESCE(l.puan,0) + COALESCE(SUM(gp.xp),0) AS genel_puan
        FROM siniflar s
        LEFT JOIN lig l ON l.sinif_id = s.id
        LEFT JOIN ogrenciler o ON o.sinif_id = s.id
        LEFT JOIN gelisim_puan gp ON gp.ogrenci_id = o.id
        GROUP BY s.id, s.sinif_adi, l.puan
        ORDER BY genel_puan DESC, toplam_xp DESC, puan DESC, s.sinif_adi
    """).fetchall()]
    con.close()
    return rows


def lig_mac_tablo_sifirla():
    con = _conn()
    _mac_tablosu_olustur(con)
    _ensure_lig_tablolari(con)
    con.execute("DELETE FROM lig_oylari")
    con.execute("DELETE FROM lig_maclar")
    con.execute("DELETE FROM lig_mac_tablo")
    con.execute("UPDATE lig SET puan = 0, hafta_basi = ?", (_bu_hafta_pazartesi(),))
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
    import random
    con = _conn()
    _kadro_tablosu_olustur(con)
    con.execute("DELETE FROM kadro_ogrenci WHERE sinif_id=?", (sinif_id,))
    ogrenciler = [dict(r) for r in con.execute(
        "SELECT id, ad_soyad, ogr_no FROM ogrenciler WHERE sinif_id=? ORDER BY ogr_no",
        (sinif_id,)
    ).fetchall()]
    mevki_liste = list(MEVKILER)
    random.shuffle(mevki_liste)
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
    con = _conn()
    _kadro_tablosu_olustur(con)
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
    mevki_map = {m[0]: (m[1], m[2]) for m in MEVKILER}
    for r in rows:
        m = mevki_map.get(r["mevki_no"], ("❓", "Bilinmeyen Mevki"))
        r["emoji"]  = m[0]
        r["mevki"]  = m[1]
    return rows


def tum_siniflar_kadro() -> dict[int, list[dict]]:
    con = _conn()
    siniflar = [dict(r) for r in con.execute("SELECT id FROM siniflar").fetchall()]
    con.close()
    return {s["id"]: sinif_kadro_getir(s["id"]) for s in siniflar}


# ══════════════════════════════════════════════════════════════════════════
# Kart Sistemi
# ══════════════════════════════════════════════════════════════════════════

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
    kriter = f"{'Sari' if kart_turu == 'sari' else 'Kirmizi'} Kart - {neden}"
    tik_sayisi = 3 if kart_turu == "sari" else 6
    for _ in range(tik_sayisi):
        tik_ekle(ogrenci_id, ogretmen_id, kriter)
    sonuc = {"kart_turu": kart_turu, "tik_eklendi": tik_sayisi, "puan_cezasi": 0}
    if kart_turu == "kirmizi":
        con = _conn()
        _mac_tablosu_olustur(con)
        con.execute("""
            UPDATE lig_mac_tablo SET puan = MAX(0, puan - 3), ag = ag - 3 WHERE sinif_id = ?
        """, (sinif_id,))
        var = con.execute(
            "SELECT sinif_id FROM lig_mac_tablo WHERE sinif_id=?", (sinif_id,)
        ).fetchone()
        if not var:
            con.execute(
                "INSERT INTO lig_mac_tablo (sinif_id, puan, ag) VALUES (?,0,-3)", (sinif_id,)
            )
        con.commit()
        con.close()
        sonuc["puan_cezasi"] = 3
    return sonuc


def mac_kartlari(mac_id: int) -> list[dict]:
    con = _conn()
    _kart_tablosu_olustur(con)
    rows = [dict(r) for r in con.execute("""
        SELECT k.id, k.kart_turu, k.neden, k.tarih,
               o.ad_soyad AS ogrenci_adi, s.sinif_adi, og.ad_soyad AS ogretmen_adi
        FROM kart_kayitlari k
        JOIN ogrenciler o  ON o.id  = k.ogrenci_id
        JOIN siniflar s    ON s.id  = k.sinif_id
        JOIN ogretmenler og ON og.id = k.ogretmen_id
        WHERE k.mac_id = ?
        ORDER BY k.tarih
    """, (mac_id,)).fetchall()]
    con.close()
    return rows


# ══════════════════════════════════════════════════════════════════════════
# Gamification
# ══════════════════════════════════════════════════════════════════════════

SEVIYELER = [
    (0,   "🥚", "Yumurta"),
    (10,  "🐣", "Civciv"),
    (25,  "🦅", "Kartal"),
    (50,  "🦁", "Aslan"),
    (100, "👑", "Efsane"),
]

MUFETTIS_YETKILILERI = ["Adem Akgul", "Yusuf Erturk"]

ROZET_TANIMI = {
    "pozitif_yildiz": ("💚", "Pozitif Yıldız",     "Olumlu davranış veya öğretmen onayı ile"),
    "temizlik_7":     ("🧹", "Tertemiz",          "7 gun hic tik almadi"),
    "sinif_yildizi":  ("⭐", "Sinif Yildizi",      "Haftanin en cok olumlu puanli ogrencisi"),
    "seri_yildiz":    ("⚡", "Seri Yildiz",        "3 mac ust uste kazanildi"),
    "donusum":        ("🦋", "Donusum",             "Kirmizi karttan sonra 5 gun temiz kalindi"),
    "mufettis_iyisi": ("🌟","Gizli Kahraman", "Gunun gizli kahramani secildi"),
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


def _gami_init(con):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS rozet_kayitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER REFERENCES ogrenciler(id),
            sinif_id INTEGER REFERENCES siniflar(id),
            rozet_kodu TEXT NOT NULL, tarih TEXT NOT NULL,
            UNIQUE(ogrenci_id, rozet_kodu)
        );
        CREATE TABLE IF NOT EXISTS sinif_rozet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id INTEGER REFERENCES siniflar(id),
            rozet_kodu TEXT NOT NULL, tarih TEXT NOT NULL,
            UNIQUE(sinif_id, rozet_kodu)
        );
        CREATE TABLE IF NOT EXISTS sinif_seri (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            guncel_seri INTEGER DEFAULT 0,
            en_uzun_seri INTEGER DEFAULT 0,
            son_guncelleme TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS gunluk_gorev (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT NOT NULL UNIQUE, gorev TEXT NOT NULL,
            puan INTEGER NOT NULL DEFAULT 3, tamamlayan_ids TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS gizli_mufettis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT NOT NULL UNIQUE,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            sonuc TEXT DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS alkis_kuponu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            mesaj TEXT DEFAULT 'Harika is!', tarih TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sezon_puan (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            puan INTEGER DEFAULT 0, sezon TEXT NOT NULL DEFAULT '2025-2026'
        );
        CREATE TABLE IF NOT EXISTS ittifak_gorev (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT NOT NULL,
            sinif1_id INTEGER NOT NULL REFERENCES siniflar(id),
            sinif2_id INTEGER NOT NULL REFERENCES siniflar(id),
            gorev TEXT NOT NULL, durum TEXT NOT NULL DEFAULT 'bekliyor',
            puan INTEGER NOT NULL DEFAULT 5
        );
        CREATE TABLE IF NOT EXISTS sans_carki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_id INTEGER REFERENCES lig_maclar(id),
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            sonuc TEXT NOT NULL, puan_deg INTEGER DEFAULT 0, tarih TEXT NOT NULL
        );
    """)
    con.commit()


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
    for r in con.execute("""
        SELECT rk.rozet_kodu, rk.tarih, o.ad_soyad AS sahip, s.sinif_adi, 'ogrenci' AS tip
        FROM rozet_kayitlari rk
        JOIN ogrenciler o ON o.id = rk.ogrenci_id
        JOIN siniflar s ON s.id = rk.sinif_id
        ORDER BY rk.tarih DESC LIMIT ?
    """, (limit,)).fetchall():
        d = dict(r)
        em, ra = rozet_emojileri_ve_metin(d["rozet_kodu"])
        d["emoji"] = em
        d["rozet_adi"] = ra
        rows.append(d)
    for r in con.execute("""
        SELECT sr.rozet_kodu, sr.tarih, s.sinif_adi AS sahip, s.sinif_adi, 'sinif' AS tip
        FROM sinif_rozet sr
        JOIN siniflar s ON s.id = sr.sinif_id
        ORDER BY sr.tarih DESC LIMIT ?
    """, (limit,)).fetchall():
        d = dict(r)
        em, ra = rozet_emojileri_ve_metin(d["rozet_kodu"])
        d["emoji"] = em
        d["rozet_adi"] = ra
        rows.append(d)
    con.close()
    rows.sort(key=lambda x: x["tarih"], reverse=True)
    return rows[:limit]


def sinif_seri_guncelle(sinif_id: int, temiz_mi: bool):
    con = _conn(); _gami_init(con)
    bugun = datetime.now().strftime("%Y-%m-%d")
    mevcut = con.execute("SELECT * FROM sinif_seri WHERE sinif_id=?", (sinif_id,)).fetchone()
    if not mevcut:
        con.execute("INSERT INTO sinif_seri (sinif_id,guncel_seri,en_uzun_seri,son_guncelleme) VALUES(?,?,0,?)",
                    (sinif_id, 1 if temiz_mi else 0, bugun))
    elif mevcut["son_guncelleme"] == bugun:
        con.close(); return
    else:
        yeni_seri = (mevcut["guncel_seri"] + 1) if temiz_mi else 0
        en_uzun   = max(mevcut["en_uzun_seri"], yeni_seri)
        con.execute("UPDATE sinif_seri SET guncel_seri=?,en_uzun_seri=?,son_guncelleme=? WHERE sinif_id=?",
                    (yeni_seri, en_uzun, bugun, sinif_id))
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


def bugun_gorev() -> dict:
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
    olumlu_sinif_etkinlik_ekle(sinif_id, 1, f"Gunluk Gorev: {row['gorev']}")
    return {"ok": True, "puan": row["puan"]}


def _ittifak_migrate(con) -> None:
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
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn(); _gami_init(con)
    row   = con.execute("SELECT m.*,o.ad_soyad,s.sinif_adi FROM gizli_mufettis m "
                        "JOIN ogrenciler o ON o.id=m.ogrenci_id "
                        "JOIN siniflar s ON s.id=m.sinif_id "
                        "WHERE m.tarih=?", (bugun,)).fetchone()
    con.close()
    return dict(row) if row else None


def mufettis_belirle(ogrenci_id: int) -> dict:
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn(); _gami_init(con)
    mevcut = con.execute("SELECT id FROM gizli_mufettis WHERE tarih=?", (bugun,)).fetchone()
    if mevcut:
        con.close(); return {"ok": False, "sebep": "Bugunun gizli kahramani zaten secildi"}
    ogr = con.execute("SELECT id, sinif_id FROM ogrenciler WHERE id=?", (ogrenci_id,)).fetchone()
    if not ogr:
        con.close(); return {"ok": False, "sebep": "Ogrenci bulunamadi"}
    con.execute("INSERT INTO gizli_mufettis (tarih,ogrenci_id,sinif_id,sonuc) VALUES(?,?,?,'kahraman')",
                (bugun, ogrenci_id, ogr["sinif_id"]))
    _gelisim_init(con)
    puan_kaydi = _gelisim_puan_ekle(con, ogrenci_id, 10)
    con.commit(); con.close()
    rozet_ver_ogrenci(ogrenci_id, ogr["sinif_id"], "mufettis_iyisi")
    return {"ok": True, "xp": 10, "puan": puan_kaydi}


def mufettis_degerlendir(mufettis_id: int, sonuc: str) -> dict:
    con = _conn(); _gami_init(con)
    row = con.execute("SELECT * FROM gizli_mufettis WHERE id=?", (mufettis_id,)).fetchone()
    if not row or row["sonuc"]:
        con.close(); return {"ok": False}
    con.execute("UPDATE gizli_mufettis SET sonuc=? WHERE id=?", (sonuc, mufettis_id))
    con.commit(); con.close()
    if sonuc == "iyi":
        olumlu_tik_ekle(
            row["ogrenci_id"], row["sinif_id"], 1,
            "Gizli Mufettis: Mukemmel davranis",
        )
        rozet_ver_ogrenci(row["ogrenci_id"], row["sinif_id"], "mufettis_iyisi")
    return {"ok": True}


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
        SELECT s.id AS sinif_id, s.sinif_adi, COALESCE(sp.puan,0) AS sezon_puan
        FROM siniflar s LEFT JOIN sezon_puan sp ON sp.sinif_id=s.id
        ORDER BY COALESCE(sp.puan,0) DESC, s.sinif_adi
    """).fetchall()]
    con.close()
    return rows


def ittifak_olustur(sinif1_id: int, sinif2_id: int) -> dict:
    import random
    con = _conn(); _gami_init(con)
    tarih = datetime.now().strftime("%Y-%m-%d")
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
        WHERE ig.tarih=? ORDER BY ig.id DESC
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
    olumlu_sinif_etkinlik_ekle(row["sinif1_id"], 1, "Ittifak Gorevi Tamamlandi")
    olumlu_sinif_etkinlik_ekle(row["sinif2_id"], 1, "Ittifak Gorevi Tamamlandi")
    sezon_puan_ekle(row["sinif1_id"], row["puan"])
    sezon_puan_ekle(row["sinif2_id"], row["puan"])
    return {"ok": True}


def ittifak_ogrenci_talebi(sinif1_id: int, sinif2_id: int, seans: str) -> dict:
    import random
    if seans not in ("sabah", "ogleden_sonra"):
        return {"ok": False, "sebep": "Gecersiz seans"}
    con = _conn(); _gami_init(con); _ittifak_migrate(con)
    tarih = datetime.now().strftime("%Y-%m-%d")
    var = con.execute(
        "SELECT id FROM ittifak_gorev WHERE tarih=? AND seans=? "
        "AND ((sinif1_id=? AND sinif2_id=?) OR (sinif1_id=? AND sinif2_id=?))",
        (tarih, seans, sinif1_id, sinif2_id, sinif2_id, sinif1_id)
    ).fetchone()
    if var:
        con.close(); return {"ok": False, "sebep": "Bu seans icin zaten talep var"}
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
    con = _conn(); _gami_init(con)
    row = con.execute("SELECT * FROM ittifak_gorev WHERE id=?", (ittifak_id,)).fetchone()
    if not row or row["durum"] != "ogrenci_talebi":
        con.close(); return {"ok": False, "sebep": "Talep bulunamadi ya da zaten islendi"}
    con.execute("UPDATE ittifak_gorev SET durum='bekliyor' WHERE id=?", (ittifak_id,))
    con.commit(); con.close()
    return {"ok": True}


def ittifak_reddet(ittifak_id: int) -> dict:
    con = _conn(); _gami_init(con)
    row = con.execute("SELECT * FROM ittifak_gorev WHERE id=?", (ittifak_id,)).fetchone()
    if not row or row["durum"] != "ogrenci_talebi":
        con.close(); return {"ok": False}
    con.execute("UPDATE ittifak_gorev SET durum='reddedildi' WHERE id=?", (ittifak_id,))
    con.commit(); con.close()
    return {"ok": True}


def bekleyen_ogrenci_talepleri() -> list[dict]:
    bugun = datetime.now().strftime("%Y-%m-%d")
    con   = _conn(); _gami_init(con); _ittifak_migrate(con)
    rows  = [dict(r) for r in con.execute("""
        SELECT ig.*, s1.sinif_adi AS sinif1_adi, s2.sinif_adi AS sinif2_adi
        FROM ittifak_gorev ig
        JOIN siniflar s1 ON s1.id=ig.sinif1_id
        JOIN siniflar s2 ON s2.id=ig.sinif2_id
        WHERE ig.tarih=? AND ig.durum='ogrenci_talebi' ORDER BY ig.id DESC
    """, (bugun,)).fetchall()]
    con.close()
    return rows


def sans_carki_cevir(mac_id: int, sinif_id: int) -> dict:
    import random
    con = _conn(); _gami_init(con)
    _mac_tablosu_olustur(con)
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


def tik_dondur(ogrenci_id: int, ogretmen_id: int) -> dict:
    bugun = datetime.now().date()
    con   = _conn()
    son3 = con.execute("""
        SELECT COUNT(*) FROM tik_kayitlari
        WHERE ogrenci_id=? AND tarih >= ?
    """, (ogrenci_id, str(bugun - __import__('datetime').timedelta(days=3)))).fetchone()[0]
    if son3 > 0:
        con.close()
        return {"ok": False, "sebep": "Son 3 gunde tik var, af hakki kazanilmadi"}
    toplam = con.execute("SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id=?", (ogrenci_id,)).fetchone()[0]
    if toplam == 0:
        con.close()
        return {"ok": False, "sebep": "Zaten hic tik yok"}
    son_tik = con.execute("SELECT id FROM tik_kayitlari WHERE ogrenci_id=? ORDER BY tarih DESC LIMIT 1",
                          (ogrenci_id,)).fetchone()
    con.execute("DELETE FROM tik_kayitlari WHERE id=?", (son_tik["id"],))
    con.commit(); con.close()
    try:
        denetim_kaydet(
            "tik_dondur",
            "Son tik silindi",
            ogretmen_id=ogretmen_id,
            ogrenci_id=ogrenci_id,
        )
    except Exception:
        pass
    return {"ok": True, "silinen_tik": 1}


def denetim_kaydet(
    islem: str,
    detay: str = "",
    ogretmen_id: int | None = None,
    ogrenci_id: int | None = None,
) -> None:
    con = _conn()
    _yardimci_tablolar_init(con)
    z = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute(
        """
        INSERT INTO denetim_gunlugu (zaman, ogretmen_id, islem, detay, ogrenci_id)
        VALUES (?,?,?,?,?)
        """,
        (z, ogretmen_id, islem[:80], (detay or "")[:2000], ogrenci_id),
    )
    con.commit()
    con.close()


def denetim_listesi(limit: int = 300) -> list[dict]:
    con = _conn()
    _yardimci_tablolar_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT d.*, og.ad_soyad AS ogretmen_adi,
               o.ad_soyad AS ogrenci_ad
        FROM denetim_gunlugu d
        LEFT JOIN ogretmenler og ON og.id = d.ogretmen_id
        LEFT JOIN ogrenciler o ON o.id = d.ogrenci_id
        ORDER BY d.id DESC
        LIMIT ?
    """, (limit,)).fetchall()]
    con.close()
    return rows


# ══════════════════════════════════════════════════════════════════════════
# Veri Sifirlama
# ══════════════════════════════════════════════════════════════════════════

_SIFIRLANACAK_TABLOLAR = [
    "tik_kayitlari", "olumlu_davranis", "davranis_hedefi", "randevu_talebi",
    "gunluk_yansima", "lig", "lig_maclar", "lig_oylari",
    "lig_mac_tablo", "kadro_ogrenci", "kart_kayitlari", "rozet_kayitlari",
    "sinif_rozet", "sinif_seri", "gunluk_gorev", "gizli_mufettis",
    "alkis_kuponu", "sezon_puan", "ittifak_gorev", "sans_carki",
    "taktik_formasyonu", "quiz_sonuclari", "odev_tamamlayanlar", "odevler",
    "gelisim_puan", "gelisim_gorevleri", "sandik_kayitlari", "telafi_gorevleri",
    "tebrik_kartlari", "avatar_envanter", "ogretmen_notlari", "hikaye_ilerleme",
    "oyun_puanlari", "bilgilendirmeler",
]


def _sistem_yedek_init(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS sistem_yedekleri (
            yedek_id INTEGER PRIMARY KEY AUTOINCREMENT,
            olusturma TEXT NOT NULL,
            ogretmen_id INTEGER,
            ogretmen_adi TEXT NOT NULL,
            tablo_sayisi INTEGER NOT NULL DEFAULT 0,
            kayit_sayisi INTEGER NOT NULL DEFAULT 0,
            json_yedek TEXT NOT NULL
        )
    """)
    con.commit()


def _tablo_satirlari_jsona_hazirla(rows: list[sqlite3.Row]) -> list[dict]:
    hazir = []
    for row in rows:
        item = {}
        for key in row.keys():
            val = row[key]
            if isinstance(val, bytes):
                item[key] = {"__bytes_hex__": val.hex()}
            else:
                item[key] = val
        hazir.append(item)
    return hazir


def sistem_yedegi_olustur(ogretmen_id: int | None, ogretmen_adi: str = "") -> dict:
    """Tam sıfırlama öncesi silinecek kullanıcı verilerini JSON olarak saklar."""
    con = _conn()
    _sistem_yedek_init(con)
    olusturma = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "olusturma": olusturma,
        "ogretmen_id": ogretmen_id,
        "ogretmen_adi": ogretmen_adi or "",
        "tablolar": {},
    }
    toplam = 0
    for tablo in _SIFIRLANACAK_TABLOLAR:
        try:
            rows = con.execute(f"SELECT * FROM {tablo}").fetchall()
            data = _tablo_satirlari_jsona_hazirla(rows)
            payload["tablolar"][tablo] = data
            toplam += len(data)
        except Exception:
            payload["tablolar"][tablo] = None
    raw = json.dumps(payload, ensure_ascii=False)
    con.execute(
        """
        INSERT INTO sistem_yedekleri
            (olusturma, ogretmen_id, ogretmen_adi, tablo_sayisi, kayit_sayisi, json_yedek)
        VALUES (?,?,?,?,?,?)
        """,
        (olusturma, ogretmen_id, ogretmen_adi or "", len(_SIFIRLANACAK_TABLOLAR), toplam, raw),
    )
    con.commit()
    yedek_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.close()
    return {"yedek_id": int(yedek_id), "olusturma": olusturma, "kayit_sayisi": toplam}


def sistem_yedek_listesi(limit: int = 8) -> list[dict]:
    con = _conn()
    _sistem_yedek_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT yedek_id, olusturma, ogretmen_adi, tablo_sayisi, kayit_sayisi,
               LENGTH(json_yedek) AS boyut
        FROM sistem_yedekleri
        ORDER BY yedek_id DESC
        LIMIT ?
    """, (limit,)).fetchall()]
    con.close()
    return rows


def _json_degerini_db_icin_coz(val):
    if isinstance(val, dict) and "__bytes_hex__" in val:
        return bytes.fromhex(val["__bytes_hex__"])
    return val


def sistem_yedegini_geri_yukle(yedek_id: int, ogretmen_id: int | None = None, ogretmen_adi: str = "") -> dict:
    """Seçilen sistem yedeğindeki kullanıcı verilerini geri yükler.

    `rapor_arsiv` ve `sistem_yedekleri` korunur; geri yüklemeden önce mevcut sıfırlanabilir
    kullanıcı verilerinin de yeni bir yedeği alınır.
    """
    onceki_yedek = sistem_yedegi_olustur(ogretmen_id, ogretmen_adi or "Geri yukleme oncesi")
    con = _conn()
    _sistem_yedek_init(con)
    row = con.execute(
        "SELECT json_yedek FROM sistem_yedekleri WHERE yedek_id = ?",
        (yedek_id,),
    ).fetchone()
    if not row:
        con.close()
        return {"ok": False, "sebep": "Yedek bulunamadi"}

    try:
        payload = json.loads(row["json_yedek"])
    except Exception:
        con.close()
        return {"ok": False, "sebep": "Yedek okunamadi"}

    tablolar = payload.get("tablolar") or {}
    restored = {}
    try:
        con.execute("PRAGMA foreign_keys = OFF")
        for tablo in reversed(_SIFIRLANACAK_TABLOLAR):
            try:
                con.execute(f"DELETE FROM {tablo}")
            except Exception:
                pass
        for tablo in _SIFIRLANACAK_TABLOLAR:
            rows = tablolar.get(tablo)
            if not rows:
                restored[tablo] = 0 if rows == [] else "yedekte yok"
                continue
            adet = 0
            for item in rows:
                if not isinstance(item, dict) or not item:
                    continue
                cols = list(item.keys())
                values = [_json_degerini_db_icin_coz(item[c]) for c in cols]
                col_sql = ", ".join(cols)
                ph = ", ".join("?" for _ in cols)
                con.execute(f"INSERT OR REPLACE INTO {tablo} ({col_sql}) VALUES ({ph})", values)
                adet += 1
            restored[tablo] = adet
        con.execute("PRAGMA foreign_keys = ON")
        con.commit()
    except Exception as exc:
        con.rollback()
        con.execute("PRAGMA foreign_keys = ON")
        con.close()
        return {"ok": False, "sebep": f"Geri yukleme basarisiz: {exc}"}
    con.close()
    return {"ok": True, "geri_yuklenen": restored, "geri_yukleme_oncesi_yedek": onceki_yedek}


def tum_verileri_sifirla(ogretmen_id: int | None = None, ogretmen_adi: str = "") -> dict:
    """Tik, lig, gamifikasyon vb. sıfırlanır. PDF analiz arşivi (rapor_arsiv) kasıtlı olarak
    bu listede yoktur — üretilmiş analiz PDF/JSON kayıtları korunur. Önce sistem yedeği alınır."""
    yedek = sistem_yedegi_olustur(ogretmen_id, ogretmen_adi)
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
    return {"ok": True, "silinen": silinen, "yedek": yedek}


# ══════════════════════════════════════════════════════════════════════════
# Odev Sistemi
# ══════════════════════════════════════════════════════════════════════════

def _odev_init(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS odevler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            baslik TEXT NOT NULL,
            aciklama TEXT NOT NULL DEFAULT '',
            son_tarih TEXT NOT NULL,
            ders TEXT NOT NULL DEFAULT 'Genel',
            tarih TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS odev_tamamlayanlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            odev_id INTEGER NOT NULL REFERENCES odevler(id) ON DELETE CASCADE,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            tarih TEXT NOT NULL,
            UNIQUE(odev_id, ogrenci_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS odev_sonuclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            odev_id INTEGER NOT NULL REFERENCES odevler(id) ON DELETE CASCADE,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            durum TEXT NOT NULL DEFAULT 'tamamlamadi',
            UNIQUE(odev_id, ogrenci_id)
        )
    """)
    try:
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_odev_sonuclari_odev_ogrenci "
            "ON odev_sonuclari(odev_id, ogrenci_id)"
        )
    except Exception:
        pass
    cols = {r[1] for r in con.execute("PRAGMA table_info(odevler)").fetchall()}
    eksik = {
        "baslik": "TEXT NOT NULL DEFAULT ''",
        "aciklama": "TEXT NOT NULL DEFAULT ''",
        "son_tarih": "TEXT NOT NULL DEFAULT ''",
        "ders": "TEXT NOT NULL DEFAULT 'Genel'",
        "ders_adi": "TEXT NOT NULL DEFAULT ''",
        "tema_adi": "TEXT NOT NULL DEFAULT ''",
        "konu_adi": "TEXT NOT NULL DEFAULT ''",
        "ogrenme_ciktilari_json": "TEXT NOT NULL DEFAULT '[]'",
        "sinif_seviyesi": "INTEGER NOT NULL DEFAULT 0",
        "ogrenme_cikti_kodlari_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for ad, decl in eksik.items():
        if ad not in cols:
            try:
                con.execute(f"ALTER TABLE odevler ADD COLUMN {ad} {decl}")
            except Exception:
                pass
            cols.add(ad)
    if "ders_adi" in cols and "ders" in cols:
        con.execute("UPDATE odevler SET ders_adi = ders WHERE (ders_adi IS NULL OR ders_adi = '') AND ders IS NOT NULL")
        con.execute("UPDATE odevler SET ders = ders_adi WHERE (ders IS NULL OR ders = '') AND ders_adi IS NOT NULL")
    if "tema_adi" in cols and "baslik" in cols:
        con.execute("UPDATE odevler SET tema_adi = baslik WHERE (tema_adi IS NULL OR tema_adi = '') AND baslik IS NOT NULL")
        con.execute("UPDATE odevler SET baslik = tema_adi WHERE (baslik IS NULL OR baslik = '') AND tema_adi IS NOT NULL")
    if "son_tarih" in cols:
        con.execute("UPDATE odevler SET son_tarih = substr(tarih, 1, 10) WHERE son_tarih IS NULL OR son_tarih = ''")
    con.commit()


def odev_ekle(sinif_id: int, ogretmen_id: int, baslik: str,
              aciklama: str, son_tarih: str, ders: str = "Genel") -> dict:
    baslik = (baslik or "").strip()
    aciklama = (aciklama or "").strip()
    ders = (ders or "Genel").strip()
    son_tarih = (son_tarih or datetime.now().strftime("%Y-%m-%d")).strip()
    if not baslik:
        return {"ok": False, "sebep": "Baslik bos olamaz"}
    con = _conn()
    _odev_init(con)
    con.execute("""
        INSERT INTO odevler (sinif_id, ogretmen_id, baslik, aciklama, son_tarih, ders, tarih)
        VALUES (?,?,?,?,?,?,?)
    """, (sinif_id, ogretmen_id, baslik, aciklama, son_tarih, ders,
          datetime.now().strftime("%Y-%m-%d %H:%M")))
    con.commit()
    odev_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.close()
    return {"ok": True, "odev_id": odev_id}


def sinif_odevleri(sinif_id: int, limit: int = 30) -> list[dict]:
    con = _conn()
    _odev_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT od.*, og.ad_soyad AS ogretmen,
               COUNT(ot.id) AS tamamlayan,
               (SELECT COUNT(*) FROM ogrenciler WHERE sinif_id = od.sinif_id) AS toplam_ogrenci
        FROM odevler od
        JOIN ogretmenler og ON og.id = od.ogretmen_id
        LEFT JOIN odev_tamamlayanlar ot ON ot.odev_id = od.id
        WHERE od.sinif_id = ?
        GROUP BY od.id
        ORDER BY od.son_tarih DESC, od.id DESC
        LIMIT ?
    """, (sinif_id, limit)).fetchall()]
    con.close()
    return rows


def odev_detay(odev_id: int) -> dict | None:
    con = _conn()
    _odev_init(con)
    row = con.execute("""
        SELECT od.*, s.sinif_adi, og.ad_soyad AS ogretmen
        FROM odevler od
        JOIN siniflar s ON s.id = od.sinif_id
        JOIN ogretmenler og ON og.id = od.ogretmen_id
        WHERE od.id = ?
    """, (odev_id,)).fetchone()
    if not row:
        con.close()
        return None
    d = dict(row)
    rows = [dict(r) for r in con.execute("""
        SELECT o.id, o.ad_soyad, o.ogr_no,
               CASE WHEN ot.id IS NULL THEN 0 ELSE 1 END AS tamamlandi,
               ot.tarih AS tamamlanma_tarihi
        FROM ogrenciler o
        LEFT JOIN odev_tamamlayanlar ot ON ot.odev_id = ? AND ot.ogrenci_id = o.id
        WHERE o.sinif_id = ?
        ORDER BY o.ad_soyad
    """, (odev_id, d["sinif_id"])).fetchall()]
    con.close()
    d["ogrenciler"] = rows
    d["tamamlayan"] = sum(1 for r in rows if r["tamamlandi"])
    d["toplam_ogrenci"] = len(rows)
    return d


def odev_tamamla(odev_id: int, ogrenci_id: int, ogretmen_id: int) -> dict:
    con = _conn()
    _odev_init(con)
    _gelisim_init(con)
    row = con.execute("""
        SELECT od.baslik, od.sinif_id, o.ad_soyad
        FROM odevler od
        JOIN ogrenciler o ON o.id = ? AND o.sinif_id = od.sinif_id
        WHERE od.id = ?
    """, (ogrenci_id, odev_id)).fetchone()
    if not row:
        con.close()
        return {"ok": False, "sebep": "Odev veya ogrenci bulunamadi"}
    con.execute("""
        INSERT OR IGNORE INTO odev_tamamlayanlar (odev_id, ogrenci_id, ogretmen_id, tarih)
        VALUES (?,?,?,?)
    """, (odev_id, ogrenci_id, ogretmen_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
    yeni = con.total_changes > 0
    xp = 0
    if yeni:
        xp = 8
        _gelisim_puan_ekle(con, ogrenci_id, xp)
    con.commit()
    con.close()
    return {"ok": True, "yeni": yeni, "xp": xp}


def odev_tamamlandi_kaldir(odev_id: int, ogrenci_id: int) -> dict:
    con = _conn()
    _odev_init(con)
    con.execute("DELETE FROM odev_tamamlayanlar WHERE odev_id=? AND ogrenci_id=?",
                (odev_id, ogrenci_id))
    con.commit()
    con.close()
    return {"ok": True}


def ogrenci_odevleri(ogrenci_id: int, limit: int = 30) -> list[dict]:
    con = _conn()
    _odev_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT od.id, od.baslik, od.aciklama, od.son_tarih, od.ders, od.tarih,
               og.ad_soyad AS ogretmen,
               CASE WHEN ot.id IS NULL THEN 0 ELSE 1 END AS tamamlandi,
               ot.tarih AS tamamlanma_tarihi
        FROM ogrenciler o
        JOIN odevler od ON od.sinif_id = o.sinif_id
        JOIN ogretmenler og ON og.id = od.ogretmen_id
        LEFT JOIN odev_tamamlayanlar ot ON ot.odev_id = od.id AND ot.ogrenci_id = o.id
        WHERE o.id = ?
        ORDER BY od.son_tarih DESC, od.id DESC
        LIMIT ?
    """, (ogrenci_id, limit)).fetchall()]
    con.close()
    return rows


# ══════════════════════════════════════════════════════════════════════════
# Gelisim Merkezi
# ══════════════════════════════════════════════════════════════════════════

GELISIM_GOREV_HAVUZU = [
    ("Bugun derse hazirlikli gir", 8),
    ("Bir arkadasina ders konusunda yardim et", 10),
    ("Odevini zamaninda tamamla", 12),
    ("Ders boyunca soz kesmeden dinle", 8),
    ("Sinif duzenine katkida bulun", 10),
    ("Bugun hic tik almadan gunu tamamla", 15),
    ("Kitabini/defterini eksiksiz getir", 8),
]

TELAFI_GOREV_HAVUZU = [
    "Ogretmenden kisa bir oz-degerlendirme formu al",
    "Bir ders boyunca sorumluluk gorevi ustlen",
    "Arkadasina yardim ederek olumlu davranis goster",
    "Eksik odevini tamamlayip teslim et",
    "Sinif duzeni icin 5 dakikalik katkida bulun",
]

SANDIK_ODULLERI = [
    ("Bronz Sandik", 20, "Avatar parcasi"),
    ("Gumus Sandik", 35, "Bonus gorev"),
    ("Altin Sandik", 50, "Efsane rozet sansi"),
    ("Surpriz Sandik", 30, "Sans puani"),
]

PAZAR_URUNLERI = [
    {"kod": "cerceve_mavi", "ad": "Mavi Profil Cercevesi", "emoji": "💠", "fiyat": 30, "nadirlik": "Yaygin", "kategori": "Cerceve"},
    {"kod": "cerceve_yesil", "ad": "Yesil Basari Cercevesi", "emoji": "✅", "fiyat": 35, "nadirlik": "Yaygin", "kategori": "Cerceve"},
    {"kod": "cerceve_sari", "ad": "Sari Enerji Cercevesi", "emoji": "⭐", "fiyat": 35, "nadirlik": "Yaygin", "kategori": "Cerceve"},
    {"kod": "lakap_duzenli", "ad": "Duzenli Ogrenci Lakabi", "emoji": "📚", "fiyat": 40, "nadirlik": "Yaygin", "kategori": "Lakap"},
    {"kod": "lakap_yardimci", "ad": "Yardimci Kahraman Lakabi", "emoji": "🤝", "fiyat": 45, "nadirlik": "Yaygin", "kategori": "Lakap"},
    {"kod": "arka_defter", "ad": "Defter Arka Plani", "emoji": "📓", "fiyat": 45, "nadirlik": "Yaygin", "kategori": "Arka Plan"},

    {"kod": "cerceve_gumus", "ad": "Gumus Parilti Cercevesi", "emoji": "🥈", "fiyat": 70, "nadirlik": "Nadir", "kategori": "Cerceve"},
    {"kod": "arka_orman", "ad": "Gizemli Orman Arka Plani", "emoji": "🌲", "fiyat": 75, "nadirlik": "Nadir", "kategori": "Arka Plan"},
    {"kod": "arka_deniz", "ad": "Mavi Deniz Arka Plani", "emoji": "🌊", "fiyat": 75, "nadirlik": "Nadir", "kategori": "Arka Plan"},
    {"kod": "tema_bilim", "ad": "Bilim Laboratuvari Temasi", "emoji": "🔬", "fiyat": 80, "nadirlik": "Nadir", "kategori": "Tema"},
    {"kod": "lakap_zeka", "ad": "Zeka Ustasi Lakabi", "emoji": "🧠", "fiyat": 85, "nadirlik": "Nadir", "kategori": "Lakap"},
    {"kod": "rozet_sessiz", "ad": "Sessiz Kahraman Rozeti", "emoji": "🤫", "fiyat": 90, "nadirlik": "Nadir", "kategori": "Rozet"},
    {"kod": "rozet_odev", "ad": "Odev Canavari Rozeti", "emoji": "📝", "fiyat": 90, "nadirlik": "Nadir", "kategori": "Rozet"},
    {"kod": "efekt_parilti", "ad": "Profil Parilti Efekti", "emoji": "✨", "fiyat": 95, "nadirlik": "Nadir", "kategori": "Efekt"},

    {"kod": "cerceve_altin", "ad": "Altin Lider Cercevesi", "emoji": "🥇", "fiyat": 130, "nadirlik": "Epik", "kategori": "Cerceve"},
    {"kod": "arka_uzay", "ad": "Uzay Yolculugu Arka Plani", "emoji": "🚀", "fiyat": 140, "nadirlik": "Epik", "kategori": "Arka Plan"},
    {"kod": "arka_hazine", "ad": "Hazine Adasi Arka Plani", "emoji": "🏝️", "fiyat": 145, "nadirlik": "Epik", "kategori": "Arka Plan"},
    {"kod": "tema_altin", "ad": "Altin Kart Temasi", "emoji": "🏆", "fiyat": 150, "nadirlik": "Epik", "kategori": "Tema"},
    {"kod": "tema_galaksi", "ad": "Galaksi Kart Temasi", "emoji": "🌌", "fiyat": 155, "nadirlik": "Epik", "kategori": "Tema"},
    {"kod": "lakap_lider", "ad": "Sinif Lideri Lakabi", "emoji": "🦁", "fiyat": 160, "nadirlik": "Epik", "kategori": "Lakap"},
    {"kod": "rozet_takim", "ad": "Takim Ruhu Rozeti", "emoji": "🛡️", "fiyat": 165, "nadirlik": "Epik", "kategori": "Rozet"},
    {"kod": "efekt_alev", "ad": "Alevli Seri Efekti", "emoji": "🔥", "fiyat": 175, "nadirlik": "Epik", "kategori": "Efekt"},

    {"kod": "cerceve_elmas", "ad": "Elmas Efsane Cercevesi", "emoji": "💎", "fiyat": 240, "nadirlik": "Efsane", "kategori": "Cerceve"},
    {"kod": "arka_krallik", "ad": "Krallik Salonu Arka Plani", "emoji": "🏰", "fiyat": 250, "nadirlik": "Efsane", "kategori": "Arka Plan"},
    {"kod": "tema_ejderha", "ad": "Ejderha Kart Temasi", "emoji": "🐉", "fiyat": 270, "nadirlik": "Efsane", "kategori": "Tema"},
    {"kod": "lakap_efsane", "ad": "Efsane Ogrenci Lakabi", "emoji": "👑", "fiyat": 280, "nadirlik": "Efsane", "kategori": "Lakap"},
    {"kod": "rozet_zirve", "ad": "Zirve Rozeti", "emoji": "⛰️", "fiyat": 300, "nadirlik": "Efsane", "kategori": "Rozet"},
    {"kod": "efekt_gokkusagi", "ad": "Gokkusagi Iz Efekti", "emoji": "🌈", "fiyat": 320, "nadirlik": "Efsane", "kategori": "Efekt"},

    {"kod": "cerceve_mitik", "ad": "Mitik Aurora Cercevesi", "emoji": "🌠", "fiyat": 420, "nadirlik": "Mitik", "kategori": "Cerceve"},
    {"kod": "arka_evren", "ad": "Evren Kapisi Arka Plani", "emoji": "🪐", "fiyat": 450, "nadirlik": "Mitik", "kategori": "Arka Plan"},
    {"kod": "tema_kristal", "ad": "Kristal Saray Temasi", "emoji": "🔮", "fiyat": 480, "nadirlik": "Mitik", "kategori": "Tema"},
    {"kod": "lakap_okul_efsanesi", "ad": "Okul Efsanesi Lakabi", "emoji": "🏅", "fiyat": 520, "nadirlik": "Mitik", "kategori": "Lakap"},
    {"kod": "efekt_yildiz_yagmuru", "ad": "Yildiz Yagmuru Efekti", "emoji": "☄️", "fiyat": 560, "nadirlik": "Mitik", "kategori": "Efekt"},
]


def rozet_emojileri_ve_metin(rozet_kodu: str) -> tuple[str, str]:
    """Rozet kodu için emoji ve görünen ad (okul / pazar)."""
    if rozet_kodu in ROZET_TANIMI:
        t = ROZET_TANIMI[rozet_kodu]
        return t[0], t[1]
    for u in PAZAR_URUNLERI:
        if u["kod"] == rozet_kodu:
            return u["emoji"], u["ad"]
    return "🏅", rozet_kodu


def ogrenci_rozetleri_yayin_map(ogrenci_ids: list[int], limit: int = 8) -> dict[int, list[dict]]:
    """Yayın listesi için öğrenci başına rozet özetleri."""
    if not ogrenci_ids:
        return {}
    from collections import defaultdict
    con = _conn()
    _gami_init(con)
    q = ",".join("?" * len(ogrenci_ids))
    rows = [dict(r) for r in con.execute(
        f"SELECT ogrenci_id, rozet_kodu, tarih FROM rozet_kayitlari WHERE ogrenci_id IN ({q})",
        ogrenci_ids,
    ).fetchall()]
    con.close()
    buckets: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[r["ogrenci_id"]].append(r)
    out: dict[int, list[dict]] = {}
    for oid, items in buckets.items():
        items.sort(key=lambda x: x.get("tarih") or "", reverse=True)
        rozetler = []
        for r in items[:limit]:
            em, ad = rozet_emojileri_ve_metin(r["rozet_kodu"])
            rozetler.append({"emoji": em, "ad": ad, "kod": r["rozet_kodu"]})
        out[oid] = rozetler
    return out


GOREV_SABLONLARI = [
    {"baslik": "Sessiz Ders Ustasi", "aciklama": "Ders boyunca soz kesmeden dinle", "xp": 10},
    {"baslik": "Odev Kahramani", "aciklama": "Bugunku odevini eksiksiz tamamla", "xp": 12},
    {"baslik": "Yardim Eli", "aciklama": "Bir arkadasina konu anlat", "xp": 10},
    {"baslik": "Temizlik Lideri", "aciklama": "Sinif duzenine katkida bulun", "xp": 8},
    {"baslik": "Hazirlikli Gel", "aciklama": "Kitap ve defterlerini eksiksiz getir", "xp": 8},
]

HIKAYE_BOLUMLERI = [
    (0, "Baslangic Kampi", "Sinif kahramanlari yola cikiyor."),
    (80, "Gizemli Orman", "Olumlu davranislarla yol aciliyor."),
    (180, "Bilim Kulesi", "Odev ve yardimlasma gucu kuleyi aydinlatiyor."),
    (320, "Hazine Adasi", "Temiz seri sinifi hazineye yaklastiriyor."),
    (500, "Efsane Zirve", "Sinif gelisim efsanesine donusuyor."),
]

AVATAR_SEVIYELERI = [
    (0, "Yumurta", "🥚"),
    (50, "Civciv", "🐣"),
    (120, "Kartal", "🦅"),
    (250, "Aslan", "🦁"),
    (500, "Efsane", "👑"),
]


def _gelisim_init(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS gelisim_puan (
            ogrenci_id INTEGER PRIMARY KEY REFERENCES ogrenciler(id),
            xp INTEGER NOT NULL DEFAULT 0,
            sandik_hakki INTEGER NOT NULL DEFAULT 0,
            guncelleme TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS gelisim_gorevleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            tarih TEXT NOT NULL,
            gorev TEXT NOT NULL,
            xp INTEGER NOT NULL DEFAULT 10,
            tamamlandi INTEGER NOT NULL DEFAULT 0,
            UNIQUE(ogrenci_id, tarih)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sandik_kayitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sandik TEXT NOT NULL,
            odul TEXT NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            tarih TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS telafi_gorevleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            gorev TEXT NOT NULL,
            durum TEXT NOT NULL DEFAULT 'bekliyor',
            tarih TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tebrik_kartlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gonderen_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            alan_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            mesaj TEXT NOT NULL,
            tarih TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS avatar_envanter (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            urun_kodu TEXT NOT NULL,
            tarih TEXT NOT NULL,
            UNIQUE(ogrenci_id, urun_kodu)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS avatar_vitrin (
            ogrenci_id INTEGER PRIMARY KEY REFERENCES ogrenciler(id),
            urun_kodu TEXT NOT NULL,
            tarih TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ogretmen_notlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
            not_metni TEXT NOT NULL,
            veliye_acik INTEGER NOT NULL DEFAULT 1,
            tarih TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS hikaye_ilerleme (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            puan INTEGER NOT NULL DEFAULT 0,
            guncelleme TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS oyun_puanlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            oyun TEXT NOT NULL,
            puan INTEGER NOT NULL DEFAULT 0,
            xp INTEGER NOT NULL DEFAULT 0,
            tarih TEXT NOT NULL
        )
    """)
    con.commit()


def _gelisim_puan_ekle(con, ogrenci_id: int, xp: int) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    con.execute("""
        INSERT INTO gelisim_puan (ogrenci_id, xp, sandik_hakki, guncelleme)
        VALUES (?, 0, 0, ?)
        ON CONFLICT(ogrenci_id) DO NOTHING
    """, (ogrenci_id, now))
    con.execute("""
        UPDATE gelisim_puan
        SET xp = xp + ?,
            sandik_hakki = sandik_hakki + CASE
                WHEN CAST((xp + ?) / 50 AS INTEGER) > CAST(xp / 50 AS INTEGER) THEN 1
                ELSE 0
            END,
            guncelleme = ?
        WHERE ogrenci_id = ?
    """, (xp, xp, now, ogrenci_id))
    return dict(con.execute("SELECT * FROM gelisim_puan WHERE ogrenci_id=?", (ogrenci_id,)).fetchone())


def oyun_puani_kaydet(ogrenci_id: int, oyun: str, puan: int) -> dict:
    oyun = (oyun or "Oyun").strip()[:40]
    puan = max(0, int(puan or 0))
    bugun = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    xp = min(20, puan // 5)
    con = _conn()
    _gelisim_init(con)
    bugunku_xp = con.execute("""
        SELECT COALESCE(SUM(xp),0) FROM oyun_puanlari
        WHERE ogrenci_id=? AND substr(tarih,1,10)=?
    """, (ogrenci_id, bugun)).fetchone()[0]
    xp = max(0, min(xp, 40 - int(bugunku_xp or 0)))
    con.execute("""
        INSERT INTO oyun_puanlari (ogrenci_id, oyun, puan, xp, tarih)
        VALUES (?,?,?,?,?)
    """, (ogrenci_id, oyun, puan, xp, now))
    sinifa_lig = False
    if xp:
        puan_kaydi = _gelisim_puan_ekle(con, ogrenci_id, xp)
        ogr = con.execute(
            "SELECT sinif_id FROM ogrenciler WHERE id=?", (ogrenci_id,)
        ).fetchone()
        if ogr:
            _lig_haftalik_puan_artir(con, ogr["sinif_id"])
            sinifa_lig = True
    else:
        puan_kaydi = dict(con.execute("SELECT * FROM gelisim_puan WHERE ogrenci_id=?", (ogrenci_id,)).fetchone())
    con.commit(); con.close()
    return {
        "ok": True,
        "xp": xp,
        "gunluk_kalan": max(0, 40 - int(bugunku_xp or 0) - xp),
        "puan": puan_kaydi,
        "sinifa_lig_katkisi": sinifa_lig,
    }


def avatar_seviyesi(xp: int) -> dict:
    secili = AVATAR_SEVIYELERI[0]
    sonraki = None
    for seviye in AVATAR_SEVIYELERI:
        if xp >= seviye[0]:
            secili = seviye
        elif not sonraki:
            sonraki = seviye
    return {
        "esik": secili[0], "ad": secili[1], "emoji": secili[2],
        "sonraki_esik": sonraki[0] if sonraki else xp,
        "sonraki_ad": sonraki[1] if sonraki else "Zirve",
    }


def gelisim_ozeti(ogrenci_id: int) -> dict:
    import random
    bugun = datetime.now().strftime("%Y-%m-%d")
    con = _conn()
    _gelisim_init(con)
    con.execute("""
        INSERT INTO gelisim_puan (ogrenci_id, xp, sandik_hakki, guncelleme)
        VALUES (?, 0, 0, ?)
        ON CONFLICT(ogrenci_id) DO NOTHING
    """, (ogrenci_id, bugun))
    if not con.execute("SELECT id FROM gelisim_gorevleri WHERE ogrenci_id=? AND tarih=?",
                       (ogrenci_id, bugun)).fetchone():
        gorev, xp = random.choice(GELISIM_GOREV_HAVUZU)
        con.execute("""
            INSERT INTO gelisim_gorevleri (ogrenci_id, tarih, gorev, xp)
            VALUES (?,?,?,?)
        """, (ogrenci_id, bugun, gorev, xp))
    con.commit()
    puan = dict(con.execute("SELECT * FROM gelisim_puan WHERE ogrenci_id=?", (ogrenci_id,)).fetchone())
    gorev = dict(con.execute("""
        SELECT * FROM gelisim_gorevleri WHERE ogrenci_id=? AND tarih=?
    """, (ogrenci_id, bugun)).fetchone())
    sandiklar = [dict(r) for r in con.execute("""
        SELECT * FROM sandik_kayitlari WHERE ogrenci_id=? ORDER BY tarih DESC LIMIT 8
    """, (ogrenci_id,)).fetchall()]
    telafiler = [dict(r) for r in con.execute("""
        SELECT * FROM telafi_gorevleri WHERE ogrenci_id=? ORDER BY id DESC LIMIT 5
    """, (ogrenci_id,)).fetchall()]
    tebrikler = [dict(r) for r in con.execute("""
        SELECT tk.*, o.ad_soyad AS gonderen
        FROM tebrik_kartlari tk JOIN ogrenciler o ON o.id = tk.gonderen_id
        WHERE tk.alan_id=? ORDER BY tk.id DESC LIMIT 8
    """, (ogrenci_id,)).fetchall()]
    oyunlar = [dict(r) for r in con.execute("""
        SELECT oyun, SUM(puan) AS puan, SUM(xp) AS xp, MAX(tarih) AS son_tarih
        FROM oyun_puanlari
        WHERE ogrenci_id=?
        GROUP BY oyun
        ORDER BY son_tarih DESC
        LIMIT 8
    """, (ogrenci_id,)).fetchall()]
    con.close()
    return {
        "puan": puan,
        "avatar": avatar_seviyesi(puan["xp"]),
        "gorev": gorev,
        "sandiklar": sandiklar,
        "telafiler": telafiler,
        "tebrikler": tebrikler,
        "oyunlar": oyunlar,
        "sandik_odulleri": SANDIK_ODULLERI,
    }


def gelisim_gorev_tamamla(ogrenci_id: int) -> dict:
    bugun = datetime.now().strftime("%Y-%m-%d")
    con = _conn()
    _gelisim_init(con)
    row = con.execute("SELECT * FROM gelisim_gorevleri WHERE ogrenci_id=? AND tarih=?",
                      (ogrenci_id, bugun)).fetchone()
    if not row:
        con.close()
        gelisim_ozeti(ogrenci_id)
        return gelisim_gorev_tamamla(ogrenci_id)
    if row["tamamlandi"]:
        con.close()
        return {"ok": False, "sebep": "Bugunku gorev zaten tamamlandi"}
    con.execute("UPDATE gelisim_gorevleri SET tamamlandi=1 WHERE id=?", (row["id"],))
    puan = _gelisim_puan_ekle(con, ogrenci_id, row["xp"])
    ogr = con.execute(
        "SELECT sinif_id FROM ogrenciler WHERE id=?", (ogrenci_id,)
    ).fetchone()
    sinifa_lig = False
    if ogr:
        _lig_haftalik_puan_artir(con, ogr["sinif_id"])
        sinifa_lig = True
    con.commit(); con.close()
    return {
        "ok": True,
        "xp": row["xp"],
        "puan": puan,
        "sinifa_lig_katkisi": sinifa_lig,
    }


def sandik_ac(ogrenci_id: int) -> dict:
    import random
    con = _conn()
    _gelisim_init(con)
    puan = con.execute("SELECT * FROM gelisim_puan WHERE ogrenci_id=?", (ogrenci_id,)).fetchone()
    if not puan or puan["sandik_hakki"] <= 0:
        con.close()
        return {"ok": False, "sebep": "Sandik hakki yok"}
    sandik, xp, odul = random.choice(SANDIK_ODULLERI)
    con.execute("UPDATE gelisim_puan SET sandik_hakki=sandik_hakki-1 WHERE ogrenci_id=?", (ogrenci_id,))
    _gelisim_puan_ekle(con, ogrenci_id, xp)
    con.execute("""
        INSERT INTO sandik_kayitlari (ogrenci_id, sandik, odul, xp, tarih)
        VALUES (?,?,?,?,?)
    """, (ogrenci_id, sandik, odul, xp, datetime.now().strftime("%Y-%m-%d %H:%M")))
    con.commit(); con.close()
    return {"ok": True, "sandik": sandik, "odul": odul, "xp": xp}


def telafi_gorevi_olustur(ogrenci_id: int) -> dict:
    import random
    con = _conn()
    _gelisim_init(con)
    gorev = random.choice(TELAFI_GOREV_HAVUZU)
    con.execute("""
        INSERT INTO telafi_gorevleri (ogrenci_id, gorev, durum, tarih)
        VALUES (?,?,'bekliyor',?)
    """, (ogrenci_id, gorev, datetime.now().strftime("%Y-%m-%d %H:%M")))
    con.commit(); con.close()
    return {"ok": True, "gorev": gorev}


def tebrik_gonder(gonderen_id: int, alan_id: int, mesaj: str) -> dict:
    mesaj = (mesaj or "Harika is cikardin!").strip()[:160]
    if gonderen_id == alan_id:
        return {"ok": False, "sebep": "Kendine tebrik gonderemezsin"}
    con = _conn()
    _gelisim_init(con)
    con.execute("""
        INSERT INTO tebrik_kartlari (gonderen_id, alan_id, mesaj, tarih)
        VALUES (?,?,?,?)
    """, (gonderen_id, alan_id, mesaj, datetime.now().strftime("%Y-%m-%d %H:%M")))
    _gelisim_puan_ekle(con, alan_id, 5)
    con.commit(); con.close()
    return {"ok": True}


def haftalik_veli_ozeti(ogrenci_id: int) -> dict:
    hafta_once = (datetime.now() - __import__("datetime").timedelta(days=7)).strftime("%Y-%m-%d")
    con = _conn()
    _gelisim_init(con)
    tik = con.execute("""
        SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id=? AND tarih>=?
    """, (ogrenci_id, hafta_once)).fetchone()[0]
    odev = con.execute("""
        SELECT COUNT(*) FROM odev_tamamlayanlar WHERE ogrenci_id=? AND tarih>=?
    """, (ogrenci_id, hafta_once)).fetchone()[0]
    tebrik = con.execute("""
        SELECT COUNT(*) FROM tebrik_kartlari WHERE alan_id=? AND tarih>=?
    """, (ogrenci_id, hafta_once)).fetchone()[0]
    gorev = con.execute("""
        SELECT COUNT(*) FROM gelisim_gorevleri WHERE ogrenci_id=? AND tarih>=? AND tamamlandi=1
    """, (ogrenci_id, hafta_once)).fetchone()[0]
    con.close()
    return {"tik": tik, "odev": odev, "tebrik": tebrik, "gorev": gorev}


def akilli_ogrenci_karnesi(ogrenci_id: int) -> dict:
    odevler = ogrenci_odevleri(ogrenci_id, 50)
    gelisim = gelisim_ozeti(ogrenci_id)
    hafta = haftalik_veli_ozeti(ogrenci_id)
    con = _conn()
    _gelisim_init(con)
    ogr = con.execute("""
        SELECT o.*, s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?
    """, (ogrenci_id,)).fetchone()
    tik_toplam = con.execute("SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id=?", (ogrenci_id,)).fetchone()[0]
    notlar = [dict(r) for r in con.execute("""
        SELECT n.*, og.ad_soyad AS ogretmen
        FROM ogretmen_notlari n JOIN ogretmenler og ON og.id=n.ogretmen_id
        WHERE n.ogrenci_id=? AND n.veliye_acik=1 ORDER BY n.id DESC LIMIT 8
    """, (ogrenci_id,)).fetchall()]
    con.close()
    tamamlanan = sum(1 for o in odevler if o.get("tamamlandi"))
    odev_orani = round(tamamlanan * 100 / len(odevler)) if odevler else 0
    risk = davranis_tahmini(ogrenci_id, tik_toplam, odev_orani, hafta)
    guclu = []
    destek = []
    if odev_orani >= 70: guclu.append("Odev sorumlulugu guclu")
    else: destek.append("Odev takibi desteklenmeli")
    if hafta["gorev"] > 0: guclu.append("Gelistirici gorevlere katiliyor")
    if tik_toplam >= 6: destek.append("Davranis telafi gorevleri onerilir")
    return {
        "ogrenci": dict(ogr) if ogr else {},
        "tik_toplam": tik_toplam,
        "odev_orani": odev_orani,
        "gelisim": gelisim,
        "hafta": hafta,
        "risk": risk,
        "guclu_yonler": guclu or ["Takip edilebilir gelisim verisi olusuyor"],
        "destek_onerileri": destek or ["Mevcut olumlu gidis korunmali"],
        "notlar": notlar,
    }


def davranis_tahmini(ogrenci_id: int, tik_toplam: int = None,
                     odev_orani: int = None, hafta: dict = None) -> dict:
    hafta = hafta or haftalik_veli_ozeti(ogrenci_id)
    if tik_toplam is None:
        con = _conn()
        tik_toplam = con.execute("SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id=?", (ogrenci_id,)).fetchone()[0]
        con.close()
    skor = 0
    skor += min(50, hafta.get("tik", 0) * 12)
    skor += min(25, tik_toplam * 3)
    if odev_orani is not None and odev_orani < 50:
        skor += 15
    skor -= min(20, hafta.get("gorev", 0) * 5 + hafta.get("tebrik", 0) * 3)
    skor = max(0, min(100, skor))
    if skor >= 70:
        seviye, mesaj = "yüksek", "Risk yukseliyor; telafi gorevi ve veli bilgilendirme onerilir."
    elif skor >= 35:
        seviye, mesaj = "orta", "Takip onerilir; olumlu gorevlerle desteklenebilir."
    else:
        seviye, mesaj = "düşük", "Gidis olumlu; mevcut motivasyon korunabilir."
    return {"skor": skor, "seviye": seviye, "mesaj": mesaj}


def ogretmen_bildirim_merkezi() -> dict:
    ogrenciler = tum_okul_ogrencileri()
    riskler = []
    for o in ogrenciler:
        hafta = haftalik_veli_ozeti(o["id"])
        odevler = ogrenci_odevleri(o["id"], 20)
        tamam = sum(1 for od in odevler if od.get("tamamlandi"))
        oran = round(tamam * 100 / len(odevler)) if odevler else 100
        risk = davranis_tahmini(o["id"], o["tik_sayisi"], oran, hafta)
        if risk["skor"] >= 35:
            riskler.append({**o, "risk": risk, "odev_orani": oran, "hafta": hafta})
    riskler.sort(key=lambda x: -x["risk"]["skor"])
    return {
        "riskler": riskler[:20],
        "odev_eksik": [r for r in riskler if r["odev_orani"] < 60][:20],
        "telafi_oneri": [r for r in riskler if r["tik_sayisi"] >= 3][:20],
    }


def gelisim_ligi() -> list[dict]:
    con = _conn()
    _gelisim_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT s.id AS sinif_id, s.sinif_adi,
               COALESCE(SUM(gp.xp),0) AS xp,
               COUNT(DISTINCT gg.id) AS gorev,
               COUNT(DISTINCT tk.id) AS tebrik,
               COUNT(DISTINCT ot.id) AS odev
        FROM siniflar s
        LEFT JOIN ogrenciler o ON o.sinif_id=s.id
        LEFT JOIN gelisim_puan gp ON gp.ogrenci_id=o.id
        LEFT JOIN gelisim_gorevleri gg ON gg.ogrenci_id=o.id AND gg.tamamlandi=1
        LEFT JOIN tebrik_kartlari tk ON tk.alan_id=o.id
        LEFT JOIN odev_tamamlayanlar ot ON ot.ogrenci_id=o.id
        GROUP BY s.id
        ORDER BY xp DESC, gorev DESC, tebrik DESC
    """).fetchall()]
    con.close()
    return rows


def hikaye_modu() -> list[dict]:
    lig = gelisim_ligi()
    sonuc = []
    for s in lig:
        puan = int(s.get("xp", 0)) + int(s.get("gorev", 0)) * 5 + int(s.get("tebrik", 0)) * 3
        bolum = HIKAYE_BOLUMLERI[0]
        sonraki = None
        for b in HIKAYE_BOLUMLERI:
            if puan >= b[0]:
                bolum = b
            elif not sonraki:
                sonraki = b
        sonuc.append({**s, "hikaye_puan": puan, "bolum": bolum[1], "aciklama": bolum[2],
                      "sonraki": sonraki[1] if sonraki else "Tamamlandi",
                      "ilerleme": min(100, round(puan * 100 / (sonraki[0] if sonraki else max(puan,1))))})
    return sonuc


def pazar_urunleri_ogrenci(ogrenci_id: int) -> list[dict]:
    con = _conn()
    _gelisim_init(con)
    _gami_init(con)
    sahip = {r["urun_kodu"] for r in con.execute(
        "SELECT urun_kodu FROM avatar_envanter WHERE ogrenci_id=?", (ogrenci_id,)
    ).fetchall()}
    rozet_sahip = {r["rozet_kodu"] for r in con.execute(
        "SELECT rozet_kodu FROM rozet_kayitlari WHERE ogrenci_id=?", (ogrenci_id,)
    ).fetchall()}
    con.close()
    siralama = {"Yaygin": 1, "Nadir": 2, "Epik": 3, "Efsane": 4, "Mitik": 5}
    urunler = []
    for u in PAZAR_URUNLERI:
        kod = u["kod"]
        sahip_mi = (kod in sahip) or (u.get("kategori") == "Rozet" and kod in rozet_sahip)
        urunler.append({**u, "sahip": sahip_mi, "nadirlik_sira": siralama.get(u.get("nadirlik"), 99)})
    return sorted(urunler, key=lambda u: (u["nadirlik_sira"], u["fiyat"], u["ad"]))


def _pazar_urun_bul(urun_kodu: str) -> dict | None:
    return next((u for u in PAZAR_URUNLERI if u["kod"] == urun_kodu), None)


def envanter_aktif_urun(ogrenci_id: int) -> dict | None:
    con = _conn()
    _gelisim_init(con)
    row = con.execute(
        "SELECT urun_kodu FROM avatar_vitrin WHERE ogrenci_id=?", (ogrenci_id,)
    ).fetchone()
    con.close()
    if not row:
        return None
    urun = _pazar_urun_bul(row["urun_kodu"])
    return {**urun, "aktif": True} if urun else None


def envanter_listele(ogrenci_id: int) -> dict:
    con = _conn()
    _gelisim_init(con)
    sahip = [dict(r) for r in con.execute("""
        SELECT urun_kodu, tarih
        FROM avatar_envanter
        WHERE ogrenci_id=?
        ORDER BY tarih DESC, id DESC
    """, (ogrenci_id,)).fetchall()]
    aktif = con.execute(
        "SELECT urun_kodu FROM avatar_vitrin WHERE ogrenci_id=?", (ogrenci_id,)
    ).fetchone()
    con.close()
    aktif_kod = aktif["urun_kodu"] if aktif else ""
    urunler = []
    for row in sahip:
        urun = _pazar_urun_bul(row["urun_kodu"])
        if not urun:
            continue
        urunler.append({**urun, "tarih": row["tarih"], "aktif": row["urun_kodu"] == aktif_kod})
    return {"aktif_kod": aktif_kod, "aktif": envanter_aktif_urun(ogrenci_id), "urunler": urunler}


def envanter_aktif_ayarla(ogrenci_id: int, urun_kodu: str) -> dict:
    urun_kodu = (urun_kodu or "").strip()
    con = _conn()
    _gelisim_init(con)
    try:
        if not urun_kodu:
            con.execute("DELETE FROM avatar_vitrin WHERE ogrenci_id=?", (ogrenci_id,))
            con.commit()
            return {"ok": True, "aktif": None}
        urun = _pazar_urun_bul(urun_kodu)
        if not urun:
            return {"ok": False, "sebep": "Urun bulunamadi"}
        sahip = con.execute("""
            SELECT id FROM avatar_envanter WHERE ogrenci_id=? AND urun_kodu=?
        """, (ogrenci_id, urun_kodu)).fetchone()
        if not sahip:
            return {"ok": False, "sebep": "Bu urun envanterinde yok"}
        con.execute("""
            INSERT INTO avatar_vitrin (ogrenci_id, urun_kodu, tarih)
            VALUES (?, ?, ?)
            ON CONFLICT(ogrenci_id) DO UPDATE SET urun_kodu=excluded.urun_kodu, tarih=excluded.tarih
        """, (ogrenci_id, urun_kodu, datetime.now().strftime("%Y-%m-%d %H:%M")))
        con.commit()
        return {"ok": True, "aktif": urun}
    finally:
        con.close()


def ogrenci_aktif_envanter_map(ogrenci_ids: list[int]) -> dict[int, dict]:
    if not ogrenci_ids:
        return {}
    con = _conn()
    _gelisim_init(con)
    q = ",".join("?" * len(ogrenci_ids))
    rows = [dict(r) for r in con.execute(
        f"SELECT ogrenci_id, urun_kodu FROM avatar_vitrin WHERE ogrenci_id IN ({q})",
        ogrenci_ids,
    ).fetchall()]
    con.close()
    out: dict[int, dict] = {}
    for r in rows:
        urun = _pazar_urun_bul(r["urun_kodu"])
        if urun:
            out[int(r["ogrenci_id"])] = {
                "kod": urun["kod"],
                "ad": urun["ad"],
                "emoji": urun["emoji"],
                "kategori": urun["kategori"],
                "nadirlik": urun["nadirlik"],
            }
    return out


def pazar_satin_al(ogrenci_id: int, urun_kodu: str) -> dict:
    urun = _pazar_urun_bul(urun_kodu)
    if not urun:
        return {"ok": False, "sebep": "Urun bulunamadi"}
    con = _conn()
    _gelisim_init(con)
    sahip = con.execute("""
        SELECT id FROM avatar_envanter WHERE ogrenci_id=? AND urun_kodu=?
    """, (ogrenci_id, urun_kodu)).fetchone()
    if sahip:
        con.close()
        return {"ok": False, "sebep": "Bu urun zaten koleksiyonda"}
    puan = con.execute("SELECT xp FROM gelisim_puan WHERE ogrenci_id=?", (ogrenci_id,)).fetchone()
    xp = puan["xp"] if puan else 0
    if xp < urun["fiyat"]:
        con.close()
        return {"ok": False, "sebep": "XP yetersiz"}
    con.execute("UPDATE gelisim_puan SET xp=xp-? WHERE ogrenci_id=?", (urun["fiyat"], ogrenci_id))
    con.execute("""
        INSERT OR IGNORE INTO avatar_envanter (ogrenci_id, urun_kodu, tarih)
        VALUES (?,?,?)
    """, (ogrenci_id, urun_kodu, datetime.now().strftime("%Y-%m-%d %H:%M")))
    ogr = con.execute("SELECT sinif_id FROM ogrenciler WHERE id=?", (ogrenci_id,)).fetchone()
    sinif_id = ogr["sinif_id"] if ogr else None
    con.commit()
    con.close()
    if urun.get("kategori") == "Rozet" and sinif_id is not None:
        rozet_ver_ogrenci(ogrenci_id, sinif_id, urun_kodu)
    return {"ok": True, "urun": urun}


def ogretmen_notu_ekle(ogrenci_id: int, ogretmen_id: int, not_metni: str, veliye_acik: bool = True) -> dict:
    not_metni = (not_metni or "").strip()
    if not not_metni:
        return {"ok": False, "sebep": "Not bos olamaz"}
    con = _conn()
    _gelisim_init(con)
    con.execute("""
        INSERT INTO ogretmen_notlari (ogrenci_id, ogretmen_id, not_metni, veliye_acik, tarih)
        VALUES (?,?,?,?,?)
    """, (ogrenci_id, ogretmen_id, not_metni, 1 if veliye_acik else 0, datetime.now().strftime("%Y-%m-%d %H:%M")))
    con.commit(); con.close()
    return {"ok": True}


def _taktik_tablosu_olustur(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS taktik_formasyonu (
            sinif_id INTEGER PRIMARY KEY REFERENCES siniflar(id),
            veri TEXT NOT NULL DEFAULT '{}', tarih TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS taktik_spor_formasyonu (
            sinif_id INTEGER NOT NULL REFERENCES siniflar(id),
            spor TEXT NOT NULL DEFAULT 'voleybol',
            veri TEXT NOT NULL DEFAULT '{}',
            tarih TEXT NOT NULL,
            PRIMARY KEY (sinif_id, spor)
        )
    """)
    con.commit()


def taktik_yukle(sinif_id: int) -> dict:
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


def taktik_kaydet(sinif_id: int, veri_str: str) -> dict:
    import json
    try:
        json.loads(veri_str)
    except Exception:
        return {"ok": False, "sebep": "Gecersiz veri"}
    con = _conn()
    _taktik_tablosu_olustur(con)
    con.execute(
        "INSERT OR REPLACE INTO taktik_formasyonu (sinif_id, veri, tarih) VALUES(?,?,?)",
        (sinif_id, veri_str, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    con.commit(); con.close()
    return {"ok": True}


def spor_taktik_yukle(sinif_id: int, spor: str) -> dict:
    import json
    spor = (spor or "").strip().lower()
    if spor == "futbol":
        return taktik_yukle(sinif_id)
    con = _conn()
    _taktik_tablosu_olustur(con)
    row = con.execute(
        "SELECT veri FROM taktik_spor_formasyonu WHERE sinif_id=? AND spor=?",
        (sinif_id, spor),
    ).fetchone()
    con.close()
    if row:
        try:
            return json.loads(row["veri"])
        except Exception:
            return {}
    return {}


def spor_taktik_kaydet(sinif_id: int, spor: str, veri_str: str) -> dict:
    import json
    spor = (spor or "").strip().lower()
    try:
        json.loads(veri_str)
    except Exception:
        return {"ok": False, "sebep": "Gecersiz veri"}
    if spor == "futbol":
        return taktik_kaydet(sinif_id, veri_str)
    con = _conn()
    _taktik_tablosu_olustur(con)
    con.execute("""
        INSERT OR REPLACE INTO taktik_spor_formasyonu (sinif_id, spor, veri, tarih)
        VALUES (?, ?, ?, ?)
    """, (sinif_id, spor, veri_str, datetime.now().strftime("%Y-%m-%d %H:%M")))
    con.commit()
    con.close()
    return {"ok": True}


def _rol_adi_normalize(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace(" ", "").replace("(", "").replace(")", "")


def taktik_kadro_guncelle(sinif_id: int, oyuncular: dict) -> None:
    rol_to_no = {_rol_adi_normalize(m[2]): m[0] for m in MEVKILER}
    varsayilan_no = 15
    con = _conn()
    _kadro_tablosu_olustur(con)
    for ogr_id_str, veri in oyuncular.items():
        try:
            ogr_id = int(ogr_id_str)
        except ValueError:
            continue
        rol = veri.get("rol", "")
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


# ══════════════════════════════════════════════════════════════════════════
# Quiz / Bilgi Yarisması
# ══════════════════════════════════════════════════════════════════════════

def _ogrenci_maclari_init(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_maclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            olusturan_ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
            sinif1_id INTEGER NOT NULL REFERENCES siniflar(id),
            sinif2_id INTEGER NOT NULL REFERENCES siniflar(id),
            spor TEXT NOT NULL DEFAULT 'futbol',
            skor1 INTEGER NOT NULL DEFAULT 0,
            skor2 INTEGER NOT NULL DEFAULT 0,
            aciklama TEXT NOT NULL DEFAULT '',
            durum TEXT NOT NULL DEFAULT 'onay_bekliyor',
            tarih TEXT NOT NULL,
            onaylayan_ogretmen_id INTEGER REFERENCES ogretmenler(id),
            onay_tarihi TEXT,
            puan_isledi INTEGER NOT NULL DEFAULT 0
        )
    """)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(ogrenci_maclari)").fetchall()}
    except Exception:
        cols = set()
    if cols and "spor" not in cols:
        con.execute("ALTER TABLE ogrenci_maclari ADD COLUMN spor TEXT NOT NULL DEFAULT 'futbol'")


def _ogrenci_mac_skor_kontrol(spor: str, skor1: int, skor2: int) -> dict:
    spor = (spor or "futbol").strip().lower()
    if spor not in {"futbol", "voleybol"}:
        return {"ok": False, "sebep": "Spor turu gecersiz."}
    if skor1 < 0 or skor2 < 0:
        return {"ok": False, "sebep": "Skor negatif olamaz."}
    if spor == "futbol":
        if skor1 > 20 or skor2 > 20:
            return {"ok": False, "sebep": "Futbolda skor gercekci aralikta degil."}
        if skor1 == skor2:
            return {"ok": True, "sonuc": "beraberlik", "puan1": 1, "puan2": 1, "kazanan": None}
        return {
            "ok": True,
            "sonuc": "galibiyet",
            "puan1": 3 if skor1 > skor2 else 0,
            "puan2": 3 if skor2 > skor1 else 0,
            "kazanan": "sinif1" if skor1 > skor2 else "sinif2",
        }
    if max(skor1, skor2) != 3 or min(skor1, skor2) > 2 or skor1 == skor2:
        return {
            "ok": False,
            "sebep": "Voleybolda mac skoru 3-0, 3-1, 3-2, 0-3, 1-3 veya 2-3 olmali.",
        }
    return {
        "ok": True,
        "sonuc": "galibiyet",
        "puan1": 3 if skor1 > skor2 else 0,
        "puan2": 3 if skor2 > skor1 else 0,
        "kazanan": "sinif1" if skor1 > skor2 else "sinif2",
    }


def ogrenci_mac_olustur(ogrenci_id: int, rakip_sinif_id: int, skor1: int, skor2: int,
                        aciklama: str = "", spor: str = "futbol") -> dict:
    try:
        skor1 = int(skor1)
        skor2 = int(skor2)
        rakip_sinif_id = int(rakip_sinif_id)
    except Exception:
        return {"ok": False, "sebep": "Skor ve rakip sinif gecersiz."}
    spor = (spor or "futbol").strip().lower()
    skor_kontrol = _ogrenci_mac_skor_kontrol(spor, skor1, skor2)
    if not skor_kontrol.get("ok"):
        return skor_kontrol
    con = _conn()
    try:
        _ogrenci_maclari_init(con)
        ogr = con.execute(
            "SELECT sinif_id FROM ogrenciler WHERE id=?", (ogrenci_id,)
        ).fetchone()
        if not ogr:
            return {"ok": False, "sebep": "Ogrenci bulunamadi."}
        sinif1_id = int(ogr["sinif_id"])
        rakip = con.execute("SELECT id FROM siniflar WHERE id=?", (rakip_sinif_id,)).fetchone()
        if not rakip:
            return {"ok": False, "sebep": "Rakip sinif bulunamadi."}
        if sinif1_id == rakip_sinif_id:
            return {"ok": False, "sebep": "Rakip sinif kendi sinifiniz olamaz."}
        con.execute("""
            INSERT INTO ogrenci_maclari
                (olusturan_ogrenci_id, sinif1_id, sinif2_id, spor, skor1, skor2, aciklama, tarih)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ogrenci_id, sinif1_id, rakip_sinif_id, spor, skor1, skor2,
            (aciklama or "").strip()[:500],
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        ))
        mac_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.commit()
        return {"ok": True, "id": mac_id}
    finally:
        con.close()


def _ogrenci_mac_satirlari(con, where: str = "", params: tuple = (), limit: int = 100) -> list[dict]:
    sql = f"""
        SELECT m.*,
               o.ad_soyad AS olusturan_adi,
               s1.sinif_adi AS sinif1_adi,
               s2.sinif_adi AS sinif2_adi,
               og.ad_soyad AS onaylayan_adi,
               CASE WHEN COALESCE(m.spor, 'futbol') = 'voleybol' THEN 'Voleybol' ELSE 'Futbol' END AS spor_adi,
               CASE
                    WHEN m.skor1 = m.skor2 THEN NULL
                    WHEN m.skor1 > m.skor2 THEN m.sinif1_id
                    ELSE m.sinif2_id
               END AS kazanan_sinif_id,
               CASE
                    WHEN m.skor1 = m.skor2 THEN 'Berabere'
                    WHEN m.skor1 > m.skor2 THEN s1.sinif_adi
                    ELSE s2.sinif_adi
               END AS kazanan_sinif_adi
        FROM ogrenci_maclari m
        JOIN ogrenciler o ON o.id = m.olusturan_ogrenci_id
        JOIN siniflar s1 ON s1.id = m.sinif1_id
        JOIN siniflar s2 ON s2.id = m.sinif2_id
        LEFT JOIN ogretmenler og ON og.id = m.onaylayan_ogretmen_id
        {where}
        ORDER BY m.id DESC
        LIMIT ?
    """
    return [dict(r) for r in con.execute(sql, (*params, limit)).fetchall()]


def ogrenci_mac_listesi(sinif_id: int | None = None, durum: str | None = None,
                        limit: int = 50, spor: str | None = None) -> list[dict]:
    con = _conn()
    try:
        _ogrenci_maclari_init(con)
        kosullar = []
        params: list = []
        if sinif_id is not None:
            kosullar.append("(m.sinif1_id = ? OR m.sinif2_id = ?)")
            params.extend([sinif_id, sinif_id])
        if durum:
            kosullar.append("m.durum = ?")
            params.append(durum)
        if spor:
            kosullar.append("COALESCE(m.spor, 'futbol') = ?")
            params.append(spor.strip().lower())
        where = "WHERE " + " AND ".join(kosullar) if kosullar else ""
        return _ogrenci_mac_satirlari(con, where, tuple(params), limit)
    finally:
        con.close()


def ogrenci_mac_detay(mac_id: int) -> dict | None:
    con = _conn()
    try:
        _ogrenci_maclari_init(con)
        rows = _ogrenci_mac_satirlari(con, "WHERE m.id = ?", (mac_id,), 1)
        return rows[0] if rows else None
    finally:
        con.close()


def ogretmen_onay_bekleyen_ogrenci_maclari(ogretmen_id: int, tum_siniflar: bool = False,
                                           durum: str | None = "onay_bekliyor") -> list[dict]:
    con = _conn()
    try:
        _ogrenci_maclari_init(con)
        kosullar = []
        params: list = []
        if durum:
            kosullar.append("m.durum = ?")
            params.append(durum)
        if not tum_siniflar:
            ids = [r["sinif_id"] for r in con.execute(
                "SELECT sinif_id FROM ogretmen_sinif WHERE ogretmen_id=?", (ogretmen_id,)
            ).fetchall()]
            if not ids:
                return []
            yer = ",".join("?" * len(ids))
            kosullar.append(f"(m.sinif1_id IN ({yer}) OR m.sinif2_id IN ({yer}))")
            params.extend(ids + ids)
        where = "WHERE " + " AND ".join(kosullar) if kosullar else ""
        return _ogrenci_mac_satirlari(con, where, tuple(params), 100)
    finally:
        con.close()


def ogrenci_mac_onayla(mac_id: int, ogretmen_id: int, onay: bool = True) -> dict:
    con = _conn()
    try:
        _ogrenci_maclari_init(con)
        mac = con.execute("SELECT * FROM ogrenci_maclari WHERE id=?", (mac_id,)).fetchone()
        if not mac:
            return {"ok": False, "sebep": "Mac bulunamadi."}
        if mac["durum"] != "onay_bekliyor":
            return {"ok": False, "sebep": "Bu mac zaten islenmis."}
        simdi = datetime.now().strftime("%Y-%m-%d %H:%M")
        if not onay:
            con.execute("""
                UPDATE ogrenci_maclari
                SET durum='reddedildi', onaylayan_ogretmen_id=?, onay_tarihi=?
                WHERE id=?
            """, (ogretmen_id, simdi, mac_id))
            con.commit()
            return {"ok": True, "durum": "reddedildi"}
        skor1, skor2 = int(mac["skor1"]), int(mac["skor2"])
        spor = (mac["spor"] or "futbol").strip().lower()
        skor_kontrol = _ogrenci_mac_skor_kontrol(spor, skor1, skor2)
        if not skor_kontrol.get("ok"):
            return skor_kontrol
        if skor_kontrol.get("sonuc") == "beraberlik":
            puan1 = _lig_puan_artir_miktar(con, int(mac["sinif1_id"]), 1)
            puan2 = _lig_puan_artir_miktar(con, int(mac["sinif2_id"]), 1)
            con.execute("""
                UPDATE ogrenci_maclari
                SET durum='onaylandi', onaylayan_ogretmen_id=?, onay_tarihi=?, puan_isledi=1
                WHERE id=?
            """, (ogretmen_id, simdi, mac_id))
            con.commit()
            return {
                "ok": True,
                "durum": "onaylandi",
                "beraberlik": True,
                "puan1": puan1,
                "puan2": puan2,
            }
        kazanan_id = int(mac["sinif1_id"] if skor1 > skor2 else mac["sinif2_id"])
        yeni_puan = _lig_puan_artir_miktar(con, kazanan_id, 3)
        con.execute("""
            UPDATE ogrenci_maclari
            SET durum='onaylandi', onaylayan_ogretmen_id=?, onay_tarihi=?, puan_isledi=1
            WHERE id=?
        """, (ogretmen_id, simdi, mac_id))
        con.commit()
        return {"ok": True, "durum": "onaylandi", "kazanan_sinif_id": kazanan_id, "puan": yeni_puan}
    finally:
        con.close()


def _quiz_init(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS quiz_sorulari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_seviyesi INTEGER NOT NULL, ders TEXT NOT NULL,
            soru TEXT NOT NULL, secenek_a TEXT NOT NULL, secenek_b TEXT NOT NULL,
            secenek_c TEXT NOT NULL, secenek_d TEXT NOT NULL,
            dogru_cevap TEXT NOT NULL, sira INTEGER NOT NULL DEFAULT 1
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS quiz_sonuclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sinif_id INTEGER REFERENCES siniflar(id),
            tarih TEXT NOT NULL, ders TEXT NOT NULL,
            sinif_seviyesi INTEGER NOT NULL,
            dogru INTEGER NOT NULL DEFAULT 0, yanlis INTEGER NOT NULL DEFAULT 0,
            puan_degisim INTEGER NOT NULL DEFAULT 0
        )
    """)
    con.commit()


def quiz_sorulari_yukle() -> None:
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
    secilen = []
    for i in range(sayi):
        secilen.append(tumSorular[(offset + i * 3) % n])
    return secilen


def quiz_sonuc_kaydet(sinif_id: int, ders: str,
                      sinif_seviyesi: int, dogru: int, yanlis: int) -> dict:
    puan_degisim = dogru - yanlis
    tarih = datetime.now().strftime("%Y-%m-%d")
    con = _conn()
    _quiz_init(con)
    con.execute("""
        INSERT INTO quiz_sonuclari
            (sinif_id, tarih, ders, sinif_seviyesi, dogru, yanlis, puan_degisim)
        VALUES (?,?,?,?,?,?,?)
    """, (sinif_id, tarih, ders, sinif_seviyesi, dogru, yanlis, puan_degisim))
    con.commit(); con.close()
    return {"ok": True, "puan_degisim": puan_degisim}


def quiz_gunluk_dersleri(sinif_id: int, tarih: str = None) -> list[str]:
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


# ══════════════════════════════════════════════════════════════════════════
# Ek özellikler: admin_meta, randevu, yansıma, hedef, rapor yardımcıları
# ══════════════════════════════════════════════════════════════════════════


def admin_meta_get(anahtar: str, varsayilan: str = "") -> str:
    con = _conn()
    _yardimci_tablolar_init(con)
    row = con.execute("SELECT deger FROM admin_meta WHERE anahtar = ?", (anahtar,)).fetchone()
    con.close()
    return str(row["deger"]) if row else varsayilan


def admin_meta_set(anahtar: str, deger: str) -> None:
    con = _conn()
    _yardimci_tablolar_init(con)
    con.execute(
        "INSERT INTO admin_meta (anahtar, deger) VALUES (?, ?) ON CONFLICT(anahtar) DO UPDATE SET deger = excluded.deger",
        (anahtar, deger),
    )
    con.commit()
    con.close()


def randevu_talep_by_id(talep_id: int) -> dict | None:
    con = _conn()
    _yardimci_tablolar_init(con)
    row = con.execute("SELECT * FROM randevu_talebi WHERE id = ?", (talep_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def gunluk_yansima_by_id(yansima_id: int) -> dict | None:
    con = _conn()
    _yardimci_tablolar_init(con)
    row = con.execute("""
        SELECT g.*, o.sinif_id AS ogrenci_sinif_id
        FROM gunluk_yansima g
        JOIN ogrenciler o ON o.id = g.ogrenci_id
        WHERE g.id = ?
    """, (yansima_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def randevu_talep_ekle(ogrenci_id: int, sinif_id: int, mesaj: str) -> dict:
    z = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = _conn()
    _yardimci_tablolar_init(con)
    cur = con.execute(
        """
        INSERT INTO randevu_talebi (ogrenci_id, sinif_id, mesaj, talep_tarihi, durum)
        VALUES (?,?,?,?, 'bekliyor')
        """,
        (ogrenci_id, sinif_id, (mesaj or "").strip()[:500], z),
    )
    rid = cur.lastrowid
    con.commit()
    con.close()
    return {"ok": True, "id": rid}


def randevu_listesi_siniflar(sinif_ids: list[int]) -> list[dict]:
    if not sinif_ids:
        return []
    con = _conn()
    _yardimci_tablolar_init(con)
    q = ",".join("?" * len(sinif_ids))
    rows = [dict(r) for r in con.execute(f"""
        SELECT r.*, o.ad_soyad AS ogrenci_ad, o.ogr_no, s.sinif_adi
        FROM randevu_talebi r
        JOIN ogrenciler o ON o.id = r.ogrenci_id
        JOIN siniflar s ON s.id = r.sinif_id
        WHERE r.sinif_id IN ({q})
        ORDER BY r.id DESC
    """, sinif_ids).fetchall()]
    con.close()
    return rows


def randevu_durum_guncelle(talep_id: int, durum: str) -> dict:
    if durum not in ("bekliyor", "gorusuldu", "iptal"):
        durum = "bekliyor"
    con = _conn()
    _yardimci_tablolar_init(con)
    con.execute("UPDATE randevu_talebi SET durum = ? WHERE id = ?", (durum, talep_id))
    con.commit()
    con.close()
    return {"ok": True}


def gunluk_yansima_ekle(ogrenci_id: int, metin: str) -> dict:
    metin = (metin or "").strip()
    if len(metin) < 3:
        return {"ok": False, "sebep": "Metin cok kisa"}
    if len(metin) > 800:
        metin = metin[:800]
    bugun = datetime.now().strftime("%Y-%m-%d")
    con = _conn()
    _yardimci_tablolar_init(con)
    var = con.execute(
        "SELECT id FROM gunluk_yansima WHERE ogrenci_id=? AND substr(tarih,1,10)=?",
        (ogrenci_id, bugun),
    ).fetchone()
    if var:
        con.close()
        return {"ok": False, "sebep": "Bugun icin zaten kayit var"}
    z = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute(
        """
        INSERT INTO gunluk_yansima (ogrenci_id, metin, tarih, durum)
        VALUES (?,?,?, 'bekliyor')
        """,
        (ogrenci_id, metin, z),
    )
    con.commit()
    con.close()
    return {"ok": True}


def gunluk_yansima_bekleyen_siniflar(sinif_ids: list[int]) -> list[dict]:
    if not sinif_ids:
        return []
    con = _conn()
    _yardimci_tablolar_init(con)
    q = ",".join("?" * len(sinif_ids))
    rows = [dict(r) for r in con.execute(f"""
        SELECT g.*, o.ad_soyad AS ogrenci_ad, o.ogr_no, s.sinif_adi
        FROM gunluk_yansima g
        JOIN ogrenciler o ON o.id = g.ogrenci_id
        JOIN siniflar s ON s.id = o.sinif_id
        WHERE o.sinif_id IN ({q}) AND g.durum = 'bekliyor'
        ORDER BY g.id DESC
    """, sinif_ids).fetchall()]
    con.close()
    return rows


def gunluk_yansima_ogrenci_gecmis(ogrenci_id: int, limit: int = 20) -> list[dict]:
    con = _conn()
    _yardimci_tablolar_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT * FROM gunluk_yansima WHERE ogrenci_id = ?
        ORDER BY id DESC LIMIT ?
    """, (ogrenci_id, limit)).fetchall()]
    con.close()
    return rows


def gunluk_yansima_degerlendir(
    yansima_id: int,
    ogretmen_id: int,
    durum: str,
    ogretmen_notu: str,
) -> dict:
    if durum not in ("onaylandi", "reddedildi"):
        durum = "onaylandi"
    con = _conn()
    _yardimci_tablolar_init(con)
    con.execute(
        """
        UPDATE gunluk_yansima SET durum=?, ogretmen_notu=?, degerlendiren_id=?
        WHERE id=?
        """,
        (durum, (ogretmen_notu or "")[:500], ogretmen_id, yansima_id),
    )
    con.commit()
    con.close()
    return {"ok": True}


def davranis_hedefi_ekle(
    sinif_id: int,
    ogretmen_id: int,
    ogrenci_id: int | None,
    hedef_tik_max: int,
    baslangic: str,
    bitis: str,
    aciklama: str,
) -> dict:
    if ogrenci_id is not None:
        con_chk = _conn()
        ok = con_chk.execute(
            "SELECT 1 FROM ogrenciler WHERE id = ? AND sinif_id = ?",
            (ogrenci_id, sinif_id),
        ).fetchone()
        con_chk.close()
        if not ok:
            return {"ok": False, "sebep": "ogrenci_sinif_uyusmuyor"}
    con = _conn()
    _yardimci_tablolar_init(con)
    con.execute(
        """
        INSERT INTO davranis_hedefi
        (sinif_id, ogretmen_id, ogrenci_id, hedef_tik_max, baslangic, bitis, aciklama, aktif)
        VALUES (?,?,?,?,?,?,?,1)
        """,
        (
            sinif_id,
            ogretmen_id,
            ogrenci_id,
            max(1, min(50, int(hedef_tik_max))),
            baslangic,
            bitis,
            (aciklama or "")[:200],
        ),
    )
    con.commit()
    con.close()
    return {"ok": True}


def davranis_hedefi_liste_sinif(sinif_id: int) -> list[dict]:
    con = _conn()
    _yardimci_tablolar_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT d.*, o.ad_soyad AS ogrenci_ad
        FROM davranis_hedefi d
        LEFT JOIN ogrenciler o ON o.id = d.ogrenci_id
        WHERE d.sinif_id = ? AND d.aktif = 1
        ORDER BY d.id DESC
    """, (sinif_id,)).fetchall()]
    con.close()
    return rows


def davranis_hedefi_pasif_et(hedef_id: int) -> None:
    con = _conn()
    _yardimci_tablolar_init(con)
    con.execute("UPDATE davranis_hedefi SET aktif = 0 WHERE id = ?", (hedef_id,))
    con.commit()
    con.close()


def tik_sayisi_sinif_aralik(sinif_id: int, baslangic: str, bitis: str) -> int:
    con = _conn()
    n = con.execute("""
        SELECT COUNT(*) FROM tik_kayitlari t
        JOIN ogrenciler o ON o.id = t.ogrenci_id
        WHERE o.sinif_id = ?
          AND substr(t.tarih, 1, 10) >= ?
          AND substr(t.tarih, 1, 10) <= ?
    """, (sinif_id, baslangic, bitis)).fetchone()[0]
    con.close()
    return int(n)


def olumlu_sayisi_sinif_aralik(sinif_id: int, baslangic: str, bitis: str) -> int:
    con = _conn()
    n = con.execute("""
        SELECT COUNT(*) FROM olumlu_davranis
        WHERE sinif_id = ?
          AND substr(tarih, 1, 10) >= ?
          AND substr(tarih, 1, 10) <= ?
    """, (sinif_id, baslangic, bitis)).fetchone()[0]
    con.close()
    return int(n)


def haftalik_sinif_ozeti(sinif_id: int, gun: int = 7) -> dict:
    """Son N gunun tik ve olumlu sayisi."""
    bit = datetime.now().date()
    bas = bit - timedelta(days=gun - 1)
    bs, bt = bas.isoformat(), bit.isoformat()
    return {
        "baslangic": bs,
        "bitis": bt,
        "tik": tik_sayisi_sinif_aralik(sinif_id, bs, bt),
        "olumlu": olumlu_sayisi_sinif_aralik(sinif_id, bs, bt),
    }


def ogretmen_notlari_veli_ozeti(ogrenci_id: int, limit: int = 25) -> list[dict]:
    con = _conn()
    _gelisim_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT ono.not_metni, ono.tarih, og.ad_soyad AS ogretmen
        FROM ogretmen_notlari ono
        JOIN ogretmenler og ON og.id = ono.ogretmen_id
        WHERE ono.ogrenci_id = ? AND ono.veliye_acik = 1
        ORDER BY ono.tarih DESC
        LIMIT ?
    """, (ogrenci_id, limit)).fetchall()]
    con.close()
    return rows


def veli_ozet_metrikleri(ogrenci_id: int, gun: int = 30) -> dict:
    """Son gun tik sayisi ve veliye acik son notlar ozeti."""
    bit = datetime.now().date()
    bas = bit - timedelta(days=gun - 1)
    bs, bt = bas.isoformat(), bit.isoformat()
    con = _conn()
    tik_n = con.execute("""
        SELECT COUNT(*) FROM tik_kayitlari WHERE ogrenci_id = ?
          AND substr(tarih, 1, 10) >= ?
          AND substr(tarih, 1, 10) <= ?
    """, (ogrenci_id, bs, bt)).fetchone()[0]
    con.close()
    notlar = ogretmen_notlari_veli_ozeti(ogrenci_id, 5)
    return {"tik_son_gun": int(tik_n), "gun": gun, "notlar": notlar}


def anonim_sinif_dagilimi(sinif_id: int) -> dict:
    """Isimsiz durum bantlari + ortalama tik (sunum icin)."""
    con = _conn()
    rows = [dict(r) for r in con.execute("""
        SELECT o.id,
               COUNT(t.id) AS tik_sayisi
        FROM ogrenciler o
        LEFT JOIN tik_kayitlari t ON t.ogrenci_id = o.id
        WHERE o.sinif_id = ?
        GROUP BY o.id
    """, (sinif_id,)).fetchall()]
    con.close()
    n = len(rows) or 1
    toplam = sum(int(r["tik_sayisi"] or 0) for r in rows)
    dd = {"temiz": 0, "uyari": 0, "idari": 0, "veli": 0, "tutanak": 0, "disiplin": 0}
    for r in rows:
        t = int(r["tik_sayisi"] or 0)
        if t == 0:
            dd["temiz"] += 1
        elif t <= 2:
            dd["uyari"] += 1
        elif t <= 5:
            dd["idari"] += 1
        elif t <= 8:
            dd["veli"] += 1
        elif t <= 11:
            dd["tutanak"] += 1
        else:
            dd["disiplin"] += 1
    return {
        "ogrenci_sayisi": len(rows),
        "ortalama_tik": round(toplam / n, 2),
        "toplam_tik": toplam,
        "dagilim": dd,
    }


# ══════════════════════════════════════════════════════════════════════════
# Rapor arşivi (PDF anlık görüntü + JSON; silinen tiklerden sonra da saklanır)
# ══════════════════════════════════════════════════════════════════════════

def tik_kayitlari_siniflarda(sinif_ids: list[int]) -> list[dict]:
    """Belirtilen sınıflardaki tüm tik satırları (rapor / arşiv anlık görüntüsü)."""
    if not sinif_ids:
        return []
    con = _conn()
    q = ",".join("?" * len(sinif_ids))
    rows = [dict(r) for r in con.execute(f"""
        SELECT t.id AS tik_id, t.kriter, t.tarih,
               o.id AS ogrenci_id, o.ad_soyad, o.ogr_no, s.sinif_adi,
               og.ad_soyad AS ogretmen
        FROM tik_kayitlari t
        JOIN ogrenciler o ON o.id = t.ogrenci_id
        JOIN siniflar s ON s.id = o.sinif_id
        JOIN ogretmenler og ON og.id = t.ogretmen_id
        WHERE o.sinif_id IN ({q})
        ORDER BY t.tarih DESC
    """, sinif_ids).fetchall()]
    con.close()
    return rows


def rapor_arsiv_kaydet(
    ogretmen_id: int,
    ogretmen_adi: str,
    kapsam: str,
    sinif_id: int | None,
    json_snapshot: str,
    pdf_blob: bytes,
    dosya_adi: str,
) -> int:
    con = _conn()
    _rapor_arsiv_init(con)
    olusturma = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute("""
        INSERT INTO rapor_arsiv (olusturma, ogretmen_id, ogretmen_adi, kapsam, sinif_id,
                                 json_snapshot, pdf_blob, dosya_adi)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        olusturma, ogretmen_id, ogretmen_adi.strip(), kapsam.strip(),
        sinif_id, json_snapshot, pdf_blob, dosya_adi.strip(),
    ))
    con.commit()
    rid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.close()
    return int(rid)


def rapor_arsiv_listesi(ogretmen_id: int, limit: int = 50) -> list[dict]:
    con = _conn()
    _rapor_arsiv_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT id, olusturma, kapsam, sinif_id, dosya_adi,
               LENGTH(pdf_blob) AS pdf_boyutu
        FROM rapor_arsiv
        WHERE ogretmen_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (ogretmen_id, limit)).fetchall()]
    con.close()
    return rows


def rapor_arsiv_pdf_oku(arsiv_id: int, ogretmen_id: int) -> dict | None:
    con = _conn()
    _rapor_arsiv_init(con)
    row = con.execute("""
        SELECT id, dosya_adi, pdf_blob, json_snapshot, olusturma, kapsam
        FROM rapor_arsiv
        WHERE id = ? AND ogretmen_id = ?
    """, (arsiv_id, ogretmen_id)).fetchone()
    con.close()
    return dict(row) if row else None


def rapor_arsiv_tumunu_yedekle_ve_sil(ogretmen_id: int) -> dict:
    """Aktif PDF arşivindeki tüm kayıtları yedek tablosuna taşır ve ana listeden siler."""
    gid = str(uuid.uuid4())
    silinme = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = _conn()
    _rapor_arsiv_init(con)
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM rapor_arsiv WHERE ogretmen_id = ?", (ogretmen_id,)
    ).fetchall()]
    for r in rows:
        con.execute("""
            INSERT INTO rapor_arsiv_yedek (
                grup_id, silinme, kaynak_id, olusturma, ogretmen_id, ogretmen_adi,
                kapsam, sinif_id, json_snapshot, pdf_blob, dosya_adi)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            gid,
            silinme,
            r.get("id"),
            r["olusturma"],
            r["ogretmen_id"],
            r["ogretmen_adi"],
            r["kapsam"],
            r["sinif_id"],
            r["json_snapshot"],
            r["pdf_blob"],
            r["dosya_adi"],
        ))
    con.execute("DELETE FROM rapor_arsiv WHERE ogretmen_id = ?", (ogretmen_id,))
    con.commit()
    n = len(rows)
    con.close()
    return {"ok": True, "grup_id": gid, "tasinan": n}


def rapor_arsiv_yedek_gruplari(ogretmen_id: int) -> list[dict]:
    """Manuel silme işlemlerinin özeti (geri yükleme için)."""
    con = _conn()
    _rapor_arsiv_yedek_init(con)
    rows = [dict(r) for r in con.execute("""
        SELECT grup_id,
               MIN(silinme) AS silinme,
               COUNT(*) AS adet
        FROM rapor_arsiv_yedek
        WHERE ogretmen_id = ?
        GROUP BY grup_id
        ORDER BY silinme DESC
    """, (ogretmen_id,)).fetchall()]
    con.close()
    return rows


def rapor_arsiv_grubu_geri_yukle(ogretmen_id: int, grup_id: str) -> dict:
    """Belirtilen yedek grubunu tekrar aktif arşive ekler; yedekten düşer."""
    con = _conn()
    _rapor_arsiv_yedek_init(con)
    n = con.execute(
        "SELECT COUNT(*) FROM rapor_arsiv_yedek WHERE ogretmen_id = ? AND grup_id = ?",
        (ogretmen_id, grup_id),
    ).fetchone()[0]
    if n == 0:
        con.close()
        return {"ok": False, "sebep": "Bu geri yükleme grubu bulunamadı."}
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM rapor_arsiv_yedek WHERE ogretmen_id = ? AND grup_id = ?",
        (ogretmen_id, grup_id),
    ).fetchall()]
    for r in rows:
        con.execute("""
            INSERT INTO rapor_arsiv (
                olusturma, ogretmen_id, ogretmen_adi, kapsam, sinif_id,
                json_snapshot, pdf_blob, dosya_adi)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            r["olusturma"],
            r["ogretmen_id"],
            r["ogretmen_adi"],
            r["kapsam"],
            r["sinif_id"],
            r["json_snapshot"],
            r["pdf_blob"],
            r["dosya_adi"],
        ))
    con.execute(
        "DELETE FROM rapor_arsiv_yedek WHERE ogretmen_id = ? AND grup_id = ?",
        (ogretmen_id, grup_id),
    )
    con.commit()
    con.close()
    return {"ok": True, "geri_yuklenen": len(rows)}

def ogrenci_ozellikleri_getir(ogrenci_id: int, tik_sayisi: int = 0) -> dict:
    con = _conn()
    row = con.execute("SELECT * FROM ogrenci_ozellikler WHERE ogrenci_id = ?", (ogrenci_id,)).fetchone()
    
    # Kalan puan hesabı: 1 tik = 1 puan. Puanlar temel 50 üzerine eklenir.
    toplam_harcanan = 0
    if row:
        toplam_harcanan = (row['hiz'] - 50) + (row['sut'] - 50) + (row['pas'] - 50) + (row['defans'] - 50) + (row['kaleci'] - 50)
        kalan = max(0, tik_sayisi - toplam_harcanan)
        if kalan != row['kalan_puan']:
            con.execute("UPDATE ogrenci_ozellikler SET kalan_puan = ? WHERE ogrenci_id = ?", (kalan, ogrenci_id))
            con.commit()
            row = con.execute("SELECT * FROM ogrenci_ozellikler WHERE ogrenci_id = ?", (ogrenci_id,)).fetchone()
    else:
        con.execute("INSERT INTO ogrenci_ozellikler (ogrenci_id, kalan_puan) VALUES (?, ?)", (ogrenci_id, tik_sayisi))
        con.commit()
        row = con.execute("SELECT * FROM ogrenci_ozellikler WHERE ogrenci_id = ?", (ogrenci_id,)).fetchone()
        
    con.close()
    return dict(row)

def ogrenci_ozellik_artir(ogrenci_id: int, ozellik: str, tik_sayisi: int) -> dict:
    gecerli = ['hiz', 'sut', 'pas', 'defans', 'kaleci']
    if ozellik not in gecerli: return {'ok': False, 'sebep': 'Geçersiz özellik'}
    
    con = _conn()
    row = con.execute("SELECT * FROM ogrenci_ozellikler WHERE ogrenci_id = ?", (ogrenci_id,)).fetchone()
    if not row:
        con.close()
        return {'ok': False, 'sebep': 'Özellik kaydı bulunamadı'}
        
    # Recalculate correctly to avoid async exploits
    toplam_harcanan = (row['hiz'] - 50) + (row['sut'] - 50) + (row['pas'] - 50) + (row['defans'] - 50) + (row['kaleci'] - 50)
    kalan = tik_sayisi - toplam_harcanan
    
    if kalan <= 0:
        con.close()
        return {'ok': False, 'sebep': 'Geliştirme puanınız kalmadı'}
        
    if row[ozellik] >= 99:
        con.close()
        return {'ok': False, 'sebep': 'Bu özellik maksimum seviyede'}
        
    con.execute(f"UPDATE ogrenci_ozellikler SET {ozellik} = {ozellik} + 1, kalan_puan = ? WHERE ogrenci_id = ?", (kalan - 1, ogrenci_id))
    con.commit()
    con.close()
    return {'ok': True, 'kalan': kalan - 1}

# ══════════════════════════════════════════════════════════════════════════
# ÖDEV TAKİBİ
# ══════════════════════════════════════════════════════════════════════════

_OYKOD_RE = re.compile(
    r"[A-ZĞÜŞÖÇİÜ][A-Za-zĞÜŞÖÇİÜğüşöçıü]*(?:\.[0-9]+)+",
    re.UNICODE,
)


def ogrenme_cikti_kodlari_cikar(metinler: list[str]) -> list[str]:
    """TYMM tarzi kodlari metinden ayiklar (orn. MAT.6.1.1, FEN.7.2.3)."""
    gordu: set[str] = set()
    sirali: list[str] = []
    for satir in metinler:
        if not isinstance(satir, str):
            continue
        for m in _OYKOD_RE.finditer(satir):
            kod = m.group(0).rstrip(".")
            if kod not in gordu:
                gordu.add(kod)
                sirali.append(kod)
    return sirali


def odev_olustur(
    ogretmen_id: int,
    sinif_id: int,
    ders_adi: str,
    tema_adi: str,
    konu_adi: str = "",
    ogrenme_ciktilari_json: str = "[]",
    sinif_seviyesi: int | None = None,
) -> int:
    konu_adi = (konu_adi or "").strip()
    try:
        oc_list = json.loads(ogrenme_ciktilari_json or "[]")
        if not isinstance(oc_list, list):
            oc_list = []
        ogrenme_ciktilari_json = json.dumps(oc_list, ensure_ascii=False)
    except Exception:
        oc_list = []
        ogrenme_ciktilari_json = "[]"
    kodlar = ogrenme_cikti_kodlari_cikar([str(x) for x in oc_list])
    kod_json = json.dumps(kodlar, ensure_ascii=False)
    sev = int(sinif_seviyesi) if sinif_seviyesi is not None else 0
    if sev < 0 or sev > 12:
        sev = 0
    con = _conn()
    _odev_init(con)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO odevler
            (ogretmen_id, sinif_id, ders_adi, tema_adi, konu_adi, ogrenme_ciktilari_json,
             ogrenme_cikti_kodlari_json, sinif_seviyesi,
             baslik, aciklama, son_tarih, ders, tarih)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)
        """,
        (
            ogretmen_id,
            sinif_id,
            ders_adi,
            tema_adi,
            konu_adi,
            ogrenme_ciktilari_json,
            kod_json,
            sev,
            tema_adi,
            datetime.now().strftime("%Y-%m-%d"),
            ders_adi,
            datetime.now().isoformat(),
        )
    )
    odev_id = cur.lastrowid
    
    # Tüm sınıf öğrencilerine varsayılan olarak 'tamamlamadi' ekle
    ogrenciler = con.execute("SELECT id FROM ogrenciler WHERE sinif_id = ?", (sinif_id,)).fetchall()
    for row in ogrenciler:
        rid = int(row["id"])
        cur.execute(
            "INSERT INTO odev_sonuclari (odev_id, ogrenci_id, durum) VALUES (?, ?, 'tamamlamadi')",
            (odev_id, rid),
        )
    con.commit()
    con.close()
    return odev_id

def odevleri_getir(ogretmen_id: int):
    con = _conn()
    _odev_init(con)
    rows = con.execute(
        '''SELECT o.id, s.sinif_adi,
                  COALESCE(NULLIF(o.ders_adi, ''), o.ders, 'Genel') AS ders_adi,
                  COALESCE(NULLIF(o.tema_adi, ''), o.baslik, 'Ödev') AS tema_adi,
                  COALESCE(NULLIF(o.konu_adi, ''), '') AS konu_adi,
                  COALESCE(o.sinif_seviyesi, 0) AS sinif_seviyesi,
                  COALESCE(NULLIF(o.ogrenme_cikti_kodlari_json, ''), '[]') AS ogrenme_cikti_kodlari_json,
                  o.tarih,
                  (SELECT count(*) FROM odev_tamamlayanlar WHERE odev_id = o.id)
                    + (SELECT count(*) FROM odev_sonuclari WHERE odev_id = o.id AND durum = 'tamamladi') as tamamlayanlar,
                  COALESCE(NULLIF((SELECT count(*) FROM odev_sonuclari WHERE odev_id = o.id), 0),
                           (SELECT count(*) FROM ogrenciler WHERE sinif_id = o.sinif_id)) as toplam_ogrenci
           FROM odevler o
           JOIN siniflar s ON o.sinif_id = s.id
           WHERE o.ogretmen_id = ?
           ORDER BY o.id DESC''' ,
        (ogretmen_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def odevleri_sinif_icin_getir(ogretmen_id: int, sinif_id: int, limit: int = 36) -> list[dict]:
    """Belirli sınıftaki tema/ödev kayıtları (öğretmen analiz / PDF bağlantıları için)."""
    con = _conn()
    _odev_init(con)
    rows = con.execute(
        """SELECT o.id, s.sinif_adi,
                  COALESCE(NULLIF(o.ders_adi, ''), o.ders, 'Genel') AS ders_adi,
                  COALESCE(NULLIF(o.tema_adi, ''), o.baslik, 'Ödev') AS tema_adi,
                  COALESCE(NULLIF(o.konu_adi, ''), '') AS konu_kisa,
                  COALESCE(o.sinif_seviyesi, 0) AS sinif_seviyesi,
                  o.tarih,
                  (SELECT count(*) FROM odev_tamamlayanlar WHERE odev_id = o.id)
                    + (SELECT count(*) FROM odev_sonuclari WHERE odev_id = o.id AND durum = 'tamamladi') AS tamamlayanlar,
                  COALESCE(NULLIF((SELECT count(*) FROM odev_sonuclari WHERE odev_id = o.id), 0),
                           (SELECT count(*) FROM ogrenciler WHERE sinif_id = o.sinif_id)) AS toplam_ogrenci
           FROM odevler o
           JOIN siniflar s ON o.sinif_id = s.id
           WHERE o.ogretmen_id = ? AND o.sinif_id = ?
           ORDER BY o.id DESC
           LIMIT ?""",
        (ogretmen_id, sinif_id, limit),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def odev_detay_getir(odev_id: int, ogretmen_id: int):
    con = _conn()
    _odev_init(con)
    odev = con.execute(
        """
        SELECT o.id, o.sinif_id, o.ogretmen_id, o.tarih,
               COALESCE(NULLIF(o.ders_adi, ''), o.ders, 'Genel') AS ders_adi,
               COALESCE(NULLIF(o.tema_adi, ''), o.baslik, 'Ödev') AS tema_adi,
               COALESCE(NULLIF(o.konu_adi, ''), '') AS konu_adi,
               COALESCE(NULLIF(o.ogrenme_ciktilari_json, ''), '[]') AS ogrenme_ciktilari_json,
               COALESCE(NULLIF(o.ogrenme_cikti_kodlari_json, ''), '[]') AS ogrenme_cikti_kodlari_json,
               COALESCE(o.sinif_seviyesi, 0) AS sinif_seviyesi,
               s.sinif_adi
        FROM odevler o
        JOIN siniflar s ON o.sinif_id = s.id
        WHERE o.id = ? AND o.ogretmen_id = ?
        """,
        (odev_id, ogretmen_id)
    ).fetchone()
    if not odev:
        con.close()
        return None
        
    ogrenciler = con.execute(
        '''SELECT og.id, og.ad_soyad, og.ogr_no,
                  CASE
                    WHEN ot.id IS NOT NULL THEN 'tamamladi'
                    ELSE COALESCE(os.durum, 'tamamlamadi')
                  END AS durum
           FROM ogrenciler og
           LEFT JOIN odev_sonuclari os ON os.ogrenci_id = og.id AND os.odev_id = ?
           LEFT JOIN odev_tamamlayanlar ot ON ot.ogrenci_id = og.id AND ot.odev_id = ?
           WHERE og.sinif_id = ?
           ORDER BY og.ogr_no ASC''' ,
        (odev_id, odev_id, dict(odev)["sinif_id"])
    ).fetchall()
    con.close()
    return {"odev": dict(odev), "ogrenciler": [dict(r) for r in ogrenciler]}


def odev_detay_ogrenci_paylasim(odev_id: int, ogrenci_id: int) -> dict | None:
    """Öğrenci / veli: ödev kendi sınıfındaysa öğretmen doğrulaması olmadan detay (PDF üretimi için)."""
    con = _conn()
    _odev_init(con)
    ogr = con.execute(
        "SELECT id, sinif_id FROM ogrenciler WHERE id = ?",
        (ogrenci_id,),
    ).fetchone()
    if not ogr:
        con.close()
        return None
    sinif_ogr = dict(ogr)["sinif_id"]
    odev = con.execute(
        """
        SELECT o.id, o.sinif_id, o.ogretmen_id, o.tarih,
               COALESCE(NULLIF(o.ders_adi, ''), o.ders, 'Genel') AS ders_adi,
               COALESCE(NULLIF(o.tema_adi, ''), o.baslik, 'Ödev') AS tema_adi,
               COALESCE(NULLIF(o.konu_adi, ''), '') AS konu_adi,
               COALESCE(NULLIF(o.ogrenme_ciktilari_json, ''), '[]') AS ogrenme_ciktilari_json,
               COALESCE(NULLIF(o.ogrenme_cikti_kodlari_json, ''), '[]') AS ogrenme_cikti_kodlari_json,
               COALESCE(o.sinif_seviyesi, 0) AS sinif_seviyesi,
               s.sinif_adi
        FROM odevler o
        JOIN siniflar s ON o.sinif_id = s.id
        WHERE o.id = ?
        """,
        (odev_id,),
    ).fetchone()
    if not odev or dict(odev)["sinif_id"] != sinif_ogr:
        con.close()
        return None
    ogret_row = con.execute(
        "SELECT ad_soyad FROM ogretmenler WHERE id = ?",
        (dict(odev)["ogretmen_id"],),
    ).fetchone()
    ogretmen_adi = (dict(ogret_row)["ad_soyad"] if ogret_row else "") or ""

    ogrenciler = con.execute(
        """SELECT og.id, og.ad_soyad, og.ogr_no,
                  CASE
                    WHEN ot.id IS NOT NULL THEN 'tamamladi'
                    ELSE COALESCE(os.durum, 'tamamlamadi')
                  END AS durum
           FROM ogrenciler og
           LEFT JOIN odev_sonuclari os ON os.ogrenci_id = og.id AND os.odev_id = ?
           LEFT JOIN odev_tamamlayanlar ot ON ot.ogrenci_id = og.id AND ot.odev_id = ?
           WHERE og.sinif_id = ?
           ORDER BY og.ogr_no ASC""",
        (odev_id, odev_id, dict(odev)["sinif_id"]),
    ).fetchall()
    con.close()
    return {
        "odev": dict(odev),
        "ogrenciler": [dict(r) for r in ogrenciler],
        "ogretmen_adi": ogretmen_adi,
    }


def _odev_iso_hafta(tarih_raw: str) -> str:
    s = (tarih_raw or "")[:10]
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    except Exception:
        return "bilinmeyen"


def odev_mufredat_ozeti(ogretmen_id: int) -> dict:
    """Ders / tema / konu / sinif seviyesi / hafta bazinda odev ozeti."""
    from collections import defaultdict

    liste = odevleri_getir(ogretmen_id)
    by_ders: dict[str, list[int]] = defaultdict(list)
    by_tema: dict[tuple[str, str], list[int]] = defaultdict(list)
    by_konu: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    by_seviye: dict[tuple[str, int], list[int]] = defaultdict(list)
    by_hafta: dict[str, list[int]] = defaultdict(list)
    for r in liste:
        t = int(r["tamamlayanlar"] or 0)
        n = int(r["toplam_ogrenci"] or 0)
        p = round((t / n * 100) if n else 0)
        d = r["ders_adi"]
        tm = r["tema_adi"]
        k = (r.get("konu_adi") or "").strip()
        by_ders[d].append(p)
        by_tema[(d, tm)].append(p)
        if k:
            by_konu[(d, tm, k)].append(p)
        sev = int(r.get("sinif_seviyesi") or 0)
        if 5 <= sev <= 8:
            by_seviye[(d, sev)].append(p)
        hw = _odev_iso_hafta(str(r.get("tarih") or ""))
        if hw != "bilinmeyen":
            by_hafta[hw].append(p)

    def _avg(vals: list[int]) -> int:
        return round(sum(vals) / len(vals)) if vals else 0

    return {
        "toplam_odev": len(liste),
        "dersler": [
            {"ders_adi": k, "odev_sayisi": len(v), "ort_tamamlama": _avg(v)}
            for k, v in sorted(by_ders.items(), key=lambda x: x[0])
        ],
        "temalar": [
            {
                "ders_adi": a,
                "tema_adi": b,
                "odev_sayisi": len(v),
                "ort_tamamlama": _avg(v),
            }
            for (a, b), v in sorted(by_tema.items(), key=lambda x: (x[0][0], x[0][1]))
        ],
        "konular": [
            {
                "ders_adi": a,
                "tema_adi": b,
                "konu_adi": c,
                "odev_sayisi": len(v),
                "ort_tamamlama": _avg(v),
            }
            for (a, b, c), v in sorted(
                by_konu.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])
            )
        ],
        "ortaokul_seviye": [
            {
                "ders_adi": a,
                "sinif_seviyesi": b,
                "odev_sayisi": len(v),
                "ort_tamamlama": _avg(v),
            }
            for (a, b), v in sorted(by_seviye.items(), key=lambda x: (x[0][0], x[0][1]))
        ],
        "haftalar": [
            {"hafta": h, "odev_sayisi": len(v), "ort_tamamlama": _avg(v)}
            for h, v in sorted(by_hafta.items(), key=lambda x: x[0], reverse=True)[:24]
        ],
    }


def odev_durum_guncelle(odev_id: int, ogrenci_id: int, durum: str):
    con = _conn()
    _odev_init(con)
    cur = con.execute(
        "UPDATE odev_sonuclari SET durum = ? WHERE odev_id = ? AND ogrenci_id = ?",
        (durum, odev_id, ogrenci_id),
    )
    if cur.rowcount == 0:
        con.execute(
            "INSERT INTO odev_sonuclari (odev_id, ogrenci_id, durum) VALUES (?, ?, ?)",
            (odev_id, ogrenci_id, durum),
        )
    if durum == "tamamladi":
        row = con.execute("SELECT ogretmen_id FROM odevler WHERE id = ?", (odev_id,)).fetchone()
        con.execute(
            """
            INSERT OR IGNORE INTO odev_tamamlayanlar (odev_id, ogrenci_id, ogretmen_id, tarih)
            VALUES (?, ?, ?, ?)
            """,
            (odev_id, ogrenci_id, row["ogretmen_id"] if row else 0, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
    else:
        con.execute("DELETE FROM odev_tamamlayanlar WHERE odev_id = ? AND ogrenci_id = ?", (odev_id, ogrenci_id))
    con.commit()
    con.close()
