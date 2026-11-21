"""Build `dataset/processed/train_data.pt` from raw songs (MP3/WAV).

Pipeline per song:
  1. Demucs htdemucs → drums + bass (cached under dataset/cache/stems)
  2. Drum kick/snare onsets + velocity; bass pitch/duration/velocity/bend
  3. Auto BPM + beat grid + chord progression estimate
  4. Tokenize to model tensors; augment by transposing through all 12 keys

If `dataset/raw_songs` is empty, optionally emit a synthetic bootstrap set
(`--allow-synthetic`) so training can still run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import torch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data_prep.pipeline import AudioPrepPipeline, BassNoteEvent, DrumOnsets  # noqa: E402
from model_symbolic.bass_groove_model import (  # noqa: E402
    NOTE_OFFSET,
    PAD_ID,
    PITCH_MAX,
    PITCH_MIN,
    REST_ID,
    STYLE_TO_ID,
    beat_duration_ms,
    parse_chord,
    parse_time_signature,
)

logger = logging.getLogger("build_dataset")

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
PC_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# Chroma templates (12,) for maj / min / 7 / maj7 / m7
_CHORD_TEMPLATES: Dict[str, np.ndarray] = {
    "": np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0], dtype=np.float32),
    "m": np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], dtype=np.float32),
    "7": np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0], dtype=np.float32),
    "maj7": np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1], dtype=np.float32),
    "m7": np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0], dtype=np.float32),
}


@dataclass
class SongAnalysis:
    song_id: str
    path: str
    bpm: float
    time_signature: str
    chords: List[str]
    kick_ms: List[float]
    kick_vel: List[float]
    snare_ms: List[float]
    snare_vel: List[float]
    bass_notes: List[dict]
    micro_timing_ms: List[float]
    backend: str


def _song_id(path: Path) -> str:
    h = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:10]
    return f"{path.stem}_{h}"


def list_raw_songs(raw_dir: Path) -> List[Path]:
    if not raw_dir.exists():
        return []
    files = [p for p in sorted(raw_dir.iterdir()) if p.is_file() and p.suffix.lower() in AUDIO_EXTS]
    return files


def estimate_bpm(y: np.ndarray, sr: int) -> float:
    import librosa

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    if isinstance(tempo, np.ndarray):
        tempo = float(tempo.flat[0]) if tempo.size else 100.0
    bpm = float(tempo)
    if not math.isfinite(bpm) or bpm < 40 or bpm > 240:
        return 100.0
    return bpm


def estimate_chords(
    y: np.ndarray,
    sr: int,
    bpm: float,
    n_bars: Optional[int] = None,
    time_signature: str = "4/4",
) -> List[str]:
    """Bar-wise chroma template matching → chord symbols."""
    import librosa

    num, den = parse_time_signature(time_signature)
    beat_ms = beat_duration_ms(bpm, den)
    bar_ms = beat_ms * num
    duration_ms = len(y) / sr * 1000.0
    if n_bars is None:
        n_bars = max(1, int(round(duration_ms / bar_ms)))
    n_bars = max(1, min(n_bars, 64))

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    # Frame times
    hop = 512
    frame_ms = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop) * 1000.0

    chords: List[str] = []
    for bar_i in range(n_bars):
        t0 = bar_i * bar_ms
        t1 = t0 + bar_ms
        mask = (frame_ms >= t0) & (frame_ms < t1)
        if not np.any(mask):
            chords.append("C")
            continue
        vec = chroma[:, mask].mean(axis=1)
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        best_score = -1.0
        best_sym = "C"
        for root in range(12):
            rotated = np.roll(vec, -root)
            for qual, tmpl in _CHORD_TEMPLATES.items():
                t = tmpl / (np.linalg.norm(tmpl) + 1e-8)
                score = float(np.dot(rotated, t))
                if score > best_score:
                    best_score = score
                    best_sym = PC_NAMES[root] + qual
        chords.append(best_sym)
    return chords


def drum_onsets_with_velocity(
    y: np.ndarray,
    sr: int,
    pipe: AudioPrepPipeline,
) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Kick/snare ms + velocity (0..127) from onset strength."""
    import librosa

    onsets = pipe._onset_from_array(y, sr)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    times_ms = librosa.times_like(onset_env, sr=sr) * 1000.0
    peak = float(np.max(onset_env) + 1e-8)

    def vel_at(t_ms: float) -> float:
        idx = int(np.argmin(np.abs(times_ms - t_ms)))
        return float(np.clip(onset_env[idx] / peak * 127.0, 1, 127))

    kick_v = [vel_at(t) for t in onsets.kick_ms]
    snare_v = [vel_at(t) for t in onsets.snare_ms]
    return onsets.kick_ms, kick_v, onsets.snare_ms, snare_v


