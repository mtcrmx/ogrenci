"""School TV: published content only, dated duty rota and read-only display links."""
import json
import os
import secrets
import threading
from functools import lru_cache
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from flask import abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge
import database as db
from broadcast_seed import duty_seed, CLOSED
from broadcast_timetable import timetable
from broadcast_calendar import calendar_seed
from lgs_sayac import ISTANBUL, lgs_sayac_verisi
from student_results import institution_allowed
from broadcast_presentations import office_command, prepared_presentation

FILE_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
              'webp': 'image/webp', 'mp4': 'video/mp4', 'webm': 'video/webm',
              'pdf': 'application/pdf', 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'}
MAX_FILE = 100 * 1024 * 1024
PDF_RENDER_LOCK = threading.Lock()
try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None  # The local browser viewer remains a fallback during upgrades.


@lru_cache(maxsize=128)
def pdf_page_count(path, modified):
    from pypdf import PdfReader
    return len(PdfReader(path).pages)


def media_dir():
    return Path(os.environ.get('YAYIN_DOSYA_KLASORU') or Path(db.DB_PATH).parent / 'yayin-dosyalar')


def init_schema():
    con = db._conn()
    con.executescript('''
        CREATE TABLE IF NOT EXISTS okul_yayin_ayar (anahtar TEXT PRIMARY KEY, deger TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS okul_yayin_gun (
            tarih TEXT PRIMARY KEY, kapali INTEGER NOT NULL DEFAULT 0,
            aciklama TEXT NOT NULL DEFAULT '', kat1 TEXT NOT NULL DEFAULT '',
            kat2 TEXT NOT NULL DEFAULT '', bahce TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS okul_yayin_icerik (
            id INTEGER PRIMARY KEY AUTOINCREMENT, baslik TEXT NOT NULL, metin TEXT NOT NULL DEFAULT '',
            dosya TEXT NOT NULL DEFAULT '', tur TEXT NOT NULL DEFAULT 'metin',
            baslangic TEXT NOT NULL, bitis TEXT NOT NULL, sure INTEGER NOT NULL DEFAULT 5,
            aktif INTEGER NOT NULL DEFAULT 1, ogretmen_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS okul_yayin_program (
            gun INTEGER NOT NULL, ders_no INTEGER NOT NULL, sinif_adi TEXT NOT NULL,
            ogretmen_adi TEXT NOT NULL, PRIMARY KEY(gun,ders_no,sinif_adi));
        CREATE TABLE IF NOT EXISTS okul_yayin_takvim (
            id TEXT PRIMARY KEY, baslik TEXT NOT NULL, baslangic TEXT NOT NULL,
            bitis TEXT NOT NULL, aktif INTEGER NOT NULL DEFAULT 1);
    ''')
    con.execute('INSERT OR IGNORE INTO okul_yayin_ayar VALUES (?,?)', ('token', secrets.token_urlsafe(32)))
    con.commit()
    con.close()


def setting(key, default=None):
    con = db._conn()
    row = con.execute('SELECT deger FROM okul_yayin_ayar WHERE anahtar=?', (key,)).fetchone()
    con.close()
    return row[0] if row else default


def token_ok(token):
    return bool(token and secrets.compare_digest(token, setting('token', '')))


def csrf():
    if not session.get('yayin_csrf'):
        session['yayin_csrf'] = secrets.token_urlsafe(32)
    return session['yayin_csrf']


def content_allowed():
    if not session.get('ogretmen_id'):
        return False
    con = db._conn()
    row = con.execute('SELECT yetki FROM ogretmenler WHERE id=?', (session['ogretmen_id'],)).fetchone()
    con.close()
    return bool(row and row['yetki'] in ('tam', 'rehber'))


def content_guard():
    if not content_allowed():
        abort(403)
    if request.method == 'POST' and not secrets.compare_digest(request.form.get('csrf', ''), session.get('yayin_csrf', '') or 'invalid'):
        abort(400, 'Form süresi doldu. Sayfayı yenileyin.')


