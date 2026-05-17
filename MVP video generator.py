import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from moviepy.editor import AudioFileClip
from moviepy.video.VideoClip import VideoClip
from moviepy.audio.AudioClip import CompositeAudioClip
import requests
import uuid
import logging
import tempfile

logger = logging.getLogger(__name__)

CONFIG = {
    "width": 1080,
    "height": 1080,
    "min_duration": 20,
    "max_duration": 30,
    "fps": 24,
    "background_music": "assets/background_music.mp3",
    "font_bold": "assets/fonts/Poppins-Bold.ttf",
    "font_regular": "assets/fonts/Poppins-Regular.ttf",
    "overlay_bg_color": (0, 0, 0, 160),
    "text_color": (255, 255, 255),
    "tts_lang": "en",
}

def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError):
        return ImageFont.load_default()

def get_image(url_or_path, save_path=None):
    if not url_or_path:
        return None
    if url_or_path.startswith("http"):
        if not save_path:
            save_path = f"temp_image_{uuid.uuid4().hex}.jpg"
        try:
            response = requests.get(url_or_path, stream=True, timeout=10)
            response.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return save_path
        except Exception as e:
            logger.error(f"Failed to download image from {url_or_path}: {e}")
            return None
    elif os.path.exists(url_or_path):
        return url_or_path
    return None

def build_branded_frame(
    photo: Image.Image,
    customer: dict,
    festival_name: str,
    frame_size: tuple[int, int] = (1080, 1080),
) -> Image.Image:
    W, H = frame_size

    # Resize photo to fill the frame (cover)
    ratio = max(W / photo.width, H / photo.height)
    new_size = (int(photo.width * ratio), int(photo.height * ratio))
    photo = photo.resize(new_size, Image.LANCZOS)
    left = (photo.width - W) // 2
    top  = (photo.height - H) // 2
    frame = photo.crop((left, top, left + W, top + H)).convert("RGBA")

    # Bottom branding strip (semi-transparent)
    strip_h = 280
    strip = Image.new("RGBA", (W, strip_h), CONFIG["overlay_bg_color"])
    frame.alpha_composite(strip, dest=(0, H - strip_h))

    # Top festival greeting strip
    top_strip = Image.new("RGBA", (W, 90), (0, 0, 0, 130))
    frame.alpha_composite(top_strip, dest=(0, 0))

    draw = ImageDraw.Draw(frame)
    tc = CONFIG["text_color"]

    font_bold_lg  = load_font(CONFIG["font_bold"],    52)
    font_bold_md  = load_font(CONFIG["font_bold"],    38)
    font_reg      = load_font(CONFIG["font_regular"], 30)
    font_greeting = load_font(CONFIG["font_bold"],    36)

    # Festival greeting (top strip)
    greeting_text = f"🎉 Wishing you a Happy {festival_name}!"
    draw.text((20, 20), greeting_text, font=font_greeting, fill=tc)

    # Branding text (bottom strip)
    bx, by = 20, H - strip_h + 20
    company_name = customer.get("company_name", "Company")
    owner_name = customer.get("owner_name", "Owner")
    whatsapp = customer.get("whatsapp", "")
    address = customer.get("address", "")
    
    draw.text((bx, by),       company_name, font=font_bold_lg,  fill=tc)
    draw.text((bx, by + 65),  f"Owner: {owner_name}", font=font_bold_md, fill=tc)
    draw.text((bx, by + 115), f"📱 {whatsapp}",        font=font_reg,    fill=tc)
    draw.text((bx, by + 155), f"📍 {address}",         font=font_reg,    fill=tc)

    # Company Logo (top-right)
    logo_url_or_path = customer.get("logo_url") or customer.get("logo_path") or ""
    if logo_url_or_path:
        logo_path = get_image(logo_url_or_path, f"temp_logo_{uuid.uuid4().hex}.png")
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo.thumbnail((160, 160), Image.LANCZOS)
                lx = W - logo.width - 20
                frame.alpha_composite(logo, dest=(lx, 10))
            except Exception as e:
                logger.warning(f"Failed to load logo: {e}")
            
            # cleanup temp logo if it was downloaded
            if logo_url_or_path.startswith("http") and os.path.exists(logo_path):
                os.remove(logo_path)
    else:
        # Draw placeholder text logo
        draw.text((W - 200, 15), company_name[:12], font=font_reg, fill=tc)

    return frame.convert("RGB")

