# MateoGrab

Local mp3/mp4 downloader. Runs a Flask server that serves a web UI and uses yt-dlp to download videos/audios.

## Requirements

- Python 3.7+
- FFmpeg (must be on your PATH)

```bash
pip install flask yt-dlp
```

## Usage

Double-click `MateoGrab.bat`. It starts the server and opens the app in your browser automatically. Downloads are saved to the `downloads/` folder.

## Files

```
server.py       # Flask backend
index.html      # Web UI
MateoGrab.bat   # Launcher (Windows)
downloads/      # Output folder
```
