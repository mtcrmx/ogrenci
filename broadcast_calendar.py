"""Recurring school observances; source: MEB EK-8, checked 1 October 2026.

https://meb.gov.tr/belirli-gun-ve-haftalar-cizelgesi/duyuru/11814
Month ordinal weeks use 1–7, 8–14, 15–21 as planning ranges. Schools can
override dates. Dates decided locally or by Diyanet are never guessed.
"""
from calendar import monthrange
from datetime import date, timedelta

# Month/day ranges are data, not statutory school closure dates.
FIXED = (
    ('hava', 'Uluslararası Temiz Hava Günü', 9, 7, 9, 7),
    ('gaziler', 'Gaziler Günü', 9, 19, 9, 19),
    ('sut', 'Dünya Okul Sütü Günü', 9, 28, 9, 28),
    ('hayvan', 'Hayvanları Koruma Günü', 10, 4, 10, 4),
    ('ahilik', 'Ahilik Kültürü Haftası', 10, 8, 10, 12),
    ('afet', 'Dünya Afet Azaltma Günü', 10, 13, 10, 13),
    ('bm', 'Birleşmiş Milletler Günü', 10, 24, 10, 24),
    ('cumhuriyet', 'Cumhuriyet Bayramı', 10, 29, 10, 29),
    ('kizilay', 'Kızılay Haftası', 10, 29, 11, 4),
    ('losemi', 'Lösemili Çocuklar Haftası', 11, 2, 11, 8),
    ('organ', 'Organ Bağışı ve Nakli Haftası', 11, 3, 11, 9),
    ('ataturk', 'Atatürk Haftası', 11, 10, 11, 16),
    ('afet-egitimi', 'Afet Eğitimi Hazırlık Günü', 11, 12, 11, 12),
    ('diyabet', 'Dünya Diyabet Günü', 11, 14, 11, 14),
    ('felsefe', 'Dünya Felsefe Günü', 11, 20, 11, 20),
    ('cocuk-haklari', 'Dünya Çocuk Hakları Günü', 11, 20, 11, 20),
    ('dis', 'Ağız ve Diş Sağlığı Haftası', 11, 21, 11, 27),
    ('ogretmen', 'Öğretmenler Günü', 11, 24, 11, 24),
    ('engelliler-gunu', 'Dünya Engelliler Günü', 12, 3, 12, 3),
    ('madenci', 'Dünya Madenciler Günü', 12, 4, 12, 4),
    ('kadin-secme', 'Türk Kadınına Seçme ve Seçilme Hakkının Verilişi', 12, 5, 12, 5),
    ('mevlana', 'Mevlana Haftası', 12, 7, 12, 17),
    ('yerli-mali', 'Tutum, Yatırım ve Türk Malları Haftası', 12, 12, 12, 18),
    ('akif', 'Mehmet Akif Ersoy’u Anma Haftası', 12, 20, 12, 27),
    ('kadin', 'Dünya Kadınlar Günü', 3, 8, 3, 8),
    ('bilim', 'Bilim ve Teknoloji Haftası', 3, 8, 3, 14),
    ('istiklal', 'İstiklâl Marşı’nın Kabulü ve Mehmet Akif Ersoy’u Anma Günü', 3, 12, 3, 12),
    ('tuketici', 'Tüketiciyi Koruma Haftası', 3, 15, 3, 21),
    ('sehit', 'Şehitler Günü', 3, 18, 3, 18),
    ('yasli', 'Yaşlılar Haftası', 3, 18, 3, 24),
    ('orman', 'Orman Haftası', 3, 21, 3, 26),
    ('su', 'Dünya Su Günü', 3, 22, 3, 22),
    ('tiyatro', 'Dünya Tiyatrolar Günü', 3, 27, 3, 27),
    ('kanser', 'Kanser Haftası', 4, 1, 4, 7),
    ('otizm', 'Dünya Otizm Farkındalık Günü', 4, 2, 4, 2),
    ('veri', 'Kişisel Verileri Koruma Günü', 4, 7, 4, 7),
    ('saglik', 'Dünya Sağlık Haftası', 4, 7, 4, 13),
    ('turizm', 'Turizm Haftası', 4, 15, 4, 22),
    ('cocuk', 'Ulusal Egemenlik ve Çocuk Bayramı', 4, 23, 4, 23),
    ('fikri', 'Dünya Fikrî Mülkiyet Günü', 4, 26, 4, 26),
    ('kut', 'Kût’ül Amâre Zaferi', 4, 29, 4, 29),
    ('is-guvenligi', 'İş Sağlığı ve Güvenliği Haftası', 5, 4, 5, 10),
    ('engelliler', 'Engelliler Haftası', 5, 10, 5, 16),
    ('muze', 'Müzeler Haftası', 5, 18, 5, 24),
    ('genclik', 'Atatürk’ü Anma, Gençlik ve Spor Bayramı', 5, 19, 5, 19),
    ('etik', 'Etik Günü', 5, 25, 5, 25),
    ('fetih', 'İstanbul’un Fethi', 5, 29, 5, 29),
    ('demokrasi', '15 Temmuz Demokrasi ve Millî Birlik Günü', 7, 15, 7, 15),
    ('zafer', 'Zafer Bayramı', 8, 30, 8, 30),
)


