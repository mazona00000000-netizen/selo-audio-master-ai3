"""Windows desktop entry point for SELO AUDIO MASTER AI."""

from __future__ import annotations

import os
import traceback
from pathlib import Path


def main() -> None:
    try:
        from app.server import main as server_main
        server_main()
    except Exception:
        details = traceback.format_exc()
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SELO AUDIO MASTER AI"
        base.mkdir(parents=True, exist_ok=True)
        log = base / "startup-error.log"
        log.write_text(details, encoding="utf-8")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "تعذر تشغيل SELO AUDIO MASTER AI. تم حفظ تفاصيل المشكلة في:\n" + str(log),
                "SELO AUDIO MASTER AI",
                0x10,
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
