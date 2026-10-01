"""Request-scoped, transactional teacher change history and conflict-safe undo.

TEMP triggers leave maintenance tools and non-web database clients unaffected.
Each request groups all related rows, including derived points, into one action.
"""
from __future__ import annotations

import json
import sqlite3
from uuid import uuid4
from flask import abort, flash, g, has_request_context, redirect, render_template, request, session, url_for

TABLES = {
    'haftalik_takip': 'Haftalık ödev / kitap', 'haftalik_odev_bilgi': 'Sınıf ödevi',
    'odevler': 'Ödev', 'odev_tamamlayanlar': 'Ödev onayı',
    'kitap_okuma_kayitlari': 'Kitap onayı', 'akademik_puan_kayitlari': 'Akademik puan',
    'gelisim_puan': 'Öğrenci puanı', 'lig': 'Sınıf puanı', 'lig_mac_tablo': 'Sınıf puanı',
    'tik_kayitlari': 'Davranış kaydı', 'olumlu_davranis': 'Olumlu davranış',
    'lgs_deneme': 'Sınav sonucu', 'lgs_deneme_ders': 'Ders sonucu',
    'rozet_kayitlari': 'Rozet', 'sinif_rozet': 'Sınıf rozeti',
    'sinav_analiz_kayitlari': 'Sınav analizi',
}


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS ogretmen_islem (
      id TEXT PRIMARY KEY, ogretmen_id INTEGER NOT NULL, yol TEXT NOT NULL,
      zaman TEXT NOT NULL DEFAULT (datetime('now','localtime')), geri_alindi INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS ogretmen_islem_satir (
      id INTEGER PRIMARY KEY AUTOINCREMENT, islem_id TEXT NOT NULL REFERENCES ogretmen_islem(id),
      tablo TEXT NOT NULL, anahtar TEXT NOT NULL, onceki TEXT, sonraki TEXT);
    CREATE INDEX IF NOT EXISTS idx_islem_ogretmen ON ogretmen_islem(ogretmen_id,zaman);
    CREATE INDEX IF NOT EXISTS idx_islem_satir ON ogretmen_islem_satir(islem_id,id);
    ''')
    con.commit()


def install_tracking(con):
    if not has_request_context() or request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return
    actor = session.get('ogretmen_id')
    if not actor or request.path.startswith('/veli') or getattr(g, 'history_disabled', False):
        return
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='ogretmen_islem'").fetchone():
        return
    teacher = con.execute('SELECT yetki FROM ogretmenler WHERE id=?', (actor,)).fetchone()
    if not teacher or teacher['yetki'] in ('rapor', 'rehber'):
        return
    if not getattr(g, 'teacher_action_id', None):
        g.teacher_action_id = uuid4().hex
    # Constants and schema identifiers below originate only from this module/SQLite.
    action = g.teacher_action_id
    con.create_function('teacher_action_id', 0, lambda: action)
    con.create_function('teacher_actor', 0, lambda: int(actor))
    con.create_function('teacher_path', 0, lambda: request.path)
    existing = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in TABLES.keys() & existing:
        columns = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        keys = [r['name'] for r in sorted(columns, key=lambda r: r['pk']) if r['pk']]
        if not keys:
            continue
        def obj(prefix, names):
            return 'json_object(' + ','.join(f"'{name}',{prefix}.\"{name}\"" for name in names) + ')'
        names = [r['name'] for r in columns]
        for kind in ('INSERT', 'UPDATE', 'DELETE'):
            before = obj('OLD', names) if kind != 'INSERT' else 'NULL'
            after = obj('NEW', names) if kind != 'DELETE' else 'NULL'
            key = obj('OLD' if kind == 'DELETE' else 'NEW', keys)
            when = f'WHEN {before} IS NOT {after}' if kind == 'UPDATE' else ''
            con.execute(f'''CREATE TEMP TRIGGER "history_{table}_{kind}" AFTER {kind} ON "{table}" {when}
              BEGIN
                INSERT OR IGNORE INTO ogretmen_islem(id,ogretmen_id,yol)
                  VALUES(teacher_action_id(),teacher_actor(),teacher_path());
                INSERT INTO ogretmen_islem_satir(islem_id,tablo,anahtar,onceki,sonraki)
                  VALUES(teacher_action_id(),'{table}',{key},{before},{after});
              END''')


def undo(con, action_id, teacher_id):
    """Reverse an entire request atomically; never overwrite intervening changes."""
    con.execute('BEGIN IMMEDIATE')
    con.execute('PRAGMA defer_foreign_keys=ON')
    try:
        action = con.execute('SELECT * FROM ogretmen_islem WHERE id=? AND ogretmen_id=?',
                             (action_id, teacher_id)).fetchone()
        if not action:
            raise PermissionError('İşlem bulunamadı veya size ait değil.')
        if action['geri_alindi']:
            raise ValueError('Bu işlem zaten geri alındı.')
        rows = con.execute('SELECT * FROM ogretmen_islem_satir WHERE islem_id=? ORDER BY id DESC',
                           (action_id,)).fetchall()
        for entry in rows:
            table = entry['tablo']
            if table not in TABLES:
                raise ValueError('Bu işlem geri alınamaz.')
            key = json.loads(entry['anahtar'])
            where = ' AND '.join(f'"{k}"=?' for k in key)
            current = con.execute(f'SELECT * FROM "{table}" WHERE {where}', tuple(key.values())).fetchone()
            current = dict(current) if current else None
            after = json.loads(entry['sonraki']) if entry['sonraki'] else None
            before = json.loads(entry['onceki']) if entry['onceki'] else None
            if current != after:
                raise ValueError('Bu kayda daha sonra başka bir değişiklik yapılmış. Önce en son işlemi geri alın; mevcut veriler korunuyor.')
            if before is None:
                # Prevent a newer child row from being silently deleted by CASCADE.
                if table in ('odevler', 'lgs_deneme'):
                    child, fk = ('odev_tamamlayanlar', 'odev_id') if table == 'odevler' else ('lgs_deneme_ders', 'deneme_id')
                    if con.execute(f'SELECT 1 FROM "{child}" WHERE "{fk}"=? LIMIT 1', (key['id'],)).fetchone():
                        raise ValueError('Bu kayda sonradan sonuç/onay eklenmiş. Önce ilgili işlemi geri alın.')
                con.execute(f'DELETE FROM "{table}" WHERE {where}', tuple(key.values()))
            elif current is None:
                fields = ','.join(f'"{k}"' for k in before)
                con.execute(f'INSERT INTO "{table}" ({fields}) VALUES ({",".join("?" for _ in before)})', tuple(before.values()))
            else:
                fields = ','.join(f'"{k}"=?' for k in before)
                con.execute(f'UPDATE "{table}" SET {fields} WHERE {where}', (*before.values(), *key.values()))
        con.execute('UPDATE ogretmen_islem SET geri_alindi=1 WHERE id=?', (action_id,))
        con.commit()
        return rows
    except Exception:
        con.rollback()
        raise


def register_history(app, login_required):
    import database as db
    con = db._conn()
    db._odev_init(con)
    db._gelisim_init(con)
    db._gami_init(con)
    init_schema(con)
    con.close()

    def full_teacher():
        con = db._conn()
        row = con.execute('SELECT yetki FROM ogretmenler WHERE id=?', (session['ogretmen_id'],)).fetchone()
        con.close()
        if not row or row['yetki'] in ('rapor', 'rehber'):
            abort(403)

    @app.route('/islem-gecmisi')
    @login_required
    def islem_gecmisi():
        full_teacher()
        con = db._conn()
        actions = [dict(r) for r in con.execute('SELECT * FROM ogretmen_islem WHERE ogretmen_id=? ORDER BY zaman DESC,rowid DESC LIMIT 100', (session['ogretmen_id'],))]
        for action in actions:
            entries = [dict(r) for r in con.execute('SELECT * FROM ogretmen_islem_satir WHERE islem_id=? ORDER BY id', (action['id'],))]
            action['baslik'] = ' · '.join(dict.fromkeys(TABLES.get(e['tablo'], 'Değişiklik') for e in entries if e['tablo'] not in ('gelisim_puan', 'lig', 'lig_mac_tablo', 'lgs_deneme_ders')))
            action['ayrinti'] = []
            action['degisiklikler'] = []
            action['duzenle_url'] = None
            old_courses, new_courses = {}, {}
            for entry in entries:
                data = json.loads(entry['sonraki'] or entry['onceki'])
                before = json.loads(entry['onceki']) if entry['onceki'] else {}
                after = json.loads(entry['sonraki']) if entry['sonraki'] else {}
                if entry['tablo'] == 'lgs_deneme_ders':
                    course = data['ders']
                    if before:
                        old_courses.setdefault(course, before)
                        new_courses.pop(course, None)
                    if after:
                        new_courses[course] = after
                if entry['tablo'] in ('lgs_deneme', 'odevler'):
                    action['degisiklikler'].append((data.get('ad') or data.get('baslik') or '') + ' — ' + ('Eklendi' if not before else 'Kaldırıldı' if not after else 'Düzenlendi'))
                labels = {'kitap_adi':'Kitap', 'kitap_okuma':'Okuma', 'kitap_getirme':'Kitap getirme', 'odev_durum':'Ödev durumu', 'odev_not':'Ödev notu', 'odev_karar_not':'Öğretmen notu', 'durum':'Onay', 'xp':'Öğrenci puanı', 'puan':'Puan', 'aciklama':'Açıklama', 'baslik':'Başlık', 'son_tarih':'Son tarih'}
                for field, label in labels.items():
                    if entry['tablo'] not in ('lig', 'lig_mac_tablo', 'lgs_deneme_ders') and before.get(field) != after.get(field):
                        action['degisiklikler'].append(f"{label}: {str(before.get(field) or '—')[:160]} → {str(after.get(field) or '—')[:160]}")
                oid = data.get('ogrenci_id')
                if oid:
                    student = con.execute('SELECT ad_soyad,sinif_id FROM ogrenciler WHERE id=?', (oid,)).fetchone()
                    if student:
                        data.setdefault('sinif_id', student['sinif_id'])
                    if student and student[0] not in action['ayrinti']:
                        action['ayrinti'].append(student[0])
                if entry['tablo'] == 'lgs_deneme' and entry['sonraki']:
                    action['duzenle_url'] = url_for('sonuclar', ogrenci=oid, duzenle=data['id'])
                elif entry['tablo'] == 'odevler' and entry['sonraki']:
                    action['duzenle_url'] = url_for('odev_duzenle', odev_id=data['id'])
                elif entry['tablo'] in ('haftalik_takip', 'haftalik_odev_bilgi'):
                    action['duzenle_url'] = url_for('haftalik_takip', sinif=data.get('sinif_id'), hafta=data.get('hafta_basi'))
                elif entry['tablo'] == 'kitap_okuma_kayitlari':
                    action['duzenle_url'] = url_for('ogretmen_kitap_okuma')
                elif oid and not action['duzenle_url']:
                    action['duzenle_url'] = url_for('dashboard', sinif=data.get('sinif_id'), q=action['ayrinti'][-1] if action['ayrinti'] else '')
            def result_label(row):
                if not row:
                    return '—'
                count = row.get('soru_sayisi') or row['dogru']+row['yanlis']+row['bos']
                return f"{row['dogru']} doğru / {row['yanlis']} yanlış / {row['bos']} boş ({count} soru, {row['net']} net)"
            for course in dict.fromkeys([*old_courses, *new_courses]):
                action['degisiklikler'].append(f'{course}: {result_label(old_courses.get(course))} → {result_label(new_courses.get(course))}')
        con.close()
        return render_template('islem_gecmisi.html', islemler=actions)

    @app.route('/islem-gecmisi/<action_id>/geri-al', methods=['POST'])
    @login_required
    def islem_geri_al(action_id):
        full_teacher()
        g.history_disabled = True
        con = db._conn()
        try:
            rows = undo(con, action_id, session['ogretmen_id'])
        except PermissionError:
            abort(403)
        except (ValueError, sqlite3.IntegrityError) as error:
            flash(str(error) if isinstance(error, ValueError) else 'Bu kayda bağlı başka bir işlem var. Önce onu geri alın.', 'warning')
        else:
            students = {json.loads(r['sonraki'] or r['onceki']).get('ogrenci_id') for r in rows}
            classes = {json.loads(r['sonraki'] or r['onceki']).get('sinif_id') for r in rows if not json.loads(r['sonraki'] or r['onceki']).get('ogrenci_id')}
            for sid in classes - {None}:
                students.update(s['id'] for s in db.sinif_ogrencileri(sid))
            for oid in students - {None}:
                db.veli_haber_ekle(oid, 'Öğretmen önceki kaydını geri aldı. Öğrenci ekranındaki bilgiler güncellendi.')
            flash('İşlem ve ona bağlı puan değişiklikleri geri alındı.', 'success')
        finally:
            con.close()
        return redirect(url_for('islem_gecmisi'))

    @app.route('/odev/<int:odev_id>/duzenle', methods=['GET', 'POST'])
    @login_required
    def odev_duzenle(odev_id):
        full_teacher()
        detail = db.odev_detay(odev_id)
        if not detail or detail['ogretmen_id'] != session['ogretmen_id']:
            abort(403)
        if request.method == 'POST':
            from datetime import date
            title = request.form.get('baslik', '').strip()
            try:
                date.fromisoformat(request.form.get('son_tarih', ''))
            except ValueError:
                flash('Geçerli bir son tarih seçin.', 'warning')
            else:
                if not title:
                    flash('Ödev başlığını yazın.', 'warning')
                else:
                    con = db._conn()
                    con.execute('BEGIN IMMEDIATE')
                    current = con.execute('SELECT * FROM odevler WHERE id=?', (odev_id,)).fetchone()
                    if not current:
                        con.rollback()
                        con.close()
                        abort(404)
                    fingerprint = json.dumps(dict(current), ensure_ascii=False, sort_keys=True)
                    if fingerprint != request.form.get('surum'):
                        con.close()
                        flash('Ödev siz düzenlerken değişmiş. Güncel kaydı açıp tekrar düzenleyin.', 'warning')
                    else:
                        con.execute('UPDATE odevler SET baslik=?,aciklama=?,ders=?,son_tarih=? WHERE id=?',
                                    (title[:200], request.form.get('aciklama', '')[:2000], request.form.get('ders', 'Genel')[:80], request.form['son_tarih'], odev_id))
                        con.commit()
                        con.close()
                        db.veli_haber_sinifa(detail['sinif_id'], f'Ödev güncellendi: {title}', 'odev')
                        flash('Ödev güncellendi.', 'success')
                        return redirect(url_for('islem_gecmisi'))
        con = db._conn()
        row = con.execute('SELECT * FROM odevler WHERE id=?', (odev_id,)).fetchone()
        if not row:
            con.close()
            abort(404)
        fingerprint = json.dumps(dict(row), ensure_ascii=False, sort_keys=True)
        con.close()
        return render_template('odev_duzenle.html', odev=detail, surum=fingerprint)
