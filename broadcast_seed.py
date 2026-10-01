"""Transcribed from the school's dated 2026–2027 duty PDF, pages 1–5.

These are date-specific assignments, not a repeating rota. H means a holiday.
"""
from datetime import date, timedelta

NAMES = {
    'F': 'FUNDA KİRAZ', 'M': 'MERVE TÜRKEL', 'H': 'HAVVA ÖZDEMİR',
    'I': 'İFTARİYE ARSLAN', 'N': 'NESLİHAN ÇAKMAK', 'C': 'CEMİL KUYUMCU',
    'O': 'ÖZGE KILIÇ', 'K': 'CANTEKİN KURTOĞLU', 'E': 'ELİF DEDEOĞLU',
    'A': 'AYTAÇ ATMACA', 'S': 'SATI ERGİN',
}
# Each row: Monday date, first floor, second floor, garden (Monday → Friday).
WEEKS = (
    ('2026-09-14', 'FHCKA', 'MIOES', 'CNFIE'),
    ('2026-09-21', 'MNOES', 'FHCKA', 'HIAMK'),
    ('2026-09-28', 'FICKA', 'MNOES', 'OHSNC'),
    ('2026-10-05', 'MHOES', 'FICKA', 'ENFHI'),
    ('2026-10-12', 'FNCKA', 'MHOES', 'OINMK'),
    ('2026-10-19', 'MIOES', 'FNCKA', 'CHSAI'),
    ('2026-10-26', 'FHCTA', 'MIOTS', 'ENFTK'),
    ('2026-11-02', 'MNOKS', 'FHCEA', 'EIHMC'),
    ('2026-11-09', 'FICEA', 'MNOKS', 'OHSAK'),
    ('2026-11-23', 'MHOKS', 'FICEA', 'CNFMI'),
    ('2026-11-30', 'FNCEA', 'MHOKS', 'EINHK'),
    ('2026-12-07', 'MIOKS', 'FNCEA', 'OHSAM'),
    ('2026-12-14', 'FHCEA', 'MIOKS', 'CNFIE'),
    ('2026-12-21', 'MNOKS', 'FHCEA', 'HINAK'),
    ('2026-12-28', 'FICET', 'MNOKT', 'OHSAT'),
    ('2027-01-04', 'MHOKA', 'FICES', 'ENSMI'),
    ('2027-01-11', 'FNCES', 'MHOKA', 'HINFK'),
    ('2027-01-18', 'MIOKA', 'FNCES', 'OHSAN'),
)
CLOSED = {'2026-10-29': '29 Ekim Cumhuriyet Bayramı', '2027-01-01': 'Yılbaşı'}
for day in range(5):
    CLOSED[(date(2026, 11, 16) + timedelta(days=day)).isoformat()] = '1. dönem ara tatili'


def duty_seed():
    result = {}
    for monday, *floors in WEEKS:
        assert all(len(row) == 5 for row in floors)
        for day in range(5):
            stamp = (date.fromisoformat(monday) + timedelta(days=day)).isoformat()
            if stamp in CLOSED:
                continue
            result[stamp] = [NAMES[row[day]] for row in floors]
    return result
