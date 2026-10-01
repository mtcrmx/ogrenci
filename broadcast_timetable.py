"""TV timetable transcribed from the supplied weekly teacher/class image.

Merged coloured cells span multiple lessons. The source has no subject names;
only teacher and class assignments are displayed, without guessing subjects.
"""
ROWS = (
    ('ADEM AKGÜL', '8B ... 8A 8B 8B', '.... 8A . 8B', '7A 7A 5A . 8B ..', '.. 8B 8B ...', '.......'),
    ('CEMİL KUYUMCU', '6B 6A 6A 7A 5A . 7A', '.......', '7B 8A 6A 7B 5B . 6B', '.......', '7A . 7B .. 8B 6B'),
    ('ELİF DEDEOĞLU', '5A 5A 8B 8B . 6A 6A', '7B . 8B 8B 7B 7B 6B', '.......', '6B 6B 6A 7A 7A ..', '7B 7B 5A 7A 7A ..'),
    ('BEYZANUR AKKIŞ', '7B 7B . 6B 6B 7A 6B', '.... 6B 5B 5B', '6B 6B 7B 7A 7A 5B 5B', '7A 7A 6B . 5B 7B 7B', '.......'),
    ('FUNDA KİRAZ', '8A 8A 6B 6A 5B 6B 5A', '6B 6B 7A 7B ...', '5A 5A 7A 6A 6A 7B 7B', '5B 5B 7A 7B 6A 8B 8B', '.......'),
    ('HAVVA ÖZDEMİR', '. 8B 5B 5A . 5A .', '. 6A 6B 5A . 8A .', '. 7B 5B 5B . 7A .', '. 8B 7B 6A . 7A .', '. 8A 7A 6B 5A 5B .'),
    ('İFTARİYE ARSLAN', '.......', '8A 8A .. 8B 8B 8A', '6A 6A 8B 8B 5A 5A 8A', '8A 8A 5A 5A 8B 6B 6B', '6A 6A . 8A 6B 6B 8B'),
    ('MERVE TÜRKEL', '7A 7A 7A . 7B 5B 5B', '... 5B 7A 7A 7B', '.......', '7B 7B 5B 5B 7B . 7A', '... 5B 5B 7B 7B'),
    ('METEHAN CÜCEN', '.... 8B . 8A', '.......', '...... 8B', '8B . 8A ....', '8A ......'),
    ('NESLİHAN ÇAKMAK', '.... 6A 8A .', '8B 8B 6A . 6A 5A 5A', '8B 8B 8A 8A . 6A 6A', '6A 6A . 8A 8A 5A 5A', '. 8B 6A 5A ...'),
    ('ÖZGE KILIÇ', '.......', '.......', '8A .. 5A 7B 8B 7A', '.......', '8B 7A 8A 7B ...'),
    ('SATI ERGİN', '.. 7B 7B ...', '7A 7A 8A 8A ...', '5B 5B 6B 6B ...', '.......', '5A 5A 8B 8B 8B 6A 6A'),
    ('SEDAT KALENDER', '6A 6B 5A 5B ...', '6A 5A 5B 6B ...', '.......', '.......', '.......'),
    ('CANTEKİN KURTOĞLU', '.......', '.... 5A 6A 6A', '.... 6B 6B 5A', '5A 5A . 6B 6B 6A 6A', '6B 6B 6B 6A 6A 5A 5A'),
    ('AYTAÇ ATMACA', '.... 7A 7B 7B', '5B 5B 7B 7A ...', '.......', '.......', '5B 5B 5B . 7B 7A 7A'),
    ('EMİNE KILIÇ', '5B 5B 8A 8A ...', '.......', '.......', '.......', '.... 8A 8A 5B'),
    ('FATİH KOCATÜRK', '.......', '.......', '.... 8A 8A .', '..... 8A 8A', '...... 8A'),
    ('NURŞEN CÜCEN', '.......', '5A 7B 5A 6A 5B 6B 7A', '.......', '.... 5A 5B 5B', '.......'),
)


def timetable():
    result = []
    for teacher, *days in ROWS:
        for day, line in enumerate(days):
            cells = [cell for part in line.split() for cell in (list(part) if part.startswith('.') else [part])]
            assert len(cells) == 7, (teacher, day, cells)
            for number, cell in enumerate(cells, 1):
                if cell != '.':
                    result.append(dict(gun=day, ders_no=number, sinif_adi=cell[0]+'/'+cell[1],
                                       ogretmen_adi=teacher, ders_adi=''))
    return result
