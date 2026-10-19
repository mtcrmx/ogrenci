"""Review-first PDF batch import. Camera capture remains disabled."""
import json
import secrets
import time
from io import BytesIO
from datetime import datetime
from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
import pypdfium2 as pdfium
import database as db
import lgs_optik as optik
import kamera_media as media
from question_viewer import PDF_LOCK

OPTIK_AZAMI_SAYFA = 60
_SON_TEMIZLIK_ZAMANI = 0.0


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


def cleanup_expired_batches(force: bool = False):
    global _SON_TEMIZLIK_ZAMANI
    simdi = time.time()
    if not force and simdi - _SON_TEMIZLIK_ZAMANI < 86400:
        return
    _SON_TEMIZLIK_ZAMANI = simdi
    con = connection()
    try:
        con.execute('DELETE FROM pdf_optik_page WHERE batch_id IN (SELECT id FROM pdf_optik_batch WHERE expires<?)', (simdi,))
        con.execute('DELETE FROM pdf_optik_batch WHERE expires<?', (simdi,))
        con.commit()
    finally:
        con.close()


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


def _batch_durumu(bid: str, batch: dict, exam: dict):
    import kamera_test as kt
    con = connection()
    try:
        raw_rows = [dict(r) for r in con.execute('SELECT no, oid, data FROM pdf_optik_page WHERE batch_id=? ORDER BY no', (bid,))]
    finally:
        con.close()
    done = {r['no'] for r in raw_rows}
    rows = []
    gorulen_oid = set()
    goturme = exam.get('yanlis_goturme', 3)
    for r in raw_rows:
        info = json.loads(r.pop('data'))
        r.update(info)
        if r.get('oid'):
            gorulen_oid.add(int(r['oid']))
        ans = r.get('answers') or ''
        uncertain = r.get('uncertain') or []
        if r.get('oid') and not r.get('error') and '?' not in ans and not uncertain:
            isaretler = ['' if c == '-' else c for c in ans]
            puan = optik.puan_hesapla(exam['cevaplar'], isaretler, goturme)
            r['dogru'] = puan['dogru']
            r['yanlis'] = puan['yanlis']
            r['bos'] = puan['bos']
            r['net'] = puan['net']
            r['hazir'] = True
        else:
            r['hazir'] = False
        rows.append(r)
    people = kt.roster(exam['sinif_id'])
    eksik_ogrenciler = [
        {'id': p['id'], 'ad_soyad': p['ad_soyad'], 'ogr_no': p['ogr_no']}
        for p in people
        if p['id'] not in gorulen_oid
    ]
    pending = [n for n in range(1, batch['pages'] + 1) if n not in done]
    return rows, pending, eksik_ogrenciler, people


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
        from pypdf import PdfWriter, PdfReader
        exam=kt.exam_owned(eid)
        data,suffix=kt.read_upload(request.files.get('pdf'))
        if suffix!='.pdf' or not data.startswith(b'%PDF-'):raise ValueError('Taranmış optikleri PDF olarak yükleyin.')
        try:
            with PDF_LOCK,pdfium.PdfDocument(data) as doc:
                count=len(doc)
                if not 1<=count<=OPTIK_AZAMI_SAYFA:raise ValueError(f'Bir dosyada 1–{OPTIK_AZAMI_SAYFA} sayfa yükleyin.')
        except ValueError:raise
        except Exception:raise ValueError('PDF açılamadı. Şifresiz bir PDF yükleyin.')
        cleanup_expired_batches()
        existing_bid = (request.form.get('bid') or '').strip()
        con=connection()
        try:
            if existing_bid:
                old_batch = con.execute('SELECT * FROM pdf_optik_batch WHERE id=? AND owner=? AND eid=? AND saved=0', (existing_bid, session['ogretmen_id'], eid)).fetchone()
                if old_batch and old_batch['pdf']:
                    writer = PdfWriter()
                    writer.append(PdfReader(BytesIO(old_batch['pdf'])), import_outline=False)
                    writer.append(PdfReader(BytesIO(data)), import_outline=False)
                    merged = BytesIO()
                    writer.write(merged)
                    new_pages = int(old_batch['pages']) + count
                    con.execute('UPDATE pdf_optik_batch SET pdf=?, pages=?, expires=? WHERE id=?', (merged.getvalue(), new_pages, time.time()+86400, existing_bid))
                    con.commit()
                    bid = existing_bid
                    count = new_pages
                else:
                    existing_bid = ''
            if not existing_bid:
                bid=secrets.token_hex(16)
                con.execute('INSERT INTO pdf_optik_batch(id,owner,eid,pdf,pages,key_hash,expires) VALUES(?,?,?,?,?,?,?)',(bid,session['ogretmen_id'],eid,data,count,kt.fingerprint(exam['cevaplar']),time.time()+86400))
                con.commit()
        finally:con.close()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
            return jsonify(ok=True, bid=bid, pages=count, review_url=url_for('.batch_review', bid=bid))
        return redirect(url_for('.batch_review',bid=bid))

    @bp.get('/pdf-optik/<bid>')
    def batch_review(bid):
        import kamera_test as kt
        batch,exam=owned(bid)
        rows, pending, eksik_ogrenciler, people = _batch_durumu(bid, batch, exam)
        return render_template('pdf_optik_batch.html',batch=batch,exam=exam,rows=rows,pending=pending,eksik_ogrenciler=eksik_ogrenciler,people=people,csrf=kt.csrf())

    @bp.get('/pdf-optik/<bid>/satirlar')
    def batch_rows_json(bid):
        batch, exam = owned(bid)
        rows, pending, eksik_ogrenciler, people = _batch_durumu(bid, batch, exam)
        return jsonify(
            ok=True,
            bid=bid,
            eid=exam['id'],
            pages=batch['pages'],
            pending=pending,
            rows=rows,
            eksik_ogrenciler=eksik_ogrenciler,
            sinif_ogrencileri=[{'id': p['id'], 'ad_soyad': p['ad_soyad'], 'ogr_no': p['ogr_no']} for p in people],
        )

    @bp.post('/pdf-optik/<bid>/ata/<int:no>')
    def batch_assign_student(bid, no):
        import kamera_test as kt
        batch, exam = owned(bid)
        if batch['saved'] or not 1 <= no <= batch['pages']:
            abort(409)
        oid = request.form.get('oid', type=int) or (request.json.get('oid') if request.is_json else None)
        if not oid:
            abort(400, description='Öğrenci seçin.')
        person = next((p for p in kt.roster(exam['sinif_id']) if p['id'] == int(oid)), None)
        if not person:
            abort(403, description='Öğrenci bu sınıfta değil.')
        con = connection()
        try:
            con.execute('BEGIN IMMEDIATE')
            dup = con.execute('SELECT no FROM pdf_optik_page WHERE batch_id=? AND oid=? AND no!=?', (bid, int(oid), no)).fetchone()
            if dup:
                abort(409, description=f'Bu öğrenci {dup["no"]}. sayfada zaten atanmış.')
            row = con.execute('SELECT * FROM pdf_optik_page WHERE batch_id=? AND no=?', (bid, no)).fetchone()
            if not row:
                abort(404)
            info = json.loads(row['data'])
            old = optik.sonuc_getir(exam['id'], int(oid))
            answers = info.get('answers') or ('-' * exam['soru_sayisi'])
            info.update(
                name=person['ad_soyad'],
                number=person['ogr_no'],
                answers=answers,
                uncertain=info.get('uncertain', []),
                existing=bool(old),
                before=kt.fingerprint(old),
                error='',
            )
            con.execute('UPDATE pdf_optik_page SET oid=?, data=? WHERE batch_id=? AND no=?', (int(oid), json.dumps(info), bid, no))
            con.commit()
        finally:
            con.close()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.args.get('format') == 'json':
            return jsonify(ok=True, no=no, oid=int(oid), name=person['ad_soyad'], number=person['ogr_no'])
        return redirect(url_for('.batch_review', bid=bid))

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
            dup = con.execute('SELECT no FROM pdf_optik_page WHERE batch_id=? AND oid=?',(bid,oid)).fetchone() if oid else None
            if dup:
                info=dict(error=f'Bu öğrenci PDF içinde tekrar ediyor ({dup["no"]}. sayfa ile). Yalnız ilk okunan sayfa kullanılabilir.', duplicate_of=dup['no'], candidate_oid=oid);oid=None
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
        json_mode = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.args.get('format') == 'json'
            or request.form.get('format') == 'json'
        )
        selected=request.form.getlist('select',type=int)
        if not selected or len(selected)!=len(set(selected)):
            if json_mode:
                return jsonify(ok=False, kaydedilen=[], bekleyen=[{'no': 0, 'neden': 'Kaydedilecek öğrencileri seçin.'}]), 400
            abort(400,description='Kaydedilecek öğrencileri seçin.')
        allowed={p['id'] for p in kt.roster(exam['sinif_id'])};con=connection()
        kaydedilen = []
        bekleyen = []
        bildirim_listesi = []
        try:
            con.execute('BEGIN IMMEDIATE')
            fresh=con.execute('SELECT saved FROM pdf_optik_batch WHERE id=?',(bid,)).fetchone()
            if fresh['saved']:abort(409,description='Bu yükleme zaten kaydedildi.')
            current=con.execute('SELECT cevaplar, yanlis_goturme FROM lgs_optik_sinav WHERE id=? AND ogretmen_id=?',(exam['id'],session['ogretmen_id'])).fetchone()
            if not current or kt.fingerprint(json.loads(current[0]))!=batch['key_hash']:abort(409,description='Cevap anahtarı değişti. PDF dosyasını yeniden yükleyin.')
            goturme = int(current['yanlis_goturme'] if current['yanlis_goturme'] is not None else exam.get('yanlis_goturme', 3))
            if not json_mode and con.execute('SELECT COUNT(*) FROM pdf_optik_page WHERE batch_id=?',(bid,)).fetchone()[0]!=batch['pages']:
                abort(409)
            for no in selected:
                row=con.execute('SELECT * FROM pdf_optik_page WHERE batch_id=? AND no=?',(bid,no)).fetchone()
                if not row or row['oid'] not in allowed:
                    if json_mode:
                        bekleyen.append({'no': no, 'neden': 'Sayfa okunmamış veya öğrenci atanmamış.'})
                        continue
                    abort(400)
                info=json.loads(row['data'])
                if info.get('error') or request.form.get(f'confirm_{no}')!='yes':
                    if json_mode:
                        bekleyen.append({'no': no, 'neden': info.get('error') or 'Kontrol onayı verilmedi.'})
                        continue
                    abort(400,description='Seçtiğiniz her öğrencinin cevaplarını kontrol edip onaylayın.')
                text=''.join(request.form.get(f'answers_{no}','').upper().split())
                if '?' in text or len(text)!=exam['soru_sayisi'] or any(a not in exam['choices']+'-' for a in text):
                    if json_mode:
                        bekleyen.append({'no': no, 'neden': 'Şüpheli (?) veya hatalı seçenek var. Boş için - seçin.'})
                        continue
                    abort(400,description='Cevap sayısı veya seçenekler hatalı. Boş cevap için - kullanın.')
                answers=['' if a=='-' else a for a in text]
                old=con.execute('SELECT * FROM lgs_optik_sonuc WHERE sinav_id=? AND ogrenci_id=?',(exam['id'],row['oid'])).fetchone()
                before=dict(old) if old else None
                if before:before['isaretler']=json.loads(before['isaretler'])
                if kt.fingerprint(before)!=info['before']:
                    if json_mode:
                        bekleyen.append({'no': no, 'neden': 'Öğrencinin sonucu değişti.'})
                        continue
                    abort(409,description='Öğrencinin sonucu değişti. PDF dosyasını yeniden yükleyin.')
                if old and request.form.get(f'replace_{no}')!='yes':
                    if json_mode:
                        bekleyen.append({'no': no, 'neden': 'Mevcut sonucu değiştirmek için onay gerekli.'})
                        continue
                    abort(409,description='Mevcut sonucu değiştirmek için ayrıca onay verin.')
                score=optik.puan_hesapla(json.loads(current[0]),answers,goturme)
                con.execute('''INSERT INTO lgs_optik_sonuc(sinav_id,ogrenci_id,isaretler,dogru,yanlis,bos,net,zaman) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(sinav_id,ogrenci_id) DO UPDATE SET isaretler=excluded.isaretler,dogru=excluded.dogru,yanlis=excluded.yanlis,bos=excluded.bos,net=excluded.net,zaman=excluded.zaman''',(exam['id'],row['oid'],json.dumps(answers),score['dogru'],score['yanlis'],score['bos'],score['net'],datetime.now().isoformat(timespec='seconds')))
                con.execute('INSERT INTO kamera_islem(sinav_id,ogrenci_id,owner,action,before_json,after_json) VALUES(?,?,?,?,?,?)',(exam['id'],row['oid'],session['ogretmen_id'],'pdf-replace' if old else 'pdf-import',json.dumps(before),json.dumps(answers)))
                kaydedilen.append({'no': no, 'oid': row['oid'], 'dogru': score['dogru'], 'yanlis': score['yanlis'], 'bos': score['bos'], 'net': score['net']})
                bildirim_listesi.append((row['oid'], f"{exam['ad']}: optik test sonucu kaydedildi ({score['dogru']} D, {score['yanlis']} Y, {score['net']} net)."))
            if kaydedilen and not bekleyen:
                con.execute('UPDATE pdf_optik_batch SET saved=1,pdf=NULL WHERE id=?',(bid,))
            con.commit()
        finally:con.close()
        for oid_val, mesaj in bildirim_listesi:
            try:
                db.veli_haber_ekle(oid_val, mesaj)
            except Exception:
                pass
        if json_mode:
            return jsonify(ok=bool(kaydedilen), kaydedilen=kaydedilen, bekleyen=bekleyen)
        flash(f'{len(kaydedilen)} öğrencinin sonucu kaydedildi.','success')
        return redirect(url_for('.detail',eid=exam['id']))
