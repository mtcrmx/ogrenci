"""Review-first PDF batch import. Camera capture remains disabled."""
import json
import secrets
import time
from io import BytesIO
from datetime import datetime
from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
import pypdfium2 as pdfium
import lgs_optik as optik
import kamera_media as media
from question_viewer import PDF_LOCK


def connection():
    import kamera_test as kt
    con=kt.connect()
    con.executescript('''
      CREATE TABLE IF NOT EXISTS pdf_optik_batch(id TEXT PRIMARY KEY,owner INTEGER,eid INTEGER,
        pdf BLOB,pages INTEGER,key_hash TEXT,expires REAL,saved INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS pdf_optik_page(batch_id TEXT,no INTEGER,oid INTEGER,data TEXT,preview BLOB,
        PRIMARY KEY(batch_id,no),UNIQUE(batch_id,oid));
    ''')
    return con


def owned(bid):
    import kamera_test as kt
    con=connection()
    row=con.execute('SELECT * FROM pdf_optik_batch WHERE id=? AND owner=?',(bid,session['ogretmen_id'])).fetchone()
    con.close()
    if not row:abort(404)
    if row['expires']<time.time():abort(410,description='Yüklemenin süresi doldu. PDF dosyasını tekrar yükleyin.')
    return dict(row),kt.exam_owned(row['eid'])


def render_page(raw,no):
    with PDF_LOCK,pdfium.PdfDocument(raw) as doc:
        page=doc[no-1]
        try:
            width,height=page.get_size()
            if width<=0 or height<=0:raise ValueError('Geçersiz sayfa boyutu.')
            bitmap=page.render(scale=min(3,2500/max(width,height)))
            try:
                image=bitmap.to_pil();out=BytesIO();image.save(out,format='JPEG',quality=92)
                return out.getvalue()
            finally:bitmap.close()
        finally:page.close()


