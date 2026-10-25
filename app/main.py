import asyncio
import re
import shutil
import subprocess
import textwrap
import uuid
from pathlib import Path

import edge_tts
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)
STATIC.mkdir(exist_ok=True)
app = FastAPI(title="ClipForge AI", version="0.2.0")
JOBS = {}
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

DEFAULT_VOICE = "en-IN-NeerjaNeural"

class RenderRequest(BaseModel):
    title: str = Field(default="My ClipForge Video", max_length=100)
    script: str = Field(min_length=20, max_length=12000)
    voice: str = "en-IN-NeerjaNeural"
    format: str = "9:16"
    quality: str = "1080p"

def split_scenes(script: str):
    parts = re.split(r"(?<=[.!?])\s+|\n+", script.strip())
    parts = [p.strip() for p in parts if p.strip()]
    scenes, current = [], ""
    for part in parts:
        if len(current) + len(part) > 180 and current:
            scenes.append(current)
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        scenes.append(current)
    return scenes[:40]

def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()

def make_card(path: Path, title: str, caption: str, index: int, total: int, dimensions):
    w, h = dimensions
    image = Image.new("RGB", (w, h), (12, 18, 38))
    pixels = image.load()
    for y in range(h):
        for x in range(0, w, 4):
            t = (x / max(1, w) + y / max(1, h)) / 2
            c = (int(18 + 35*t), int(25 + 12*t), int(58 + 95*t))
            for xx in range(x, min(x+4, w)):
                pixels[xx, y] = c
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((int(w*.58), int(h*.08), int(w*1.05), int(h*.40)), fill=(118, 83, 255, 55))
    draw.rounded_rectangle((int(w*.08), int(h*.12), int(w*.92), int(h*.88)), radius=28, outline=(255,255,255,45), width=2)
    draw.text((int(w*.12), int(h*.17)), "CLIPFORGE / AI STORY", font=font(max(18, int(w*.025)), True), fill=(180, 190, 255, 255))
    max_chars = 22 if h > w else 34
    wrapped = textwrap.wrap(caption, width=max_chars)
    size = max(26, int(w*.052))
    f = font(size, True)
    while size > 20 and len(wrapped) * (size * 1.35) > h*.38:
        size -= 2
        f = font(size, True)
    line_h = int(size * 1.35)
    y = int(h*.36)
    for line in wrapped[:7]:
        draw.text((int(w*.12), y), line, font=f, fill=(255,255,255,255), stroke_width=1, stroke_fill=(10,10,30,180))
        y += line_h
    draw.text((int(w*.12), int(h*.78)), title[:70], font=font(max(16,int(w*.023))), fill=(210,218,245,255))
    draw.text((int(w*.12), int(h*.83)), f"SCENE {index:02d} / {total:02d}", font=font(max(14,int(w*.018)), True), fill=(170,180,220,255))
    image.save(path, quality=92)

def run_cmd(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-1800:] or "Media processing failed")

