"""Staged parent credentials. Enable only after private code distribution."""
import hashlib
import os
import secrets
import time

from flask import abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import database as db


def enabled():
    return os.environ.get('VELI_KISISEL_SIFRE', '0') == '1'


def connect():
    con = db._conn()
    con.execute('''CREATE TABLE IF NOT EXISTS veli_credentials (
        ogrenci_id INTEGER PRIMARY KEY REFERENCES ogrenciler(id),
        password_hash TEXT, code_hash TEXT, code_until REAL,
        ticket_hash TEXT, ticket_until REAL,
        failures INTEGER NOT NULL DEFAULT 0, blocked_until REAL NOT NULL DEFAULT 0)''')
    return con


def issue_code(oid):
    """Return a one-time distribution code; never store its plaintext."""
    code = secrets.token_urlsafe(12)
    con = connect()
    try:
        if not con.execute('SELECT id FROM ogrenciler WHERE id=?', (oid,)).fetchone():
            raise ValueError('Öğrenci bulunamadı.')
        with con:
            con.execute('''INSERT INTO veli_credentials (ogrenci_id,code_hash,code_until)
                VALUES (?,?,?) ON CONFLICT(ogrenci_id) DO UPDATE SET
                code_hash=excluded.code_hash,code_until=excluded.code_until,
                ticket_hash=NULL,ticket_until=NULL,failures=0,blocked_until=0''',
                (oid, generate_password_hash(code), time.time()+30*86400))
        return code
    finally:
        con.close()


def authenticate(oid, password):
    con = connect()
    try:
        with con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('INSERT OR IGNORE INTO veli_credentials (ogrenci_id) VALUES (?)', (oid,))
            row = con.execute('SELECT * FROM veli_credentials WHERE ogrenci_id=?', (oid,)).fetchone()
            now = time.time()
            if row['blocked_until'] > now:
                return None, None
            if row['password_hash'] and check_password_hash(row['password_hash'], password):
                con.execute('UPDATE veli_credentials SET failures=0,blocked_until=0 WHERE ogrenci_id=?', (oid,))
                return 'login', None
            if row['code_hash'] and (row['code_until'] or 0) > now and check_password_hash(row['code_hash'], password):
                ticket = secrets.token_urlsafe(32)
                con.execute('UPDATE veli_credentials SET ticket_hash=?,ticket_until=?,failures=0,blocked_until=0 WHERE ogrenci_id=?',
                            (hashlib.sha256(ticket.encode()).hexdigest(), now+600, oid))
                return 'setup', ticket
            failures = (row['failures'] if row['blocked_until'] == 0 else 0)+1
            con.execute('UPDATE veli_credentials SET failures=?,blocked_until=? WHERE ogrenci_id=?',
                        (failures, now+900 if failures >= 5 else 0, oid))
        return None, None
    finally:
        con.close()


def register(app):
    @app.route('/veli/sifre-belirle', methods=['GET', 'POST'])
    def veli_sifre_belirle():
        pending = session.get('veli_setup')
        if not enabled() or not pending:
            return redirect(url_for('veli_giris'))
        con = connect()
        try:
            digest = hashlib.sha256(pending['ticket'].encode()).hexdigest()
            row = con.execute('SELECT * FROM veli_credentials WHERE ogrenci_id=?', (pending['oid'],)).fetchone()
            if not row or row['ticket_hash'] != digest or (row['ticket_until'] or 0) < time.time():
                session.pop('veli_setup', None)
                return redirect(url_for('veli_giris'))
            session.setdefault('veli_setup_csrf', secrets.token_urlsafe(32))
            error = None
            if request.method == 'POST':
                if not secrets.compare_digest(request.form.get('csrf',''), session['veli_setup_csrf']):
                    abort(400)
                password = request.form.get('password','')
                if len(password) < 12 or len(password) > 128:
                    error = 'Şifreniz 12–128 karakter olmalı. Hatırlayabileceğiniz birkaç kelime kullanabilirsiniz.'
                elif password != request.form.get('confirm',''):
                    error = 'Yazdığınız iki şifre aynı değil.'
                elif row['code_hash'] and check_password_hash(row['code_hash'], password):
                    error = 'Geçici giriş kodundan farklı bir şifre belirleyin.'
                else:
                    hashed = generate_password_hash(password)
                    with con:
                        changed = con.execute('''UPDATE veli_credentials SET password_hash=?,code_hash=NULL,
                            code_until=NULL,ticket_hash=NULL,ticket_until=NULL,failures=0,blocked_until=0
                            WHERE ogrenci_id=? AND ticket_hash=? AND ticket_until>?''',
                            (hashed, pending['oid'], digest, time.time())).rowcount
                    if not changed:
                        session.pop('veli_setup', None)
                        return redirect(url_for('veli_giris'))
                    session.clear()
                    session.permanent = True
                    session['veli_ogrenci_id'] = pending['oid']
                    return redirect(url_for('veli_panel'))
            return render_template('veli_sifre_belirle.html', hata=error)
        finally:
            con.close()

    @app.after_request
    def credential_cache(response):
        if request.endpoint in {'veli_giris', 'veli_sifre_belirle'}:
            response.headers['Cache-Control'] = 'private, no-store'
        return response
