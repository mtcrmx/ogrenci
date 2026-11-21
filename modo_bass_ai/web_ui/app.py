"""Gradio UI: performance + Training Merkezi for MODO BASS AI."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import gradio as gr

from data_prep.pipeline import AudioPrepPipeline
from model_symbolic.bass_groove_model import generate_bass_line
from modo_mapper.articulation_engine import ArticulationEngine, BassMelodyNote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("modo_bass_ui")

CONFIG_PATH = _ROOT / "config" / "modo_bass_map.json"
BEST_CKPT = _ROOT / "checkpoints" / "best_bass_model.pt"
CUSTOM_CKPT = _ROOT / "checkpoints" / "custom_style_bass.pt"
OUTPUT_DIR = _ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STYLES = ["Fingerstyle", "Slap", "Fretless", "Pick", "Mute"]
TIME_SIGS = ["4/4", "3/4", "6/8", "5/8", "7/8", "9/8", "12/8"]

MODEL_RULES = "Kural Tabanlı Hibrit"
MODEL_BEST = "Eğitilmiş Genel Basçı (best_bass_model)"
MODEL_CUSTOM = "Özel Tarzım (custom_style_bass)"
MODEL_CHOICES = [MODEL_RULES, MODEL_BEST, MODEL_CUSTOM]


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

    def send(msg_type: str, data: Tuple[int, ...]) -> None:
        if msg_type == "note_on":
            midi_out.send_message([0x90, data[0], data[1]])
        elif msg_type == "note_off":
            midi_out.send_message([0x80, data[0], 0])
        elif msg_type == "control_change":
            midi_out.send_message([0xB0, data[0], data[1]])

    t0 = time.perf_counter()
    try:
        for abs_t, msgs in engine.iter_realtime_messages(melody, play_style=play_style):
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
            midi_out.send_message([0xB0, 123, 0])
        except Exception:  # noqa: BLE001
            pass
        midi_out.close_port()
        del midi_out
    return "\n".join(status_lines)


def generate(
    drum_wav,
    chords: str,
    bpm: float,
    time_signature: str,
    play_style: str,
    humanize_ms: float,
    groove_amount: float,
    midi_port: str,
    do_stream: bool,
    model_choice: str,
    progress=gr.Progress(track_tqdm=False),
):
    progress(0.05, desc="Hazırlanıyor")
    kick_ms: List[float] = []
    snare_ms: List[float] = []
    drum_info = "Davul WAV yok — yalnızca akor/ritim kuralları."

    if drum_wav is not None:
        progress(0.2, desc="Davul onset analizi")
        path = drum_wav if isinstance(drum_wav, str) else getattr(drum_wav, "name", None)
        if path:
            pipe = AudioPrepPipeline()
            try:
                onsets = pipe.analyze_drums_only(path)
                kick_ms = onsets.kick_ms
                snare_ms = onsets.snare_ms
                drum_info = f"Kick: {len(kick_ms)} | Snare: {len(snare_ms)}"
            except Exception as exc:  # noqa: BLE001
                drum_info = f"Davul analizi başarısız ({exc})."

    ckpt, force_rules = resolve_checkpoint(model_choice)
    if model_choice != MODEL_RULES and ckpt is None:
        drum_info += f"\nUyarı: {model_choice} checkpoint yok → kural hibrit."
    elif ckpt is not None:
        drum_info += f"\nModel: {ckpt.name}"

    progress(0.45, desc="Bas hattı üretiliyor")
    notes = generate_bass_line(
        chords or "Am7 | D9 | Gmaj7 | Cmaj7",
        bpm=float(bpm),
        time_signature=time_signature,
        play_style=play_style,
        kick_ms=kick_ms,
        snare_ms=snare_ms,
        humanize_ms=float(humanize_ms),
        groove_amount=float(groove_amount),
        checkpoint=ckpt,
        force_rules=force_rules,
    )
    melody = _to_melody(notes)

    progress(0.7, desc="MODO keyswitch / CC")
    engine = ArticulationEngine(CONFIG_PATH)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    mid_path = OUTPUT_DIR / f"modo_bass_{stamp}.mid"
    engine.write_midi(melody, mid_path, play_style=play_style)

    stream_status = "Canlı stream seçilmedi."
    if do_stream:
        progress(0.85, desc="MIDI stream")
        box: List[str] = []

        def _run() -> None:
            box.append(stream_to_port(melody, play_style, midi_port, engine))

        th = threading.Thread(target=_run, daemon=True)
        th.start()
        th.join(timeout=max(30.0, (notes[-1].end_ms / 1000.0) + 5.0 if notes else 30.0))
        stream_status = box[0] if box else "Stream zaman aşımı."

    progress(1.0, desc="Tamam")
    summary = (
        f"Notalar: {len(notes)}\n{drum_info}\n"
        f"Seçim: {model_choice}\n"
        f"Stil: {play_style} | {bpm} BPM | {time_signature}\n"
        f"MIDI: {mid_path.name}\n{stream_status}"
    )
    return str(mid_path), summary


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
            Davul WAV + akor → insanvari bas MIDI (keyswitch + CC) →
            **Fender Studio Pro 8 / MODO BASS 2** (loopMIDI).
            """
        )
        with gr.Tabs():
            with gr.Tab("Performans"):
                with gr.Row():
                    with gr.Column():
                        drum = gr.Audio(
                            sources=["upload"], type="filepath", label="Davul WAV (opsiyonel)"
                        )
                        chords = gr.Textbox(
                            value="Am7 | D9 | Gmaj7 | Cmaj7",
                            label="Akorlar ( | ile ayırın)",
                        )
                        bpm = gr.Slider(40, 200, value=100, step=1, label="BPM")
                        time_signature = gr.Dropdown(TIME_SIGS, value="4/4", label="Ölçü")
                        play_style = gr.Dropdown(STYLES, value="Fingerstyle", label="MODO stili")
                        humanize = gr.Slider(0, 40, value=12, step=1, label="Humanize (ms)")
                        groove = gr.Slider(
                            0, 1, value=0.55, step=0.05, label="Groove / ghost yoğunluğu"
                        )
                        model_choice = gr.Dropdown(
                            MODEL_CHOICES,
                            value=MODEL_RULES,
                            label="Model",
                        )
                        midi_port = gr.Dropdown(
                            choices=list_midi_ports(),
                            value=list_midi_ports()[0],
                            label="Virtual MIDI port (loopMIDI)",
                            allow_custom_value=True,
                        )
                        refresh = gr.Button("MIDI portlarını yenile")
                        do_stream = gr.Checkbox(
                            value=False, label="Oluşturunca canlı MIDI stream"
                        )
                        go = gr.Button("MIDI üret", variant="primary")
                    with gr.Column():
                        midi_file = gr.File(label="İndirilebilir .mid")
                        log = gr.Textbox(label="Durum", lines=14)

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
                    btn_train = gr.Button("Eğitimi Başlat", variant="primary")
                    btn_ft = gr.Button("Fine-tune (custom MIDI)", variant="secondary")

                train_log = gr.Textbox(label="Eğitim günlüğü (canlı)", lines=22)

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
            - Checkpoint’ler: `checkpoints/best_bass_model.pt`,
              `checkpoints/custom_style_bass.pt`
            - Keyswitch haritası: `config/modo_bass_map.json`
            """
        )
    return demo


def main() -> None:
    demo = build_ui()
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
