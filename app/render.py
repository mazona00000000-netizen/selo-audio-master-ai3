"""تجميع التعليق الصوتي: كل مقطع بصوته وإحساسه، مع الوقفات وعلو الصوت."""

from __future__ import annotations

from typing import Callable

import numpy as np

from .audio import apply_gain, fade_edges, normalize_peak, resample_linear, silence
from .engines.base import Engine
from .script import Paragraph

PARAGRAPH_GAP = 0.5  # ثواني بين الفقرات
MIN_PAUSE_ONLY = 0.8  # لو كتب [وقفة] لوحدها


class Cancelled(Exception):
    pass


def pick_voice(engine: Engine, voices: dict, default_voice: str, paragraph: int) -> str:
    chosen = voices.get(str(paragraph)) or voices.get(paragraph) or default_voice
    if chosen:
        return chosen
    available = engine.voices()
    if not available:
        raise RuntimeError("مفيش أصوات متاحة للمحرك ده.")
    return available[0]


def render_script(
    engine: Engine,
    paragraphs: list[Paragraph],
    voices: dict,
    default_voice: str = "",
    only_paragraph: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> tuple[np.ndarray, int]:
    selected = [p for p in paragraphs if only_paragraph is None or p.index == only_paragraph]
    total = sum(len(p.segments) for p in selected)
    if total == 0:
        raise ValueError("السكريبت فاضي.")

    pieces: list[np.ndarray] = []
    sample_rate: int | None = None
    done = 0

    def sr_or_default() -> int:
        return sample_rate or 24000

    for p_pos, paragraph in enumerate(selected):
        voice = pick_voice(engine, voices, default_voice, paragraph.index)
        if p_pos > 0:
            pieces.append(silence(sr_or_default(), PARAGRAPH_GAP))

        for segment in paragraph.segments:
            if is_cancelled and is_cancelled():
                raise Cancelled()
            profile = segment.profile

            if segment.is_pause_only:
                length = profile.pause_before + profile.pause_after
                pieces.append(silence(sr_or_default(), length if length > 0.25 else MIN_PAUSE_ONLY))
            else:
                wav, sr = engine.synthesize(segment.text, voice, profile)
                if sample_rate is None:
                    sample_rate = sr
                elif sr != sample_rate:
                    wav = resample_linear(wav, sr, sample_rate)
                wav = fade_edges(apply_gain(wav, profile.volume), sample_rate)
                pieces.append(silence(sample_rate, profile.pause_before))
                pieces.append(wav)
                pieces.append(silence(sample_rate, profile.pause_after))

            done += 1
            if on_progress:
                on_progress(done, total)

    sr = sr_or_default()
    return normalize_peak(np.concatenate(pieces)), sr
