from unittest.mock import patch
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from html import unescape
import re
import pytest
from test_app_workflows import w, d
import simple_ui as ui
import school_broadcast as tv
import veli_auth


@pytest.fixture
def teacher():
    con=d._conn()
    row=dict(con.execute("SELECT * FROM ogretmenler WHERE COALESCE(yetki,'tam')='tam' ORDER BY id LIMIT 1").fetchone())
    con.close()
    c=w.app.test_client()
    with c.session_transaction() as s:
        s.update(ogretmen_id=row['id'],ogretmen_yetki='tam')
    return c


def test_weighted_chart_empty_single_clamped_and_input_preserved():
    assert ui.chart([])['percent'] is None
    rows=[dict(tarih='2026-10-01',dogru=1,soru_sayisi=1,yanlis=0),
          dict(tarih='2026-10-02',dogru=0,soru_sayisi=9,yanlis=9)]
    result=ui.chart(rows)
    assert result['percent']==10
    assert rows[1]['yanlis']==9 and 'cy' not in rows[1]
    assert ui.chart(rows[:1])['points'][0]['cx']==50
    clipped=ui.chart([dict(tarih='2026-10-01',dogru=100,soru_sayisi=5),dict(tarih='2026-10-02',dogru=-1,soru_sayisi=5)])
    assert all(0<=p['percent']<=100 and 5<=p['cy']<=95 for p in clipped['points'])


def test_explicit_selection_repeated_navigation_and_denied_ids(teacher):
    classes=[dict(id=901,sinif_adi='5/A'),dict(id=902,sinif_adi='8/A')]
    def students(sid): return [dict(id=sid+1000,ad_soyad='SYNTHETIC CHILD '+str(sid),sinif_id=sid)]
    with patch.object(ui,'yetkili',return_value=False),patch.object(d,'ogretmen_siniflari',return_value=classes),patch.object(d,'sinif_ogrencileri',side_effect=students),patch.object(ui.sinav_okuyucu,'birlesik_sonuclar',return_value=[]) as read:
        first=teacher.get('/analizler')
        assert first.status_code==200
        read.assert_not_called()
        assert 'SYNTHETIC CHILD' not in first.text
        for _ in range(2):
            response=teacher.get('/analizler?sinif=901&sinif=902&start=2026-10-01&end=2026-10-24&source=ev')
            assert response.status_code==200
            assert '5/A · Evde sorular' in response.text and '8/A · Evde sorular' in response.text
            detail=teacher.get('/analizler?sinif=901&sinif=902&ogrenci=1901&start=2026-10-01&source=ev')
            assert detail.status_code==200
            back=unescape(re.search(r'class="simple-back" href="([^"]+)"',detail.text)[1])
            assert parse_qs(urlparse(back).query)==dict(sinif=['901','902'],start=['2026-10-01'],source=['ev'])
            assert teacher.get(back).status_code==200
        assert teacher.get('/analizler?sinif=999').status_code==403
        assert teacher.get('/analizler?sinif=901&ogrenci=1902').status_code==403
        assert teacher.get('/analizler?sinif=901&start=bad').status_code==400
        assert teacher.get('/analizler?sinif=901&start=2026-10-24&end=2026-10-01').status_code==400
        assert teacher.get('/analizler?sinif=abc').status_code==400


