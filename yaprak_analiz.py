"""Read-only school leaf-test analytics, using existing aggregate results."""
from collections import defaultdict
from datetime import date
from hashlib import sha256
from statistics import mean
from flask import Blueprint, abort, redirect, render_template, request, session, url_for
import database as db
import lgs_optik as optik

bp = Blueprint('yaprak_analiz', __name__)

def summarize(rows):
    if not rows:
        return dict(n=0,dogru=0,yanlis=0,bos=0,net=0,rate=0)
    return dict(n=len(rows), **{k:round(mean(r[k] for r in rows),1) for k in ('dogru','yanlis','bos','net','rate')})

def group_records(rows):
    groups={}
    for source in rows:
        r=dict(source)
        count=r['soru_sayisi'] or (r['dogru']+r['yanlis']+r['bos'])
        if count<=0: continue
        r['soru_sayisi']=count
        r['rate']=round(100*r['dogru']/count,1)
        key=(r['ad'],r['tarih'],r['ders'],count,r['yanlis_goturme'])
        if r.get('camera_exam'): key=(*key,'kamera',r['camera_exam'])
        ident=sha256(repr(key).encode()).hexdigest()[:20]
        group=groups.setdefault(ident,dict(id=ident,ad=r['ad'],tarih=r['tarih'],ders=r['ders'],count=count,rule=r['yanlis_goturme'],camera_exam=r.get('camera_exam'),rows=[]))
        # Old duplicate entries: keep the latest saved course row per student.
        group['rows']=[p for p in group['rows'] if p['ogrenci_id']!=r['ogrenci_id']]+[r]
    return sorted(groups.values(),key=lambda g:(g['tarih'],g['ad'],g['id']),reverse=True)

def register(app, accessible):
    bp.accessible=accessible
    app.register_blueprint(bp)

