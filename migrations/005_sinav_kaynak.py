"""Migration 005: lgs_optik_sinav.kaynak ve giris_taslak / ogretmen_giris_tercih tabloları."""
VERSION = 5


def _ensure_optik_table(con):
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS lgs_optik_sinav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            tarih TEXT NOT NULL,
            pdf_dosya TEXT NOT NULL,
            cevaplar TEXT NOT NULL,
            soru_sayisi INTEGER NOT NULL,
            ogretmen_id INTEGER,
            olusturma TEXT NOT NULL,
            tur TEXT NOT NULL DEFAULT 'deneme'
        );
        """
    )


def up(con):
    _ensure_optik_table(con)
    cols = {r[1] for r in con.execute("PRAGMA table_info(lgs_optik_sinav)").fetchall()}
    if "kaynak" not in cols:
        con.execute("ALTER TABLE lgs_optik_sinav ADD COLUMN kaynak TEXT NOT NULL DEFAULT 'ev'")
    con.execute(
        """
        UPDATE lgs_optik_sinav
        SET kaynak = 'ev_yaprak'
        WHERE tur = 'yaprak' AND (kaynak IS NULL OR kaynak = '' OR kaynak = 'ev')
        """
    )
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
    con.commit()


def down(con):
    con.executescript(
        """
        DROP TABLE IF EXISTS giris_taslak;
        DROP TABLE IF EXISTS ogretmen_giris_tercih;
        """
    )
    con.commit()
