"""Flexible per-student tests, exam editing and authorized student search."""
from datetime import date
import unicodedata
from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
import database as db

COURSES = ('Türkçe', 'Matematik', 'Fen Bilimleri', 'Sosyal Bilgiler', 'T.C. İnkılap Tarihi', 'Din Kültürü', 'İngilizce')


def school_courses():
    con = db._conn()
    names = [r[0] for r in con.execute("SELECT DISTINCT ders_adi FROM ders_programi WHERE ders_adi IS NOT NULL AND ders_adi<>'' ORDER BY ders_adi")]
    con.close()
    aliases = {'Din Kültürü ve Ahlak Bilgisi':'Din Kültürü', 'T.C. İnkılap Tarihi ve Atatürkçülük':'T.C. İnkılap Tarihi'}
    return tuple(dict.fromkeys([*COURSES, *(aliases.get(n, n) for n in names if n != 'Rehberlik')]))


def normalize(text):
    text = str(text or '').replace('ı', 'i').replace('İ', 'I').casefold()
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).split())


def institution_allowed():
    if not session.get('ogretmen_id'):
        return False
    con = db._conn()
    teacher = con.execute('SELECT ad_soyad,yetki FROM ogretmenler WHERE id=?', (session['ogretmen_id'],)).fetchone()
    con.close()
    return bool(teacher and teacher['yetki'] not in ('rapor', 'rehber') and normalize(teacher['ad_soyad']) in ('adem akgul', 'metehan cucen'))


def course_analysis(records, include_exams=False):
    groups = {}
    for record in reversed(records):
        if record.get('tur') != 'ders' and not include_exams:
            continue
        for row in record['dersler']:
            count = row.get('soru_sayisi') or db.LGS_SORU_SAYISI.get(row['ders'], 10)
            groups.setdefault(row['ders'], []).append(dict(row, ad=record['ad'], tarih=record['tarih'],
                yuzde=round(100 * row['dogru'] / count, 1), soru_sayisi=count))
    result = []
    for name, entries in groups.items():
        last = entries[-1]
        result.append({'ders': name, 'son': last, 'gecmis': entries[-6:],
                       'fark': round(last['yuzde'] - entries[-2]['yuzde'], 1) if len(entries) > 1 else None})
    result.sort(key=lambda a: a['son']['tarih'], reverse=True)
    return result


