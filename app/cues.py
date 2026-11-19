"""تحويل الإحساس المكتوب بين أقواس (زي [صوت واطي حزين]) لإعدادات أداء.

الفكرة: الإحساس بيتحوّل لـ Profile فيه أرقام (سرعة، علو صوت، وقفات، شدة تعبير).
كل محرك صوت بياخد من الـ Profile اللي بيفهمه بس، والباقي بيتنفّذ على الصوت نفسه
(علو الصوت والوقفات بيتطبقوا على أي محرك).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_DIACRITICS = re.compile("[ً-ْـ]")
_ARABIC = re.compile("[؀-ۿ]")


def normalize(text: str) -> str:
    """تطبيع بسيط للعربي: شيل التشكيل والتطويل ووحّد الألف والياء والتاء المربوطة."""
    text = _DIACRITICS.sub("", text.lower())
    for src, dst in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        text = text.replace(src, dst)
    return text


@dataclass(frozen=True)
class Profile:
    key: str = "neutral"
    label: str = "عادي"
    speed: float = 1.0
    volume: float = 1.0
    exaggeration: float = 0.5
    pause_before: float = 0.0
    pause_after: float = 0.2
    unknown: bool = False
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "speed": round(self.speed, 3),
            "volume": round(self.volume, 3),
            "exaggeration": round(self.exaggeration, 3),
            "pause_before": round(self.pause_before, 3),
            "pause_after": round(self.pause_after, 3),
            "unknown": self.unknown,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class Rule:
    key: str
    label: str
    words: tuple[str, ...]
    speed: float = 1.0
    volume: float = 1.0
    exaggeration: float | None = None
    pause_before: float = 0.0
    pause_after: float = 0.0

    def matches(self, normalized_cue: str, tokens: list[str]) -> bool:
        for word in self.words:
            w = normalize(word)
            if _ARABIC.search(w):
                if w in normalized_cue:
                    return True
            elif any(tok.startswith(w) for tok in tokens):
                return True
        return False


# الترتيب مهم: أول قاعدة بتطابق هي اللي بتحدد "نوع الإحساس" (key) المستخدم
# في مقاطع المرجع، والقواعد اللي بعدها (واطي، بطيء...) بتعدّل بس.
RULES: tuple[Rule, ...] = (
    Rule("sad", "حزين", ("حزين", "حزن", "حزينه", "sad", "بكاء", "بيبكي", "مكسور", "منكسر", "crying"),
         speed=0.88, volume=0.85, exaggeration=0.4, pause_before=0.25, pause_after=0.5),
    Rule("angry", "غاضب", ("غضب", "غاضب", "عصبي", "angry", "furious", "زعلان جدا"),
         speed=1.1, volume=1.2, exaggeration=0.9),
    Rule("happy", "فرحان", ("فرحان", "فرح", "سعيد", "مبسوط", "متحمس", "حماس", "happy", "excited", "joy"),
         speed=1.08, volume=1.05, exaggeration=0.8),
    Rule("fear", "خايف", ("خايف", "خوف", "رعب", "مرعوب", "قلق", "fear", "scared", "terrified", "afraid"),
         speed=1.1, volume=0.85, exaggeration=0.75, pause_after=0.3),
    Rule("suspense", "تشويق", ("تشويق", "غموض", "غامض", "ترقب", "suspense", "mysterious", "tense"),
         speed=0.9, volume=0.8, exaggeration=0.45, pause_before=0.35, pause_after=0.5),
    Rule("surprise", "مفاجأة", ("مفاجا", "صدمه", "صدمة", "ذهول", "surprise", "shock", "gasp"),
         speed=1.08, exaggeration=0.8, pause_before=0.15),
    Rule("calm", "هادي", ("هادي", "هدوء", "رايق", "calm", "gentle", "peaceful"),
         speed=0.95, volume=0.9, exaggeration=0.3, pause_after=0.3),
    Rule("whisper", "همس", ("همس", "بيهمس", "وشوشه", "whisper"),
         speed=0.9, volume=0.35, exaggeration=0.3),
    Rule("low", "صوت واطي", ("واطي", "منخفض", "خافت", "low voice", "quiet", "soft", "low"),
         speed=0.95, volume=0.6, exaggeration=0.35),
    Rule("loud", "صوت عالي", ("عالي", "ارتفاع", "يعلي", "صراخ", "بيصرخ", "يصرخ", "rising", "loud", "shout", "yell"),
         speed=1.04, volume=1.35, exaggeration=0.85),
    Rule("slow", "بطيء", ("بطء", "بطي", "بطئ", "ببطء", "slow"), speed=0.85),
    Rule("fast", "سريع", ("سريع", "بسرعه", "اسرع", "fast", "quick", "hurried"), speed=1.18),
    Rule("pause", "وقفة", ("وقفه", "وقفة", "صمت", "سكوت", "pause", "silence", "beat"),
         pause_before=0.8),
)


def build_profile(raw_cue: str) -> Profile:
    """حوّل نص الإحساس (من جوه الأقواس) لـ Profile. لو مفهمناش حاجة يرجّع عادي مع علامة unknown."""
    raw_cue = raw_cue.strip()
    if not raw_cue:
        return Profile()

    normalized = normalize(raw_cue)
    tokens = re.findall(r"\w+", normalized)
    matched = [rule for rule in RULES if rule.matches(normalized, tokens)]
    if not matched:
        return Profile(unknown=True, raw=raw_cue, label=raw_cue)

    speed = 1.0
    volume = 1.0
    for rule in matched:
        speed *= rule.speed
        volume *= rule.volume
    exaggerations = [r.exaggeration for r in matched if r.exaggeration is not None]
    exaggeration = sum(exaggerations) / len(exaggerations) if exaggerations else 0.5

    return Profile(
        key=matched[0].key,
        label=" + ".join(rule.label for rule in matched),
        speed=min(max(speed, 0.6), 1.5),
        volume=min(max(volume, 0.2), 1.6),
        exaggeration=min(max(exaggeration, 0.25), 1.0),
        pause_before=min(sum(r.pause_before for r in matched), 1.5),
        pause_after=min(0.2 + sum(r.pause_after for r in matched), 1.5),
        raw=raw_cue,
    )


def known_cue_examples() -> list[str]:
    """أمثلة للأزرار السريعة في الواجهة."""
    return [rule.label for rule in RULES]
