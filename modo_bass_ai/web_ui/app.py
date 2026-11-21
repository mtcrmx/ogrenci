"""Gradio UI: performance + Training Merkezi for MODO BASS AI."""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
from collections import Counter
from bisect import bisect_right
from pathlib import Path
from typing import Callable, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import gradio as gr
from audioread.exceptions import DecodeError

from data_prep.build_dataset import estimate_bpm
from data_prep.pipeline import AudioPrepPipeline
from data_prep.song_timeline import analyze_song_timeline
from model_symbolic.bass_groove_model import (
    CHORD_TONES,
    bar_duration_ms,
    generate_bass_line,
    generate_song_bass_line,
    parse_progression,
    parse_time_signature,
)
from model_symbolic.performance_phrasing import PERFORMANCE_LEVELS
from modo_mapper.articulation_engine import ArticulationEngine, BassMelodyNote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("modo_bass_ui")

CONFIG_PATH = _ROOT / "config" / "modo_bass_map.json"
BEST_CKPT = _ROOT / "checkpoints" / "best_bass_model.pt"
PERFORMANCE_CKPT = _ROOT / "checkpoints" / "performance_bass.pt"
SESSION_CKPT = _ROOT / "checkpoints" / "session_bass.pt"
ENSEMBLE_CKPT = _ROOT / "checkpoints" / "ensemble_bass.pt"
EGE_CKPT = _ROOT / "checkpoints" / "ege_bass.pt"
TURKISH_CKPT = _ROOT / "checkpoints" / "turkish_repertoire_bass.pt"
CUSTOM_CKPT = _ROOT / "checkpoints" / "custom_style_bass.pt"
OUTPUT_DIR = _ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STYLES = ["Fingerstyle", "Slap", "Fretless", "Pick", "Mute"]
TIME_SIGS = ["4/4", "2/4", "3/4", "5/8", "6/8", "7/8", "8/8", "9/8", "10/8", "12/8", "9/4"]

MODEL_RULES = "Kural Tabanlı Hibrit"
MODEL_PERFORMANCE = "Performans Basçısı"
MODEL_SESSION = "Stüdyo Basçısı"
MODEL_ENSEMBLE = "Stüdyo Basçısı · Geniş Repertuvar"
MODEL_EGE = "Stüdyo Basçısı · Ege / Balkan"
MODEL_TURKISH = "Stüdyo Basçısı · Türk Repertuvarı"
MIDI_MODO = "MODO BASS 2"
MIDI_CONCERT = "Standart MIDI (konser perdesi)"
TECHNIQUE_NAMES = {
    "slide_up": "yukarı slide", "slide_down": "aşağı slide",
    "slide_in_up": "alttan slide girişi", "slide_in_down": "üstten slide girişi",
    "hammer_on": "hammer-on", "pull_off": "pull-off", "palm_mute": "palm mute",
    "harmonic": "armonik", "ghost": "ghost nota",
}
MODEL_BEST = "Eğitilmiş Genel Basçı (best_bass_model)"
MODEL_CUSTOM = "Özel Tarzım (custom_style_bass)"
MODEL_CHOICES = [MODEL_TURKISH, MODEL_EGE, MODEL_ENSEMBLE, MODEL_SESSION, MODEL_PERFORMANCE, MODEL_BEST, MODEL_CUSTOM, MODEL_RULES]


