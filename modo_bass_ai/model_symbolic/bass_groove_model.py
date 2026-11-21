"""PyTorch Transformer bass groove model + hybrid music-theory inference.

When no checkpoint is loaded (or weights are random), `generate_bass_line`
falls back to deterministic groove / theory rules so the app works untrained.
"""

from __future__ import annotations

import logging
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

# Pitch vocabulary: MIDI 28 (E1) .. 67 (G4) + specials
PITCH_MIN = 28
PITCH_MAX = 67
N_PITCH = PITCH_MAX - PITCH_MIN + 1  # 40
PAD_ID = 0
REST_ID = 1
NOTE_OFFSET = 2  # token = pitch - PITCH_MIN + NOTE_OFFSET
VOCAB_SIZE = NOTE_OFFSET + N_PITCH  # 42

STYLE_TO_ID = {
    "Fingerstyle": 0,
    "Slap": 1,
    "Fretless": 2,
    "Pick": 3,
    "Mute": 4,
}
N_STYLES = len(STYLE_TO_ID)

# Chord quality → relative scale degrees (semitones from root)
CHORD_TONES: Dict[str, List[int]] = {
    "": [0, 4, 7],
    "maj": [0, 4, 7],
    "M": [0, 4, 7],
    "min": [0, 3, 7],
    "m": [0, 3, 7],
    "-": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "M7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
    "min7": [0, 3, 7, 10],
    "9": [0, 4, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
    "m9": [0, 3, 7, 10, 14],
    "m7b5": [0, 3, 6, 10],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "6": [0, 4, 7, 9],
    "m6": [0, 3, 7, 9],
    "add9": [0, 4, 7, 14],
}

NOTE_NAME_TO_PC = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}


@dataclass
class GrooveConfig:
    bpm: float = 100.0
    time_signature: str = "4/4"
    play_style: str = "Fingerstyle"
    humanize_ms: float = 12.0
    groove_amount: float = 0.55  # 0..1 swing / ghost density
    bars: Optional[int] = None  # defaults to len(chords)
    seed: Optional[int] = None


@dataclass
class GeneratedNote:
    start_ms: float
    end_ms: float
    pitch: int
    velocity: int
    articulation: Optional[str] = None
    is_passing: bool = False


