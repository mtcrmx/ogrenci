"""8. sınıf LGS ders programı: Ekim tempoları, aylar ve çalışma defteri dersleri."""

TEMPO_AD = {
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


def _gun_ici(birinci, ikinci, ucuncu, sure: str, soru: int) -> list[dict]:
    return [
        _b("Paragraf", 15),
        _b(birinci, sure=sure),
        _b(ikinci, sure=sure),
        _b(ucuncu, soru=soru, sure=sure),
    ]


def _alisma_siki(sure: str, paragraf: int, sozel: int, sayisal: int, dil: int) -> tuple:
    return (
        _gun_ici("Matematik", "Fen Bilimleri", "T.C. İnkılap Tarihi", sure, 75),
        _gun_ici("Türkçe", "Matematik", "İngilizce", sure, 75),
        _gun_ici("Fen Bilimleri", "Matematik", "Din Kültürü", sure, 75),
        _gun_ici("Türkçe", "Fen Bilimleri", "T.C. İnkılap Tarihi", sure, 75),
        [_b("Hafta tekrarı", sure="45 dk")],
        [
            _b("Paragraf", paragraf),
            _b("Türkçe", sozel),
            _b("Matematik", sayisal),
            _b("İngilizce", dil),
        ],
        [
            _b("Paragraf", paragraf),
            _b("Fen Bilimleri", sozel),
            _b("T.C. İnkılap Tarihi", sayisal),
            _b("Din Kültürü", dil),
        ],
    )


def _tempo_gun(a, b, c, d) -> list[dict]:
    return [
        _b("Paragraf", 15),
        _b(a, sure="50 dk"),
        _b(b, sure="50 dk"),
        _b(c, soru=100, sure="50 dk"),
        _b(d, sure="50 dk"),
    ]


PROGRAM = {
    "alisma": _alisma_siki("40-45 dk", 15, 30, 30, 25),
    "siki": _alisma_siki("50-55 dk", 20, 40, 50, 30),
    "tempo": (
        _tempo_gun("Matematik", "Matematik", "Fen Bilimleri", "T.C. İnkılap Tarihi"),
        _tempo_gun("Türkçe", "Matematik", "T.C. İnkılap Tarihi", "İngilizce"),
        _tempo_gun("Fen Bilimleri", "Fen Bilimleri", "Matematik", "Din Kültürü"),
        _tempo_gun("Türkçe", "Fen Bilimleri", "T.C. İnkılap Tarihi", "İngilizce"),
        [_b("Hafta tekrarı", sure="45 dk")],
        [
            _b("Paragraf", 25),
            _b("Matematik", 60),
            _b("Türkçe", 50),
            _b("İngilizce", 45),
        ],
        [
            _b("Paragraf", 20),
            _b("Fen Bilimleri", 50),
            _b("T.C. İnkılap Tarihi", 50),
            _b("Din Kültürü", 30),
        ],
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