def list_midi_ports() -> List[str]:
    seq_path = Path("/dev/snd/seq")
    if sys.platform.startswith("linux") and not seq_path.exists():
        return ["(no ALSA sequencer — use loopMIDI on Windows / IAC on macOS)"]
    try:
        import rtmidi

        midi_out = rtmidi.MidiOut()
        ports = midi_out.get_ports()
        del midi_out
        return ports if ports else ["(no MIDI ports found)"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("rtmidi port list failed: %s", exc)
        return ["(rtmidi unavailable — install python-rtmidi)"]


def resolve_checkpoint(model_choice: str) -> Tuple[Optional[Path], bool]:
    """Return (checkpoint_path_or_None, force_rules)."""
    if model_choice == MODEL_TURKISH:
        if not TURKISH_CKPT.is_file():
            raise gr.Error("Türk Repertuvarı modelini Eğitim Merkezi’nden eğitin.")
        return TURKISH_CKPT, False
    if model_choice == MODEL_EGE:
        if not EGE_CKPT.is_file():
            raise gr.Error("Ege / Balkan modelini Eğitim Merkezi’nden eğitin.")
        return EGE_CKPT, False
    if model_choice == MODEL_ENSEMBLE:
        if not ENSEMBLE_CKPT.is_file():
            raise gr.Error("Geniş Repertuvar modelini Eğitim Merkezi’nden eğitin.")
        return ENSEMBLE_CKPT, False
    if model_choice == MODEL_SESSION:
        if not SESSION_CKPT.is_file():
            raise gr.Error("Stüdyo Basçısı modelini Eğitim Merkezi’nden eğitin.")
        return SESSION_CKPT, False
    if model_choice == MODEL_PERFORMANCE:
        if not PERFORMANCE_CKPT.is_file():
            raise gr.Error("Performans modelinin eğitimini Eğitim Merkezi’nden başlatın.")
        return PERFORMANCE_CKPT, False
    if model_choice == MODEL_BEST:
        if BEST_CKPT.exists():
            return BEST_CKPT, False
        return None, True
    if model_choice == MODEL_CUSTOM:
        if CUSTOM_CKPT.exists():
            return CUSTOM_CKPT, False
        if BEST_CKPT.exists():
            return BEST_CKPT, False
        return None, True
    return None, True


def _to_melody(notes) -> List[BassMelodyNote]:
    return [
        BassMelodyNote(
            start_ms=n.start_ms,
            end_ms=n.end_ms,
            pitch=n.pitch,
            velocity=n.velocity,
            articulation=n.articulation,
            is_passing=n.is_passing,
        )
        for n in notes
    ]


def stream_to_port(
    melody: List[BassMelodyNote],
    play_style: str,
    port_name: str,
    engine: ArticulationEngine,
    target: str = "modo",
) -> str:
    try:
        import rtmidi
    except ImportError:
        return "python-rtmidi yüklü değil."

    midi_out = rtmidi.MidiOut()
    ports = midi_out.get_ports()
    if not ports or port_name.startswith("("):
        return "Açık MIDI portu yok. Windows'ta loopMIDI ile sanal port oluşturun."

    try:
        idx = ports.index(port_name)
    except ValueError:
        idx = 0
        port_name = ports[0]

    midi_out.open_port(idx)
    status_lines = [f"Streaming → {port_name}"]

    channel = engine.channel

    def send(msg_type: str, data: Tuple[int, ...]) -> None:
        if msg_type == "note_on":
            midi_out.send_message([0x90 | channel, data[0], data[1]])
        elif msg_type == "note_off":
            midi_out.send_message([0x80 | channel, data[0], 0])
        elif msg_type == "control_change":
            midi_out.send_message([0xB0 | channel, data[0], data[1]])
        elif msg_type == "pitchwheel":
            value = data[0] + 8192
            midi_out.send_message([0xE0 | channel, value & 127, value >> 7])

    t0 = time.perf_counter()
    try:
        for abs_t, msgs in engine.iter_realtime_messages(melody, play_style=play_style, target=target):
            delay = (t0 + abs_t) - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            for msg_type, data in msgs:
                send(msg_type, data)
        status_lines.append("Stream tamamlandı.")
    except Exception as exc:  # noqa: BLE001
        status_lines.append(f"Stream hatası: {exc}")
    finally:
        try:
            midi_out.send_message([0xB0 | channel, 123, 0])
            midi_out.send_message([0xE0 | channel, 0, 64])
            midi_out.send_message([0xB0 | channel, 1, 0])
            midi_out.send_message([0xB0 | channel, 9, 0])
        except Exception:  # noqa: BLE001
            pass
        midi_out.close_port()
        del midi_out
    return "\n".join(status_lines)


def _coerce_bpm_override(bpm) -> Optional[float]:
    """Return a positive BPM when the user typed one; otherwise None (auto)."""
    if bpm is None or bpm == "":
        return None
    try:
        value = float(bpm)
    except (TypeError, ValueError):
        return None
    if not value or value != value:  # NaN / 0
        return None
    if value < 0:
        raise gr.Error("BPM negatif olamaz.")
    return value


def _detect_drum_bpm(path: str | Path) -> float:
    import librosa

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    return float(estimate_bpm(y, sr))


def _resolve_manual_tempo(
    bpm_override, drum_path: Optional[str]
) -> Tuple[float, str, Optional[float]]:
    """Prefer the typed BPM; otherwise estimate from the drum WAV (fallback 100)."""
    override = _coerce_bpm_override(bpm_override)
    detected: Optional[float] = None
    if drum_path:
        try:
            detected = _detect_drum_bpm(drum_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("drum BPM detection failed: %s", exc)
    if override is not None:
        return override, "elle girilen", detected
    if detected is not None:
        return detected, "davul kaydından", detected
    return 100.0, "varsayılan", detected


def _daw_timing_block(
    bpm: float,
    time_signature: str,
    duration_s: float,
    *,
    bars: Optional[float] = None,
    source: str = "",
) -> str:
    """Clear BPM / meter / duration block so the MIDI can be placed in a DAW."""
    num, _den = parse_time_signature(time_signature)
    bar_s = bar_duration_ms(bpm, time_signature) / 1000.0
    if bars is None and bar_s > 0:
        bars = duration_s / bar_s
    beats = bars * num if bars is not None else None
    bpm_text = f"{bpm:g}"
    if abs(bpm - round(bpm)) < 1e-6:
        bpm_text = f"{round(bpm)}"
    lines = [
        "—— Tempo / DAW yerleştirme ——",
        f"BPM (dörtlük): {bpm_text}" + (f" · kaynak: {source}" if source else ""),
        f"Ölçü: {time_signature}",
        f"Süre: {duration_s:.2f} s",
    ]
    if bars is not None and beats is not None:
        lines.append(f"Uzunluk: ~{bars:.2f} ölçü · ~{beats:.1f} vuruş")
    lines.append(
        f"Öneri: Fender Studio Pro 8 proje temposunu {bpm_text} BPM / {time_signature} "
        "yapın, sonra .mid dosyasını aynı başlangıç noktasına sürükleyin."
    )
    lines.append("MIDI dosyasına set_tempo ve time_signature meta olayları yazıldı.")
    return "\n".join(lines)


def generate(
    drum_wav,
    chords: str,
    bpm,
    time_signature: str,
    play_style: str,
    humanize_ms: float,
    groove_amount: float,
    midi_port: str,
    do_stream: bool,
    model_choice: str,
    performance_level: str = "Sade",
    midi_target: str = MIDI_MODO,
    progress=gr.Progress(track_tqdm=False),
):
    progress(0.05, desc="Hazırlanıyor")
    kick_ms: List[float] = []
    snare_ms: List[float] = []
    drum_info = "Elle girilen akorlar kullanıldı."
    drum_path = None

    if drum_wav is not None:
        progress(0.2, desc="Davul onset ve tempo analizi")
        drum_path = drum_wav if isinstance(drum_wav, str) else getattr(drum_wav, "name", None)
        if drum_path:
            pipe = AudioPrepPipeline()
            try:
                onsets = pipe.analyze_drums_only(drum_path)
                kick_ms = onsets.kick_ms
                snare_ms = onsets.snare_ms
                drum_info = f"Kick: {len(kick_ms)} | Snare: {len(snare_ms)}"
            except Exception as exc:  # noqa: BLE001
                drum_info = f"Davul analizi başarısız ({exc})."

    effective_bpm, bpm_source, detected_bpm = _resolve_manual_tempo(bpm, drum_path)
    if detected_bpm is not None and bpm_source != "davul kaydından":
        drum_info += f"\nDavul tahmini tempo: {detected_bpm:g} BPM (üretimde {bpm_source} kullanıldı)"
    elif detected_bpm is not None:
        drum_info += f"\nDavul tahmini tempo: {detected_bpm:g} BPM"

    ckpt, force_rules = resolve_checkpoint(model_choice)
    if model_choice != MODEL_RULES and ckpt is None:
        drum_info += f"\nUyarı: {model_choice} checkpoint yok → kural hibrit."
    elif ckpt is not None:
        drum_info += f"\nModel: {ckpt.name}"

    progress(0.45, desc="Bas hattı üretiliyor")
    chart = parse_progression(chords or "") or ["Am7", "D9", "Gmaj7", "Cmaj7"]
    duration_s = len(chart) * bar_duration_ms(effective_bpm, time_signature) / 1000
    notes = generate_bass_line(
        chart,
        bpm=effective_bpm,
        time_signature=time_signature,
        play_style=play_style,
        kick_ms=kick_ms,
        snare_ms=snare_ms,
        humanize_ms=float(humanize_ms),
        groove_amount=float(groove_amount),
        checkpoint=ckpt,
        force_rules=force_rules,
        performance_level=performance_level,
    )
    return _export_performance(
        notes, play_style, midi_port, do_stream, progress, midi_target=midi_target,
        summary=(
            f"{drum_info}\n{play_style} · {performance_level}\n"
            + _daw_timing_block(
                effective_bpm, time_signature, duration_s,
                bars=float(len(chart)), source=bpm_source,
            )
        ),
        bpm=effective_bpm, time_signature=time_signature, duration_s=duration_s,
    )


def _export_performance(notes, play_style, midi_port, do_stream, progress, summary, midi_target, **timing):
    progress(0.8, desc="Bas MIDI dosyası yazılıyor")
    melody = _to_melody(notes)
    engine = ArticulationEngine(CONFIG_PATH)
    mid_path = OUTPUT_DIR / f"modo_bass_{time.time_ns()}.mid"
    target = "concert" if midi_target == MIDI_CONCERT else "modo"
    engine.write_midi(melody, mid_path, play_style=play_style, target=target, **timing)
    techniques = Counter(n.articulation for n in notes if n.articulation and n.articulation != "normal")
    if techniques:
        summary += "\nÇalım teknikleri · " + ", ".join(
            f"{TECHNIQUE_NAMES.get(name, name)} ×{count}" for name, count in techniques.most_common()
        )
    summary += f"\nMIDI hedefi · {midi_target}"
    if do_stream:
        progress(0.9, desc="Canlı MIDI çalınıyor")
        summary += "\n" + stream_to_port(melody, play_style, midi_port, engine, target=target)
    progress(1.0, desc="Tamam")
    return str(mid_path), f"{summary}\n{len(notes)} bas notası · {mid_path.name}"


def _uploaded_chart(song, text, positions=None):
    """Align one chord per bar to the recording's downbeats; keep any pickup."""
    symbols = parse_progression(text)
    if not symbols:
        raise ValueError("En az bir akor girin.")
    chart = []
    for symbol in symbols:
        if symbol.upper() in {"ES", "NC", "N.C.", "-"}:
            chart.append("")
            continue
        symbol = symbol.replace("♭", "b").replace("♯", "#").replace("Δ", "maj")
        match = re.fullmatch(r"([A-Ga-g])([#b]?)([^/]*)(?:/([A-Ga-g])([#b]?))?", symbol)
        if not match or match[3] not in CHORD_TONES:
            raise ValueError(f"“{symbol}” akoru tanınmadı. Örnek yazım: Am7 | D/F# | G5 | Es.")
        chart.append(match[1].upper() + match[2] + match[3] + ("/" + match[4].upper() + match[5] if match[4] else ""))
    downbeats = [t for t in song.bar_starts_s if t >= song.downbeat_s - 1e-6]
    beats = []
    if positions is None:
        positions = song.beat_times_s[:-1]
    for t in positions:
        bar = bisect_right(downbeats, t + 1e-6) - 1
        old_beat = min(len(song.beat_chords) - 1, max(0, bisect_right(song.beat_times_s, t) - 1))
        detected = song.beat_chords[old_beat]
        beats.append(chart[bar % len(chart)] if bar >= 0 else detected)
    return beats


def generate_for_song(
    song_file, meter, tempo_override, play_style, humanize_ms, groove_amount,
    midi_port, do_stream, model_choice, performance_level="Sade",
    midi_target=MIDI_MODO, song_chart="", first_downbeat=None, progress=gr.Progress(track_tqdm=False),
):
    if not song_file:
        return None, "Önce eşlik edilecek şarkıyı yükleyin."
    progress(0.05, desc="Şarkının vuruşları ve akorları bulunuyor")
    try:
        bpm_override = _coerce_bpm_override(tempo_override)
        song = analyze_song_timeline(
            song_file, time_signature="auto" if meter == "Otomatik" else meter,
            bpm=bpm_override,
            first_downbeat_s=float(first_downbeat) if first_downbeat is not None else None,
        )
    except (DecodeError, EOFError):
        return None, "Ses dosyası okunamadı. Şarkıyı WAV, MP3 veya FLAC olarak yeniden yükleyin."
    except (OSError, ValueError, RuntimeError) as exc:
        return None, f"Şarkı analiz edilemedi. {exc}"
    supplied = bool((song_chart or "").strip())
    grid = song.beat_times_s
    chords = song.beat_chords
    energy = song.beat_energy
    indices = song.downbeat_indices
    eighths = False
    if supplied:
        try:
            num, den = map(int, song.time_signature.split("/"))
            eighths = den == 8 and num % 2 == 1
            if eighths:
                grid = [p for a,b in zip(grid,grid[1:]) for p in (a,(a+b)/2)] + [grid[-1]]
                energy = [e for e in energy for _ in range(2)] if energy is not None else None
                indices = [i * 2 for i in indices]
            chords = _uploaded_chart(song, song_chart, grid[:-1])
        except ValueError as exc:
            return None, str(exc)
    if not any(chords):
        return None, "Bas yazılabilecek akor bulunamadı. Şarkı ayarlarına akor dizisini girebilirsiniz."
    checkpoint, force_rules = resolve_checkpoint(model_choice)
    progress(0.55, desc="Şarkının akorlarına bas yürüyüşü yazılıyor")
    notes = generate_song_bass_line(
        beat_times_ms=[t * 1000 for t in grid], beat_chords=chords,
        downbeat_indices=indices, duration_ms=song.duration_s * 1000,
        downbeat_times_ms=[t * 1000 for t in song.bar_starts_s if t >= song.downbeat_s - 1e-6],
        bpm=song.bpm, time_signature=song.time_signature, play_style=play_style,
        kick_ms=song.kick_ms, snare_ms=song.snare_ms,
        humanize_ms=float(humanize_ms), groove_amount=float(groove_amount),
        checkpoint=checkpoint, force_rules=force_rules,
        performance_level=performance_level, beat_energy=energy, pulse_quarters=.5 if eighths else 1.,
    )
    if not notes:
        return None, "Bas yazılabilecek bir akor bölümü bulunamadı. Akorlar belliyse elle girebilirsiniz."
    changes = [
        f"{grid[i]:.2f} s  {chord or 'es'}"
        for i, chord in enumerate(chords)
        if i == 0 or chord != chords[i - 1]
    ]
    model = checkpoint.stem if checkpoint else MODEL_RULES
    key_name = song.key.replace(" major", " majör").replace(" minor", " minör")
    bpm_source = "elle girilen" if bpm_override is not None else "şarkı / davul analizinden"
    bar_count = max(1, len([t for t in song.bar_starts_s if t >= song.downbeat_s - 1e-6]))
    summary = [
        f"{Path(song_file).name}",
        _daw_timing_block(
            song.bpm, song.time_signature, song.duration_s,
            bars=float(bar_count), source=bpm_source,
        ),
        f"İlk ölçü başı {song.downbeat_s:.2f} s"
        + (f" · Tahmini ton {key_name}" if key_name and not supplied else ""),
        f"{play_style} · {performance_level} · {model}",
        "Girilen akorların şarkıdaki konumları" if supplied else "Tahmini akor değişimleri",
        "  |  ".join(changes[:24]),
    ]
    if len(changes) > 24:
        summary.append("İlk 24 değişim gösteriliyor. MIDI tüm şarkıyı kapsar.")
    summary.extend(w for w in song.warnings if not supplied or not any(k in w.lower() for k in ("akor", "armoni")))
    return _export_performance(
        notes, play_style, midi_port, do_stream, progress, summary="\n".join(summary), midi_target=midi_target,
        bpm=song.bpm, time_signature=song.time_signature, duration_s=song.duration_s,
        beat_times_s=song.beat_times_s, downbeat_s=song.downbeat_s,
    )


class _LogBuffer:
    """Thread-safe log lines for Gradio streaming."""

    def __init__(self) -> None:
        self.lines: List[str] = []
        self._lock = threading.Lock()

    def __call__(self, msg: str) -> None:
        with self._lock:
            self.lines.append(str(msg))
            logger.info("%s", msg)

    def text(self) -> str:
        with self._lock:
            return "\n".join(self.lines[-400:])


def ui_prepare_dataset(raw_dir: str, allow_synthetic: bool):
    log = _LogBuffer()
    raw = (raw_dir or "").strip() or os.environ.get("MODO_RAW_SONGS_DIR", "")
    raw_path = Path(raw) if raw else _ROOT / "dataset" / "raw_songs"
    log(f"Ham ses klasörü: {raw_path}")
    if not raw_path.exists():
        log(f"UYARI: klasör yok ({raw_path}). Sentetik izin={allow_synthetic}.")

    def _job() -> None:
        try:
            from data_prep.build_dataset import build_dataset

            out = build_dataset(
                raw_dir=raw_path,
                allow_synthetic=bool(allow_synthetic),
                log=log,
            )
            log(f"TAMAM → {out}")
        except Exception as exc:  # noqa: BLE001
            log(f"HATA: {exc}")

    th = threading.Thread(target=_job, daemon=True)
    th.start()
    while th.is_alive():
        yield log.text()
        time.sleep(0.4)
    yield log.text()


def ui_run_training(epochs: int, batch_size: int, device: str, raw_dir: str):
    log = _LogBuffer()
    raw = (raw_dir or "").strip() or os.environ.get("MODO_RAW_SONGS_DIR", "")

    def _job() -> None:
        try:
            from model_symbolic.train import run_training

            run_training(
                epochs=int(epochs),
                batch_size=int(batch_size),
                device=device,
                raw_dir=Path(raw) if raw else None,
                log=log,
            )
            log("Eğitim tamam.")
        except Exception as exc:  # noqa: BLE001
            log(f"HATA: {exc}")

    th = threading.Thread(target=_job, daemon=True)
    th.start()
    while th.is_alive():
        yield log.text()
        time.sleep(0.4)
    yield log.text()


def ui_run_performance_training(device: str, model_choice=MODEL_PERFORMANCE):
    from model_symbolic.train_performance import run_performance_training
    from model_symbolic.train_session import run_session_training
    from model_symbolic.train_ensemble import run_ensemble_training
    from model_symbolic.train_ege import train as train_ege
    from model_symbolic.train_turkish_repertoire import train as train_turkish

    log = _LogBuffer()

    def train():
        try:
            trainer = {MODEL_TURKISH: train_turkish, MODEL_EGE: train_ege, MODEL_ENSEMBLE: run_ensemble_training, MODEL_SESSION: run_session_training,
                       MODEL_PERFORMANCE: run_performance_training}[model_choice]
            path = trainer(device=device, log=log)
            log(f"{model_choice} hazır. {path}")
        except Exception as exc:
            logger.exception("Performance training failed")
            log(f"Eğitim tamamlanamadı. {exc}")

    job = threading.Thread(target=train, daemon=True)
    job.start()
    while job.is_alive():
        yield log.text()
        job.join(0.5)
    yield log.text()


def ui_run_finetune(midi_dir: str, epochs: int, device: str):
    log = _LogBuffer()
    midi = (midi_dir or "").strip() or os.environ.get("MODO_CUSTOM_MIDI_DIR", "")
    midi_path = Path(midi) if midi else _ROOT / "dataset" / "custom_midi"
    log(f"MIDI klasörü: {midi_path}")

    def _job() -> None:
        try:
            from model_symbolic.fine_tune import run_fine_tune

            run_fine_tune(
                midi_dir=midi_path,
                epochs=int(epochs),
                device=device,
                log=log,
            )
            log("Fine-tune tamam.")
        except Exception as exc:  # noqa: BLE001
            log(f"HATA: {exc}")

    th = threading.Thread(target=_job, daemon=True)
    th.start()
    while th.is_alive():
        yield log.text()
        time.sleep(0.4)
    yield log.text()


def _default_raw_hint() -> str:
    return os.environ.get("MODO_RAW_SONGS_DIR", "") or str(_ROOT / "dataset" / "raw_songs")


def _default_midi_hint() -> str:
    return os.environ.get("MODO_CUSTOM_MIDI_DIR", "") or str(_ROOT / "dataset" / "custom_midi")


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="MODO BASS AI") as demo:
        gr.Markdown(
            """
            # MODO BASS AI
            Şarkınıza MODO BASS 2 için bas eşliği yazın ve MIDI olarak indirin.
            """
        )
        with gr.Tabs():
            with gr.Tab("Performans"):
                with gr.Row():
                    with gr.Column():
                        song_mode = "Şarkıdan bas eşliği"
                        manual_mode = "Akorları elle gir"
                        mode = gr.Radio(
                            [song_mode, manual_mode], value=song_mode, label="Üretim modu"
                        )
                        with gr.Group() as song_controls:
                            song_file = gr.File(
                                label="Şarkı veya altyapı", type="filepath",
                                file_types=[".wav", ".mp3", ".flac", ".ogg", ".aif", ".aiff"],
                            )
                            with gr.Accordion("Şarkının tempo, ölçü ve akor ayarları", open=False):
                                song_meter = gr.Dropdown(
                                    ["Otomatik", *TIME_SIGS], value="Otomatik", label="Ölçü",
                                    info="Otomatik analiz 3/4 ve 4/4 ölçülerini karşılaştırır. Örneğin 9/8 çalıyorsanız buradan seçin.",
                                )
                                song_bpm = gr.Number(
                                    value=None, minimum=0, label="Dörtlük BPM (otomatik için boş bırakın)",
                                    info="Boş = şarkıdan tempo. Dolu = hem bas üretimi hem MIDI set_tempo bu BPM’i kullanır.",
                                )
                                first_downbeat = gr.Number(
                                    value=None, minimum=0, label="İlk ölçünün başlangıcı (saniye, isteğe bağlı)",
                                    info="Özellikle aksak ölçülerde, ilk ölçü başını biliyorsanız girin.",
                                )
                                song_chart = gr.Textbox(
                                    label="Şarkının akorları (isteğe bağlı)", value="", placeholder="Am7 | F | G | Em",
                                    info="Her ölçüye bir akor yazın. Dizi ilk ölçü başından itibaren tekrar eder. Susulacak ölçü için Es yazın.",
                                )
                        with gr.Group(visible=False) as manual_controls:
                            drum = gr.Audio(
                                sources=["upload"], type="filepath", label="Davul kaydı (isteğe bağlı)",
                            )
                            chords = gr.Textbox(
                                value="Am7 | D9 | Gmaj7 | Cmaj7",
                                label="Her ölçü için bir akor (| ile ayırın)",
                            )
                            bpm = gr.Number(
                                value=None, minimum=40, maximum=240, label="BPM (dörtlük)",
                                info="Boş bırakırsanız davul WAV varsa oradan tempo alınır; yoksa 100 BPM kullanılır. "
                                "Girdiğiniz değer hem üretimi hem MIDI set_tempo metasını belirler.",
                            )
                            time_signature = gr.Dropdown(TIME_SIGS, value="4/4", label="Ölçü")
                        play_style = gr.Dropdown(STYLES, value="Fingerstyle", label="MODO stili")
                        performance_level = gr.Radio(
                            PERFORMANCE_LEVELS, value="Hareketli", label="Çalım yoğunluğu",
                            info="Geçiş notalarını, senkopları ve ölçü sonu dolgularını ayarlar.",
                        )
                        humanize = gr.Slider(0, 40, value=12, step=1, label="Humanize (ms)")
                        groove = gr.Slider(
                            0, 1, value=0.55, step=0.05, label="Groove / ghost yoğunluğu"
                        )
                        model_choice = gr.Dropdown(
                            MODEL_CHOICES,
                            value=(MODEL_EGE if EGE_CKPT.is_file()
                                   else MODEL_TURKISH if TURKISH_CKPT.is_file()
                                   else MODEL_ENSEMBLE if ENSEMBLE_CKPT.is_file()
                                   else MODEL_SESSION if SESSION_CKPT.is_file()
                                   else MODEL_PERFORMANCE if PERFORMANCE_CKPT.is_file()
                                   else MODEL_BEST if BEST_CKPT.is_file() else MODEL_RULES),
                            label="Model",
                        )
                        midi_port = gr.Dropdown(
                            choices=list_midi_ports(),
                            value=list_midi_ports()[0],
                            label="Virtual MIDI port (loopMIDI)",
                            allow_custom_value=True,
                        )
                        midi_target = gr.Dropdown(
                            [MIDI_MODO, MIDI_CONCERT], value=MIDI_MODO, label="MIDI hedefi",
                            info="MODO BASS 2 için enstrümanın kendi nota ve teknik eşlemesini kullanır.",
                        )
                        refresh = gr.Button("MIDI portlarını yenile")
                        do_stream = gr.Checkbox(
                            value=False, label="Oluşturunca canlı MIDI stream"
                        )
                        song_go = gr.Button("Şarkıya bas yaz", variant="primary")
                        go = gr.Button("Akorlardan bas yaz", variant="primary", visible=False)
                    with gr.Column():
                        midi_file = gr.File(label="İndirilebilir .mid")
                        log = gr.Textbox(
                            label="Durum · BPM / ölçü / süre / DAW önerisi",
                            lines=16,
                            info="Her üretimde BPM, ölçü, süre (saniye + ölçü/vuruş) ve Fender Studio Pro yerleştirme önerisi burada görünür.",
                        )

                def switch_mode(choice):
                    use_song = choice == song_mode
                    return [gr.update(visible=v) for v in (use_song, not use_song, use_song, not use_song)]

                mode.change(
                    switch_mode, inputs=mode, outputs=[song_controls, manual_controls, song_go, go],
                    queue=False,
                )
                song_go.click(
                    generate_for_song,
                    inputs=[song_file, song_meter, song_bpm, play_style, humanize, groove,
                            midi_port, do_stream, model_choice, performance_level, midi_target, song_chart, first_downbeat],
                    outputs=[midi_file, log],
                )
                refresh.click(
                    lambda: gr.update(choices=list_midi_ports()), outputs=midi_port
                )
                go.click(
                    generate,
                    inputs=[
                        drum,
                        chords,
                        bpm,
                        time_signature,
                        play_style,
                        humanize,
                        groove,
                        midi_port,
                        do_stream,
                        model_choice,
                        performance_level,
                        midi_target,
                    ],
                    outputs=[midi_file, log],
                )

            with gr.Tab("Eğitim Merkezi (Training)"):
                gr.Markdown(
                    """
                    ### Veri klasörleri
                    Windows masaüstündeki **Bas Gitar Loop** (ses) ve **Yuruyus Veri Seti**
                    (MIDI) klasörlerini kopyalayın / symlink edin, **veya** aşağıdaki
                    yollara doğrudan yazın (manuel kopya gerekmez):

                    - Ses → `dataset/raw_songs` veya özel yol / `MODO_RAW_SONGS_DIR`
                    - MIDI yürüyüşleri → `dataset/custom_midi` veya `MODO_CUSTOM_MIDI_DIR`

                    Genel eğitim **çok görevli kayıp** kullanır (pitch CE, MODO keyswitch CE,
                    micro-timing/duration Huber, velocity MSE). Her epoch sonunda canlı
                    günlükte **Akor Uyum Oranı (% In-Chord Notes)** ve
                    **Davul Kick Kilidi Oranı (% Kick-Lock Accuracy)** görünür.
                    """
                )
                raw_dir = gr.Textbox(
                    value=_default_raw_hint(),
                    label="Ham şarkı klasörü (MP3/WAV) — örn. Desktop\\Bas Gitar Loop",
                )
                midi_dir = gr.Textbox(
                    value=_default_midi_hint(),
                    label="Özel MIDI klasörü — örn. Desktop\\Yuruyus Veri Seti",
                )
                with gr.Row():
                    allow_synth = gr.Checkbox(
                        value=True,
                        label="raw_songs boşsa sentetik bootstrap üret",
                    )
                    epochs = gr.Slider(1, 50, value=5, step=1, label="Epoch")
                    batch = gr.Slider(1, 64, value=16, step=1, label="Batch")
                    device = gr.Dropdown(
                        ["auto", "cpu", "cuda"], value="auto", label="Cihaz"
                    )
                    ft_epochs = gr.Slider(1, 40, value=8, step=1, label="Fine-tune epoch")

                with gr.Row():
                    btn_prep = gr.Button("Veri Setini Hazırla", variant="secondary")
                    btn_train = gr.Button("Genel modeli eğit", variant="secondary")
                    btn_ft = gr.Button("Fine-tune (custom MIDI)", variant="secondary")

                with gr.Accordion("Performans ve stüdyo modellerinin eğitimi", open=False):
                    gr.Markdown(
                        "Akor ve vuruş bilgisi bulunan performans veri setini kullanır. "
                        "En iyi turu doğrulama kayıtlarından seçer."
                    )
                    train_model = gr.Radio([MODEL_TURKISH, MODEL_EGE, MODEL_ENSEMBLE, MODEL_SESSION, MODEL_PERFORMANCE], value=MODEL_TURKISH, label="Eğitilecek model")
                    btn_performance = gr.Button("Seçilen modeli yeniden eğit", variant="primary")
                train_log = gr.Textbox(label="Eğitim günlüğü (canlı)", lines=22)
                btn_performance.click(ui_run_performance_training, inputs=[device, train_model], outputs=train_log)

                btn_prep.click(
                    ui_prepare_dataset,
                    inputs=[raw_dir, allow_synth],
                    outputs=train_log,
                )
                btn_train.click(
                    ui_run_training,
                    inputs=[epochs, batch, device, raw_dir],
                    outputs=train_log,
                )
                btn_ft.click(
                    ui_run_finetune,
                    inputs=[midi_dir, ft_epochs, device],
                    outputs=train_log,
                )

        gr.Markdown(
            """
            ### Notlar
            - Windows: **loopMIDI** → Fender Studio Pro 8 → MODO BASS 2.
            - Model dosyaları `checkpoints/performance_bass.pt`,
              `checkpoints/best_bass_model.pt` ve `checkpoints/custom_style_bass.pt`
            - Keyswitch haritası: `config/modo_bass_map.json`
            """
        )
    return demo


def main() -> None:
    demo = build_ui()
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
