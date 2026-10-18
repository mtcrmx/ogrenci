"""LGS test rankings. Parent payloads contain no other student identities."""
from datetime import date, timedelta
from flask import request, session, url_for
import database as db

METRICS = {'test': 'Test', 'soru': 'Çözülen soru', 'dogru': 'Doğru',
           'yanlis': 'Yanlış', 'bos': 'Boş', 'basari': 'Başarı %',
           'aktif': 'Aktif gün', 'seri': 'En uzun çalışma serisi', 'ders': 'Ders çeşitliliği'}


def build(con, args, own_id=None, today=None):
    today = today or date.today()
    metric = args.get('sr_olcut', 'test')
    if metric not in METRICS:
        metric = 'test'
    direction = 'artan' if args.get('sr_yon') == 'artan' else 'azalan'
    period = args.get('sr_donem', 'tum')
    if period not in {'tum', 'hafta', 'ay'}:
        period = 'tum'
    start = {'tum': date.min, 'hafta': today-timedelta(days=today.weekday()),
             'ay': today.replace(day=1)}[period]
    students = [dict(r) for r in con.execute(
        "SELECT o.id,o.ad_soyad,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi IN ('8/A','8/B') ORDER BY o.id")]
    if own_id is not None and not any(s['id'] == own_id for s in students):
        return None
    classes = sorted({s['sinif_adi'] for s in students})
    classroom = args.get('sr_sinif', '')
    if classroom not in classes:
        classroom = ''
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    results = []
    if {'lgs_optik_sinav', 'lgs_optik_sonuc'} <= tables:
        results = [dict(r) for r in con.execute("""SELECT r.ogrenci_id,r.dogru,r.yanlis,r.bos,r.zaman,e.ders
            FROM lgs_optik_sonuc r JOIN lgs_optik_sinav e ON e.id=r.sinav_id
            WHERE e.tur='yaprak'""")]
    subjects = sorted({r['ders'] for r in results if r['ders']})
    subject = args.get('sr_ders', '')
    if subject not in subjects:
        subject = ''
    try:
        minimum = max(0, min(100000, int(args.get('sr_min', 0))))
    except (ValueError, TypeError):
        minimum = 0
    totals = {}
    for s in students:
        if classroom and s['sinif_adi'] != classroom:
            continue
        totals[s['id']] = dict(test=0, soru=0, dogru=0, yanlis=0, bos=0, days=set(), subjects=set())
    for result in results:
        total = totals.get(result['ogrenci_id'])
        if total is None or (subject and result['ders'] != subject):
            continue
        try:
            day = date.fromisoformat(result['zaman'][:10])
        except (ValueError, TypeError):
            continue
        if not start <= day <= today:
            continue
        total['test'] += 1
        for key in ('dogru', 'yanlis', 'bos'):
            total[key] += result[key]
        total['days'].add(day)
        if result['ders']:
            total['subjects'].add(result['ders'])
    rows = []
    for index, student in enumerate(students, 1):
        total = totals.get(student['id'])
        if total is None:
            continue
        total['soru'] = total['dogru'] + total['yanlis']
        if total['soru'] < minimum:
            continue
        all_questions = total['soru'] + total['bos']
        total['basari'] = round(100*total['dogru']/all_questions, 2) if all_questions else None
        days = sorted(total.pop('days'))
        total['aktif'] = len(days)
        longest = current = 0
        previous = None
        for day in days:
            current = current+1 if previous and day-previous == timedelta(days=1) else 1
            longest = max(longest, current)
            previous = day
        total['seri'] = longest
        total['ders'] = len(total.pop('subjects'))
        own = own_id == student['id']
        # No student ID, class, real name or profile link for other parents.
        total['ad'] = student['ad_soyad'] if own_id is None or own else f'Öğrenci {index}'
        total['kendi'] = own
        rows.append(total)
    rows.sort(key=lambda row: (row[metric] is None, (row[metric] or 0)*(1 if direction == 'artan' else -1)))
    last = object()
    for index, row in enumerate(rows, 1):
        if row[metric] != last:
            rank = index
        row['sira'] = rank
        last = row[metric]
    return dict(rows=rows, metrics=METRICS, metric=metric, direction=direction,
                period=period, classes=classes, classroom=classroom, subjects=subjects,
                subject=subject, minimum=minimum, parent=own_id is not None)


def register(app):
    @app.context_processor
    def ranking_context():
        if request.endpoint not in {'lgs', 'veli_lgs'}:
            return {}
        parent = request.endpoint == 'veli_lgs'
        own_id = session.get('veli_ogrenci_id') if parent else None
        if (parent and not own_id) or (not parent and not session.get('ogretmen_id')):
            return {}
        con = db._conn()
        try:
            data = build(con, request.args, own_id)
        finally:
            con.close()
        if not data:
            return {}
        def sorting_link(key):
            args = request.args.to_dict()
            if key == 'dogru' and data['metric'] == 'dogru':
                key = 'yanlis'
            args.update(sr_olcut=key, sr_yon='azalan')
            return url_for(request.endpoint, **args) + '#lgs-siralama'
        data['link'] = sorting_link
        data['preserved'] = {k: v for k, v in request.args.items() if not k.startswith('sr_')}
        return {'lgs_ranking': data}

    @app.after_request
    def ranking_cache(response):
        if request.endpoint in {'lgs', 'veli_lgs'}:
            response.headers['Cache-Control'] = 'private, no-store'
        return response
