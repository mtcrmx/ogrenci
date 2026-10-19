"""Parent home feed, always scoped to the signed-in student's current records."""
from datetime import date, timedelta
from flask import url_for
import database as db
import lgs_optik


def build(student):
    from moduller import seviye as sinif_seviyesi
    oid, sid = int(student['id']), int(student['sinif_id'])
    lgs = sinif_seviyesi(student) == 8
    items = []
    def add(key, kind, title, body, stamp='', teacher='', status='', href='', action='Ayrıntıyı aç', pending=False):
        items.append(dict(key=key, kind=kind, title=title, body=body or '', stamp=stamp or '',
                          teacher=teacher or '', status=status, href=href, action=action, pending=pending))
    # Read current assignments and results, not just push notifications: edits and
    # deletions therefore appear on the next refresh as well as new entries.
    con = db._conn()
    try:
        lgs_optik._init(con)
        tests = con.execute('''SELECT e.id,e.ad,e.ders,e.kaynak,e.olusturma,e.soru_sayisi,
            t.ad_soyad AS teacher,r.id AS result_id,r.dogru,r.yanlis,r.bos,r.zaman
            FROM lgs_optik_sinav e LEFT JOIN ogretmenler t ON t.id=e.ogretmen_id
            LEFT JOIN lgs_optik_sonuc r ON r.sinav_id=e.id AND r.ogrenci_id=?
            WHERE (e.silindi_at IS NULL OR e.silindi_at='')
              AND (e.sinif_id=? OR (e.sinif_id IS NULL AND ?))
              AND (e.kaynak='kamera' OR ?)
            ORDER BY COALESCE(r.zaman,e.olusturma) DESC,e.id DESC LIMIT 40''', (oid,sid,lgs,lgs)).fetchall()
    finally:
        con.close()
    for row in tests:
        school = row['kaynak']=='kamera'
        complete = row['result_id'] is not None
        body = f"{row['ders'] or 'Test'} · {row['soru_sayisi']} soru"
        if complete:
            body += f" · {row['dogru']} doğru, {row['yanlis']} yanlış, {row['bos']} boş"
        add(f"test-{row['id']}", 'sonuc' if complete else 'gorev', row['ad'], body,
            row['zaman'] or row['olusturma'], row['teacher'],
            ('Sonuç hazır' if complete else 'Sınıfta çözülecek' if school else 'Çözülmesi bekleniyor'),
            url_for('ev_analiz.index',test=row['id']) if complete else
            url_for('yaprak_analiz.index') if school else url_for('veli_lgs',bolum='soru',sinav=row['id']),
            'Sonucu incele' if complete else 'Okul testlerine git' if school else 'Testi aç', pending=not complete and not school)
    homework = db.ogrenci_odevleri(oid,30)
    for row in homework:
        add(f"odev-{row['id']}",'gorev',row['baslik'],
            f"{row['ders'] or 'Ödev'} · {row['aciklama']}" + (f" · Son tarih: {row['son_tarih']}" if row['son_tarih'] else ''),
            row['tarih'],row['ogretmen'],'Tamamlandı' if row['tamamlandi'] else 'Yapılması bekleniyor',pending=not row['tamamlandi'])
    notes = db.ogretmen_notlari_veli_ozeti(oid,30)
    for row in notes:
        add(f"not-{row['id']}",'mesaj',{'uyari':'Öğretmen uyarısı','olumlu':'Olumlu geri bildirim'}.get(row['tur'],'Öğretmen mesajı'),
            row['not_metni'],row['tarih'],row['ogretmen'],href='#mesajlar',action='Mesajlara git')
    messages = db.veli_haber_liste(oid)
    results = db.lgs_denemeler(oid,30)
    for row in results:
        stamp = max((h['zaman'] for h in messages if h.get('sonuc_id')==row['id']),default=row['tarih'])
        add(f"sonuc-{row['id']}",'sonuc',row['ad'],f"{row['net']} net · Sınav tarihi: {row['tarih']} · Derslere göre ayrıntılar hazır.",
            stamp,status='Sonuç hazır',href=url_for('veli_sonuclar',sonuc=row['id']),action='Sonucu incele')
    result_ids = {r['id'] for r in results}
    for row in messages:
        if row.get('sonuc_id') in result_ids or any(n['not_metni'] in row['metin'] for n in notes):
            continue
        if row['tur']=='odev' and row['metin'].startswith('Yeni ödev') and any(h['baslik'] in row['metin'] for h in homework):
            continue
        add(f"haber-{row['id']}",'mesaj','Öğretmenden güncelleme',row['metin'],row['zaman'],
            status='Yeni' if not row['goruldu'] else 'Bilgilendirme',href='#mesajlar',action='Mesajlara git')
    if not lgs:
        week=(date.today()-timedelta(days=date.today().weekday())).isoformat()
        info=db.haftalik_odev_bilgi_getir(sid,week)
        record=db.haftalik_takip_sinif(sid,week).get(oid,{})
        text=record.get('odev_not') or info.get('aciklama')
        if text:
            status={'tam':'Öğretmen onayladı','eksik':'Eksikleri tamamlayın','yok':'Yapılmadı'}.get(record.get('odev_durum'),
                   'Öğretmen onayı bekleniyor' if record.get('odev_bildirim')=='yaptim' else 'Yapılması bekleniyor')
            add('hafta-odev','gorev',record.get('odev_ders') or info.get('ders') or 'Haftanın ödevi',text,
                record.get('guncelleme') or info.get('guncelleme') or week,record.get('ogretmen_adi'),status,'#hafta','Ödevi incele',
                pending=not record.get('odev_durum') and record.get('odev_bildirim')!='yaptim')
        if record.get('kitap_adi'):
            add('hafta-kitap','gorev','Okuma kitabı',record['kitap_adi'],record.get('guncelleme') or week,
                record.get('ogretmen_adi'),'Okundu' if record.get('kitap_okuma')=='okudu' else 'Okunması bekleniyor',
                url_for('veli_kitap_okuma'),'Kitabı incele',pending=record.get('kitap_okuma')!='okudu')
    items.sort(key=lambda x:(x['stamp'],x['key']),reverse=True)
    return dict(items=items, pending=sum(x['pending'] for x in items),
                results=sum(x['kind']=='sonuc' for x in items), unread=sum(not h['goruldu'] for h in messages))
