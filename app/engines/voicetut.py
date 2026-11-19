"""VoiceTut-TTS: موديل مفتوح (Apache-2.0) متدرّب على المصري. بيشتغل أوفلاين على جهازك.

التثبيت:
    pip install voicetut-tts
    pip install git+https://github.com/k2-fsa/OmniVoice.git
المشاعر: الموديل نفسه مفيهوش تحكم في الإحساس، فبنستخدم السرعة + مقاطع مرجعية للإحساس
(references/<الصوت>/<الإحساس>.wav و .txt بنفس الاسم فيه نص المقطع).
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import threading

import numpy as np

from ..audio import read_wav
from ..cues import Profile
from .base import Engine

MALE = ["Ahmed", "Ali", "Hassan", "Karim", "Mahmoud", "Mohammed", "Mostafa", "Ramy", "Shaker", "Tareq", "Yehia", "Youssef"]
FEMALE = ["Hadeer", "Hanan", "Mariam", "Rana", "Sarah", "Yasmin", "Yara"]


class VoiceTutEngine(Engine):
    name = "voicetut"
    label = "VoiceTut (مصري، محلي ومجاني)"
    description = "موديل مفتوح للهجة المصرية بيشتغل على جهازك. المشاعر عن طريق السرعة والوقفات ومقاطع مرجعية."
    install_hint = "pip install voicetut-tts  ثم  pip install git+https://github.com/k2-fsa/OmniVoice.git"
    uses_speed = True

    def __init__(self) -> None:
        self._tts = None
        self._lock = threading.Lock()

    def available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("voicetut_tts") is None:
            return False, f"المكتبة مش متسطبة. شغّل: {self.install_hint}"
        return True, ""

    def builtin_voices(self) -> list[str]:
        return MALE + FEMALE

    def _load(self):
        with self._lock:
            if self._tts is None:
                from voicetut_tts import VoiceTutTTS  # type: ignore

                repo = os.environ.get("VOICETUT_MODEL", "mohammedaly22/VoiceTut-TTS")
                self._tts = VoiceTutTTS.from_pretrained(repo)
        return self._tts

    def synthesize(self, text: str, voice: str, profile: Profile) -> tuple[np.ndarray, int]:
        tts = self._load()
        kwargs: dict = {
            "speed": profile.speed,
            "num_step": int(os.environ.get("VOICETUT_NUM_STEP", "32")),
        }

        is_custom = voice in self.custom_voices()
        ref = self.find_reference(voice, profile.key, allow_default=is_custom)
        if ref and ref[1]:
            kwargs["ref_audio"] = str(ref[0])
            kwargs["ref_text"] = ref[1]
        elif is_custom:
            raise RuntimeError(
                f"الصوت المخصص '{voice}' محتاج ملف نص جنب المقطع المرجعي "
                f"(references/{voice}/default.txt فيه كلام المقطع بالظبط)."
            )
        else:
            kwargs["speaker"] = voice

        with tempfile.TemporaryDirectory() as folder:
            out = os.path.join(folder, "segment.wav")
            tts.synthesize(text, output=out, **kwargs)
            return read_wav(out)
