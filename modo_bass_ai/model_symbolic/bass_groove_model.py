"""PyTorch Transformer bass groove model + hybrid music-theory inference.

When no checkpoint is loaded (or weights are random), `generate_bass_line`
falls back to deterministic groove / theory rules so the app works untrained.
"""

from __future__ import annotations

import logging
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from model_symbolic.performance_phrasing import PERFORMANCE_LEVELS, phrase_performance
except ImportError:  # optional until performance package is present
    PERFORMANCE_LEVELS = ("Sade",)
    phrase_performance = None  # type: ignore[assignment]

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

# MODO BASS keyswitch / articulation classes (aligned with config/modo_bass_map.json)
KS_CLASSES: Tuple[str, ...] = (
    "none",
    "fingerstyle",
    "pick",
    "slap",
    "legato",
    "ghost_note",
    "harmonics",
    "thumb",
    "pop",
    "hammer_on",
    "pull_off",
)
KS_TO_ID = {name: i for i, name in enumerate(KS_CLASSES)}
N_KS = len(KS_CLASSES)
KS_IGNORE_ID = -100

# Style id → default MODO play-style keyswitch
STYLE_DEFAULT_KS = {
    0: KS_TO_ID["fingerstyle"],
    1: KS_TO_ID["slap"],
    2: KS_TO_ID["legato"],  # fretless → legato
    3: KS_TO_ID["pick"],
    4: KS_TO_ID["fingerstyle"],  # mute uses fingerstyle + CC
}

