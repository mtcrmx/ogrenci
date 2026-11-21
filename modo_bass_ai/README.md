# MODO BASS AI

IK Multimedia **MODO BASS 2** için yerel Python + Gradio performans aracı.
Akor ilerlemesi + davul ritmi analizinden insanvari bas hattı üretir; ses sentezi yok —
çıktı yalnızca **MIDI** (keyswitch, CC, artikülasyon). `.mid` indirme ve **loopMIDI**
üzerinden Fender Studio Pro 8 → MODO BASS 2 canlı stream desteklenir.

> Keyswitch / CC numaraları `config/modo_bass_map.json` içindedir. MODO preset’leri
> MIDI Learn ile değişebilir; varsayılanlar yaygın fabrika düzenine yakındır
> (C-1…B-1 artikülasyon, C0…D0 tel seçimi, CC1 vibrato, CC11 expression).

## Kurulum (venv)

```bash
cd modo_bass_ai
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

`torch` / `demucs` kurulumu uzun sürebilir. CPU host’ta önce:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

**basic-pitch** Python 3.12’de `tensorflow<2.15.1` istediği için bu ortamda
kurulamayabilir; `data_prep` otomatik **librosa.pyin** yedeğine düşer.
Python 3.10/3.11’de `pip install "basic-pitch>=0.3.0"` deneyin. Demucs yoksa
stem ayırma da librosa (full-mix) yedeği kullanır.

### Linux MIDI notu

`python-rtmidi` ALSA ister. Sanal port için örn. `snd-virmidi` veya `a2jmidid`.
Windows’ta **loopMIDI**, macOS’ta **IAC Driver** kullanın.

## Gradio’yu çalıştırma

```bash
cd modo_bass_ai
source .venv/bin/activate
python web_ui/app.py
# veya: python scripts/run_app.py
```

Tarayıcı: `http://127.0.0.1:7860`

Smoke test:

```bash
python scripts/smoke_test.py
```

İsteğe bağlı model eğitimi (sentetik veri ile bootstrap):

```bash
python -m model_symbolic.train --epochs 3 --out checkpoints/bass_groove.pt
```

## Fender Studio Pro 8 + loopMIDI (Windows)

1. [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) kurun.
2. loopMIDI’de örn. `MODO_BASS_AI` adında sanal port oluşturun.
3. Fender Studio Pro 8’i açın → MIDI Input olarak bu portu seçin.
4. Enstrüman kanalına **MODO BASS 2** yükleyin; MIDI kanalı 1.
5. Bu uygulamada aynı portu seçip **Canlı MIDI stream** ile çalın veya `.mid`
   dosyasını DAW’a sürükleyin.
6. Artikülasyonlar duyulmuyorsa MODO’daki keyswitch haritasını
   `config/modo_bass_map.json` ile eşleştirin / MIDI Learn uygulayın.

## Proje ağacı

```
modo_bass_ai/
  config/modo_bass_map.json
  data_prep/pipeline.py
  modo_mapper/articulation_engine.py
  model_symbolic/bass_groove_model.py
  model_symbolic/train.py
  web_ui/app.py
  scripts/run_app.py
  scripts/smoke_test.py
  requirements.txt
  README.md
```

## Varsayımlar

- Çalınabilir bas aralığı: E1–G4 (MIDI 28–67).
- Keyswitch’ler notadan **15–20 ms** önce.
- Düşük velocity (<40) → Ghost + Palm Mute.
- Uzun notalarda CC1 / CC11 eğrileri sona doğru yükselir.
- Tel seçimi (E/A/D/G) fretboard konumu ile gereksiz atlamaları azaltır.
- Eğitilmemiş modelde **müzik teorisi + groove kuralları** ile hybrid çıkarım.
