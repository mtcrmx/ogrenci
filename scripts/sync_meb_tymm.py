#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TYMM (https://tymm.meb.gov.tr) temel egitim ogretim programi HTML sayfalarindan
unite basliklari, icerik cercevesi konu satirlari ve ogrenme ciktilarini okur;
`data/meb_temel_egitim_curriculum.json` icindeki `dersler` alanini gunceller.

Ornekler:
  python scripts/sync_meb_tymm.py
  python scripts/sync_meb_tymm.py --ders Matematik
  python scripts/sync_meb_tymm.py --dry-run --delay 0.5

Istekler arasinda --delay kullanarak siteye yuk bindirmeyin.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TYMM_BASE = "https://tymm.meb.gov.tr"

# Uygulamadaki `ders_adi` anahtarlari -> TYMM ders URL slug + sinif path segmenti
# sinif_path: /ogretim-programlari/{slug}/{sinif_path} — TYMM arayuzunde gosterilen sinif
# etiketi slug’a gore degisir (genelde 7 ≈ 6. sinif ortaokul matematik gibi).
DEFAULT_SLUG_MAP: dict[str, dict[str, Any]] = {
    "Matematik": {"slug": "ortaokul-matematik-dersi", "sinif_path": 7},
    "Türkçe": {"slug": "ortaokul-turkce-dersi", "sinif_path": 7},
    "Fen Bilimleri": {"slug": "fen-bilimleri-dersi", "sinif_path": 7},
    "Sosyal Bilgiler": {"slug": "sosyal-bilgiler-dersi", "sinif_path": 7},
    "İngilizce": {"slug": "ingilizce-dersi-temel-egitim", "sinif_path": 7},
    "Din Kültürü": {"slug": "din-kulturu-ve-ahlak-bilgisi-dersi", "sinif_path": 7},
    "Görsel Sanatlar": {"slug": "gorsel-sanatlar-dersi-temel-egitim", "sinif_path": 7},
    "Bilişim Teknolojileri": {"slug": "bilisim-teknolojileri-ve-yazilim-dersi", "sinif_path": 7},
    "Müzik": {"slug": "muzik-dersi-temel-egitim", "sinif_path": 7},
    "T.C. İnkılap Tarihi ve Atatürkçülük": {
        "slug": "t-c-inkilap-tarihi-ve-ataturkculuk-dersi",
        "sinif_path": 7,
    },
    "İnsan Hakları ve Vatandaşlık": {
        "slug": "insan-haklari-vatandaslik-ve-demokrasi-dersi",
        "sinif_path": 7,
    },
    "Trafik Güvenliği": {"slug": "trafik-guvenligi-dersi", "sinif_path": 7},
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s, flags=re.I)


def text_content(s: str) -> str:
    t = _strip_tags(unescape(s))
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def http_get(url: str, timeout: float) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8", "replace")


def abs_url(href: str) -> str:
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return TYMM_BASE.rstrip("/") + href


def extract_row_inner_html(page_html: str, title_contains: str) -> str | None:
    """TYMM unite makalesindeki iki kolonlu satirin sag hucre ham HTML'i."""
    esc = re.escape(title_contains)
    pat = (
        r'<div class="col-md-3[^"]*bg-light[^"]*p-2 title">[\s\S]*?'
        + esc
        + r"[\s\S]*?"
        + r"</div>\s*"
        + r'<div class="col-md-9 p-2 content"[^>]*>([\s\S]*?)</div>\s*</div>'
    )
    m = re.search(pat, page_html, re.I)
    return m.group(1) if m else None


def parse_icindekiler_satirlari(inner: str) -> list[str]:
    raw = inner.strip()
    parts = re.split(r"<br\s*/?>", raw, flags=re.I)
    lines: list[str] = []
    for p in parts:
        t = text_content(p)
        if len(t) > 2 and t not in lines:
            lines.append(t)
    if not lines:
        t = text_content(raw)
        if t:
            lines.append(t)
    return lines


def parse_ogrenme_ciktilari(inner: str, max_each: int = 900) -> list[str]:
    out: list[str] = []
    for pblock in re.findall(r"<p>([\s\S]*?)</p>", inner, flags=re.I):
        m = re.search(r"<strong>([^<]+)</strong>", pblock, flags=re.I)
        if not m:
            continue
        t = text_content(m.group(1))
        if len(t) < 25:
            continue
        out.append(t[:max_each])
    return out


def parse_grade_unit_links(grade_html: str) -> list[tuple[str, str]]:
    """(unite_href, tema_basligi) listesi."""
    pairs = re.findall(
        r'<h4 class="title[^"]*"[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>',
        grade_html,
        flags=re.I,
    )
    return [(h.strip(), text_content(t)) for h, t in pairs if h.strip() and t.strip()]


def scrape_unite(unite_url: str, timeout: float) -> dict[str, Any]:
    html = http_get(unite_url, timeout)
    ic = extract_row_inner_html(html, "İçerik Çerçevesi")
    oc = extract_row_inner_html(html, "Öğrenme Çıktıları ve Süreç Bileşenleri")
    konu_satirlari = parse_icindekiler_satirlari(ic) if ic else []
    ciktilar = parse_ogrenme_ciktilari(oc) if oc else []
    if not konu_satirlari:
        konu_satirlari = ["Genel"]
    konular = [{"baslik": k, "ciktilar": ciktilar} for k in konu_satirlari]
    return {"tema": None, "konular": konular, "_unite_url": unite_url}


