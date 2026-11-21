"""Audio stem separation, onset alignment, and dataset building."""

from .pipeline import AudioPrepPipeline, DrumOnsets, BassNoteEvent

__all__ = ["AudioPrepPipeline", "DrumOnsets", "BassNoteEvent", "build_dataset"]


def __getattr__(name: str):
    if name == "build_dataset":
        from .build_dataset import build_dataset

        return build_dataset
    raise AttributeError(name)
