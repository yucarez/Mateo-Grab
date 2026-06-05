import os
import sys
import json
import threading
import subprocess
import webbrowser
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file

try:
    import yt_dlp
except ImportError:
    print("yt-dlp not found. Install it with:  pip install yt-dlp")
    sys.exit(1)

app = Flask(__name__, static_folder=".")

# config

BASE_DIR    = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

MP4_QUALITY_MAP = {
    "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
    "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
    "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
    "360":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best",
}

MP3_BITRATE_MAP = {
    "best": "320", "320": "320", "192": "192", "128": "128", "96": "96",
}

# active download jobs
jobs = {}
jobs_lock = threading.Lock()
job_counter = [0]


# helpers
def new_job_id():
    with jobs_lock:
        job_counter[0] += 1
        jid = str(job_counter[0])
        jobs[jid] = {"status": "queued", "progress": 0, "title": "", "speed": "", "eta": "", "error": ""}
        return jid

def set_job(jid, **kwargs):
    with jobs_lock:
        jobs[jid].update(kwargs)

def make_hooks(jid):
    def progress_hook(d):
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            done  = d.get("downloaded_bytes", 0)
            speed = d.get("speed", 0) or 0
            eta   = d.get("eta", 0) or 0
            pct   = round(done * 100 / total, 1) if total else 0
            spd   = f"{speed/1024:.0f} KB/s" if speed else ""
            eta_s = f"{eta}s" if eta else ""
            set_job(jid, status="downloading", progress=pct, speed=spd, eta=eta_s)
        elif status == "finished":
            set_job(jid, progress=99, speed="", eta="", status="processing")
        elif status == "error":
            set_job(jid, status="error", error="Download error")
    return [progress_hook]


def build_ydl_opts(fmt, quality, jid):
    outtmpl = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
    common = {
        "outtmpl": outtmpl,
        "progress_hooks": make_hooks(jid),
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "retries": 5,
        "fragment_retries": 5,
        "nooverwrites": True,
        "writeinfojson": False,
        "writethumbnail": False,
    }
    if fmt == "mp3":
        bitrate = MP3_BITRATE_MAP.get(str(quality), "192")
        return {
            **common,
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": bitrate},
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ],
            "writethumbnail": True,
        }
    else:
        fmt_str = MP4_QUALITY_MAP.get(str(quality), MP4_QUALITY_MAP["best"])
        return {
            **common,
            "format": fmt_str,
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegMetadata"}],
        }


def run_download(jid, url, fmt, quality):
    try:
        opts = build_ydl_opts(fmt, quality, jid)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown") if info else "Unknown"
            set_job(jid, title=title, status="downloading")
            ydl.download([url])
        set_job(jid, status="done", progress=100, speed="", eta="")
    except Exception as e:
        set_job(jid, status="error", error=str(e))


# routes

@app.route("/")
def index():
    return send_file(BASE_DIR / "index.html")


@app.route("/api/download", methods=["POST"])
def start_download():
    data    = request.json or {}
    url     = (data.get("url") or "").strip()
    fmt     = data.get("format", "mp4").lower()
    quality = data.get("quality", "best")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    jid = new_job_id()
    t = threading.Thread(target=run_download, args=(jid, url, fmt, quality), daemon=True)
    t.start()
    return jsonify({"job_id": jid})


@app.route("/api/status/<jid>")
def job_status(jid):
    with jobs_lock:
        job = jobs.get(jid)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/files")
def list_files():
    files = []
    for f in sorted(DOWNLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in (".mp3", ".mp4", ".webm", ".m4a"):
            size = f.stat().st_size
            files.append({
                "name": f.name,
                "size": size,
                "size_str": fmt_size(size),
                "ext": f.suffix.lstrip(".").upper(),
            })
    return jsonify(files)


@app.route("/api/files/<path:filename>")
def serve_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


@app.route("/api/files/<path:filename>", methods=["DELETE"])
def delete_file(filename):
    target = DOWNLOAD_DIR / filename
    if target.exists() and target.parent == DOWNLOAD_DIR:
        target.unlink()
        return jsonify({"ok": True})
    return jsonify({"error": "File not found"}), 404


def fmt_size(b):
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# launch

if __name__ == "__main__":
    url = "http://localhost:5000"
    print(f"\n YT Downloader running at {url}")
    print(f"Downloads folder: {DOWNLOAD_DIR}")
    print(f"Press Ctrl+C to stop.\n")
    # open browser after short delay
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
