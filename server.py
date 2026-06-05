import os
import sys
import tempfile
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

try:
    import yt_dlp
except ImportError:
    print("yt-dlp not found. Install it with: pip install yt-dlp")
    sys.exit(1)

app = Flask(__name__)
CORS(app)

# config
COOKIES_FILE = Path("/etc/secrets/cookies.txt")

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

# routes
@app.route("/")
def index():
    return jsonify({"status": "MateoGrab backend is running"})

@app.route("/api/download", methods=["POST"])
def download():
    data    = request.json or {}
    url     = (data.get("url") or "").strip()
    fmt     = data.get("format", "mp4").lower()
    quality = data.get("quality", "best")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = str(Path(tmpdir) / "%(title)s.%(ext)s")

            if fmt == "mp3":
                bitrate = MP3_BITRATE_MAP.get(str(quality), "192")
                ydl_opts = {
                    "outtmpl": outtmpl,
                    "format": "bestaudio/best",
                    "quiet": True,
                    "no_warnings": True,
                    "cookiefile": str(COOKIES_FILE) if COOKIES_FILE.exists() else None,
                    "postprocessors": [
                        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": bitrate},
                        {"key": "FFmpegMetadata"},
                    ],
                }
            else:
                fmt_str = MP4_QUALITY_MAP.get(str(quality), MP4_QUALITY_MAP["best"])
                ydl_opts = {
                    "outtmpl": outtmpl,
                    "format": fmt_str,
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "no_warnings": True,
                    "cookiefile": str(COOKIES_FILE) if COOKIES_FILE.exists() else None,
                    "postprocessors": [{"key": "FFmpegMetadata"}],
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # find output file
            files = list(Path(tmpdir).iterdir())
            if not files:
                return jsonify({"error": "Download produced no output"}), 500

            out_file = files[0]
            mime = "audio/mpeg" if fmt == "mp3" else "video/mp4"

            # read into memory before temp dir is cleaned up
            data_bytes = out_file.read_bytes()
            filename   = out_file.name

        return Response(
            data_bytes,
            mimetype=mime,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(data_bytes)),
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# launch
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
