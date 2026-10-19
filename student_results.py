"""Flexible per-student tests, exam editing and authorized student search."""
from datetime import date
import json
import unicodedata
from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
import database as db

COURSES = ('Türkçe', 'Matematik', 'Fen Bilimleri', 'Sosyal Bilgiler', 'T.C. İnkılap Tarihi', 'Din Kültürü', 'İngilizce')


def school_courses():
    con = db._conn()
    names = [r[0] for r in con.execute("SELECT DISTINCT ders_adi FROM ders_programi WHERE ders_adi IS NOT NULL AND ders_adi<>'' ORDER BY ders_adi")]
    con.close()
    aliases = {'Din Kültürü ve Ahlak Bilgisi':'Din Kültürü', 'T.C. İnkılap Tarihi ve Atatürkçülük':'T.C. İnkılap Tarihi'}
    return tuple(dict.fromkeys([*COURSES, *(aliases.get(n, n) for n in names if n != 'Rehberlik')]))


def normalize(text):
    text = str(text or '').replace('ı', 'i').replace('İ', 'I').casefold()
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).split())


BOS_ISARET = frozenset('-._*Xx0')


def answer_letters(text, key=False):
    """'AB-C D' → ['A','B','','C','D']. Spaces only separate; '-', '.', '_', '*', 'X', '0' mean blank."""
    letters = []
    for ch in str(text or ''):
        if ch.isspace() or ch in ',;':
            continue
        up = ch.upper()
        if up in db.CEVAP_SIKLARI:
            letters.append(up)
        elif ch in BOS_ISARET and not key:
            letters.append('')
        else:
            raise ValueError(f"'{ch}' tanınmadı. {'Cevap anahtarında yalnız A–E harfleri' if key else 'Cevaplarda A–E harfleri, boş için -'} kullanın.")
    return letters


def institution_allowed():
    from yetki import yetkili
    return yetkili(session.get('ogretmen_id'), 'yonetici')


def course_analysis(records, include_exams=False):
    groups = {}
    for record in reversed(records):
        if record.get('tur') != 'ders' and not include_exams:
            continue
        for row in record['dersler']:
            count = row.get('soru_sayisi') or db.LGS_SORU_SAYISI.get(row['ders'], 10)
            groups.setdefault(row['ders'], []).append(dict(row, ad=record['ad'], tarih=record['tarih'],
                yuzde=round(100 * row['dogru'] / count, 1), soru_sayisi=count))
    result = []
    for name, entries in groups.items():
        last = entries[-1]
        result.append({'ders': name, 'son': last, 'gecmis': entries[-6:],
                       'fark': round(last['yuzde'] - entries[-2]['yuzde'], 1) if len(entries) > 1 else None})
    result.sort(key=lambda a: a['son']['tarih'], reverse=True)
    return result


