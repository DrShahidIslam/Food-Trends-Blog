import os
import json
import base64
import requests
import textwrap
import random
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
BRIDGE_PAGE_URL_BASE = os.getenv("BRIDGE_PAGE_URL", "https://drshahidislam.github.io/discovery/")

# --- Premium Templates ---

TEMPLATES = {
    "modern": """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Discovery</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700&family=Outfit:wght@300;600&display=swap" rel="stylesheet">
    <style>
        :root {{ --primary: #8f1f28; --bg: #fffaf5; --text: #2a1910; }}
        body {{ font-family: 'Outfit', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
        .card {{ max-width: 500px; width: 90%; background: white; padding: 50px; border-radius: 30px; box-shadow: 0 20px 60px rgba(0,0,0,0.05); text-align: center; border: 1px solid rgba(143,31,40,0.1); }}
        h1 {{ font-family: 'Montserrat', sans-serif; color: var(--primary); font-size: 1.8rem; line-height: 1.2; margin-bottom: 20px; }}
        p {{ line-height: 1.6; opacity: 0.8; margin-bottom: 30px; }}
        .btn {{ display: inline-block; background: var(--primary); color: white; padding: 20px 45px; border-radius: 50px; text-decoration: none; font-weight: 600; transition: transform 0.3s; }}
        .btn:hover {{ transform: translateY(-5px); box-shadow: 0 10px 20px rgba(143,31,40,0.2); }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <p>{excerpt}</p>
        <a href="{target_url}" class="btn">DISCOVER SECRETS</a>
    </div>
</body>
</html>
""",
    "minimal": """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ background: #111; color: #eee; font-family: serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
        .content {{ text-align: center; max-width: 600px; padding: 20px; }}
        h1 {{ font-size: 2.5rem; letter-spacing: -1px; margin-bottom: 40px; }}
        .link {{ color: white; text-decoration: none; border-bottom: 2px solid #8f1f28; padding-bottom: 5px; font-size: 1.2rem; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="content">
        <h1>{title}</h1>
        <a href="{target_url}" class="link">READ THE FULL STORY</a>
    </div>
</body>
</html>
""",
    "editorial": """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Featured: {title}</title>
    <style>
        body {{ font-family: sans-serif; margin: 0; background: #f4f4f4; }}
        .hero {{ height: 100vh; display: flex; flex-direction: column; justify-content: flex-end; padding: 10% 5%; background: linear-gradient(to top, rgba(0,0,0,0.8), transparent); }}
        h1 {{ color: white; font-size: 4rem; margin: 0; max-width: 800px; line-height: 1; }}
        .cta {{ margin-top: 40px; }}
        .cta a {{ background: white; color: black; padding: 20px 40px; text-decoration: none; font-weight: bold; text-transform: uppercase; letter-spacing: 2px; }}
    </style>
</head>
<body>
    <div class="hero">
        <h1>{title}</h1>
        <div class="cta"><a href="{target_url}">Open Article</a></div>
    </div>
</body>
</html>
"""
}

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
        # Shadow
        draw.text(((width-w)/2 + 2, y_text + 2), line, font=font, fill=(0,0,0,100))
        # Main
        draw.text(((width-w)/2, y_text), line, font=font, fill=(255,255,255,255))
        y_text += line_h
        
    # Floating Branding
    try:
        brand_font = ImageFont.truetype(font_paths[0], int(width * 0.035)) if font else None
        if brand_font:
            brand_text = "EL MORDJENE"
            bw = draw.textlength(brand_text, font=brand_font)
            draw.text(((width-bw)/2, height - 70), brand_text, font=brand_font, fill=(255,255,255,160))
    except: pass
    
    img.convert("RGB").save(output_path, "JPEG", quality=95)

def create_unique_bridge_page(slug, title, target_url, excerpt):
    """Generate a unique physical HTML file on GitHub Pages"""
    template_name = random.choice(list(TEMPLATES.keys()))
    html_content = TEMPLATES[template_name].format(
        title=title,
        excerpt=excerpt,
        target_url=target_url
    )
    
    # Ensure subdirectory exists
    subdir = BRIDGE_PAGE_ROOT / "discovery"
    subdir.mkdir(parents=True, exist_ok=True)
    
    file_path = subdir / f"{slug}.html"
    file_path.write_text(html_content, encoding="utf-8")
    
    print(f"Generated unique bridge page: {file_path} (Style: {template_name})")
    return f"{BRIDGE_PAGE_URL_BASE}discovery/{slug}.html"

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
    """Master flow for a single pin"""
    print(f"--- Unified Flow: {title} ---")
    
    raw_img = f"temp_raw_{slug}.jpg"
    final_img = f"final_pin_{slug}.jpg"
    
    # 1. Image Generation
    if generate_image(f"A luxury close-up editorial shot of {title}", raw_img):
        # 2. Design
        design_pin(raw_img, title, final_img)
        
        # 3. Unique Bridge Page
        bridge_url = create_unique_bridge_page(slug, title, url, description)
        
        # 4. Pinterest Publish
        success = publish_pin(final_img, title, description, bridge_url, board_id)
        
        # Cleanup
        if os.path.exists(raw_img): os.remove(raw_img)
        return success
    return False
