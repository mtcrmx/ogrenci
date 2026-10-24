"""Explicit, server-scoped analysis navigation. No schema changes."""
from collections import defaultdict
from datetime import date
from urllib.parse import urlencode

from flask import abort, render_template, request, session, url_for
import database as db
import sinav_okuyucu
from yetki import yetkili


def chart(rows):
    """Weighted daily accuracy; chart coordinates never replace result fields."""
    daily = defaultdict(lambda: [0, 0])
    for row in rows:
        count = max(0, int(row.get('soru_sayisi') or 0))
        if count:
            daily[str(row.get('tarih') or '')[:10]][0] += min(count, max(0, int(row.get('dogru') or 0)))
            daily[str(row.get('tarih') or '')[:10]][1] += count
    points = []
    for index, (day, (correct, count)) in enumerate(sorted(daily.items())):
        percent = round(100 * correct / count, 1)
        points.append(dict(day=day, percent=percent,
                           cx=50 if len(daily) == 1 else 5 + 90 * index / (len(daily)-1),
                           cy=95 - .9 * percent))
    total = sum(value[1] for value in daily.values())
    return dict(points=points, percent=round(100*sum(v[0] for v in daily.values())/total, 1) if total else None,
                questions=total)


def filters():
    values = {k: request.args.get(k, '').strip() for k in ('start', 'end', 'source', 'course')}
    for key in ('start', 'end'):
        if values[key]:
            try:
                date.fromisoformat(values[key])
            except ValueError:
                abort(400)
    if values['start'] and values['end'] and values['start'] > values['end']:
        abort(400)
    if values['source'] not in ('', 'ev', 'deneme', 'okul'):
        abort(400)
    return values


def panels(students, selected, values, teacher):
    ids = {int(o['id']) for o in students}
    rows = sinav_okuyucu.birlesik_sonuclar(ids, teacher=teacher) if ids else []
    if not teacher:
        import home_test_window
        rows = [r for r in rows if not r.get('exam_id') or home_test_window.released(r)]
    courses = sorted({r.get('ders') for r in rows if r.get('ders')})
    rows = [r for r in rows if
            (not values['start'] or str(r.get('tarih') or '')[:10] >= values['start']) and
            (not values['end'] or str(r.get('tarih') or '')[:10] <= values['end']) and
            (not values['source'] or r.get('source') == values['source']) and
            (not values['course'] or r.get('ders') == values['course'])]
    result = []
    # Each class and source retains its own series. Never sum incompatible exam nets.
    for group in selected:
        group_ids = {int(o['id']) for o in students if int(o['sinif_id']) == int(group['id'])}
        for source, label in [('ev', 'Evde sorular'), ('deneme', 'Denemeler'), ('okul', 'Okulda sorular')]:
            if values['source'] and values['source'] != source:
                continue
            if source == 'okul' and not str(group['sinif_adi']).startswith('8'):
                continue
            data = chart([r for r in rows if int(r['ogrenci_id']) in group_ids and r['source'] == source])
            result.append(dict(title=group['sinif_adi']+' · '+label, **data))
    return result, courses


def register(app, login_required):
    @app.get('/analizler')
    @login_required
    def simple_analysis():
        tid = session['ogretmen_id']
        classes = db.aktif_sube_siniflari() if yetkili(tid, 'yonetici') else db.ogretmen_siniflari(tid)
        allowed = {int(c['id']): c for c in classes}
        try:
            selected_ids = list(dict.fromkeys(int(v) for v in request.args.getlist('sinif')))
            student_id = int(request.args['ogrenci']) if request.args.get('ogrenci') else None
        except ValueError:
            abort(400)
        if any(sid not in allowed for sid in selected_ids):
            abort(403)
        selected = [allowed[sid] for sid in selected_ids]
        students = [dict(o, sinif_id=sid) for sid in selected_ids for o in db.sinif_ogrencileri(sid)]
        chosen = next((o for o in students if int(o['id']) == student_id), None)
        if student_id and not chosen:
            abort(403)
        values = filters()
        analysis_classes = [c for c in selected if not chosen or int(c['id']) == int(chosen['sinif_id'])]
        data, courses = panels([chosen] if chosen else students, analysis_classes, values, tid)
        scope = [('sinif', sid) for sid in selected_ids] + [(k, v) for k, v in values.items() if v]
        back = url_for('simple_analysis') + '?' + urlencode(scope)
        student_links = [dict(name=o['ad_soyad'], url=back+'&ogrenci='+str(o['id'])) for o in students]
        response = render_template('simple_analysis.html', classes=classes, selected_ids=selected_ids,
                                   panels=data, filters=values, courses=courses, chosen=chosen,
                                   back=back, student_links=student_links, parent=False)
        return response, 200, {'Cache-Control': 'private, no-store'}


def parent_analysis():
    # The only identity source is the authenticated session, never a URL parameter.
    oid = int(session['veli_ogrenci_id'])
    con = db._conn()
    try:
        row = con.execute('SELECT o.id,o.ad_soyad,o.sinif_id,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?', (oid,)).fetchone()
    finally:
        con.close()
    if not row:
        abort(404)
    student = dict(row)
    values = filters()
    groups = [dict(id=student['sinif_id'], sinif_adi=student['sinif_adi'])]
    data, courses = panels([student], groups, values, None)
    return render_template('simple_analysis.html', classes=[], selected_ids=[], panels=data,
                           filters=values, courses=courses, chosen=student, parent=True,
                           student_links=[], back=url_for('veli_panel')), 200, {'Cache-Control': 'private, no-store'}
