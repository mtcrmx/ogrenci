"""Owner-scoped record editing with transactional, conflict-safe recovery."""
import hashlib
import json
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from flask import abort, flash, g, redirect, render_template, request, session, url_for
import database as db
import lgs_optik as optik


def field(name, label, kind='text', required=False, options=None, maximum=1000):
    return dict(name=name,label=label,kind=kind,required=required,options=options,maximum=maximum)


REGISTRY = {
    'not': dict(table='ogretmen_notlari',label='Öğretmen notları',fields=[field('not_metni','Not','textarea',True,maximum=2000),field('tur','Tür','select',options={'':'Genel','uyari':'Uyarı','olumlu':'Olumlu not','duyuru':'Duyuru'}),field('veliye_acik','Veliye görünür','select',options={'0':'Hayır','1':'Evet'})]),
    'ev-testi': dict(table='lgs_optik_sinav',label='Evde soru testleri',fields=[field('ad','Test adı',required=True,maximum=80),field('tarih','Tarih','date',True),field('ders','Ders',maximum=80),field('cevaplar','Cevap anahtarı (A B C D…)','key',True)]),
    'sinif-odevi': dict(table='haftalik_odev_bilgi',label='Sınıfın haftalık ödevi',fields=[field('ders','Ders',maximum=80),field('kitap_adi','Kitap adı',maximum=160),field('aciklama','Ödev açıklaması','textarea',maximum=500)]),
    'haftalik': dict(table='haftalik_takip',label='Öğrencinin kitap / ödev takibi',fields=[field('kitap_adi','Kitap adı',maximum=160),field('kitap_sayfa','Okunan sayfa','number'),field('kitap_okuma','Okuma durumu','select',options={'':'İşaret yok','okudu':'Okudu','okumadi':'Okumadı'}),field('kitap_getirme','Kitap getirme','select',options={'':'İşaret yok','getirdi':'Getirdi','getirmedi':'Getirmedi'}),field('odev_durum','Ödev durumu','select',options={'':'İşaret yok','tam':'Tam','eksik':'Eksik','yok':'Yok'}),field('odev_ders','Ödev dersi',maximum=80),field('odev_not','Ödev notu','textarea',maximum=300),field('odev_karar_not','Öğretmen değerlendirmesi','textarea',maximum=200)]),
    'odev': dict(table='odevler',label='Ödev ve tema kayıtları',fields=[field('baslik','Başlık',required=True,maximum=200),field('ders','Ders',required=True,maximum=80),field('aciklama','Açıklama','textarea',maximum=2000),field('son_tarih','Son tarih','date',True)]),
    'sonuc': dict(table='lgs_deneme',label='Ders / deneme sonuçları',native='sonuclar',fields=[]),
    'duyuru': dict(table='bilgilendirmeler',label='Duyurular',owner='yayinlayan',fields=[field('baslik','Başlık',required=True,maximum=200),field('metin','Duyuru','textarea',True,maximum=5000),field('hedef','Hedef kitle','select',options={'herkes':'Herkes','ogretmen':'Öğretmenler','ogrenci':'Öğrenciler','veli':'Veliler'})]),
    'rehber-takip': dict(table='rehber_takip',label='Rehberlik takip dosyaları',owner='owner',private=True,native='rehberlik_takip_dosya',fields=[]),
    'rehber-not': dict(table='rehber_not',label='Özel görüşme notları',owner='case_id',private=True,fields=[field('body','Görüşme notu','textarea',True,maximum=5000)]),
    'rehber-ajanda': dict(table='rehber_ajanda',label='Görüşme ajandası',owner='owner',private=True,fields=[field('starts','Başlangıç','datetime-local',True),field('ends','Bitiş','datetime-local',True),field('kind','Tür','select',options={'ogrenci':'Öğrenci','veli':'Veli','ogretmen':'Öğretmen'}),field('place','Yer',required=True,maximum=120),field('state','Durum','select',options={'planlandi':'Planlandı','tamamlandi':'Tamamlandı','iptal':'İptal'})]),
    'rehber-etkinlik': dict(table='rehber_etkinlik',label='Sınıf rehberlik çalışmaları',owner='owner',private=True,fields=[field('title','Başlık',required=True,maximum=160),field('goal','Amaç ve plan','textarea',True,maximum=1500),field('day','Tarih','date',True),field('participants','Katılımcı sayısı','number',maximum=500),field('state','Durum','select',options={'planlandi':'Planlandı','tamamlandi':'Tamamlandı','iptal':'İptal'})]),
    'rehber-icerik': dict(table='rehber_icerik',label='Veliye paylaşılan rehberlik içerikleri',private=True,fields=[field('baslik','Başlık',required=True,maximum=200),field('ozet','Özet','textarea',maximum=1000),field('metin','İçerik','textarea',maximum=20000),field('etkinlik','Ev etkinliği','textarea',maximum=5000)]),
}
CHILDREN = {'ev-testi':[('lgs_optik_sonuc','sinav_id')], 'sonuc':[('lgs_deneme_ders','deneme_id')],
    'odev':[('odev_tamamlayanlar','odev_id'),('odev_sonuclari','odev_id')],
    'rehber-takip':[('rehber_not','case_id')], 'rehber-icerik':[('rehber_alici','icerik_id')]}
