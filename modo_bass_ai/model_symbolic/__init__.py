"""Symbolic bass groove model (Transformer + hybrid rule fallback)."""

from .bass_groove_model import (
    BassGrooveModel,
    GrooveConfig,
    generate_bass_line,
    load_checkpoint,
    load_model_from_checkpoint,
)

__all__ = [
    "BassGrooveModel",
    "GrooveConfig",
    "generate_bass_line",
    "load_checkpoint",
    "load_model_from_checkpoint",
]
