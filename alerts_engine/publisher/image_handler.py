"""
Image Handler — Generates AI featured images via Gemini and
compresses them to WebP under 100KB for SEO + hosting efficiency.
Food photography focused.
"""
import logging
import io
import os
import re
from datetime import datetime

from PIL import Image

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from writer.seo_prompt import build_image_prompt
from gemini_client import generate_content_with_fallback, generate_image_with_fallback, generate_image_with_gemini_flash

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024
TARGET_WIDTH = 1200
TARGET_HEIGHT = 630


def _compress_to_webp(image_path_or_bytes, output_path, max_size=MAX_FILE_SIZE):
    """Compress an image to WebP format under the target file size."""
    try:
        if isinstance(image_path_or_bytes, Image.Image):
            img = image_path_or_bytes
        elif isinstance(image_path_or_bytes, bytes):
            img = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            img = Image.open(image_path_or_bytes)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img = _resize_and_crop(img, TARGET_WIDTH, TARGET_HEIGHT)

        if not output_path.lower().endswith(".webp"):
            output_path = os.path.splitext(output_path)[0] + ".webp"

        quality = 85
        while quality >= 10:
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=quality, method=6)
            size = buffer.tell()
            if size <= max_size:
                with open(output_path, "wb") as f:
                    f.write(buffer.getvalue())
                logger.info(f"    Compressed to WebP: {size/1024:.1f}KB (quality={quality})")
                return output_path
            quality -= 5

        img = img.resize((800, 420), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=10, method=6)
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())
        return output_path

    except Exception as e:
        logger.error(f"    WebP compression error: {e}")
        return None


def _compress_to_jpg(image_path_or_bytes, output_path, max_size=MAX_FILE_SIZE):
    """Compress an image to JPEG format under the target file size."""
    try:
        if isinstance(image_path_or_bytes, Image.Image):
            img = image_path_or_bytes
        elif isinstance(image_path_or_bytes, bytes):
            img = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            img = Image.open(image_path_or_bytes)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img = _resize_and_crop(img, TARGET_WIDTH, TARGET_HEIGHT)

        if not output_path.lower().endswith((".jpg", ".jpeg")):
            output_path = os.path.splitext(output_path)[0] + ".jpg"

        quality = 85
        while quality >= 10:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            size = buffer.tell()
            if size <= max_size:
                with open(output_path, "wb") as f:
                    f.write(buffer.getvalue())
                return output_path
            quality -= 5

        img = img.resize((800, 420), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=15, optimize=True)
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())
        return output_path

    except Exception as e:
        logger.error(f"    JPEG compression error: {e}")
        return None


def _resize_and_crop(img, target_w, target_h):
    """Resize image to fill target dimensions, then center-crop."""
    w_ratio = target_w / img.width
    h_ratio = target_h / img.height
    scale = max(w_ratio, h_ratio)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))
    return img


def _try_gemini_imagen(article_title, output_path_webp, output_path_jpg):
    """Try to generate image using Gemini Imagen 3."""
    try:
        prompt = build_image_prompt(article_title)
        from google.genai import types
        response = generate_image_with_fallback(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            generation_config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="16:9",
            )
        )
        if response and getattr(response, "generated_images", None):
            image_bytes = response.generated_images[0].image.image_bytes
            if isinstance(image_bytes, bytes) and len(image_bytes) > 100:
                result_webp = _compress_to_webp(image_bytes, output_path_webp)
                result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
                if result_webp and result_jpg:
                    logger.info("    Images ready from Gemini Imagen 3")
                    return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    Gemini Imagen failed: {e}")
    return None, None


def _try_gemini_flash_image(article_title, output_path_webp, output_path_jpg):
    """Try Gemini 2.5 Flash Image (free tier)."""
    try:
        prompt = build_image_prompt(article_title)
        response = generate_image_with_gemini_flash(prompt)
        if not response or not getattr(response, "candidates", None):
            return None, None
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                image_bytes = part.inline_data.data
                if isinstance(image_bytes, bytes) and len(image_bytes) > 100:
                    result_webp = _compress_to_webp(image_bytes, output_path_webp)
                    result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
                    if result_webp and result_jpg:
                        logger.info(f"    Images ready from Gemini Flash Image")
                        return result_webp, result_jpg
                break
    except Exception as e:
        logger.warning(f"    Gemini Flash Image failed: {e}")
    return None, None


def _try_source_image(source_url, output_path_webp, output_path_jpg):
    """Try to use the featured image from the source article."""
    if not source_url or not source_url.startswith("http") or "trends.google" in source_url:
        return None, None
    try:
        import requests
        from urllib.parse import urljoin
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ElMordjeneAgent/1.0)"}
        r = requests.get(source_url, headers=headers, timeout=12)
        r.raise_for_status()
        html = r.text
        image_url = None

        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            image_url = m.group(1).strip()
        if not image_url:
            m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
            if m:
                image_url = m.group(1).strip()
        if not image_url:
            for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', html, re.I):
                src = m.group(1).strip()
                if "logo" in src.lower() or "avatar" in src.lower() or "icon" in src.lower():
                    continue
                image_url = src
                break

        if not image_url:
            return None, None

        image_url = urljoin(source_url, image_url)
        img_r = requests.get(image_url, headers=headers, timeout=12)
        img_r.raise_for_status()
        image_bytes = img_r.content

        if len(image_bytes) < 3000:
            return None, None

        result_webp = _compress_to_webp(image_bytes, output_path_webp)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
        if result_webp and result_jpg:
            logger.info(f"    Image from source article")
            return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    Source image failed: {e}")
    return None, None


