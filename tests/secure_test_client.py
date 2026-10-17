"""Supply browser CSRF tokens and explicitly authenticated fixture sessions.

Security boundary tests use FlaskClient directly and do not use this helper.
"""
from contextlib import contextmanager
from flask.testing import FlaskClient
import account_security as auth


class BrowserClient(FlaskClient):
    @contextmanager
    def session_transaction(self, *args, **kwargs):
        with super().session_transaction(*args, **kwargs) as session:
            previous_teacher = session.get('ogretmen_id')
            previous_parent = session.get('veli_ogrenci_id')
            yield session
            if session.get('ogretmen_id') and ('teacher_auth_version' not in session or previous_teacher != session['ogretmen_id']):
                session['teacher_auth_version'] = auth.teacher_version(session['ogretmen_id'])
            if session.get('veli_ogrenci_id') and ('veli_auth_version' not in session or previous_parent != session['veli_ogrenci_id']):
                oid = session['veli_ogrenci_id']
                row = auth.parent_credential(oid)
                if not row:
                    auth.issue_parent_code(oid)
                    row = auth.parent_credential(oid)
                session['veli_auth_version'] = row['version']

    def open(self, *args, **kwargs):
        with self.session_transaction() as session:
            token = session.setdefault('request_csrf', 'browser-fixture-csrf')
        headers = dict(kwargs.pop('headers', {}) or {})
        headers.setdefault('X-CSRF-Token', token)
        kwargs['headers'] = headers
        return super().open(*args, **kwargs)


def install(app):
    app.test_client_class = BrowserClient
