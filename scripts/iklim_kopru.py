"""Read the USB temperature sensor and post it to the school screen every reading.

The Arduino prints lines like ``ISI 23.4 NEM 41 WIFI ok`` on COM8 at 9600 baud.
Set IKLIM_URL and IKLIM_ANAHTAR for the live site. Without them, the script
uses this computer's local database key and http://127.0.0.1:5000/api/iklim.
"""
import os
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"ISI\s+(-?\d+(?:\.\d+)?)\s+NEM\s+(\d+(?:\.\d+)?)(?:\s+WIFI\s+(ok|yok))?")


def local_key():
    env = os.environ.get("IKLIM_ANAHTAR", "").strip()
    if env:
        return env
    sys.path.insert(0, str(ROOT))
    import database as db
    if not Path(db.DB_PATH).exists():
        return ""
    con = sqlite3.connect(db.DB_PATH)
    row = con.execute("SELECT deger FROM okul_yayin_ayar WHERE anahtar='iklim_anahtar'").fetchone()
    con.close()
    return row[0] if row else ""


def post(url, key, sicaklik, nem, wifi):
    body = f'{{"sicaklik":{sicaklik},"nem":{nem},"wifi":"{wifi}"}}'.encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-Iklim-Anahtar": key,
    })
    with urllib.request.urlopen(request, timeout=8) as response:
        response.read()


def main():
    port = os.environ.get("IKLIM_PORT", "COM8")
    url = os.environ.get("IKLIM_URL", "http://127.0.0.1:5000/api/iklim")
    key = local_key()
    if not key:
        print("Sensör anahtarı yok. IKLIM_ANAHTAR tanımlayın.", file=sys.stderr)
        return 1
    import serial
    link = serial.Serial(port, 9600, timeout=2)
    print(f"{port} dinleniyor", flush=True)
    while True:
        raw = link.readline().decode("utf-8", "ignore").strip()
        match = LINE.search(raw)
        if not match:
            continue
        wifi = match.group(3) or ""
        try:
            post(url, key, match.group(1), match.group(2), wifi)
            print(f"gonderildi {match.group(1)} C nem {match.group(2)} {wifi}", flush=True)
        except OSError as exc:
            print(f"gonderilemedi: {exc}", file=sys.stderr)
            time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
