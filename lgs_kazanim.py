"""Versioned, owner-scoped question/outcome assignments for grade-eight tests."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import json,secrets
from flask import Blueprint,abort,render_template,request,session,redirect,url_for,flash
import database as db
import lgs_optik as optik
from ev_analiz import connection

bp=Blueprint('lgs_kazanim',__name__,url_prefix='/lgs/kazanimlar')

@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent/'data/lgs8_kazanimlar_2026.json').read_text(encoding='utf-8'))

def connect():
    con=connection()
    con.execute('CREATE TABLE IF NOT EXISTS lgs_soru_kazanim (sinav_id INTEGER NOT NULL,no INTEGER NOT NULL,kazanim_id TEXT NOT NULL,version TEXT NOT NULL,PRIMARY KEY(sinav_id,no))')
    return con

def fingerprint(exam):
    return sha256(json.dumps(exam['cevaplar']).encode()).hexdigest()

@bp.before_request
def protect():
    if not session.get('ogretmen_id'):return redirect(url_for('login'))
    if db.ogretmen_yetki_al(session['ogretmen_id'])!='tam':abort(403)
    if 'kazanim_csrf' not in session:session['kazanim_csrf']=secrets.token_urlsafe(32)
    if request.method=='POST' and not secrets.compare_digest(request.form.get('csrf',''),session['kazanim_csrf']):abort(400)

@bp.after_request
def private(response):
    response.headers['Cache-Control']='private, no-store'
    return response

@bp.get('')
def index():
    exams=[e for e in optik.sinavlari_listele() if e.get('ogretmen_id')==session['ogretmen_id'] and (not e.get('sinif_id') or (e.get('sinif_adi') or '').startswith('8/'))]
    return render_template('lgs_kazanim.html',exam=None,exams=exams,catalog=catalog())

@bp.route('/<int:eid>',methods=['GET','POST'])
def edit(eid):
    exam=optik.sinav_getir(eid)
    if not exam:abort(404)
    if exam.get('ogretmen_id')!=session['ogretmen_id']:abort(403)
    con=connect()
    if exam.get('sinif_id'):
        row=con.execute('SELECT sinif_adi FROM siniflar WHERE id=?',(exam['sinif_id'],)).fetchone()
        if not row or not row[0].startswith('8/'):con.close();abort(400)
    entries={r['id']:r for r in catalog()['items']}
    saved={r['no']:r['kazanim_id'] for r in con.execute('SELECT * FROM lgs_soru_kazanim WHERE sinav_id=?',(eid,))}
    if request.method=='POST':
        if request.form.get('fingerprint')!=fingerprint(exam):con.close();abort(409,'Cevap anahtarı değişmiş. Sayfayı yenileyin.')
        values={i:request.form.get('q_'+str(i),'') for i in range(1,exam['soru_sayisi']+1)}
        if any(v and v not in entries for v in values.values()):con.close();abort(400)
        with con:
            for no,value in values.items():
                if not value:
                    con.execute('DELETE FROM lgs_soru_kazanim WHERE sinav_id=? AND no=?',(eid,no))
                    if no in saved:con.execute("UPDATE ev_soru_meta SET konu='' WHERE sinav_id=? AND no=?",(eid,no))
                    continue
                item=entries[value]
                con.execute('INSERT INTO lgs_soru_kazanim VALUES(?,?,?,?) ON CONFLICT(sinav_id,no) DO UPDATE SET kazanim_id=excluded.kazanim_id,version=excluded.version',(eid,no,value,catalog()['year']))
                con.execute("INSERT INTO ev_soru_meta(sinav_id,no,konu,cozum) VALUES(?,?,?,'') ON CONFLICT(sinav_id,no) DO UPDATE SET konu=excluded.konu",(eid,no,item['topic']+' · '+item['code']))
        con.close();flash('Soru kazanımları kaydedildi. Analizler güncellendi.','success')
        return redirect(url_for('.edit',eid=eid))
    con.close()
    return render_template('lgs_kazanim.html',exam=exam,catalog=catalog(),saved=saved,csrf=session['kazanim_csrf'],fingerprint=fingerprint(exam))


def outcome_summary(rows):
    entries={r['id']:r for r in catalog()['items']}
    con=connect()
    mappings={(r['sinav_id'],r['no']):r['kazanim_id'] for r in con.execute('SELECT * FROM lgs_soru_kazanim WHERE version=?',(catalog()['year'],))}
    con.close();groups={};eligible=0;tagged=0
    for r in rows:
        if r['exam_key'][0]!='optik':continue
        answers=json.loads(r.get('isaretler') or '[]');keys=json.loads(r.get('cevaplar') or '[]')
        eligible+=len(keys)
        for no,key in enumerate(keys,1):
            item=entries.get(mappings.get((r['exam_id'],no)))
            if not item:continue
            tagged+=1
            g=groups.setdefault(item['id'],dict(item,correct=0,wrong=0,blank=0,total=0,students=set()))
            answer=answers[no-1] if no<=len(answers) else ''
            g['total']+=1;g['students'].add(r['ogrenci_id'])
            g['blank' if not answer else 'correct' if answer==key else 'wrong']+=1
    for g in groups.values():g['rate']=round(100*g['correct']/g['total'],1);g['students']=len(g['students'])
    return dict(rows=sorted(groups.values(),key=lambda g:(g['rate'],g['course'],g['code'])),tagged=tagged,eligible=eligible)
