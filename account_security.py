"""Credential storage and school-admin account provisioning.

Parent codes are displayed once, never stored in recoverable form.
"""
import hashlib
import os
import secrets
import time
from werkzeug.security import generate_password_hash, check_password_hash


def password_hash(value):
    return generate_password_hash(value, method='scrypt')


def is_hash(value):
    return value.startswith(('scrypt:', 'pbkdf2:'))


def migrate(con):
    con.execute('CREATE TABLE IF NOT EXISTS parent_credentials (student_id INTEGER PRIMARY KEY REFERENCES ogrenciler(id), password_hash TEXT NOT NULL, version TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS login_attempts (bucket TEXT PRIMARY KEY, started REAL NOT NULL, attempts INTEGER NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS security_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)')
    for row in con.execute('SELECT id, sifre FROM ogretmenler').fetchall():
        if not is_hash(row['sifre']):
            con.execute('UPDATE ogretmenler SET sifre=? WHERE id=?', (password_hash(row['sifre'] or secrets.token_urlsafe(24)), row['id']))
    con.commit()


def signing_key():
    # Persist an installation-specific key on the same durable volume as the DB.
    from database import _conn
    configured = os.environ.get('SECRET_KEY', '')
    if len(configured) >= 32 and configured != 'erenler-cumhuriyet-2025-gizli':
        return configured
    with _conn() as con:
        con.execute('INSERT OR IGNORE INTO security_settings VALUES (?, ?)', ('session_key', secrets.token_urlsafe(48)))
        key = con.execute('SELECT value FROM security_settings WHERE name=?', ('session_key',)).fetchone()[0]
    con.close()
    return key


def admin_allowed(teacher_id):
    from database import _conn
    if not teacher_id:
        return False
    con = _conn()
    row = con.execute('SELECT ad_soyad FROM ogretmenler WHERE id=?', (teacher_id,)).fetchone()
    con.close()
    return bool(row and row[0] in {'ADEM AKGÜL', 'METEHAN CÜCEN'})


def teacher_version(teacher_id):
    from database import _conn
    con = _conn()
    row = con.execute('SELECT sifre FROM ogretmenler WHERE id=?', (teacher_id,)).fetchone()
    con.close()
    return hashlib.sha256(row[0].encode()).hexdigest() if row else None


def issue_teacher_code(teacher_id):
    from database import _conn
    code = secrets.token_urlsafe(12)
    with _conn() as con:
        updated = con.execute('UPDATE ogretmenler SET sifre=? WHERE id=?', (password_hash(code), teacher_id)).rowcount
    con.close()
    if not updated:
        raise ValueError('Öğretmen bulunamadı.')
    return code


def parent_credential(student_id):
    from database import _conn
    con = _conn()
    row = con.execute('SELECT * FROM parent_credentials WHERE student_id=?', (student_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def issue_parent_code(student_id):
    from database import _conn
    code = secrets.token_urlsafe(12)
    version = secrets.token_urlsafe(24)
    with _conn() as con:
        if not con.execute('SELECT 1 FROM ogrenciler WHERE id=?', (student_id,)).fetchone():
            raise ValueError('Öğrenci bulunamadı.')
        con.execute('INSERT INTO parent_credentials VALUES (?,?,?) ON CONFLICT(student_id) DO UPDATE SET password_hash=excluded.password_hash, version=excluded.version', (student_id, password_hash(code), version))
        # A reset also invalidates previously registered phone notification tokens.
        if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='veli_cihaz'").fetchone():
            con.execute('DELETE FROM veli_cihaz WHERE ogrenci_id=?', (student_id,))
    con.close()
    return code


_DUMMY_HASH = password_hash(secrets.token_urlsafe(24))


def verify_parent(student_id, password):
    row = parent_credential(student_id) if student_id else None
    valid = check_password_hash(row['password_hash'] if row else _DUMMY_HASH, password)
    return row['version'] if row and valid else None


def login_succeeded(kind, identity, address):
    from database import _conn
    account = hashlib.sha256(f'{kind}:account:{identity}'.encode()).hexdigest()
    ip = hashlib.sha256(f'ip:{address}'.encode()).hexdigest()
    with _conn() as con:
        con.execute('DELETE FROM login_attempts WHERE bucket=?', (account,))
        con.execute('UPDATE login_attempts SET attempts=MAX(0,attempts-1) WHERE bucket=?', (ip,))
    con.close()


def login_permitted(kind, identity, address):
    """Shared, atomic fixed-window limits; do not trust client X-Forwarded-For."""
    from database import _conn
    now = time.time()
    buckets = [(f'{kind}:account:{identity}', 10), (f'ip:{address}', 100)]
    con = _conn()
    try:
        con.execute('BEGIN IMMEDIATE')
        con.execute('DELETE FROM login_attempts WHERE started < ?', (now - 900,))
        permitted = True
        for value, limit in buckets:
            bucket = hashlib.sha256(value.encode()).hexdigest()
            con.execute('INSERT INTO login_attempts VALUES (?,?,1) ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1', (bucket, now))
            count = con.execute('SELECT attempts FROM login_attempts WHERE bucket=?', (bucket,)).fetchone()[0]
            permitted = permitted and count <= limit
        con.commit()
        return permitted
    finally:
        con.close()
