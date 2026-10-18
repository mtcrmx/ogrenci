"""Outcome matrix and teacher-selected follow-up work using recorded answers."""
import json
from datetime import datetime
from flask import abort
import database as db
import lgs_optik as optik

def init(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS ev_option_note (
        sinav_id INTEGER NOT NULL, no INTEGER NOT NULL, option TEXT NOT NULL,
        note TEXT NOT NULL, PRIMARY KEY(sinav_id,no,option));
    CREATE TABLE IF NOT EXISTS ev_support_plan (
        grup_id INTEGER PRIMARY KEY, target_id INTEGER NOT NULL,
        outcomes TEXT NOT NULL, baseline TEXT NOT NULL,
        created TEXT NOT NULL);
    ''')

def mappings(eid):
    from lgs_kazanim import connect, catalog
    con=connect()
    entries={i['id']:i for i in catalog()['items']}
    result={r['no']:entries[r['kazanim_id']] for r in con.execute(
        'SELECT * FROM lgs_soru_kazanim WHERE sinav_id=? AND version=?', (eid,catalog()['year']))
        if r['kazanim_id'] in entries}
    con.close()
    return result

def cells(person, mapping):
    result={}
    for no,item in mapping.items():
        cell=result.setdefault(item['id'],dict(correct=0,total=0,questions=[]))
        if not person or no>len(person['satirlar']):continue
        q=person['satirlar'][no-1]
        cell['total']+=1
        cell['correct']+=q['durum']=='dogru'
        cell['questions'].append(q)
    for cell in result.values():
        cell['rate']=round(100*cell['correct']/cell['total']) if cell['total'] else None
    return result

def matrix(exam, people, teacher, can_access, selected_class):
    if not exam or not teacher:return dict(columns=[],rows=[])
    from ev_analiz import visible
    mapping=mappings(exam['id'])
    columns=list({v['id']:v for v in mapping.values()}.values())
    con=db._conn()
    roster=[dict(r) for r in con.execute('SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id ORDER BY s.sinif_adi,o.ad_soyad')]
    con.close()
    submitted={p['id']:p for p in people}
    roster=[p for p in roster if can_access(teacher,p['id']) and visible(exam,p) and (not selected_class or p['sinif_adi']==selected_class)]
    rows=[dict(id=p['id'],name=p['ad_soyad'],sinif=p['sinif_adi'],cells=cells(submitted.get(p['id']),mapping)) for p in roster]
    for column in columns:
        column['support_members']=[r['id'] for r in rows if r['cells'][column['id']]['rate'] is not None and r['cells'][column['id']]['rate']<80]
    return dict(columns=columns,rows=rows)

def assign(con, exam, teacher, can_access, form):
    from ev_analiz import visible, student_row
    if db.ogretmen_yetki_al(teacher)!='tam':abort(403)
    members=set(form.getlist('member',type=int))
    outcomes=set(form.getlist('outcome'))
    name=form.get('name','').strip()[:120]
    target=optik.sinav_getir(form.get('target',type=int) or 0)
    source_map=mappings(exam['id'])
    if not name or not members or not outcomes or not outcomes <= {v['id'] for v in source_map.values()}:abort(400)
    if not target or target['id']==exam['id'] or target.get('kaynak')=='kamera':abort(400,'Yeni bir evde tekrar testi seçin.')
    if target.get('ogretmen_id')!=teacher:abort(403)
    target_map=mappings(target['id'])
    if not outcomes <= {v['id'] for v in target_map.values()}:abort(400,'Tekrar testinde seçilen kazanımların tümü eşleştirilmiş olmalı.')
    source_people={p['id']:p for p in optik.cozen_ogrenciler(exam['id'])}
    if not members <= set(source_people):abort(400)
    if any(not can_access(teacher,m) or not visible(target,student_row(m) or {}) for m in members):abort(403)
    if any(optik.sonuc_getir(target['id'],m) for m in members):abort(400,'Seçilen öğrencilerden biri bu testi zaten tamamlamış. Yeni bir test seçin.')
    baseline={str(m):{k:v for k,v in cells(source_people[m],source_map).items() if k in outcomes} for m in members}
    cur=con.execute('INSERT INTO ev_grup(ad,ogretmen_id,kaynak_id) VALUES(?,?,?)',(name,teacher,exam['id']))
    gid=cur.lastrowid
    con.executemany('INSERT INTO ev_grup_uye VALUES(?,?)',[(gid,m) for m in members])
    con.execute('INSERT INTO ev_grup_test VALUES(?,?)',(gid,target['id']))
    con.execute('INSERT INTO ev_support_plan VALUES(?,?,?,?,?)',(gid,target['id'],json.dumps(sorted(outcomes)),json.dumps(baseline),datetime.now().isoformat(timespec='seconds')))

def progress(con, group, teacher, oid, can_access):
    plan=con.execute('SELECT * FROM ev_support_plan WHERE grup_id=?',(group['id'],)).fetchone()
    if not plan:return None
    from lgs_kazanim import catalog
    entries={i['id']:i for i in catalog()['items']}
    baseline=json.loads(plan['baseline'])
    ids=set(json.loads(plan['outcomes']))
    mapping=mappings(plan['target_id'])
    people={p['id']:p for p in optik.cozen_ogrenciler(plan['target_id'])}
    rows=[]
    for member,scores in baseline.items():
        mid=int(member)
        if not (can_access(teacher,mid) if teacher else mid==oid):continue
        name=con.execute('SELECT ad_soyad FROM ogrenciler WHERE id=?',(mid,)).fetchone()
        if not name:continue
        after=cells(people.get(mid),mapping)
        for key,before in scores.items():
            a=after.get(key,{})
            rows.append(dict(name=name[0],outcome=entries.get(key,{}).get('code',key),before=before,after=a,
                delta=a['rate']-before['rate'] if a.get('rate') is not None and before['rate'] is not None else None))
    return dict(rows=rows,created=plan['created'],outcomes=[entries.get(k,{}).get('code',k) for k in sorted(ids)])
