code_to_append = """
# ══════════════════════════════════════════════════════════════════════════
# ÖDEV TAKİBİ EKRANLARI
# ══════════════════════════════════════════════════════════════════════════

@app.route("/odevler", methods=["GET", "POST"])
@login_required
def odevler():
    oid = session["ogretmen_id"]
    from database import odev_olustur, odevleri_getir
    
    if request.method == "POST":
        sinif_id = int(request.form.get("sinif_id", 0))
        ders_adi = request.form.get("ders_adi", "").strip()
        tema_adi = request.form.get("tema_adi", "").strip()
        
        if sinif_id and ders_adi and tema_adi:
            odev_id = odev_olustur(oid, sinif_id, ders_adi, tema_adi)
            return redirect(url_for('odev_detay', odev_id=odev_id))
            
    odev_listesi = odevleri_getir(oid)
    return render_template("odevler.html", odevler=odev_listesi, siniflar=ogretmen_siniflari(oid), yetki=session.get('ogretmen_yetki'))

@app.route("/odev/<int:odev_id>", methods=["GET", "POST"])
@login_required
def odev_detay(odev_id):
    oid = session["ogretmen_id"]
    from database import odev_detay_getir, odev_durum_guncelle
    
    detay = odev_detay_getir(odev_id, oid)
    if not detay:
        return redirect(url_for('odevler'))
        
    if request.method == "POST":
        for key, val in request.form.items():
            if key.startswith("durum_"):
                ogr_id = int(key.split("_")[1])
                odev_durum_guncelle(odev_id, ogr_id, val)
        return redirect(url_for('odev_detay', odev_id=odev_id))
        
    return render_template("odev_detay.html", odev=detay["odev"], ogrenciler=detay["ogrenciler"], yetki=session.get('ogretmen_yetki'))
"""

with open('c:/Users/METE/OneDrive/Belgeler/GitHub/ogrenci-takip/web_app.py', 'a', encoding='utf-8') as f:
    f.write(code_to_append)

print("web_app.py appended successfully.")
