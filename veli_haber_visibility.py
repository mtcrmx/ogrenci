"""Validate notification sources on every parent read; retain history for undo."""
import re
from datetime import date, timedelta


def is_internal_operation(text):
    """Teacher housekeeping changes data silently, without a parent message."""
    text = ' '.join((text or '').split())
    return text in {
        'Öğretmen önceki kaydını geri aldı. Öğrenci ekranındaki bilgiler güncellendi.',
        'Öğretmen bugünkü LGS programını onayladı.',
        'Öğretmen çalışma defterini gördü.',
    } or bool(re.fullmatch(
        r'.+: sonuç silindi\.|.+: sonuç güncellendi\. Ders analizinizi inceleyebilirsiniz\.|Ödev güncellendi: .+',
        text,
    ))


def current(con, oid, rows):
    tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    def query(table, sql):
        return [dict(r) for r in con.execute(sql,(oid,))] if table in tables else []
    results=query('lgs_deneme','SELECT id,ad FROM lgs_deneme WHERE ogrenci_id=?')
    notes=query('ogretmen_notlari','SELECT * FROM ogretmen_notlari WHERE ogrenci_id=? AND veliye_acik=1')
    homework=query('odevler','SELECT * FROM odevler WHERE sinif_id=(SELECT sinif_id FROM ogrenciler WHERE id=?)')
    weekly=query('haftalik_takip','SELECT * FROM haftalik_takip WHERE ogrenci_id=?')
    classwork=query('haftalik_odev_bilgi','SELECT * FROM haftalik_odev_bilgi WHERE sinif_id=(SELECT sinif_id FROM ogrenciler WHERE id=?)')
    normalize=lambda value: ' '.join((value or '').split())
    ids={r['id'] for r in results};names={normalize(r['ad']) for r in results}
    note_texts={normalize(({'uyari':'Uyarı','olumlu':'Olumlu not','duyuru':'Duyuru'}.get(n.get('tur'),'Öğretmen notu')+': '+n['not_metni'])[:240]) for n in notes}
    homework_texts={normalize((f"Yeni ödev ({h['ders']}): {h['baslik']}" if h['ders'] and h['ders']!='Genel' else f"Yeni ödev: {h['baslik']}")[:240]) for h in homework}
    kept=[]
    for row in rows:
        text=normalize(row['metin'])
        if is_internal_operation(text):continue
        if row.get('sonuc_id') is not None:
            if row['sonuc_id'] not in ids:continue
        else:
            # Only exact generated formats are matched for old records without
            # a source id; unrelated messages must not be discarded.
            match=re.fullmatch(r'(.+): sonuç (?:kaydedildi|güncellendi)\. Ders analizinizi inceleyebilirsiniz\.',text)
            legacy=re.fullmatch(r'(.+) sonucu geldi\. Toplam net [-\d.,]+\.',text)
            if (match or legacy) and normalize((match or legacy)[1]) not in names:continue
            if re.match(r'^Yeni ödev(?: \([^)]*\))?: ',text) and text not in homework_texts:continue
            if row.get('kaynak_tur')=='not':
                if not any(n['id']==row.get('kaynak_id') for n in notes) or text not in note_texts:continue
            elif text.startswith(('Uyarı: ','Olumlu not: ','Duyuru: ')) and text not in note_texts:continue
            if text.startswith(('Bu hafta kitap verildi: ','Bu hafta ödev dersi: ','Ödev notu: ','Öğretmen notu: ','Bu hafta ödev: ')):
                try:
                    day=date.fromisoformat(row['zaman'][:10]);week=(day-timedelta(days=day.weekday())).isoformat()
                except (ValueError,TypeError):week=''
                expected=set(note_texts)
                for record in weekly:
                    if record['hafta_basi']!=week:continue
                    for prefix,field in [('Bu hafta kitap verildi: ','kitap_adi'),('Bu hafta ödev dersi: ','odev_ders'),('Ödev notu: ','odev_not'),('Öğretmen notu: ','odev_karar_not')]:
                        if record.get(field):expected.add(normalize((prefix+record[field])[:240]))
                for record in classwork:
                    if record['hafta_basi']==week:
                        parts=[record[k] for k in ('ders','kitap_adi','aciklama') if record.get(k)]
                        expected.add(normalize(('Bu hafta ödev: '+' — '.join(parts))[:240]))
                if text not in expected:continue
            assessment=re.fullmatch(r'.+ için bu haftaki ödev (tam|eksik|yok) işaretlendi\.',text)
            book=re.fullmatch(r'.+ kitabı (okudu|okumadı) olarak işaretlendi\.',text)
            brought=re.fullmatch(r'.+ kitabı (getirdi|getirmedi)\.',text)
            photo=re.fullmatch(r'.+ için ödev fotoğrafı eklendi\.',text)
            if assessment or book or brought or photo:
                try:
                    day=date.fromisoformat(row['zaman'][:10]);week=(day-timedelta(days=day.weekday())).isoformat()
                except (ValueError,TypeError):week=''
                record=next((r for r in weekly if r['hafta_basi']==week),{})
                if assessment and record.get('odev_durum')!=assessment[1]:continue
                if book and record.get('kitap_okuma')!={'okudu':'okudu','okumadı':'okumadi'}[book[1]]:continue
                if brought and record.get('kitap_getirme')!=brought[1]:continue
                if photo and not record.get('odev_foto'):continue
        kept.append(row)
    return kept