def register(bp):
    @bp.get('/<int:eid>/pdf-optik/formlar')
    def batch_forms(eid):
        import kamera_test as kt
        from pypdf import PdfWriter,PdfReader
        from flask import send_file
        exam=kt.exam_owned(eid);people=kt.roster(exam['sinif_id'])
        if not people:abort(404)
        con=connection();writer=PdfWriter()
        try:
            for person in people:
                con.execute('INSERT OR IGNORE INTO kamera_form VALUES(?,?,?,?,?)',(secrets.token_urlsafe(24),eid,person['id'],exam['soru_sayisi'],exam['choices']))
                token=con.execute('SELECT token FROM kamera_form WHERE sinav_id=? AND ogrenci_id=? AND count=? AND choices=?',(eid,person['id'],exam['soru_sayisi'],exam['choices'])).fetchone()[0]
                writer.append(PdfReader(BytesIO(media.form_pdf(exam,person,token,exam['choices']))),import_outline=False)
            con.commit()
        finally:con.close()
        out=BytesIO();writer.write(out);out.seek(0)
        return send_file(out,mimetype='application/pdf',download_name=f'ogrenci-optikleri-{eid}.pdf')

    @bp.post('/<int:eid>/pdf-optik/yukle')
    def batch_upload(eid):
        import kamera_test as kt
        exam=kt.exam_owned(eid)
        data,suffix=kt.read_upload(request.files.get('pdf'))
        if suffix!='.pdf' or not data.startswith(b'%PDF-'):raise ValueError('Taranmış optikleri PDF olarak yükleyin.')
        try:
            with PDF_LOCK,pdfium.PdfDocument(data) as doc:
                count=len(doc)
                if not 1<=count<=60:raise ValueError('Bir dosyada 1–60 sayfa yükleyin.')
        except ValueError:raise
        except Exception:raise ValueError('PDF açılamadı. Şifresiz bir PDF yükleyin.')
        bid=secrets.token_hex(16);con=connection()
        try:
            con.execute('DELETE FROM pdf_optik_page WHERE batch_id IN (SELECT id FROM pdf_optik_batch WHERE expires<?)',(time.time(),))
            con.execute('DELETE FROM pdf_optik_batch WHERE expires<?',(time.time(),))
            con.execute('INSERT INTO pdf_optik_batch(id,owner,eid,pdf,pages,key_hash,expires) VALUES(?,?,?,?,?,?,?)',(bid,session['ogretmen_id'],eid,data,count,kt.fingerprint(exam['cevaplar']),time.time()+86400))
            con.commit()
        finally:con.close()
        return redirect(url_for('.batch_review',bid=bid))

    @bp.get('/pdf-optik/<bid>')
    def batch_review(bid):
        import kamera_test as kt
        batch,exam=owned(bid);con=connection()
        try:rows=[dict(r) for r in con.execute('SELECT no,data FROM pdf_optik_page WHERE batch_id=? ORDER BY no',(bid,))]
        finally:con.close()
        done={r['no'] for r in rows}
        for row in rows:row.update(json.loads(row.pop('data')))
        return render_template('pdf_optik_batch.html',batch=batch,exam=exam,rows=rows,pending=[n for n in range(1,batch['pages']+1) if n not in done],csrf=kt.csrf())

    @bp.post('/pdf-optik/<bid>/oku/<int:no>')
    def batch_page_read(bid,no):
        import kamera_test as kt
        batch,exam=owned(bid)
        if batch['saved'] or not 1<=no<=batch['pages']:abort(409)
        if kt.fingerprint(exam['cevaplar'])!=batch['key_hash']:abort(409)
        con=connection()
        try:
            if con.execute('SELECT 1 FROM pdf_optik_page WHERE batch_id=? AND no=?',(bid,no)).fetchone():return jsonify(ok=True)
        finally:con.close()
        preview=b'';oid=None
        try:
            preview=render_page(batch['pdf'],no)
            result=media.read_form(preview,exam['soru_sayisi'],exam['choices'])
            con=connection()
            try:form=con.execute('SELECT * FROM kamera_form WHERE token=? AND sinav_id=?',(result['token'],exam['id'])).fetchone()
            finally:con.close()
            if not form or form['count']!=exam['soru_sayisi'] or form['choices']!=exam['choices']:raise ValueError('Bu sayfa seçili testin güncel optiği değil.')
            person=next((p for p in kt.roster(exam['sinif_id']) if p['id']==form['ogrenci_id']),None)
            if not person:raise ValueError('Öğrenci bu sınıfta değil veya erişim yetkiniz yok.')
            oid=person['id'];old=optik.sonuc_getir(exam['id'],oid)
            info=dict(name=person['ad_soyad'],number=person['ogr_no'],answers=''.join(a or '-' for a in result['answers']),uncertain=result['uncertain'],existing=bool(old),before=kt.fingerprint(old),error='')
            preview=result['preview']
        except ValueError as exc:info=dict(error=str(exc))
        except Exception:
            from flask import current_app
            current_app.logger.exception('Batch optical page read failed')
            info=dict(error='Sayfa okunamadı. Net, 200–300 dpi tarama ile yeniden deneyin.')
        con=connection()
        try:
            con.execute('BEGIN IMMEDIATE')
            if oid and con.execute('SELECT 1 FROM pdf_optik_page WHERE batch_id=? AND oid=?',(bid,oid)).fetchone():
                info=dict(error='Bu öğrenci PDF içinde tekrar ediyor. Yalnız ilk okunan sayfa kullanılabilir.');oid=None
            con.execute('INSERT OR IGNORE INTO pdf_optik_page VALUES(?,?,?,?,?)',(bid,no,oid,json.dumps(info),preview))
            con.commit()
        finally:con.close()
        return jsonify(ok=True)

    @bp.get('/pdf-optik/<bid>/onizleme/<int:no>')
    def batch_preview(bid,no):
        from flask import send_file
        owned(bid);con=connection()
        try:row=con.execute('SELECT preview FROM pdf_optik_page WHERE batch_id=? AND no=?',(bid,no)).fetchone()
        finally:con.close()
        if not row or not row[0]:abort(404)
        return send_file(BytesIO(row[0]),mimetype='image/jpeg')

    @bp.post('/pdf-optik/<bid>/kaydet')
    def batch_save(bid):
        import kamera_test as kt
        batch,exam=owned(bid)
        selected=request.form.getlist('select',type=int)
        if not selected or len(selected)!=len(set(selected)):abort(400,description='Kaydedilecek öğrencileri seçin.')
        allowed={p['id'] for p in kt.roster(exam['sinif_id'])};con=connection()
        try:
            con.execute('BEGIN IMMEDIATE')
            fresh=con.execute('SELECT saved FROM pdf_optik_batch WHERE id=?',(bid,)).fetchone()
            if fresh['saved']:abort(409,description='Bu yükleme zaten kaydedildi.')
            current=con.execute('SELECT cevaplar FROM lgs_optik_sinav WHERE id=? AND ogretmen_id=?',(exam['id'],session['ogretmen_id'])).fetchone()
            if not current or kt.fingerprint(json.loads(current[0]))!=batch['key_hash']:abort(409,description='Cevap anahtarı değişti. PDF dosyasını yeniden yükleyin.')
            if con.execute('SELECT COUNT(*) FROM pdf_optik_page WHERE batch_id=?',(bid,)).fetchone()[0]!=batch['pages']:abort(409)
            for no in selected:
                row=con.execute('SELECT * FROM pdf_optik_page WHERE batch_id=? AND no=?',(bid,no)).fetchone()
                if not row or row['oid'] not in allowed:abort(400)
                info=json.loads(row['data'])
                if info.get('error') or request.form.get(f'confirm_{no}')!='yes':abort(400,description='Seçtiğiniz her öğrencinin cevaplarını kontrol edip onaylayın.')
                text=''.join(request.form.get(f'answers_{no}','').upper().split())
                if len(text)!=exam['soru_sayisi'] or any(a not in exam['choices']+'-' for a in text):abort(400,description='Cevap sayısı veya seçenekler hatalı. Boş cevap için - kullanın.')
                answers=['' if a=='-' else a for a in text]
                old=con.execute('SELECT * FROM lgs_optik_sonuc WHERE sinav_id=? AND ogrenci_id=?',(exam['id'],row['oid'])).fetchone()
                before=dict(old) if old else None
                if before:before['isaretler']=json.loads(before['isaretler'])
                if kt.fingerprint(before)!=info['before']:abort(409,description='Öğrencinin sonucu değişti. PDF dosyasını yeniden yükleyin.')
                if old and request.form.get(f'replace_{no}')!='yes':abort(409,description='Mevcut sonucu değiştirmek için ayrıca onay verin.')
                score=optik.puan_hesapla(json.loads(current[0]),answers)
                con.execute('''INSERT INTO lgs_optik_sonuc(sinav_id,ogrenci_id,isaretler,dogru,yanlis,bos,net,zaman) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(sinav_id,ogrenci_id) DO UPDATE SET isaretler=excluded.isaretler,dogru=excluded.dogru,yanlis=excluded.yanlis,bos=excluded.bos,net=excluded.net,zaman=excluded.zaman''',(exam['id'],row['oid'],json.dumps(answers),score['dogru'],score['yanlis'],score['bos'],score['net'],datetime.now().isoformat(timespec='seconds')))
                con.execute('INSERT INTO kamera_islem(sinav_id,ogrenci_id,owner,action,before_json,after_json) VALUES(?,?,?,?,?,?)',(exam['id'],row['oid'],session['ogretmen_id'],'pdf-replace' if old else 'pdf-import',json.dumps(before),json.dumps(answers)))
            con.execute('UPDATE pdf_optik_batch SET saved=1,pdf=NULL WHERE id=?',(bid,));con.commit()
        finally:con.close()
        flash(f'{len(selected)} öğrencinin sonucu kaydedildi.','success')
        return redirect(url_for('.detail',eid=exam['id']))
