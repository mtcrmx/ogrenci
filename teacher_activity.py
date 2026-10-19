"""Management-only teacher work history; never records submitted private fields."""
import json
from datetime import date, timedelta, datetime, timezone
from flask import request, session, g, abort
import database as db
from change_history import TABLES


def init(con):
    con.execute('''CREATE TABLE IF NOT EXISTS teacher_work_request(
        id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL, at TEXT NOT NULL,
        endpoint TEXT NOT NULL, path TEXT NOT NULL, status INTEGER NOT NULL, action_id TEXT)''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_teacher_work_time ON teacher_work_request(at,teacher_id)')
    con.commit()


def register(app):
    con=db._conn();init(con);con.close()
    @app.after_request
    def record_work(response):
        actor=session.get('ogretmen_id')
        endpoint=request.endpoint or ''
        if not actor or request.method not in {'POST','PUT','PATCH','DELETE'} or request.path.startswith('/veli') or endpoint in {'login','logout','yonetici_login'}:
            return response
        con=db._conn()
        try:
            if con.execute('SELECT 1 FROM ogretmenler WHERE id=?',(actor,)).fetchone():
                con.execute('INSERT INTO teacher_work_request(teacher_id,at,endpoint,path,status,action_id) VALUES(?,?,?,?,?,?)',
                    (actor,datetime.now(timezone(timedelta(hours=3))).isoformat(timespec='seconds'),endpoint,request.path,response.status_code,getattr(g,'teacher_action_id',None)))
                con.commit()
        except Exception:
            con.rollback();app.logger.exception('Teacher work history could not be saved')
        finally:con.close()
        return response


def report(args):
    # Check the current database identity, not a requested teacher or session label.
    con=db._conn()
    try:
        actor=con.execute('SELECT ad_soyad FROM ogretmenler WHERE id=?',(session.get('ogretmen_id'),)).fetchone()
        if not actor or actor[0] not in {'METEHAN CÜCEN','ADEM AKGÜL'}:abort(403)
        start=args.get('is_baslangic','');end=args.get('is_bitis','')
        try:
            if start:date.fromisoformat(start)
            if end:date.fromisoformat(end)
            page=max(1,int(args.get('is_sayfa',1)))
            teacher=int(args.get('is_ogretmen') or 0)
        except (ValueError,TypeError):abort(400)
        if start and end and start>end:abort(400)
        teachers=[dict(r) for r in con.execute('SELECT id,ad_soyad FROM ogretmenler ORDER BY ad_soyad')]
        if teacher and teacher not in {r['id'] for r in teachers}:abort(400)
        kind=args.get('is_tur','')
        if kind not in {'','ekleme','duzenleme','silme','geri_alma','istek'}:abort(400)
        sql='''WITH entries AS (
          SELECT a.id AS ref,a.ogretmen_id AS teacher_id,a.zaman AS at,a.yol AS path,
            CASE WHEN a.geri_alindi=1 THEN 'geri_alma'
              WHEN EXISTS(SELECT 1 FROM ogretmen_islem_satir s WHERE s.islem_id=a.id AND s.sonraki IS NULL) THEN 'silme'
              WHEN EXISTS(SELECT 1 FROM ogretmen_islem_satir s WHERE s.islem_id=a.id AND s.onceki IS NOT NULL) THEN 'duzenleme'
              ELSE 'ekleme' END AS kind,'history' AS source,NULL AS status
          FROM ogretmen_islem a
          UNION ALL
          SELECT CAST(r.id AS TEXT),r.teacher_id,r.at,r.path,'istek','request',r.status
          FROM teacher_work_request r WHERE r.action_id IS NULL OR NOT EXISTS(SELECT 1 FROM ogretmen_islem a WHERE a.id=r.action_id)
        ) SELECT e.*,t.ad_soyad FROM entries e LEFT JOIN ogretmenler t ON t.id=e.teacher_id
        WHERE (?=0 OR e.teacher_id=?) AND (?='' OR substr(e.at,1,10)>=?)
        AND (?='' OR substr(e.at,1,10)<=?) AND (?='' OR e.kind=?)'''
        params=(teacher,teacher,start,start,end,end,kind,kind)
        total=con.execute('SELECT COUNT(*) FROM ('+sql+')',params).fetchone()[0]
        page=min(page,max(1,(total+29)//30))
        actions=[dict(r) for r in con.execute(sql+' ORDER BY substr(e.at,1,10) DESC,substr(e.at,12,8) DESC,e.ref DESC LIMIT 30 OFFSET ?',(*params,(page-1)*30))]
        labels={'ekleme':'Kayıt ekleme','duzenleme':'Düzenleme','silme':'Silme','geri_alma':'Geri alınmış işlem','istek':'İşlem isteği'}
        for action in actions:
            action['label']=labels[action['kind']];action['categories']=[];action['students']=[];action['changes']=[]
            if action['source']=='request':
                action['changes']=['İstek yanıtı: '+str(action['status'])+'. Bu kayıt tek başına veri kaydedildiğini göstermez.'];continue
            entries=con.execute('SELECT tablo,onceki,sonraki FROM ogretmen_islem_satir WHERE islem_id=? ORDER BY id',(action['ref'],)).fetchall()
            for entry in entries:
                category=TABLES.get(entry['tablo'],'Diğer kayıt')
                if category not in action['categories']:action['categories'].append(category)
                try:
                    before=json.loads(entry['onceki'] or '{}');after=json.loads(entry['sonraki'] or '{}')
                except (ValueError,TypeError):continue
                data=after or before
                oid=data.get('ogrenci_id')
                if oid:
                    row=con.execute('SELECT o.ad_soyad,s.sinif_adi FROM ogrenciler o LEFT JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?',(oid,)).fetchone()
                    if row:
                        name=row['ad_soyad']+' · '+(row['sinif_adi'] or '')
                        if name not in action['students']:action['students'].append(name)
                elif data.get('sinif_id'):
                    row=con.execute('SELECT sinif_adi FROM siniflar WHERE id=?',(data['sinif_id'],)).fetchone()
                    if row and row[0] not in action['students']:action['students'].append(row[0])
                for field,label in {'ad':'Ad','baslik':'Başlık','ders':'Ders','kitap_adi':'Kitap','kitap_okuma':'Okuma','kitap_getirme':'Getirme','odev_durum':'Ödev','dogru':'Doğru','yanlis':'Yanlış','bos':'Boş','net':'Net','veliye_acik':'Veliye görünür'}.items():
                    if before.get(field)!=after.get(field):
                        a=before.get(field);b=after.get(field)
                        text=f'{label}: {a if a is not None else "—"} → {b if b is not None else "—"}'
                        if text not in action['changes']:action['changes'].append(text[:250])
        return dict(actions=actions,total=total,page=page,pages=max(1,(total+29)//30),teachers=teachers,teacher=teacher,start=start,end=end,kind=kind,labels=labels)
    finally:con.close()
