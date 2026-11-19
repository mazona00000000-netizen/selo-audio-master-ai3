import json
import threading
import time
import urllib.request
import wave
import io

import numpy as np
import pytest

from app.audio import to_wav_bytes
from app.cues import build_profile, normalize
from app.engines import get_engine
from app.render import render_script
from app.script import parse_script, unknown_cues


def test_normalize_arabic():
    assert normalize("حَزِينة") == "حزينه"
    assert normalize("أإآ") == "ااا"


def test_cue_sad_low_combines():
    p = build_profile("صوت واطي حزين")
    assert p.key == "sad"
    assert p.speed < 1.0
    assert p.volume < 0.6
    assert not p.unknown


def test_cue_angry_loud():
    p = build_profile("غضب صوت عالي")
    assert p.key == "angry"
    assert p.volume > 1.3
    assert p.exaggeration > 0.8


def test_latin_word_boundary_slow_is_not_low():
    p = build_profile("slow")
    assert p.key == "slow"
    assert p.volume == 1.0  # لو "low" اتطابقت غلط كان الصوت هيقل


def test_unknown_and_empty_cues():
    assert build_profile("بيرقص").unknown
    assert not build_profile("").unknown


def test_parse_paragraphs_and_cues():
    script = (
        "# تعليق\n"
        "[هادي] أول سطر.\n"
        "سطر عادي.\n"
        "\n"
        "[خايف] [صوت واطي] تاني فقرة.\n"
        "[وقفة]\n"
        "[حزين] جملة أولى. [فرحان] جملة تانية.\n"
    )
    paras = parse_script(script)
    assert len(paras) == 2
    first, second = paras
    assert [s.profile.key for s in first.segments] == ["calm", "neutral"]
    assert second.segments[0].profile.key == "fear"
    assert second.segments[0].text == "تاني فقرة."
    assert second.segments[1].is_pause_only
    assert [s.profile.key for s in second.segments[2:]] == ["sad", "happy"]


def test_unknown_cues_listed():
    paras = parse_script("[بيرقص] كلام\n[حزين] كلام")
    assert unknown_cues(paras) == ["بيرقص"]


def test_render_with_demo_engine_applies_pauses_and_volume():
    engine = get_engine("demo")
    paras = parse_script("[همس] كلام قصير.\n[وقفة]\n[صوت عالي] كلام تاني.")
    progress = []
    wav, sr = render_script(engine, paras, {}, "", on_progress=lambda d, t: progress.append((d, t)))
    assert sr == 16000
    assert progress[-1] == (3, 3)
    assert len(wav) / sr > 2.0  # وقفة 0.8 + كلام
    assert float(np.max(np.abs(wav))) <= 0.951


def test_render_only_paragraph():
    engine = get_engine("demo")
    paras = parse_script("أول فقرة.\n\nتاني فقرة أطول شوية.")
    full, sr = render_script(engine, paras, {}, "")
    part, _ = render_script(engine, paras, {}, "", only_paragraph=1)
    assert len(part) < len(full)


def test_empty_script_raises():
    with pytest.raises(ValueError):
        render_script(get_engine("demo"), [], {}, "")


def test_wav_bytes_valid():
    data = to_wav_bytes(np.zeros(1600, dtype=np.float32), 16000)
    with wave.open(io.BytesIO(data)) as handle:
        assert handle.getframerate() == 16000
        assert handle.getnframes() == 1600


def test_server_end_to_end(tmp_path, monkeypatch):
    from app import server

    monkeypatch.setattr(server, "OUTPUTS", tmp_path)
    httpd = server.create_server("127.0.0.1", 0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    def call(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return resp.read(), resp.headers.get("Content-Type")

    try:
        raw, _ = call("/api/engines")
        engines = json.loads(raw)["engines"]
        assert {e["name"] for e in engines} >= {"voicetut", "chatterbox", "darijat", "demo"}

        raw, _ = call("/api/parse", {"script": "[حزين] كلام.\n\n[بيرقص] تاني."})
        parsed = json.loads(raw)
        assert len(parsed["paragraphs"]) == 2
        assert parsed["unknown_cues"] == ["بيرقص"]

        raw, _ = call("/api/jobs", {"engine": "demo", "script": "[حزين] كلام.\n[وقفة]\n[فرحان] تاني.", "voices": {}, "default_voice": ""})
        job = json.loads(raw)
        for _ in range(100):
            raw, _ = call(f"/api/jobs/{job['id']}")
            state = json.loads(raw)
            if state["status"] in ("done", "error"):
                break
            time.sleep(0.05)
        assert state["status"] == "done", state
        audio, ctype = call(f"/api/jobs/{job['id']}/audio")
        assert ctype == "audio/wav" and audio[:4] == b"RIFF"
        assert any(tmp_path.glob("voiceover-*.wav"))

        raw, _ = call("/api/jobs", {"engine": "darijat", "script": "كلام"})
        job2 = json.loads(raw)
        for _ in range(100):
            raw, _ = call(f"/api/jobs/{job2['id']}")
            state2 = json.loads(raw)
            if state2["status"] in ("done", "error"):
                break
            time.sleep(0.05)
        assert state2["status"] == "error"  # من غير توكن لازم يفشل برسالة واضحة
        assert "DARIJAT_API_TOKEN" in state2["error"]
    finally:
        httpd.shutdown()
        httpd.server_close()