ALLOWED_TABLES={v['table'] for v in REGISTRY.values()}|{t for children in CHILDREN.values() for t,_ in children}|{'rehber_gorusme','akademik_puan_kayitlari','gelisim_puan','lig','lig_mac_tablo'}


def packed(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def fingerprint(value):
    return hashlib.sha256(packed(value).encode()).hexdigest()


def identity(con,table,row):
    return {c['name']:row[c['name']] for c in con.execute(f'PRAGMA table_info("{table}")') if c['pk']}


def fetch(con,table,key):
    if table not in ALLOWED_TABLES:raise ValueError('Desteklenmeyen kayıt türü.')
    where=' AND '.join('"'+k+'"=?' for k in key)
    row=con.execute(f'SELECT * FROM "{table}" WHERE {where}',tuple(key.values())).fetchone()
    return dict(row) if row else None


def owner_filter(spec,teacher):
    owner=spec.get('owner','ogretmen_id')
    if owner=='case_id':return 'case_id IN (SELECT id FROM rehber_takip WHERE owner=?)',(teacher['id'],)
    return f'"{owner}"=?',(teacher['ad_soyad'] if owner=='yayinlayan' else teacher['id'],)


def title(row):
    return str(row.get('ad') or row.get('baslik') or row.get('title') or row.get('kitap_adi') or row.get('topic') or row.get('not_metni') or row.get('body') or row.get('place') or row.get('ders') or 'Kayıt')[:160]


def bundle(con,kind,row):
    entries=[]
    def add(table,value):
        if value:
            value=dict(value);key=identity(con,table,value)
            if not any(e['table']==table and e['key']==key for e in entries):entries.append(dict(table=table,key=key,before=value))
    add(REGISTRY[kind]['table'],row)
    for table,fk in CHILDREN.get(kind,[]):
        for child in con.execute(f'SELECT * FROM "{table}" WHERE "{fk}"=?',(row['id'],)):add(table,child)
    if kind=='rehber-icerik':
        for child in con.execute('SELECT * FROM rehber_gorusme WHERE icerik_id=?',(row['id'],)):add('rehber_gorusme',child)
    if kind=='odev':
        for score in con.execute("SELECT * FROM akademik_puan_kayitlari WHERE kaynak_turu='odev_onayi' AND kaynak_id=?",(row['id'],)):
            add('akademik_puan_kayitlari',score)
            for table,key in [('gelisim_puan',{'ogrenci_id':score['ogrenci_id']}),('lig',{'sinif_id':score['sinif_id']}),('lig_mac_tablo',{'sinif_id':score['sinif_id']})]:add(table,fetch(con,table,key))
    return entries


def validated(spec,form):
    result={}
    for f in spec['fields']:
        value=form.get(f['name'],'').strip()
        if f['required'] and not value:raise ValueError(f["label"]+' boş bırakılamaz.')
        if f['kind']=='select':
            if value not in f['options']:raise ValueError('Listeden geçerli bir seçenek seçin.')
        elif f['kind']=='number':
            try:value=int(value)
            except ValueError:raise ValueError('Geçerli bir sayı girin.')
            if not 0<=value<=f['maximum']:raise ValueError('Sayı izin verilen aralıkta değil.')
        elif f['kind']=='date':
            try:value=date.fromisoformat(value).isoformat()
            except ValueError:raise ValueError('Geçerli bir tarih girin.')
        elif f['kind']=='datetime-local':
            try:parsed=datetime.fromisoformat(value)
            except ValueError:raise ValueError('Geçerli bir tarih ve saat girin.')
            if parsed.tzinfo:raise ValueError('Türkiye yerel saatini kullanın.')
            value=parsed.strftime('%Y-%m-%d %H:%M')
        elif f['kind']=='key':
            cleaned=''.join(value.upper().split())
            if not 1<=len(cleaned)<=90 or any(c not in 'ABCDE' for c in cleaned):raise ValueError('1–90 soruluk anahtarı yalnızca A–E harfleriyle girin.')
            value=json.dumps(list(cleaned))
        elif len(value)>f['maximum']:raise ValueError(f["label"]+' çok uzun.')
        result[f['name']]=value
    return result


def register(app,login_required):
    con=db._conn()
    con.execute('''CREATE TABLE IF NOT EXISTS ogretmen_kayit_yedek (
      id INTEGER PRIMARY KEY AUTOINCREMENT,owner INTEGER NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,
      action TEXT NOT NULL,created TEXT NOT NULL,payload TEXT NOT NULL,restored INTEGER NOT NULL DEFAULT 0)''')
    con.commit();con.close()

    def teacher():
        con=db._conn()
        try:row=con.execute('SELECT id,ad_soyad,yetki FROM ogretmenler WHERE id=?',(session.get('ogretmen_id'),)).fetchone()
        finally:con.close()
        if not row or row['yetki'] not in ('tam','rehber'):abort(403)
        return dict(row)

    def spec_for(kind,t):
        spec=REGISTRY.get(kind)
        if not spec or bool(spec.get('private'))!=(t['yetki']=='rehber'):abort(403)
        return spec

    def csrf():
        if 'records_csrf' not in session:session['records_csrf']=secrets.token_urlsafe(32)
        return session['records_csrf']

    def check():
        if not secrets.compare_digest(request.form.get('csrf',''),csrf()):abort(400)

    @app.context_processor
    def record_context():return dict(records_csrf=csrf)

    @app.route('/kayitlarim')
    @login_required
    def teacher_records():
        csrf()
        t=teacher();kind=request.args.get('tur','');q=request.args.get('q','').strip().casefold()
        choices={k:s for k,s in REGISTRY.items() if bool(s.get('private'))==(t['yetki']=='rehber')}
        if kind and kind not in choices:abort(403)
        rows=[];con=db._conn()
        try:
            for k,spec in choices.items():
                if kind and kind!=k:continue
                where,args=owner_filter(spec,t)
                for raw in con.execute(f'SELECT * FROM "{spec["table"]}" WHERE {where} ORDER BY id DESC',args):
                    r=dict(raw);oid=r.get('ogrenci_id') or r.get('student_id');sid=r.get('sinif_id') or r.get('class_id');student=None
                    if oid:student=con.execute('SELECT o.ad_soyad,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?',(oid,)).fetchone()
                    classroom=con.execute('SELECT sinif_adi FROM siniflar WHERE id=?',(sid,)).fetchone() if sid else None
                    context=' · '.join([*(student if student else []),*(classroom if classroom and not student else [])])
                    label=title(r)
                    if q and q not in (label+' '+context).casefold():continue
                    rows.append(dict(id=r['id'],kind=k,label=spec['label'],title=label,context=context,day=r.get('starts') or r.get('tarih') or r.get('day') or r.get('created') or r.get('hafta_basi') or r.get('zaman') or ''))
            backups=[dict(r) for r in con.execute('SELECT id,title,action,created,restored FROM ogretmen_kayit_yedek WHERE owner=? ORDER BY id DESC LIMIT 50',(t['id'],))]
        finally:con.close()
        rows.sort(key=lambda r:(r['day'],r['id']),reverse=True)
        page=max(1,request.args.get('sayfa',1,type=int));total=len(rows)
        return render_template('teacher_records.html',rows=rows[(page-1)*40:page*40],choices=choices,kind=kind,q=request.args.get('q',''),page=page,total=total,backups=backups)

    @app.route('/kayitlarim/<kind>/<int:rid>',methods=['GET','POST'])
    @login_required
    def teacher_record_edit(kind,rid):
        t=teacher();spec=spec_for(kind,t);where,args=owner_filter(spec,t);con=db._conn();error=''
        try:
            if request.method=='POST':check();con.execute('BEGIN IMMEDIATE')
            raw=con.execute(f'SELECT * FROM "{spec["table"]}" WHERE id=? AND {where}',(rid,*args)).fetchone()
            if not raw:abort(404)
            row=dict(raw);entries=bundle(con,kind,row);version=fingerprint(entries)
            if request.method=='POST':
                if not secrets.compare_digest(request.form.get('version',''),version):raise ValueError('Bu kayıt veya bağlı sonuçları değişti. Sayfayı yeniden açıp güncel bilgiyi kontrol edin.')
                action=request.form.get('action')
                if action=='delete':
                    if request.form.get('confirm')!='yes':raise ValueError('Silme onay kutusunu işaretleyin.')
                    if kind=='odev':
                        for e in entries:
                            if e['table']=='akademik_puan_kayitlari':
                                score=e['before']
                                con.execute('UPDATE gelisim_puan SET sandik_hakki=MAX(0,sandik_hakki-(CAST(xp/50 AS INTEGER)-CAST(MAX(0,xp-?)/50 AS INTEGER))),xp=MAX(0,xp-?) WHERE ogrenci_id=?',(score['xp'],score['xp'],score['ogrenci_id']))
                                week=(date.fromisoformat(score['tarih'][:10])-timedelta(days=date.fromisoformat(score['tarih'][:10]).weekday())).isoformat()
                                con.execute('UPDATE lig SET puan=MAX(0,puan-?) WHERE sinif_id=? AND hafta_basi=?',(score['lig_puani'],score['sinif_id'],week))
                                con.execute('UPDATE lig_mac_tablo SET puan=MAX(0,puan-?),ag=MAX(0,ag-1) WHERE sinif_id=?',(score['lig_puani'],score['sinif_id']))
                                con.execute('DELETE FROM akademik_puan_kayitlari WHERE id=?',(score['id'],))
                    if kind=='rehber-icerik':con.execute('UPDATE rehber_gorusme SET icerik_id=NULL WHERE icerik_id=?',(rid,))
                    for table,fk in CHILDREN.get(kind,[]):con.execute(f'DELETE FROM "{table}" WHERE "{fk}"=?',(rid,))
                    con.execute(f'DELETE FROM "{spec["table"]}" WHERE id=?',(rid,))
                elif action=='save' and not spec.get('native'):
                    values=validated(spec,request.form)
                    if kind=='ev-testi':
                        if row.get('kaynak')!='kamera' and values['tarih']!=row['tarih']:
                            from home_test_window import validate_schedule_date
                            values['tarih']=validate_schedule_date(values['tarih'])
                        answers=json.loads(values['cevaplar']);results=[e['before'] for e in entries if e['table']=='lgs_optik_sonuc']
                        if row.get('kaynak')=='kamera':
                            camera=con.execute('SELECT choices FROM kamera_sinav WHERE sinav_id=?',(rid,)).fetchone()
                            if camera and any(a not in camera['choices'] for a in answers):raise ValueError('Cevap anahtarı basılı optikteki seçeneklerle uyumlu olmalı.')
                            if len(answers)!=row['soru_sayisi']:raise ValueError('Basılmış kamera testinde soru sayısı değiştirilemez. Yeni bir test oluşturun.')
                        if results and len(answers)!=row['soru_sayisi']:raise ValueError('Öğrenci yanıtları varken soru sayısı değiştirilemez. Aynı sayıda sorunun cevaplarını düzeltebilirsiniz.')
                        values['soru_sayisi']=len(answers)
                        for result in results:
                            calc=optik.puan_hesapla(answers,json.loads(result['isaretler']))
                            con.execute('UPDATE lgs_optik_sonuc SET dogru=?,yanlis=?,bos=?,net=? WHERE id=?',(calc['dogru'],calc['yanlis'],calc['bos'],calc['net'],result['id']))
                    if kind=='haftalik' and values['kitap_adi']!=row['kitap_adi']:
                        values['kitap_okuma']='';values['kitap_sayfa']=0
                    if kind=='odev':values.update(ders_adi=values['ders'],tema_adi=values['baslik'])
                    if kind=='rehber-ajanda':
                        if not values['starts']<values['ends']:raise ValueError('Bitiş başlangıçtan sonra olmalı.')
                        if values['state']!='iptal' and con.execute("SELECT 1 FROM rehber_ajanda WHERE owner=? AND id!=? AND state!='iptal' AND starts<? AND ends>?",(t['id'],rid,values['ends'],values['starts'])).fetchone():raise ValueError('Bu saatlerde başka bir görüşme var.')
                    con.execute(f'UPDATE "{spec["table"]}" SET '+','.join('"'+k+'"=?' for k in values)+' WHERE id=?',(*values.values(),rid))
                else:abort(400)
                for entry in entries:entry['after']=fetch(con,entry['table'],entry['key'])
                con.execute('INSERT INTO ogretmen_kayit_yedek(owner,kind,title,action,created,payload) VALUES(?,?,?,?,?,?)',(t['id'],kind,title(row),'Silindi' if action=='delete' else 'Düzenlendi',datetime.now().strftime('%Y-%m-%d %H:%M'),packed(entries)))
                con.commit()
                flash('Kayıt silindi. Kayıtlarım ekranından geri alabilirsiniz.' if action=='delete' else 'Kayıt güncellendi.','success')
                return redirect(url_for('teacher_records',tur=kind))
        except (ValueError,sqlite3.IntegrityError) as exc:
            con.rollback();error=str(exc) if isinstance(exc,ValueError) else 'Kayıt ilişkileri nedeniyle işlem tamamlanamadı.'
        finally:con.close()
        values=dict(row)
        if kind=='ev-testi':values['cevaplar']=' '.join(json.loads(row['cevaplar']))
        if request.method=='POST':values.update(request.form)
        native=None
        if spec.get('native')=='sonuclar':native=url_for('sonuclar',ogrenci=row['ogrenci_id'],duzenle=rid)
        if spec.get('native')=='rehberlik_takip_dosya':native=url_for('rehberlik_takip_dosya',cid=rid)
        return render_template('teacher_record_edit.html',spec=spec,row=row,title=title(row),values=values,version=version,error=error,kind=kind,native=native,linked=len(entries)-1),(400 if error else 200)

    @app.route('/kayitlarim/geri-al/<int:bid>',methods=['POST'])
    @login_required
    def teacher_record_restore(bid):
        t=teacher();check();con=db._conn()
        try:
            con.execute('BEGIN IMMEDIATE');con.execute('PRAGMA defer_foreign_keys=ON')
            backup=con.execute('SELECT * FROM ogretmen_kayit_yedek WHERE id=? AND owner=?',(bid,t['id'])).fetchone()
            if not backup:abort(404)
            spec_for(backup['kind'],t)
            if backup['restored']:raise ValueError('Bu işlem zaten geri alındı.')
            entries=json.loads(backup['payload'])
            known={(e['table'],packed(e['key'])) for e in entries}
            if any((e['table'],packed(e['key'])) not in known for e in bundle(con,backup['kind'],entries[0]['before'])):
                raise ValueError('Bu kayda yeni bir sonuç veya alt kayıt eklenmiş. Güncel veriler korunuyor; geri alma yapılmadı.')
            for entry in entries:
                if fetch(con,entry['table'],entry['key'])!=entry['after']:raise ValueError('Kayıt üzerinde daha yeni bir işlem var. Önce onu geri alın; güncel veriler korunuyor.')
            if backup['kind']=='rehber-ajanda':
                old=entries[0]['before']
                if old['state']!='iptal' and con.execute("SELECT 1 FROM rehber_ajanda WHERE owner=? AND id!=? AND state!='iptal' AND starts<? AND ends>?",(t['id'],old['id'],old['ends'],old['starts'])).fetchone():
                    raise ValueError('Eski görüşme saati artık başka bir görüşmeyle çakışıyor. Geri alma yapılmadı.')
            for entry in entries:
                table=entry['table'];before=entry['before'];key=entry['key']
                if entry['after'] is None:
                    con.execute(f'INSERT INTO "{table}" ('+','.join('"'+k+'"' for k in before)+') VALUES ('+','.join('?' for _ in before)+')',tuple(before.values()))
                else:
                    con.execute(f'UPDATE "{table}" SET '+','.join('"'+k+'"=?' for k in before)+' WHERE '+' AND '.join('"'+k+'"=?' for k in key),(*before.values(),*key.values()))
            con.execute('UPDATE ogretmen_kayit_yedek SET restored=1 WHERE id=?',(bid,));con.commit()
            flash('Kayıt ve bağlı sonuçları geri yüklendi.','success')
        except (ValueError,sqlite3.IntegrityError) as exc:
            con.rollback();flash(str(exc) if isinstance(exc,ValueError) else 'Aynı yerde yeni bir kayıt var. Geri yükleme yapılmadı.','warning')
        finally:con.close()
        return redirect(url_for('teacher_records'))
