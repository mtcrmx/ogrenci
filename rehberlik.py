"""Private counselor library, audience snapshots, feedback and appointments."""
from __future__ import annotations

import os
import mimetypes
import secrets
import zipfile
from datetime import datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.datastructures import MultiDict
import database as db

CATEGORIES = ('Aile iletişimi', 'Ders çalışma', 'Sınav süreci', 'Dijital denge', 'Arkadaşlık', 'Okula uyum', 'Diğer')
FILE_TYPES = {'pdf': ('application/pdf', 'PDF'),
              'pptx': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', 'Sunum'),
              'docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Word'),
              'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Excel'),
              'xls': ('application/vnd.ms-excel', 'Excel'),
              'jpg': ('image/jpeg', 'Görsel'), 'jpeg': ('image/jpeg', 'Görsel'), 'png': ('image/png', 'Görsel'),
              'gif': ('image/gif', 'Görsel'), 'webp': ('image/webp', 'Görsel'),
              'mp4': ('video/mp4', 'Video'), 'webm': ('video/webm', 'Video'), 'mov': ('video/mp4', 'Video'),
              'm4v': ('video/mp4', 'Video'),
              'mp3': ('audio/mpeg', 'Ses'), 'm4a': ('audio/mp4', 'Ses'),
              # Eski yüklemeler için; yeni PPT yüklemesi kabul edilmez.
              'ppt': ('application/vnd.ms-powerpoint', 'Sunum')}
UPLOAD_TYPES = tuple(t for t in FILE_TYPES if t != 'ppt')
VIDEO_TYPES = ('mp4', 'webm', 'mov', 'm4v')
AUDIO_TYPES = ('mp3', 'm4a')
IMAGE_TYPES = ('jpg', 'jpeg', 'png', 'gif', 'webp')
OOXML_PARTS = {'pptx': 'ppt/presentation.xml', 'docx': 'word/document.xml', 'xlsx': 'xl/workbook.xml'}
FILE_DIR = Path(os.environ.get('REHBERLIK_DOSYA_KLASORU') or Path(db.DB_PATH).parent / 'rehberlik-dosyalar')
READ_REPORTS = {'api_ogrenci_ara', 'analiz_merkezi', 'rapor_ozet', 'rapor_ozet_csv', 'rapor_excel', 'rapor_excel_detayli',
                'rapor_analiz_pdf', 'rapor_haftalik', 'rapor_karsilastir', 'rapor_anonim_sinif',
                'ogretmen_kitap_okuma', 'ogretmen_kitap_okuma_excel', 'ders_programi', 'kitap_odev_rapor',
                'yayin', 'api_yayin_okul', 'yayin_medya', 'yayin_sayfa'}


