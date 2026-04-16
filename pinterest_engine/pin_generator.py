import os
import json
import base64
import requests
import textwrap
import random
import datetime
import shutil
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv()

SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/images/generations"
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "Kwai-Kolors/Kolors")

PINTEREST_API_BASE = "https://api.pinterest.com/v5"
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")

BRIDGE_PAGE_ROOT = Path("bridge_page")
BRIDGE_PAGE_URL_BASE = os.getenv("BRIDGE_PAGE_URL", "https://drshahidislam.github.io/Food-Trends-Blog/")

WEEKLY_MAGAZINE_CSS = """
        :root { --primary: #e6dfd9; --accent: #8b2b2b; --text: #1a1a1a; --surface: #ffffff; }
        body { font-family: 'Georgia', serif; background-color: var(--primary); color: var(--text); margin: 0; padding: 0; }
        .header { background: var(--surface); padding: 40px 20px; text-align: center; border-bottom: 1px solid #dcd3cb; }
        .header h1 { margin: 0; font-size: 2.5rem; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; }
        .header p { color: #666; font-family: sans-serif; letter-spacing: 1px; margin-top: 10px; }
        .gallery-container { max-width: 1200px; margin: 50px auto; padding: 0 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 40px; }
        .card { background: var(--surface); border-radius: 8px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.05); transition: transform 0.3s ease; display: flex; flex-direction: column; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 15px 40px rgba(139,43,43,0.15); }
        .card-img-wrapper { position: relative; width: 100%; padding-top: 133%; overflow: hidden; }
        .card-img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }
        .card-body { padding: 25px; flex-grow: 1; display: flex; flex-direction: column; }
        .card-title { font-size: 1.4rem; color: var(--text); margin: 0 0 15px 0; line-height: 1.3; }
        .card-excerpt { color: #555; font-family: sans-serif; font-size: 0.95rem; line-height: 1.6; margin-bottom: 25px; flex-grow: 1; }
        .card-btn { display: inline-block; background-color: var(--accent); color: white; text-align: center; padding: 12px 20px; text-decoration: none; border-radius: 4px; font-family: sans-serif; font-weight: bold; letter-spacing: 1px; transition: background 0.2s; }
        .card-btn:hover { background-color: #6a1f1f; }
"""

# --- Core Functions ---

def generate_image(prompt, output_path):
    """Generate image using SiliconFlow"""
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": SILICONFLOW_MODEL,
        "prompt": f"{prompt}, food photography, ultra-realistic, macro shot, 8k, professional lighting, editorial beauty photography",
        "image_size": "768x1024", 
        "batch_size": 1,
    }
    
    try:
        response = requests.post(SILICONFLOW_API_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            image_url = response.json()["images"][0]["url"]
            img_data = requests.get(image_url, timeout=30).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            return True
        else:
            print(f"SiliconFlow Error: {response.text}")
    except Exception as e:
        print(f"SiliconFlow Exception: {e}")
    return False

def design_pin(image_path, title, output_path):
    """Apply premium design overlays using Pillow"""
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Sophisticated Gradient
    grad_height = int(height * 0.5)
    for y in range(height - grad_height, height):
        progress = (y - (height - grad_height)) / grad_height
        alpha = int(220 * (progress ** 1.5))
        draw.line([(0, y), (width, y)], fill=(42, 25, 16, alpha))
        
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    # Premium Typography
    font_size = int(width * 0.08)
    font_paths = [
        "C:/Windows/Fonts/Montserrat-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arialbd.ttf"
    ]
    font = None
    for fp in font_paths:
        try:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, font_size)
                break
        except: continue
    if not font: font = ImageFont.load_default()
    
    wrapped_lines = textwrap.wrap(title, width=18)
    line_h = font_size * 1.2
    y_text = height - (len(wrapped_lines) * line_h) - 150
    
    for line in wrapped_lines:
        w = draw.textlength(line, font=font)
        draw.text(((width-w)/2 + 2, y_text + 2), line, font=font, fill=(0,0,0,100))
        draw.text(((width-w)/2, y_text), line, font=font, fill=(255,255,255,255))
        y_text += line_h
        
    try:
        brand_font = ImageFont.truetype(font_paths[0], int(width * 0.035)) if font else None
        if brand_font:
            brand_text = "EL MORDJENE"
            bw = draw.textlength(brand_text, font=brand_font)
            draw.text(((width-bw)/2, height - 70), brand_text, font=brand_font, fill=(255,255,255,160))
    except: pass
    
    img.convert("RGB").save(output_path, "JPEG", quality=95)

