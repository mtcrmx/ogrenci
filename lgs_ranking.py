"""Student rankings over evde soru, deneme and yaprak test results.

Parent payloads contain no other student identities.
"""
from datetime import date, timedelta
from flask import request, session, url_for
import database as db
from metrik import KAYNAK_ADLARI, _seviye_sql, birlesik_sonuclar, seviye_kaynaklari

METRICS = {'net': 'Toplam net', 'test': 'Kayıt', 'soru': 'Çözülen soru', 'dogru': 'Doğru',
           'yanlis': 'Yanlış', 'bos': 'Boş', 'basari': 'Başarı %',
           'aktif': 'Aktif gün', 'seri': 'En uzun çalışma serisi', 'ders': 'Ders çeşitliliği'}

ENDPOINTS = {'lgs', 'veli_lgs', 'rehberlik_lgs', 'deneme_analiz', 'veli_deneme_analiz',
             'veli_analizler', 'sonuclar', 'veli_sonuclar'}


def _level_of_class(con, sinif_id):
    if not sinif_id:
        return None
    row = con.execute(f"SELECT {_seviye_sql(con)} FROM siniflar s WHERE s.id=?", (sinif_id,)).fetchone()
    return int(row[0]) if row and row[0] else None


def build(con, args, own_id=None, today=None, level=None):
    today = today or date.today()
    metric = args.get('sr_olcut', 'net')
    if metric not in METRICS:
        metric = 'net'
    direction = 'artan' if args.get('sr_yon') == 'artan' else 'azalan'
    period = args.get('sr_donem', 'tum')
    if period not in {'tum', 'hafta', 'ay'}:
        period = 'tum'
    start = {'tum': date.min, 'hafta': today-timedelta(days=today.weekday()),
             'ay': today.replace(day=1)}[period]
    sev = _seviye_sql(con)
    all_students = [dict(r) for r in con.execute(
        f"SELECT o.id,o.ad_soyad,s.sinif_adi,{sev} AS seviye FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id ORDER BY o.id")]
    levels = sorted({int(s['seviye']) for s in all_students if s['seviye']})
    if own_id is not None:
        own = next((s for s in all_students if s['id'] == own_id), None)
        if own is None:
            return None
        level = int(own['seviye'] or 0)
    else:
        try:
            requested = int(args.get('sr_seviye') or 0)
        except (TypeError, ValueError):
            requested = 0
        if requested in levels:
            level = requested
        if level not in levels:
            level = 8 if 8 in levels else (levels[0] if levels else None)
    students = [s for s in all_students if s['seviye'] == level]
    classes = sorted({s['sinif_adi'] for s in students})
    classroom = args.get('sr_sinif', args.get('sube', ''))
    if classroom not in classes:
        classroom = ''
    sources = seviye_kaynaklari(level)
    source = args.get('sr_kaynak', '')
    if source not in sources:
        source = ''
    results = birlesik_sonuclar(con, [s['id'] for s in students])
    subjects = sorted({r['ders'] for r in results if r['ders']})
    # Include assigned home tests even before their first submission.
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    home_tests = []
    if 'lgs_optik_sinav' in tables:
        home_tests = [dict(r) for r in con.execute("""SELECT e.id,e.ad,e.tarih,e.ders,s.sinif_adi
            FROM lgs_optik_sinav e LEFT JOIN siniflar s ON s.id=e.sinif_id
            WHERE e.kaynak IN ('ev','ev_yaprak') AND (e.silindi_at IS NULL OR e.silindi_at='')
            ORDER BY e.tarih DESC,e.id DESC""")
            if (r['sinif_adi'] in classes or (not r['sinif_adi'] and level == 8))]
    tests = {f"optik-{r['id']}": f"{r['ad']} · {r['sinif_adi'] or '8/A + 8/B'} · {r['tarih']}" for r in home_tests}
    home_keys = set(tests)
    selected_test = args.get('sr_test', '')
    if selected_test not in tests and selected_test != 'ev-tumu':
        selected_test = ''
    subjects = sorted(set(subjects) | {r['ders'] for r in home_tests if r['ders']})
    filtered_results = []
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
        totals[s['id']] = dict(kayitlar=set(), soru=0, dogru=0, yanlis=0, bos=0, net=0.0, days=set(), subjects=set())
    for result in results:
        total = totals.get(result['ogrenci_id'])
        if total is None or (subject and result['ders'] != subject) or (source and result['kaynak'] != source):
            continue
        if selected_test == 'ev-tumu' and result['kayit'] not in home_keys:
            continue
        if selected_test and selected_test != 'ev-tumu' and result['kayit'] != selected_test:
            continue
        try:
            day = date.fromisoformat(result['tarih'][:10])
        except (ValueError, TypeError):
            continue
        if not start <= day <= today:
            continue
        filtered_results.append(result)
        total['kayitlar'].add(result['kayit'])
        for key in ('dogru', 'yanlis', 'bos'):
            total[key] += result[key]
        total['net'] += result['net']
        total['days'].add(day)
        if result['ders']:
            total['subjects'].add(result['ders'])
    rows = []
    for index, student in enumerate(students, 1):
        total = totals.get(student['id'])
        if total is None:
            continue
        total['test'] = len(total.pop('kayitlar'))
        total['net'] = round(total['net'], 2)
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
    course_stats = []
    for name in sorted({r['ders'] or 'Dersi belirtilmemiş / karma test' for r in filtered_results}):
        items = [r for r in filtered_results if (r['ders'] or 'Dersi belirtilmemiş / karma test') == name]
        count = len({r['ogrenci_id'] for r in items})
        correct = sum(r['dogru'] for r in items)
        total = sum(r['dogru'] + r['yanlis'] + r['bos'] for r in items)
        course_stats.append(dict(ad=name,katilim=count,net=round(sum(r['net'] for r in items)/count,2) if count else 0,
                                 basari=round(correct*100/total,1) if total else 0))
    return dict(tests=tests, selected_test=selected_test, course_stats=course_stats,
                participant_count=sum(1 for r in rows if r['test']),
                rows=rows, metrics=METRICS, metric=metric, direction=direction,
                period=period, classes=classes, classroom=classroom, subjects=subjects,
                subject=subject, minimum=minimum, parent=own_id is not None,
                level=level, levels=levels, sources={k: KAYNAK_ADLARI[k] for k in sources},
                source=source)


def register(app):
    @app.context_processor
    def ranking_context():
        if request.endpoint not in ENDPOINTS:
            return {}
        parent = request.endpoint.startswith('veli_')
        own_id = session.get('veli_ogrenci_id') if parent else None
        if (parent and not own_id) or (not parent and not session.get('ogretmen_id')):
            return {}
        con = db._conn()
        try:
            level = None
            if not parent:
                sinif_id = request.args.get('sinif', type=int)
                ogrenci_id = request.args.get('ogrenci', type=int)
                if ogrenci_id and not sinif_id:
                    row = con.execute('SELECT sinif_id FROM ogrenciler WHERE id=?', (ogrenci_id,)).fetchone()
                    sinif_id = row[0] if row else None
                level = _level_of_class(con, sinif_id or session.get('ui_sinif_id'))
            if request.endpoint == 'lgs' and request.args.get('ekran') == 'analiz':
                level = 8
            data = build(con, request.args, own_id, level=level)
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
        if request.endpoint in ENDPOINTS:
            response.headers['Cache-Control'] = 'private, no-store'
        return response
