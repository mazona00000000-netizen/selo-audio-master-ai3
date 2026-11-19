"""VoiceTut-TTS: لهجة مصرية، 19 صوتًا جاهزًا.

الافتراضي يستخدم Space عام على Hugging Face لتوليد الصوت عبر الإنترنت؛
وده بيجنب تثبيت PyTorch والموديل الكبير محليًا. لو مكتبة VoiceTut المحلية
موجودة، نستخدمها بدل الاتصال الخارجي.
"""

from __future__ import annotations

import importlib.util
import os
import threading
import urllib.request
from pathlib import Path

import numpy as np

from ..audio import decode_audio_bytes, read_wav
from ..cues import Profile
from .base import Engine

MALE = ["Ahmed", "Ali", "Hassan", "Karim", "Mahmoud", "Mohammed", "Mostafa", "Ramy", "Shaker", "Tareq", "Yehia", "Youssef"]
FEMALE = ["Hadeer", "Hanan", "Mariam", "Rana", "Sarah", "Yasmin", "Yara"]
SPACE_ID = "mohammedaly22/VoiceTut-TTS"


class VoiceTutEngine(Engine):
    name = "voicetut"
    label = "VoiceTut المصري (19 صوتًا عبر الإنترنت)"
    description = "19 صوتًا مصريًا رجاليًا ونسائيًا. التوليد عبر الإنترنت ولا يحتاج موديل محلي."
    install_hint = "اتأكد من اتصال الإنترنت. مكتبة الاتصال المطلوبة: gradio_client"
    uses_speed = True

    def __init__(self) -> None:
        self._tts = None
        self._client = None
        self._lock = threading.Lock()

    def available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("voicetut_tts") is not None:
            return True, ""
        if importlib.util.find_spec("gradio_client") is None:
            return False, "مكتبة الاتصال غير موجودة. أعد تثبيت إصدار التطبيق الأحدث."
        return True, "يتطلب اتصال إنترنت أثناء توليد الصوت."

    def builtin_voices(self) -> list[str]:
        return MALE + FEMALE

    def _load_local(self):
        with self._lock:
            if self._tts is None:
                from voicetut_tts import VoiceTutTTS  # type: ignore
                repo = os.environ.get("VOICETUT_MODEL", "mohammedaly22/VoiceTut-TTS")
                self._tts = VoiceTutTTS.from_pretrained(repo)
        return self._tts

    def _remote_client(self):
        with self._lock:
            if self._client is None:
                from gradio_client import Client  # type: ignore
                self._client = Client(SPACE_ID, verbose=False)
        return self._client

    @staticmethod
    def _remote_audio_file(result):
        candidate = result[0] if isinstance(result, (tuple, list)) else result
        if isinstance(candidate, dict):
            candidate = candidate.get("path") or candidate.get("url") or candidate.get("name")
        if hasattr(candidate, "path"):
            candidate = candidate.path
        if not candidate:
            raise RuntimeError("خدمة الصوت رجّعت نتيجة من غير ملف صوت.")
        return candidate

    def synthesize(self, text: str, voice: str, profile: Profile) -> tuple[np.ndarray, int]:
        # Local install takes precedence, if one is deliberately installed.
        if importlib.util.find_spec("voicetut_tts") is not None:
            tts = self._load_local()
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

            import tempfile
            with tempfile.TemporaryDirectory() as folder:
                out = os.path.join(folder, "segment.wav")
                tts.synthesize(text, output=out, **kwargs)
                return read_wav(out)

        try:
            client = self._remote_client()
            result = client.predict(
                text,
                "arz",
                "builtin",
                voice,
                None,
                "",
                int(os.environ.get("VOICETUT_NUM_STEP", "32")),
                2.0,
                float(profile.speed),
                True,
                api_name="/synthesize",
            )
            audio_file = self._remote_audio_file(result)
            audio_file = str(audio_file)
            if audio_file.startswith(("http://", "https://")):
                with urllib.request.urlopen(audio_file, timeout=120) as response:
                    return decode_audio_bytes(response.read())
            if not Path(audio_file).is_file():
                raise RuntimeError(f"ملف الصوت الناتج غير موجود: {audio_file}")
            return read_wav(audio_file)
        except Exception as exc:
            raise RuntimeError(
                "تعذر الاتصال بخدمة VoiceTut أو توليد الصوت. اتأكد من الإنترنت، "
                "وجرب تاني بعد دقيقة. التفاصيل: " + str(exc)
            ) from exc
