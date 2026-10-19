"""Migration 006: Sınavlar için yumuşak silme (silindi_at) sütunu."""
VERSION = 6


def up(con):
    for table in ("lgs_optik_sinav", "lgs_deneme"):
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        if "silindi_at" not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN silindi_at TEXT DEFAULT NULL")
    con.commit()


def down(con):
    for table in ("lgs_optik_sinav", "lgs_deneme"):
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        if "silindi_at" in cols:
            con.execute(f"UPDATE {table} SET silindi_at = NULL")
    con.commit()