def scrape_ders(
    ders_adi: str,
    slug: str,
    sinif_path: int,
    timeout: float,
    delay: float,
) -> list[dict[str, Any]]:
    grade_url = f"{TYMM_BASE}/ogretim-programlari/{slug}/{sinif_path}"
    grade_html = http_get(grade_url, timeout)
    time.sleep(delay)
    units = parse_grade_unit_links(grade_html)
    temalar: list[dict[str, Any]] = []
    for href, tema_baslik in units:
        unite_url = abs_url(href)
        try:
            block = scrape_unite(unite_url, timeout)
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            temalar.append(
                {
                    "tema": tema_baslik,
                    "konular": [
                        {
                            "baslik": "Hata",
                            "ciktilar": [f"Unite yuklenemedi: {unite_url} ({e})"],
                        }
                    ],
                }
            )
            time.sleep(delay)
            continue
        block["tema"] = tema_baslik
        block.pop("_unite_url", None)
        temalar.append(block)
        time.sleep(delay)
    if not temalar:
        raise RuntimeError(f"Bir unite bulunamadi: {grade_url}")
    return temalar


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_slug_map(path: Path | None) -> dict[str, dict[str, Any]]:
    m = dict(DEFAULT_SLUG_MAP)
    if path and path.is_file():
        extra = json.loads(path.read_text(encoding="utf-8"))
        for k, v in extra.items():
            if isinstance(v, dict) and "slug" in v:
                m[k] = {**m.get(k, {}), **v}
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description="TYMM'den mufredat JSON senkronu")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Cikti JSON (varsayilan: repo/data/meb_temel_egitim_curriculum.json)",
    )
    ap.add_argument("--ders", action="append", help="Sadece bu ders anahtari (tekrarlanabilir)")
    ap.add_argument("--config", type=Path, help="Slug haritasi JSON (varsayilanlarin uzerine yazar)")
    ap.add_argument("--timeout", type=float, default=35.0)
    ap.add_argument("--delay", type=float, default=0.35, help="Istekler arasi bekleme (sn)")
    ap.add_argument("--dry-run", action="store_true", help="Dosyaya yazma, ozet yazdir")
    args = ap.parse_args()

    root = repo_root()
    out_path = args.output or (root / "data" / "meb_temel_egitim_curriculum.json")
    slug_map = load_slug_map(args.config)

    ders_filter = set(args.ders) if args.ders else None
    to_run = [
        (name, slug_map[name])
        for name in slug_map
        if ders_filter is None or name in ders_filter
    ]
    if ders_filter:
        missing = ders_filter - {n for n, _ in to_run}
        if missing:
            print("Bilinmeyen --ders:", ", ".join(sorted(missing)), file=sys.stderr)
            return 2

    if ders_filter and not out_path.is_file() and not args.dry_run:
        print(
            "Hata: --ders ile kismi senkron icin hedef JSON dosyasi zaten var olmali "
            "(once tam dosyayi olusturun veya -o ile mevcut data/meb_temel_egitim_curriculum.json verin).",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        ozet: dict[str, int] = {}
        for ders_adi, meta in to_run:
            slug = str(meta["slug"])
            sp = int(meta.get("sinif_path", 7))
            print(f"[+] {ders_adi}  ->  {slug}  sinif_path={sp}", flush=True)
            try:
                temas = scrape_ders(ders_adi, slug, sp, args.timeout, args.delay)
                ozet[ders_adi] = len(temas)
            except Exception as e:
                print(f"[!] {ders_adi} basarisiz: {e}", file=sys.stderr, flush=True)
                return 1
        print(json.dumps(ozet, indent=2, ensure_ascii=True))
        return 0

    doc: dict[str, Any]
    if out_path.is_file():
        doc = json.loads(out_path.read_text(encoding="utf-8"))
    else:
        doc = {
            "kaynakUrl": "https://tymm.meb.gov.tr/ogretim-programlari/temel-egitim",
            "aciklama": "TYMM HTML senkronu (scripts/sync_meb_tymm.py)",
            "surum": "",
            "dersler": {},
        }

    doc["kaynakUrl"] = "https://tymm.meb.gov.tr/ogretim-programlari/temel-egitim"
    doc["sonSenkronUtc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["surum"] = datetime.now(timezone.utc).strftime("%Y-%m-%d-tymm-html")

    dersler = doc.setdefault("dersler", {})
    for ders_adi, meta in to_run:
        slug = str(meta["slug"])
        sp = int(meta.get("sinif_path", 7))
        print(f"[+] {ders_adi}  ->  {slug}  sinif_path={sp}", flush=True)
        try:
            dersler[ders_adi] = scrape_ders(ders_adi, slug, sp, args.timeout, args.delay)
        except Exception as e:
            print(f"[!] {ders_adi} basarisiz: {e}", file=sys.stderr, flush=True)
            return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("Yazildi:", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
