# ClipForge AI

An open-source starter for generating faceless videos from a script. Built with FastAPI, Edge TTS, Pillow and FFmpeg.

## Features
- Script-to-video slideshow with automatically split scenes
- Text-to-speech narration
- Vertical 9:16, square 1:1 and landscape 16:9 exports
- Automatic SRT captions
- Downloadable MP4 and SRT files
- Responsive web interface
- Docker/Railway-ready deployment

This MVP creates designed scene cards from your script. It does not generate photorealistic AI footage by itself. For AI video clips or licensed stock footage, connect a video-generation/stock provider and configure its API key.

## Run locally
Requirements: Python 3.11+, FFmpeg installed and available on PATH.

    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Open http://127.0.0.1:8000.

## Deploy to Railway
1. Create a Railway project from this GitHub repository.
2. Railway detects the Dockerfile and builds the app.
3. Deploy. The app binds to Railway's PORT environment variable.
4. FFmpeg is included in the container.

Generated videos are stored in outputs/ and may be cleared on ephemeral hosting restarts. Edge TTS requires an internet connection. Review usage rights before publishing any content.