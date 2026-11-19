"""قراءة السكريبت: كل سطر ممكن يبدأ بإحساس بين أقواس، والفقرات بتتفصل بسطر فاضي."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .cues import Profile, build_profile

_CUE_SPLIT = re.compile(r"(\[[^\]]*\])")


@dataclass
class Segment:
    text: str
    profile: Profile
    paragraph: int
    line: int

    @property
    def is_pause_only(self) -> bool:
        return not self.text

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "paragraph": self.paragraph,
            "line": self.line,
            "profile": self.profile.to_dict(),
        }


@dataclass
class Paragraph:
    index: int
    segments: list[Segment] = field(default_factory=list)

    @property
    def snippet(self) -> str:
        for seg in self.segments:
            if seg.text:
                return seg.text[:60]
        return "(وقفة)"

    def to_dict(self) -> dict:
        labels: list[str] = []
        for seg in self.segments:
            label = seg.profile.label
            if label != "عادي" and label not in labels:
                labels.append(label)
        return {
            "index": self.index,
            "snippet": self.snippet,
            "cues": labels,
            "segments": len(self.segments),
        }


def clean_text(text: str) -> str:
    text = text.replace("*", "").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_line(line: str, paragraph: int, line_no: int) -> list[Segment]:
    segments: list[Segment] = []
    pending: list[str] = []
    for chunk in _CUE_SPLIT.split(line):
        if not chunk:
            continue
        if chunk.startswith("[") and chunk.endswith("]"):
            pending.append(chunk[1:-1].strip())
            continue
        text = clean_text(chunk)
        if not text:
            continue
        profile = build_profile(" ".join(c for c in pending if c))
        segments.append(Segment(text, profile, paragraph, line_no))
        pending = []
    if pending and any(pending):
        # أقواس من غير نص بعدها (زي [وقفة]) = وقفة بس
        segments.append(Segment("", build_profile(" ".join(c for c in pending if c)), paragraph, line_no))
    return segments


def parse_script(script: str) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    current: Paragraph | None = None

    for line_no, raw_line in enumerate(script.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            current = None
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        segments = _parse_line(line, len(paragraphs) if current is None else current.index, line_no)
        if not segments:
            continue
        if current is None:
            current = Paragraph(index=len(paragraphs))
            paragraphs.append(current)
            for seg in segments:
                seg.paragraph = current.index
        current.segments.extend(segments)
    return paragraphs


def unknown_cues(paragraphs: list[Paragraph]) -> list[str]:
    seen: list[str] = []
    for para in paragraphs:
        for seg in para.segments:
            if seg.profile.unknown and seg.profile.raw not in seen:
                seen.append(seg.profile.raw)
    return seen