def micro_timing_for_notes(
    notes: Sequence[BassNoteEvent],
    bpm: float,
    time_signature: str = "4/4",
) -> List[float]:
    """Deviation from nearest 16th-note grid, in milliseconds."""
    num, den = parse_time_signature(time_signature)
    beat_ms = beat_duration_ms(bpm, den)
    grid = beat_ms / 4.0  # 16th
    out: List[float] = []
    for n in notes:
        nearest = round(n.start_ms / grid) * grid
        out.append(float(n.start_ms - nearest))
    return out


def transpose_note_dicts(notes: Sequence[dict], semitones: int) -> List[dict]:
    out = []
    for n in notes:
        p = int(n["pitch"]) + semitones
        if p < PITCH_MIN or p > PITCH_MAX:
            # wrap into bass range by octave
            while p > PITCH_MAX:
                p -= 12
            while p < PITCH_MIN:
                p += 12
        d = dict(n)
        d["pitch"] = p
        out.append(d)
    return out


def transpose_chords(chords: Sequence[str], semitones: int) -> List[str]:
    out = []
    for sym in chords:
        root, tones = parse_chord(sym)
        # recover quality string
        m_qual = sym
        for name in sorted(PC_NAMES, key=len, reverse=True):
            if sym.startswith(name):
                m_qual = sym[len(name) :]
                break
        new_root = (root + semitones) % 12
        out.append(PC_NAMES[new_root] + m_qual)
    return out