# Chord quality → relative scale degrees (semitones from root)
CHORD_TONES: Dict[str, List[int]] = {
    "": [0, 4, 7],
    "5": [0, 7],
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


@dataclass
class BassGrooveOutput:
    """Multi-head forward result. Unpacks as ``(logits, velocity)`` for legacy callers."""

    logits: torch.Tensor
    velocity: torch.Tensor
    micro_ms: torch.Tensor
    duration_ms: torch.Tensor
    ks_logits: torch.Tensor

    def __iter__(self):
        yield self.logits
        yield self.velocity

    def __getitem__(self, index):
        return (self.logits, self.velocity)[index]


def derive_step_ms(meter_feats: torch.Tensor) -> torch.Tensor:
    """Eighth-note grid step length (ms) from meter features (num/16, den/16, bpm/240, phase)."""
    den = (meter_feats[..., 1] * 16.0).clamp(min=1.0)
    bpm = (meter_feats[..., 2] * 240.0).clamp(min=1.0)
    beat_ms = 60_000.0 / bpm * (4.0 / den)
    return beat_ms * 0.5


def derive_duration_ms(tokens: torch.Tensor, meter_feats: torch.Tensor) -> torch.Tensor:
    """Per-step sounding duration (ms) from onset→next-onset span on the eighth grid."""
    step_ms = derive_step_ms(meter_feats)
    note = tokens >= NOTE_OFFSET
    bsz, steps = tokens.shape
    dur = torch.zeros(bsz, steps, device=tokens.device, dtype=torch.float32)
    for b in range(bsz):
        idxs = torch.nonzero(note[b], as_tuple=False).flatten()
        if idxs.numel() == 0:
            continue
        for j, i in enumerate(idxs.tolist()):
            nxt = int(idxs[j + 1]) if j + 1 < idxs.numel() else steps
            # Stop early at PAD so padding does not inflate the last note.
            end = nxt
            for t in range(i + 1, nxt):
                if tokens[b, t] == PAD_ID:
                    end = t
                    break
            n_steps = max(1, end - i)
            dur[b, i] = float(n_steps) * float(step_ms[b, i]) * 0.85
    return dur


def derive_keyswitch_targets(
    tokens: torch.Tensor,
    vels: torch.Tensor,
    style_id: torch.Tensor,
    ghost_vel_max: float = 40.0,
) -> torch.Tensor:
    """Heuristic MODO keyswitch labels from style + velocity (no artic labels in train_data)."""
    bsz, steps = tokens.shape
    style = style_id.view(-1, 1).expand(bsz, steps)
    ks = torch.full((bsz, steps), KS_IGNORE_ID, device=tokens.device, dtype=torch.long)
    note = tokens >= NOTE_OFFSET
    if not note.any():
        return ks
    # Default play-style keyswitch for sounding notes
    default = torch.zeros_like(ks)
    for sid, kid in STYLE_DEFAULT_KS.items():
        default = torch.where(style == sid, torch.full_like(default, kid), default)
    ks = torch.where(note, default, ks)
    # Ghost notes override style KS
    ghost = note & (vels <= ghost_vel_max)
    ks = torch.where(ghost, torch.full_like(ks, KS_TO_ID["ghost_note"]), ks)
    return ks


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
    """Autoregressive Transformer with pitch, keyswitch, timing, duration, velocity heads."""

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
        # Older checkpoints used two steps per denominator beat in manual mode.
        self.steps_per_quarter: Optional[int] = None
        self.duration_model = None
        self.duration_model_state = None
        self.technique_model = None
        self.technique_model_state = None
        self.onset_rates = {}
        self.pitch_emb = nn.Embedding(VOCAB_SIZE, d_model)
        self.style_emb = nn.Embedding(N_STYLES, d_model)
        self.drum_proj = nn.Linear(2, d_model)  # kick/snare density per step
        self.chord_proj = nn.Linear(12, d_model)  # pitch-class chroma
        self.next_chord_proj = None
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
        self.timing_head = nn.Linear(d_model, 1)  # micro-timing offset (ms)
        self.dur_head = nn.Linear(d_model, 1)  # note duration (ms)
        self.ks_head = nn.Linear(d_model, N_KS)  # MODO keyswitch class

    def enable_harmonic_lookahead(self):
        """Start from exactly the existing sound while learning to anticipate changes."""
        self.next_chord_proj = nn.Linear(12, self.d_model, bias=False).to(self.chord_proj.weight)
        nn.init.zeros_(self.next_chord_proj.weight)

    def forward(
        self,
        tokens: torch.Tensor,
        style_id: torch.Tensor,
        drum_feats: torch.Tensor,
        chord_feats: torch.Tensor,
        meter_feats: torch.Tensor,
        src_key_padding_mask: Optional[torch.Tensor] = None,
        next_chord_feats: Optional[torch.Tensor] = None,
    ) -> BassGrooveOutput:
        """
        tokens: (B, T) long
        style_id: (B,) long
        drum_feats: (B, T, 2)
        chord_feats: (B, T, 12)
        meter_feats: (B, T, 4)
        returns BassGrooveOutput (unpacks as logits, velocity)
        """
        x = self.pitch_emb(tokens) * math.sqrt(self.d_model)
        x = x + self.style_emb(style_id).unsqueeze(1)
        x = x + self.drum_proj(drum_feats)
        x = x + self.chord_proj(chord_feats)
        if self.next_chord_proj is not None and next_chord_feats is not None:
            x = x + self.next_chord_proj(next_chord_feats - chord_feats)
        x = x + self.meter_proj(meter_feats)
        x = self.pos(x)
        # Causal mask
        t = tokens.size(1)
        causal = torch.triu(torch.ones(t, t, device=tokens.device, dtype=torch.bool), diagonal=1)
        h = self.encoder(x, mask=causal, src_key_padding_mask=src_key_padding_mask)
        logits = self.head(h)
        vel = torch.sigmoid(self.vel_head(h)).squeeze(-1) * 127.0
        micro = self.timing_head(h).squeeze(-1)
        duration = F.softplus(self.dur_head(h).squeeze(-1)) + 1.0
        ks_logits = self.ks_head(h)
        return BassGrooveOutput(
            logits=logits,
            velocity=vel,
            micro_ms=micro,
            duration_ms=duration,
            ks_logits=ks_logits,
        )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state_dict": self.state_dict(),
            "vocab": VOCAB_SIZE,
            "d_model": self.d_model,
            "n_ks": N_KS,
            "multi_task_heads": True,
        }
        if self.steps_per_quarter is not None:
            payload["steps_per_quarter"] = self.steps_per_quarter
        if self.duration_model_state is not None:
            payload["duration_model"] = self.duration_model_state
        if self.technique_model_state is not None:
            payload["technique_model"] = self.technique_model_state
        if self.onset_rates:
            payload["onset_rates"] = self.onset_rates
        torch.save(payload, path)

    def load(self, path: str | Path, map_location: str = "cpu") -> None:
        load_checkpoint(self, path, map_location=map_location)


