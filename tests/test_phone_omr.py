import json, subprocess, tempfile, time, unittest
from pathlib import Path
import numpy as np
import cv2
from test_kamera_test import marked_form, media, CameraWorkflow

ROOT=Path(__file__).resolve().parents[1]

class NewOptic(unittest.TestCase):
    def test_phone_and_server_read_new_layouts(self):
        for count,choices in [(14,'ABCD'),(40,'ABCDE'),(60,'ABCD'),(90,'ABCDE')]:
            with self.subTest(count=count):
                marks=[choices[i%len(choices)] for i in range(count)];marks[4]=''
                im=marked_form(dict(ad='New optical test',soru_sayisi=count),dict(ad_soyad='Sample Student',sinif_adi='8/A',ogr_no=1),'new-form-token',marks,extra=1 if count==90 else None,choices=choices,version=2)
                if count==90:marks[0]=''
                if count==60:
                    h,w=im.shape[:2]
                    src=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
                    dst=np.float32([[60,30],[w-70,0],[w-20,h-60],[10,h-10]])
                    im=cv2.warpPerspective(im,cv2.getPerspectiveTransform(src,dst),(w,h),borderValue=(255,255,255))
                _,jpg=cv2.imencode('.jpg',im)
                result=media.read_form(jpg.tobytes(),count,choices)
                self.assertEqual(result['answers'],marks)
                self.assertEqual(result['uncertain'],[1] if count==90 else [])
                # Mobile-sized photo, shaded and rotated.
                scale=1600/max(im.shape[:2]);im=cv2.resize(im,None,fx=scale,fy=scale)
                im=np.uint8(im*np.linspace(.7,1,im.shape[1])[None,:,None])
                im=cv2.rotate(im,cv2.ROTATE_90_CLOCKWISE)
                rgba=cv2.cvtColor(im,cv2.COLOR_RGB2RGBA)
                with tempfile.TemporaryDirectory() as td:
                    raw=Path(td)/'pixels.bin';raw.write_bytes(rgba.tobytes())
                    script="""const fs=require('fs'),reader=require(process.argv[1]),qr=require(process.argv[2]);
const bytes=new Uint8ClampedArray(fs.readFileSync(process.argv[3]));const t=performance.now();
const r=reader.read(bytes,Number(process.argv[4]),Number(process.argv[5]),Number(process.argv[6]),process.argv[7],qr);
console.log(JSON.stringify({answers:r.answers,uncertain:r.uncertain,token:r.token,ms:performance.now()-t}));"""
                    output=subprocess.check_output(['node','-e',script,str(ROOT/'static/phone_omr.js'),str(ROOT/'static/vendor/jsqr/jsQR.js'),str(raw),str(im.shape[1]),str(im.shape[0]),str(count),choices],text=True)
                    local=json.loads(output)
                    self.assertEqual(local['answers'],marks)
                    self.assertEqual(local['uncertain'],[1] if count==90 else [])
                    self.assertEqual(local['token'],'new-form-token')
                    print('Phone algorithm',count,'questions:',round(local['ms']), 'ms')

class LocalScanSecurity(CameraWorkflow):
    def test_local_review_required_and_token_bound(self):
        self.form()
        import kamera_test as kt
        con=kt.connect();token=con.execute('SELECT token FROM kamera_form WHERE sinav_id=?',(self.eid,)).fetchone()[0];con.close()
        payload=dict(token=token,answers=self.exam['cevaplar'],uncertain=[])
        response=self.c.post(f'/yaprak-kamera/{self.eid}/telefonda-oku',data={'csrf':self.csrf,'reading':json.dumps(payload)})
        self.assertEqual(response.status_code,200,response.data)
        self.assertTrue(response.json['local'])
        self.assertEqual(self.save(response.json).status_code,400)
        self.assertEqual(self.save(response.json,reviewed='yes').status_code,200)
        payload['token']='other-test-token'
        self.assertEqual(self.c.post(f'/yaprak-kamera/{self.eid}/telefonda-oku',data={'csrf':self.csrf,'reading':json.dumps(payload)}).status_code,400)
        payload['answers']=['X']*14
        self.assertEqual(self.c.post(f'/yaprak-kamera/{self.eid}/telefonda-oku',data={'csrf':self.csrf,'reading':json.dumps(payload)}).status_code,400)

if __name__=='__main__':unittest.main()
