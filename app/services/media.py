"""ffprobe / thumbnail / proxy bang ffmpeg."""
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from app import config

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)


def frames_to_tc(total_frames: int, fps: float) -> str:
    """So frame -> hh:mm:ss:ff (non-drop)."""
    nominal = max(int(round(fps)), 1)
    ff = total_frames % nominal
    total_sec = total_frames // nominal
    return f"{total_sec // 3600:02d}:{total_sec % 3600 // 60:02d}:{total_sec % 60:02d}:{ff:02d}"


def probe(path: Path) -> dict:
    """Tra ve codec, width, height, fps, duration_sec, duration_tc."""
    proc = _run([config.FFPROBE_BIN, "-v", "error", "-print_format", "json",
                 "-show_format", "-show_streams", str(path)], timeout=120)
    if proc.returncode != 0:
        raise RuntimeError("ffprobe lỗi: " + proc.stderr.decode("utf-8", "replace")[-300:])
    info = json.loads(proc.stdout)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError("File không có luồng video")
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "25/1"
    try:
        fps = float(Fraction(rate)) if rate not in ("0/0", "") else 25.0
    except (ZeroDivisionError, ValueError):
        fps = 25.0
    if fps <= 0:
        fps = 25.0
    duration = float(video.get("duration") or info.get("format", {}).get("duration") or 0)
    return {
        "codec": video.get("codec_name", ""),
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "fps": round(fps, 3),
        "duration_sec": duration,
        "duration_tc": frames_to_tc(int(round(duration * fps)), fps),
    }


def make_thumbnail(src: Path, dest: Path, at_sec: float = 1.0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for ss in (at_sec, 0):
        proc = _run([config.FFMPEG_BIN, "-y", "-ss", str(ss), "-i", str(src), "-frames:v", "1",
                     "-vf", "scale=320:-2", str(dest)], timeout=300)
        if proc.returncode == 0 and dest.exists():
            return
    raise RuntimeError("Không tạo được thumbnail")


def make_proxy(src: Path, dest: Path) -> None:
    """Proxy H.264 720p de duyet tren trinh duyet (file goc 4K/HEVC co the khong phat on)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = _run([
        config.FFMPEG_BIN, "-y", "-i", str(src),
        "-vf", "scale=-2:720", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-pix_fmt", "yuv420p", "-g", "25", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(dest),
    ])
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError("Transcode proxy lỗi: " + proc.stderr.decode("utf-8", "replace")[-300:])