async def build_video(job: str, req: RenderRequest):
    ffmpeg = shutil.which("ffmpeg")
    probe = shutil.which("ffprobe")
    if not ffmpeg or not probe:
        raise RuntimeError("FFmpeg and FFprobe are required. Use the provided Dockerfile.")
    scenes = split_scenes(req.script)
    if not scenes:
        raise ValueError("Please enter a script with some sentences.")
    base_dims = {"9:16": (1080,1920), "1:1": (1080,1080), "16:9": (1920,1080)}.get(req.format)
    if not base_dims:
        raise ValueError("Choose 9:16, 1:1 or 16:9.")
    scales = {"720p": 2/3, "1080p": 1.0, "4K": 2.0}
    if req.quality not in scales:
        raise ValueError("Choose 720p, 1080p or 4K quality.")
    dims = tuple(max(2, int(v * scales[req.quality] // 2 * 2)) for v in base_dims)
    folder = OUTPUTS / job
    folder.mkdir(parents=True, exist_ok=True)
    audio, srt, mp4 = folder / "narration.mp3", folder / "captions.srt", folder / "clipforge-video.mp4"
    state = JOBS[job]
    state.update({"status": "running", "stage": "Generating narration", "progress": 5, "total_scenes": len(scenes), "current_scene": 0})
    voice = req.voice if re.fullmatch(r"[a-z]{2,3}-[A-Z]{2,4}-[A-Za-z0-9]+Neural", req.voice or "") else DEFAULT_VOICE
    await edge_tts.Communicate(req.script, voice).save(str(audio))
    result = await asyncio.to_thread(subprocess.run, [probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio)], capture_output=True, text=True)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("Could not determine narration duration.")
    duration = max(3.0, float(result.stdout.strip()))
    per_scene = duration / len(scenes)
    cards = []
    state.update({"stage": "Designing scene previews", "progress": 15})
    for i, scene in enumerate(scenes, 1):
        card = folder / f"scene-{i:03d}.png"
        await asyncio.to_thread(make_card, card, req.title, scene, i, len(scenes), dims)
        cards.append(card)
        state.update({
            "stage": f"Building scene {i} of {len(scenes)}",
            "progress": min(70, 15 + int(55 * i / len(scenes))),
            "current_scene": i,
            "preview_url": f"/api/jobs/{job}/preview/{i}",
            "scene_caption": scene[:240],
        })
    state.update({"stage": "Assembling MP4 and audio", "progress": 75})
    concat = folder / "concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for card in cards:
            f.write(f"file '{card.as_posix()}'\n")
            f.write(f"duration {per_scene:.4f}\n")
        f.write(f"file '{cards[-1].as_posix()}'\n")
    await asyncio.to_thread(run_cmd, [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(audio),
             "-vf", "format=yuv420p", "-r", "25", "-c:v", "libx264", "-preset", "veryfast",
             "-t", f"{duration:.3f}", "-c:a", "aac", "-b:a", "160k", "-shortest", str(mp4)])
    state.update({"stage": "Creating captions", "progress": 92})
    total_chars = max(1, sum(len(s) for s in scenes))
    elapsed = 0.0
    def stamp(sec):
        ms = int(sec * 1000)
        hh, ms = divmod(ms, 3600000)
        mm, ms = divmod(ms, 60000)
        ss, ms = divmod(ms, 1000)
        return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"
    with srt.open("w", encoding="utf-8") as f:
        for i, scene in enumerate(scenes, 1):
            span = duration * len(scene) / total_chars
            start, end = elapsed, min(duration, elapsed + span)
            f.write(f"{i}\n{stamp(start)} --> {stamp(end)}\n{scene}\n\n")
            elapsed = end
    return mp4, srt, duration, len(scenes)

async def run_generation(job: str, req: RenderRequest):
    try:
        mp4, srt, duration, count = await build_video(job, req)
        JOBS[job].update({
            "status": "completed", "stage": "Video ready", "progress": 100,
            "duration_seconds": round(duration, 1), "scene_count": count,
            "quality": req.quality, "video_url": f"/api/download/{job}/video",
            "captions_url": f"/api/download/{job}/captions",
        })
    except Exception as exc:
        JOBS[job].update({"status": "failed", "stage": "Generation failed", "error": str(exc)[:1000]})

@app.get("/", response_class=HTMLResponse)
async def home():
    index = STATIC / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>ClipForge AI</h1><p>Frontend is being set up.</p>")
    return HTMLResponse(index.read_text(encoding="utf-8"))

@app.get("/api/voices")
async def voices():
    """Return all voices currently available from Edge TTS, covering many supported languages."""
    try:
        catalogue = await edge_tts.list_voices()
        return sorted([{"id": v["ShortName"], "label": f'{v.get("FriendlyName", v["ShortName"])} · {v.get("Locale", "Unknown locale")} · {v.get("Gender", "Voice")}' , "locale": v.get("Locale", "und")} for v in catalogue], key=lambda v: (v["locale"], v["label"]))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not load voice catalogue: {str(exc)[:200]}")

@app.post("/api/generate")
async def generate(req: RenderRequest):
    job = uuid.uuid4().hex[:12]
    JOBS[job] = {"job_id": job, "status": "queued", "stage": "Queued", "progress": 0,
                 "current_scene": 0, "total_scenes": 0, "preview_url": None, "scene_caption": ""}
    asyncio.create_task(run_generation(job, req))
    return {"job_id": job, "status_url": f"/api/jobs/{job}"}

@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id) or job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found. Jobs are kept in memory while this server process is running.")
    return JOBS[job_id]

@app.get("/api/jobs/{job_id}/preview/{scene_index}")
async def scene_preview(job_id: str, scene_index: int):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id) or job_id not in JOBS or scene_index < 1:
        raise HTTPException(status_code=404, detail="Preview not found")
    target = OUTPUTS / job_id / f"scene-{scene_index:03d}.png"
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Scene preview is not ready yet")
    return FileResponse(target, media_type="image/png", headers={"Cache-Control": "no-store"})

@app.get("/api/download/{job_id}/{kind}")
async def download(job_id: str, kind: str):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        raise HTTPException(status_code=404, detail="File not found")
    folder = OUTPUTS / job_id
    target = folder / ("clipforge-video.mp4" if kind == "video" else "captions.srt" if kind == "captions" else "missing")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target, filename=target.name)
