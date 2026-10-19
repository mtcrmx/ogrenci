"""
migrations
----------
Ekleyici veritabanı migration yöneticisi.
Uygulanan sürümler `schema_version` tablosunda tutulur.
"""

import importlib.util
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parent
_PATTERN = re.compile(r"^(\d{3})_([a-zA-Z0-9_]+)\.py$")


def _ensure_schema_table(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            name       TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)
    con.commit()


def discover_migrations() -> list[tuple[int, str, Path]]:
    items: list[tuple[int, str, Path]] = []
    for entry in sorted(os.listdir(_MIGRATIONS_DIR)):
        m = _PATTERN.match(entry)
        if not m:
            continue
        ver = int(m.group(1))
        name = entry[:-3]
        items.append((ver, name, _MIGRATIONS_DIR / entry))
    items.sort(key=lambda x: x[0])
    return items


def load_migration_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"migrations.{path.stem}", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Migration yüklenemedi: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def applied_versions(con: sqlite3.Connection) -> set[int]:
    _ensure_schema_table(con)
    return {int(r[0]) for r in con.execute("SELECT version FROM schema_version").fetchall()}


def current_version(con: sqlite3.Connection) -> int:
    versions = applied_versions(con)
    return max(versions) if versions else 0


def migrate_up(con: sqlite3.Connection, target: int | None = None) -> list[str]:
    _ensure_schema_table(con)
    applied = applied_versions(con)
    ran: list[str] = []
    for ver, name, path in discover_migrations():
        if target is not None and ver > target:
            break
        if ver in applied:
            continue
        mod = load_migration_module(path)
        mod.up(con)
        con.execute(
            "INSERT OR REPLACE INTO schema_version (version, name, applied_at) VALUES (?, ?, ?)",
            (ver, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        con.commit()
        ran.append(name)
    return ran


def migrate_down(con: sqlite3.Connection, target: int = 0) -> list[str]:
    _ensure_schema_table(con)
    applied = applied_versions(con)
    reverted: list[str] = []
    for ver, name, path in reversed(discover_migrations()):
        if ver <= target:
            break
        if ver not in applied:
            continue
        mod = load_migration_module(path)
        mod.down(con)
        con.execute("DELETE FROM schema_version WHERE version = ?", (ver,))
        con.commit()
        reverted.append(name)
    return reverted
