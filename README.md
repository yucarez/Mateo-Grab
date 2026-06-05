# MateoGrab

Local YouTube downloader. Runs a Flask server that serves a web UI and uses yt-dlp to download videos/audio.

## Requirements

- Python 3.7+
- FFmpeg

```bash
pip install flask yt-dlp
```

## Usage

```bash
python server.py
```

Opens `http://localhost:5000` automatically. Downloads are saved to the `downloads/` folder.

## Files

```
server.py            # Flask backend
index.html           # Web UI
Open MateoGrab.html  # Shortcut that redirects to localhost:5000
```
