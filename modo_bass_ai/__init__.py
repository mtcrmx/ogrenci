"""MODO BASS AI — chord/drum-aware bass MIDI performance generator for MODO BASS 2."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config" / "modo_bass_map.json"

__version__ = "0.1.0"

__all__ = ["PROJECT_ROOT", "CONFIG_PATH", "__version__"]