def register_results(app, login_required, accessible):
    @app.context_processor
    def results_context():
        return {'kurum_deneme_yetkili': institution_allowed()}

    @app.route('/api/ogrenci-ara')
    @login_required
    def api_ogrenci_ara():
        query = normalize(request.args.get('q', '')[:100])
        if not query:
            return jsonify(ogrenciler=[])
        classes = db.aktif_sube_siniflari() or db.ogretmen_siniflari(session['ogretmen_id'])
        scope = request.args.get('kapsam')
        results = []
        for classroom in classes:
            if scope == 'lgs' and not classroom['sinif_adi'].startswith('8/'):
                continue
            for student in db.sinif_ogrencileri(classroom['id']):
                name = normalize(student['ad_soyad'])
                if (query.isdecimal() and str(student['ogr_no']).startswith(query)) or (not query.isdecimal() and all(t in name for t in query.split())):
                    results.append({'id': student['id'], 'ad': student['ad_soyad'], 'no': student['ogr_no'],
                                    'sinif': classroom['sinif_adi'], 'sinif_id': classroom['id']})
        results.sort(key=lambda r: (str(r['no']) != query, r['sinif'], normalize(r['ad'])))
        response = jsonify(ogrenciler=results[:25], toplam=len(results))
        response.headers['Cache-Control'] = 'no-store'
        return response

    def full_teacher():
        con = db._conn()
        row = con.execute('SELECT yetki FROM ogretmenler WHERE id=?', (session['ogretmen_id'],)).fetchone()
        con.close()
        if not row or row['yetki'] in ('rapor', 'rehber'):
            abort(403)

    def records_for(oid):
        records = db.lgs_denemeler(oid, 200)
        for r in records:
            r['duzenlenebilir'] = r.get('ogretmen_id') == session.get('ogretmen_id') or (r.get('tur') == 'kurum' and institution_allowed())
        return records

    @app.route('/sonuclar', methods=['GET', 'POST'])
    @login_required
    def sonuclar():
        full_teacher()
        oid = request.values.get('ogrenci', type=int)
        if not oid:
            if request.method == 'POST':
                abort(400)
            classes = db.aktif_sube_siniflari() or db.ogretmen_siniflari(session['ogretmen_id'])
            selected = request.args.get('sinif', type=int) or session.get('ui_sinif_id')
            if selected in {s['id'] for s in classes}:
                classes = [s for s in classes if s['id'] == selected]
            return render_template('sonuclar.html', ogrenci=None, gruplar=[{'sinif': s, 'ogrenciler': db.sinif_ogrencileri(s['id'])} for s in classes])
        if not accessible(session['ogretmen_id'], oid):
            abort(403)
        con = db._conn()
        student = con.execute('SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?', (oid,)).fetchone()
        con.close()
        records = records_for(oid)
        edit_id = request.values.get('duzenle', type=int)
        editing = next((r for r in records if r['id'] == edit_id), None) if edit_id else None
        if edit_id and (not editing or not editing['duzenlenebilir']):
            abort(403)
        courses = school_courses()
        if editing:
            courses = tuple(dict.fromkeys([*courses, *(r['ders'] for r in editing['dersler'])]))
        form = None
        if request.method == 'POST':
            form = request.form
            try:
                title = request.form.get('ad', '').strip()
                when = request.form.get('tarih', '')
                when = date.fromisoformat(when).isoformat()
                kind = request.form.get('tur')
                if not title or kind not in ('ders', 'deneme', 'kurum'):
                    raise ValueError('Sonuç adını ve türünü seçin.')
                if kind == 'kurum' and not institution_allowed():
                    abort(403)
                names = request.form.getlist('ders')
                totals = request.form.getlist('soru_sayisi')
                correct = request.form.getlist('dogru')
                wrong = request.form.getlist('yanlis')
                penalties = request.form.getlist('yanlis_goturme')
                if not 1 <= len(names) <= len(courses) or len(set(names)) != len(names) or any(len(v) != len(names) for v in (totals, correct, wrong, penalties)):
                    raise ValueError('Her ders için bir sonuç satırı girin; aynı dersi iki kez seçmeyin.')
                if kind == 'ders' and len(names) != 1:
                    raise ValueError('Ders testinde tek ders seçin. Birden fazla ders için deneme seçin.')
                rows = []
                for i, name in enumerate(names):
                    count, c, w, penalty = int(totals[i]), int(correct[i]), int(wrong[i]), int(penalties[i])
                    if name not in courses or not 1 <= count <= 500 or min(c, w) < 0 or c + w > count or penalty not in (0, 3, 4):
                        raise ValueError('Soru sayısı 1–500 olmalı; doğru ve yanlış toplamı soru sayısını geçemez.')
                    rows.append(dict(ders=name, soru_sayisi=count, dogru=c, yanlis=w, bos=count-c-w, yanlis_goturme=penalty))
                if editing:
                    if editing['tur'] == 'kurum' and kind != 'kurum':
                        raise ValueError('Kurum denemesinin türü değiştirilemez.')
                    if editing['tur'] == 'kurum' and (title != editing['ad'] or when != editing['tarih']):
                        raise ValueError('Kurum denemesinde ad ve tarih ortak sınavı tanımlar; burada yalnızca öğrencinin ders sonuçlarını düzenleyin.')
                    con = db._conn()
                    con.execute('BEGIN IMMEDIATE')
                    current = con.execute('SELECT surum FROM lgs_deneme WHERE id=?', (edit_id,)).fetchone()
                    if not current or current[0] != request.form.get('surum', type=int):
                        con.rollback()
                        con.close()
                        raise ValueError('Bu sonuç siz düzenlerken değişti. Güncel kaydı tekrar açın.')
                    con.execute('UPDATE lgs_deneme SET ad=?,tarih=?,tur=?,surum=surum+1 WHERE id=?', (title[:80], when, kind, edit_id))
                    con.execute('DELETE FROM lgs_deneme_ders WHERE deneme_id=?', (edit_id,))
                    for row in rows:
                        net = round(row['dogru'] - (row['yanlis']/row['yanlis_goturme'] if row['yanlis_goturme'] else 0), 2)
                        con.execute('INSERT INTO lgs_deneme_ders(deneme_id,ders,soru_sayisi,dogru,yanlis,bos,net,yanlis_goturme) VALUES(?,?,?,?,?,?,?,?)',
                                    (edit_id, row['ders'], row['soru_sayisi'], row['dogru'], row['yanlis'], row['bos'], net, row['yanlis_goturme']))
                    con.commit()
                    con.close()
                else:
                    saved = db.lgs_deneme_ekle(oid, title, when, rows, ogretmen_id=session['ogretmen_id'], tur=kind)
                    if not saved['ok']:
                        raise ValueError(saved['hata'])
                db.veli_haber_ekle(oid, f'{title}: sonuç {"güncellendi" if editing else "kaydedildi"}. Ders analizinizi inceleyebilirsiniz.')
                flash('Sonuç güncellendi.' if editing else 'Sonuç kaydedildi ve öğrenci analizine eklendi.', 'success')
                return redirect(url_for('sonuclar', ogrenci=oid))
            except (ValueError, TypeError) as error:
                flash(str(error) or 'Sonuç alanlarını kontrol edin.', 'warning')
        return render_template('sonuclar.html', ogrenci=dict(student), kayitlar=records, duzenlenen=editing,
                               dersler=courses, bugun=date.today().isoformat(), analiz=course_analysis(records, True), form=form, veli=False)

    @app.route('/veli/sonuclar')
    def veli_sonuclar():
        oid = session.get('veli_ogrenci_id')
        if not oid:
            return redirect(url_for('veli_giris'))
        con = db._conn()
        student = con.execute('SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?', (oid,)).fetchone()
        con.close()
        if not student:
            abort(404)
        records = db.lgs_denemeler(oid, 200)
        return render_template('sonuclar.html', ogrenci=dict(student), kayitlar=records, analiz=course_analysis(records, True), veli=True)