def test_parent_uses_session_identity_and_never_roster():
    con=d._conn();student=dict(con.execute('SELECT * FROM ogrenciler ORDER BY id LIMIT 1').fetchone());con.close()
    con=veli_auth.connect()
    old=con.execute('SELECT * FROM veli_credentials WHERE ogrenci_id=?',(student['id'],)).fetchone()
    con.execute("INSERT INTO veli_credentials(ogrenci_id,password_hash,auth_version) VALUES(?,?,?) ON CONFLICT(ogrenci_id) DO UPDATE SET auth_version=excluded.auth_version",(student['id'],'test-only','simple-ui-test'))
    con.commit();con.close()
    client=w.app.test_client()
    try:
        with client.session_transaction() as s:s.update(veli_ogrenci_id=student['id'],veli_auth_version='simple-ui-test')
        with patch.object(ui.sinav_okuyucu,'birlesik_sonuclar',return_value=[]) as read:
            response=client.get('/veli/analizler?ogrenci=999999&sinif=999999')
            assert response.status_code==200
            read.assert_called_once_with({student['id']},teacher=None)
            assert 'Öğrenci ayrıntısı' not in response.text
            assert 'Cache-Control' in response.headers
        assert client.get('/analizler?sinif=1').status_code==302
        assert client.post('/lgs',data={'islem':'optik_ekle'}).status_code==302
        assert client.get('/yayin/yonetim').status_code in (302,403)
        with client.session_transaction() as s:s.clear()
        assert client.get('/veli/analizler').status_code==302
    finally:
        con=veli_auth.connect()
        if old:con.execute('UPDATE veli_credentials SET auth_version=? WHERE ogrenci_id=?',(old['auth_version'],student['id']))
        else:con.execute('DELETE FROM veli_credentials WHERE ogrenci_id=?',(student['id'],))
        con.commit();con.close()


def test_filters_and_class_sources_are_separate():
    students=[dict(id=1,sinif_id=5),dict(id=2,sinif_id=8)]
    classes=[dict(id=5,sinif_adi='5/A'),dict(id=8,sinif_adi='8/A')]
    rows=[dict(ogrenci_id=1,source='deneme',ders='Matematik',tarih='2026-10-01',dogru=2,soru_sayisi=10),
          dict(ogrenci_id=2,source='deneme',ders='Matematik',tarih='2026-10-02',dogru=8,soru_sayisi=10)]
    with patch.object(ui.sinav_okuyucu,'birlesik_sonuclar',return_value=rows):
        panels,_=ui.panels(students,classes,dict(start='',end='',source='deneme',course=''),1)
        assert [p['percent'] for p in panels]==[20,80]
        panels,_=ui.panels(students,classes,dict(start='2026-10-02',end='',source='deneme',course='Matematik'),1)
        assert [p['percent'] for p in panels]==[None,80]


def test_home_no_kpis_and_tv_has_no_student_leaders(teacher):
    response=teacher.get('/dashboard')
    assert response.status_code==200
    assert 'Bugün ne yapmak istersiniz?' in response.text
    assert 'dash-kpis' not in response.text
    with w.app.test_request_context('/'):
        with patch.object(tv,'net_leaders',side_effect=AssertionError('Student ranking must not be queried')):
            data=tv.payload()
            assert 'net_liderleri' not in data
            assert {'saatler','program','icerikler','takvim'}<=data.keys()


def test_parent_rank_contains_only_own_row():
    import lgs_ranking
    con=d._conn()
    students=con.execute('SELECT id FROM ogrenciler ORDER BY id LIMIT 2').fetchall()
    try:
        data=lgs_ranking.build(con,{},own_id=students[0]['id'])
        assert len(data['rows'])<=1
        assert all(row['kendi'] for row in data['rows'])
        assert data['course_stats']==[]
    finally:
        con.close()


def test_word_upload_uses_existing_converter_and_rejects_bad_docx(teacher):
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas
    import kamera_media
    out=BytesIO();canvas=Canvas(out);canvas.drawString(20,700,'SYNTHETIC QUESTION');canvas.save()
    with patch.object(kamera_media,'convert_document',return_value=out.getvalue()) as convert:
        # Intentionally incomplete metadata: the established wizard retains its PDF on error.
        response=teacher.post('/lgs',data={'islem':'optik_ekle','pdf':(BytesIO(b'synthetic docx input'),'questions.docx')})
        assert response.status_code==422
        convert.assert_called_once_with(b'synthetic docx input','.docx')
        assert 'tmp_' in response.text
    response=teacher.post('/lgs',data={'islem':'optik_ekle','pdf':(BytesIO(b'invalid zip'),'bad.docx')})
    assert response.status_code==422
    assert 'Word belgesi okunamadı' in response.text