def edit_guard(row):
    if not row:
        abort(404)
    if row['ogretmen_id'] != session.get('ogretmen_id') and not institution_allowed():
        abort(403)


def slots(day):
    key = 'cuma' if day == 4 else 'haftaici'
    raw = setting(key)
    hours = json.loads(raw) if raw else [db.ders_saati(day, n) for n in range(1, 8)]
    return [dict(no=n+1, baslangic=h[0], bitis=h[1]) for n, h in enumerate(hours)]


def day_info(stamp):
    con = db._conn()
    row = con.execute('SELECT * FROM okul_yayin_gun WHERE tarih=?', (stamp,)).fetchone()
    con.close()
    if row:
        return dict(kapali=bool(row['kapali']), aciklama=row['aciklama'],
                    nobet=[row['kat1'], row['kat2'], row['bahce']], ozel=True)
    if stamp in CLOSED:
        return dict(kapali=True, aciklama=CLOSED[stamp], nobet=[], ozel=False)
    if date.fromisoformat(stamp).weekday() > 4:
        return dict(kapali=True, aciklama='Hafta sonu', nobet=[], ozel=False)
    return dict(kapali=False, aciklama='', nobet=duty_seed().get(stamp, []), ozel=False)


def program_for(day):
    con = db._conn()
    rows = [dict(r) for r in con.execute('SELECT * FROM okul_yayin_program WHERE gun=? ORDER BY ders_no,sinif_adi', (day,))]
    con.close()
    if rows:
        return [{**r, 'ders_adi': ''} for r in rows if r['ogretmen_adi']]
    return [r for r in timetable() if r['gun'] == day]


def calendar_items(year):
    items = {i['id']: i for i in calendar_seed(year)}
    con = db._conn()
    rows = [dict(r) for r in con.execute('SELECT * FROM okul_yayin_takvim')]
    con.close()
    for row in rows:
        if row['id'] in items:
            items[row['id']].update(row, planlama=False, ozel=True)
        elif row['id'].startswith('ozel-') and row['baslangic'][:4] <= str(year) <= row['bitis'][:4]:
            items[row['id']] = dict(row, planlama=False, ozel=True)
    return sorted(items.values(), key=lambda i: (i['baslangic'], i['baslik']))


def calendar_display(stamp):
    year = date.fromisoformat(stamp).year
    items = {i['id']: i for y in (year-1, year, year+1) for i in calendar_items(y) if i['aktif']}
    ordered = sorted(items.values(), key=lambda i: (i['baslangic'], i['baslik']))
    return dict(bugun=[i for i in ordered if i['baslangic'] <= stamp <= i['bitis']],
                yaklasan=[i for i in ordered if i['baslangic'] > stamp][:3])


def payload(token=None, now=None):
    now = (now or datetime.now(ISTANBUL)).astimezone(ISTANBUL)
    stamp = now.date().isoformat()
    info = day_info(stamp)
    periods = slots(now.weekday())
    con = db._conn()
    items = [dict(r) for r in con.execute('''SELECT id,baslik,metin,tur,sure,baslangic,bitis,dosya FROM okul_yayin_icerik
        WHERE aktif=1 AND baslangic<=? AND bitis>=? ORDER BY id''', (stamp, stamp))]
    con.close()
    for item in items:
        item['sure'] = 10 if item['sure'] == 10 else 5
        filename = item.pop('dosya')
        item['version'] = filename
        if item['tur'] != 'metin':
            item['url'] = url_for('okul_ekran_medya', token=token, cid=item['id']) if token else url_for('yayin_medya', cid=item['id'])
        if item['tur'] in ('pdf', 'pptx') and pdfium:
            path = media_dir() / filename
            try:
                ready = True
                if item['tur'] == 'pptx':
                    prepared = prepared_presentation(path)
                    item['presentation_status'] = prepared['status']
                    ready = prepared['status'] == 'ready'
                    if ready:
                        path = prepared['path']
                if ready:
                    item['pdf_pages'] = pdf_page_count(str(path), path.stat().st_mtime_ns)
                    item['page_url'] = url_for('okul_ekran_sayfa', token=token, cid=item['id']) if token else url_for('yayin_sayfa', cid=item['id'])
            except (OSError, ValueError):
                pass
    # Only whitelist public timetable fields. Never merge student/parent/guidance data.
    program = program_for(now.weekday())
    return dict(simdi=now.isoformat(), tarih=stamp, gun=now.weekday(), **info,
                saatler=periods, program=program, siniflar=sorted({r['sinif_adi'] for r in timetable()}),
                icerikler=items, takvim=calendar_display(stamp), lgs=lgs_sayac_verisi(now))


