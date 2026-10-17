"""Counselor workspace: private follow-ups, agenda and read-only academic oversight."""
import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from flask import abort, flash, redirect, render_template, request, session, url_for, make_response
import database as db
import lgs_optik as optik

TOPICS = ('Ders çalışma', 'Sınav süreci', 'Okula uyum', 'Akran ilişkileri', 'Aile iletişimi', 'Devamsızlık', 'Kariyer ve hedef', 'Diğer')
STATES = {'aktif': 'Takipte', 'beklemede': 'Beklemede', 'kapali': 'Tamamlandı'}
KINDS = {'ogrenci': 'Öğrenci görüşmesi', 'veli': 'Veli görüşmesi', 'ogretmen': 'Öğretmen görüşmesi'}
EVENT_STATES = {'planlandi': 'Planlandı', 'tamamlandi': 'Tamamlandı', 'iptal': 'İptal'}


def today():
    return datetime.now(timezone(timedelta(hours=3))).date()


def stamp():
    return datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M')


def init_schema():
    con = db._conn()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS rehber_takip (
      id INTEGER PRIMARY KEY, owner INTEGER NOT NULL, student_id INTEGER NOT NULL REFERENCES ogrenciler(id),
      topic TEXT NOT NULL, goal TEXT NOT NULL, next_step TEXT NOT NULL DEFAULT '', due TEXT NOT NULL DEFAULT '',
      priority TEXT NOT NULL DEFAULT 'normal', state TEXT NOT NULL DEFAULT 'aktif', created TEXT NOT NULL,
      updated TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
    CREATE INDEX IF NOT EXISTS rehber_takip_owner ON rehber_takip(owner,state,due);
    CREATE TABLE IF NOT EXISTS rehber_not (
      id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES rehber_takip(id),
      body TEXT NOT NULL, created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS rehber_ajanda (
      id INTEGER PRIMARY KEY, owner INTEGER NOT NULL, student_id INTEGER NOT NULL REFERENCES ogrenciler(id),
      kind TEXT NOT NULL, starts TEXT NOT NULL, ends TEXT NOT NULL, place TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'planlandi', created TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS rehber_ajanda_owner ON rehber_ajanda(owner,starts);
    CREATE TABLE IF NOT EXISTS rehber_etkinlik (
      id INTEGER PRIMARY KEY, owner INTEGER NOT NULL, class_id INTEGER NOT NULL REFERENCES siniflar(id),
      title TEXT NOT NULL, topic TEXT NOT NULL, goal TEXT NOT NULL, day TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'planlandi', participants INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
    ''')
    optik._init(con)
    con.commit(); con.close()


def query(sql, params=()):
    con = db._conn()
    try:
        return [dict(r) for r in con.execute(sql, params)]
    finally:
        con.close()


def case_rows(owner):
    return query('''SELECT c.*,o.ad_soyad,o.ogr_no,s.sinif_adi FROM rehber_takip c
        JOIN ogrenciler o ON o.id=c.student_id JOIN siniflar s ON s.id=o.sinif_id
        WHERE c.owner=? ORDER BY c.updated DESC,c.id DESC''', (owner,))


def event_rows(owner, start, end):
    return query('''SELECT a.*,o.ad_soyad,s.sinif_adi FROM rehber_ajanda a
        JOIN ogrenciler o ON o.id=a.student_id JOIN siniflar s ON s.id=o.sinif_id
        WHERE a.owner=? AND substr(a.starts,1,10)>=? AND substr(a.starts,1,10)<=? ORDER BY a.starts''', (owner,start,end))


def text(form, name, maximum, required=False):
    value = form.get(name, '').strip()
    if (required and not value) or len(value)>maximum:
        raise ValueError('Zorunlu alanları ve metin uzunluklarını kontrol edin.')
    return value


def valid_day(value, optional=False):
    if optional and not value:
        return ''
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError('Geçerli bir tarih seçin.')


def choice(form, name, allowed):
    value = form.get(name, '')
    if value not in allowed:
        raise ValueError('Geçerli bir konu, tür ve durum seçin.')
    return value


def student_choice(form, roster):
    oid = form.get('student_id', type=int)
    if oid not in {r['id'] for r in roster}:
        raise ValueError('Listeden bir öğrenci seçin.')
    return oid


def dashboard_data(owner, meetings, library):
    day = today().isoformat()
    cases = case_rows(owner)
    due = sorted([c for c in cases if c['state']!='kapali' and c['due'] and c['due']<=day], key=lambda c:c['due'])
    agenda = [e for e in event_rows(owner,day,day) if e['state']!='iptal']
    requests = [r for r in meetings() if r['durum']=='bekliyor']
    items = library()
    return dict(day=day, agenda=agenda, due=due, active=sum(c['state']!='kapali' for c in cases), requests=requests,
                published=sum(i['durum']=='yayinda' for i in items), drafts=sum(i['durum']=='taslak' for i in items))


def register_workspace(app, auth, roster_fn, meetings, library):
    init_schema()

    def page(name, **data):
        return render_template('rehberlik/'+name+'.html', topics=TOPICS, states=STATES, kinds=KINDS,
            event_states=EVENT_STATES, today=today().isoformat(), form=request.form if request.method=='POST' else request.args,
            **data)

    @app.after_request
    def private_response(response):
        if (request.endpoint or '').startswith('rehberlik_'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.route('/rehberlik/takip', methods=['GET','POST'])
    @auth('rehber')
    def rehberlik_takip():
        owner=session['ogretmen_id']; roster=roster_fn(); error=''
        if request.method=='POST':
            try:
                oid=student_choice(request.form,roster)
                topic=choice(request.form,'topic',TOPICS); goal=text(request.form,'goal',1000,True)
                step=text(request.form,'next_step',1000); due=valid_day(request.form.get('due',''),True)
                priority=choice(request.form,'priority',('normal','yakin'))
                con=db._conn()
                with con:
                    cid=con.execute('INSERT INTO rehber_takip(owner,student_id,topic,goal,next_step,due,priority,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                        (owner,oid,topic,goal,step,due,priority,stamp(),stamp())).lastrowid
                con.close()
                flash('Özel takip dosyası oluşturuldu.','success')
                return redirect(url_for('rehberlik_takip_dosya',cid=cid))
            except ValueError as exc:error=str(exc)
        rows=case_rows(owner);q=request.args.get('q','').strip().casefold();state=request.args.get('durum','aktif');classroom=request.args.get('sinif','')
        rows=[r for r in rows if (not q or q in (r['ad_soyad']+' '+str(r['ogr_no'])).casefold()) and (not state or r['state']==state) and (not classroom or r['sinif_adi']==classroom)]
        if request.args.get('vadesi')=='gelen':
            rows=[r for r in rows if r['state']!='kapali' and r['due'] and r['due']<=today().isoformat()]
        return page('takip',rows=rows,roster=roster,classes=db.aktif_sube_siniflari(),error=error,selected_state=state), (400 if error else 200)

    @app.route('/rehberlik/takip/<int:cid>', methods=['GET','POST'])
    @auth('rehber')
    def rehberlik_takip_dosya(cid):
        owner=session['ogretmen_id'];rows=[c for c in case_rows(owner) if c['id']==cid]
        if not rows:abort(404)
        case=rows[0];error=''
        if request.method=='POST':
            try:
                action=request.form.get('action')
                con=db._conn()
                try:
                    with con:
                        if action=='note':
                            body=text(request.form,'body',5000,True)
                            con.execute('INSERT INTO rehber_not(case_id,body,created) VALUES(?,?,?)',(cid,body,stamp()))
                            con.execute('UPDATE rehber_takip SET updated=? WHERE id=? AND owner=?',(stamp(),cid,owner))
                        elif action=='update':
                            goal=text(request.form,'goal',1000,True);step=text(request.form,'next_step',1000)
                            due=valid_day(request.form.get('due',''),True);state=choice(request.form,'state',STATES)
                            priority=choice(request.form,'priority',('normal','yakin'))
                            changed=con.execute('UPDATE rehber_takip SET goal=?,next_step=?,due=?,state=?,priority=?,updated=?,version=version+1 WHERE id=? AND owner=? AND version=?',
                                (goal,step,due,state,priority,stamp(),cid,owner,request.form.get('version',type=int))).rowcount
                            if not changed:raise ValueError('Dosya başka bir sekmede değişti. Sayfayı yenileyip tekrar deneyin.')
                        else:raise ValueError('Geçerli bir işlem seçin.')
                finally:con.close()
                flash('Dosya kaydedildi. Bu kayıt veliye gönderilmez.','success')
                return redirect(url_for('rehberlik_takip_dosya',cid=cid))
            except ValueError as exc:error=str(exc)
        return page('dosya',case=case,notes=query('SELECT * FROM rehber_not WHERE case_id=? ORDER BY id DESC',(cid,)),error=error), (400 if error else 200)

    @app.route('/rehberlik/ajanda', methods=['GET','POST'])
    @auth('rehber')
    def rehberlik_ajanda():
        owner=session['ogretmen_id'];roster=roster_fn();error=''
        selected=request.args.get('gun') or today().isoformat()
        try:selected=valid_day(selected)
        except ValueError:abort(400)
        if request.method=='POST':
            try:
                con=db._conn()
                try:
                    con.execute('BEGIN IMMEDIATE')
                    with con:
                        if request.form.get('action')=='status':
                            state=choice(request.form,'state',EVENT_STATES)
                            if state=='planlandi':raise ValueError('İptal edilen görüşme için yeni bir saat planlayın.')
                            changed=con.execute('UPDATE rehber_ajanda SET state=? WHERE id=? AND owner=?',(state,request.form.get('id',type=int),owner)).rowcount
                            if not changed:abort(404)
                        else:
                            oid=student_choice(request.form,roster);kind=choice(request.form,'kind',KINDS)
                            day=valid_day(request.form.get('day',''));clock=request.form.get('time','')
                            try:
                                start=datetime.fromisoformat(day+'T'+clock)
                                duration=int(request.form.get('duration',''))
                            except ValueError:raise ValueError('Geçerli bir saat ve süre girin.')
                            if start.tzinfo or duration not in (15,20,30,40,45,60,90):raise ValueError('Listeden görüşme süresini seçin.')
                            end=start+timedelta(minutes=duration)
                            starts=start.strftime('%Y-%m-%d %H:%M');ends=end.strftime('%Y-%m-%d %H:%M')
                            if con.execute("SELECT 1 FROM rehber_ajanda WHERE owner=? AND state!='iptal' AND starts<? AND ends>?",(owner,ends,starts)).fetchone():
                                raise ValueError('Bu saat aralığında başka bir görüşme var. Farklı bir saat seçin.')
                            place=text(request.form,'place',120,True)
                            con.execute('INSERT INTO rehber_ajanda(owner,student_id,kind,starts,ends,place,created) VALUES(?,?,?,?,?,?,?)',(owner,oid,kind,starts,ends,place,stamp()))
                            selected=day
                finally:con.close()
                flash('Ajanda kaydedildi. Veliye bilgi vermek için Görüşme talepleri ekranını kullanın.','success')
                return redirect(url_for('rehberlik_ajanda',gun=selected))
            except ValueError as exc:error=str(exc)
        start=date.fromisoformat(selected);week=[start+timedelta(days=i) for i in range(7)]
        return page('ajanda',events=event_rows(owner,selected,(start+timedelta(days=6)).isoformat()),selected=selected,
            week=week,roster=roster,error=error), (400 if error else 200)

    @app.route('/rehberlik/etkinlikler', methods=['GET','POST'])
    @auth('rehber')
    def rehberlik_etkinlikler():
        owner=session['ogretmen_id'];error='';classes=db.aktif_sube_siniflari()
        if request.method=='POST':
            try:
                state=choice(request.form,'state',EVENT_STATES)
                participants=request.form.get('participants',type=int)
                if participants is None or not 0<=participants<=500:raise ValueError('Katılımcı sayısı 0–500 arasında olmalı.')
                con=db._conn()
                try:
                    with con:
                        if request.form.get('action')=='status':
                            changed=con.execute('UPDATE rehber_etkinlik SET state=?,participants=? WHERE id=? AND owner=?',(state,participants,request.form.get('id',type=int),owner)).rowcount
                            if not changed:abort(404)
                        else:
                            title=text(request.form,'title',160,True);goal=text(request.form,'goal',1500,True);topic=choice(request.form,'topic',TOPICS)
                            day=valid_day(request.form.get('day',''));sid=request.form.get('class_id',type=int)
                            if sid not in {s['id'] for s in classes}:raise ValueError('Geçerli bir sınıf seçin.')
                            con.execute('INSERT INTO rehber_etkinlik(owner,class_id,title,topic,goal,day,state,participants,created) VALUES(?,?,?,?,?,?,?,?,?)',(owner,sid,title,topic,goal,day,state,participants,stamp()))
                finally:con.close()
                flash('Sınıf çalışması kaydedildi.','success');return redirect(url_for('rehberlik_etkinlikler'))
            except ValueError as exc:error=str(exc)
        rows=query('SELECT e.*,s.sinif_adi FROM rehber_etkinlik e JOIN siniflar s ON s.id=e.class_id WHERE e.owner=? ORDER BY e.day DESC,e.id DESC',(owner,))
        return page('etkinlikler',rows=rows,classes=classes,error=error), (400 if error else 200)

    @app.route('/rehberlik/ozet')
    @auth('rehber')
    def rehberlik_ozet():
        owner=session['ogretmen_id'];month=request.args.get('ay',today().strftime('%Y-%m'))
        try:start=date.fromisoformat(month+'-01');end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
        except ValueError:abort(400)
        events=event_rows(owner,start.isoformat(),(end-timedelta(days=1)).isoformat())
        activities=query('SELECT * FROM rehber_etkinlik WHERE owner=? AND day>=? AND day<?',(owner,start.isoformat(),end.isoformat()))
        counts=[(label,sum(e['kind']==kind and e['state']=='tamamlandi' for e in events)) for kind,label in KINDS.items()]
        counts += [('Tamamlanan sınıf çalışması',sum(e['state']=='tamamlandi' for e in activities)),('Etkinlik katılımı (tekil kişi değil)',sum(e['participants'] for e in activities if e['state']=='tamamlandi'))]
        if request.args.get('format')=='csv':
            out=io.StringIO();writer=csv.writer(out);writer.writerow(['Dönem','Çalışma','Adet'])
            writer.writerows((month,label,n) for label,n in counts)
            response=make_response('\ufeff'+out.getvalue());response.headers['Content-Type']='text/csv; charset=utf-8';response.headers['Content-Disposition']=f'attachment; filename=rehberlik-{month}.csv'
            return response
        return page('ozet',month=month,counts=counts,planned=sum(e['state']=='planlandi' for e in events),cancelled=sum(e['state']=='iptal' for e in events))

    @app.route('/rehberlik/lgs')
    @auth('rehber')
    def rehberlik_lgs():
        roster=[r for r in roster_fn() if r['sinif_adi'].startswith('8/')]
        classroom=request.args.get('sinif','');q=request.args.get('q','').strip().casefold()
        exams=query('''SELECT e.*,t.ad_soyad AS teacher FROM lgs_optik_sinav e LEFT JOIN ogretmenler t ON t.id=e.ogretmen_id ORDER BY e.tarih DESC,e.id DESC''')
        results=query('SELECT sinav_id,ogrenci_id FROM lgs_optik_sonuc');completed={(r['sinav_id'],r['ogrenci_id']) for r in results}
        rows=[]
        for student in roster:
            records=db.lgs_denemeler(student['id'],200)
            denemeler=[r for r in records if r.get('tur')!='ders']
            assigned=[e for e in exams if not e['sinif_id'] or e['sinif_id']==student['sinif_id']]
            done=sum((e['id'],student['id']) in completed for e in assigned)
            rows.append(dict(student,latest=denemeler[0] if denemeler else None,exam_count=len(denemeler),school_count=sum(r.get('tur')=='ders' for r in records),assigned=len(assigned),done=done,pending=len(assigned)-done))
        summaries=[dict(name=name,students=len(group),with_data=sum(bool(r['latest']) for r in group),pending=sum(r['pending'] for r in group)) for name in sorted({r['sinif_adi'] for r in rows}) for group in [[r for r in rows if r['sinif_adi']==name]]]
        rows=[r for r in rows if (not classroom or r['sinif_adi']==classroom) and (not q or q in (r['ad_soyad']+' '+str(r['ogr_no'])).casefold())]
        return page('lgs',rows=rows,summaries=summaries,classroom=classroom)

    @app.route('/rehberlik/lgs/<int:oid>')
    @auth('rehber')
    def rehberlik_lgs_ogrenci(oid):
        student=next((r for r in roster_fn() if r['id']==oid and r['sinif_adi'].startswith('8/')),None)
        if not student:abort(404)
        records=db.lgs_denemeler(oid,200);teachers={t['id']:t['ad_soyad'] for t in db.tum_ogretmenler()}
        exams=query('''SELECT e.*,t.ad_soyad AS teacher,r.isaretler,r.dogru,r.yanlis,r.bos,r.zaman AS completed
            FROM lgs_optik_sinav e LEFT JOIN ogretmenler t ON t.id=e.ogretmen_id
            LEFT JOIN lgs_optik_sonuc r ON r.sinav_id=e.id AND r.ogrenci_id=?
            WHERE e.sinif_id IS NULL OR e.sinif_id=? ORDER BY e.tarih DESC,e.id DESC''',(oid,student['sinif_id']))
        for exam in exams:
            exam['questions']=optik.puan_hesapla(json.loads(exam['cevaplar']),json.loads(exam['isaretler']))['satirlar'] if exam['isaretler'] else []
        day=today();week=(day-timedelta(days=day.weekday())).isoformat()
        marks=list(db.lgs_program_isaretler(oid,(day-timedelta(days=13)).isoformat(),day.isoformat()).values())
        marks.sort(key=lambda r:(r['tarih'],r['sira']),reverse=True)
        return page('lgs_ogrenci',student=student,records=records,teachers=teachers,exams=exams,profile=db.lgs_profil(oid),
            tasks=db.lgs_gorevler(oid,week),marks=marks,week=week,cases=[c for c in case_rows(session['ogretmen_id']) if c['student_id']==oid])

    @app.route('/rehberlik/ogretmenler')
    @auth('rehber')
    def rehberlik_ogretmenler():
        teacher=request.args.get('ogretmen',type=int);classroom=request.args.get('sinif','')
        start=request.args.get('baslangic') or (today()-timedelta(days=30)).isoformat();end=request.args.get('bitis') or today().isoformat()
        try:start=valid_day(start);end=valid_day(end)
        except ValueError:abort(400)
        if start>end:abort(400)
        exams=query('''SELECT e.id,e.ad AS title,e.tarih AS day,e.olusturma AS recorded,e.ders,e.soru_sayisi,e.ogretmen_id,t.ad_soyad AS teacher,
          s.sinif_adi,COUNT(r.id) AS count FROM lgs_optik_sinav e LEFT JOIN ogretmenler t ON t.id=e.ogretmen_id
          LEFT JOIN siniflar s ON s.id=e.sinif_id LEFT JOIN lgs_optik_sonuc r ON r.sinav_id=e.id
          WHERE e.tarih>=? AND e.tarih<=? GROUP BY e.id ORDER BY e.tarih DESC''',(start,end))
        records=query('''SELECT d.ad AS title,d.tarih AS day,d.tur,d.ogretmen_id,t.ad_soyad AS teacher,s.sinif_adi,
          COUNT(DISTINCT d.ogrenci_id) AS count FROM lgs_deneme d JOIN ogrenciler o ON o.id=d.ogrenci_id JOIN siniflar s ON s.id=o.sinif_id
          LEFT JOIN ogretmenler t ON t.id=d.ogretmen_id WHERE d.tarih>=? AND d.tarih<=?
          GROUP BY d.ad,d.tarih,d.tur,d.ogretmen_id,s.sinif_adi ORDER BY d.tarih DESC''',(start,end))
        exams=[e for e in exams if (not teacher or e['ogretmen_id']==teacher) and (not classroom or not e['sinif_adi'] or e['sinif_adi']==classroom)]
        records=[r for r in records if (not teacher or r['ogretmen_id']==teacher) and (not classroom or r['sinif_adi']==classroom)]
        # Only descriptive academic fields are projected; never expose raw audit JSON or private notes.
        changes=query('''SELECT a.id,a.zaman,a.geri_alindi,a.ogretmen_id,t.ad_soyad AS teacher,r.tablo,r.onceki,r.sonraki
          FROM ogretmen_islem a JOIN ogretmenler t ON t.id=a.ogretmen_id JOIN ogretmen_islem_satir r ON r.islem_id=a.id
          WHERE substr(a.zaman,1,10)>=? AND substr(a.zaman,1,10)<=? AND r.tablo IN ('lgs_deneme','haftalik_odev_bilgi','haftalik_takip','odevler')
          ORDER BY a.zaman DESC,r.id DESC''',(start,end))
        roster={r['id']:r for r in roster_fn()};classes={c['id']:c['sinif_adi'] for c in db.aktif_sube_siniflari()};feed=[];seen=set()
        labels={'lgs_deneme':'Sınav sonucu','haftalik_odev_bilgi':'Sınıf ödevi','haftalik_takip':'Kitap / ödev takibi','odevler':'Ödev'}
        for r in changes:
            if teacher and r['ogretmen_id']!=teacher:continue
            before=json.loads(r['onceki'] or '{}');after=json.loads(r['sonraki'] or '{}')
            data=after or before;student=roster.get(data.get('ogrenci_id'),{})
            name=student.get('sinif_adi') or classes.get(data.get('sinif_id'),'')
            if classroom and name!=classroom:continue
            key=(r['id'],r['tablo'],name,data.get('ogrenci_id'))
            if key in seen:continue
            seen.add(key)
            fields={'kitap_adi':'Kitap','kitap_okuma':'Okuma','kitap_getirme':'Kitap getirme','odev_durum':'Ödev durumu','odev_ders':'Ders','ders':'Ders','ders_adi':'Ders','tema_adi':'Konu','hafta_basi':'Hafta'}
            values={'okudu':'Okudu','okumadi':'Okumadı','getirdi':'Getirdi','getirmedi':'Getirmedi','tam':'Tam','eksik':'Eksik','yapmadi':'Yapmadı'}
            detail=' · '.join(label+': '+values.get(str(data.get(field)),str(data.get(field))) for field,label in fields.items() if data.get(field) not in (None,'') and (not before or not after or before.get(field)!=after.get(field)))
            feed.append(dict(day=r['zaman'],teacher=r['teacher'],classroom=name,label=labels[r['tablo']],student=student.get('ad_soyad',''),detail=detail,
                title=data.get('ad') or data.get('baslik') or data.get('kitap_adi') or data.get('ders') or data.get('ders_adi') or labels[r['tablo']],
                action='Eklendi' if not r['onceki'] else 'Silindi' if not r['sonraki'] else 'Güncellendi',undone=r['geri_alindi']))
        return page('ogretmenler',exams=exams,records=records,feed=feed[:200],truncated=len(feed)>200,teachers=db.tum_ogretmenler(),
            classes=db.aktif_sube_siniflari(),start=start,end=end,selected_teacher=teacher,classroom=classroom)
