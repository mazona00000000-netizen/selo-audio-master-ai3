"""محرك تجريبي: بيطلّع همهمة بدل كلام. بس عشان تجرّب الواجهة والتجميع من غير موديل."""

from __future__ import annotations

import numpy as np

from ..cues import Profile
from .base import Engine

SR = 16000


class DemoEngine(Engine):
    name = "demo"
    label = "تجريبي (بدون موديل)"
    description = "بيطلّع صوت همهمة بدل الكلام، لاختبار الواجهة والوقفات وعلو الصوت."
    uses_speed = True

    def builtin_voices(self) -> list[str]:
        return ["صوت منخفض", "صوت متوسط", "صوت عالي"]

    def synthesize(self, text: str, voice: str, profile: Profile) -> tuple[np.ndarray, int]:
        base = {"صوت منخفض": 110.0, "صوت متوسط": 170.0, "صوت عالي": 240.0}.get(voice, 170.0)
        seconds = max(0.4, len(text) * 0.055 / profile.speed)
        t = np.linspace(0.0, seconds, int(SR * seconds), endpoint=False)
        vibrato = 1.0 + 0.04 * np.sin(2 * np.pi * 5.0 * t)
        wave = np.sin(2 * np.pi * base * t * vibrato) * 0.5
        wave += np.sin(2 * np.pi * base * 2 * t) * 0.15
        envelope = 0.55 + 0.45 * np.sin(2 * np.pi * 3.0 * t) ** 2
        return (wave * envelope * 0.6).astype(np.float32), SR
