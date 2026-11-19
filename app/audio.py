"""أدوات صوت بسيطة (numpy + مكتبة wave القياسية بس)."""

from __future__ import annotations

import io
import wave

import numpy as np


def silence(sample_rate: int, seconds: float) -> np.ndarray:
    return np.zeros(int(sample_rate * max(0.0, seconds)), dtype=np.float32)


def apply_gain(wav: np.ndarray, gain: float) -> np.ndarray:
    return (wav * gain).astype(np.float32)


def fade_edges(wav: np.ndarray, sample_rate: int, ms: float = 12.0) -> np.ndarray:
    """تدرّج قصير في أول وآخر المقطع عشان ما يبقاش في طقطقة بين المقاطع."""
    n = min(int(sample_rate * ms / 1000), len(wav) // 2)
    if n <= 0:
        return wav
    out = wav.copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def normalize_peak(wav: np.ndarray, peak: float = 0.95) -> np.ndarray:
    top = float(np.max(np.abs(wav))) if len(wav) else 0.0
    if top < 1e-9:
        return wav
    return (wav * (peak / top)).astype(np.float32)


def resample_linear(wav: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    if sr_from == sr_to or len(wav) == 0:
        return wav
    n_out = int(len(wav) * sr_to / sr_from)
    x_old = np.linspace(0.0, 1.0, num=len(wav), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, wav).astype(np.float32)


def to_float_mono(data) -> np.ndarray:
    arr = np.asarray(data)
    if arr.ndim > 1:
        arr = arr.squeeze()
    if arr.ndim > 1:  # قنوات متعددة: ندمجها
        arr = arr.mean(axis=0 if arr.shape[0] < arr.shape[-1] else 1)
    return arr.astype(np.float32)


def to_wav_bytes(wav: np.ndarray, sample_rate: int) -> bytes:
    clipped = np.clip(wav, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buf.getvalue()


def decode_audio_bytes(data: bytes) -> tuple[np.ndarray, int]:
    """فك أي صوت جاي من API (WAV أو MP3...). بنجرّب wave ثم soundfile ثم ffmpeg."""
    import os
    import shutil
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        src = os.path.join(folder, "in.bin")
        with open(src, "wb") as handle:
            handle.write(data)

        if data[:4] == b"RIFF":
            try:
                return read_wav(src)
            except Exception:
                pass

        try:
            import soundfile as sf  # type: ignore

            decoded, sr = sf.read(src, dtype="float32")
            return to_float_mono(decoded), int(sr)
        except Exception:
            pass

        if shutil.which("ffmpeg"):
            dst = os.path.join(folder, "out.wav")
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ac", "1", dst],
                check=True,
                timeout=120,
            )
            return read_wav(dst)

    raise RuntimeError("مقدرتش أفك الصوت اللي رجع. ثبّت soundfile (pip install soundfile) أو ffmpeg.")


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """اقرا ملف WAV. بنجرّب soundfile الأول (بيدعم كل الأنواع) وبعدين wave القياسية."""
    try:
        import soundfile as sf  # type: ignore

        data, sr = sf.read(path, dtype="float32")
        return to_float_mono(data), int(sr)
    except ImportError:
        pass

    with wave.open(path, "rb") as handle:
        sr = handle.getframerate()
        width = handle.getsampwidth()
        channels = handle.getnchannels()
        raw = handle.readframes(handle.getnframes())
    if width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise RuntimeError(f"نوع ملف WAV مش مدعوم ({width * 8} bit). ثبّت soundfile: pip install soundfile")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, sr
