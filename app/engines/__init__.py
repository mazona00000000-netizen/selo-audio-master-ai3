"""سجل المحركات. ضيف محرك جديد بإنك تعمل ملف جنب دول وتسجّله هنا."""

from __future__ import annotations

from .base import Engine
from .chatterbox import ChatterboxEngine
from .darijat import DarijatEngine
from .demo import DemoEngine
from .voicetut import VoiceTutEngine

_ENGINES: dict[str, Engine] = {
    engine.name: engine
    for engine in (VoiceTutEngine(), ChatterboxEngine(), DarijatEngine(), DemoEngine())
}


def get_engine(name: str) -> Engine:
    try:
        return _ENGINES[name]
    except KeyError:
        raise KeyError(f"محرك غير معروف: {name}") from None


def engine_info() -> list[dict]:
    info = []
    for engine in _ENGINES.values():
        ok, reason = engine.available()
        info.append(
            {
                "name": engine.name,
                "label": engine.label,
                "description": engine.description,
                "available": ok,
                "reason": reason,
                "voices": engine.voices() if ok else [],
                "uses_speed": engine.uses_speed,
                "uses_exaggeration": engine.uses_exaggeration,
            }
        )
    return info
