"""Demucs stem separation + basic-pitch bass transcription + drum onset alignment.

Falls back to librosa-only analysis when demucs / basic-pitch are unavailable
so the rest of the app remains usable on CPU-only or constrained hosts.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import librosa
except ImportError as exc:  # pragma: no cover
    raise ImportError("librosa is required for data_prep.pipeline") from exc


@dataclass
class BassNoteEvent:
    """Single transcribed bass note."""

    start_ms: float
    end_ms: float
    pitch: int
    velocity: int
    pitch_bend: float = 0.0  # semitones (approx from pitch track)

    @property
    def duration_ms(self) -> float:
        return max(0.0, self.end_ms - self.start_ms)


@dataclass
class DrumOnsets:
    """Kick / snare onset times in milliseconds."""

    kick_ms: List[float] = field(default_factory=list)
    snare_ms: List[float] = field(default_factory=list)
    sample_rate: int = 44100

    def as_dict(self) -> Dict[str, List[float]]:
        return {"kick_ms": list(self.kick_ms), "snare_ms": list(self.snare_ms)}


@dataclass
class PrepResult:
    bass_notes: List[BassNoteEvent]
    drums: DrumOnsets
    bass_wav_path: Optional[Path] = None
    drums_wav_path: Optional[Path] = None
    backend: str = "librosa"


class AudioPrepPipeline:
    """Separate stems, transcribe bass, align drum onsets."""

    def __init__(
        self,
        sample_rate: int = 44100,
        demucs_model: str = "htdemucs",
        work_dir: Optional[Path] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.demucs_model = demucs_model
        self.work_dir = Path(work_dir) if work_dir else None

    # ------------------------------------------------------------------ API
    def process(self, audio_path: str | Path) -> PrepResult:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)

        stems = self._separate_stems(audio_path)
        bass_notes = self._transcribe_bass(stems["bass"], stems.get("bass_path"))
        drums = self._align_drum_onsets(stems["drums"], stems.get("drums_path"))
        return PrepResult(
            bass_notes=bass_notes,
            drums=drums,
            bass_wav_path=stems.get("bass_path"),
            drums_wav_path=stems.get("drums_path"),
            backend=stems.get("backend", "librosa"),
        )

    def analyze_drums_only(self, drum_wav: str | Path) -> DrumOnsets:
        """Analyze a drum-only (or full-mix) WAV for kick/snare onsets."""
        y, sr = librosa.load(str(drum_wav), sr=self.sample_rate, mono=True)
        return self._onset_from_array(y, sr)

    # ----------------------------------------------------------- separation
    def _separate_stems(self, audio_path: Path) -> Dict[str, Any]:
        try:
            return self._demucs_separate(audio_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Demucs unavailable/failed (%s); using full mix for both stems.", exc)
            y, sr = librosa.load(str(audio_path), sr=self.sample_rate, mono=True)
            return {"bass": y, "drums": y, "sr": sr, "backend": "librosa-fallback"}

    def _demucs_separate(self, audio_path: Path) -> Dict[str, Any]:
        import torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model
        from demucs.audio import AudioFile, save_audio

        model = get_model(self.demucs_model)
        model.eval()
        wav = AudioFile(audio_path).read(
            streams=0,
            samplerate=model.samplerate,
            channels=model.audio_channels,
        )
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / (ref.std() + 1e-8)
        with torch.no_grad():
            sources = apply_model(model, wav[None], device="cpu", split=True, overlap=0.25)[0]
        sources = sources * (ref.std() + 1e-8) + ref.mean()
        names = model.sources  # typically drums, bass, other, vocals
        out: Dict[str, Any] = {"sr": model.samplerate, "backend": f"demucs:{self.demucs_model}"}
        work = self.work_dir or Path(tempfile.mkdtemp(prefix="modo_stems_"))
        work.mkdir(parents=True, exist_ok=True)
        for name, source in zip(names, sources):
            mono = source.mean(0).cpu().numpy()
            path = work / f"{name}.wav"
            save_audio(source.cpu(), path, model.samplerate)
            out[name] = mono
            out[f"{name}_path"] = path
        if "bass" not in out:
            out["bass"] = out.get("other", wav.mean(0).numpy())
        if "drums" not in out:
            out["drums"] = out.get("other", wav.mean(0).numpy())
        return out

    # ----------------------------------------------------------- transcription
    def _transcribe_bass(
        self,
        bass_audio: np.ndarray,
        bass_path: Optional[Path] = None,
    ) -> List[BassNoteEvent]:
        try:
            return self._basic_pitch_transcribe(bass_audio, bass_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("basic-pitch failed (%s); falling back to librosa pitch track.", exc)
            return self._librosa_transcribe(bass_audio)

    def _basic_pitch_transcribe(
        self,
        bass_audio: np.ndarray,
        bass_path: Optional[Path],
    ) -> List[BassNoteEvent]:
        from basic_pitch.inference import predict
        from basic_pitch import ICASSP_2022_MODEL_PATH

        if bass_path is None:
            tmp = Path(tempfile.mkdtemp(prefix="modo_bass_")) / "bass.wav"
            import soundfile as sf

            sf.write(str(tmp), bass_audio, self.sample_rate)
            bass_path = tmp

        _model_out, midi_data, note_events = predict(str(bass_path), ICASSP_2022_MODEL_PATH)
        notes: List[BassNoteEvent] = []
        # note_events: list of (start_s, end_s, pitch, amplitude, …)
        for ev in note_events:
            start_s, end_s, pitch, amp = float(ev[0]), float(ev[1]), int(ev[2]), float(ev[3])
            vel = int(np.clip(amp * 127.0, 1, 127))
            notes.append(
                BassNoteEvent(
                    start_ms=start_s * 1000.0,
                    end_ms=end_s * 1000.0,
                    pitch=pitch,
                    velocity=vel,
                    pitch_bend=0.0,
                )
            )
        notes.sort(key=lambda n: n.start_ms)
        return self._attach_pitch_bend(bass_audio, notes)

    def _librosa_transcribe(self, y: np.ndarray) -> List[BassNoteEvent]:
        sr = self.sample_rate
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("E1"),
            fmax=librosa.note_to_hz("G4"),
            sr=sr,
        )
        times = librosa.times_like(f0, sr=sr)
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        rms = np.interp(np.linspace(0, 1, len(f0)), np.linspace(0, 1, len(rms)), rms)

        notes: List[BassNoteEvent] = []
        active_pitch: Optional[int] = None
        start_idx = 0
        bends: List[float] = []

        def flush(end_idx: int) -> None:
            nonlocal active_pitch, bends
            if active_pitch is None:
                return
            start_ms = float(times[start_idx] * 1000.0)
            end_ms = float(times[min(end_idx, len(times) - 1)] * 1000.0)
            seg_rms = float(np.nanmean(rms[start_idx : end_idx + 1]))
            vel = int(np.clip(seg_rms / (np.nanmax(rms) + 1e-8) * 127.0, 20, 127))
            bend = float(np.nanmean(bends)) if bends else 0.0
            notes.append(
                BassNoteEvent(
                    start_ms=start_ms,
                    end_ms=max(end_ms, start_ms + 40.0),
                    pitch=active_pitch,
                    velocity=vel,
                    pitch_bend=bend,
                )
            )
            active_pitch = None
            bends = []

        for i, (hz, voiced) in enumerate(zip(f0, voiced_flag)):
            if not voiced or hz is None or np.isnan(hz):
                flush(i)
                continue
            midi_f = librosa.hz_to_midi(hz)
            pitch = int(round(midi_f))
            bend = float(midi_f - pitch)
            if active_pitch is None:
                active_pitch = pitch
                start_idx = i
                bends = [bend]
            elif abs(pitch - active_pitch) >= 1:
                flush(i)
                active_pitch = pitch
                start_idx = i
                bends = [bend]
            else:
                bends.append(bend)
        flush(len(f0) - 1)
        return notes

    def _attach_pitch_bend(self, y: np.ndarray, notes: List[BassNoteEvent]) -> List[BassNoteEvent]:
        if not notes:
            return notes
        try:
            f0, voiced_flag, _ = librosa.pyin(
                y,
                fmin=librosa.note_to_hz("E1"),
                fmax=librosa.note_to_hz("G4"),
                sr=self.sample_rate,
            )
            times = librosa.times_like(f0, sr=self.sample_rate) * 1000.0
            for note in notes:
                mask = (times >= note.start_ms) & (times <= note.end_ms) & voiced_flag
                if not np.any(mask):
                    continue
                midi_f = librosa.hz_to_midi(f0[mask])
                note.pitch_bend = float(np.nanmean(midi_f) - note.pitch)
        except Exception as exc:  # noqa: BLE001
            logger.debug("pitch-bend attach skipped: %s", exc)
        return notes

    # ----------------------------------------------------------- drum onsets
    def _align_drum_onsets(
        self,
        drums_audio: np.ndarray,
        drums_path: Optional[Path] = None,
    ) -> DrumOnsets:
        _ = drums_path
        return self._onset_from_array(drums_audio, self.sample_rate)

    def _onset_from_array(self, y: np.ndarray, sr: int) -> DrumOnsets:
        # Spectral flux onsets, then split by spectral centroid (kick=low, snare=high)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env, sr=sr, units="frames", backtrack=True
        )
        onset_times_ms = librosa.frames_to_time(onset_frames, sr=sr) * 1000.0

        S = np.abs(librosa.stft(y))
        cents = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
        kick: List[float] = []
        snare: List[float] = []
        for frame, t_ms in zip(onset_frames, onset_times_ms):
            c = float(cents[min(frame, len(cents) - 1)])
            # Empirical split ~2.2 kHz works for many rock/pop kits
            if c < 2200.0:
                kick.append(float(t_ms))
            else:
                snare.append(float(t_ms))
        return DrumOnsets(kick_ms=kick, snare_ms=snare, sample_rate=sr)


def parse_time_signature(ts: str) -> Tuple[int, int]:
    """Parse '4/4', '7/8', … into (numerator, denominator)."""
    parts = ts.strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid time signature: {ts}")
    return int(parts[0]), int(parts[1])