def encode_sample(
    bass_notes: Sequence[dict],
    chords: Sequence[str],
    bpm: float,
    time_signature: str,
    kick_ms: Sequence[float],
    snare_ms: Sequence[float],
    kick_vel: Optional[Sequence[float]] = None,
    snare_vel: Optional[Sequence[float]] = None,
    play_style: str = "Fingerstyle",
    max_steps: int = 256,
) -> dict:
    """Convert analysis → padded training tensors."""
    num, den = parse_time_signature(time_signature)
    beat_ms = beat_duration_ms(bpm, den)
    bar_ms = beat_ms * num
    step = beat_ms / 2.0  # 8th-note grid
    if bass_notes:
        total_ms = max(float(n["end_ms"]) for n in bass_notes)
    else:
        total_ms = bar_ms * max(1, len(chords))
    total_ms = max(total_ms, bar_ms * max(1, len(chords)))
    n_steps = min(max_steps, max(8, int(math.ceil(total_ms / step))))

    tokens = [REST_ID] * n_steps
    vels = [0.0] * n_steps
    bends = [0.0] * n_steps
    micro = [0.0] * n_steps
    for n in bass_notes:
        i = int(round(float(n["start_ms"]) / step))
        if 0 <= i < n_steps:
            pitch = int(np.clip(n["pitch"], PITCH_MIN, PITCH_MAX))
            tokens[i] = int(pitch - PITCH_MIN + NOTE_OFFSET)
            vels[i] = float(n.get("velocity", 80))
            bends[i] = float(n.get("pitch_bend", 0.0))
            # micro-timing vs grid
            nearest = round(float(n["start_ms"]) / step) * step
            micro[i] = float(n["start_ms"]) - nearest

    drum = torch.zeros(n_steps, 2)
    drum_vel = torch.zeros(n_steps, 2)
    chord_f = torch.zeros(n_steps, 12)
    meter = torch.zeros(n_steps, 4)
    chord_list = list(chords) if chords else ["C"]

    for i in range(n_steps):
        t_ms = i * step
        bar_i = min(len(chord_list) - 1, int(t_ms // bar_ms))
        root, tones = parse_chord(chord_list[bar_i])
        for tt in tones:
            chord_f[i, (root + tt) % 12] = 1.0
        for k_i, k in enumerate(kick_ms):
            if abs(t_ms - k) < step:
                drum[i, 0] = 1.0
                if kick_vel is not None and k_i < len(kick_vel):
                    drum_vel[i, 0] = float(kick_vel[k_i]) / 127.0
        for s_i, s in enumerate(snare_ms):
            if abs(t_ms - s) < step:
                drum[i, 1] = 1.0
                if snare_vel is not None and s_i < len(snare_vel):
                    drum_vel[i, 1] = float(snare_vel[s_i]) / 127.0
        meter[i] = torch.tensor(
            [num / 16.0, den / 16.0, min(bpm, 240) / 240.0, (t_ms % bar_ms) / bar_ms]
        )

    length = n_steps
    pad_n = max_steps - n_steps
    if pad_n > 0:
        tokens = tokens + [PAD_ID] * pad_n
        vels = vels + [0.0] * pad_n
        bends = bends + [0.0] * pad_n
        micro = micro + [0.0] * pad_n
        drum = torch.cat([drum, torch.zeros(pad_n, 2)], dim=0)
        drum_vel = torch.cat([drum_vel, torch.zeros(pad_n, 2)], dim=0)
        chord_f = torch.cat([chord_f, torch.zeros(pad_n, 12)], dim=0)
        meter = torch.cat([meter, torch.zeros(pad_n, 4)], dim=0)
    else:
        tokens = tokens[:max_steps]
        vels = vels[:max_steps]
        bends = bends[:max_steps]
        micro = micro[:max_steps]
        length = max_steps

    style = play_style if play_style in STYLE_TO_ID else "Fingerstyle"
    return {
        "tokens": torch.tensor(tokens, dtype=torch.long),
        "vels": torch.tensor(vels, dtype=torch.float32),
        "bends": torch.tensor(bends, dtype=torch.float32),
        "micro_ms": torch.tensor(micro, dtype=torch.float32),
        "drum": drum,
        "drum_vel": drum_vel,
        "chord": chord_f,
        "meter": meter,
        "style": torch.tensor(STYLE_TO_ID[style], dtype=torch.long),
        "length": length,
        "bpm": float(bpm),
        "time_signature": time_signature,
        "chords": list(chord_list),
    }


def _cache_paths(cache_dir: Path, song_id: str) -> Dict[str, Path]:
    d = cache_dir / song_id
    d.mkdir(parents=True, exist_ok=True)
    return {
        "dir": d,
        "drums": d / "drums.wav",
        "bass": d / "bass.wav",
        "meta": d / "meta.json",
        "analysis": d / "analysis.json",
    }


def separate_and_cache(
    audio_path: Path,
    cache_dir: Path,
    song_id: str,
    pipe: AudioPrepPipeline,
    log: Callable[[str], None] = logger.info,
) -> Dict[str, Path]:
    """Run Demucs (or librosa fallback) and cache stems. Skip if present."""
    paths = _cache_paths(cache_dir, song_id)
    if paths["drums"].exists() and paths["bass"].exists():
        log(f"[cache hit] {song_id}")
        return paths

    log(f"[separate] {audio_path.name} …")
    # Reuse pipeline demucs; write stems into cache
    pipe.work_dir = paths["dir"]
    result = pipe.process(audio_path)
    import soundfile as sf
    import librosa

    # Prefer demucs-written paths; else write arrays
    if result.drums_wav_path and Path(result.drums_wav_path).exists():
        # copy/rename into cache layout if needed
        if Path(result.drums_wav_path).resolve() != paths["drums"].resolve():
            y, sr = librosa.load(str(result.drums_wav_path), sr=pipe.sample_rate, mono=True)
            sf.write(str(paths["drums"]), y, pipe.sample_rate)
    else:
        # process() may have returned arrays only via fallback — re-load mix as drums
        y, sr = librosa.load(str(audio_path), sr=pipe.sample_rate, mono=True)
        sf.write(str(paths["drums"]), y, sr)

    if result.bass_wav_path and Path(result.bass_wav_path).exists():
        if Path(result.bass_wav_path).resolve() != paths["bass"].resolve():
            y, sr = librosa.load(str(result.bass_wav_path), sr=pipe.sample_rate, mono=True)
            sf.write(str(paths["bass"]), y, pipe.sample_rate)
    else:
        y, sr = librosa.load(str(audio_path), sr=pipe.sample_rate, mono=True)
        sf.write(str(paths["bass"]), y, sr)

    meta = {"source": str(audio_path), "backend": result.backend, "song_id": song_id}
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log(f"[cached] {song_id} backend={result.backend}")
    return paths


def analyze_song(
    audio_path: Path,
    cache_dir: Path,
    pipe: AudioPrepPipeline,
    time_signature: str = "4/4",
    play_style: str = "Fingerstyle",
    log: Callable[[str], None] = logger.info,
) -> SongAnalysis:
    import librosa

    song_id = _song_id(audio_path)
    paths = separate_and_cache(audio_path, cache_dir, song_id, pipe, log=log)

    # Prefer analysis cache
    if paths["analysis"].exists():
        raw = json.loads(paths["analysis"].read_text(encoding="utf-8"))
        return SongAnalysis(**raw)

    drums_y, sr = librosa.load(str(paths["drums"]), sr=pipe.sample_rate, mono=True)
    bass_y, _ = librosa.load(str(paths["bass"]), sr=pipe.sample_rate, mono=True)
    mix_y, _ = librosa.load(str(audio_path), sr=pipe.sample_rate, mono=True)

    bpm = estimate_bpm(mix_y if np.any(mix_y) else drums_y, sr)
    chords = estimate_chords(mix_y, sr, bpm, time_signature=time_signature)
    kick_ms, kick_vel, snare_ms, snare_vel = drum_onsets_with_velocity(drums_y, sr, pipe)

    # Bass transcription via pipeline helpers
    bass_notes_ev = pipe._transcribe_bass(bass_y, paths["bass"])
    micro = micro_timing_for_notes(bass_notes_ev, bpm, time_signature)
    bass_dicts = [
        {
            "start_ms": n.start_ms,
            "end_ms": n.end_ms,
            "pitch": n.pitch,
            "velocity": n.velocity,
            "pitch_bend": n.pitch_bend,
            "micro_timing_ms": micro[i] if i < len(micro) else 0.0,
        }
        for i, n in enumerate(bass_notes_ev)
    ]

    analysis = SongAnalysis(
        song_id=song_id,
        path=str(audio_path),
        bpm=bpm,
        time_signature=time_signature,
        chords=chords,
        kick_ms=kick_ms,
        kick_vel=kick_vel,
        snare_ms=snare_ms,
        snare_vel=snare_vel,
        bass_notes=bass_dicts,
        micro_timing_ms=micro,
        backend=json.loads(paths["meta"].read_text(encoding="utf-8")).get("backend", "unknown")
        if paths["meta"].exists()
        else "unknown",
    )
    paths["analysis"].write_text(json.dumps(asdict(analysis), indent=2), encoding="utf-8")
    log(
        f"[analyzed] {song_id}: bpm={bpm:.1f} bars={len(chords)} "
        f"bass_notes={len(bass_dicts)} kick={len(kick_ms)} snare={len(snare_ms)}"
    )
    _ = play_style
    return analysis


def samples_from_analysis(
    analysis: SongAnalysis,
    play_style: str = "Fingerstyle",
    max_steps: int = 256,
    transpose_all_keys: bool = True,
) -> List[dict]:
    samples: List[dict] = []
    keys = range(12) if transpose_all_keys else [0]
    for semi in keys:
        notes = transpose_note_dicts(analysis.bass_notes, semi)
        chords = transpose_chords(analysis.chords, semi)
        # Transpose drum times? timing stays; only pitch/chords change
        sample = encode_sample(
            notes,
            chords,
            analysis.bpm,
            analysis.time_signature,
            analysis.kick_ms,
            analysis.snare_ms,
            kick_vel=analysis.kick_vel,
            snare_vel=analysis.snare_vel,
            play_style=play_style,
            max_steps=max_steps,
        )
        sample["song_id"] = analysis.song_id
        sample["transpose"] = semi
        samples.append(sample)
    return samples


def synthetic_bootstrap_samples(
    n_songs: int = 4,
    max_steps: int = 256,
    seed: int = 0,
) -> List[dict]:
    """When raw_songs is empty — build synthetic rule-based sequences."""
    from model_symbolic.bass_groove_model import generate_bass_line_rules

    rng = np.random.default_rng(seed)
    progressions = [
        ["Am7", "D9", "Gmaj7", "Cmaj7"],
        ["Em7", "A7", "Dmaj7", "Gmaj7"],
        ["Dm7", "G7", "Cmaj7", "Fmaj7"],
        ["Cm7", "F7", "Bbmaj7", "Ebmaj7"],
    ]
    samples: List[dict] = []
    for i in range(n_songs):
        chords = progressions[i % len(progressions)]
        bpm = float(rng.uniform(80, 130))
        style = list(STYLE_TO_ID.keys())[i % len(STYLE_TO_ID)]
        num, den = 4, 4
        beat_ms = beat_duration_ms(bpm, den)
        bar_ms = beat_ms * num
        total_ms = bar_ms * len(chords)
        kick = [b * beat_ms for b in range(0, int(total_ms / beat_ms), num)]
        snare = [bar * bar_ms + 2 * beat_ms for bar in range(len(chords))]
        notes = generate_bass_line_rules(
            chords, bpm, "4/4", style, kick_ms=kick, snare_ms=snare, seed=int(seed) + i
        )
        bass_dicts = [
            {
                "start_ms": n.start_ms,
                "end_ms": n.end_ms,
                "pitch": n.pitch,
                "velocity": n.velocity,
                "pitch_bend": 0.0,
            }
            for n in notes
        ]
        analysis = SongAnalysis(
            song_id=f"synth_{i}",
            path="",
            bpm=bpm,
            time_signature="4/4",
            chords=chords,
            kick_ms=kick,
            kick_vel=[100.0] * len(kick),
            snare_ms=snare,
            snare_vel=[90.0] * len(snare),
            bass_notes=bass_dicts,
            micro_timing_ms=[0.0] * len(bass_dicts),
            backend="synthetic",
        )
        samples.extend(samples_from_analysis(analysis, play_style=style, max_steps=max_steps))
    return samples


def build_dataset(
    raw_dir: Optional[Path] = None,
    processed_dir: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    max_steps: int = 256,
    play_style: str = "Fingerstyle",
    time_signature: str = "4/4",
    transpose: bool = True,
    allow_synthetic: bool = True,
    log: Callable[[str], None] = logger.info,
) -> Path:
    raw_dir = Path(raw_dir or _ROOT / "dataset" / "raw_songs")
    processed_dir = Path(processed_dir or _ROOT / "dataset" / "processed")
    cache_dir = Path(cache_dir or _ROOT / "dataset" / "cache" / "stems")
    processed_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    songs = list_raw_songs(raw_dir)
    pipe = AudioPrepPipeline(work_dir=cache_dir)
    all_samples: List[dict] = []

    if not songs:
        msg = f"No audio in {raw_dir}"
        if allow_synthetic:
            log(msg + " — generating synthetic bootstrap set (12-key aug).")
            all_samples = synthetic_bootstrap_samples(max_steps=max_steps)
        else:
            raise FileNotFoundError(msg)
    else:
        log(f"Found {len(songs)} song(s) in {raw_dir}")
        for song in songs:
            try:
                analysis = analyze_song(
                    song,
                    cache_dir,
                    pipe,
                    time_signature=time_signature,
                    play_style=play_style,
                    log=log,
                )
                all_samples.extend(
                    samples_from_analysis(
                        analysis,
                        play_style=play_style,
                        max_steps=max_steps,
                        transpose_all_keys=transpose,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                log(f"[skip] {song.name}: {exc}")

    if not all_samples:
        raise RuntimeError("No training samples produced.")

    out_path = processed_dir / "train_data.pt"
    payload = {
        "samples": all_samples,
        "meta": {
            "n_samples": len(all_samples),
            "max_steps": max_steps,
            "n_songs": len(songs) if songs else 0,
            "transpose": transpose,
        },
    }
    torch.save(payload, out_path)
    log(f"Saved {len(all_samples)} samples → {out_path}")
    return out_path


def main() -> None:
    import os

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build MODO bass train_data.pt")
    parser.add_argument(
        "--raw",
        type=str,
        default="",
        help="Audio folder (MP3/WAV). Default: dataset/raw_songs or env MODO_RAW_SONGS_DIR. "
        "On Windows you can point at Desktop\\Bas Gitar Loop without copying.",
    )
    parser.add_argument("--out-dir", type=str, default=str(_ROOT / "dataset" / "processed"))
    parser.add_argument("--cache", type=str, default=str(_ROOT / "dataset" / "cache" / "stems"))
    parser.add_argument("--max-steps", type=int, default=256)
    parser.add_argument("--no-transpose", action="store_true")
    parser.add_argument("--no-synthetic", action="store_true")
    parser.add_argument("--style", type=str, default="Fingerstyle")
    args = parser.parse_args()
    raw = args.raw or os.environ.get("MODO_RAW_SONGS_DIR", "") or str(_ROOT / "dataset" / "raw_songs")
    build_dataset(
        raw_dir=Path(raw),
        processed_dir=Path(args.out_dir),
        cache_dir=Path(args.cache),
        max_steps=args.max_steps,
        play_style=args.style,
        transpose=not args.no_transpose,
        allow_synthetic=not args.no_synthetic,
    )


if __name__ == "__main__":
    main()
