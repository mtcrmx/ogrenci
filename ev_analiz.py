"""Evde testlerden soru analizi, yardım ve öğretmen çalışma grupları."""
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
    # Existing home tests are available to their class (or any eighth grade).
    from moduller import seviye as sinif_seviyesi
    return (exam.get('kaynak')=='kamera' or sinif_seviyesi(student) == 8) and (not exam.get('sinif_id') or int(exam['sinif_id']) == int(student['sinif_id']))

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
        if action in {'help','meta','option_note'} and (not qno or not 1 <= qno <= exam['soru_sayisi']):
            con.close(); abort(400)
        if action == 'help' and student:
            con.execute('INSERT INTO ev_yardim(sinav_id,ogrenci_id,no,notu) VALUES(?,?,?,?) ON CONFLICT(sinav_id,ogrenci_id,no) DO UPDATE SET notu=excluded.notu, yanit=\'\', ogretmen_id=NULL, zaman=CURRENT_TIMESTAMP',
                (exam['id'],oid,qno,request.form.get('note','').strip()[:1000]))
            message = 'Yardım isteğiniz öğretmen ekranına eklendi.'
        elif action == 'reply' and teacher:
            ids = request.form.getlist('help_id', type=int)
            reply = request.form.get('reply','').strip()
            if not ids or not reply or len(reply)>4000: con.close(); abort(400)
            rows = [dict(r) for r in con.execute('SELECT * FROM ev_yardim WHERE sinav_id=?',(exam['id'],)) if r['id'] in ids]
            if len(rows)!=len(set(ids)) or any(not bp.can_access(teacher,r['ogrenci_id']) for r in rows): con.close(); abort(403)
            for row in rows:
                con.execute('UPDATE ev_yardim SET yanit=?,ogretmen_id=? WHERE id=?',(reply,teacher,row['id']))
            message = 'Yanıt seçilen öğrencilerin veli paneline eklendi.'
        elif action == 'meta' and teacher:
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
        elif action == 'support' and teacher:
            from analysis_support import assign
            try:
                assign(con,exam,teacher,bp.can_access,request.form)
            except Exception:
                con.rollback();con.close();raise
            message='Tekrar testi seçilen öğrencilerin çalışma listesine eklendi. Önce–sonra takibi hazır.'
        elif action == 'group' and teacher:
            members=set(request.form.getlist('member',type=int))
            actual={p['id'] for p in optik.cozen_ogrenciler(exam['id'])}
            name=request.form.get('name','').strip()[:120]
            if not members or not name or not members <= actual: con.close(); abort(400)
            if any(not bp.can_access(teacher,m) for m in members): con.close(); abort(403)
            cur=con.execute('INSERT INTO ev_grup(ad,ogretmen_id,kaynak_id) VALUES(?,?,?)',(name,teacher,exam['id']))
            con.executemany('INSERT INTO ev_grup_uye VALUES(?,?)',[(cur.lastrowid,m) for m in members])
            message='Çalışma grubu oluşturuldu. Gruba evde test atayabilirsiniz.'
        elif action == 'assign' and teacher:
            gid=request.form.get('group',type=int); target=request.form.get('target',type=int)
            group=con.execute('SELECT * FROM ev_grup WHERE id=? AND ogretmen_id=?',(gid,teacher)).fetchone()
            target_exam=next((e for e in exams if e['id']==target),None)
            members=[r[0] for r in con.execute('SELECT ogrenci_id FROM ev_grup_uye WHERE grup_id=?',(gid,))]
            if not group or not target_exam or not members: con.close(); abort(400)
            if any(not bp.can_access(teacher,m) or not visible(target_exam,student_row(m) or {}) for m in members): con.close(); abort(403)
            con.execute('INSERT OR IGNORE INTO ev_grup_test VALUES(?,?)',(gid,target))
            message='Test grubun çalışma listesine eklendi; veliler kendi panellerinde görebilir.'
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
    help_rows=[dict(r) for r in con.execute('SELECT h.*,o.ad_soyad FROM ev_yardim h JOIN ogrenciler o ON o.id=h.ogrenci_id WHERE h.sinav_id=? ORDER BY h.no,h.zaman DESC',(exam['id'],))] if exam else []
    help_rows=[r for r in help_rows if (bp.can_access(teacher,r['ogrenci_id']) if teacher else r['ogrenci_id']==oid)]
    groups=[dict(r) for r in con.execute('SELECT * FROM ev_grup WHERE ogretmen_id=? ORDER BY id DESC',(teacher,))] if teacher else [dict(r) for r in con.execute('SELECT g.* FROM ev_grup g JOIN ev_grup_uye u ON u.grup_id=g.id WHERE u.ogrenci_id=?',(oid,))]
    for g in groups:
        g['members']=[dict(r) for r in con.execute('SELECT o.id,o.ad_soyad FROM ev_grup_uye u JOIN ogrenciler o ON o.id=u.ogrenci_id WHERE u.grup_id=?',(g['id'],))] if teacher else []
        g['tests']=[dict(r) for r in con.execute('SELECT e.id,e.ad,e.ogretmen_id,e.kaynak FROM ev_grup_test t JOIN lgs_optik_sinav e ON e.id=t.sinav_id WHERE t.grup_id=?',(g['id'],)) if optik.teacher_can_view(dict(r))]
        from analysis_support import progress
        g['progress']=progress(con,g,teacher,oid,bp.can_access)
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
    from analysis_support import matrix
    outcome_matrix=matrix(exam,people,teacher,bp.can_access,selected_class)
    targets=[e for e in exams if teacher and e.get('ogretmen_id')==teacher and e.get('kaynak')!='kamera' and (not exam or e['id']!=exam['id'])]
    con.close()
    totals={k:sum(p[k] for p in people) for k in ['dogru','yanlis','bos']}
    return render_template('ev_analiz.html',teacher=bool(teacher),read_only=bool(teacher and db.ogretmen_yetki_al(teacher)=='rehber'),student=student,exams=exams,exam=exam,
      people=people,questions=questions,topics=topics,totals=totals,help_rows=help_rows,groups=groups,outcome_matrix=outcome_matrix,targets=targets,
      csrf=csrf,classes=classes,selected_class=selected_class,completed=completed,
      can_edit=bool(teacher and db.ogretmen_yetki_al(teacher)!='rehber' and exam and exam.get('ogretmen_id')==teacher),
      weekly=weekly,weekly_topics=dict(weekly_topics),trend=sorted(trend,key=lambda x:x['date']),pending=pending,week=start.isoformat(),week_end=(end-timedelta(days=1)).isoformat(),
      tab=request.args.get('tab','overview'))