def valid_media(upload):
    ext = Path(upload.filename or '').suffix.lower().lstrip('.')
    if ext not in FILE_TYPES:
        raise ValueError('PNG, JPG, WEBP, MP4, WEBM, PDF veya PPTX seçin. Eski PPT sunumunu PPTX olarak kaydedin.')
    head = upload.stream.read(32)
    upload.stream.seek(0)
    ok = (ext == 'png' and head.startswith(b'\x89PNG\r\n\x1a\n') or
          ext in ('jpg', 'jpeg') and head.startswith(b'\xff\xd8\xff') or
          ext == 'webp' and head.startswith(b'RIFF') and head[8:12] == b'WEBP' or
          ext == 'mp4' and head[4:8] == b'ftyp' or
          ext == 'webm' and head.startswith(b'\x1a\x45\xdf\xa3') or
          ext == 'pdf' and head.startswith(b'%PDF-') or
          ext == 'pptx' and head.startswith(b'PK'))
    if not ok:
        raise ValueError('Dosya içeriği seçilen görsel/video türüyle uyuşmuyor.')
    folder = media_dir()
    folder.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(20) + '.' + ext
    path = folder / name
    size = 0
    try:
        with path.open('wb') as out:
            while chunk := upload.stream.read(1024 * 1024):
                size += len(chunk)
                limit = MAX_FILE if ext in ('mp4', 'webm') else 20 * 1024 * 1024
                if size > limit:
                    raise ValueError('Video en fazla 100 MB, görsel ve sunum en fazla 20 MB olabilir.')
                out.write(chunk)
        if ext == 'pdf':
            from pypdf import PdfReader
            try:
                pdf = PdfReader(path)
                if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 100:
                    raise ValueError()
            except Exception:
                raise ValueError('PDF şifresiz ve 1–100 sayfa arasında olmalı.')
        elif ext == 'pptx':
            try:
                with zipfile.ZipFile(path) as archive:
                    entries = archive.infolist()
                    if len(entries) > 2000 or sum(i.file_size for i in entries) > 100 * 1024 * 1024:
                        raise ValueError()
                    names = archive.namelist()
                    if '[Content_Types].xml' not in names or 'ppt/presentation.xml' not in names:
                        raise ValueError()
                    root = ET.fromstring(archive.read('ppt/presentation.xml'))
                    count = len(root.findall('.//{http://schemas.openxmlformats.org/presentationml/2006/main}sldId'))
                    if not 1 <= count <= 100:
                        raise ValueError()
            except (ValueError, KeyError, zipfile.BadZipFile, ET.ParseError):
                raise ValueError('Geçerli bir PPTX sunumu seçin (1–100 slayt, açılmış içerik en fazla 100 MB).')
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return name, ext if ext in ('pdf', 'pptx') else 'video' if ext in ('mp4', 'webm') else 'gorsel'


