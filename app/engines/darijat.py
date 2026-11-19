"""Darijat TTS (tts.darijat.com): خدمة عربية مدفوعة بتدعم لهجات منها المصري. تجريبي.

تنبيه: شكل رد الـ API مش موثّق على موقعهم وقت كتابة الكود، فالمحرك ده بيحاول يفهم
أكتر من شكل (صوت مباشر، أو JSON فيه رابط أو base64). لو فشل بيطبعلك أول جزء من الرد
عشان نظبطه سوا. وكل مقطع بيتحسب عليك رصيد من حسابك.

الإعداد (متغيرات بيئة):
    DARIJAT_API_TOKEN     التوكن (إجباري)
    DARIJAT_API_VERSION   v2 (الافتراضي) أو v1
    DARIJAT_VOICES        أسماء الأصوات مفصولة بفاصلة (لو عايز تغيّر القائمة)
    DARIJAT_STYLE_MODE    text_command (الافتراضي: الإحساس بيتبعت كأمر أسلوب في النص) أو none
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

import numpy as np

from ..audio import decode_audio_bytes
from ..cues import Profile
from .base import Engine

BASE_URL = "https://tts.darijat.com"
DEFAULT_VOICES = ["سارة", "مريم", "طارق", "يوسف", "خالد", "ليلى", "فاطمة", "معلق سعودي"]
_URL_KEYS = ("audio_url", "url", "file_url", "audio_file", "file")
_B64_KEYS = ("audio_base64", "audio", "data", "base64")


class DarijatEngine(Engine):
    name = "darijat"
    label = "Darijat (API مدفوع، تجريبي)"
    description = "خدمة عربية بلهجات متعددة منها المصري. محتاج توكن، ورصيدك بيتخصم."
    install_hint = "ضيف DARIJAT_API_TOKEN في ملف .env"
    uses_speed = True

    def available(self) -> tuple[bool, str]:
        if not os.environ.get("DARIJAT_API_TOKEN"):
            return False, "محتاج التوكن: حطه في المتغير DARIJAT_API_TOKEN (ملف .env)"
        return True, ""

    def builtin_voices(self) -> list[str]:
        custom = os.environ.get("DARIJAT_VOICES", "")
        names = [v.strip() for v in custom.split(",") if v.strip()]
        return names or DEFAULT_VOICES

    def custom_voices(self) -> list[str]:
        return []  # الأصوات هنا من حسابك على الموقع، مش من مقاطع مرجعية

    def _request(self, payload: dict) -> tuple[bytes, str]:
        version = os.environ.get("DARIJAT_API_VERSION", "v2").lower()
        url = f"{BASE_URL}/api/{version}/external/generate-audio"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {os.environ['DARIJAT_API_TOKEN']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.read(), resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as err:
            body = err.read()[:300].decode("utf-8", "replace")
            raise RuntimeError(f"Darijat رجّع خطأ {err.code}: {body}") from err

    def _download(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=180) as resp:
            return resp.read()

    def _audio_from_response(self, body: bytes, content_type: str) -> bytes:
        if content_type.startswith("audio/") or body[:4] == b"RIFF" or body[:3] == b"ID3" or body[:2] == b"\xff\xfb":
            return body
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError:
            raise RuntimeError(f"رد غير مفهوم من Darijat: {body[:200]!r}")

        def search(node):
            if isinstance(node, dict):
                for key in _URL_KEYS:
                    value = node.get(key)
                    if isinstance(value, str) and value.startswith("http"):
                        return ("url", value)
                for key in _B64_KEYS:
                    value = node.get(key)
                    if isinstance(value, str) and len(value) > 200:
                        return ("b64", value)
                for value in node.values():
                    found = search(value)
                    if found:
                        return found
            return None

        found = search(data)
        if not found:
            raise RuntimeError(f"مش لاقي الصوت جوه رد Darijat. الرد بيبدأ بـ: {json.dumps(data, ensure_ascii=False)[:300]}")
        kind, value = found
        if kind == "url":
            return self._download(value)
        return base64.b64decode(value.split(",", 1)[-1])

    def synthesize(self, text: str, voice: str, profile: Profile) -> tuple[np.ndarray, int]:
        spoken = text
        if os.environ.get("DARIJAT_STYLE_MODE", "text_command") == "text_command" and profile.raw:
            spoken = f'النص: "{text}"، الأسلوب: "{profile.raw}"'
        payload = {"text": spoken, "voice_name": voice, "speed": round(profile.speed, 2)}
        body, content_type = self._request(payload)
        return decode_audio_bytes(self._audio_from_response(body, content_type))
