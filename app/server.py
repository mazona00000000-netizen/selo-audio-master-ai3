"""سيرفر محلي بسيط (مكتبة بايثون القياسية بس، من غير FastAPI).

التشغيل:  python -m app.server
وبعدين افتح:  http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .audio import to_wav_bytes
from .cues import known_cue_examples
from .engines import engine_info, get_engine
from .engines.base import ROOT
from .render import Cancelled, render_script
from .script import parse_script, unknown_cues

STATIC = ROOT / "static"
OUTPUTS = ROOT / "outputs"
MAX_BODY = 2 * 1024 * 1024
GENERATION_LOCK = threading.Lock()  # موديل واحد على الجهاز: مهمة واحدة في المرة


def load_env_file(path: Path) -> None:
    """اقرا ملف .env بسيط (KEY=VALUE) من غير مكتبات."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Job:
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex
        self.status = "queued"  # queued | running | done | error | cancelled
        self.done = 0
        self.total = 0
        self.error = ""
        self.audio = b""
        self.filename = ""
        self.cancel = False

    def public(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "done": self.done,
            "total": self.total,
            "error": self.error,
            "filename": self.filename,
        }


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()


def _run_job(job: Job, body: dict) -> None:
    try:
        engine = get_engine(str(body.get("engine", "")))
        ok, reason = engine.available()
        if not ok:
            raise RuntimeError(reason)

        paragraphs = parse_script(str(body.get("script", "")))
        only = body.get("only_paragraph")
        only = int(only) if only is not None else None

        job.total = sum(len(p.segments) for p in paragraphs if only is None or p.index == only)
        with GENERATION_LOCK:
            job.status = "running"

            def progress(done: int, total: int) -> None:
                job.done, job.total = done, total

            wav, sr = render_script(
                engine,
                paragraphs,
                voices=body.get("voices") or {},
                default_voice=str(body.get("default_voice") or ""),
                only_paragraph=only,
                on_progress=progress,
                is_cancelled=lambda: job.cancel,
            )
        job.audio = to_wav_bytes(wav, sr)
        if only is None:
            OUTPUTS.mkdir(exist_ok=True)
            job.filename = f"voiceover-{datetime.now():%Y%m%d-%H%M%S}.wav"
            (OUTPUTS / job.filename).write_bytes(job.audio)
        else:
            job.filename = f"paragraph-{only + 1}.wav"
        job.status = "done"
    except Cancelled:
        job.status = "cancelled"
    except Exception as exc:  # نعرض الخطأ للمستخدم بدل ما الخيط يموت بصمت
        job.status = "error"
        job.error = f"{type(exc).__name__}: {exc}"


class Handler(BaseHTTPRequestHandler):
    server_version = "SeloStudio/1.0"

    def log_message(self, fmt, *args):  # هدوء في التيرمنال
        return

    # ---------- مساعدات ----------
    def _send(self, code: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("الطلب كبير أوي.")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("لازم JSON object.")
        return data

    # ---------- المسارات ----------
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            page = STATIC / "index.html"
            if not page.is_file():
                return self._json(404, {"error": "static/index.html مش موجود"})
            return self._send(200, page.read_bytes(), "text/html; charset=utf-8")

        if path == "/api/engines":
            return self._json(200, {"engines": engine_info(), "cues": known_cue_examples()})

        match = re.fullmatch(r"/api/jobs/([0-9a-f]{32})(/audio)?", path)
        if match:
            with JOBS_LOCK:
                job = JOBS.get(match.group(1))
            if job is None:
                return self._json(404, {"error": "المهمة مش موجودة"})
            if not match.group(2):
                return self._json(200, job.public())
            if job.status != "done":
                return self._json(409, {"error": "الصوت لسه ما خلصش"})
            return self._send(
                200,
                job.audio,
                "audio/wav",
                {"Content-Disposition": f'inline; filename="{job.filename}"'},
            )
        self._json(404, {"error": "مسار غير موجود"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            body = self._read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)})

        if path == "/api/parse":
            paragraphs = parse_script(str(body.get("script", "")))
            return self._json(
                200,
                {
                    "paragraphs": [p.to_dict() for p in paragraphs],
                    "unknown_cues": unknown_cues(paragraphs),
                    "segments": sum(len(p.segments) for p in paragraphs),
                },
            )

        if path == "/api/jobs":
            if not str(body.get("script", "")).strip():
                return self._json(400, {"error": "السكريبت فاضي."})
            try:
                get_engine(str(body.get("engine", "")))
            except KeyError as exc:
                return self._json(400, {"error": str(exc)})
            job = Job()
            with JOBS_LOCK:
                JOBS[job.id] = job
                # نحافظ على آخر 30 مهمة بس عشان الرام
                for old in list(JOBS)[:-30]:
                    del JOBS[old]
            threading.Thread(target=_run_job, args=(job, body), daemon=True).start()
            return self._json(202, job.public())

        match = re.fullmatch(r"/api/jobs/([0-9a-f]{32})/cancel", path)
        if match:
            with JOBS_LOCK:
                job = JOBS.get(match.group(1))
            if job is None:
                return self._json(404, {"error": "المهمة مش موجودة"})
            job.cancel = True
            return self._json(200, job.public())

        self._json(404, {"error": "مسار غير موجود"})


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    load_env_file(ROOT / ".env")
    parser = argparse.ArgumentParser(description="استوديو الراوي")
    parser.add_argument("--host", default="127.0.0.1", help="127.0.0.1 = على جهازك بس (أأمن اختيار)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    url = f"http://{args.host}:{args.port}"
    print(f"استوديو الراوي شغال على {url}  (اقفله بـ Ctrl+C)")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nمع السلامة")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