# ------------------------------------------------------------------ model
class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 2048) -> None:
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div)
        pe[:, 1::2] = torch.cos(position * div)
        self.register_buffer("pe", pe.unsqueeze(0), persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class BassGrooveModel(nn.Module):
    """Autoregressive Transformer over pitch tokens conditioned on groove context."""

    def __init__(
        self,
        d_model: int = 128,
        nhead: int = 4,
        num_layers: int = 4,
        dim_feedforward: int = 256,
        dropout: float = 0.1,
        max_len: int = 512,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.pitch_emb = nn.Embedding(VOCAB_SIZE, d_model)
        self.style_emb = nn.Embedding(N_STYLES, d_model)
        self.drum_proj = nn.Linear(2, d_model)  # kick/snare density per step
        self.chord_proj = nn.Linear(12, d_model)  # pitch-class chroma
        self.meter_proj = nn.Linear(4, d_model)  # num, den, bpm_norm, beat_pos
        self.pos = PositionalEncoding(d_model, max_len=max_len)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.head = nn.Linear(d_model, VOCAB_SIZE)
        self.vel_head = nn.Linear(d_model, 1)

    def forward(
        self,
        tokens: torch.Tensor,
        style_id: torch.Tensor,
        drum_feats: torch.Tensor,
        chord_feats: torch.Tensor,
        meter_feats: torch.Tensor,
        src_key_padding_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        tokens: (B, T) long
        style_id: (B,) long
        drum_feats: (B, T, 2)
        chord_feats: (B, T, 12)
        meter_feats: (B, T, 4)
        returns logits (B,T,V), velocity (B,T)
        """
        x = self.pitch_emb(tokens) * math.sqrt(self.d_model)
        x = x + self.style_emb(style_id).unsqueeze(1)
        x = x + self.drum_proj(drum_feats)
        x = x + self.chord_proj(chord_feats)
        x = x + self.meter_proj(meter_feats)
        x = self.pos(x)
        # Causal mask
        t = tokens.size(1)
        causal = torch.triu(torch.ones(t, t, device=tokens.device, dtype=torch.bool), diagonal=1)
        h = self.encoder(x, mask=causal, src_key_padding_mask=src_key_padding_mask)
        logits = self.head(h)
        vel = torch.sigmoid(self.vel_head(h)).squeeze(-1) * 127.0
        return logits, vel

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": self.state_dict(), "vocab": VOCAB_SIZE}, path)

    def load(self, path: str | Path, map_location: str = "cpu") -> None:
        ckpt = torch.load(path, map_location=map_location)
        self.load_state_dict(ckpt["state_dict"])


# ----------------------------------------------------------- theory helpers
def parse_chord(symbol: str) -> Tuple[int, List[int]]:
    """Return (root_pc, chord_tone_semitones)."""
    symbol = symbol.strip()
    if not symbol or symbol == "N.C." or symbol.upper() == "NC":
        return 0, [0, 7]
    m = re.match(r"^([A-Ga-g](?:#|b)?)(.*)$", symbol)
    if not m:
        return 0, [0, 4, 7]
    root_name, quality = m.group(1), m.group(2).strip()
    # Normalize quality keys
    q = quality.replace("Δ", "maj").replace("Major", "maj").replace("minor", "m")
    q = q.replace("min", "m").replace("Maj", "maj")
    root = NOTE_NAME_TO_PC.get(root_name[0].upper() + root_name[1:], 0)
    tones = None
    # Try longest quality match
    for key in sorted(CHORD_TONES.keys(), key=len, reverse=True):
        if key and q.startswith(key):
            tones = CHORD_TONES[key]
            break
    if tones is None:
        if q.startswith("m") or q.startswith("-"):
            tones = CHORD_TONES["m"]
        elif not q:
            tones = CHORD_TONES[""]
        else:
            # e.g. maj7, 7, 9 already covered; default triad
            tones = CHORD_TONES["7"] if "7" in q else CHORD_TONES[""]
    return root, list(tones)


def parse_progression(text: str) -> List[str]:
    """Split 'Am7 | D9 | Gmaj7 | Cmaj7' or comma-separated chords."""
    text = text.replace(",", "|")
    parts = [p.strip() for p in text.split("|")]
    return [p for p in parts if p]


def parse_time_signature(ts: str) -> Tuple[int, int]:
    num, den = ts.strip().split("/")
    return int(num), int(den)


def beat_duration_ms(bpm: float, denominator: int = 4) -> float:
    quarter_ms = 60_000.0 / max(bpm, 1.0)
    return quarter_ms * (4.0 / denominator)


def bar_duration_ms(bpm: float, time_signature: str) -> float:
    num, den = parse_time_signature(time_signature)
    return beat_duration_ms(bpm, den) * num


def _nearest_chord_tone(pitch: int, root: int, tones: Sequence[int]) -> int:
    pcs = [(root + t) % 12 for t in tones]
    best = pitch
    best_d = 99
    for pc in pcs:
        # candidate in same octave region
        for octv in range(1, 5):
            cand = pc + 12 * octv
            if cand < PITCH_MIN or cand > PITCH_MAX:
                continue
            d = abs(cand - pitch)
            if d < best_d:
                best_d = d
                best = cand
    return best


def _chromatic_approach(target: int, from_pitch: Optional[int]) -> Optional[int]:
    if from_pitch is None:
        return None
    direction = 1 if target >= from_pitch else -1
    approach = target - direction
    if PITCH_MIN <= approach <= PITCH_MAX and approach != from_pitch:
        return approach
    return None


def _humanize(t_ms: float, amount_ms: float, rng: random.Random) -> float:
    if amount_ms <= 0:
        return t_ms
    return t_ms + rng.uniform(-amount_ms, amount_ms)


def _swing_offset(beat_idx: float, beat_ms: float, groove: float, num: int, den: int) -> float:
    """Delay off-beats slightly (swing) for duple meters."""
    if den != 4 or num not in (3, 4) or groove <= 0:
        return 0.0
    frac = beat_idx - math.floor(beat_idx)
    if 0.45 < frac < 0.55:
        return beat_ms * 0.08 * groove
    return 0.0


def _kick_snare_grids(
    kick_ms: Sequence[float],
    snare_ms: Sequence[float],
    total_ms: float,
    beat_ms: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Quantize onsets onto beat grid → density vectors."""
    n_beats = max(1, int(math.ceil(total_ms / beat_ms)))
    kick = np.zeros(n_beats, dtype=np.float32)
    snare = np.zeros(n_beats, dtype=np.float32)
    for t in kick_ms:
        i = int(round(t / beat_ms))
        if 0 <= i < n_beats:
            kick[i] = 1.0
    for t in snare_ms:
        i = int(round(t / beat_ms))
        if 0 <= i < n_beats:
            snare[i] = 1.0
    return kick, snare


# ----------------------------------------------------------- hybrid generate
def generate_bass_line_rules(
    chords: Sequence[str],
    bpm: float,
    time_signature: str,
    play_style: str,
    kick_ms: Optional[Sequence[float]] = None,
    snare_ms: Optional[Sequence[float]] = None,
    humanize_ms: float = 12.0,
    groove_amount: float = 0.55,
    seed: Optional[int] = None,
) -> List[GeneratedNote]:
    """Music-theory + drum-lock groove writer (works without training)."""
    rng = random.Random(seed)
    kick_ms = list(kick_ms or [])
    snare_ms = list(snare_ms or [])
    num, den = parse_time_signature(time_signature)
    beat_ms = beat_duration_ms(bpm, den)
    bar_ms = beat_ms * num
    notes: List[GeneratedNote] = []

    # Style velocity / density presets
    style = play_style if play_style in STYLE_TO_ID else "Fingerstyle"
    base_vel = {"Fingerstyle": 88, "Slap": 100, "Fretless": 78, "Pick": 92, "Mute": 70}[style]
    ghost_prob = 0.12 + 0.25 * groove_amount
    if style == "Slap":
        ghost_prob += 0.15
    if style == "Mute":
        ghost_prob += 0.1
    passing_prob = 0.18 + 0.2 * groove_amount

    prev_pitch: Optional[int] = None

    for bar_i, chord_sym in enumerate(chords):
        root, tones = parse_chord(chord_sym)
        # Root around E1.. for comfort — prefer pitch near previous
        prefer = prev_pitch if prev_pitch is not None else 33  # A1-ish
        root_pitch = _nearest_chord_tone(prefer - (prefer % 12) + root, root, [0])
        fifth = _nearest_chord_tone(root_pitch, root, [7])
        third = _nearest_chord_tone(root_pitch, root, [tones[1] if len(tones) > 1 else 4])
        octave = min(PITCH_MAX, root_pitch + 12)

        bar_start = bar_i * bar_ms

        # Pattern by meter
        if (num, den) == (4, 4):
            anchors = [0.0, 1.0, 2.0, 3.0]  # beats
            roles = ["root", "fifth", "root", "octave"]
        elif (num, den) == (3, 4):
            anchors = [0.0, 1.0, 2.0]
            roles = ["root", "fifth", "third"]
        elif den == 8:
            # Odd meters: hit beat 1 strongly, then +2/+3 groupings
            anchors = [float(i) for i in range(num)]
            roles = []
            for i in range(num):
                if i == 0:
                    roles.append("root")
                elif i % 3 == 0:
                    roles.append("fifth")
                elif i % 2 == 0:
                    roles.append("third")
                else:
                    roles.append("ghost_or_root")
        else:
            anchors = [float(i) for i in range(num)]
            roles = ["root" if i == 0 else ("fifth" if i % 2 == 0 else "third") for i in range(num)]

        # Lock to kick on beat 1; snare often → ghost or fifth answer
        for beat_pos, role in zip(anchors, roles):
            t = bar_start + beat_pos * beat_ms
            t += _swing_offset(beat_pos, beat_ms, groove_amount, num, den)
            t = _humanize(t, humanize_ms * groove_amount, rng)

            # Drum awareness
            near_kick = any(abs(t - k) < beat_ms * 0.35 for k in kick_ms)
            near_snare = any(abs(t - s) < beat_ms * 0.35 for s in snare_ms)

            pitch_map = {
                "root": root_pitch,
                "fifth": fifth,
                "third": third,
                "octave": octave,
                "ghost_or_root": root_pitch,
            }
            pitch = pitch_map.get(role, root_pitch)
            vel = base_vel + rng.randint(-8, 8)
            art: Optional[str] = None
            is_passing = False

            if role == "ghost_or_root" and rng.random() < ghost_prob:
                pitch = root_pitch
                vel = rng.randint(18, 36)
                art = "ghost"
            elif near_snare and beat_pos != 0 and rng.random() < ghost_prob:
                vel = rng.randint(20, 38)
                art = "ghost"
            elif near_kick and beat_pos == 0:
                vel = min(127, base_vel + 12)
                pitch = root_pitch

            # Duration: mostly 1 beat, shorten for ghosts
            dur = beat_ms * (0.55 if art == "ghost" else 0.85)
            if style == "Slap" and art != "ghost":
                dur *= 0.7
            if style == "Fretless":
                dur *= 1.05
                if rng.random() < 0.25:
                    art = "legato"

            # Chromatic passing into next strong beat
            if (
                beat_pos > 0
                and art is None
                and rng.random() < passing_prob
                and prev_pitch is not None
            ):
                approach = _chromatic_approach(pitch, prev_pitch)
                if approach is not None:
                    ap_start = t - beat_ms * 0.25
                    ap_start = _humanize(ap_start, humanize_ms * 0.5, rng)
                    notes.append(
                        GeneratedNote(
                            start_ms=max(bar_start, ap_start),
                            end_ms=t - 5.0,
                            pitch=approach,
                            velocity=max(40, vel - 20),
                            articulation="legato",
                            is_passing=True,
                        )
                    )
                    is_passing = False
                    art = "legato"

            # Occasional slide into downbeat
            if beat_pos == 0 and bar_i > 0 and rng.random() < 0.12 * groove_amount:
                art = "slide"

            end = t + dur
            notes.append(
                GeneratedNote(
                    start_ms=max(0.0, t),
                    end_ms=end,
                    pitch=int(np.clip(pitch, PITCH_MIN, PITCH_MAX)),
                    velocity=int(np.clip(vel, 1, 127)),
                    articulation=art,
                    is_passing=is_passing,
                )
            )
            prev_pitch = pitch

        # Extra ghost between beats for slap/groove
        if style in ("Slap", "Fingerstyle", "Mute") and groove_amount > 0.3:
            for extra_beat in (0.5, 1.5, 2.5, 3.5):
                if extra_beat >= num:
                    continue
                if rng.random() > ghost_prob * 0.7:
                    continue
                t = bar_start + extra_beat * beat_ms
                t = _humanize(t, humanize_ms, rng)
                notes.append(
                    GeneratedNote(
                        start_ms=t,
                        end_ms=t + beat_ms * 0.2,
                        pitch=root_pitch,
                        velocity=rng.randint(16, 32),
                        articulation="ghost",
                    )
                )

    notes.sort(key=lambda n: n.start_ms)
    return _resolve_overlaps(notes)


def _resolve_overlaps(notes: List[GeneratedNote]) -> List[GeneratedNote]:
    if not notes:
        return notes
    out: List[GeneratedNote] = []
    for n in notes:
        if out and n.start_ms < out[-1].end_ms:
            out[-1] = GeneratedNote(
                start_ms=out[-1].start_ms,
                end_ms=max(out[-1].start_ms + 20.0, n.start_ms - 2.0),
                pitch=out[-1].pitch,
                velocity=out[-1].velocity,
                articulation=out[-1].articulation,
                is_passing=out[-1].is_passing,
            )
        out.append(n)
    return out


@torch.no_grad()
def generate_bass_line_model(
    model: BassGrooveModel,
    chords: Sequence[str],
    bpm: float,
    time_signature: str,
    play_style: str,
    kick_ms: Optional[Sequence[float]] = None,
    snare_ms: Optional[Sequence[float]] = None,
    humanize_ms: float = 12.0,
    groove_amount: float = 0.55,
    device: str = "cpu",
    temperature: float = 0.9,
) -> List[GeneratedNote]:
    """Neural decode; blends with rules for timing if model output is weak."""
    model.eval()
    model.to(device)
    num, den = parse_time_signature(time_signature)
    beat_ms = beat_duration_ms(bpm, den)
    bar_ms = beat_ms * num
    total_ms = bar_ms * len(chords)
    n_steps = max(1, int(math.ceil(total_ms / (beat_ms / 2))))  # 8th-note grid

    kick_g, snare_g = _kick_snare_grids(kick_ms or [], snare_ms or [], total_ms, beat_ms / 2)

    tokens = torch.full((1, n_steps), REST_ID, dtype=torch.long, device=device)
    style_id = torch.tensor([STYLE_TO_ID.get(play_style, 0)], device=device)
    drum = torch.zeros(1, n_steps, 2, device=device)
    chord_f = torch.zeros(1, n_steps, 12, device=device)
    meter = torch.zeros(1, n_steps, 4, device=device)

    for i in range(n_steps):
        t_ms = i * (beat_ms / 2)
        bar_i = min(len(chords) - 1, int(t_ms // bar_ms))
        root, tones = parse_chord(chords[bar_i])
        for tt in tones:
            chord_f[0, i, (root + tt) % 12] = 1.0
        gi = min(i, len(kick_g) - 1)
        drum[0, i, 0] = float(kick_g[gi]) if len(kick_g) else 0.0
        drum[0, i, 1] = float(snare_g[gi]) if len(snare_g) else 0.0
        beat_pos = (t_ms % bar_ms) / bar_ms
        meter[0, i] = torch.tensor(
            [num / 16.0, den / 16.0, min(bpm, 240) / 240.0, beat_pos],
            device=device,
        )

    # Autoregressive fill
    generated = [REST_ID]
    for i in range(1, n_steps):
        tok = torch.tensor([generated + [PAD_ID] * (n_steps - len(generated))], device=device)
        tok = tok[:, :n_steps]
        logits, _vel = model(tok, style_id, drum, chord_f, meter)
        step_logits = logits[0, i - 1] / max(temperature, 1e-3)
        probs = torch.softmax(step_logits, dim=-1)
        nxt = int(torch.multinomial(probs, 1).item())
        generated.append(nxt)

    # If mostly REST / pad (untrained), fall back
    note_tokens = [t for t in generated if t >= NOTE_OFFSET]
    if len(note_tokens) < max(2, n_steps // 8):
        logger.info("Model output sparse — using hybrid rule engine.")
        return generate_bass_line_rules(
            chords,
            bpm,
            time_signature,
            play_style,
            kick_ms=kick_ms,
            snare_ms=snare_ms,
            humanize_ms=humanize_ms,
            groove_amount=groove_amount,
        )

    notes: List[GeneratedNote] = []
    step_ms = beat_ms / 2
    for i, tok in enumerate(generated):
        if tok < NOTE_OFFSET:
            continue
        pitch = tok - NOTE_OFFSET + PITCH_MIN
        t = i * step_ms + random.uniform(-humanize_ms, humanize_ms) * groove_amount
        notes.append(
            GeneratedNote(
                start_ms=max(0.0, t),
                end_ms=t + step_ms * 0.85,
                pitch=int(np.clip(pitch, PITCH_MIN, PITCH_MAX)),
                velocity=int(np.clip(70 + groove_amount * 30, 1, 127)),
            )
        )
    return _resolve_overlaps(notes)


def generate_bass_line(
    chords: str | Sequence[str],
    bpm: float = 100.0,
    time_signature: str = "4/4",
    play_style: str = "Fingerstyle",
    kick_ms: Optional[Sequence[float]] = None,
    snare_ms: Optional[Sequence[float]] = None,
    humanize_ms: float = 12.0,
    groove_amount: float = 0.55,
    checkpoint: Optional[str | Path] = None,
    seed: Optional[int] = None,
    force_rules: bool = False,
) -> List[GeneratedNote]:
    """Public hybrid entry: rules always available; neural if checkpoint loads."""
    if isinstance(chords, str):
        chord_list = parse_progression(chords)
    else:
        chord_list = list(chords)
    if not chord_list:
        chord_list = ["Am7", "D9", "Gmaj7", "Cmaj7"]

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

    if force_rules or checkpoint is None:
        return generate_bass_line_rules(
            chord_list,
            bpm,
            time_signature,
            play_style,
            kick_ms=kick_ms,
            snare_ms=snare_ms,
            humanize_ms=humanize_ms,
            groove_amount=groove_amount,
            seed=seed,
        )

    model = BassGrooveModel()
    try:
        model.load(checkpoint)
        return generate_bass_line_model(
            model,
            chord_list,
            bpm,
            time_signature,
            play_style,
            kick_ms=kick_ms,
            snare_ms=snare_ms,
            humanize_ms=humanize_ms,
            groove_amount=groove_amount,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Checkpoint load/inference failed (%s); using rules.", exc)
        return generate_bass_line_rules(
            chord_list,
            bpm,
            time_signature,
            play_style,
            kick_ms=kick_ms,
            snare_ms=snare_ms,
            humanize_ms=humanize_ms,
            groove_amount=groove_amount,
            seed=seed,
        )