def published_media(cid):
    stamp = datetime.now(ISTANBUL).date().isoformat()
    con = db._conn()
    row = con.execute('SELECT * FROM okul_yayin_icerik WHERE id=? AND aktif=1 AND baslangic<=? AND bitis>=?', (cid, stamp, stamp)).fetchone()
    con.close()
    if not row or not row['dosya']:
        abort(404)
    path = media_dir() / row['dosya']
    if not path.is_file():
        abort(404)
    return row, path


def pdf_page_response(cid):
    row, path = published_media(cid)
    number = request.args.get('sayfa', default=1, type=int)
    if row['tur'] not in ('pdf', 'pptx') or not 1 <= number <= 100:
        abort(404)
    if not pdfium:
        abort(503)
    original_name = path.name
    if row['tur'] == 'pptx':
        prepared = prepared_presentation(path)
        if prepared['status'] != 'ready':
            abort(503)
        path = prepared['path']
    # PDFium is not thread-safe. Cache immutable uploads; never serve this directory directly.
    with PDF_RENDER_LOCK:
        cache = media_dir() / 'pdf-onizleme'
        cache.mkdir(exist_ok=True)
        target = cache / f'{original_name}-{number}.jpg'
        if not target.exists():
            with pdfium.PdfDocument(path) as doc:
                if number > len(doc):
                    abort(404)
                page = doc[number - 1]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        abort(422)
                    bitmap = page.render(scale=min(1920/width, 1080/height), rev_byteorder=True)
                    try:
                        with bitmap.to_pil().convert('RGB') as image:
                            temporary = target.with_suffix('.' + secrets.token_hex(6) + '.tmp')
                            try:
                                image.save(temporary, format='JPEG', quality=94)
                                os.replace(temporary, target)
                            finally:
                                temporary.unlink(missing_ok=True)
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            # Bound the regenerable preview cache on the school's persistent disk.
            entries = sorted(cache.glob('*.jpg'), key=lambda p:p.stat().st_mtime)
            total = sum(p.stat().st_size for p in entries)
            for entry in entries:
                if total <= 128 * 1024 * 1024:
                    break
                if entry != target:
                    total -= entry.stat().st_size
                    entry.unlink(missing_ok=True)
    response = send_file(target, mimetype='image/jpeg', conditional=True)
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


def media_response(cid):
    row, path = published_media(cid)
    response = send_file(path, mimetype=FILE_TYPES[path.suffix[1:]], conditional=True)
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


