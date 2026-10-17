"""Application-wide CSRF protection for HTML forms and same-origin JS calls."""
import re
import secrets
from urllib.parse import urlsplit
from flask import request, session, jsonify, redirect, url_for
from markupsafe import escape


def install(app):
    @app.before_request
    def protect_request():
        if request.endpoint == 'static':
            return None
        if session.get('ogretmen_id'):
            from account_security import teacher_version
            version = teacher_version(session['ogretmen_id'])
            if not version or session.get('teacher_auth_version') != version:
                session.clear()
                return redirect(url_for('login'))
        if session.get('veli_ogrenci_id'):
            from account_security import parent_credential
            row = parent_credential(session['veli_ogrenci_id'])
            if not row or session.get('veli_auth_version') != row['version']:
                session.clear()
                if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                    return jsonify(ok=False, sebep='Oturumunuz sona erdi. Yeniden giriş yapın.'), 401
                return redirect(url_for('veli_giris'))
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            expected = session.get('request_csrf', '')
            received = request.headers.get('X-CSRF-Token') or request.form.get('_csrf_token', '')
            if not expected or not secrets.compare_digest(expected, received):
                return jsonify(ok=False, sebep='Güvenlik doğrulaması yenilenmeli. Sayfayı yenileyip tekrar deneyin.'), 400

    @app.after_request
    def secure_response(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        if response.direct_passthrough:
            return response
        if response.mimetype == 'text/html':
            token = session.setdefault('request_csrf', secrets.token_urlsafe(32))
            html = response.get_data(as_text=True)
            def form_token(match):
                tag = match.group(0)
                method = re.search(r'\bmethod\s*=\s*[\"\']?([^\s\"\'>]+)', tag, re.I)
                action = re.search(r'\baction\s*=\s*[\"\']([^\"\']*)', tag, re.I)
                target = urlsplit(action.group(1)) if action else None
                same_origin = not target or (not target.netloc and not target.scheme) or (target.scheme + '://' + target.netloc == request.host_url.rstrip('/'))
                if method and method.group(1).lower() == 'post' and same_origin:
                    return tag + f'<input type="hidden" name="_csrf_token" value="{escape(token)}">'
                return tag
            html = re.sub(r'<form\b[^>]*>', form_token, html, flags=re.I)
            security_head = f'<meta name="csrf-token" content="{escape(token)}"><script src="{url_for("static", filename="request_security.js")}"></script>'
            html = re.sub(r'(<head\b[^>]*>)', lambda m: m.group(0) + security_head, html, count=1, flags=re.I)
            response.set_data(html)
            response.headers['Cache-Control'] = 'no-store'
        elif session.get('ogretmen_id') or session.get('veli_ogrenci_id'):
            response.headers['Cache-Control'] = 'no-store'
        return response
