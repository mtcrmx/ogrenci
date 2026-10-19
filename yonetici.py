"""Dedicated administrator sign-in and read-only parent account inspection."""
import os
import secrets
import time
from functools import wraps
from flask import abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
import database as db

DEFAULT_HASH = 'scrypt:32768:8:1$NarNvYIWuP3V7JOF$7aca456689dc64aaedcc6512af40fd583be8edfd521a57c8b8c29b8a10e41960060ad09ed796c22f01f4724e4068372a1e90ac3ba7c199b4f7394d6d1fab724c'


def active():
    return session.get('yonetici_until', 0) > time.time()


def required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not active():
            return redirect(url_for('yonetici_login'))
        return fn(*args, **kwargs)
    return wrapper


def register(app):
    @app.before_request
    def inspection_guard():
        # Authentication must remain available when leaving read-only inspection.
        # Teacher login clears inspection state only after valid credentials.
        if request.endpoint in {'login', 'logout'}:
            return
        if session.get('yonetici_until') and not active():
            session.clear()
            return redirect(url_for('yonetici_login'))
        if active():
            if request.method != 'GET' and request.endpoint not in {'yonetici_select', 'yonetici_login'}:
                abort(403, 'Yönetici önizlemesinde öğrenci verileri değiştirilemez.')
            if request.endpoint in {'veli_cihaz_anahtar', 'veli_sifre_belirle'}:
                abort(403)

    @app.route('/yonetici/giris', methods=['GET', 'POST'])
    def yonetici_login():
        error = None
        session.setdefault('yonetici_csrf', secrets.token_urlsafe(32))
        if request.method == 'POST':
            if not secrets.compare_digest(request.form.get('csrf', ''), session['yonetici_csrf']):
                abort(400)
            con = db._conn()
            try:
                con.execute('CREATE TABLE IF NOT EXISTS yonetici_login_attempt (id INTEGER PRIMARY KEY, failures INTEGER, blocked REAL)')
                with con:
                    con.execute('INSERT OR IGNORE INTO yonetici_login_attempt VALUES (1,0,0)')
                    row = con.execute('SELECT * FROM yonetici_login_attempt WHERE id=1').fetchone()
                    now = time.time()
                    password = request.form.get('password', '')
                    valid = row['blocked'] <= now and len(password) <= 128 and request.form.get('username') == 'yonetici' and check_password_hash(os.environ.get('YONETICI_PASSWORD_HASH', DEFAULT_HASH), password)
                    if valid:
                        con.execute('UPDATE yonetici_login_attempt SET failures=0,blocked=0 WHERE id=1')
                    elif row['blocked'] <= now:
                        failures = (row['failures'] if not row['blocked'] else 0)+1
                        con.execute('UPDATE yonetici_login_attempt SET failures=?,blocked=? WHERE id=1', (failures, now+900 if failures >= 5 else 0))
                if valid:
                    session.clear()
                    session['yonetici_until'] = now+8*3600
                    session['yonetici_csrf'] = secrets.token_urlsafe(32)
                    return redirect(url_for('yonetici_students'))
                error = 'Kullanıcı adı veya şifre hatalı. Çok sayıda deneme yaptıysanız 15 dakika sonra tekrar deneyin.'
            finally:
                con.close()
        return render_template('yonetici.html', login=True, error=error)

    @app.get('/yonetici')
    @required
    def yonetici_students():
        session.pop('veli_ogrenci_id', None)
        query = request.args.get('q', '').strip()
        classroom = request.args.get('sinif', '')
        con = db._conn()
        try:
            students = [dict(r) for r in con.execute('SELECT o.id,o.ad_soyad,o.ogr_no,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id ORDER BY s.sinif_adi,o.ad_soyad')]
        finally:
            con.close()
        classes = sorted({s['sinif_adi'] for s in students})
        students = [s for s in students if (not classroom or s['sinif_adi']==classroom) and (not query or query.casefold() in s['ad_soyad'].casefold() or query in str(s['ogr_no']))]
        return render_template('yonetici.html', login=False, students=students, classes=classes, classroom=classroom, query=query)

    @app.post('/yonetici/ogrenci/<int:oid>')
    @required
    def yonetici_select(oid):
        if not secrets.compare_digest(request.form.get('csrf', ''), session.get('yonetici_csrf', '')):
            abort(400)
        con = db._conn()
        try:
            if not con.execute('SELECT id FROM ogrenciler WHERE id=?', (oid,)).fetchone():
                abort(404)
        finally:
            con.close()
        session['veli_ogrenci_id'] = oid
        return redirect(url_for('veli_panel'))

    @app.after_request
    def private_admin(response):
        if active() or request.path.startswith('/yonetici'):
            response.headers['Cache-Control'] = 'private, no-store'
        return response
