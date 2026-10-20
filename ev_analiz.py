"""Evde testlerden soru analizi."""
from collections import defaultdict
from datetime import date, timedelta
import secrets
from flask import Blueprint, abort, render_template, request, session, redirect, url_for, flash
import database as db
import lgs_optik as optik
import home_test_window as test_window
import metrik

bp = Blueprint('ev_analiz', __name__)

def connection():
    con = db._conn()
    optik._init(con)
    con.executescript('''
    CREATE TABLE IF NOT EXISTS ev_soru_meta (
      sinav_id INTEGER NOT NULL, no INTEGER NOT NULL, konu TEXT NOT NULL DEFAULT '',
      cozum TEXT NOT NULL DEFAULT '', PRIMARY KEY(sinav_id,no));
    CREATE TABLE IF NOT EXISTS ev_yardim (
      id INTEGER PRIMARY KEY, sinav_id INTEGER NOT NULL, ogrenci_id INTEGER NOT NULL,
      no INTEGER NOT NULL, notu TEXT NOT NULL DEFAULT '', yanit TEXT NOT NULL DEFAULT '',
      ogretmen_id INTEGER, zaman TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(sinav_id,ogrenci_id,no));
    CREATE TABLE IF NOT EXISTS ev_grup (
      id INTEGER PRIMARY KEY, ad TEXT NOT NULL, ogretmen_id INTEGER NOT NULL,
      kaynak_id INTEGER NOT NULL, zaman TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS ev_grup_uye (
      grup_id INTEGER NOT NULL, ogrenci_id INTEGER NOT NULL, PRIMARY KEY(grup_id,ogrenci_id));
    CREATE TABLE IF NOT EXISTS ev_grup_test (
      grup_id INTEGER NOT NULL, sinav_id INTEGER NOT NULL, PRIMARY KEY(grup_id,sinav_id));
    ''')
    from analysis_support import init
    init(con)
    return con

def visible(exam, student):
    # Class-bound tests are visible to that class; tests without a class are for all eighth grades.
    from moduller import seviye as sinif_seviyesi
    if exam.get('sinif_id'):
        return int(exam['sinif_id']) == int(student['sinif_id'])
    return exam.get('kaynak') == 'kamera' or sinif_seviyesi(student) == 8

def student_row(oid):
    con = db._conn()
    row = con.execute('SELECT o.*, s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?', (oid,)).fetchone()
    con.close()
    return dict(row) if row else None

def token():
    if 'ev_csrf' not in session:
        session['ev_csrf'] = secrets.token_urlsafe(32)
    return session['ev_csrf']

def aggregate(exam, people, metadata):
    questions = []
    for i, key in enumerate(exam['cevaplar'], 1):
        counts = dict.fromkeys(['A','B','C','D','E',''], 0)
        wrong, blank = [], []
        for person in people:
            answer = person['satirlar'][i-1]['verilen']
            counts[answer] += 1
            if not answer: blank.append(person['id'])
            elif answer != key: wrong.append(person['id'])
        meta = metadata.get(i, {})
        questions.append(dict(no=i, key=key, counts=counts, correct=counts[key], wrong=wrong, blank=blank,
            rate=metrik.oran(counts[key], len(people)),
            konu=meta.get('konu',''), cozum=meta.get('cozum','')))
    return questions

def register(app, can_access):
    bp.can_access = can_access
    app.register_blueprint(bp)

