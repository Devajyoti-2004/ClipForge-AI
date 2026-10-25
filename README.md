# ClipForge AI

An open-source starter for generating faceless videos from a script. Built with FastAPI, Edge TTS, Pillow and FFmpeg.

## Features
- Script-to-video slideshow with automatically split scenes
- Text-to-speech narration
- Vertical 9:16, square 1:1 and landscape 16:9 exports
- Selectable 720p, 1080p and 4K render resolutions (4K is resource-intensive)
- Dynamic voice list from the Edge TTS catalogue, covering many supported languages and locales
- Automatic SRT captions
- Downloadable MP4 and SRT files
- Responsive web interface
- Docker/Railway-ready deployment
- Optional GitHub Actions deployment to Railway whenever code is pushed to `main`

This MVP follows the user-provided script and creates designed scene cards plus narration; it does not invent a script or generate photorealistic AI footage by itself. For cinematic AI video clips or licensed stock footage, connect a video-generation/stock provider and configure its API key. The voice list covers languages exposed by Edge TTS, not every language spoken worldwide. The app does not impose a per-video credit counter, but hosting, storage, provider, and compute limits still apply; “unlimited” processing cannot be guaranteed on a free host. 4K and long-video rendering can exceed free-host memory, CPU, or request limits.

## Gemini AI cinematic scene mode

The web app has two visual modes:
- **Fast scene cards**: the original local slideshow renderer.
- **Gemini AI animated scenes**: sends each script excerpt to Google's Gemini Omni Flash video-generation model and assembles the generated MP4 clips with the narration. The app shows per-scene progress, retries a failed scene once, and exposes a frame preview when available.

### Configure the Gemini API key on Render

1. Create or copy an API key at [Google AI Studio API keys](https://aistudio.google.com/api-keys).
2. Open the Render dashboard and select the ClipForge AI web service.
3. Open **Environment** and add a variable named `GEMINI_API_KEY`; paste the key as its value.
4. Save the changes and redeploy the service.
5. Open ClipForge AI, choose **Gemini AI animated scenes**, then generate a short test script first.

Never commit the API key to GitHub, include it in frontend JavaScript, or share it in screenshots or public logs. If a key is exposed, revoke it and create another. The key is read only by the backend from the environment.

Gemini video generation consumes provider quota and may incur charges depending on the account and current Google terms. Use short test scripts first. Each scene is a separate generation request, and retries can also consume quota. Character descriptions are repeated between scenes to encourage visual continuity, but identical character appearance is not guaranteed. This mode currently generates video clips from text prompts; it does not yet create uploaded character-reference sheets or use the previous scene's final frame as a reference. Generated files are stored on the service filesystem and may disappear after an ephemeral-host restart.

## Run locally
Requirements: Python 3.11+, FFmpeg installed and available on PATH.

    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Open http://127.0.0.1:8000.

## Deploy to Railway manually
1. Create a Railway project and service from this GitHub repository.
2. Railway detects the Dockerfile and builds the app.
3. Deploy and generate a public domain for the service.
4. The app binds to Railway's `PORT` environment variable. FFmpeg is included in the container.

## Automatic deployment using GitHub Actions
The workflow `.github/workflows/deploy-railway.yml` deploys to Railway on every push to `main` and can also be started manually from the GitHub Actions tab.

Configure these in GitHub repository **Settings → Secrets and variables → Actions**:

**Repository secret**
- `RAILWAY_TOKEN`: a Railway **project token** for the target environment. Keep this secret; do not commit it into the repository.

**Repository variables**
- `RAILWAY_PROJECT_ID`: the Railway project ID.
- `RAILWAY_ENVIRONMENT`: the target environment name or ID (usually `production`).
- `RAILWAY_SERVICE`: optional; set the exact Railway service name or ID if the project has multiple services. Leave unset for a single-service project.

Once those values are saved, push a commit to `main` or run the workflow manually from **Actions → Deploy to Railway → Run workflow**. Check the workflow run logs if the deployment fails.

Generated videos are stored in `outputs/` and may be cleared on ephemeral hosting restarts. Edge TTS requires an internet connection. Review usage rights before publishing any content.
