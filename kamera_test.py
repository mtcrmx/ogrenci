"""Owner-scoped paper test preparation and camera ingestion into existing analysis."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import secrets
import sqlite3

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from pypdf import PdfReader, PdfWriter

import database as db
import lgs_optik as optik
import kamera_media as media

bp=Blueprint('kamera_test', __name__, url_prefix='/yaprak-kamera')


def connect():
    con=db._conn();optik._init(con)
    con.executescript('''
    CREATE TABLE IF NOT EXISTS kamera_taslak (
      id TEXT PRIMARY KEY, owner INTEGER NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS kamera_sinav (
      sinav_id INTEGER PRIMARY KEY, choices TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS kamera_form (
      token TEXT PRIMARY KEY, sinav_id INTEGER NOT NULL, ogrenci_id INTEGER NOT NULL,
      count INTEGER NOT NULL, choices TEXT NOT NULL,
      UNIQUE(sinav_id,ogrenci_id,count,choices));
    CREATE TABLE IF NOT EXISTS kamera_islem (
      id INTEGER PRIMARY KEY, sinav_id INTEGER NOT NULL, ogrenci_id INTEGER NOT NULL,
      owner INTEGER NOT NULL, action TEXT NOT NULL, before_json TEXT, after_json TEXT,
      created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    ''')
    return con


def register(app, accessible):
    bp.accessible=accessible
    app.register_blueprint(bp)
    @app.context_processor
    def home_key_upload_context():
        return {'home_key_csrf':csrf() if session.get('ogretmen_id') else ''}


def csrf():
    if not session.get('kamera_csrf'): session['kamera_csrf']=secrets.token_urlsafe(32)
    return session['kamera_csrf']


@bp.before_request
def protect():
    teacher=session.get('ogretmen_id')
    if not teacher: return redirect(url_for('login'))
    if db.ogretmen_yetki_al(teacher)!='tam': abort(403)
    request.max_content_length=65*1024*1024
    if request.method=='POST' and not secrets.compare_digest(request.form.get('csrf',''),csrf()):
        abort(400,'Oturum doğrulanamadı. Sayfayı yenileyin.')


@bp.after_request
def private_response(response):
    response.headers['Cache-Control']='private, no-store'
    return response


@bp.errorhandler(ValueError)
def bad_input(exc):
    if request.path.endswith(('/tara','/telefonda-oku','/kaydet','/anahtar-oku')):
        return jsonify(error=str(exc)),400
    flash(str(exc),'error')
    return redirect(url_for('.index'))


def roster(sid=None):
    con=db._conn()
    rows=[dict(r) for r in con.execute('SELECT o.id,o.ad_soyad,o.ogr_no,o.sinif_id,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id ORDER BY s.sinif_adi,o.ad_soyad')]
    con.close()
    return [r for r in rows if (sid is None or r['sinif_id']==sid) and bp.accessible(session['ogretmen_id'],r['id'])]


def exam_owned(eid):
    con=connect()
    row=con.execute('SELECT e.*,k.choices FROM lgs_optik_sinav e JOIN kamera_sinav k ON k.sinav_id=e.id WHERE e.id=? AND e.ogretmen_id=?',(eid,session['ogretmen_id'])).fetchone()
    con.close()
    if not row: abort(404)
    exam=dict(row);exam['cevaplar']=json.loads(exam['cevaplar'])
    return exam


def read_upload(upload):
    if not upload or not upload.filename: raise ValueError('Dosya seçin.')
    data=upload.read(20*1024*1024+1)
    if not data or len(data)>20*1024*1024: raise ValueError('Her dosya 20 MB veya daha küçük olmalı.')
    return data,Path(upload.filename).suffix.lower()


@bp.post('/anahtar-oku')
def read_home_key():
    count=request.form.get('count',type=int) or request.form.get('soru_sayisi',type=int)
    if not count or not 1<=count<=90:
        raise ValueError('Önce 1–90 arasında soru sayısı girin.')
    data,suffix=read_upload(request.files.get('key') or request.files.get('anahtar_dosya'))
    try:
        text,ocr=media.extract_key_text(data,suffix)
        answers,warnings=media.parse_key(text,count,'ABCDE')
    except ValueError:
        raise
    except Exception:
        current_app.logger.exception('Home answer key extraction failed')
        return jsonify(error='Cevap anahtarı okunamadı. Daha net bir PDF veya görsel deneyin. Girdiğiniz test bilgileri korunuyor.'),422
    return jsonify(answers=answers,warnings=warnings,ocr=ocr,read=sum(bool(a) for a in answers))


@bp.get('')
def index():
    con=connect()
    exams=[dict(r) for r in con.execute("SELECT e.*,COUNT(r.id) AS scanned FROM kamera_sinav k JOIN lgs_optik_sinav e ON e.id=k.sinav_id LEFT JOIN lgs_optik_sonuc r ON r.sinav_id=e.id WHERE e.ogretmen_id=? AND (e.silindi_at IS NULL OR e.silindi_at='') GROUP BY e.id ORDER BY e.id DESC",(session['ogretmen_id'],))]
    con.close()
    classes={r['sinif_id']:r['sinif_adi'] for r in roster()}
    return render_template('kamera_test.html',mode='index',exams=exams,classes=classes,csrf=csrf())


@bp.post('/hazirla')
def prepare():
    count=request.form.get('count',type=int) or request.form.get('soru_sayisi',type=int)
    choices=request.form.get('choices') or request.form.get('secenekler') or 'ABCD'
    sid=request.form.get('class_id',type=int) or request.form.get('sinif_id',type=int)
    name=(request.form.get('name') or request.form.get('ad') or '').strip()
    course=(request.form.get('course') or request.form.get('ders') or '').strip()[:40]
    goturme=request.form.get('yanlis_goturme',type=int)
    if goturme not in (0,3,4): goturme=3
    if not count or not 1<=count<=90 or choices not in ('ABCD','ABCDE'): raise ValueError('1-90 soru ve 4 veya 5 seçenek seçin.')
    if not name or len(name)>80: raise ValueError('Test adı 1-80 karakter olmalı.')
    if not sid or not roster(sid): abort(403)
    uploads=request.files.getlist('questions') or request.files.getlist('sorular')
    if not 1<=len(uploads)<=20: raise ValueError('1-20 dosya seçin.')
    try:
        pdf,pages=media.merge_documents([read_upload(u) for u in uploads])
    except ValueError: raise
    except Exception as exc:
        current_app.logger.warning('Question conversion failed: %s',type(exc).__name__)
        raise ValueError('Soru dosyası açılamadı. Dosya biçimini kontrol edip tekrar yükleyin.') from exc
    answers=['']*count;warnings=[];text='';key_pdf=None
    key=request.files.get('key') or request.files.get('anahtar_dosya')
    if key and key.filename:
        data,suffix=read_upload(key)
        try:
            text,ocr=media.extract_key_text(data,suffix)
            answers,warnings=media.parse_key(text,count,choices)
            if ocr: warnings.insert(0,'Görselden okunan cevapları belgeyle karşılaştırın. Belirsiz cevaplar boş bırakıldı.')
            try: key_pdf=media.convert_document(data,suffix)
            except ValueError: warnings.append('Belge önizlemesi oluşturulamadı. Orijinal belgenizle cevapları karşılaştırın.')
        except ValueError as exc:
            warnings=[str(exc)]
        except Exception as exc:
            current_app.logger.warning('Answer extraction failed: %s',type(exc).__name__)
            warnings=['Cevap anahtarı okuma servisi bu belgeyi işleyemedi. Daha net bir PDF/görsel deneyin veya belgeyi destek için paylaşın.']
    ident=secrets.token_hex(16)
    (optik.klasor()/(ident+'.pdf')).write_bytes(pdf)
    if key_pdf: (optik.klasor()/(ident+'-key.pdf')).write_bytes(key_pdf)
    payload=dict(name=name,count=count,choices=choices,class_id=sid,course=course,yanlis_goturme=goturme,
                 answers=answers,warnings=warnings,text=text[:20000],pages=pages,key_pdf=bool(key_pdf),
                 key_pages=min(len(PdfReader(BytesIO(key_pdf)).pages),5) if key_pdf else 0)
    con=connect();con.execute('INSERT INTO kamera_taslak(id,owner,data) VALUES(?,?,?)',(ident,session['ogretmen_id'],json.dumps(payload)));con.commit();con.close()
    return redirect(url_for('.draft',ident=ident))


def draft_owned(ident):
    con=connect();row=con.execute('SELECT * FROM kamera_taslak WHERE id=? AND owner=?',(ident,session['ogretmen_id'])).fetchone();con.close()
    if not row: abort(404)
    return json.loads(row['data'])


@bp.route('/taslak/<ident>',methods=['GET','POST'])
def draft(ident):
    data=draft_owned(ident);error=''
    if request.method=='POST':
        answers=[request.form.get('q'+str(i),'') for i in range(1,data['count']+1)]
        if any(a not in list(data['choices']) for a in answers) or request.form.get('confirmed')!='yes':
            error='Her sorunun cevabını seçin ve belgeyle karşılaştırdığınızı onaylayın.';data['answers']=answers
        elif not roster(data['class_id']): abort(403)
        else:
            con=connect()
            try:
                con.execute('BEGIN IMMEDIATE')
                if not con.execute('SELECT 1 FROM kamera_taslak WHERE id=? AND owner=?',(ident,session['ogretmen_id'])).fetchone(): abort(409)
                cur=con.execute('INSERT INTO lgs_optik_sinav(ad,tarih,pdf_dosya,cevaplar,soru_sayisi,ogretmen_id,olusturma,tur,ders,sinif_id,yanlis_goturme,secenekler,kaynak) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                (data['name'],date.today().isoformat(),ident+'.pdf',json.dumps(answers),data['count'],session['ogretmen_id'],datetime.now().strftime('%Y-%m-%d %H:%M'),'yaprak',data['course'],data['class_id'],int(data.get('yanlis_goturme',3)),data['choices'],'kamera'))
                eid=cur.lastrowid
                con.execute('INSERT INTO kamera_sinav(sinav_id,choices) VALUES(?,?)',(eid,data['choices']))
                con.execute('DELETE FROM kamera_taslak WHERE id=?',(ident,));con.commit()
            finally: con.close()
            (optik.klasor()/(ident+'-key.pdf')).unlink(missing_ok=True)
            flash('Cevap anahtarı onaylandı. Sınıfın testlerini yazdırabilirsiniz.','success')
            return redirect(url_for('.detail',eid=eid))
    return render_template('kamera_test.html',mode='draft',draft=data,ident=ident,error=error,csrf=csrf())


@bp.get('/taslak/<ident>/belge/<kind>')
def draft_file(ident,kind):
    data=draft_owned(ident)
    if kind not in ('questions','key') or (kind=='key' and not data['key_pdf']): abort(404)
    return send_file(optik.klasor()/(ident+('-key' if kind=='key' else '')+'.pdf'),mimetype='application/pdf')


@bp.get('/taslak/<ident>/onizleme/<int:page>')
def key_preview(ident,page):
    data=draft_owned(ident)
    if not data['key_pdf'] or not 1<=page<=data.get('key_pages',1): abort(404)
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(str(optik.klasor()/(ident+'-key.pdf'))) as pdf:
        if page>len(pdf): abort(404)
        bitmap=pdf[page-1].render(scale=1.5)
        image=bitmap.to_pil();out=BytesIO();image.save(out,format='PNG');bitmap.close()
    out.seek(0)
    return send_file(out,mimetype='image/png')


@bp.get('/taslak/<ident>/sorular')
def questions_view(ident):
    from question_viewer import view
    data=draft_owned(ident)
    return view(optik.klasor()/(ident+'.pdf'),data['name'],lambda page:url_for('.question_page',ident=ident,page=page))


@bp.get('/taslak/<ident>/soru-sayfasi/<int:page>')
def question_page(ident,page):
    from question_viewer import page_image
    draft_owned(ident)
    return page_image(optik.klasor()/(ident+'.pdf'),page)


@bp.get('/<int:eid>')
def detail(eid):
    exam=exam_owned(eid);people=roster(exam['sinif_id'])
    results={r['ogrenci_id']:r for r in optik.sinav_sonuclari(eid)}
    for result in results.values(): result['version']=result_version(result)
    return render_template('kamera_test.html',mode='detail',exam=exam,people=people,results=results,csrf=csrf())


@bp.get('/<int:eid>/yazdir')
def print_exam(eid):
    exam=exam_owned(eid);people=roster(exam['sinif_id'])
    oid=request.args.get('student',type=int)
    if oid is not None: people=[p for p in people if p['id']==oid]
    if not people: abort(404)
    source=optik.pdf_yolu(exam)
    if not source: abort(404)
    if request.args.get('only')=='optik': abort(410)
    writer=PdfWriter()
    for person in people:
        writer.append(PdfReader(source),import_outline=False)
    out=BytesIO();writer.write(out);out.seek(0)
    return send_file(out,mimetype='application/pdf',download_name=f'yaprak-test-{eid}.pdf')


def fingerprint(value): return sha256(json.dumps(value,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
def result_version(row): return fingerprint([row[k] for k in ('id','isaretler','dogru','yanlis','bos','net','zaman')])
@bp.post('/<int:eid>/tara')
@bp.post('/<int:eid>/telefonda-oku')
@bp.post('/<int:eid>/kaydet')
def optical_removed(eid):
    exam_owned(eid)
    return jsonify(error='Optikten okuma özelliği kaldırıldı. Mevcut sonuçlarınız korunuyor.'),410


@bp.post('/taslak/<ident>/vazgec')
def discard_draft(ident):
    draft_owned(ident)
    con=connect();con.execute('DELETE FROM kamera_taslak WHERE id=? AND owner=?',(ident,session['ogretmen_id']));con.commit();con.close()
    for suffix in ('.pdf','-key.pdf'): (optik.klasor()/(ident+suffix)).unlink(missing_ok=True)
    flash('Taslak iptal edildi. Öğrenci testi oluşturulmadı.','success')
    return redirect(url_for('.index'))


@bp.post('/<int:eid>/sil/<int:oid>')
def delete_result(eid,oid):
    exam=exam_owned(eid)
    if oid not in {r['id'] for r in roster(exam['sinif_id'])}: abort(403)
    if request.form.get('confirm')!='yes': abort(400)
    con=connect()
    try:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM lgs_optik_sonuc WHERE sinav_id=? AND ogrenci_id=?',(eid,oid)).fetchone()
        if not row or result_version(dict(row))!=request.form.get('version'): abort(409)
        con.execute('INSERT INTO kamera_islem(sinav_id,ogrenci_id,owner,action,before_json) VALUES(?,?,?,?,?)',(eid,oid,session['ogretmen_id'],'delete',json.dumps(dict(row))))
        con.execute('DELETE FROM lgs_optik_sonuc WHERE sinav_id=? AND ogrenci_id=?',(eid,oid));con.commit()
    finally: con.close()
    flash('Öğrenci sonucu silindi. ','success')
    return redirect(url_for('.detail',eid=eid))


from batch_optik import register as register_batch_optik
register_batch_optik(bp)