def _try_pollinations_image(article_title, output_path_webp, output_path_jpg):
    """Try to generate image via free Pollinations.ai."""
    import urllib.request
    import urllib.parse
    import time
    try:
        logger.info(f"    Trying Pollinations (free): {article_title[:40]}...")
        prompt = (
            f"Professional food photography, appetizing, warm lighting, "
            f"shallow depth of field, clean styled background, no text, "
            f"high quality editorial photo of: {article_title}. "
            f"Photorealistic, 8k resolution, Bon Appetit magazine style"
        )
        safe_prompt = urllib.parse.quote(prompt)
        seed = int(time.time() * 1000) % 1000000
        url = (
            f"https://image.pollinations.ai/prompt/{safe_prompt}"
            f"?width={TARGET_WIDTH}&height={TARGET_HEIGHT}&seed={seed}&nologo=true&model=flux"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ElMordjeneAgent/1.0)"})
        with urllib.request.urlopen(req, timeout=45) as response:
            image_bytes = response.read()

        result_webp = _compress_to_webp(image_bytes, output_path_webp)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
        if result_webp and result_jpg:
            logger.info(f"    Images ready from Pollinations")
            return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    Pollinations failed: {e}")
    return None, None


def _try_loremflickr_image(article_title, output_path_webp, output_path_jpg):
    """Try to get a random food image from LoremFlickr."""
    import urllib.request
    import random
    try:
        logger.info(f"    Trying LoremFlickr (free fallback): {article_title[:40]}...")
        keywords = "dessert,chocolate,baking"
        r = random.randint(1, 1000)
        url = f"https://loremflickr.com/1200/630/{keywords}?lock={r}"
        
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ElMordjeneAgent/1.0)"})
        with urllib.request.urlopen(req, timeout=15) as response:
            image_bytes = response.read()

        result_webp = _compress_to_webp(image_bytes, output_path_webp)
        result_jpg = _compress_to_jpg(image_bytes, output_path_jpg)
        if result_webp and result_jpg:
            logger.info(f"    Images ready from LoremFlickr")
            return result_webp, result_jpg
    except Exception as e:
        logger.warning(f"    LoremFlickr failed: {e}")
    return None, None


def _generate_placeholder_image(article_title, output_path_webp, output_path_jpg):
    """Generate a simple placeholder image (food-themed gradient + title text)."""
    from PIL import ImageDraw, ImageFont
    try:
        width, height = TARGET_WIDTH, TARGET_HEIGHT
        img = Image.new("RGB", (width, height), color=(61, 43, 31))
        draw = ImageDraw.Draw(img)

        # Draw a warm gradient
        for y in range(height):
            r = int(61 + (139 - 61) * y / height)
            g = int(43 + (105 - 43) * y / height)
            b = int(31 + (20 - 31) * y / height)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", 42)
            except OSError:
                font = ImageFont.load_default()

        words = article_title.split()
        lines, current_line = [], ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) > 35:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)

        y_pos = height // 2 - len(lines) * 30
        for line in lines[:4]:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, y_pos), line, fill=(245, 230, 211), font=font)
            y_pos += 55

        result_webp = _compress_to_webp(img, output_path_webp)
        result_jpg = _compress_to_jpg(img, output_path_jpg)
        return result_webp, result_jpg
    except Exception as e:
        logger.error(f"    Placeholder image error: {e}")
        return None, None


def generate_featured_image(article_title, save_dir=None, source_url=None):
    """
    Generate a featured image. 
    Bulletproof cascading fallbacks:
    1. Gemini Imagen 3
    2. Gemini Flash Image
    3. Source Article OG Image
    4. Pollinations AI
    5. LoremFlickr
    6. Local Placeholder
    """
    if config.SKIP_AI_IMAGE:
        logger.info("  Skipping AI image generation (SKIP_AI_IMAGE=true)")
        return None, None

    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")
    os.makedirs(save_dir, exist_ok=True)

    slug = re.sub(r"[^a-z0-9]+", "-", article_title.lower())[:50].strip("-")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path_webp = os.path.join(save_dir, f"{slug}_{timestamp}.webp")
    output_path_jpg = os.path.join(save_dir, f"{slug}_{timestamp}.jpg")

    logger.info(f"  Generating featured image for: {article_title[:60]}")

    # 1. Gemini Imagen 3
    webp, jpg = _try_gemini_imagen(article_title, output_path_webp, output_path_jpg)
    if webp and jpg:
        return webp, jpg

    # 2. Gemini Flash Image
    webp, jpg = _try_gemini_flash_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg:
        return webp, jpg

    # 3. Source article
    if source_url:
        webp, jpg = _try_source_image(source_url, output_path_webp, output_path_jpg)
        if webp and jpg:
            return webp, jpg

    # 4. Pollinations
    webp, jpg = _try_pollinations_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg:
        return webp, jpg

    # 5. LoremFlickr
    webp, jpg = _try_loremflickr_image(article_title, output_path_webp, output_path_jpg)
    if webp and jpg:
        return webp, jpg

    # 6. Placeholder
    logger.info("    Using placeholder image")
    return _generate_placeholder_image(article_title, output_path_webp, output_path_jpg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_title = "Dubai Chocolate Strawberries: The Viral TikTok Recipe Everyone Is Trying"
    webp_path, jpg_path = generate_featured_image(test_title)
    if webp_path and jpg_path:
        size_kb = os.path.getsize(webp_path) / 1024
        print(f"Image: {webp_path} ({size_kb:.1f}KB)")
    else:
        print("Image generation failed")