def init_schema():
    con = db._conn()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS rehber_icerik (
        id INTEGER PRIMARY KEY, ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id),
        baslik TEXT NOT NULL, kategori TEXT NOT NULL, ozet TEXT NOT NULL, metin TEXT NOT NULL,
        etkinlik TEXT NOT NULL, dosya TEXT NOT NULL DEFAULT '', dosya_adi TEXT NOT NULL DEFAULT '',
        uzanti TEXT NOT NULL DEFAULT '', boyut INTEGER NOT NULL DEFAULT 0,
        hedef TEXT NOT NULL, durum TEXT NOT NULL DEFAULT 'taslak', zaman TEXT NOT NULL,
        yayin_zamani TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS rehber_alici (
        icerik_id INTEGER NOT NULL REFERENCES rehber_icerik(id) ON DELETE CASCADE,
        ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id) ON DELETE CASCADE,
        acildi TEXT NOT NULL DEFAULT '', incelendi TEXT NOT NULL DEFAULT '', uygulandi TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (icerik_id, ogrenci_id));
    CREATE INDEX IF NOT EXISTS rehber_alici_ogrenci ON rehber_alici(ogrenci_id, icerik_id);
    CREATE TABLE IF NOT EXISTS rehber_gorusme (
        id INTEGER PRIMARY KEY, ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id) ON DELETE CASCADE,
        icerik_id INTEGER REFERENCES rehber_icerik(id), mesaj TEXT NOT NULL, zaman TEXT NOT NULL,
        durum TEXT NOT NULL DEFAULT 'bekliyor', yanit TEXT NOT NULL DEFAULT '', guncelleme TEXT NOT NULL DEFAULT '');
    ''')
    con.close()


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def counselor():
    return bool(session.get('ogretmen_id') and db.ogretmen_yetki_al(session['ogretmen_id']) == 'rehber')


def csrf():
    if 'rehber_csrf' not in session:
        session['rehber_csrf'] = secrets.token_urlsafe(32)
    return session['rehber_csrf']


def check_csrf():
    value = request.form.get('csrf', '')
    if not value or not secrets.compare_digest(value, session.get('rehber_csrf', '')):
        abort(400, 'Oturum doğrulanamadı. Sayfayı yenileyip tekrar deneyin.')


def auth(role):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if role == 'rehber' and not counselor():
                if not session.get('ogretmen_id'):
                    return redirect(url_for('login'))
                abort(403)
            if role == 'veli' and not session.get('veli_ogrenci_id'):
                return redirect(url_for('veli_giris'))
            if role == 'veli':
                con = db._conn()
                exists = con.execute('SELECT 1 FROM ogrenciler WHERE id=?', (session['veli_ogrenci_id'],)).fetchone()
                con.close()
                if not exists:
                    session.pop('veli_ogrenci_id', None)
                    return redirect(url_for('veli_giris'))
            if request.method == 'POST':
                request.max_content_length = 102 * 1024 * 1024
                check_csrf()
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def students():
    con = db._conn()
    names = tuple(db._AKTIF_SUBELER)
    rows = [dict(r) for r in con.execute(f'''SELECT o.id, o.ad_soyad, o.ogr_no, o.sinif_id, s.sinif_adi
        FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id
        WHERE s.sinif_adi IN ({','.join('?' for _ in names)}) ORDER BY s.sinif_adi, o.ad_soyad''', names)]
    con.close()
    return rows


def audience(form):
    roster = students()
    mode = form.get('hedef', '')
    try:
        ids = {int(x) for x in form.getlist('ogrenciler')}
        classes = {int(x) for x in form.getlist('siniflar')}
    except (ValueError, TypeError):
        raise ValueError('Geçerli bir sınıf veya öğrenci seçin.')
    if mode == 'tum':
        selected = roster
        label = 'Tüm veliler'
    elif mode == 'sinif':
        if not classes or not classes.issubset({r['sinif_id'] for r in roster}):
            raise ValueError('En az bir geçerli sınıf seçin.')
        selected = [r for r in roster if r['sinif_id'] in classes]
        label = ', '.join(sorted({r['sinif_adi'] for r in selected})) + ' velileri'
    elif mode == 'ogrenci':
        if not ids or not ids.issubset({r['id'] for r in roster}):
            raise ValueError('En az bir geçerli öğrenci seçin.')
        selected = [r for r in roster if r['id'] in ids]
        label = 'Seçili veliler'
    else:
        raise ValueError('İçeriği kimlerin göreceğini seçin.')
    if not selected:
        raise ValueError('Seçilen grupta öğrenci bulunamadı.')
    return selected, label


def save_upload(upload):
    if not upload or not upload.filename:
        return '', '', '', 0
    original = Path(upload.filename.replace('\\', '/')).name[:160]
    ext = original.rsplit('.', 1)[-1].lower()
    if ext in ('doc', 'ppt'):
        raise ValueError('Eski Office biçimi tarayıcıda gösterilemiyor. Dosyayı Word/PowerPoint’te “Farklı kaydet” ile DOCX/PPTX olarak kaydedip yükleyin.')
    if ext not in UPLOAD_TYPES:
        raise ValueError('Görsel (JPG, PNG, GIF, WebP), PDF, Word (DOCX), Excel (XLSX/XLS), PowerPoint (PPTX), video (MP4, WebM, MOV) veya ses (MP3, M4A) yükleyin.')
    limit = (100 if ext in VIDEO_TYPES else 20) * 1024 * 1024
    FILE_DIR.mkdir(parents=True, exist_ok=True)
    path = FILE_DIR / (uuid4().hex + '.' + ext)
    size = 0
    try:
        with path.open('xb') as stream:
            while chunk := upload.stream.read(256 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Video en fazla 100 MB, diğer dosyalar en fazla 20 MB olabilir.')
                stream.write(chunk)
        with path.open('rb') as stream:
            header = stream.read(16)
        valid = ((ext == 'pdf' and header.startswith(b'%PDF-')) or
                 (ext in ('mp4', 'mov', 'm4v', 'm4a') and header[4:8] == b'ftyp') or
                 (ext == 'mov' and header[4:8] in (b'moov', b'wide', b'mdat', b'free')) or
                 (ext == 'webm' and header.startswith(b'\x1a\x45\xdf\xa3')) or
                 (ext == 'xls' and header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')) or
                 (ext in ('jpg', 'jpeg') and header.startswith(b'\xff\xd8\xff')) or
                 (ext == 'png' and header.startswith(b'\x89PNG\r\n\x1a\n')) or
                 (ext == 'gif' and header[:6] in (b'GIF87a', b'GIF89a')) or
                 (ext == 'webp' and header[:4] == b'RIFF' and header[8:12] == b'WEBP') or
                 (ext == 'mp3' and (header.startswith(b'ID3') or (header[0] == 0xFF and header[1] & 0xE0 == 0xE0))))
        if ext in OOXML_PARTS:
            try:
                with zipfile.ZipFile(path) as archive:
                    names = archive.namelist()
                    valid = '[Content_Types].xml' in names and OOXML_PARTS[ext] in names
            except zipfile.BadZipFile:
                valid = False
        if not valid or not size:
            raise ValueError('Dosya içeriği uzantısıyla uyuşmuyor veya dosya boş.')
        return path.name, original, ext, size
    except Exception:
        path.unlink(missing_ok=True)
        raise


def content(cid, parent_id=None):
    con = db._conn()
    if parent_id is not None:
        row = con.execute('''SELECT i.*, a.acildi, a.incelendi, a.uygulandi FROM rehber_icerik i
            JOIN rehber_alici a ON a.icerik_id=i.id WHERE i.id=? AND a.ogrenci_id=? AND i.durum='yayinda' ''',
            (cid, parent_id)).fetchone()
    else:
        row = con.execute('SELECT * FROM rehber_icerik WHERE id=?', (cid,)).fetchone()
    con.close()
    if not row:
        abort(404)
    return dict(row)


def recipients(cid):
    con = db._conn()
    rows = [dict(r) for r in con.execute('''SELECT a.*, o.ad_soyad, o.ogr_no, s.sinif_adi
        FROM rehber_alici a JOIN ogrenciler o ON o.id=a.ogrenci_id JOIN siniflar s ON s.id=o.sinif_id
        WHERE a.icerik_id=? ORDER BY s.sinif_adi, o.ad_soyad''', (cid,))]
    con.close()
    return rows


def meetings(parent_id=None):
    con = db._conn()
    sql = '''SELECT g.*, o.ad_soyad, s.sinif_adi, i.baslik FROM rehber_gorusme g
        JOIN ogrenciler o ON o.id=g.ogrenci_id JOIN siniflar s ON s.id=o.sinif_id
        LEFT JOIN rehber_icerik i ON i.id=g.icerik_id'''
    args = ()
    if parent_id is not None:
        sql += ' WHERE g.ogrenci_id=?'
        args = (parent_id,)
    rows = [dict(r) for r in con.execute(sql + ' ORDER BY g.id DESC', args)]
    con.close()
    return rows


def library(parent_id=None):
    con = db._conn()
    if parent_id is None:
        rows = [dict(r) for r in con.execute('''SELECT i.*, COUNT(a.ogrenci_id) AS alici,
            SUM(CASE WHEN a.acildi!='' THEN 1 ELSE 0 END) AS acan,
            SUM(CASE WHEN a.incelendi!='' THEN 1 ELSE 0 END) AS inceleyen,
            SUM(CASE WHEN a.uygulandi!='' THEN 1 ELSE 0 END) AS uygulayan
            FROM rehber_icerik i LEFT JOIN rehber_alici a ON a.icerik_id=i.id GROUP BY i.id ORDER BY i.id DESC''')]
    else:
        rows = [dict(r) for r in con.execute('''SELECT i.*, a.acildi, a.incelendi, a.uygulandi
            FROM rehber_icerik i JOIN rehber_alici a ON a.icerik_id=i.id
            WHERE a.ogrenci_id=? AND i.durum='yayinda' ORDER BY i.id DESC''', (parent_id,))]
    con.close()
    return rows


def register_rehberlik(app):
    # Windows file associations may report .mjs as text/plain; module imports reject that.
    mimetypes.add_type('text/javascript', '.mjs')
    mimetypes.add_type('application/wasm', '.wasm')
    init_schema()

    @app.before_request
    def rehber_role_gate():
        # Resolve the database role so an old session cannot retain full teacher access.
        if session.get('ogretmen_id') and not request.path.startswith('/veli') and counselor():
            session['ogretmen_yetki'] = 'rehber'
            ep = request.endpoint or ''
            if ep.startswith('rehberlik_') or ep in {'static', 'login', 'logout', 'manifest', 'manifest_veli', 'service_worker', 'favicon', 'okul_ekran', 'okul_ekran_veri', 'okul_ekran_medya', 'yayin_yonetim'}:
                return None
            if request.method == 'GET' and ep in READ_REPORTS:
                return None
            return redirect(url_for('rehberlik_panel')) if request.method == 'GET' else ('Yetkisiz işlem', 403)

    @app.context_processor
    def rehber_context():
        return {'rehber_csrf': csrf, 'rehber_kategoriler': CATEGORIES, 'rehber_turler': FILE_TYPES,
                'rehber_yukleme_turleri': UPLOAD_TYPES, 'rehber_video_turleri': VIDEO_TYPES,
                'rehber_ses_turleri': AUDIO_TYPES, 'rehber_gorsel_turleri': IMAGE_TYPES}

    def page(template, **data):
        return render_template('rehberlik/' + template + '.html', **data)

    @app.route('/rehberlik')
    @auth('rehber')
    def rehberlik_panel():
        items = library()
        requests = meetings()
        return page('panel', items=items, requests=requests,
                    published=sum(i['durum'] == 'yayinda' for i in items),
                    pending=sum(r['durum'] == 'bekliyor' for r in requests),
                    reviewed=sum(i['inceleyen'] for i in items))

    @app.route('/rehberlik/yeni', defaults={'cid': None}, methods=['GET', 'POST'])
    @app.route('/rehberlik/icerik/<int:cid>/duzenle', endpoint='rehberlik_duzenle', methods=['GET', 'POST'])
    @auth('rehber')
    def rehberlik_yeni(cid):
        error = ''
        draft = content(cid) if cid else None
        if draft and draft['durum'] != 'taslak':
            abort(409, 'Yayınlanan içeriğin alıcıları değiştirilemez. Yeni bir içerik oluşturun.')
        values = request.form
        if draft and request.method == 'GET':
            selected = recipients(cid)
            mode = 'tum' if draft['hedef'] == 'Tüm veliler' else 'ogrenci' if draft['hedef'] == 'Seçili veliler' else 'sinif'
            values = MultiDict({**draft, 'hedef': mode})
            values.setlist('ogrenciler', [str(r['ogrenci_id']) for r in selected])
            values.setlist('siniflar', [str(s['id']) for s in db.aktif_sube_siniflari() if any(r['sinif_adi']==s['sinif_adi'] for r in selected)])
        if request.method == 'POST':
            file_name = ''
            try:
                form = request.form
                title, summary = form.get('baslik', '').strip(), form.get('ozet', '').strip()
                body, activity = form.get('metin', '').strip(), form.get('etkinlik', '').strip()
                category = form.get('kategori', '')
                if not title or len(title) > 120 or not summary or len(summary) > 500:
                    raise ValueError('Başlık (en fazla 120 karakter) ve kısa açıklama (en fazla 500 karakter) gerekli.')
                if category not in CATEGORIES or len(body) > 20000 or len(activity) > 3000:
                    raise ValueError('Geçerli bir kategori seçin; yazı en fazla 20.000, etkinlik 3.000 karakter olabilir.')
                selected, target = audience(form)
                file_name, original, ext, size = save_upload(request.files.get('dosya'))
                stored_file = (file_name, original, ext, size)
                if not file_name and draft:
                    stored_file = tuple(draft[k] for k in ('dosya','dosya_adi','uzanti','boyut'))
                if not body and not stored_file[0]:
                    raise ValueError('Bir rehber yazısı yazın veya dosya yükleyin.')
                con = db._conn()
                try:
                    con.execute('BEGIN IMMEDIATE')
                    with con:
                        if draft:
                            if con.execute('SELECT durum FROM rehber_icerik WHERE id=?',(cid,)).fetchone()[0] != 'taslak':
                                raise ValueError('İçerik başka bir oturumda yayınlandı. Sayfayı yenileyin.')
                            con.execute('''UPDATE rehber_icerik SET baslik=?,kategori=?,ozet=?,metin=?,etkinlik=?,
                                dosya=?,dosya_adi=?,uzanti=?,boyut=?,hedef=? WHERE id=?''',
                                (title,category,summary,body,activity,*stored_file,target,cid))
                            con.execute('DELETE FROM rehber_alici WHERE icerik_id=?',(cid,))
                        else:
                            cur = con.execute('''INSERT INTO rehber_icerik
                                (ogretmen_id,baslik,kategori,ozet,metin,etkinlik,dosya,dosya_adi,uzanti,boyut,hedef,zaman)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                                (session['ogretmen_id'], title, category, summary, body, activity, *stored_file, target, now()))
                            cid = cur.lastrowid
                        con.executemany('INSERT INTO rehber_alici (icerik_id,ogrenci_id) VALUES (?,?)', [(cid,r['id']) for r in selected])
                finally:
                    con.close()
                if draft and file_name and draft['dosya']:
                    try:
                        (FILE_DIR / draft['dosya']).unlink(missing_ok=True)
                    except OSError:
                        app.logger.warning('Eski rehberlik dosyası temizlenemedi: içerik %s', cid)
                flash('Taslak kaydedildi. Önizlemeyi kontrol edip yayınlayabilirsiniz.', 'success')
                return redirect(url_for('rehberlik_detay', cid=cid))
            except ValueError as exc:
                error = str(exc)
                if file_name:
                    (FILE_DIR / file_name).unlink(missing_ok=True)
            except OSError:
                error = 'Dosya kaydedilemedi. Depolama alanını kontrol edip tekrar deneyin.'
                app.logger.exception('Rehberlik dosyası kaydedilemedi')
            except Exception:
                if file_name:
                    (FILE_DIR / file_name).unlink(missing_ok=True)
                raise
        return page('yeni', error=error, roster=students(), classes=db.aktif_sube_siniflari(), values=values, draft=draft), (400 if error else 200)

    @app.route('/rehberlik/icerik/<int:cid>')
    @auth('rehber')
    def rehberlik_detay(cid):
        item = content(cid)
        return page('detay', item=item, parents=recipients(cid), parent=False)

    @app.route('/rehberlik/icerik/<int:cid>/yayinla', methods=['POST'])
    @auth('rehber')
    def rehberlik_yayinla(cid):
        item = content(cid)
        if item['durum'] == 'arsiv':
            abort(409)
        if item['dosya'] and not (FILE_DIR / item['dosya']).is_file():
            flash('Dosya bulunamadı; yayınlama yapılamadı.', 'error')
            return redirect(url_for('rehberlik_detay', cid=cid))
        con = db._conn()
        notifications = []
        try:
            db._haftalik_takip_init(con)
            con.execute('BEGIN IMMEDIATE')
            current = con.execute('SELECT durum FROM rehber_icerik WHERE id=?', (cid,)).fetchone()
            if current['durum'] == 'arsiv':
                abort(409)
            if current['durum'] == 'taslak':
                ids = [r[0] for r in con.execute('SELECT ogrenci_id FROM rehber_alici WHERE icerik_id=?', (cid,))]
                if not ids:
                    raise ValueError('Alıcı bulunamadı; yeni bir taslak oluşturun.')
                message = f"Rehberlik servisi: {item['baslik']}"
                con.execute("UPDATE rehber_icerik SET durum='yayinda', yayin_zamani=? WHERE id=?", (now(),cid))
                for oid in ids:
                    con.execute("INSERT INTO veli_haber (ogrenci_id,metin,zaman,tur,goruldu) VALUES (?,?,?,'duyuru',0)", (oid,message,now()))
                    notifications.append((oid,message,'duyuru',url_for('veli_rehberlik_detay',cid=cid)))
            con.commit()
        except ValueError as exc:
            con.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('rehberlik_detay', cid=cid))
        finally:
            con.close()
        for notification in notifications:
            db._veli_push_sonra(*notification)
        flash('İçerik yayında. Seçilen velilere bildirim kaydı oluşturuldu.', 'success')
        return redirect(url_for('rehberlik_detay', cid=cid))

    @app.route('/rehberlik/icerik/<int:cid>/arsivle', methods=['POST'])
    @auth('rehber')
    def rehberlik_arsivle(cid):
        content(cid)
        con = db._conn()
        with con:
            con.execute("UPDATE rehber_icerik SET durum='arsiv' WHERE id=?", (cid,))
        con.close()
        flash('İçerik arşivlendi. Veliler artık bu içeriğe veya dosyasına erişemez; geri bildirimler korundu.', 'success')
        return redirect(url_for('rehberlik_panel'))

    @app.route('/rehberlik/gorusmeler', methods=['GET', 'POST'])
    @auth('rehber')
    def rehberlik_gorusmeler():
        if request.method == 'POST':
            gid = request.form.get('id', type=int)
            status = request.form.get('durum', '')
            reply = request.form.get('yanit', '').strip()
            if status not in ('bekliyor', 'planlandi', 'tamamlandi') or len(reply) > 2000:
                abort(400)
            con = db._conn()
            row = con.execute('SELECT ogrenci_id FROM rehber_gorusme WHERE id=?', (gid,)).fetchone()
            if not row:
                con.close()
                abort(404)
            with con:
                con.execute('UPDATE rehber_gorusme SET durum=?,yanit=?,guncelleme=? WHERE id=?', (status,reply,now(),gid))
            con.close()
            db.veli_haber_ekle(row['ogrenci_id'], 'Rehberlik görüşme talebiniz güncellendi. Rehberlik servisi ekranından inceleyebilirsiniz.')
            flash('Görüşme durumu ve veliye görünen yanıt kaydedildi.', 'success')
            return redirect(url_for('rehberlik_gorusmeler'))
        return page('gorusmeler', requests=meetings(), parent=False)

    @app.route('/veli/rehberlik')
    @auth('veli')
    def veli_rehberlik():
        items = library(int(session['veli_ogrenci_id']))
        q = request.args.get('q', '').strip().casefold()
        category = request.args.get('kategori', '')
        items = [i for i in items if (not q or q in (i['baslik'] + ' ' + i['ozet']).casefold()) and (not category or i['kategori']==category)]
        return page('veli', items=items, requests=meetings(int(session['veli_ogrenci_id'])))

    @app.route('/veli/rehberlik/icerik/<int:cid>', methods=['GET', 'POST'])
    @auth('veli')
    def veli_rehberlik_detay(cid):
        oid = int(session['veli_ogrenci_id'])
        item = content(cid, oid)
        con = db._conn()
        try:
            if request.method == 'POST':
                action = request.form.get('islem', '')
                if action not in ('incelendi', 'uygulandi'):
                    abort(400)
                with con:
                    # A deliberate confirmation is distinct from opening the page.
                    con.execute(f"UPDATE rehber_alici SET {action}=CASE WHEN {action}='' THEN ? ELSE {action} END WHERE icerik_id=? AND ogrenci_id=?", (now(),cid,oid))
                flash('Geri bildiriminiz Alperen hocaya iletildi.', 'success')
                return redirect(url_for('veli_rehberlik_detay', cid=cid))
            with con:
                con.execute("UPDATE rehber_alici SET acildi=CASE WHEN acildi='' THEN ? ELSE acildi END WHERE icerik_id=? AND ogrenci_id=?", (now(),cid,oid))
        finally:
            con.close()
        return page('detay', item=item, parents=[], parent=True)

    @app.route('/veli/rehberlik/gorusme', methods=['POST'])
    @auth('veli')
    def veli_rehberlik_gorusme():
        oid = int(session['veli_ogrenci_id'])
        cid = request.form.get('icerik_id', type=int)
        if request.form.get('icerik_id') and not cid:
            abort(400)
        if cid:
            content(cid, oid)
        message = request.form.get('mesaj', '').strip()
        if not message or len(message) > 2000:
            flash('Görüşme konusunu 1–2.000 karakter arasında yazın.', 'error')
            return redirect(url_for('veli_rehberlik_detay',cid=cid) if cid else url_for('veli_rehberlik'))
        con = db._conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            existing = con.execute("SELECT id FROM rehber_gorusme WHERE ogrenci_id=? AND icerik_id IS ? AND durum!='tamamlandi'", (oid,cid)).fetchone()
            if not existing:
                con.execute('INSERT INTO rehber_gorusme (ogrenci_id,icerik_id,mesaj,zaman) VALUES (?,?,?,?)', (oid,cid,message,now()))
            con.commit()
        finally:
            con.close()
        flash('Bu konu için görüşme talebiniz bekliyor.' if existing else 'Görüşme talebiniz Alperen hocaya iletildi.', 'success')
        return redirect(url_for('veli_rehberlik'))

    @app.route('/rehberlik/dosya/<int:cid>')
    def rehberlik_dosya(cid):
        # Mixed sessions visiting the parent area always use that child's audience.
        if request.args.get('veli') == '1':
            if not session.get('veli_ogrenci_id'):
                abort(403)
            item = content(cid, int(session['veli_ogrenci_id']))
        elif counselor():
            item = content(cid)
        elif session.get('veli_ogrenci_id'):
            item = content(cid, int(session['veli_ogrenci_id']))
        else:
            abort(403)
        if not item['dosya'] or Path(item['dosya']).name != item['dosya'] or not (FILE_DIR/item['dosya']).is_file():
            abort(404)
        # Dosya yalnızca sayfa içi önizlemeye verilir; adres çubuğundan açılınca indirilmesin.
        if request.headers.get('Sec-Fetch-Dest') in ('document', 'iframe', 'frame', 'embed', 'object'):
            abort(403)
        response = send_file(FILE_DIR / item['dosya'], mimetype=FILE_TYPES[item['uzanti']][0],
                             download_name=item['dosya_adi'], conditional=True, as_attachment=False)
        response.headers['Content-Disposition'] = 'inline'
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.after_request
    def rehber_private_cache(response):
        if request.path.startswith(('/rehberlik', '/veli/rehberlik')):
            response.headers['Cache-Control'] = 'private, no-store'
        return response