def load_checkpoint(
    model: BassGrooveModel,
    path: str | Path,
    map_location: str = "cpu",
) -> BassGrooveModel:
    """Load a training/fine-tune checkpoint into `model` (in-place) and return it."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        ckpt = torch.load(path, map_location=map_location, weights_only=False)
    except TypeError:
        ckpt = torch.load(path, map_location=map_location)
    state = ckpt["state_dict"] if isinstance(ckpt, dict) and "state_dict" in ckpt else ckpt
    if "next_chord_proj.weight" in state:
        if model.next_chord_proj is None:
            model.enable_harmonic_lookahead()
    else:
        model.next_chord_proj = None
    # Older checkpoints lack timing/duration/keyswitch heads — keep freshly init'd weights.
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        logger.info("Checkpoint missing keys (kept init): %s", sorted(missing)[:12])
    if unexpected:
        logger.info("Checkpoint unexpected keys ignored: %s", sorted(unexpected)[:12])
    resolution = ckpt.get("steps_per_quarter")
    if resolution is not None and resolution not in (2, 4):
        raise ValueError(f"Unsupported checkpoint rhythm resolution: {resolution}")
    model.steps_per_quarter = resolution
    model.onset_rates = ckpt.get("onset_rates", {})
    model.duration_model_state = ckpt.get("duration_model")
    model.duration_model = None
    if resolution == 4 and model.duration_model_state is not None:
        from model_symbolic.note_lengths import load_duration_model

        model.duration_model = load_duration_model(model.duration_model_state)
    model.technique_model_state = ckpt.get("technique_model")
    model.technique_model = None
    if resolution == 4 and model.technique_model_state is not None:
        from model_symbolic.technique_choice import load_technique_model

        model.technique_model = load_technique_model(model.technique_model_state)
    model.eval()
    return model


def load_model_from_checkpoint(
    path: str | Path,
    map_location: str = "cpu",
) -> BassGrooveModel:
    """Construct a BassGrooveModel and load weights from disk."""
    model = BassGrooveModel()
    return load_checkpoint(model, path, map_location=map_location)


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
    pcs = {(root + tone) % 12 for tone in tones}
    candidates = (p for p in range(PITCH_MIN, PITCH_MAX + 1) if p % 12 in pcs)
    return min(candidates, key=lambda p: abs(p - pitch))


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
    performance_level: str = "Sade",
) -> List[GeneratedNote]:
    """Music-theory + drum-lock groove writer (works without training)."""
    if performance_level != "Sade":
        return generate_bass_line_model(
            None, chords, bpm, time_signature, play_style, kick_ms=kick_ms,
            snare_ms=snare_ms, humanize_ms=humanize_ms, groove_amount=groove_amount,
            seed=seed, performance_level=performance_level,
        )
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
        inversion = chord_sym.partition("/")[2].strip()
        bass_pc = NOTE_NAME_TO_PC.get(inversion, root)
        root_pitch = _nearest_chord_tone(min(prefer, 47), bass_pc, [0])
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
            if beat_pos:
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


def _chord_and_bass(symbol):
    """Return the harmonic pitch classes separately from the inversion bass."""
    symbol = str(symbol or "").strip().replace("♭", "b").replace("♯", "#").replace(":", "")
    if not re.match(r"^[A-Ga-g]", symbol):
        return None
    name, _, inversion = symbol.partition("/")
    root, tones = parse_chord(name)
    bass = NOTE_NAME_TO_PC.get(inversion.strip(), root)
    return bass, {(root + tone) % 12 for tone in tones}


def _onset_features(step_times, step_lengths, onsets):
    if onsets is None or len(onsets) == 0:
        return np.zeros(len(step_times), dtype=np.float32)
    onsets = np.sort(np.asarray(onsets, dtype=float))
    # Training marks every step strictly less than one grid interval from an onset.
    left = np.searchsorted(onsets, step_times - step_lengths, side="right")
    right = np.searchsorted(onsets, step_times + step_lengths, side="left")
    return (right > left).astype(np.float32)


def _bar_phase(beat_times, downbeat_indices, downbeat_times_ms, pulses_per_bar, subdivisions):
    """Find each decoder step's bar position and any measured downbeat attack."""
    beat_count = len(beat_times) - 1
    slots = np.arange(beat_count * subdivisions) / subdivisions
    bar_positions = np.asarray(downbeat_indices, dtype=float)
    exact_attacks = {}
    if downbeat_times_ms is not None and len(downbeat_times_ms):
        measured = np.asarray(downbeat_times_ms, dtype=float)
        if not np.all(np.isfinite(measured)) or np.any(np.diff(measured) <= 0):
            raise ValueError("Downbeat times must be finite and strictly increasing.")
        measured = measured[(measured >= beat_times[0]) & (measured < beat_times[-1])]
        if len(measured):
            bar_positions = np.interp(measured, beat_times, np.arange(beat_count + 1))
            # A 7/8 bar can start between two recorded quarter pulses.
            for position, timestamp in zip(bar_positions, measured):
                slot = min(len(slots) - 1, int(math.floor(position * subdivisions + 0.5)))
                exact_attacks[slot] = float(timestamp)

    origin = bar_positions[0] if len(bar_positions) else 0.0
    phase = ((slots - origin) % pulses_per_bar) / pulses_per_bar
    for index, start in enumerate(bar_positions):
        stop = bar_positions[index + 1] if index + 1 < len(bar_positions) else beat_count
        span = stop - start if index + 1 < len(bar_positions) else pulses_per_bar
        within = (slots >= start) & (slots < stop)
        phase[within] = ((slots[within] - start) % span) / span
    for slot in exact_attacks:
        phase[slot] = 0.0
    return phase, exact_attacks


