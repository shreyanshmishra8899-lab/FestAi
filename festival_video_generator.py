"""
Festival Video Generation System
=================================
Automatically generates 1080x1080 promotional videos for festivals,
combining company branding, festival photos, background music, and voiceovers.

Requirements:
    pip install moviepy opencv-python pillow gtts apscheduler google-api-python-client google-auth-httplib2 google-auth-oauthlib requests

Usage:
    python festival_video_generator.py
"""

import os
import json
import random
import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# ── Scheduling ────────────────────────────────────────────────────────────────
from apscheduler.schedulers.blocking import BlockingScheduler

# ── Video / Image ─────────────────────────────────────────────────────────────
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip, ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip
)
from moviepy.audio.AudioClip import CompositeAudioClip

# ── TTS ───────────────────────────────────────────────────────────────────────
from gtts import gTTS

# ── Google Drive ──────────────────────────────────────────────────────────────
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
import io

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION  – edit these values for your deployment
# ─────────────────────────────────────────────────────────────────────────────

CONFIG = {
    # Output video dimensions & duration
    "width": 1080,
    "height": 1080,
    "min_duration": 20,   # seconds
    "max_duration": 30,   # seconds
    "fps": 30,

    # Google Drive
    "service_account_file": "service_account.json",   # path to your SA key
    "drive_folder_id": "YOUR_GOOGLE_DRIVE_FOLDER_ID", # folder with company photos

    # Background music file (local .mp3 / .wav)
    "background_music": "assets/background_music.mp3",

    # Font paths (TTF) – fall back to PIL default if not found
    "font_bold": "assets/fonts/Poppins-Bold.ttf",
    "font_regular": "assets/fonts/Poppins-Regular.ttf",

    # Branding overlay colours
    "overlay_bg_color": (0, 0, 0, 160),   # RGBA – semi-transparent black
    "text_color": (255, 255, 255),

    # Output directory
    "output_dir": "output_videos",

    # TTS language
    "tts_lang": "en",
}

# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE DATA  – replace / extend with your real data source
# ─────────────────────────────────────────────────────────────────────────────

FESTIVALS = [
    {"name": "Diwali",        "date": "2024-11-01", "greeting": "Wishing you a bright and joyful Diwali!"},
    {"name": "Holi",          "date": "2024-03-25", "greeting": "May your life be as colourful as Holi!"},
    {"name": "Eid",           "date": "2024-04-10", "greeting": "Eid Mubarak! Peace and blessings to you."},
    {"name": "Christmas",     "date": "2024-12-25", "greeting": "Merry Christmas and a Happy New Year!"},
    {"name": "New Year",      "date": "2025-01-01", "greeting": "Happy New Year! Wishing you success ahead."},
]

