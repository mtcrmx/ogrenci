"""Home-test access uses the exam date and Turkey's UTC+03:00 clock."""
from datetime import datetime, date, time, timedelta, timezone
from flask import has_request_context, session

TURKEY = timezone(timedelta(hours=3), 'Europe/Istanbul')


def now():
    return datetime.now(TURKEY)


def parent_request():
    return has_request_context() and bool(session.get('veli_ogrenci_id')) and not session.get('ogretmen_id')


def state(exam, at=None):
    if exam.get('kaynak') == 'kamera':
        return dict(home=False, open=True, released=True, message='', start=None, end=None, remaining=None)
    current = (at or now()).astimezone(TURKEY)
    try:
        day = date.fromisoformat(exam.get('tarih') or '')
    except (ValueError, TypeError):
        return dict(home=True, open=False, released=False, message='Test tarihi geçerli değil. Öğretmeninizle görüşün.', start=None, end=None, remaining=None)
    start = datetime.combine(day, time(19), TURKEY)
    end = datetime.combine(day, time(21), TURKEY)
    opened = start <= current < end
    released = current >= end
    label = day.strftime('%d.%m.%Y')
    message = (f'{label} · Türkiye saatiyle 19.00–21.00. Testi 21.00’den önce bitirip gönderin. Cevap anahtarı 21.00’de açılır.' if opened
               else 'Çözüm süresi sona erdi. Sorular kapalı; cevap anahtarı ve sonuçlar açık.' if released
               else f'Sorular {label} tarihinde Türkiye saatiyle 19.00–21.00 arasında açılır. Cevap anahtarı aynı gün 21.00’de açılır.')
    return dict(home=True, open=opened, released=released, message=message, start=start.isoformat(), end=end.isoformat(),
                remaining=max(0, (end-current).total_seconds()) if opened else None)


def released(exam):
    return state(exam)['released']


def parent_exam(exam):
    window=state(exam)
    exam['window']=window
    # Aggregate totals are allowed immediately, but no answer-by-answer clues.
    exam['sonuclar']=[]
    if not window['released']:
        exam['cevaplar']=[]
        exam.pop('analiz',None)
        if exam.get('sonuc'):
            exam['sonuc']={k:exam['sonuc'][k] for k in ('dogru','yanlis','bos','net')}
    return exam