@bp.get('/okul-yaprak-analiz')
def index():
    teacher=session.get('ogretmen_id')
    oid=None if teacher else session.get('veli_ogrenci_id')
    if not teacher and not oid: return redirect(url_for('veli_giris'))
    con=db._conn();db._lgs_init(con);optik._init(con)
    roster=[dict(r) for r in con.execute('SELECT o.id,o.ad_soyad,o.ogr_no,o.sinif_id,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id')]
    child=next((r for r in roster if r['id']==oid),None)
    if oid and not child: con.close();abort(403)
    if teacher:
        roster=[r for r in roster if bp.accessible(teacher,r['id'])]
    else:
        roster=[r for r in roster if r['sinif_id']==child['sinif_id']]
    allowed={r['id'] for r in roster}
    rows=[dict(r) for r in con.execute('''SELECT d.ad,d.tarih,d.ogrenci_id,dd.*,o.ad_soyad,o.ogr_no,o.sinif_id,s.sinif_adi
        FROM lgs_deneme d JOIN lgs_deneme_ders dd ON dd.deneme_id=d.id
        JOIN ogrenciler o ON o.id=d.ogrenci_id JOIN siniflar s ON s.id=o.sinif_id
        WHERE d.tur='ders' ORDER BY dd.id''') if r['ogrenci_id'] in allowed]
    rows += [dict(r) for r in con.execute('''SELECT e.id AS camera_exam,e.ad,e.tarih,e.ders,e.soru_sayisi,
        r.ogrenci_id,r.dogru,r.yanlis,r.bos,r.net,3 AS yanlis_goturme,
        o.ad_soyad,o.ogr_no,o.sinif_id,s.sinif_adi FROM lgs_optik_sinav e
        JOIN lgs_optik_sonuc r ON r.sinav_id=e.id JOIN ogrenciler o ON o.id=r.ogrenci_id
        JOIN siniflar s ON s.id=o.sinif_id WHERE e.kaynak='kamera' ORDER BY r.id''') if r['ogrenci_id'] in allowed]
    con.close()
    groups=group_records(rows)
    if child: groups=[g for g in groups if any(r['ogrenci_id']==oid for r in g['rows'])]
    courses=sorted({g['ders'] for g in groups})
    course=request.args.get('ders') or (groups[0]['ders'] if groups else '')
    classroom=request.args.get('sinif','') if teacher else child['sinif_adi']
    if classroom.isdecimal():
        classroom=next((r['sinif_adi'] for r in roster if r['sinif_id']==int(classroom)), classroom)
    selected_student=request.args.get('ogrenci',type=int) if teacher else oid
    if selected_student and selected_student not in allowed: abort(403)
    start=request.args.get('baslangic','');end=request.args.get('bitis','')
    for value in (start,end):
        if value:
            try: date.fromisoformat(value)
            except ValueError: abort(400)
    if start and end and start>end: abort(400)
    filtered=[g for g in groups if g['ders']==course and (not start or g['tarih']>=start) and (not end or g['tarih']<=end) and (not classroom or any(r['sinif_adi']==classroom for r in g['rows']))]
    selected=request.args.get('test')
    exam=next((g for g in filtered if g['id']==selected),None) or (filtered[0] if filtered else None)
    people=[];class_rows=[];summary=summarize([]);own=None;branches=[];missing=[];trend=[];history=[]
    if exam:
        class_rows=[r for r in exam['rows'] if not classroom or r['sinif_adi']==classroom]
        summary=summarize(class_rows)
        own=next((r for r in class_rows if r['ogrenci_id']==selected_student),None)
        for r in class_rows:
            previous=[(g,next((p for p in g['rows'] if p['ogrenci_id']==r['ogrenci_id']),None)) for g in groups if g['ders']==course and g['tarih']<exam['tarih']]
            prior=next((p for g,p in previous if p),None)
            r['delta']=round(r['rate']-prior['rate'],1) if prior else None
            r['previous_date']=next((g['tarih'] for g,p in previous if p),None)
            r['gap']=round(r['rate']-summary['rate'],1)
        people=sorted(class_rows,key=lambda r:(-r['rate'],r['ad_soyad'])) if teacher else ([own] if own else [])
        participating={r['ogrenci_id'] for r in class_rows}
        included_classes={r['sinif_adi'] for r in class_rows}
        missing=[r for r in roster if (r['sinif_adi']==classroom if classroom else r['sinif_adi'] in included_classes) and r['id'] not in participating] if teacher else []
        if teacher:
            for name in sorted({r['sinif_adi'] for r in exam['rows']}):
                branches.append(dict(name=name,**summarize([r for r in exam['rows'] if r['sinif_adi']==name])))
    for g in reversed(filtered):
        selected_rows=[r for r in g['rows'] if not classroom or r['sinif_adi']==classroom]
        if not selected_rows:continue
        stats=summarize(selected_rows)
        individual=next((r for r in selected_rows if r['ogrenci_id']==selected_student),None)
        trend.append(dict(ad=g['ad'],date=g['tarih'],class_rate=stats['rate'],own_rate=individual['rate'] if individual else None))
        history.append(dict(id=g['id'],ad=g['ad'],date=g['tarih'],count=g['count'],own_rate=individual['rate'] if individual else None,own_net=individual['net'] if individual else None,**stats))
    for i,t in enumerate(trend):
        t['x']=35+(i*630/max(len(trend)-1,1));t['y']=185-t['class_rate']*1.6
        t['own_y']=185-t['own_rate']*1.6 if t['own_rate'] is not None else None
    buckets=[]
    for low,high in [(0,25),(25,50),(50,75),(75,101)]:
        entries=[r for r in class_rows if low<=r['rate']<high]
        buckets.append(dict(low=low,high=high,label=f'%{low}–<{high}' if high!=101 else '%75–100',n=len(entries),width=round(100*len(entries)/max(len(class_rows),1))))
    return render_template('yaprak_analiz.html',teacher=bool(teacher),child=child,exam=exam,exams=filtered,courses=courses,course=course,
        classroom=classroom,classes=sorted({r['sinif_adi'] for r in roster}),start=start,end=end,summary=summary,own=own,
        people=people,missing=missing,branches=branches,trend=trend,history=list(reversed(history)),buckets=buckets,
        selected_student=selected_student,roster=roster if teacher else [],
        points=' '.join(f'{t["x"]},{t["y"]}' for t in trend))


SOURCE_NAMES = {'ev': 'Evde test', 'okul': 'Okulda yaprak test', 'deneme': 'Deneme'}


def combined_stats(rows):
    total = sum(r['soru_sayisi'] for r in rows)
    correct = sum(r['dogru'] for r in rows)
    return dict(n=len(rows), tests=len({r['exam_key'] for r in rows}),
                students=len({r['ogrenci_id'] for r in rows}), total=total,
                correct=correct, wrong=sum(r['yanlis'] for r in rows),
                blank=sum(r['bos'] for r in rows),
                rate=round(100*correct/total, 1) if total else 0)


