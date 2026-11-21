"""Gradio UI: drum WAV + chords → MODO BASS 2 MIDI (+ optional rtmidi stream)."""

from __future__ import annotations

import logging
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

# Project root on sys.path when launched as `python web_ui/app.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import gradio as gr
import numpy as np

from data_prep.pipeline import AudioPrepPipeline
from model_symbolic.bass_groove_model import generate_bass_line
from modo_mapper.articulation_engine import ArticulationEngine, BassMelodyNote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("modo_bass_ui")

CONFIG_PATH = _ROOT / "config" / "modo_bass_map.json"
CHECKPOINT = _ROOT / "checkpoints" / "bass_groove.pt"
OUTPUT_DIR = _ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STYLES = ["Fingerstyle", "Slap", "Fretless", "Pick", "Mute"]
TIME_SIGS = ["4/4", "3/4", "6/8", "5/8", "7/8", "9/8", "12/8"]


def list_midi_ports() -> List[str]:
    # Headless Linux CI/cloud often has no ALSA sequencer (/dev/snd/seq).
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
    """Blocking realtime playback to a virtual MIDI port (e.g. loopMIDI)."""
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
            target = t0 + abs_t
            delay = target - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            for msg_type, data in msgs:
                send(msg_type, data)
        status_lines.append("Stream tamamlandı.")
    except Exception as exc:  # noqa: BLE001
        status_lines.append(f"Stream hatası: {exc}")
    finally:
        # All notes off
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
    use_checkpoint: bool,
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
                drum_info = (
                    f"Kick onset: {len(kick_ms)} | Snare onset: {len(snare_ms)} "
                    f"(backend librosa onset)"
                )
            except Exception as exc:  # noqa: BLE001
                drum_info = f"Davul analizi başarısız ({exc}); kural motoru devam ediyor."

    progress(0.45, desc="Bas hattı üretiliyor")
    ckpt = CHECKPOINT if use_checkpoint and CHECKPOINT.exists() else None
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
        force_rules=ckpt is None,
    )
    melody = _to_melody(notes)

    progress(0.7, desc="MODO keyswitch / CC yazılıyor")
    engine = ArticulationEngine(CONFIG_PATH)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    mid_path = OUTPUT_DIR / f"modo_bass_{stamp}.mid"
    engine.write_midi(melody, mid_path, play_style=play_style)

    stream_status = "Canlı stream seçilmedi."
    if do_stream:
        progress(0.85, desc="MIDI portuna stream")
        # Run stream in-thread so Gradio stays responsive for download
        result_box: List[str] = []

        def _run() -> None:
            result_box.append(stream_to_port(melody, play_style, midi_port, engine))

        th = threading.Thread(target=_run, daemon=True)
        th.start()
        th.join(timeout=max(30.0, (notes[-1].end_ms / 1000.0) + 5.0 if notes else 30.0))
        stream_status = result_box[0] if result_box else "Stream zaman aşımı / hâlâ çalıyor."

    progress(1.0, desc="Tamam")
    summary = (
        f"Notalar: {len(notes)}\n"
        f"{drum_info}\n"
        f"Stil: {play_style} | {bpm} BPM | {time_signature}\n"
        f"MIDI: {mid_path.name}\n"
        f"{stream_status}"
    )
    return str(mid_path), summary


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="MODO BASS AI") as demo:
        gr.Markdown(
            """
            # MODO BASS AI
            Davul WAV + akor ilerlemesi → insanvari bas MIDI (keyswitch + CC) →
            **Fender Studio Pro 8 / MODO BASS 2** (loopMIDI).
            """
        )
        with gr.Row():
            with gr.Column():
                drum = gr.Audio(sources=["upload"], type="filepath", label="Davul WAV (opsiyonel)")
                chords = gr.Textbox(
                    value="Am7 | D9 | Gmaj7 | Cmaj7",
                    label="Akorlar ( | ile ayırın)",
                )
                bpm = gr.Slider(40, 200, value=100, step=1, label="BPM")
                time_signature = gr.Dropdown(TIME_SIGS, value="4/4", label="Ölçü")
                play_style = gr.Dropdown(STYLES, value="Fingerstyle", label="MODO stili")
                humanize = gr.Slider(0, 40, value=12, step=1, label="Humanize (ms)")
                groove = gr.Slider(0, 1, value=0.55, step=0.05, label="Groove / ghost yoğunluğu")
                use_ckpt = gr.Checkbox(
                    value=False,
                    label="Eğitilmiş checkpoint kullan (varsa checkpoints/bass_groove.pt)",
                )
                midi_port = gr.Dropdown(
                    choices=list_midi_ports(),
                    value=list_midi_ports()[0],
                    label="Virtual MIDI port (loopMIDI)",
                    allow_custom_value=True,
                )
                refresh = gr.Button("MIDI portlarını yenile")
                do_stream = gr.Checkbox(value=False, label="Oluşturunca canlı MIDI stream")
                go = gr.Button("MIDI üret", variant="primary")
            with gr.Column():
                midi_file = gr.File(label="İndirilebilir .mid")
                log = gr.Textbox(label="Durum", lines=12)

        refresh.click(lambda: gr.update(choices=list_midi_ports()), outputs=midi_port)
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
                use_ckpt,
            ],
            outputs=[midi_file, log],
        )
        gr.Markdown(
            """
            ### Notlar
            - Windows: **loopMIDI** sanal port → Fender Studio Pro 8 MIDI In → MODO BASS 2.
            - Linux: ALSA `snd-virmidi` / a2jmidid; macOS: IAC Driver.
            - Keyswitch haritası `config/modo_bass_map.json` — preset’iniz farklıysa düzenleyin.
            """
        )
    return demo


def main() -> None:
    demo = build_ui()
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
