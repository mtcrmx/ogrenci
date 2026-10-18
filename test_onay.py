"""Teacher review of completed tests, bound to the exact answer revision."""
import hashlib
import json
import secrets
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
import database as db
import lgs_optik as optik

bp = Blueprint('test_onay', __name__)

def connection():
    con = db._conn()
    optik._init(con)
    con.execute('CREATE TABLE IF NOT EXISTS test_onay (sonuc_id INTEGER PRIMARY KEY, revision TEXT NOT NULL, ogretmen_id INTEGER NOT NULL, zaman TEXT DEFAULT CURRENT_TIMESTAMP)')
    return con

def revision(row):
    return hashlib.sha256(json.dumps([row['isaretler'], row['cevaplar'], row['zaman']], ensure_ascii=False).encode()).hexdigest()

def records(teacher):
    con = connection()
    rows = [dict(r) for r in con.execute('''SELECT r.*, e.ad, e.ders, e.kaynak, e.tur, e.cevaplar,
        o.ad_soyad, o.ogr_no, s.sinif_adi, a.revision AS approved_revision
        FROM lgs_optik_sonuc r JOIN lgs_optik_sinav e ON e.id=r.sinav_id
        JOIN ogrenciler o ON o.id=r.ogrenci_id JOIN siniflar s ON s.id=o.sinif_id
        LEFT JOIN test_onay a ON a.sonuc_id=r.id WHERE e.ogretmen_id=? ORDER BY r.zaman DESC,r.id DESC''', (teacher,))]
    con.close()
    for row in rows:
        row['revision'] = revision(row)
        row['approved'] = row['revision'] == row['approved_revision']
    return rows

def pending(teacher):
    if db.ogretmen_yetki_al(teacher) != 'tam':
        return []
    return [r for r in records(teacher) if not r['approved']]

@bp.route('/onay-kutusu/test/<int:rid>', methods=['GET', 'POST'])
def review(rid):
    teacher = session.get('ogretmen_id')
    if not teacher:
        return redirect(url_for('login'))
    if db.ogretmen_yetki_al(teacher) != 'tam':
        abort(403)
    row = next((r for r in records(teacher) if r['id'] == rid), None)
    if not row:
        abort(404)
    session.setdefault('test_review_csrf', secrets.token_urlsafe(32))
    if request.method == 'POST':
        if not secrets.compare_digest(request.form.get('csrf', ''), session['test_review_csrf']):
            abort(400)
        con = connection()
        try:
            con.execute('BEGIN IMMEDIATE')
            current = con.execute('''SELECT r.isaretler,r.zaman,e.cevaplar FROM lgs_optik_sonuc r
                JOIN lgs_optik_sinav e ON e.id=r.sinav_id WHERE r.id=? AND e.ogretmen_id=?''', (rid, teacher)).fetchone()
            if not current or revision(current) != request.form.get('revision'):
                abort(409, 'Test değişti. Sayfayı yenileyip yeniden inceleyin.')
            con.execute('INSERT OR REPLACE INTO test_onay(sonuc_id,revision,ogretmen_id) VALUES(?,?,?)', (rid, revision(current), teacher))
            con.commit()
        finally:
            con.close()
        flash('Test içeriği incelendi ve onaylandı.', 'success')
        return redirect(url_for('onay_kutusu'))
    score = optik.puan_hesapla(json.loads(row['cevaplar']), json.loads(row['isaretler']))
    return render_template('test_onay.html', record=row, score=score)

@bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response

@bp.get('/yardim')
def help_page():
    if not (session.get('ogretmen_id') or session.get('veli_ogrenci_id') or session.get('ogrenci_giris')):
        return redirect(url_for('login'))
    return render_template('yardim.html')