@bp.route('/evde-analiz', methods=['GET','POST'])
def index():
    teacher = session.get('ogretmen_id')
    oid = None if teacher else session.get('veli_ogrenci_id')
    if not teacher and not oid:
        return redirect(url_for('veli_giris'))
    student = student_row(oid) if oid else None
    if oid and not student: abort(403)
    exams = optik.sinavlari_listele()
    if student: exams = [e for e in exams if visible(e, student) and test_window.released(e)]
    selected = request.values.get('test', type=int)
    exam = next((e for e in exams if e['id'] == selected), None)
    if selected and exam is None: abort(404)
    if not exam and exams: exam = exams[0]
    con = connection()
    csrf = token()
    if request.method == 'POST':
        if not secrets.compare_digest(request.form.get('csrf',''), csrf):
            con.close(); abort(400)
        if not exam: con.close(); abort(404)
        action = request.form.get('action')
        qno = request.form.get('no', type=int)
        if action in {'meta','option_note'} and (not qno or not 1 <= qno <= exam['soru_sayisi']):
            con.close(); abort(400)
        if action == 'meta' and teacher:
            if exam.get('ogretmen_id') != teacher: con.close(); abort(403)
            con.execute('INSERT INTO ev_soru_meta VALUES(?,?,?,?) ON CONFLICT(sinav_id,no) DO UPDATE SET konu=excluded.konu,cozum=excluded.cozum',
                (exam['id'],qno,request.form.get('topic','').strip()[:160],request.form.get('solution','').strip()[:4000]))
            message='Konu ve çözüm kaydedildi.'
        elif action == 'option_note' and teacher:
            if exam.get('ogretmen_id') != teacher or db.ogretmen_yetki_al(teacher) != 'tam': con.close(); abort(403)
            option=request.form.get('option','')
            if option not in ['A','B','C','D','E','']: con.close(); abort(400)
            con.execute('INSERT INTO ev_option_note VALUES(?,?,?,?) ON CONFLICT(sinav_id,no,option) DO UPDATE SET note=excluded.note',
                (exam['id'],qno,option,request.form.get('note','').strip()[:500]))
            message='Seçenek açıklaması kaydedildi.'
        else:
            con.close(); abort(403)
        con.commit(); con.close(); flash(message,'success')
        return redirect(url_for('ev_analiz.index',test=exam['id'],tab=request.form.get('tab','overview'), **{'class':request.form.get('class','')}))
    all_people = optik.cozen_ogrenciler(exam['id']) if exam else []
    if teacher: all_people=[p for p in all_people if bp.can_access(teacher,p['id'])]
    classes=sorted({p['sinif'] for p in all_people}) if teacher else []
    selected_class=request.args.get('class','') if teacher else ''
    people=[p for p in all_people if p['sinif']==selected_class] if selected_class else all_people
    if student: people=[p for p in all_people if p['id']==oid]
    metadata={r['no']:dict(r) for r in con.execute('SELECT * FROM ev_soru_meta WHERE sinav_id=?',(exam['id'],))} if exam else {}
    questions=aggregate(exam,people,metadata) if exam else []
    option_notes={(r['no'],r['option']):r['note'] for r in con.execute('SELECT * FROM ev_option_note WHERE sinav_id=?',(exam['id'],))} if exam else {}
    for q in questions:
        q['options']=[dict(letter=letter,count=count,note=option_notes.get((q['no'],letter),''),
            members=[p for p in people if p['satirlar'][q['no']-1]['verilen']==letter]) for letter,count in q['counts'].items()]
    completed=bool(people) if student else True
    if student and not completed:
        # Never send answer keys / solutions before this student's submission.
        for q in questions: q.update(key='',cozum='',counts={},rate=None)
    weekly=[]; trend=[]; pending=0; weekly_topics=defaultdict(lambda: {'dogru':0,'yanlis':0,'bos':0})
    week=request.args.get('week','')
    try: start=date.fromisoformat(week)
    except ValueError: start=date.today()
    start-=timedelta(days=start.weekday()); end=start+timedelta(days=7)
    if student:
        for e in exams:
            result=optik.sonuc_getir(e['id'],oid)
            if result:
                entry=dict(id=e['id'],ad=e['ad'],date=result['zaman'][:10],dogru=result['dogru'],yanlis=result['yanlis'],bos=result['bos'],rate=metrik.oran(result['dogru'],e['soru_sayisi']))
                trend.append(entry)
                if start.isoformat()<=entry['date']<end.isoformat():
                    weekly.append(entry)
                    labels={r['no']:r['konu'] for r in con.execute('SELECT no,konu FROM ev_soru_meta WHERE sinav_id=?',(e['id'],))}
                    for a in optik.puan_hesapla(e['cevaplar'],result['isaretler'],e.get('yanlis_goturme',3))['satirlar']:
                        weekly_topics[labels.get(a['no']) or 'Konu tanımlanmamış'][a['durum']]+=1
            else: pending+=1
    if teacher:
        for e in exams:
            cohort=[p for p in optik.cozen_ogrenciler(e['id']) if bp.can_access(teacher,p['id']) and (not selected_class or p['sinif']==selected_class)]
            if cohort:
                trend.append(dict(id=e['id'],ad=e['ad'],date=e['tarih'],rate=metrik.oran(sum(p['dogru'] for p in cohort),len(cohort)*e['soru_sayisi'])))
    topic_map=defaultdict(lambda:dict(correct=0,total=0,members=set()))
    for q in questions:
        name=q['konu'] or 'Konu tanımlanmamış'
        topic_map[name]['correct']+=q['correct']; topic_map[name]['total']+=len(people)
        topic_map[name]['members'].update(q['wrong']+q['blank'])
    topics=[dict(name=name,rate=metrik.oran(v['correct'],v['total']),members=sorted(v['members'])) for name,v in topic_map.items()]
    con.close()
    totals={k:sum(p[k] for p in people) for k in ['dogru','yanlis','bos']}
    return render_template('ev_analiz.html',teacher=bool(teacher),read_only=bool(teacher and db.ogretmen_yetki_al(teacher)=='rehber'),student=student,exams=exams,exam=exam,
      people=people,questions=questions,topics=topics,totals=totals,
      csrf=csrf,classes=classes,selected_class=selected_class,completed=completed,
      can_edit=bool(teacher and db.ogretmen_yetki_al(teacher)!='rehber' and exam and exam.get('ogretmen_id')==teacher),
      weekly=weekly,weekly_topics=dict(weekly_topics),trend=sorted(trend,key=lambda x:x['date']),pending=pending,week=start.isoformat(),week_end=(end-timedelta(days=1)).isoformat(),
      tab=request.args.get('tab','overview'))
