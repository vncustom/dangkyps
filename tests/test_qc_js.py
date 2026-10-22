"""Kiem tra code Check file (JS chay trong trinh duyet) bang cach chay chinh no trong Node."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app import config

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="can Node.js de test code JS")


def run_node(*args):
    proc = subprocess.run([NODE, *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def ffprobe(path):
    out = subprocess.run([config.FFPROBE_BIN, "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", str(path)], capture_output=True, check=True).stdout
    return json.loads(out)


def test_md5_js_matches_node_crypto():
    assert "OK" in run_node(ROOT / "tests" / "js" / "md5_test.js")


@pytest.mark.parametrize("codec", ["h264", "hevc"])
def test_qc_js_matches_file_and_ffprobe(codec, sample_videos, tmp_path):
    path = sample_videos[codec]
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(config.QC_SPEC), encoding="utf-8")
    out = json.loads(run_node(ROOT / "tests" / "js" / "run_qc.js", path, spec))
    # MD5 phai bang MD5 cua file goc
    assert out["md5"] == hashlib.md5(path.read_bytes()).hexdigest().upper()
    info, items = out["info"], {i["param"]: i for i in out["report"]["items"]}
    probe = ffprobe(path)
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert info["video"]["codec"] == v["codec_name"]
    assert (info["video"]["width"], info["video"]["height"]) == (v["width"], v["height"])
    assert info["video"]["fps"] == pytest.approx(25.0)
    assert info["video"]["durationSec"] == pytest.approx(float(v["duration"]), abs=0.05)
    assert info["video"]["chroma"] == 1 and info["video"]["depth"] == 8
    assert info["video"]["progressive"] is True
    assert info["audio"]["codec"] == "aac" and info["audio"]["profile"] == "LC"
    assert info["audio"]["rate"] == int(a["sample_rate"]) and info["audio"]["channels"] == a["channels"]
    # doi chieu voi spec: mau 320x240 25fps nen resolution/fps FAIL; h264 va hevc deu duoc chap nhan
    assert items["Resolution"]["status"] == "FAIL" and items["Frame rate"]["status"] == "FAIL"
    assert items["Video compression"]["status"] == "PASS"
    assert items["Audio format"]["status"] == "PASS" and items["Audio sample rate"]["status"] in ("PASS", "FAIL")
    assert items["Frame cadence"]["status"] == "PASS"
    assert items["File MD5"]["actual"] == out["md5"]
    assert out["report"]["result"] == "FAIL" and len(out["report"]["items"]) == 25


def make_pcm_video(path, audio_codec):
    subprocess.run([config.FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=25",
                    "-f", "lavfi", "-i", "sine=duration=1:sample_rate=48000", "-ac", "2", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", audio_codec, "-strict", "-2", "-shortest", str(path)],
                   check=True, capture_output=True)


def qc(path, tmp_path, **spec_override):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({**config.QC_SPEC, **spec_override}), encoding="utf-8")
    out = json.loads(run_node(ROOT / "tests" / "js" / "run_qc.js", path, spec))
    return out, {i["param"]: i for i in out["report"]["items"]}


@pytest.mark.parametrize("audio_codec,fourcc,kbps", [("pcm_s16le", "ipcm", 1536), ("pcm_s24le", "ipcm", 2304),
                                                       ("pcm_f32le", "fpcm", 3072)])
def test_qc_js_accepts_uncompressed_audio(audio_codec, fourcc, kbps, tmp_path):
    path = tmp_path / f"{audio_codec}.mp4"
    make_pcm_video(path, audio_codec)
    out, items = qc(path, tmp_path)
    assert out["info"]["audio"]["codec"] == "pcm"
    assert items["Audio format"]["status"] == "PASS" and fourcc in items["Audio format"]["actual"]
    assert items["Audio sample rate"]["status"] == "PASS" and items["Audio channels"]["status"] == "PASS"
    assert items["Audio bitrate"]["actual"] == f"{kbps} kb/s"
    # neu spec chi cho AAC thi PCM phai FAIL
    _, items = qc(path, tmp_path, audio_formats=["aac"])
    assert items["Audio format"]["status"] == "FAIL"


def test_qc_js_profile_list_and_level_threshold(sample_videos, tmp_path):
    path = sample_videos["h264"]          # libx264 mac dinh: High, level 1.3 (320x240)
    _, items = qc(path, tmp_path)
    assert items["Video profile"]["actual"] == "High" and items["Video profile"]["status"] == "PASS"
    assert items["Video profile"]["expected"] == "Main / Main 10 / High"
    assert items["Video level"]["expected"] == "≥ 4.0" and items["Video level"]["status"] == "FAIL"
    _, items = qc(path, tmp_path, video_profiles=["Main", "Main 10"], video_level_min=1.3)
    assert items["Video profile"]["status"] == "FAIL" and items["Video level"]["status"] == "PASS"
    _, items = qc(path, tmp_path, video_profiles=["high"])           # khong phan biet hoa thuong
    assert items["Video profile"]["status"] == "PASS"


def test_qc_js_rejects_non_mp4(tmp_path):
    bad = tmp_path / "x.mp4"
    bad.write_bytes(b"not an mp4 file at all" * 10)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(config.QC_SPEC), encoding="utf-8")
    proc = subprocess.run([NODE, str(ROOT / "tests" / "js" / "run_qc.js"), str(bad), str(spec)],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode != 0 and "moov" in proc.stderr


def test_qc_js_video_codec_list(sample_videos, tmp_path):
    _, items = qc(sample_videos["hevc"], tmp_path)
    assert items["Video compression"]["expected"] == "H.264 / AVC / H.265 / HEVC"
    _, items = qc(sample_videos["hevc"], tmp_path, video_codecs=["h264"])
    assert items["Video compression"]["status"] == "FAIL"
    _, items = qc(sample_videos["hevc"], tmp_path, video_codecs=["h264", "h265"])   # h265 = hevc
    assert items["Video compression"]["status"] == "PASS"