def sinif_ders_toplu_kaydet(
    sinif_id: int,
    title: str,
    when: str,
    course: str,
    count: int,
    penalty: int,
    form_data,
    ogretmen_id: int | None = None,
    key: list[str] | None = None,
    satir_bazli: bool = False,
) -> dict:
    """Sınıf ders yaprak testini satır bazlı doğrulayıp tek transaction içinde kaydeder."""
    from datetime import datetime
    from metrik import net as metrik_net

    title = (title or '').strip()[:80]
    when = date.fromisoformat((when or '').strip()).isoformat()
    course = (course or '').strip()
    courses = school_courses()
    if not title or course not in courses or not 1 <= int(count) <= 500 or int(penalty) not in (0, 3, 4):
        raise ValueError('Deneme adı, ders, soru sayısı ve net kuralını seçin.')
    count = int(count)
    penalty = int(penalty)
    students = db.sinif_ogrencileri(sinif_id)
    hazir = []
    bekleyen = []
    for student in students:
        sid = student['id']
        durum = (form_data.get(f"durum_{sid}") or '').strip().upper()
        if durum in ('K', 'KATILMADI'):
            continue
        raw_cevap = (form_data.get(f"cevap_{sid}") or '').strip()
        if key and raw_cevap:
            try:
                marks = answer_letters(raw_cevap)
                if len(marks) > count:
                    raise ValueError(f"{student['ad_soyad']}: {len(marks)} cevap yazıldı, testte {count} soru var.")
                marks += [''] * (count - len(marks))
                rows = db.soru_durumlari(key, marks)
                dogru = sum(r['durum'] == 'dogru' for r in rows)
                yanlis = sum(r['durum'] == 'yanlis' for r in rows)
                hazir.append((student, dogru, yanlis, marks))
            except ValueError as err:
                if satir_bazli:
                    bekleyen.append({'ogrenci_id': sid, 'ad_soyad': student['ad_soyad'], 'neden': str(err)})
                else:
                    raise
            continue
        raw_dogru = (form_data.get(f"dogru_{sid}") or '').strip()
        raw_yanlis = (form_data.get(f"yanlis_{sid}") or '').strip()
        if raw_dogru == '' and raw_yanlis == '':
            continue
        if raw_dogru.upper() == 'K' or raw_yanlis.upper() == 'K':
            continue
        try:
            dogru = int(raw_dogru or 0)
            yanlis = int(raw_yanlis or 0)
        except ValueError:
            msg = f"{student['ad_soyad']}: doğru ve yanlış sayı olmalı."
            if satir_bazli:
                bekleyen.append({'ogrenci_id': sid, 'ad_soyad': student['ad_soyad'], 'neden': msg})
                continue
            raise ValueError(msg)
        if min(dogru, yanlis) < 0 or dogru + yanlis > count:
            msg = f"{student['ad_soyad']}: doğru ve yanlış toplamı {count} soruyu geçemez."
            if satir_bazli:
                bekleyen.append({'ogrenci_id': sid, 'ad_soyad': student['ad_soyad'], 'neden': msg})
                continue
            raise ValueError(msg)
        hazir.append((student, dogru, yanlis, None))

    if not hazir and not (satir_bazli and bekleyen):
        raise ValueError('En az bir öğrencinin cevaplarını ya da doğru ve yanlışını yazın. Boş satırlar kayda girmez.')

    kaydedilen = []
    con = db._conn()
    db._lgs_init(con)
    try:
        with con:
            for student, dogru, yanlis, marks in hazir:
                bos = count - dogru - yanlis
                net_val = metrik_net(dogru, yanlis, penalty)
                cur = con.execute(
                    "INSERT INTO lgs_deneme (ogrenci_id, ad, tarih, ogretmen_id, tur) VALUES (?, ?, ?, ?, 'ders')",
                    (int(student['id']), title, when, ogretmen_id),
                )
                deneme_id = int(cur.lastrowid)
                con.execute(
                    """INSERT INTO lgs_deneme_ders
                       (deneme_id, ders, soru_sayisi, dogru, yanlis, bos, net, yanlis_goturme, anahtar, isaretler)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        deneme_id, course, count, dogru, yanlis, bos, net_val, penalty,
                        json.dumps(key) if key else None,
                        json.dumps(marks) if marks else None,
                    ),
                )
                kaydedilen.append({
                    'ogrenci_id': int(student['id']),
                    'ad_soyad': student['ad_soyad'],
                    'deneme_id': deneme_id,
                    'dogru': dogru,
                    'yanlis': yanlis,
                    'bos': bos,
                    'net': net_val,
                })
    finally:
        con.close()

    for item in kaydedilen:
        try:
            db.veli_haber_ekle(item['ogrenci_id'], f'{title}: sonuç kaydedildi. Ders analizinizi inceleyebilirsiniz.', sonuc_id=item['deneme_id'])
        except Exception:
            pass
    return {'ok': bool(kaydedilen), 'kaydedilen': kaydedilen, 'bekleyen': bekleyen}


def register_results(app, login_required, accessible):
    @app.context_processor
    def results_context():
        return {'kurum_deneme_yetkili': institution_allowed()}

    @app.route('/api/ogrenci-ara')
    @login_required
    def api_ogrenci_ara():
        query = normalize(request.args.get('q', '')[:100])
        if not query:
            return jsonify(ogrenciler=[])
        classes = db.aktif_sube_siniflari() or db.ogretmen_siniflari(session['ogretmen_id'])
        scope = request.args.get('kapsam')
        results = []
        for classroom in classes:
            from moduller import seviye as sinif_seviyesi
            if scope == 'lgs' and sinif_seviyesi(classroom) != 8:
                continue
            for student in db.sinif_ogrencileri(classroom['id']):
                name = normalize(student['ad_soyad'])
                if (query.isdecimal() and str(student['ogr_no']).startswith(query)) or (not query.isdecimal() and all(t in name for t in query.split())):
                    results.append({'id': student['id'], 'ad': student['ad_soyad'], 'no': student['ogr_no'],
                                    'sinif': classroom['sinif_adi'], 'sinif_id': classroom['id']})
        results.sort(key=lambda r: (str(r['no']) != query, r['sinif'], normalize(r['ad'])))
        response = jsonify(ogrenciler=results[:25], toplam=len(results))
        response.headers['Cache-Control'] = 'no-store'
        return response

    def full_teacher():
        con = db._conn()
        row = con.execute('SELECT yetki FROM ogretmenler WHERE id=?', (session['ogretmen_id'],)).fetchone()
        con.close()
        if not row or row['yetki'] in ('rapor', 'rehber'):
            abort(403)

    def records_for(oid):
        records = db.lgs_denemeler(oid, 200)
        for r in records:
            r['duzenlenebilir'] = r.get('ogretmen_id') == session.get('ogretmen_id') or (r.get('tur') == 'kurum' and institution_allowed())
        return records

    def _sinif_denemeleri(sinif_id):
        con = db._conn()
        rows = con.execute(
            '''SELECT d.ad, d.tarih, d.tur, COUNT(DISTINCT d.id) AS n,
                      GROUP_CONCAT(DISTINCT dd.ders) AS dersler,
                      MAX(dd.anahtar) AS anahtar
               FROM lgs_deneme d
               JOIN ogrenciler o ON o.id=d.ogrenci_id
               LEFT JOIN lgs_deneme_ders dd ON dd.deneme_id=d.id
               WHERE o.sinif_id=? AND d.ogretmen_id=?
               GROUP BY d.ad, d.tarih, d.tur
               ORDER BY d.tarih DESC, d.ad''',
            (sinif_id, session['ogretmen_id']),
        ).fetchall()
        con.close()
        cikti = []
        for row in rows:
            kayit = dict(row)
            kayit['ders_listesi'] = [parca for parca in (kayit.get('dersler') or '').split(',') if parca]
            try:
                kayit['anahtar'] = json.loads(kayit.get('anahtar') or 'null') or []
            except ValueError:
                kayit['anahtar'] = []
            cikti.append(kayit)
        return cikti

    def _denemeleri_sil(ids):
        if not ids:
            raise ValueError('Silinecek kayıt yok.')
        con = db._conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            for deneme_id in ids:
                con.execute('DELETE FROM lgs_deneme_ders WHERE deneme_id=?', (deneme_id,))
                con.execute('DELETE FROM lgs_deneme WHERE id=?', (deneme_id,))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _sinif_ders_sil():
        classes = db.aktif_sube_siniflari() or db.ogretmen_siniflari(session['ogretmen_id'])
        sinif_id = request.form.get('sinif_id', type=int) or 0
        if sinif_id not in {int(s['id']) for s in classes}:
            abort(403)
        title = request.form.get('ad', '').strip()
        when = date.fromisoformat(request.form.get('tarih', '')).isoformat()
        kind = request.form.get('tur') or 'ders'
        if kind not in ('ders', 'deneme', 'kurum'):
            raise ValueError('Silinecek kayıt türü geçersiz.')
        con = db._conn()
        rows = con.execute(
            '''SELECT d.id, d.ogrenci_id FROM lgs_deneme d
               JOIN ogrenciler o ON o.id=d.ogrenci_id
               WHERE o.sinif_id=? AND d.ogretmen_id=? AND d.ad=? AND d.tarih=? AND d.tur=?''',
            (sinif_id, session['ogretmen_id'], title[:80], when, kind),
        ).fetchall()
        con.close()
        if not rows:
            raise ValueError('Bu sınıfta size ait böyle bir kayıt yok.')
        _denemeleri_sil([r['id'] for r in rows])
        for row in rows:
            db.veli_haber_ekle(row['ogrenci_id'], f'{title}: sonuç silindi.')
        flash(f'{title}: {len(rows)} öğrencinin kaydı silindi. İşlem geçmişinden geri alabilirsiniz.', 'success')
        return redirect(url_for('sonuclar', sinif=sinif_id))

    def _sinif_ders_kaydet():
        classes = db.aktif_sube_siniflari() or db.ogretmen_siniflari(session['ogretmen_id'])
        sinif_id = request.form.get('sinif_id', type=int) or 0
        if sinif_id not in {int(s['id']) for s in classes}:
            abort(403)
        title = request.form.get('ad', '').strip()
        when = date.fromisoformat(request.form.get('tarih', '')).isoformat()
        course = request.form.get('ders', '').strip()
        key = answer_letters(request.form.get('anahtar'), key=True)
        if len(key) > 500:
            raise ValueError('Cevap anahtarı en fazla 500 soru olabilir.')
        count = len(key) if key else int(request.form.get('soru_sayisi', ''))
        penalty = int(request.form.get('yanlis_goturme', ''))
        satir_bazli = request.form.get('satir_bazli') == '1'
        res = sinif_ders_toplu_kaydet(
            sinif_id=sinif_id,
            title=title,
            when=when,
            course=course,
            count=count,
            penalty=penalty,
            form_data=request.form,
            ogretmen_id=session.get('ogretmen_id'),
            key=key or None,
            satir_bazli=satir_bazli,
        )
        if res['bekleyen']:
            hatalar = '; '.join(b['neden'] for b in res['bekleyen'])
            flash(f"{title}: {len(res['kaydedilen'])} öğrenciye yazıldı. Hatalı satırlar bekletildi: {hatalar}", 'warning')
        else:
            flash(f"{title}: {len(res['kaydedilen'])} öğrenciye yazıldı. Boş bırakılan satırlar kayda girmedi.", 'success')
        return redirect(url_for('sonuclar', sinif=sinif_id))

    @app.route('/sonuclar', methods=['GET', 'POST'])
    @login_required
    def sonuclar():
        full_teacher()
        oid = request.values.get('ogrenci', type=int)
        if not oid and request.method == 'GET':
            return redirect(url_for('kamera_test.index'))
        if not oid:
            sinif_form = None
            if request.method == 'POST':
                if request.form.get('islem') == 'sinif_ders_sil':
                    try:
                        return _sinif_ders_sil()
                    except (ValueError, TypeError) as error:
                        flash(str(error) or 'Deneme silinemedi.', 'warning')
                elif request.form.get('islem') != 'sinif_ders':
                    abort(400)
                else:
                    sinif_form = request.form
                    try:
                        return _sinif_ders_kaydet()
                    except (ValueError, TypeError) as error:
                        flash(str(error) or 'Ders denemesi alanlarını kontrol edin.', 'warning')
            classes = db.aktif_sube_siniflari() or db.ogretmen_siniflari(session['ogretmen_id'])
            selected = request.args.get('sinif', type=int) or session.get('ui_sinif_id')
            if sinif_form and sinif_form.get('sinif_id', type=int):
                selected = sinif_form.get('sinif_id', type=int)
            sinif_idler = {s['id'] for s in classes}
            goster = [s for s in classes if s['id'] == selected] if selected in sinif_idler else classes
            return render_template(
                'sonuclar.html', ogrenci=None, dersler=school_courses(), bugun=date.today().isoformat(),
                sinif_form=sinif_form, sinif_nav=classes, secili_sinif=selected if selected in sinif_idler else None,
                gruplar=[{
                    'sinif': s,
                    'ogrenciler': db.sinif_ogrencileri(s['id']),
                    'denemeler': _sinif_denemeleri(s['id']),
                } for s in goster],
            )
        if not accessible(session['ogretmen_id'], oid):
            abort(403)
        con = db._conn()
        student = con.execute('SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?', (oid,)).fetchone()
        con.close()
        records = records_for(oid)
        edit_id = request.values.get('duzenle', type=int)
        editing = next((r for r in records if r['id'] == edit_id), None) if edit_id else None
        if edit_id and (not editing or not editing['duzenlenebilir']):
            abort(403)
        courses = school_courses()
        if editing:
            courses = tuple(dict.fromkeys([*courses, *(r['ders'] for r in editing['dersler'])]))
        form = None
        if request.method == 'POST' and request.form.get('islem') == 'sil':
            kayit = next((r for r in records if r['id'] == request.form.get('deneme', type=int)), None)
            if not kayit or not kayit['duzenlenebilir']:
                abort(403)
            _denemeleri_sil([kayit['id']])
            db.veli_haber_ekle(oid, f"{kayit['ad']}: sonuç silindi.")
            flash('Kayıt silindi. Yanlışlıkla sildiyseniz İşlem geçmişinden geri alabilirsiniz.', 'success')
            return redirect(url_for('sonuclar', ogrenci=oid))
        if request.method == 'POST':
            form = request.form
            try:
                title = request.form.get('ad', '').strip()
                when = request.form.get('tarih', '')
                when = date.fromisoformat(when).isoformat()
                kind = request.form.get('tur')
                if not title or kind not in ('ders', 'deneme', 'kurum'):
                    raise ValueError('Sonuç adını ve türünü seçin.')
                if kind == 'kurum' and not institution_allowed():
                    abort(403)
                names = request.form.getlist('ders')
                totals = request.form.getlist('soru_sayisi')
                correct = request.form.getlist('dogru')
                wrong = request.form.getlist('yanlis')
                penalties = request.form.getlist('yanlis_goturme')
                if not 1 <= len(names) <= len(courses) or len(set(names)) != len(names) or any(len(v) != len(names) for v in (totals, correct, wrong, penalties)):
                    raise ValueError('Her ders için bir sonuç satırı girin; aynı dersi iki kez seçmeyin.')
                if kind == 'ders' and len(names) != 1:
                    raise ValueError('Ders testinde tek ders seçin. Birden fazla ders için deneme seçin.')
                rows = []
                for i, name in enumerate(names):
                    count, c, w, penalty = int(totals[i]), int(correct[i]), int(wrong[i]), int(penalties[i])
                    if name not in courses or not 1 <= count <= 500 or min(c, w) < 0 or c + w > count or penalty not in (0, 3, 4):
                        raise ValueError('Soru sayısı 1–500 olmalı; doğru ve yanlış toplamı soru sayısını geçemez.')
                    rows.append(dict(ders=name, soru_sayisi=count, dogru=c, yanlis=w, bos=count-c-w, yanlis_goturme=penalty))
                if editing:
                    if editing['tur'] == 'kurum' and kind != 'kurum':
                        raise ValueError('Kurum denemesinin türü değiştirilemez.')
                    if editing['tur'] == 'kurum' and (title != editing['ad'] or when != editing['tarih']):
                        raise ValueError('Kurum denemesinde ad ve tarih ortak sınavı tanımlar; burada yalnızca öğrencinin ders sonuçlarını düzenleyin.')
                    con = db._conn()
                    con.execute('BEGIN IMMEDIATE')
                    current = con.execute('SELECT surum FROM lgs_deneme WHERE id=?', (edit_id,)).fetchone()
                    if not current or current[0] != request.form.get('surum', type=int):
                        con.rollback()
                        con.close()
                        raise ValueError('Bu sonuç siz düzenlerken değişti. Güncel kaydı tekrar açın.')
                    con.execute('UPDATE lgs_deneme SET ad=?,tarih=?,tur=?,surum=surum+1 WHERE id=?', (title[:80], when, kind, edit_id))
                    con.execute('DELETE FROM lgs_deneme_ders WHERE deneme_id=?', (edit_id,))
                    from metrik import net as metrik_net
                    for row in rows:
                        net = metrik_net(row['dogru'], row['yanlis'], row['yanlis_goturme'])
                        old = next((d for d in editing['dersler'] if d['ders'] == row['ders'] and d.get('anahtar')
                                    and (d['soru_sayisi'], d['dogru'], d['yanlis']) == (row['soru_sayisi'], row['dogru'], row['yanlis'])), None)
                        con.execute('INSERT INTO lgs_deneme_ders(deneme_id,ders,soru_sayisi,dogru,yanlis,bos,net,yanlis_goturme,anahtar,isaretler) VALUES(?,?,?,?,?,?,?,?,?,?)',
                                    (edit_id, row['ders'], row['soru_sayisi'], row['dogru'], row['yanlis'], row['bos'], net, row['yanlis_goturme'],
                                     json.dumps(old['anahtar']) if old else None, json.dumps(old['isaretler']) if old else None))
                    con.commit()
                    con.close()
                else:
                    saved = db.lgs_deneme_ekle(oid, title, when, rows, ogretmen_id=session['ogretmen_id'], tur=kind)
                    if not saved['ok']:
                        raise ValueError(saved['hata'])
                db.veli_haber_ekle(oid, f'{title}: sonuç {"güncellendi" if editing else "kaydedildi"}. Ders analizinizi inceleyebilirsiniz.', sonuc_id=edit_id if editing else saved['id'])
                flash('Sonuç güncellendi.' if editing else 'Sonuç kaydedildi ve öğrenci analizine eklendi.', 'success')
                return redirect(url_for('sonuclar', ogrenci=oid))
            except (ValueError, TypeError) as error:
                flash(str(error) or 'Sonuç alanlarını kontrol edin.', 'warning')
        return render_template('sonuclar.html', ogrenci=dict(student), kayitlar=records, duzenlenen=editing,
                               dersler=courses, bugun=date.today().isoformat(), analiz=course_analysis(records, True), form=form, veli=False)

    @app.route('/veli/sonuclar')
    def veli_sonuclar():
        oid = session.get('veli_ogrenci_id')
        if not oid:
            return redirect(url_for('veli_giris'))
        con = db._conn()
        student = con.execute('SELECT o.*,s.sinif_adi FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE o.id=?', (oid,)).fetchone()
        con.close()
        if not student:
            abort(404)
        records = db.lgs_denemeler(oid, 200)
        requested = request.args.get('sonuc', type=int)
        if requested:
            records = [r for r in records if r['id'] == requested]
            if not records:
                flash('Bu sonuç artık mevcut değil veya bu öğrenciye ait değil.', 'warning')
        return render_template('sonuclar.html', ogrenci=dict(student), kayitlar=records, analiz=course_analysis(records, True), veli=True)