@bp.get('/lgs/birlesik-analiz')
def combined():
    teacher = None if session.get('veli_ogrenci_id') else session.get('ogretmen_id')
    child_id = None if teacher else session.get('veli_ogrenci_id')
    if not teacher and not child_id:
        return redirect(url_for('veli_giris'))
    con = db._conn()
    db._lgs_init(con); optik._init(con)
    roster = [dict(r) for r in con.execute('SELECT o.id,o.ad_soyad,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id')]
    roster = [r for r in roster if bp.accessible(teacher,r['id'])] if teacher else [r for r in roster if r['id']==child_id]
    allowed = {r['id'] for r in roster}
    if child_id and not allowed:
        con.close(); abort(403)
    rows = []
    for row in con.execute('SELECT d.ad,d.tarih,d.tur,d.ogretmen_id,d.ogrenci_id,dd.* FROM lgs_deneme d JOIN lgs_deneme_ders dd ON dd.deneme_id=d.id ORDER BY dd.id'):
        r = dict(row)
        if r['ogrenci_id'] not in allowed: continue
        r['source'] = 'okul' if r['tur']=='ders' else 'deneme'
        r['exam_key'] = ('legacy',r['ogretmen_id'],r['ad'],r['tarih'],r['tur'])
        r['detail'] = url_for('yaprak_analiz.index',ders=r['ders']) if r['source']=='okul' else (url_for('deneme_analiz') if teacher else url_for('veli_lgs',bolum='deneme'))
        rows.append(r)
    for row in con.execute('SELECT e.id AS exam_id,e.ad,e.tarih,e.tur,e.kaynak,e.ders,e.soru_sayisi,e.cevaplar,r.isaretler,r.ogrenci_id,r.dogru,r.yanlis,r.bos,r.net FROM lgs_optik_sinav e JOIN lgs_optik_sonuc r ON r.sinav_id=e.id ORDER BY r.id'):
        r = dict(row)
        if r['ogrenci_id'] not in allowed: continue
        r['source'] = 'okul' if r['kaynak']=='kamera' else ('deneme' if r['tur']=='deneme' else 'ev')
        r['exam_key'] = ('optik',r['exam_id'])
        r['detail'] = url_for('ev_analiz.index',test=r['exam_id'])
        r['ders'] = r['ders'] or 'Genel deneme'
        rows.append(r)
    con.close()
    students = {r['id']:r for r in roster}
    unique = {}
    for r in rows:
        r['soru_sayisi'] = r['soru_sayisi'] or (r['dogru']+r['yanlis']+r['bos'])
        if r['soru_sayisi'] <= 0: continue
        r.update(students[r['ogrenci_id']])
        unique[(r['exam_key'],r['ders'],r['ogrenci_id'])] = r
    rows = list(unique.values())
    courses = sorted({r['ders'] for r in rows})
    source = request.args.get('tur','tumu')
    if source not in ('tumu',*SOURCE_NAMES): abort(400)
    classroom = request.args.get('sinif','') if teacher else ''
    student = request.args.get('ogrenci',type=int) if teacher else child_id
    if student and student not in allowed: abort(403)
    course = request.args.get('ders','')
    start,end = request.args.get('baslangic',''),request.args.get('bitis','')
    for value in (start,end):
        if value:
            try: date.fromisoformat(value)
            except ValueError: abort(400)
    if start and end and start>end: abort(400)
    rows = [r for r in rows if (source=='tumu' or r['source']==source) and
            (not classroom or r['sinif_adi']==classroom) and (not student or r['ogrenci_id']==student) and
            (not course or r['ders']==course) and (not start or r['tarih']>=start) and (not end or r['tarih']<=end)]
    breakdown = [dict(name=name,**combined_stats([r for r in rows if r['source']==key])) for key,name in SOURCE_NAMES.items() if source in ('tumu',key)]
    grouped = defaultdict(list)
    for r in rows: grouped[(r['exam_key'],r['ders'])].append(r)
    history = [dict(ad=rs[0]['ad'],date=rs[0]['tarih'],course=rs[0]['ders'],source=SOURCE_NAMES[rs[0]['source']],detail=rs[0]['detail'],**combined_stats(rs)) for rs in grouped.values()]
    history.sort(key=lambda r:(r['date'],r['ad']),reverse=True)
    people = [dict(name=p['ad_soyad'],classroom=p['sinif_adi'],**combined_stats([r for r in rows if r['ogrenci_id']==p['id']])) for p in roster if any(r['ogrenci_id']==p['id'] for r in rows)]
    from lgs_kazanim import outcome_summary
    outcomes=outcome_summary(rows)
    return render_template('birlesik_analiz.html',outcomes=outcomes,teacher=bool(teacher),sources=SOURCE_NAMES,source=source,
        classes=sorted({r['sinif_adi'] for r in roster}),classroom=classroom,roster=roster,student=student,
        courses=courses,course=course,start=start,end=end,stats=combined_stats(rows),breakdown=breakdown,history=history,people=people)