def generate_video(customer_data: dict, festival_name: str, photo_index: int):
    try:
        temp_dir = tempfile.mkdtemp(prefix="video_temp_")
        
        photo_key = f"photo{photo_index}"
        photo_url_or_path = customer_data.get(photo_key)

        if not photo_url_or_path:
            logger.error(f"No photo found for index {photo_index}")
            return None

        photo_path = os.path.join(temp_dir, "bg_photo.jpg")
        actual_photo_path = get_image(photo_url_or_path, photo_path)
        
        if not actual_photo_path or not os.path.exists(actual_photo_path):
            logger.error("Failed to retrieve photo.")
            return None

        try:
            photo_img = Image.open(actual_photo_path).convert("RGB")
        except Exception as e:
            logger.error(f"Failed to open image: {e}")
            return None

        W, H = CONFIG["width"], CONFIG["height"]
        fps = CONFIG["fps"]
        duration = 20.0

        # Voiceover
        company_name = customer_data.get("company_name", "Company")
        whatsapp = customer_data.get("whatsapp", "")
        tts_text = f"Greetings from {company_name}! Wishing you a Happy {festival_name}!"
        
        audio_path = os.path.join(temp_dir, "voiceover.mp3")
        try:
            tts = gTTS(text=tts_text, lang=CONFIG["tts_lang"], slow=False)
            tts.save(audio_path)
        except Exception as e:
            logger.warning(f"Failed to generate voiceover: {e}")
            audio_path = None

        branded = build_branded_frame(photo_img, customer_data, festival_name, (W, H))
        branded_np = np.array(branded)

        # Ken-Burns zoom (subtle scale 1.0 -> 1.08 over duration)
        def make_frame(t: float) -> np.ndarray:
            progress = t / duration
            scale    = 1.0 + 0.08 * progress        # gentle zoom-in
            new_w    = int(W * scale)
            new_h    = int(H * scale)
            resized  = cv2.resize(branded_np, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            x0 = (new_w - W) // 2
            y0 = (new_h - H) // 2
            return resized[y0:y0+H, x0:x0+W]

        video_clip = VideoClip(make_frame, duration=duration)
        video_clip = video_clip.set_fps(fps)

        # Audio
        audio_clips = []
        bg_music_path = CONFIG.get("background_music")
        if bg_music_path and os.path.exists(bg_music_path):
            try:
                bg = AudioFileClip(bg_music_path).subclip(0, duration).volumex(0.3)
                audio_clips.append(bg)
            except Exception as e:
                logger.warning(f"Failed to load background music: {e}")

        if audio_path and os.path.exists(audio_path):
            try:
                vo_clip = AudioFileClip(audio_path).volumex(1.0)
                vo_clip = vo_clip.set_start(1.0)
                audio_clips.append(vo_clip)
            except Exception as e:
                logger.warning(f"Failed to load voiceover audio: {e}")

        if audio_clips:
            mixed_audio = CompositeAudioClip(audio_clips).set_duration(duration)
            video_clip  = video_clip.set_audio(mixed_audio)

        output_video_path = f"output_{uuid.uuid4().hex}.mp4"
        video_clip.write_videofile(
            output_video_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None,
        )

        return output_video_path

    except Exception as e:
        logger.error(f"Error generating video: {e}")
        return None

def get_next_photo_index(last_used: int) -> int:
    next_idx = last_used + 1
    if next_idx > 10:
        next_idx = 1
    return next_idx
