"""8. sınıf LGS ders programı: Ekim önerileri ve çalışma defteri dersleri."""

TEMPO_AD = {
    "baslangic": "Başlangıç",
    "alisma": "Alışma",
    "siki": "Sıkı",
    "tempo": "Tempo",
}

LGS_AYLAR = (
    (10, "Ekim"),
    (11, "Kasım"),
    (12, "Aralık"),
    (1, "Ocak"),
    (2, "Şubat"),
    (3, "Mart"),
    (4, "Nisan"),
    (5, "Mayıs"),
    (6, "Haziran"),
)

DEFTER_DERSLER = (
    ("odev", "Ödev"),
    ("turkce", "Türkçe"),
    ("matematik", "Matematik"),
    ("fen", "Fen Bilimleri"),
    ("inkilap", "T.C. İnkılap Tarihi"),
    ("ingilizce", "İngilizce"),
    ("din", "Din Kültürü"),
)


def _b(ders: str, soru: int = 0, sure: str = "") -> dict:
    return {"ders": ders, "soru": int(soru or 0), "sure": sure}


def _hafta_ici(ana_dersler: tuple[str, ...], tekrar: str, paragraf: int, sure: str) -> list[dict]:
    return [
        _b("Günlük tekrar", sure=tekrar),
        _b("Paragraf", soru=paragraf),
        *(_b(ders, sure=sure) for ders in ana_dersler),
    ]


def _tempo_hafta_ici(ana_dersler: tuple[str, ...]) -> list[dict]:
    return [_b("Paragraf", soru=15), *(_b(ders, sure="50 dk") for ders in ana_dersler)]


def _cuma(tekrar: str, soru: int) -> list[dict]:
    # Belgedeki soru adedi belirli bir derse bağlı değil; ayrı hedef olarak tutulur.
    return [_b("Hafta tekrarı", sure=tekrar), _b("Soru hedefi", soru=soru)]


PROGRAM = {
    "baslangic": (
        _hafta_ici(("Matematik", "Din Kültürü"), "10-15 dk", 10, "30 dk"),
        _hafta_ici(("Fen Bilimleri", "İngilizce"), "10-15 dk", 10, "30 dk"),
        _hafta_ici(("Matematik", "T.C. İnkılap Tarihi"), "10-15 dk", 10, "30 dk"),
        _hafta_ici(("Türkçe", "Fen Bilimleri"), "10-15 dk", 10, "30 dk"),
        _cuma("35 dk", 60),
        [_b("Paragraf", 10), _b("Türkçe", 20), _b("Matematik", 20), _b("İngilizce", 10)],
        [_b("Paragraf", 10), _b("Fen Bilimleri", 20), _b("T.C. İnkılap Tarihi", 20), _b("Din Kültürü", 10)],
    ),
    "alisma": (
        _hafta_ici(("Matematik", "Din Kültürü"), "15-20 dk", 15, "35-40 dk"),
        _hafta_ici(("Fen Bilimleri", "İngilizce"), "15-20 dk", 15, "35-40 dk"),
        _hafta_ici(("Matematik", "T.C. İnkılap Tarihi"), "15-20 dk", 15, "35-40 dk"),
        _hafta_ici(("Türkçe", "Fen Bilimleri"), "15-20 dk", 15, "35-40 dk"),
        _cuma("45 dk", 75),
        [_b("Paragraf", 10), _b("Türkçe", 25), _b("Matematik", 25), _b("İngilizce", 20)],
        [_b("Paragraf", 10), _b("Fen Bilimleri", 25), _b("T.C. İnkılap Tarihi", 25), _b("Din Kültürü", 20)],
    ),
    "siki": (
        _hafta_ici(("Matematik", "T.C. İnkılap Tarihi", "Din Kültürü"), "15-20 dk", 15, "40-45 dk"),
        _hafta_ici(("Fen Bilimleri", "Türkçe", "İngilizce"), "15-20 dk", 15, "40-45 dk"),
        _hafta_ici(("Matematik", "Fen Bilimleri", "T.C. İnkılap Tarihi"), "15-20 dk", 15, "40-45 dk"),
        _hafta_ici(("Türkçe", "Matematik", "İngilizce"), "15-20 dk", 15, "40-45 dk"),
        _cuma("45 dk", 90),
        [_b("Paragraf", 20), _b("Türkçe", 40), _b("Matematik", 40), _b("İngilizce", 30)],
        [_b("Paragraf", 20), _b("Fen Bilimleri", 40), _b("T.C. İnkılap Tarihi", 40), _b("Din Kültürü", 30)],
    ),
    "tempo": (
        _tempo_hafta_ici(("Matematik", "Matematik", "Fen Bilimleri", "T.C. İnkılap Tarihi")),
        _tempo_hafta_ici(("Türkçe", "Matematik", "T.C. İnkılap Tarihi", "İngilizce")),
        _tempo_hafta_ici(("Fen Bilimleri", "Fen Bilimleri", "Matematik", "Din Kültürü")),
        _tempo_hafta_ici(("Türkçe", "Fen Bilimleri", "T.C. İnkılap Tarihi", "İngilizce")),
        _cuma("45 dk", 100),
        [_b("Paragraf", 25), _b("Matematik", 60), _b("T.C. İnkılap Tarihi", 50), _b("İngilizce", 35)],
        [_b("Paragraf", 20), _b("Türkçe", 50), _b("Fen Bilimleri", 50), _b("Din Kültürü", 30)],
    ),
}


def blok_metin(blok: dict) -> str:
    parca = [blok["ders"]]
    if blok.get("soru"):
        parca.append(f"{blok['soru']} soru")
    if blok.get("sure"):
        parca.append(blok["sure"])
    return " · ".join(parca)


def gun_plani(tempo: str, gun: int) -> list[dict]:
    if tempo not in PROGRAM or gun not in range(7):
        return []
    return PROGRAM[tempo][gun]