def register_broadcast(app, login_required):
    init_schema()
    @app.context_processor
    def broadcast_context():
        return {'yayin_yonetebilir': institution_allowed, 'yayin_icerik_ekleyebilir': content_allowed}

    @app.after_request
    def broadcast_headers(response):
        if request.endpoint in ('yayin', 'api_yayin_okul', 'okul_ekran', 'okul_ekran_veri', 'okul_ekran_medya', 'yayin_medya', 'okul_ekran_sayfa', 'yayin_sayfa', 'yayin_yonetim'):
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
        if request.endpoint in ('yayin', 'okul_ekran'):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; frame-ancestors 'self'"
        return response

    @app.get('/saglik')
    def saglik():
        return jsonify(ok=True, pdf=bool(pdfium), sunum=bool(office_command()))

    @app.get('/api/yayin/okul')
    @login_required
    def api_yayin_okul():
        return jsonify(payload())

    @app.get('/ekran/<token>')
    def okul_ekran(token):
        if not token_ok(token):
            abort(404)
        return render_template('school_broadcast.html', data=payload(token), veri_url=url_for('okul_ekran_veri', token=token), tv=True)

    @app.get('/ekran/<token>/veri')
    def okul_ekran_veri(token):
        if not token_ok(token):
            abort(404)
        return jsonify(payload(token))

    @app.get('/ekran/<token>/medya/<int:cid>')
    def okul_ekran_medya(token, cid):
        if not token_ok(token):
            abort(404)
        return media_response(cid)

    @app.get('/yayin/medya/<int:cid>')
    @login_required
    def yayin_medya(cid):
        return media_response(cid)

    @app.get('/ekran/<token>/medya/<int:cid>/sayfa')
    def okul_ekran_sayfa(token, cid):
        if not token_ok(token):
            abort(404)
        return pdf_page_response(cid)

    @app.get('/yayin/medya/<int:cid>/sayfa')
    @login_required
    def yayin_sayfa(cid):
        return pdf_page_response(cid)

    @app.route('/yayin/yonetim', methods=['GET', 'POST'])
    @login_required
    def yayin_yonetim():
        if request.method == 'POST':
            request.max_content_length = MAX_FILE + 1024 * 1024
        content_guard()
        admin = institution_allowed()
        if request.method == 'POST' and request.form.get('islem') not in ('icerik', 'duyuru', 'sil', 'sunum_hazirla') and not admin:
            abort(403)
        today = datetime.now(ISTANBUL).date().isoformat()
        con = db._conn()
        new_file, old_file, saved = '', '', False
        try:
            if request.method == 'POST':
                action = request.form.get('islem')
                if action == 'token':
                    con.execute('UPDATE okul_yayin_ayar SET deger=? WHERE anahtar=?', (secrets.token_urlsafe(32), 'token'))
                elif action == 'gun':
                    stamp = date.fromisoformat(request.form['tarih']).isoformat()
                    names = [request.form.get(k, '').strip() for k in ('kat1', 'kat2', 'bahce')]
                    text = request.form.get('aciklama', '').strip()
                    if any(len(n) > 100 for n in names) or len(text) > 150:
                        raise ValueError('Öğretmen adı en fazla 100, açıklama 150 karakter olabilir.')
                    con.execute('INSERT OR REPLACE INTO okul_yayin_gun VALUES (?,?,?,?,?,?)', (stamp, int('kapali' in request.form), text, *names))
                elif action == 'gun_sifirla':
                    stamp = date.fromisoformat(request.form['tarih']).isoformat()
                    con.execute('DELETE FROM okul_yayin_gun WHERE tarih=?', (stamp,))
                elif action in ('takvim', 'takvim_sifirla'):
                    year = int(request.form.get('takvim_yil', today[:4]))
                    if not 2020 <= year <= 2100:
                        raise ValueError('Takvim yılı 2020–2100 arasında olmalı.')
                    cid = request.form.get('takvim_id', '').strip()
                    existing = con.execute('SELECT id FROM okul_yayin_takvim WHERE id=?', (cid,)).fetchone()
                    if cid and not existing and cid not in {i['id'] for i in calendar_seed(year)}:
                        abort(404)
                    if action == 'takvim_sifirla':
                        con.execute('DELETE FROM okul_yayin_takvim WHERE id=?', (cid,))
                    else:
                        title = request.form.get('takvim_baslik', '').strip()
                        start, end = (date.fromisoformat(request.form[k]) for k in ('takvim_baslangic', 'takvim_bitis'))
                        if not title or len(title) > 100 or start > end or (end-start).days > 366:
                            raise ValueError('Etkinlik başlığı 1–100 karakter, tarih aralığı en fazla bir yıl olmalı.')
                        if not start.year <= year <= end.year:
                            raise ValueError('Etkinlik tarihleri seçilen takvim yılını kapsamalı.')
                        cid = cid or 'ozel-' + secrets.token_hex(12)
                        con.execute('''INSERT INTO okul_yayin_takvim VALUES (?,?,?,?,?)
                            ON CONFLICT(id) DO UPDATE SET baslik=excluded.baslik,baslangic=excluded.baslangic,
                            bitis=excluded.bitis,aktif=excluded.aktif''',
                            (cid, title, start.isoformat(), end.isoformat(), int('takvim_aktif' in request.form)))
                elif action == 'saat':
                    for key in ('haftaici', 'cuma'):
                        hours = [[request.form.get(f'{key}_{n}_{edge}', '') for edge in ('bas', 'bit')] for n in range(1, 8)]
                        previous = ''
                        for start, end in hours:
                            datetime.strptime(start, '%H:%M'); datetime.strptime(end, '%H:%M')
                            if start >= end or start < previous:
                                raise ValueError('Ders saatleri sıralı olmalı ve birbiriyle çakışmamalı.')
                            previous = end
                        con.execute('INSERT OR REPLACE INTO okul_yayin_ayar VALUES (?,?)', (key, json.dumps(hours)))
                elif action in ('program', 'program_sifirla'):
                    day = int(request.form.get('gun', '-1'))
                    if day not in range(5):
                        raise ValueError('Program için bir hafta içi günü seçin.')
                    con.execute('DELETE FROM okul_yayin_program WHERE gun=?', (day,))
                    if action == 'program':
                        from broadcast_timetable import ROWS
                        teachers = {r[0] for r in ROWS}
                        classes = sorted({r['sinif_adi'] for r in timetable()})
                        for n in range(1, 8):
                            occupied = set()
                            for name in classes:
                                teacher = request.form.get(f'p_{n}_{name}', '').strip()
                                if teacher and (teacher not in teachers or teacher in occupied):
                                    raise ValueError(f'{n}. derste bir öğretmen iki sınıfta olamaz. Seçimleri kontrol edin.')
                                if teacher:
                                    occupied.add(teacher)
                                con.execute('INSERT INTO okul_yayin_program VALUES (?,?,?,?)', (day, n, name, teacher))
                elif action == 'sunum_hazirla':
                    row = con.execute('SELECT * FROM okul_yayin_icerik WHERE id=?', (request.form.get('id', type=int),)).fetchone()
                    edit_guard(row)
                    if row['tur'] != 'pptx':
                        abort(400)
                    state = prepared_presentation(media_dir() / row['dosya'], retry=True)
                    flash(state['message'], 'warning' if state['status'] == 'failed' else 'success')
                elif action == 'sil':
                    # Hide immediately; keep the file until after the transaction commits.
                    row = con.execute('SELECT * FROM okul_yayin_icerik WHERE id=?', (request.form.get('id', type=int),)).fetchone()
                    edit_guard(row)
                    old_file = row['dosya']
                    con.execute('DELETE FROM okul_yayin_icerik WHERE id=?', (request.form.get('id', type=int),))
                elif action in ('icerik', 'duyuru'):
                    title = request.form.get('baslik', '').strip()
                    text = request.form.get('metin', '').strip()
                    start, end = (date.fromisoformat(request.form[k]).isoformat() for k in ('baslangic', 'bitis'))
                    duration = request.form.get('sure', '5') if action == 'icerik' else '5'
                    if duration not in ('5', '10'):
                        raise ValueError('Otomatik geçiş için 5 veya 10 saniye seçin.')
                    duration = int(duration)
                    limit = 1000 if action == 'duyuru' else 300
                    if not title or len(title) > 100 or len(text) > limit or start > end:
                        raise ValueError(f'Başlık 1–100, metin en fazla {limit} karakter ve tarih aralığı geçerli olmalı.')
                    if action == 'duyuru' and not text:
                        raise ValueError('Kayan yazıda gösterilecek duyuru metnini yazın.')
                    cid = request.form.get('id', type=int)
                    old = con.execute('SELECT * FROM okul_yayin_icerik WHERE id=?', (cid,)).fetchone() if cid else None
                    if cid:
                        edit_guard(old)
                        if action == 'duyuru' and old['tur'] != 'metin':
                            abort(400)
                    filename, kind = (old['dosya'], old['tur']) if old else ('', 'metin')
                    upload = request.files.get('dosya')
                    if action == 'duyuru' and upload and upload.filename:
                        raise ValueError('Duyuruya dosya eklemeyin. Sunum ve videolar bölümünü kullanın.')
                    if upload and upload.filename:
                        old_file = filename
                        filename, kind = valid_media(upload)
                        new_file = filename
                    fields = (title, text, filename, kind, start, end, duration, int('aktif' in request.form), old['ogretmen_id'] if old else session['ogretmen_id'])
                    if cid:
                        con.execute('UPDATE okul_yayin_icerik SET baslik=?,metin=?,dosya=?,tur=?,baslangic=?,bitis=?,sure=?,aktif=?,ogretmen_id=? WHERE id=?', (*fields, cid))
                    else:
                        con.execute('INSERT INTO okul_yayin_icerik (baslik,metin,dosya,tur,baslangic,bitis,sure,aktif,ogretmen_id) VALUES (?,?,?,?,?,?,?,?,?)', fields)
                else:
                    abort(400)
                con.commit()
                saved = True
                if old_file:
                    (media_dir() / old_file).unlink(missing_ok=True)
                flash('Yayın ayarları kaydedildi. Ekran en geç 30 saniye içinde yenilenir.', 'success')
                return redirect(url_for('yayin_yonetim', tarih=request.form.get('tarih', today),
                    takvim_yil=request.form.get('takvim_yil', today[:4]),
                    _anchor='duyurular' if action == 'duyuru' or request.form.get('bolum') == 'duyurular' else 'icerik' if action == 'icerik' else None))
        except (ValueError, KeyError, RequestEntityTooLarge) as exc:
            con.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else 'Alanları ve dosya boyutunu kontrol edin.', 'warning')
        finally:
            con.close()
            if new_file and not saved:
                (media_dir() / new_file).unlink(missing_ok=True)
        stamp = request.args.get('tarih', today)
        try:
            date.fromisoformat(stamp)
        except ValueError:
            stamp = today
        con = db._conn()
        items = [dict(r) for r in con.execute('SELECT * FROM okul_yayin_icerik '+('' if admin else 'WHERE ogretmen_id=? ')+'ORDER BY id DESC', () if admin else (session['ogretmen_id'],))]
        con.close()
        for item in items:
            item['sure'] = 10 if item['sure'] == 10 else 5
            if item['tur'] == 'pptx':
                item['preparation'] = prepared_presentation(media_dir() / item['dosya'])
        edit_id = request.args.get('duzenle', type=int)
        edit = next((i for i in items if i['id'] == edit_id), None)
        if edit_id and not edit:
            abort(404)
        calendar_year = request.args.get('takvim_yil', default=int(today[:4]), type=int)
        calendar_year = calendar_year if 2020 <= calendar_year <= 2100 else int(today[:4])
        calendar = calendar_items(calendar_year) if admin else []
        calendar_edit_id = request.args.get('takvim_duzenle', '')
        calendar_edit = next((i for i in calendar if i['id'] == calendar_edit_id), None)
        if calendar_edit_id and not calendar_edit:
            abort(404)
        from broadcast_timetable import ROWS
        day = request.args.get('program_gun', default=min(datetime.now(ISTANBUL).weekday(), 4), type=int)
        day = day if day in range(5) else 0
        day_program = program_for(day)
        program_map = {(r['ders_no'], r['sinif_adi']): r['ogretmen_adi'] for r in day_program}
        return render_template('school_broadcast_manage.html', csrf=csrf(), today=today, stamp=stamp,
            info=day_info(stamp), items=items, edit=edit, hours={'haftaici': slots(0), 'cuma': slots(4)},
            program_day=day, program_map=program_map, program_teachers=sorted(r[0] for r in ROWS),
            program_classes=sorted({r['sinif_adi'] for r in timetable()}), days=db.DERS_GUNLERI,
            admin=admin, calendar=calendar, calendar_edit=calendar_edit, calendar_year=calendar_year,
            calendar_default=today if calendar_year == int(today[:4]) else f'{calendar_year}-01-01',
            ekran_url=url_for('okul_ekran', token=setting('token'), _external=True) if admin else '')
