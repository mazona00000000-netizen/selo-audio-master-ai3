"""الشكل العام لأي محرك صوت. كل محرك بيترجم الـ Profile لتعليماته هو."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from ..cues import Profile

ROOT = Path(__file__).resolve().parent.parent.parent


def references_dir() -> Path:
    return Path(os.environ.get("REFERENCES_DIR", ROOT / "references"))


class Engine:
    name = ""
    label = ""
    description = ""
    install_hint = ""
    #: هل المحرك بيستخدم السرعة/شدة التعبير من الـ Profile (للعرض في الواجهة بس)
    uses_speed = False
    uses_exaggeration = False

    def available(self) -> tuple[bool, str]:
        """(جاهز؟، سبب لو مش جاهز). ما تحمّلش الموديل هنا."""
        return True, ""

    def builtin_voices(self) -> list[str]:
        return []

    def custom_voices(self) -> list[str]:
        """أصوات مخصصة: أي فولدر جوه references/ فيه ملف wav."""
        base = references_dir()
        if not base.is_dir():
            return []
        found = []
        for child in sorted(base.iterdir()):
            if child.is_dir() and any(child.glob("*.wav")):
                found.append(child.name)
        return found

    def voices(self) -> list[str]:
        merged = list(self.builtin_voices())
        for name in self.custom_voices():
            if name not in merged:
                merged.append(name)
        return merged

    def find_reference(self, voice: str, key: str, allow_default: bool) -> tuple[Path, str | None] | None:
        """دوّر على مقطع مرجعي للإحساس ده: references/<الصوت>/<الإحساس>.wav (وممكن .txt جنبه بالنص)."""
        folder = references_dir() / voice
        names = [key] + (["default"] if allow_default else [])
        for stem in names:
            wav = folder / f"{stem}.wav"
            if wav.is_file():
                txt = folder / f"{stem}.txt"
                transcript = txt.read_text(encoding="utf-8").strip() if txt.is_file() else None
                return wav, transcript
        return None

    def synthesize(self, text: str, voice: str, profile: Profile) -> tuple[np.ndarray, int]:
        raise NotImplementedError