def containing_week(day):
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def weekday_in_month(year, month, weekday, occurrence):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday-first.weekday()) % 7 + (occurrence-1)*7)


def calendar_seed(year):
    items = []
    def add(key, title, start, end=None, planned=False):
        items.append(dict(id=f'takvim-{year}-{key}', baslik=title,
                          baslangic=start.isoformat(), bitis=(end or start).isoformat(),
                          aktif=1, planlama=planned, ozel=False))
    for key, title, month, day, last_month, last_day in FIXED:
        add(key, title, date(year, month, day), date(year, last_month, last_day))
    for key, title, month, week in (
        ('ilkogretim', 'İlköğretim Haftası', 9, 3),
        ('disleksi', 'Disleksi Haftası', 10, 1),
        ('enerji', 'Enerji Tasarrufu Haftası', 1, 2),
        ('girisim', 'Girişimcilik Haftası', 3, 1),
        ('bilisim', 'Bilişim Haftası', 5, 1),
        ('trafik', 'Trafik ve İlkyardım Haftası', 5, 1),
        ('vakif', 'Vakıflar Haftası', 5, 2),
        ('ogrenme', 'Hayat Boyu Öğrenme Haftası', 6, 1),
        ('cevre', 'Çevre ve İklim Değişikliği Haftası', 6, 2),
    ):
        add(key, title, date(year, month, (week-1)*7+1), date(year, month, week*7), True)
    add('ogrenciler', 'Öğrenciler Günü', date(year, 9, 21), planned=True)
    add('ilk-yardim', 'Dünya İlk Yardım Günü', weekday_in_month(year, 9, 5, 2))
    add('disleksi-gunu', 'Dünya Disleksi Günü', weekday_in_month(year, 10, 3, 1))
    add('anneler', 'Anneler Günü', weekday_in_month(year, 5, 6, 2))
    add('babalar', 'Babalar Günü', weekday_in_month(year, 6, 6, 3))
    for key, title, day in (
        ('insan-haklari', 'İnsan Hakları ve Demokrasi Haftası', date(year, 12, 10)),
        ('yesilay', 'Yeşilay Haftası', date(year, 3, 1)),
        ('turk-dunyasi', 'Türk Dünyası ve Toplulukları Haftası', date(year, 3, 21)),
        ('kutuphane', 'Kütüphaneler Haftası', weekday_in_month(year, 3, 0, 1) +
         timedelta(days=((monthrange(year, 3)[1]-weekday_in_month(year, 3, 0, 1).day)//7)*7)),
        ('vergi', 'Vergi Haftası', date(year, 2, monthrange(year, 2)[1])),
    ):
        add(key, title, *containing_week(day), planned=True)
    return sorted(items, key=lambda i: (i['baslangic'], i['baslik']))