CUSTOMERS = [
    {
        "id": "C001",
        "active": True,
        "company_name": "Sharma Traders",
        "owner_name": "Ramesh Sharma",
        "whatsapp": "+91 98765 43210",
        "address": "12, MG Road, Sagar, MP",
        "logo_path": "assets/logos/sharma_traders.png",
        "festival_photos": {},          # populated by photo logic
        "last_used_photo": None,
    },
    {
        "id": "C002",
        "active": True,
        "company_name": "Patel Enterprises",
        "owner_name": "Suresh Patel",
        "whatsapp": "+91 87654 32109",
        "address": "45, Station Road, Bhopal, MP",
        "logo_path": "assets/logos/patel_enterprises.png",
        "festival_photos": {},
        "last_used_photo": None,
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("FestivalVideo")

# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE DRIVE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_drive_service():
    """Authenticate with a service-account and return a Drive API client."""
    creds = service_account.Credentials.from_service_account_file(
        CONFIG["service_account_file"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def list_drive_photos(service, folder_id: str) -> list[dict]:
    """Return all image files in a Drive folder."""
    query = (
        f"'{folder_id}' in parents "
        "and mimeType contains 'image/' "
        "and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])


def download_drive_photo(service, file_id: str) -> Image.Image:
    """Download a Drive file and return a PIL Image."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return Image.open(buf).convert("RGB")

# ─────────────────────────────────────────────────────────────────────────────
# PHOTO SELECTION  (no consecutive repeat)
# ─────────────────────────────────────────────────────────────────────────────

def pick_photo(customer: dict, available_photos: list[dict]) -> dict:
    """
    Choose a photo for this customer, ensuring it differs from the last one used.
    """
    if not available_photos:
        raise ValueError("No photos available in Drive folder.")

    last = customer.get("last_used_photo")
    candidates = [p for p in available_photos if p["id"] != last]

    # If only one photo exists, allow reuse (unavoidable)
    chosen = random.choice(candidates) if candidates else random.choice(available_photos)
    customer["last_used_photo"] = chosen["id"]
    return chosen

# ─────────────────────────────────────────────────────────────────────────────
# TEXT-TO-SPEECH
# ─────────────────────────────────────────────────────────────────────────────

def generate_voiceover(text: str, output_path: str) -> str:
    """Generate a gTTS voiceover MP3 and return the file path."""
    tts = gTTS(text=text, lang=CONFIG["tts_lang"], slow=False)
    tts.save(output_path)
    log.info("Voiceover saved: %s", output_path)
    return output_path

# ─────────────────────────────────────────────────────────────────────────────
# IMAGE OVERLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError):
        log.warning("Font not found at %s – using PIL default.", path)
        return ImageFont.load_default()


def build_branded_frame(
    photo: Image.Image,
    customer: dict,
    festival: dict,
    frame_size: tuple[int, int] = (1080, 1080),
) -> Image.Image:
    """
    Compose a single 1080×1080 branded frame:
      - festival photo (background, cropped/resized)
      - semi-transparent branding strip at the bottom
      - Company Name, Owner Name, WhatsApp, Address
      - Company Logo (top-right corner)
      - Festival greeting (top-left)
    """
    W, H = frame_size

    # 1. Resize photo to fill the frame (cover)
    ratio = max(W / photo.width, H / photo.height)
    new_size = (int(photo.width * ratio), int(photo.height * ratio))
    photo = photo.resize(new_size, Image.LANCZOS)
    left = (photo.width - W) // 2
    top  = (photo.height - H) // 2
    frame = photo.crop((left, top, left + W, top + H)).convert("RGBA")

    draw = ImageDraw.Draw(frame)

    # 2. Bottom branding strip (semi-transparent)
    strip_h = 280
    strip = Image.new("RGBA", (W, strip_h), CONFIG["overlay_bg_color"])
    frame.alpha_composite(strip, dest=(0, H - strip_h))

    # 3. Top festival greeting strip
    top_strip = Image.new("RGBA", (W, 90), (0, 0, 0, 130))
    frame.alpha_composite(top_strip, dest=(0, 0))

    draw = ImageDraw.Draw(frame)
    tc = CONFIG["text_color"]

    font_bold_lg  = load_font(CONFIG["font_bold"],    52)
    font_bold_md  = load_font(CONFIG["font_bold"],    38)
    font_reg      = load_font(CONFIG["font_regular"], 30)
    font_greeting = load_font(CONFIG["font_bold"],    36)

    # Festival greeting (top strip)
    draw.text((20, 20), f"🎉 {festival['greeting']}", font=font_greeting, fill=tc)

    # Branding text (bottom strip)
    bx, by = 20, H - strip_h + 20
    draw.text((bx, by),       customer["company_name"], font=font_bold_lg,  fill=tc)
    draw.text((bx, by + 65),  f"Owner: {customer['owner_name']}", font=font_bold_md, fill=tc)
    draw.text((bx, by + 115), f"📱 {customer['whatsapp']}",        font=font_reg,    fill=tc)
    draw.text((bx, by + 155), f"📍 {customer['address']}",         font=font_reg,    fill=tc)

    # 4. Company Logo (top-right)
    logo_path = customer.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((160, 160), Image.LANCZOS)
        lx = W - logo.width - 20
        frame.alpha_composite(logo, dest=(lx, 10))
    else:
        # Draw placeholder text logo
        draw.text((W - 200, 15), customer["company_name"][:12], font=font_reg, fill=tc)

    return frame.convert("RGB")

# ─────────────────────────────────────────────────────────────────────────────
# VIDEO ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def create_video(
    customer: dict,
    festival: dict,
    photo_img: Image.Image,
    output_path: str,
    duration: int = 25,
) -> str:
    """
    Build the final MP4:
      - Ken-Burns animated image clip (zoom effect)
      - Branding overlay baked into frames
      - Background music + gTTS voiceover mixed together
    """
    W, H = CONFIG["width"], CONFIG["height"]
    fps   = CONFIG["fps"]

    with tempfile.TemporaryDirectory() as tmp:

        # ── 1. Generate voiceover ────────────────────────────────────────────
        tts_text = (
            f"Happy {festival['name']} from {customer['company_name']}! "
            f"{festival['greeting']} "
            f"Contact us at {customer['whatsapp']}."
        )
        vo_path = os.path.join(tmp, "voiceover.mp3")
        generate_voiceover(tts_text, vo_path)

        # ── 2. Build branded PIL frame ────────────────────────────────────────
        branded = build_branded_frame(photo_img, customer, festival, (W, H))
        branded_np = np.array(branded)   # (H, W, 3) uint8

        # ── 3. Ken-Burns zoom (subtle scale 1.0 → 1.08 over duration) ────────
        def make_frame(t: float) -> np.ndarray:
            progress = t / duration
            scale    = 1.0 + 0.08 * progress        # gentle zoom-in
            new_w    = int(W * scale)
            new_h    = int(H * scale)
            resized  = cv2.resize(branded_np, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            x0 = (new_w - W) // 2
            y0 = (new_h - H) // 2
            return resized[y0:y0+H, x0:x0+W]

        video_clip = VideoFileClip.__new__(VideoFileClip)   # avoid normal __init__
        from moviepy.video.VideoClip import VideoClip
        video_clip = VideoClip(make_frame, duration=duration)
        video_clip = video_clip.set_fps(fps)

        # ── 4. Audio: mix background music + voiceover ────────────────────────
        audio_clips = []

        bg_music_path = CONFIG.get("background_music")
        if bg_music_path and os.path.exists(bg_music_path):
            bg = AudioFileClip(bg_music_path).subclip(0, duration).volumex(0.3)
            audio_clips.append(bg)

        vo_clip = AudioFileClip(vo_path).volumex(1.0)
        # Start voiceover 1 s in
        vo_clip = vo_clip.set_start(1.0)
        audio_clips.append(vo_clip)

        if audio_clips:
            mixed_audio = CompositeAudioClip(audio_clips).set_duration(duration)
            video_clip  = video_clip.set_audio(mixed_audio)

        # ── 5. Write output ───────────────────────────────────────────────────
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        video_clip.write_videofile(
            output_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None,
        )
        log.info("Video saved → %s", output_path)

    return output_path

# ─────────────────────────────────────────────────────────────────────────────
# FESTIVAL LOOKUP
# ─────────────────────────────────────────────────────────────────────────────

def get_tomorrow_festivals() -> list[dict]:
    """Return festivals whose date matches tomorrow."""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return [f for f in FESTIVALS if f["date"] == tomorrow]

# ─────────────────────────────────────────────────────────────────────────────
# MAIN JOB
# ─────────────────────────────────────────────────────────────────────────────

def generate_festival_videos():
    """
    Core job invoked daily at midnight:
      1. Find festivals tomorrow.
      2. For each active customer × festival, pick a non-repeat photo,
         build the branded video, and save it.
    """
    log.info("=== Festival Video Job Started ===")
    festivals = get_tomorrow_festivals()

    if not festivals:
        log.info("No festivals tomorrow. Skipping.")
        return

    log.info("Festivals tomorrow: %s", [f["name"] for f in festivals])

    # Connect to Google Drive
    try:
        drive_svc = get_drive_service()
        all_photos = list_drive_photos(drive_svc, CONFIG["drive_folder_id"])
        log.info("Found %d photos in Drive.", len(all_photos))
    except Exception as exc:
        log.error("Drive error: %s – using placeholder image.", exc)
        drive_svc  = None
        all_photos = []

    for customer in CUSTOMERS:
        if not customer.get("active"):
            continue

        for festival in festivals:
            log.info(
                "Generating: %s × %s", customer["company_name"], festival["name"]
            )
            try:
                # ── Photo selection ──────────────────────────────────────────
                if all_photos and drive_svc:
                    chosen_meta  = pick_photo(customer, all_photos)
                    photo_img    = download_drive_photo(drive_svc, chosen_meta["id"])
                else:
                    # Fallback: solid colour placeholder
                    photo_img = Image.new("RGB", (1080, 1080), (30, 60, 120))

                # ── Duration: random in configured range ─────────────────────
                duration = random.randint(
                    CONFIG["min_duration"], CONFIG["max_duration"]
                )

                # ── Output path ──────────────────────────────────────────────
                date_str  = datetime.now().strftime("%Y%m%d")
                safe_name = customer["company_name"].replace(" ", "_")
                filename  = f"{date_str}_{safe_name}_{festival['name']}.mp4"
                out_path  = os.path.join(CONFIG["output_dir"], filename)

                create_video(customer, festival, photo_img, out_path, duration)

            except Exception as exc:
                log.exception(
                    "Failed for %s / %s: %s",
                    customer["company_name"], festival["name"], exc
                )

    log.info("=== Festival Video Job Complete ===")

# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER  – runs daily at midnight
# ─────────────────────────────────────────────────────────────────────────────

def start_scheduler():
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        generate_festival_videos,
        trigger="cron",
        hour=0,
        minute=0,
        id="festival_video_job",
    )
    log.info("Scheduler started – job runs daily at midnight IST.")
    log.info("Press Ctrl+C to stop.")

    # Run immediately on startup so you can test without waiting for midnight
    generate_festival_videos()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_scheduler()
