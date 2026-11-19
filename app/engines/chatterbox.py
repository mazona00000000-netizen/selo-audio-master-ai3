"""Chatterbox Multilingual (Resemble AI): مفتوح، بيدعم العربي، وفيه مفتاح لشدة التعبير.

التثبيت:  pip install chatterbox-tts
اختياري: نسخة معمولة fine-tune للمصري (صوت واحد، مش مكتملة التدريب):
    CHATTERBOX_EGYPTIAN=1
لتغيير الصوت: حط مقطع مرجعي في references/<اسم>/default.wav
"""

from __future__ import annotations

import importlib.util
import os
import threading

import numpy as np

from ..audio import to_float_mono
from ..cues import Profile
from .base import Engine


class ChatterboxEngine(Engine):
    name = "chatterbox"
    label = "Chatterbox (عربي، محلي ومجاني)"
    description = "بيدعم العربي وفيه شدة تعبير حقيقية. الصوت بيتحدد بمقطع مرجعي."
    install_hint = "pip install chatterbox-tts"
    uses_exaggeration = True

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("chatterbox") is None:
            return False, f"المكتبة مش متسطبة. شغّل: {self.install_hint}"
        return True, ""

    def builtin_voices(self) -> list[str]:
        return ["الصوت الافتراضي"]

    def _device(self) -> str:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load(self):
        with self._lock:
            if self._model is None:
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # type: ignore

                device = self._device()
                model = ChatterboxMultilingualTTS.from_pretrained(device=device)
                if os.environ.get("CHATTERBOX_EGYPTIAN") == "1":
                    from huggingface_hub import hf_hub_download  # type: ignore
                    from safetensors.torch import load_file  # type: ignore

                    path = hf_hub_download(repo_id="AliAbdallah/egyptian-arabic-tts-chatterbox", filename="model.safetensors")
                    model.t3.load_state_dict(load_file(path, device=device), strict=False)
                    model.t3.eval()
                    model.s3gen.eval()
                    model.ve.eval()
                self._model = model
        return self._model

    def synthesize(self, text: str, voice: str, profile: Profile) -> tuple[np.ndarray, int]:
        model = self._load()
        kwargs: dict = {
            "language_id": "ar",
            "exaggeration": profile.exaggeration,
            "cfg_weight": 0.5,
            "temperature": 0.8,
        }
        is_custom = voice in self.custom_voices()
        ref = self.find_reference(voice, profile.key, allow_default=is_custom)
        if ref:
            kwargs["audio_prompt_path"] = str(ref[0])

        wav = model.generate(text, **kwargs)
        return to_float_mono(wav.squeeze().cpu().numpy()), int(model.sr)
