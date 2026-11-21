# MODO BASS AI

IK Multimedia **MODO BASS 2** için yerel Python + Gradio performans aracı.
Şarkının temposunu, ölçüsünü ve akorlarını tahmin edip kaydın süresine uygun
bir **bas MIDI** hattı üretir (keyswitch, CC, artikülasyon). `.mid` indirme ve **loopMIDI**
üzerinden Fender Studio Pro 8 → MODO BASS 2 canlı stream desteklenir.

Bu bilgisayardaki MODO BASS 2 elektrik bas ayarlarıyla sınanan MIDI eşlemesi
`config/modo_bass_map.json` dosyasındadır. MIDI Learn veya slide aralığı
değiştiğinde bu dosyadaki karşılığını da güncelleyin.

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

- **Performans → Şarkıdan bas eşliği** bölümüne şarkıyı veya altyapıyı yükleyip **Şarkıya bas yaz** düğmesine basın. Durum alanı **BPM**, **ölçü**, **süre (saniye / ölçü / vuruş)** ve Fender Studio Pro yerleştirme önerisini gösterir. **Şarkının tempo, ölçü ve akor ayarları** bölümünde bildiğiniz değerleri girebilirsiniz; elle girilen BPM hem üretimi hem `.mid` içindeki `set_tempo` metasını belirler. İsteğe bağlı akor dizisi ilk ölçü başından başlayarak tekrar eder. MIDI'yi ses kaydıyla aynı başlangıç noktasına yerleştirmeden önce proje temposunu bu BPM’e ayarlayın.
- **Performans → Akorları elle gir** bölümünde her ölçü için bir akor yazabilir ve isteğe bağlı bir davul kaydı yükleyebilirsiniz. BPM boşsa tempo davul WAV’dan tahmin edilir (yoksa 100); girdiğiniz BPM üretimi ve MIDI temposunu sabitler.
- **Performans Basçısı** modeli dörtlük vuruş başına dört konumda nota ve vuruş şiddeti tahmin eder. **Çalım yoğunluğu** ayarıyla sade, dengeli veya hareketli eşlik seçilebilir. Hareketli çalım senkoplar, motif cevapları ve ölçü sonu geçişleri kullanır.
- **Stüdyo Basçısı** bu modeli çalınmış şarkı pasajlarıyla geliştirir. Eğitim 7 şarkı, doğrulama 2 şarkı ve test 1 şarkı içerir. Ses kayıtlarından çıkarılan notalar otomatik tahmindir. Ayrı bir teknik modeli 31 özgün etüt ailesi üzerinden slide, hammer-on, pull-off, ghost, palm mute, vibrato, armonik, slap ve pop için karar verir. Aynı telde erişilebilirlik, nota süresi ve ölçü içindeki vurgu konumu seçimleri sınırlar.
- **Stüdyo Basçısı · Geniş Repertuvar** bas hattını yazarken davul ataklarını, geçerli armoniyi ve bir dörtlük sonraki akoru kullanır. Stüdyo kayıtlarına ek olarak Slakh2100-redux'tan 823 elektrik bas düzenlemesiyle eğitildi. Kaynaklar çok kanallı MIDI'dir. Akorlar eşlik çalgılarından tahmin edildi. Hareketli ayarında yürüyüşler bir sonraki akora komşu seslerden bağlanabilir.
- **Stüdyo Basçısı · Ege / Balkan** pes notaların tekrarına, sekizlik nabza ve cümle sonundaki küçük geçişlere ağırlık verir. 2/4, 4/4, 5/8, 7/8 ve 9/8 için özgün dört ölçülük pasajlarla uyarlandı. Aksak ölçüde kaydın ölçüsünü, dörtlük BPM değerini ve ilk ölçü başını biliyorsanız şarkı ayarlarına girebilirsiniz. Aynı alanda girilen akorlar her ölçü başında değişir.
- **Stüdyo Basçısı · Türk Repertuvarı** SymbTr 2.4.3 yazılı repertuvarındaki şarkı, türkü ve Rumeli türkülerinden türetilen bas eşlikleriyle uyarlandı. Kaynak notalardan ölçü, usul ve melodik ağırlıklar alınır. Bas ve davul etiketleri bu ölçülere sonradan yazıldı. Önceki gerçek stüdyo performansları ve Ege etütleri de uyarlamada tekrar kullanıldı. Kaynak koleksiyonu CC BY-NC-SA 4.0 lisanslıdır. [SymbTr](https://github.com/MTG/SymbTr/releases/tag/v2.4.3)
- Windows'taki yerel Chordino kurulumu, seyrek veya kararsız akor tahminlerini ikinci bir ses analiziyle kontrol eder. Ses bilgisayarda işlenir. Bu bileşeni yeniden kurmak gerekirse `scripts/install_chordino.py` içindeki kurulum açıklamasını izleyin.
- **MIDI hedefi** olarak MODO BASS 2 seçildiğinde program konser perdesini eklentinin girişine çevirir. Örneğin yaklaşık 41,2 Hz ses veren E1 için bu kurulumda MIDI 40 gönderilir. Standart MIDI seçeneği E1 için MIDI 28 yazar. MODO hedefi kontrol tuşlarını ve slide mesajlarını dosyaya ve canlı çıkışa işler.
- **Eğitim Merkezi** üzerinden genel modeli, özel MIDI tarzını ve performans modelini ayrı ayrı eğitebilirsiniz. Performans eğitiminde doğrulama için ayrılan motif aileleri ve kayıtlar en iyi turu seçmek için kullanılır.

## Eğitim pipeline (CLI)

```bash
# 1) Ham şarkılardan train_data.pt (Demucs cache + 12 ton augment)
python -m data_prep.build_dataset

# 2) Genel model → checkpoints/best_bass_model.pt (+ örnek MIDI)
python -m model_symbolic.train --epochs 5

# 3) Kendi MIDI yürüyüşlerinizle fine-tune → checkpoints/custom_style_bass.pt
python -m model_symbolic.fine_tune --lr 1e-5

# Performans Basçısını yeniden eğit
python -m model_symbolic.train_performance

# Şarkı pasajları ve etütlerle Stüdyo Basçısını yeniden eğit
python -m model_symbolic.train_session

# Stüdyo ağırlıklarından çok kanallı düzenlemelere uyarlama
python -m model_symbolic.train_ensemble

# Ege/Balkan için özgün çalışma dizilerini oluştur ve modeli uyarla
python -m data_prep.build_ege_studies dataset/performance/ege_studies.jsonl
python -m model_symbolic.train_ege

# SymbTr 2.4.3 kaynak arşivinden Türkçe şarkı ve türkü eşlikleri üret
python -m data_prep.import_turkish_scores symbtr_v243.zip
python -m model_symbolic.train_turkish_repertoire
```

Performans eğitimi için `dataset/performance/paired_clips.jsonl`, 192 özgün MIDI'nin akorlarını ve dosya özetlerini içerir. `repertoire.jsonl` sekiz ölçülük özgün etütler, `recorded.jsonl` ise çalınmış kayıtlardan ses perdesiyle karşılaştırılan otomatik transkripsiyonlar ve yayımlanmış bir MIDI içerir. Kayıtların kaynağı ve atfı her satırda bulunur. `training_report.json` eğitim, doğrulama ve test bölümlerinin sonuçlarını saklar.

Stüdyo Basçısı için `song_performances.jsonl` kaynak zamanlarını, şarkı bazlı bölümleri ve nota tahminlerini içerir. `song_sources.json` sanatçıları, lisansları ve bağlantıları listeler. `technique_studies.jsonl` etütlerde her notanın çalım tekniğini verir. Sonuçlar `dataset/performance/session_training_report.json`, eğitilmiş model ise `checkpoints/session_bass.pt` dosyasına yazılır.

Geniş Repertuvar eğitiminde `dataset/performance/ensemble_phrases.jsonl` dört ölçülük bölümleri, MIDI şiddetlerini ve eşlik akorlarını, `ensemble_sources.json` kaynak kimliklerini ve lisansını içerir. Eğitimde 823, doğrulamada 211, resmî test bölümünde 126 farklı düzenleme vardır. Farklı MIDI düzenlemelerinin aynı ses kaydına bağlanabildiği durumları dışlayan ek test 72 düzenleme içerir. Eğitim ve temel test sonuçları `ensemble_training_report.json`, model `checkpoints/ensemble_bass.pt` dosyasındadır. Veri kaynağı Ethan Manilow, Gordon Wichern, Prem Seetharaman ve Jonathan Le Roux'un Slakh2100-redux çalışmasıdır. [Slakh2100-redux](https://zenodo.org/records/4599666)

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

- İç nota aralığı konser perdesinde MIDI 28–67 (E1–G4). MODO hedefinde kontrol tuşları gerekirse notadan 12 ms önce gönderilir.
- Bu kurulumda CC1 vibratoyu, CC9 susturmayı ve CC64 bağlı slide'ı kontrol eder. Kısa slide girişleri iki yarım ses aralığında pitch bend kullanır. Uzun slide için iki nota aynı telde kısa süre örtüşür.
- Eğitilmemiş / eksik checkpoint’te kural + groove hibrit çıkarım.