def update_weekly_magazine(slug, title, target_url, excerpt, image_file_name):
    """
    Update or create a robust Weekly Gallery page holding multiple pins.
    Copies the generated image to assets folder so it displays properly.
    """
    now = datetime.datetime.now()
    week_num = now.isocalendar()[1]
    year = now.year
    week_slug = f"edition-{week_num}-{year}"
    
    discovery_dir = BRIDGE_PAGE_ROOT / "discovery"
    assets_dir = discovery_dir / "assets"
    discovery_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Move the raw image to assets folder to act as the gorgeous thumbnail
    dest_img_path = assets_dir / f"{slug}.jpg"
    shutil.copy(image_file_name, dest_img_path)
    
    html_file = discovery_dir / f"{week_slug}.html"
    
    # HTML Card for this pin
    card_html = f"""
        <!-- POST: {slug} -->
        <div class="card" id="{slug}">
            <div class="card-img-wrapper">
                <img src="assets/{slug}.jpg" alt="{title}" class="card-img">
            </div>
            <div class="card-body">
                <h2 class="card-title">{title}</h2>
                <p class="card-excerpt">{excerpt}</p>
                <a href="{target_url}" class="card-btn">READ FULL RECIPE</a>
            </div>
        </div>
    """

    if not html_file.exists():
        # Create fresh weekly magazine
        base_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>El Mordjene Weekly Finds - Week {week_num}, {year}</title>
    <style>
{WEEKLY_MAGAZINE_CSS}
    </style>
</head>
<body>
    <div class="header">
        <h1>Weekly Edition</h1>
        <p>Curated Top Trends & Beautiful Recipes • Week {week_num}</p>
    </div>
    <div class="gallery-container">
        <!-- CARDS BEGIN -->
{card_html}
        <!-- CARDS END -->
    </div>
</body>
</html>"""
        html_file.write_text(base_html, encoding="utf-8")
    else:
        # Inject card into existing magazine
        content = html_file.read_text(encoding="utf-8")
        inject_marker = "<!-- CARDS BEGIN -->"
        if inject_marker in content:
            new_content = content.replace(inject_marker, f"{inject_marker}\n{card_html}")
            html_file.write_text(new_content, encoding="utf-8")
            
    # Format the final Pinterest link resolving cleanly to github pages hash
    return f"{BRIDGE_PAGE_URL_BASE.strip('/')}/discovery/{week_slug}.html#{slug}"

def publish_pin(image_path, title, description, bridge_url, board_id):
    """Push to Pinterest API"""
    if not PINTEREST_ACCESS_TOKEN:
        print("Skipping Pinterest publish: No Access Token")
        return False
        
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
        
    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:500],
        "link": bridge_url,
        "media_source": {
            "source_type": "image_base64",
            "content_type": "image/jpeg",
            "data": img_b64,
        }
    }
    
    headers = {"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}", "Content-Type": "application/json"}
    try:
        response = requests.post(f"{PINTEREST_API_BASE}/pins", headers=headers, json=payload, timeout=60)
        if response.status_code in (200, 201):
            print(f"Pin Published! ID: {response.json().get('id')}")
            return True
        else:
            print(f"Pinterest Error: {response.text}")
    except Exception as e:
        print(f"Pinterest Exception: {e}")
    return False

def process_new_pin(title, slug, url, description, board_id):
    """Master flow for generating multiple pins per article (4x multiplier) -> Weekly Gallery"""
    print(f"--- Unified Flow: {title} (Generating 4 Variations) ---")
    
    angles = [
        "A luxury close-up editorial shot, macro",
        "A beautiful overhead flat-lay photography composition",
        "A bright minimalist lifestyle setting",
        "A dramatic moody lighting rustic shot"
    ]
    
    success_count = 0
    for i, angle in enumerate(angles):
        iter_slug = f"{slug}-pin-{i+1}"
        raw_img = f"temp_raw_{iter_slug}.jpg"
        final_img = f"final_pin_{iter_slug}.jpg"
        
        print(f"  -> Variation {i+1}: {angle}")
        
        # 1. Image Generation
        pin_prompt = f"{angle} of {title}"
        if generate_image(pin_prompt, raw_img):
            # 2. Design Overlay
            design_pin(raw_img, title, final_img)
            
            # 3. Weekly Magazine Injection (Host the raw image for the beautiful gallery thumb)
            bridge_url = update_weekly_magazine(iter_slug, title, url, description, raw_img)
            
            # 4. Pinterest Publish
            if publish_pin(final_img, title, description, bridge_url, board_id):
                success_count += 1
            
            # Cleanup local temp files (raw_img was copied to bridge assets folder already)
            if os.path.exists(raw_img): os.remove(raw_img)
            if os.path.exists(final_img): os.remove(final_img)
            
    print(f"--- Completed: {success_count}/4 Pins Published ---")
    return success_count > 0
