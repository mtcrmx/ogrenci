import sys

def add_api(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    new_api = """
@app.route("/api/ogrenci/mac/2d_data", methods=["POST"])
@ogrenci_giris_zorunlu
def api_ogrenci_mac_2d_data():
    oid = int(session["ogrenci_id"])
    o = _ogrenci_bul(oid)
    if not o:
        return jsonify({"ok": False}), 404
        
    veri = request.get_json(silent=True) or {}
    rakip_sinif_id = veri.get("rakip_sinif_id")
    spor = veri.get("spor", "futbol")
    
    bizim_sinif_id = int(o["sinif_id"])
    
    bizim_taktik = spor_taktik_yukle(bizim_sinif_id, spor) if spor == "voleybol" else taktik_yukle(bizim_sinif_id)
    rakip_taktik = spor_taktik_yukle(rakip_sinif_id, spor) if spor == "voleybol" else taktik_yukle(rakip_sinif_id)
    
    biz_kadro = sinif_ogrencileri(bizim_sinif_id)
    rak_kadro = sinif_ogrencileri(rakip_sinif_id)
    
    def extract_players(taktik, kadro, takim_renk):
        players = []
        if not taktik or "oyuncular" not in taktik:
            return players
        for pid, p in taktik["oyuncular"].items():
            ogr = next((x for x in kadro if str(x["id"]) == str(pid)), None)
            if ogr:
                xp = ogr.get("tik_sayisi", 0)
                ovr = min(99, 50 + int(xp * 0.8))
                players.append({
                    "id": ogr["id"],
                    "ad": ogr["ad_soyad"].split()[0],
                    "numara": p.get("mevki_no", 10),
                    "rol": p.get("rol", ""),
                    "baseX": p.get("x", 50),
                    "baseY": p.get("y", 50),
                    "ovr": ovr,
                    "renk": taktik.get("renk", takim_renk)
                })
        return players
        
    bizim_oyuncular = extract_players(bizim_taktik, biz_kadro, "#3b82f6")
    rakip_oyuncular = extract_players(rakip_taktik, rak_kadro, "#ef4444")
    
    return jsonify({
        "ok": True,
        "bizim_takim": {"ad": o["sinif_adi"], "oyuncular": bizim_oyuncular},
        "rakip_takim": {"ad": "Rakip Sınıf", "oyuncular": rakip_oyuncular}
    })

@app.route("/ogrenci/mac/saha_2d")
@ogrenci_giris_zorunlu
def ogrenci_mac_saha_2d():
    return render_template("mac_2d.html")
"""
    # Insert after api_ogrenci_mac_simule
    insert_marker = "return jsonify({\n        \"ok\": True,\n        \"bizim_skor\": bizim_skor,\n        \"rakip_skor\": rakip_skor,\n        \"anlatim\": \"\\n\".join(anlatim)\n    })"
    
    if insert_marker in text and "api_ogrenci_mac_2d_data" not in text:
        text = text.replace(insert_marker, insert_marker + "\n" + new_api)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        print("API added")
    else:
        print("Marker not found or already added")

add_api('web_app.py')
