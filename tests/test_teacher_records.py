import json
import re
import unittest
from html import unescape
from test_app_workflows import w,d
import lgs_optik as optik


class TeacherRecords(unittest.TestCase):
    def setUp(self):
        self.t=next(t for t in d.tum_ogretmenler() if t['yetki']=='tam')
        self.c=w.app.test_client()
        with self.c.session_transaction() as s:s.update(ogretmen_id=self.t['id'],ogretmen_adi=self.t['ad_soyad'],ogretmen_yetki='tam')
        con=d._conn()
        self.student=dict(con.execute("SELECT o.* FROM ogrenciler o JOIN siniflar s ON s.id=o.sinif_id WHERE s.sinif_adi='6/A' LIMIT 1").fetchone())
        con.close()
        self.assertEqual(self.c.get('/kayitlarim').status_code,200)
        with self.c.session_transaction() as s:self.csrf=s['records_csrf']

    def note(self):
        d.ogretmen_notu_ekle(self.student['id'],self.t['id'],'Record editor test',False)
        con=d._conn();rid=con.execute('SELECT MAX(id) FROM ogretmen_notlari').fetchone()[0];con.close()
        return rid

    def version(self,path):
        r=self.c.get(path);self.assertEqual(r.status_code,200)
        return re.search('name="version" value="([^"]+)"',r.get_data(as_text=True))[1]

    def post(self,path,**data):
        return self.c.post(path,data=dict(csrf=self.csrf,version=self.version(path),**data))

    def latest(self):
        con=d._conn();bid=con.execute('SELECT MAX(id) FROM ogretmen_kayit_yedek WHERE owner=?',(self.t['id'],)).fetchone()[0];con.close();return bid

    def restore(self,bid):return self.c.post('/kayitlarim/geri-al/'+str(bid),data=dict(csrf=self.csrf),follow_redirects=True)

    def test_note_edit_delete_and_recovery(self):
        rid=self.note();path=f'/kayitlarim/not/{rid}'
        self.assertEqual(self.post(path,action='save',not_metni='Changed note',tur='',veliye_acik='0').status_code,302)
        edit=self.latest()
        self.assertIn('Changed note',self.c.get(path).get_data(as_text=True))
        self.assertEqual(self.post(path,action='delete',confirm='yes').status_code,302)
        deletion=self.latest()
        self.assertEqual(self.c.get(path).status_code,404)
        self.assertIn('geri yüklendi',self.restore(deletion).get_data(as_text=True))
        self.assertIn('Changed note',self.c.get(path).get_data(as_text=True))
        self.restore(edit)
        self.assertIn('Record editor test',self.c.get(path).get_data(as_text=True))

    def test_permissions_csrf_confirm_and_conflict(self):
        rid=self.note();path=f'/kayitlarim/not/{rid}'
        self.assertEqual(self.c.post(path,data=dict(action='delete',confirm='yes')).status_code,400)
        self.assertEqual(self.post(path,action='delete').status_code,400)
        stale=self.version(path)
        self.post(path,action='save',not_metni='A newer note',tur='',veliye_acik='0')
        self.assertEqual(self.c.post(path,data=dict(csrf=self.csrf,version=stale,action='delete',confirm='yes')).status_code,400)
        other=w.app.test_client()
        t=next(t for t in d.tum_ogretmenler() if t['yetki']=='tam' and t['id']!=self.t['id'])
        with other.session_transaction() as s:s.update(ogretmen_id=t['id'],ogretmen_yetki='tam')
        self.assertEqual(other.get(path).status_code,404)
        self.assertEqual(w.app.test_client().get(path).status_code,302)
        self.assertEqual(self.c.get('/kayitlarim/rehber-not/1').status_code,403)
        self.assertEqual(self.c.get('/islem-gecmisi').status_code,200)
        con=d._conn()
        action=con.execute("SELECT id FROM ogretmen_islem WHERE yol=? ORDER BY rowid DESC LIMIT 1",(path,)).fetchone()
        con.close()
        self.assertIsNotNone(action)
        r=self.c.post('/islem-gecmisi/'+action[0]+'/geri-al',follow_redirects=True)
        self.assertIn('Kayıtlarım ekranındaki geçmişten',r.get_data(as_text=True))

    def test_answer_key_recalculates_and_restore_detects_new_response(self):
        eid=optik.sinav_ekle('Editable exam','2026-10-17','test.pdf',['A','B'],self.t['id'],sinif_id=self.student['sinif_id'])
        optik.sonuc_kaydet(eid,self.student['id'],['A','C'])
        path=f'/kayitlarim/ev-testi/{eid}'
        self.assertEqual(self.post(path,action='save',ad='Edited exam',tarih='2026-10-17',ders='',cevaplar='A C').status_code,302)
        bid=self.latest()
        self.assertEqual(optik.sonuc_getir(eid,self.student['id'])['dogru'],2)
        self.assertEqual(self.post(path,action='save',ad='Edited exam',tarih='2026-10-17',ders='',cevaplar='A C D').status_code,400)
        another=next(s for s in d.sinif_ogrencileri(self.student['sinif_id']) if s['id']!=self.student['id'])
        optik.sonuc_kaydet(eid,another['id'],['A','C'])
        self.assertIn('yeni bir sonuç',self.restore(bid).get_data(as_text=True))
        self.assertEqual(optik.sonuc_getir(eid,self.student['id'])['dogru'],2)

    def test_delete_exam_restores_all_answers(self):
        eid=optik.sinav_ekle('Delete exam','2026-10-17','test.pdf',['A'],self.t['id'],sinif_id=self.student['sinif_id'])
        optik.sonuc_kaydet(eid,self.student['id'],['A'])
        self.post(f'/kayitlarim/ev-testi/{eid}',action='delete',confirm='yes')
        self.assertIsNone(optik.sinav_getir(eid))
        self.restore(self.latest())
        self.assertEqual(optik.sonuc_getir(eid,self.student['id'])['dogru'],1)

    def test_book_change_clears_old_reading_decision(self):
        sid=self.student['sinif_id'];oid=self.student['id'];week='2032-02-02'
        d.haftalik_takip_metin(sid,oid,week,'kitap_adi','Old book',self.t['id'])
        d.haftalik_takip_isaretle(sid,oid,week,'kitap_okuma','okudu',self.t['id'])
        con=d._conn();rid=con.execute('SELECT id FROM haftalik_takip WHERE ogrenci_id=? AND hafta_basi=?',(oid,week)).fetchone()[0];con.close()
        r=self.post(f'/kayitlarim/haftalik/{rid}',action='save',kitap_adi='New book',kitap_sayfa='100',kitap_okuma='okudu',kitap_getirme='',odev_durum='',odev_ders='',odev_not='',odev_karar_not='')
        self.assertEqual(r.status_code,302)
        self.assertEqual(d.haftalik_takip_sinif(sid,week)[oid]['kitap_okuma'],'')

    def test_homework_deletion_and_scores_restore(self):
        result=d.odev_ekle(self.student['sinif_id'],self.t['id'],'Delete homework','Details','2030-01-01')
        oid=result['odev_id'];d.odev_tamamla(oid,self.student['id'],self.t['id'])
        con=d._conn();before=con.execute('SELECT xp FROM gelisim_puan WHERE ogrenci_id=?',(self.student['id'],)).fetchone()[0];con.close()
        self.assertEqual(self.post(f'/kayitlarim/odev/{oid}',action='delete',confirm='yes').status_code,302)
        con=d._conn();after=con.execute('SELECT xp FROM gelisim_puan WHERE ogrenci_id=?',(self.student['id'],)).fetchone()[0];con.close()
        self.assertEqual(after,before-8)
        self.restore(self.latest())
        self.assertIsNotNone(d.odev_detay(oid))
        con=d._conn();restored=con.execute('SELECT xp FROM gelisim_puan WHERE ogrenci_id=?',(self.student['id'],)).fetchone()[0];con.close()
        self.assertEqual(restored,before)

    def test_counselor_own_notes_only(self):
        t=next(t for t in d.tum_ogretmenler() if t['yetki']=='rehber')
        with self.c.session_transaction() as s:s.update(ogretmen_id=t['id'],ogretmen_adi=t['ad_soyad'],ogretmen_yetki='rehber')
        self.assertEqual(self.c.get('/kayitlarim').status_code,200)
        self.assertEqual(self.c.get('/kayitlarim?tur=not').status_code,403)
        con=d._conn()
        with con:
            cid=con.execute("INSERT INTO rehber_takip(owner,student_id,topic,goal,created,updated) VALUES(?,?,?,?,?,?)",(t['id'],self.student['id'],'Diğer','Private goal','2030-01-01','2030-01-01')).lastrowid
            nid=con.execute('INSERT INTO rehber_not(case_id,body,created) VALUES(?,?,?)',(cid,'Private note','2030-01-01')).lastrowid
        con.close()
        self.assertEqual(self.post(f'/kayitlarim/rehber-not/{nid}',action='save',body='Corrected private note').status_code,302)
        self.assertEqual(self.post(f'/kayitlarim/rehber-takip/{cid}',action='delete',confirm='yes').status_code,302)
        self.assertEqual(self.c.get(f'/kayitlarim/rehber-not/{nid}').status_code,404)

if __name__=='__main__':unittest.main()