def _pitch_options(pitches, bass_class, chord_classes, accent, next_bass_class, previous_pitch):
    """Allow chord members and a stepwise chromatic approach before a change."""
    pitch_classes = pitches % 12
    allowed = np.isin(pitch_classes, list(chord_classes | {bass_class}))
    approaches = np.zeros_like(allowed)
    if accent:
        allowed = pitch_classes == bass_class
    elif next_bass_class is not None:
        neighbors = ((next_bass_class - 1) % 12, (next_bass_class + 1) % 12)
        approaches = np.isin(pitch_classes, neighbors) & (abs(pitches - previous_pitch) <= 3)
        allowed |= approaches
    return allowed, approaches


def next_quarter_harmony(chords, padding=None):
    """Known backing harmony one quarter ahead. Trailing/padded slots keep their chord."""
    future = chords.clone()
    if chords.shape[1] > 4:
        upcoming = chords[:, 4:]
        if padding is not None:
            upcoming = torch.where(padding[:, 4:, None], chords[:, :-4], upcoming)
        future[:, :-4] = upcoming
    return future


@torch.inference_mode()
def _generate_on_grid(
    model,
    beat_times,
    beat_chords,
    *,
    downbeats,
    strong_beats,
    duration_ms,
    config,
    kick_ms,
    snare_ms,
    bass_hints,
    device,
    temperature,
    quarter_pulse,
    downbeat_times_ms=None,
    performance_level="Sade",
    beat_energy=None,
):
    if performance_level not in PERFORMANCE_LEVELS:
        raise ValueError(f"Unknown performance level: {performance_level}")
    beat_times = np.asarray(beat_times, dtype=float)
    count = len(beat_chords)
    bpm = config.bpm
    play_style = config.play_style
    num, den = parse_time_signature(config.time_signature)
    if num <= 0 or den <= 0 or not math.isfinite(bpm) or bpm <= 0:
        raise ValueError("BPM and time signature must be positive.")
    if not math.isfinite(duration_ms) or duration_ms <= 0:
        raise ValueError("Audio duration must be finite and positive.")
    if beat_times.shape != (count + 1,) or not np.all(np.isfinite(beat_times)):
        raise ValueError("Provide one start per chord plus a final beat boundary, in milliseconds.")
    if beat_times[0] < 0 or np.any(np.diff(beat_times) <= 0):
        raise ValueError("Beat times must be nonnegative and strictly increasing.")
    if bass_hints is not None and len(bass_hints) != count:
        raise ValueError("Provide one optional MIDI bass pitch per beat.")
    if count == 0:
        return []

    rng = random.Random(config.seed)
    groove = max(0.0, min(1.0, config.groove_amount))
    harmonies = [_chord_and_bass(symbol) for symbol in beat_chords]
    downbeats = sorted(set(int(index) for index in downbeats if 0 <= index < count))
    strong_beats = set(strong_beats) if strong_beats is not None else set()
    anchors = set(downbeats)
    anchors.update(i for i in range(count) if i == 0 or beat_chords[i] != beat_chords[i - 1])
    beat_lengths = np.diff(beat_times)
    native_resolution = getattr(model, "steps_per_quarter", None)
    quarters_per_pulse = 1 if quarter_pulse else 4 / den
    subdivisions = max(1, round(native_resolution * quarters_per_pulse)) if native_resolution else 2
    step_lengths = np.repeat(beat_lengths / subdivisions, subdivisions)
    step_times = np.repeat(beat_times[:-1], subdivisions)
    step_times += np.tile(np.arange(subdivisions), count) * step_lengths
    n_steps = len(step_times)
    nominal_bar = num * 4 / den if quarter_pulse else float(num)
    phase, barline_attacks = _bar_phase(
        beat_times, downbeats, downbeat_times_ms, nominal_bar, subdivisions
    )
    style_onset_odds = None
    if native_resolution == 4:
        rates = getattr(model, "onset_rates", {})
        profile = rates.get(play_style, rates.get("default"))
        if profile is not None:
            rates = np.clip(np.asarray(profile, dtype=float), .02, .98)
            if rates.shape != (4,) or not np.all(np.isfinite(rates)):
                raise ValueError("Checkpoint onset rates must contain four finite probabilities.")
            style_onset_odds = np.log(rates / (1 - rates))

    kick = _onset_features(step_times, step_lengths, kick_ms)
    snare = _onset_features(step_times, step_lengths, snare_ms)
    chroma = np.zeros((n_steps, 12), dtype=np.float32)
    for beat, harmony in enumerate(harmonies):
        if harmony is not None:
            chroma[subdivisions * beat : subdivisions * (beat + 1), list(harmony[1])] = 1
    if model is not None:
        model.to(device).eval()
        generator = (
            torch.Generator(device=device).manual_seed(config.seed)
            if config.seed is not None
            else None
        )
        style = torch.tensor([STYLE_TO_ID.get(play_style, 0)], device=device)
        drum = torch.tensor(np.column_stack((kick, snare)), device=device).unsqueeze(0)
        chord = torch.tensor(chroma, device=device).unsqueeze(0)
        lookahead = model.next_chord_proj is not None
        future_chords = next_quarter_harmony(chord) if lookahead else None
        meter = np.column_stack(
            (
                np.full(n_steps, num / 16),
                np.full(n_steps, den / 16),
                np.full(n_steps, min(bpm, 240) / 240),
                phase,
            )
        )
        meter = torch.as_tensor(meter, dtype=torch.float32, device=device).unsqueeze(0)
        # Retain the previous phrase as context on long uploads. Local positions
        # stay inside both the training range and the checkpoint's position buffer.
        capacity = model.pos.pe.shape[1]
        phrase = max(1, min(round(2 * subdivisions * nominal_bar), capacity // 2))

    tokens = []
    notes = []
    previous_pitch = 38
    pitches = np.arange(PITCH_MIN, PITCH_MAX + 1)
    for step_index, grid_time in enumerate(step_times):
        if grid_time >= duration_ms:
            break
        beat_index, within_beat = divmod(step_index, subdivisions)
        harmony = harmonies[beat_index]
        if harmony is None:
            tokens.append(REST_ID)
            continue
        bass_class, chord_classes = harmony
        hint = bass_hints[beat_index] if bass_hints is not None else None
        has_hint = hint is not None and np.isfinite(hint) and 0 <= hint <= 127
        anchor = step_index in barline_attacks or (within_beat == 0 and beat_index in anchors)
        strong = anchor or (within_beat == 0 and beat_index in strong_beats)
        if has_hint and anchor and "/" not in beat_chords[beat_index]:
            bass_class = int(round(hint)) % 12
        next_beat = beat_index + 1
        approaching_change = (
            within_beat == subdivisions - 1 and next_beat in anchors and harmonies[next_beat] is not None
        )
        next_bass = harmonies[next_beat][0] if approaching_change else None
        allowed, approach = _pitch_options(
            pitches, bass_class, chord_classes, anchor, next_bass, previous_pitch
        )
        if model is not None and lookahead and not anchor:
            # A walking line can approach the next root on the last quarter,
            # or use the second/fourth of the current chord in a stepwise line.
            if next_beat < count and next_beat in anchors and harmonies[next_beat]:
                target_pc = harmonies[next_beat][0]
                approach |= np.isin(pitches % 12, [(target_pc-1) % 12, (target_pc+1) % 12]) & (abs(pitches-previous_pitch) <= 3)
            if "/" not in beat_chords[beat_index] and (within_beat or phase[step_index] > 0):
                passing_classes = [(bass_class + 2) % 12, (bass_class + 5) % 12]
                approach |= np.isin(pitches % 12, passing_classes) & (abs(pitches-previous_pitch) <= 2)
            allowed |= approach
        if model is not None:
            context_start = max(0, (step_index // phrase - 1) * phrase, step_index + 1 - capacity)
            inputs = [REST_ID if context_start == 0 else tokens[context_start - 1]] + tokens[
                context_start:step_index
            ]
            prefix = torch.tensor([inputs], device=device)
            context = slice(context_start, step_index + 1)
            logits, velocity = model(
                prefix, style, drum[:, context], chord[:, context], meter[:, context],
                next_chord_feats=future_chords[:, context] if lookahead else None,
            )
            scores = logits[0, -1].clone() / max(temperature, 0.01)
            scores[PAD_ID] = -torch.inf
            if strong:
                scores[REST_ID] = -torch.inf
            elif within_beat:
                # The groove control varies offbeat density around the trained default.
                scores[REST_ID] += (0.55 - groove) * 1.5
            # Prefer connected low-register lines while retaining learned interval
            # and octave choices. Downbeats and chord changes sound their bass note.
            center = (
                float(np.clip(hint, PITCH_MIN, PITCH_MAX))
                if has_hint and anchor
                else previous_pitch
            )
            penalty = 0.22 * np.maximum(abs(pitches - center) - 5, 0) + 0.26 * np.maximum(
                pitches - 52, 0
            )
            bias = np.where(allowed, -penalty, -np.inf)
            scores[NOTE_OFFSET:] += torch.as_tensor(bias, dtype=scores.dtype, device=device)
            if native_resolution == 4:
                # The sixteenth-note model was trained to decide attack/rest
                # separately from pitch. Selecting a chord tone must preserve
                # its probability of playing on this beat.
                pitch_logits = scores[NOTE_OFFSET:]
                raw = logits[0, -1]
                note_mass = raw[NOTE_OFFSET:].logsumexp(0)
                pitch_logits += note_mass - pitch_logits.logsumexp(0)
                if not strong:
                    rest = raw[REST_ID]
                    if style_onset_odds is not None:
                        # Shrink sequence-specific attack odds gently toward
                        # that technique's observed onsets on 1, e, &, and a.
                        subdivision = round(phase[step_index] * nominal_bar * quarters_per_pulse * 4) % 4
                        weight = .35
                        rest = (1 - weight) * rest + weight * (note_mass - style_onset_odds[subdivision])
                    scores[REST_ID] = rest + ((.55 - groove) * 1.5 if within_beat else 0)
            token = int(torch.multinomial(scores.softmax(-1), 1, generator=generator).item())
            note_velocity = int(np.clip(round(velocity[0, -1].item()), 1, 127))
        else:
            if (
                within_beat
                and not strong
                and rng.random() > min(0.85, 0.12 + groove * 0.30 + kick[step_index] * 0.24)
            ):
                tokens.append(REST_ID)
                continue
            if anchor:
                target = int(hint) if has_hint else int(np.clip(previous_pitch, 32, 46))
            else:
                target = previous_pitch + rng.choice((-5, -3, 2, 4, 7))
            candidates = pitches[allowed]
            pitch = int(candidates[np.argmin(abs(candidates - np.clip(target, 29, 53)))])
            token = pitch - PITCH_MIN + NOTE_OFFSET
            note_velocity = int(
                np.clip((92 if strong else 76) + 6 * kick[step_index] + rng.randint(-6, 6), 1, 127)
            )
        tokens.append(token)
        if token == REST_ID:
            continue
        previous_pitch = token - NOTE_OFFSET + PITCH_MIN
        slot_length = step_lengths[step_index]
        # Preserve analyzed attacks at downbeats/chord entries, and keep timing
        # jitter inside the beat whose harmony was used to select this pitch.
        jitter = min(max(0.0, config.humanize_ms) * groove, slot_length * 0.10)
        start_ms = float(
            barline_attacks.get(step_index, grid_time)
            if strong
            else np.clip(
                grid_time + rng.uniform(-jitter, jitter),
                beat_times[beat_index],
                grid_time + slot_length * 0.10,
            )
        )
        if start_ms >= duration_ms:
            continue
        next_boundary = min(duration_ms, beat_times[beat_index + 1])
        gate = 0.65 if play_style in ("Mute", "Slap") else 0.93
        # A strong note may sustain across the next eighth-slot when it is a rest.
        # A following attack will shorten it before playback.
        end_ms = min(next_boundary, start_ms + slot_length * gate * (1 if within_beat else subdivisions))
        if end_ms <= start_ms:
            continue
        if notes and notes[-1].end_ms > start_ms:
            notes[-1].end_ms = start_ms
        passing = bool(approach[token - NOTE_OFFSET]) and previous_pitch % 12 not in chord_classes
        notes.append(
            GeneratedNote(
                start_ms, float(end_ms), previous_pitch, note_velocity, is_passing=passing
            )
        )
    if performance_level != "Sade":
        if phrase_performance is None:
            raise ImportError(
                "performance_phrasing is required for non-Sade performance levels"
            )
        notes = phrase_performance(
            notes, beat_times, harmonies, duration_ms=duration_ms, downbeat_indices=downbeats,
            downbeat_times_ms=downbeat_times_ms, quarters_per_pulse=quarters_per_pulse,
            pulses_per_bar=nominal_bar, style=play_style, level=performance_level,
            groove=groove, humanize_ms=config.humanize_ms, kick_ms=kick_ms, seed=config.seed,
            beat_energy=beat_energy,
        )
    duration_model = getattr(model, "duration_model", None)
    bar_times = downbeat_times_ms if downbeat_times_ms is not None else beat_times[downbeats]
    if native_resolution == 4 and duration_model is not None:
        from model_symbolic.note_lengths import apply_note_lengths

        notes = apply_note_lengths(
            notes, duration_model, beat_times, beat_chords, duration_ms, bpm,
            config.time_signature, play_style, downbeat_times_ms=bar_times,
            quarters_per_pulse=quarters_per_pulse,
        )
    technique_model = getattr(model, "technique_model", None)
    if native_resolution == 4 and technique_model is not None:
        from model_symbolic.technique_choice import apply_techniques

        notes = apply_techniques(
            notes, technique_model, beat_times, duration_ms, bpm, config.time_signature,
            play_style, performance_level, downbeat_times_ms=bar_times,
            quarters_per_pulse=quarters_per_pulse,
        )
    return notes


def generate_song_bass_line(
    *,
    beat_times_ms: Sequence[float],
    beat_chords: Sequence[str],
    downbeat_indices: Sequence[int],
    duration_ms: float,
    bpm: float,
    time_signature: str = "4/4",
    play_style: str = "Fingerstyle",
    strong_beat_indices: Optional[Sequence[int]] = None,
    kick_ms: Optional[Sequence[float]] = None,
    snare_ms: Optional[Sequence[float]] = None,
    humanize_ms: float = 12.0,
    groove_amount: float = 0.55,
    checkpoint: Optional[str | Path] = None,
    seed: Optional[int] = None,
    force_rules: bool = False,
    bass_hints: Optional[Sequence[Optional[int]]] = None,
    downbeat_times_ms: Optional[Sequence[float]] = None,
    performance_level: str = "Sade",
    beat_energy: Optional[Sequence[float]] = None,
) -> List[GeneratedNote]:
    """Accompany a recording on its own quarter-pulse grid (N starts and one end).

    Chords, optional bass pitches, and optional relative energy each describe
    one pulse. Energy ranges from 0 (quiet) through 0.5 (neutral) to 1 (loud).
    Downbeat indices are zero-based. Times stay relative to the source recording, including its
    lead-in. Unknown chords produce silence until a usable harmony reappears.
    """
    model = None
    if checkpoint is not None and not force_rules:
        model = load_model_from_checkpoint(checkpoint)
    config = GrooveConfig(
        bpm=bpm,
        time_signature=time_signature,
        play_style=play_style,
        humanize_ms=humanize_ms,
        groove_amount=groove_amount,
        seed=seed,
    )
    return _generate_on_grid(
        model,
        beat_times_ms,
        beat_chords,
        downbeats=downbeat_indices,
        strong_beats=strong_beat_indices,
        duration_ms=duration_ms,
        config=config,
        kick_ms=kick_ms,
        snare_ms=snare_ms,
        bass_hints=bass_hints,
        device="cpu",
        temperature=0.9,
        quarter_pulse=True,
        downbeat_times_ms=downbeat_times_ms,
        performance_level=performance_level,
        beat_energy=beat_energy,
    )


def generate_bass_line_model(
    model: Optional[BassGrooveModel],
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
    seed: Optional[int] = None,
    performance_level: str = "Sade",
) -> List[GeneratedNote]:
    """Decode a manual chart with one chord per bar on the denominator beat."""
    if not chords:
        return []
    num, den = parse_time_signature(time_signature)
    per_beat = [chord for chord in chords for _ in range(num)]
    boundaries = np.arange(len(per_beat) + 1) * beat_duration_ms(bpm, den)
    config = GrooveConfig(
        bpm=bpm,
        time_signature=time_signature,
        play_style=play_style,
        humanize_ms=humanize_ms,
        groove_amount=groove_amount,
        seed=seed,
    )
    return _generate_on_grid(
        model,
        boundaries,
        per_beat,
        downbeats=range(0, len(per_beat), num),
        strong_beats=None,
        duration_ms=boundaries[-1],
        config=config,
        kick_ms=kick_ms,
        snare_ms=snare_ms,
        bass_hints=None,
        device=device,
        temperature=temperature,
        quarter_pulse=False,
        performance_level=performance_level,
    )


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
    performance_level: str = "Sade",
) -> List[GeneratedNote]:
    """Public hybrid entry: rules always available; neural if checkpoint loads."""
    if performance_level not in PERFORMANCE_LEVELS:
        raise ValueError(f"Unknown performance level: {performance_level}")
    if isinstance(chords, str):
        chord_list = parse_progression(chords)
    else:
        chord_list = list(chords)
    if not chord_list:
        chord_list = ["Am7", "D9", "Gmaj7", "Cmaj7"]

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
            performance_level=performance_level,
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
            seed=seed,
            performance_level=performance_level,
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
            performance_level=performance_level,
        )
