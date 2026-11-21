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
pip install torch --index-url https://download.pytorch.org/whl/cpu   # veya CUDA torch
pip install -r requirements.txt
```

**basic-pitch** Python 3.12’de `tensorflow<2.15.1` istediği için kurulamayabilir;
`data_prep` otomatik **librosa.pyin** yedeğine düşer. Demucs yoksa stem ayırma
da librosa (full-mix) yedeği kullanır.

### Linux MIDI notu

`python-rtmidi` ALSA ister. Sanal port: `snd-virmidi` / `a2jmidid`.
Windows: **loopMIDI**. macOS: **IAC Driver**.

## Referans veri (Windows masaüstü)

İndirdiğiniz klasörler genelde şuralardadır:

- `%USERPROFILE%\Desktop\Bas Gitar Loop` — ses loop / şarkı (MP3/WAV)
- `%USERPROFILE%\Desktop\Yuruyus Veri Seti` — bas yürüyüş MIDI’leri

Bunları projeye alın (**kopya veya symlink**):

```text
Bas Gitar Loop\*          →  modo_bass_ai/dataset/raw_songs/
Yuruyus Veri Seti\*.mid   →  modo_bass_ai/dataset/custom_midi/
```

PowerShell örneği (kopya):

```powershell
Copy-Item "$env:USERPROFILE\Desktop\Bas Gitar Loop\*" `
  .\modo_bass_ai\dataset\raw_songs\ -Recurse -Force
Copy-Item "$env:USERPROFILE\Desktop\Yuruyus Veri Seti\*" `
  .\modo_bass_ai\dataset\custom_midi\ -Recurse -Force
```

**Kopyalamadan** da çalıştırabilirsiniz — CLI / ortam değişkeni / Gradio Eğitim
sekmesindeki yol alanları:

```bash
# Ortam değişkenleri
set MODO_RAW_SONGS_DIR=%USERPROFILE%\Desktop\Bas Gitar Loop
set MODO_CUSTOM_MIDI_DIR=%USERPROFILE%\Desktop\Yuruyus Veri Seti

# veya CLI
python -m data_prep.build_dataset --raw "%USERPROFILE%\Desktop\Bas Gitar Loop"
python -m model_symbolic.train --raw-dir "%USERPROFILE%\Desktop\Bas Gitar Loop"
python -m model_symbolic.fine_tune --midi-dir "%USERPROFILE%\Desktop\Yuruyus Veri Seti"
```

Gradio → **Eğitim Merkezi (Training)** sekmesinde aynı yolları Textbox’lara yazın.
Bulut / CI ortamında bu Desktop klasörleri **yoktur**; boş `raw_songs` ile
sentetik bootstrap eğitim mümkündür.

## Gradio

```bash
cd modo_bass_ai
source .venv/bin/activate
python web_ui/app.py
```

Tarayıcı: `http://127.0.0.1:7860`

- **Performans**: model seçimi — *Kural Tabanlı Hibrit* | *best_bass_model* | *custom_style_bass*
- **Eğitim Merkezi**: Veri Setini Hazırla / Eğitimi Başlat / Fine-tune + canlı log

## Eğitim pipeline (CLI)

```bash
# 1) Ham şarkılardan train_data.pt (Demucs cache + 12 ton augment)
python -m data_prep.build_dataset

# 2) Genel model → checkpoints/best_bass_model.pt (+ örnek MIDI)
python -m model_symbolic.train --epochs 5

# 3) Kendi MIDI yürüyüşlerinizle fine-tune → checkpoints/custom_style_bass.pt
python -m model_symbolic.fine_tune --lr 1e-5
```

Smoke:

```bash
python scripts/smoke_test.py
```

## Fender Studio Pro 8 + loopMIDI (Windows)

1. [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) kurun; sanal port oluşturun.
2. Fender Studio Pro 8 → MIDI In = o port; kanala **MODO BASS 2**.
3. Uygulamada aynı port + canlı stream veya `.mid` sürükle-bırak.
4. Keyswitch duyulmuyorsa `config/modo_bass_map.json` ile eşleştirin.

## Proje ağacı

```
modo_bass_ai/
  config/modo_bass_map.json
  data_prep/pipeline.py
  data_prep/build_dataset.py
  dataset/raw_songs/          # MP3/WAV buraya
  dataset/custom_midi/        # .mid yürüyüşler
  dataset/processed/          # train_data.pt
  modo_mapper/articulation_engine.py
  model_symbolic/bass_groove_model.py
  model_symbolic/train.py
  model_symbolic/fine_tune.py
  web_ui/app.py
  checkpoints/
  scripts/
```

## Varsayımlar

- Bas aralığı E1–G4 (MIDI 28–67); keyswitch 15–20 ms önce.
- Düşük velocity → Ghost + Mute; uzun notlarda CC1/CC11 yükselir.
- Eğitilmemiş / eksik checkpoint’te kural + groove hibrit çıkarım.
