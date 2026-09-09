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
import argparse
import urllib.parse
from google import genai
from huggingface_hub import InferenceClient

VERSION = "1.2.2"
print(f"--- PIN GENERATOR v{VERSION} START ---", flush=True)

# Load environment
root_dir = Path(__file__).parent.parent
env_path = root_dir / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# API Configurations
PINTEREST_API_BASE = "https://api.pinterest.com/v5"

# Priority: Load token from dashboard OAuth first
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip()
token_file = root_dir / "pinterest_auth.json"
if token_file.exists():
    try:
        with open(token_file, "r") as f:
            token_data = json.load(f)
            PINTEREST_ACCESS_TOKEN = token_data.get("access_token", PINTEREST_ACCESS_TOKEN)
    except: pass

hf_keys = os.getenv("HUGGINGFACE_API_KEY", "").split(",")
hf_keys = [k.strip() for k in hf_keys if k.strip()]
HUGGINGFACE_MODEL = "black-forest-labs/FLUX.1-schnell" 

GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")

def generate_pin_content_with_gemini(topic, pin_index=0):
    """Generate high-CTR title, description, and visual prompts using Pinterest Annotated Keywords and index-based variation angles."""
    if not GEMINI_API_KEYS: return None
    
    # Establish specific angles based on pin_index to prevent duplicate pins
    if pin_index == 0:
        angle_instruction = """
        - Visual Focus: A luxury editorial food photography hero shot.
        - Recipe Name: The actual clean recipe or food item name (e.g. 'DUBAI CHOCOLATE BAR' or 'EL MORDJENE CREPES'). Max 4 words, all caps.
        - Hook: A premium editorial tagline that creates desire (e.g. 'MELT-IN-YOUR-MOUTH PERFECTION', 'THE ULTIMATE INDULGENCE', 'PURE CHOCOLATE BLISS'). Max 6 words, all caps.
        """
        secondary_angle_focus = "A close-up macro texture shot showing melt-in-your-mouth detail."
    elif pin_index == 1:
        angle_instruction = """
        - Visual Focus: A beautiful overhead flat-lay of ingredients, garnishes, and prep.
        - Recipe Name: The actual clean recipe or food item name (e.g. 'EASY CREPES' or 'CHOCOLATE COOKIES'). Max 4 words, all caps.
        - Hook: A quick-time/simplicity hook focusing on prep ease (e.g. 'READY IN JUST 15 MINUTES!', 'ONE-BOWL WONDER!', 'SIMPLE STEP BY STEP'). Max 6 words, all caps.
        """
        secondary_angle_focus = "A luxury editorial food photography hero shot."
    else:
        angle_instruction = """
        - Visual Focus: A close-up macro shot showing glistening texture and delicious details.
        - Recipe Name: The actual clean recipe or food item name (e.g. 'CREPE RECIPE' or 'CHOCOLATE BARS'). Max 4 words, all caps.
        - Hook: A chef secret, hack, or craving hook (e.g. 'THE SECRET CHEF TRICK!', 'YOU WON\'T BELIEVE THIS!', 'IRRESISTIBLY CRISPY!'). Max 6 words, all caps.
        """
        secondary_angle_focus = "An overhead flat-lay of ingredients and preparation layout."

    seasonal_context = ""
    try:
        import sys
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))
        from alerts_engine.sources.seasonal_calendar import get_seasonal_pin_context
        seasonal_context = get_seasonal_pin_context(topic)
    except Exception:
        pass

    # Dynamic headline frameworks to prevent repetitive titles across pins
    headline_frameworks = [
        {
            "name": "Speed & Weeknight Convenience",
            "instruction": "Focus on fast prep or cook time and weeknight simplicity (e.g., '20-Minute Crispy [Dish] (Better Than Takeout)', 'Easy 30-Minute [Dish] for Busy Nights', 'Quick One-Pan [Dish] in Under 25 Minutes')."
        },
        {
            "name": "Sensory & Craving Appeal",
            "instruction": "Focus on mouthwatering sensory texture and flavor details (e.g., 'Extra Gooey [Dish] with [Special Feature]', 'Golden Glazed [Dish] with Crispy Edges', 'Ultra-Creamy [Dish] with Melty [Ingredient]')."
        },
        {
            "name": "Technique & Kitchen Method",
            "instruction": "Focus on a specific cooking method or smart kitchen hack (e.g., 'The One-Pan Method for Perfect [Dish]', 'The Skillet Trick for Extra Tender [Dish]', 'How to Make Restaurant-Crispy [Dish] at Home')."
        },
        {
            "name": "Occasion & Crowd-Pleaser",
            "instruction": "Focus on gatherings, game day, cozy autumn evenings, or family favorites (e.g., 'The Ultimate Crowd-Pleaser [Dish] for Game Day', 'Cozy Autumn [Dish] Everyone Will Ask Seconds For', 'The #1 Party [Dish] That Disappears in Minutes')."
        },
        {
            "name": "Effortless / High-Value Result",
            "instruction": "Focus on few ingredients, no-stress prep, or foolproof results (e.g., '5-Ingredient [Dish] in One Bowl', 'Foolproof [Dish] with Zero Fuss', 'The Only [Dish] Recipe You Will Ever Need')."
        }
    ]
    # Deterministic rotation based on topic hash and pin_index
    framework = headline_frameworks[(abs(hash(topic)) + pin_index) % len(headline_frameworks)]

    prompt = f"""
    You are a top-tier viral Pinterest marketing expert. Your task is to generate high-performance content for Pin #{pin_index + 1} about: "{topic}".
    
    {seasonal_context}
    
    Adhere strictly to these targeted angle guidelines for this pin variation:
    {angle_instruction}

    TARGET HEADLINE ARCHETYPE FOR THIS PIN:
    - Style: {framework['name']}
    - Guidance: {framework['instruction']}
    
    CRITICAL TITLE & HOOK DIVERSITY RULES (REVERSE-ENGINEERED PINTEREST STRATEGY):
    1. STRICTLY FORBIDDEN: DO NOT start titles with audience colon prefixes like "Busy Moms:", "For Busy Moms:", "For Beginners:", "For Home Cooks:", or "For Busy Professionals:".
    2. STRICTLY FORBIDDEN: DO NOT use cliché formulas like "The Secret Ingredient for...", "The Secret Shortcut to...", "The Secret Technique for...", or "The Secret Restaurant Method for...".
    3. Make the Title completely unique, compelling, human-sounding, and under 100 characters. It MUST prominently include the dish name.
    4. Hook (text overlay): MUST be 3-5 punchy words directly highlighting this exact dish's distinct appeal (e.g., 'READY IN 20 MINS', 'EXTRA CHEESY PULL', 'CRISPY & GOLDEN', 'RICH & VELVETY COMFORT', 'MELT-IN-YOUR-MOUTH'). DO NOT use a generic hook like 'THE ULTIMATE COZY FALL DINNER' for every pin.
    5. Description (Exactly 50-75 words): Warm, conversational, sensory tone. Weave in 4-6 natural search phrases. Rotate opening styles: do NOT always start with "Looking for..." or "Craving the ultimate...". End with a soft CTA (e.g., "Save this recipe for dinner!"). NO HASHTAGS.
    6. Alt Text (150-300 chars): High-detail visual food description for accessibility & SEO.
    7. Image Prompts (400-600 chars each): Hyper-realistic food photography. MUST explicitly state "NO TEXT IN THE IMAGE".
    8. Accurate Recipe Data: Prep/cook minutes, yield, full ingredient list with measurements, and clear instructions.
    
    Return ONLY valid JSON:
    {{
      "annotated_keywords": ["keyword1", "keyword2", "keyword3"],
      "title": "Unique Compelling Title Matching The Selected Framework (Under 100 chars)",
      "description": "50-75 word sensory description ending in soft Save CTA. NO HASHTAGS...",
      "alt_text": "Descriptive visual alt text...",
      "recipe_name": "CLEAN RECIPE NAME (max 4 words, all caps)",
      "hook": "3-5 WORD UNIQUE OVERLAY (e.g., 'EXTRA CRISPY & TENDER')",
      "image_prompt": "Primary visual focus photography prompt. NO TEXT...",
      "secondary_image_prompt": "Secondary visual focus photography prompt. NO TEXT...",
      "prep_time_minutes": 10,
      "cook_time_minutes": 15,
      "recipe_yield": "4 servings",
      "ingredients": [
        "1 1/2 lbs main ingredient, prepped",
        "1/2 tsp garlic powder",
        "2 tbsp olive oil",
        "1 tsp salt and black pepper"
      ],
      "instructions": [
        "Prepare and season all ingredients thoroughly.",
        "Cook over medium-high heat until golden brown and tender.",
        "Rest for 3 minutes and serve hot."
      ],
      "recipe_category": "Dinner",
      "recipe_cuisine": "American"
    }}
    """
    
    # Model from config
    try:
        from alerts_engine import config as wp_config
        model_name = getattr(wp_config, "GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    except:
        model_name = "gemini-3.1-flash-lite-preview"

    for key in GEMINI_API_KEYS:
        clean_key = key.strip().strip("'").strip('"')
        if not clean_key:
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
        try:
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=60)
            if res.status_code == 200:
                text = res.json()['candidates'][0]['content']['parts'][0]['text']
                text = text.strip().replace("```json", "").replace("```", "")
                return json.loads(text)
            else:
                print(f"   [Gemini] Key fail (status {res.status_code})")
        except Exception as e:
            print(f"   [Gemini] Request error: {e}")
            continue
    return None

BRIDGE_PAGE_ROOT = Path("bridge_page")
BRIDGE_PAGE_URL_BASE = os.getenv("BRIDGE_PAGE_URL", "https://drshahidislam.github.io/Food-Trends-Blog/bridge_page/")
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

WEEKLY_MAGAZINE_CSS = """
    :root { 
        --primary: #8f1f28; 
        --accent: #d87439; 
        --bg: #fffaf5; 
        --text: #2a1910; 
        --glass: rgba(255, 255, 255, 0.9);
        --surface: #ffffff;
    }
    
    body { 
        font-family: 'Outfit', sans-serif; 
        background-color: var(--bg); 
        background-image: 
            radial-gradient(at 0% 0%, hsla(11,100%,94%,1) 0, transparent 50%), 
            radial-gradient(at 50% 0%, hsla(35,100%,92%,1) 0, transparent 50%), 
            radial-gradient(at 100% 0%, hsla(11,100%,94%,1) 0, transparent 50%);
        color: var(--text); 
        margin: 0; 
        padding: 0; 
        scroll-behavior: smooth;
        min-height: 100vh;
    }
    
    .header { 
        padding: 60px 20px; 
        text-align: center; 
        animation: fadeInDown 0.8s ease-out;
    }
    
    .header h1 { 
        font-family: 'Playfair Display', serif;
        margin: 0; 
        font-size: 3.5rem; 
        color: var(--primary); 
        letter-spacing: -1px; 
        text-transform: uppercase; 
        font-weight: 900; 
    }
    
    .header p { 
        color: var(--accent); 
        font-weight: 600;
        letter-spacing: 4px; 
        margin-top: 15px; 
        text-transform: uppercase; 
        font-size: 0.9rem; 
    }
    
    .gallery-container { 
        max-width: 1100px; 
        margin: 0 auto 80px auto; 
        padding: 0 20px; 
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 40px; 
    }
    
    .card { 
        background: var(--glass); 
        backdrop-filter: blur(10px);
        border-radius: 24px; 
        overflow: hidden; 
        box-shadow: 0 20px 40px rgba(143, 31, 40, 0.05); 
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); 
        display: flex; 
        flex-direction: column; 
        border: 1px solid rgba(255, 255, 255, 0.5); 
    }
    
    .card:hover { 
        transform: translateY(-12px) scale(1.02); 
        box-shadow: 0 30px 60px rgba(143, 31, 40, 0.15);
    }
    
    .card-img-wrapper { 
        position: relative; 
        width: 100%; 
        padding-top: 130%; 
        overflow: hidden; 
    }
    
    .card-img { 
        position: absolute; 
        top: 0; 
        left: 0; 
        width: 100%; 
        height: 100%; 
        object-fit: cover; 
        transition: transform 0.8s ease; 
    }
    
    .card:hover .card-img { transform: scale(1.1); }
    
    .card-body { 
        padding: 30px; 
        text-align: center; 
        display: flex;
        flex-direction: column;
        flex-grow: 1;
    }
    
    .card-title { 
        font-family: 'Playfair Display', serif;
        font-size: 1.8rem; 
        color: var(--text); 
        margin: 0 0 15px 0; 
        line-height: 1.2; 
        font-weight: 700; 
    }
    
    .card-excerpt { 
        color: #554a44; 
        font-size: 1rem; 
        line-height: 1.6; 
        margin-bottom: 25px; 
        flex-grow: 1;
    }
    
    .card-btn { 
        display: block; 
        background: linear-gradient(135deg, var(--primary) 0%, #b32a35 100%);
        color: white; 
        text-align: center; 
        padding: 18px 30px; 
        text-decoration: none; 
        border-radius: 100px; 
        font-weight: 700; 
        letter-spacing: 1px; 
        transition: all 0.3s ease; 
        text-transform: uppercase; 
        font-size: 0.9rem; 
        box-shadow: 0 10px 20px rgba(143, 31, 40, 0.2); 
    }
    
    .card-btn:hover { 
        background: linear-gradient(135deg, var(--accent) 0%, #e68a4d 100%);
        transform: scale(1.05); 
        box-shadow: 0 15px 30px rgba(216, 116, 57, 0.4); 
    }

    /* Deep Link Focus Styles */
    .hero-focus {
        grid-column: 1 / -1;
        background: var(--glass);
        padding: 40px;
        border-radius: 32px;
        text-align: center;
        margin-bottom: 20px;
        border: 2px solid var(--primary);
        animation: fadeInUp 0.8s ease-out;
    }
    
    .glass-tag {
        display: inline-block;
        background: #fff0f0;
        color: var(--primary);
        padding: 8px 16px;
        border-radius: 50px;
        font-size: 0.75rem;
        font-weight: 800;
        margin-bottom: 20px;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    .show-all-btn {
        background: none;
        border: 2px solid var(--primary);
        color: var(--primary);
        padding: 12px 25px;
        border-radius: 50px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.3s;
        margin-top: 20px;
    }

    .show-all-btn:hover {
        background: var(--primary);
        color: white;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(30px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .focused-card {
        max-width: 500px;
        margin: 0 auto;
        border: 2px solid var(--primary);
        box-shadow: 0 30px 60px rgba(143, 31, 40, 0.3);
    }
"""

DEEP_LINK_JS = """
    function initDeepLink() {
        const hash = window.location.hash.substring(1);
        if (hash) {
            const targetCard = document.getElementById(hash);
            if (targetCard) {
                // Hide all cards initially
                const allCards = document.querySelectorAll('.card');
                allCards.forEach(c => c.style.display = 'none');
                
                // Show target card with focus
                targetCard.style.display = 'flex';
                targetCard.classList.add('focused-card');
                
                // Add Focus Header
                const container = document.querySelector('.gallery-container');
                const hero = document.createElement('div');
                hero.className = 'hero-focus';
                hero.id = 'focus-header';
                hero.innerHTML = `
                    <div class="glass-tag">EXCLUSIVELY CURATED FOR YOU</div>
                    <h2 style="font-family: 'Playfair Display', serif; margin-bottom: 10px;">Found Your Trend!</h2>
                    <p style="color: #666; margin-bottom: 20px;">We've matched your interest with our latest discovery.</p>
                    <button class="show-all-btn" onclick="showAllTrends()">EXPLORE MORE TRENDS</button>
                `;
                container.prepend(hero);
                
                // Scroll to top to see the focused card
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }
    }

    function showAllTrends() {
        document.querySelectorAll('.card').forEach(c => {
            c.style.display = 'flex';
            c.classList.remove('focused-card');
        });
        const header = document.getElementById('focus-header');
        if (header) header.remove();

        window.location.hash = '';
    }

    window.addEventListener('DOMContentLoaded', initDeepLink);
"""

# --- Niche CTA Options ---

CTA_OPTIONS = {
    "viral": ["SAVE THIS RECIPE 📌", "Tap To See The Trend", "SAVE For Later! 📌", "Find Out How Here"],
    "healthy": ["SAVE THIS RECIPE 📌", "Eat Better Today", "SAVE For Meal Prep! 📌", "Healthy & Easy"],
    "dinner": ["SAVE FOR DINNER 📌", "Easy Weeknight Meal", "SAVE For Tonight! 📌", "Cook This Tonight"],
    "dessert": ["SAVE THIS RECIPE 📌", "Decadent & Delicious", "SAVE For Dessert Night! 📌", "Try This Treat"],
    "recipe": ["SAVE THIS RECIPE 📌", "Step-By-Step Guide", "SAVE For Weekend Cooking! 📌", "Master This Dish"]
}

# --- Multi-Backend Generation ---

def _try_huggingface(prompt, output_path):
    if not hf_keys: return False
    # Use a highly realistic static photography string
    full_prompt = f"{prompt}, high-end food photography, award-winning, ultra-realistic, 8k resolution, shot on 100mm macro lens, f/2.8, cinematic soft lighting, detailed textures, professional food styling, bokeh background, 768x1365"
    
    for i, key in enumerate(hf_keys):
        try:
            print(f"HuggingFace: Key {i+1}/{len(hf_keys)}...", flush=True)
            hf_client = InferenceClient(api_key=key)
            image = hf_client.text_to_image(full_prompt, model=HUGGINGFACE_MODEL)
            image.save(output_path)
            return True
        except Exception as e:
            err_str = str(e)
            print(f"HuggingFace Key {i+1} Error: {err_str}")
            if "402" in err_str or "Payment Required" in err_str or "depleted" in err_str:
                print(f"HuggingFace credits depleted for key {i+1}. Trying next key...", flush=True)
            continue
    return False

def _try_cloudflare(prompt, output_path):
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token: return False
    try:
        print(f"DEBUG: Trying Cloudflare SDXL Fallback...", flush=True)
        enhanced_prompt = f"{prompt}, professional food photography, award-winning, ultra-realistic, 8k resolution, shot on 100mm macro lens, f/2.8, cinematic soft lighting, detailed textures, professional food styling, bokeh background, vertical portrait, 9:16 aspect ratio, high resolution"
        
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id.strip()}/ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {
            "Authorization": f"Bearer {api_token.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": enhanced_prompt
        }
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"DEBUG: Cloudflare SDXL API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"DEBUG: Cloudflare SDXL failed: {e}")
    return False

def _try_pollinations(prompt, output_path):
    try:
        print(f"DEBUG: Trying Pollinations AI...", flush=True)
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=1365&model=flux&nologo=true&seed={random.randint(1,999999)}"
        res = requests.get(url, timeout=30)
        if res.status_code == 200:
            with open(output_path, "wb") as f: f.write(res.content)
            return True
    except Exception as e:
        print(f"DEBUG: Pollinations failed: {e}")
    return False

def generate_image_master(prompt, output_path):
    if _try_huggingface(prompt, output_path): return True
    if _try_cloudflare(prompt, output_path): return True
    if _try_pollinations(prompt, output_path): return True
    return False

# --- Premium Design Engine ---

def create_split_screen_layout(image_path, title, output_path, board_type="recipe", secondary_image_path=None, hook_text=None):
    """
    Creates a premium 1000x1500 px vertical split-screen card:
    - Top 40% (1000x600 px): standard crop of the recipe image (zoom 1.0)
    - Middle 20% (1000x300 px): solid board-matched color block with large text
    - Bottom 40% (1000x600 px): either a second complementary image, or a 2.3x close-up macro zoom of the first image
    """
    print(f"   [Layout] Building Split-Screen Vertical Layout for board: {board_type}")
    try:
        orig_img = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"   [Layout Error] Failed to open base image: {e}")
        return False

    target_w, target_h = 1000, 1500
    canvas = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 255))

    # Helper function to crop-to-fill and resize to specific bounds
    def crop_and_resize(img, tw, th, zoom=1.0):
        w, h = img.size
        # zoom in
        zw = int(w / zoom)
        zh = int(h / zoom)
        left = (w - zw) // 2
        top = (h - zh) // 2
        zoomed = img.crop((left, top, left + zw, top + zh))
        
        # aspect ratio crop
        zw, zh = zoomed.size
        target_aspect = tw / th
        zoomed_aspect = zw / zh
        
        if zoomed_aspect > target_aspect:
            new_w = int(zh * target_aspect)
            crop_left = (zw - new_w) // 2
            cropped = zoomed.crop((crop_left, 0, crop_left + new_w, zh))
        else:
            new_h = int(zw / target_aspect)
            crop_top = (zh - new_h) // 2
            cropped = zoomed.crop((0, crop_top, zw, crop_top + new_h))
            
        return cropped.resize((tw, th), Image.Resampling.LANCZOS)

    # 1. Top Image Segment (1000x600 px)
    top_segment = crop_and_resize(orig_img, target_w, 600, zoom=1.0)
    canvas.paste(top_segment, (0, 0))

    # 2. Bottom Image Segment (1000x600 px)
    # Check if we have a secondary complementary image
    if secondary_image_path and os.path.exists(secondary_image_path):
        try:
            print(f"   [Layout] Placing secondary complementary image as bottom segment...")
            sec_img = Image.open(secondary_image_path).convert("RGBA")
            bottom_segment = crop_and_resize(sec_img, target_w, 600, zoom=1.0)
        except Exception as e:
            print(f"   [Layout Warning] Failed to load secondary image: {e}. Falling back to extreme zoom.")
            bottom_segment = crop_and_resize(orig_img, target_w, 600, zoom=2.3)
    else:
        # Extreme 2.3x macro close-up zoom of the primary food texture
        print(f"   [Layout] Placing 2.3x extreme zoom of primary image as bottom segment...")
        bottom_segment = crop_and_resize(orig_img, target_w, 600, zoom=2.3)
        
    canvas.paste(bottom_segment, (0, 900))

    # 3. Middle Text Box Segment (1000x300 px)
    # Harmonious curated HSL color palettes matching Pinterest food trends
    board_colors = {
        "dessert": (74, 44, 17, 255),    # Rich Cocoa Brown
        "dinner": (179, 54, 42, 255),     # Warm Terracotta/Red
        "salad": (68, 97, 62, 255),       # Deep Sage Green
        "soup": (189, 101, 49, 255),      # Golden Mustard/Orange
        "trend": (33, 40, 48, 255),       # Dark Slate Blue
        "recipe": (48, 32, 21, 255)       # Espresso Brown
    }
    box_color = board_colors.get(board_type, board_colors["recipe"])

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(0, 600), (target_w, 900)], fill=box_color)

    # Fonts
    fonts_dir = root_dir / "fonts"
    montserrat_path = str(fonts_dir / "Montserrat-Bold.ttf")

    font_badge_size = 26
    font_recipe_size = 54
    font_hook_size = 28

    badge_font = None
    recipe_font = None
    hook_font = None

    try:
        if os.path.exists(montserrat_path):
            badge_font = ImageFont.truetype(montserrat_path, font_badge_size)
            recipe_font = ImageFont.truetype(montserrat_path, font_recipe_size)
            hook_font = ImageFont.truetype(montserrat_path, font_hook_size)
        else:
            fallbacks = ["C:/Windows/Fonts/arialbd.ttf", "arialbd.ttf"]
            for f_path in fallbacks:
                if os.path.exists(f_path):
                    badge_font = ImageFont.truetype(f_path, font_badge_size)
                    recipe_font = ImageFont.truetype(f_path, font_recipe_size)
                    hook_font = ImageFont.truetype(f_path, font_hook_size)
                    break
    except Exception as e:
        print(f"   [Layout Font Error] {e}")

    if not badge_font: badge_font = ImageFont.load_default()
    if not recipe_font: recipe_font = ImageFont.load_default()
    if not hook_font: hook_font = ImageFont.load_default()

    # --- Three-Tier Magazine Text Layout ---
    # Tier 1: Category Badge (e.g. "EASY RECIPE")
    badge_text = board_type.upper()
    if badge_text == "RECIPE": badge_text = "EASY RECIPE"
    elif badge_text == "TREND": badge_text = "VIRAL TREND"

    # Tier 2: Recipe Name (hero text — large, bold, white)
    clean_title = title.replace("-", " ").upper()
    recipe_lines = textwrap.wrap(clean_title, width=20)

    # Scale down if recipe name is too long for 2 lines
    if len(recipe_lines) > 2:
        font_recipe_size = 44
        try:
            if os.path.exists(montserrat_path):
                recipe_font = ImageFont.truetype(montserrat_path, font_recipe_size)
            elif os.path.exists("C:/Windows/Fonts/arialbd.ttf"):
                recipe_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_recipe_size)
        except Exception:
            pass
        recipe_lines = textwrap.wrap(clean_title, width=26)
    recipe_lines = recipe_lines[:2]  # Max 2 lines for recipe name

    # Tier 3: Hook Text (contextual curiosity/desire subtitle)
    hook_lines = []
    if hook_text:
        hook_display = hook_text.replace("-", " ").upper()
        hook_lines = textwrap.wrap(hook_display, width=30)
        hook_lines = hook_lines[:2]  # Max 2 lines for hook

    # --- Calculate vertical layout for perfect centering in 300px box ---
    recipe_line_h = font_recipe_size * 1.15
    hook_line_h = font_hook_size * 1.15

    badge_h = font_badge_size
    gap_badge_recipe = 10
    recipe_block_h = len(recipe_lines) * recipe_line_h
    gap_recipe_hook = 16  # includes space for decorative separator
    hook_block_h = len(hook_lines) * hook_line_h if hook_lines else 0

    total_content_h = badge_h + gap_badge_recipe + recipe_block_h
    if hook_lines:
        total_content_h += gap_recipe_hook + hook_block_h

    block_start_y = 600 + (300 - total_content_h) / 2

    # Draw Tier 1: Category Badge
    badge_w = draw.textlength(badge_text, font=badge_font)
    draw.text(((target_w - badge_w) / 2, block_start_y), badge_text, font=badge_font, fill=(216, 116, 57, 255))

    # Draw Tier 2: Recipe Name (hero)
    y_cursor = block_start_y + badge_h + gap_badge_recipe
    for line in recipe_lines:
        tw = draw.textlength(line, font=recipe_font)
        draw.text(((target_w - tw) / 2, y_cursor), line, font=recipe_font, fill=(255, 255, 255, 255))
        y_cursor += recipe_line_h

    # Draw Tier 3: Hook with decorative separator
    if hook_lines:
        # Thin gold separator line for premium magazine feel
        sep_y = y_cursor + gap_recipe_hook / 2 - 1
        sep_w = 80
        draw.rectangle([((target_w - sep_w) / 2, sep_y), ((target_w + sep_w) / 2, sep_y + 2)], fill=(216, 116, 57, 180))
        y_cursor += gap_recipe_hook
        for line in hook_lines:
            tw = draw.textlength(line, font=hook_font)
            draw.text(((target_w - tw) / 2, y_cursor), line, font=hook_font, fill=(255, 220, 175, 255))
            y_cursor += hook_line_h

    # Draw Save Pill Badge overlay on top-right of the image
    save_badge_text = "📌 SAVE FOR LATER"
    save_badge_w = draw.textlength(save_badge_text, font=badge_font)
    pill_px, pill_py = 18, 8
    pill_x2 = target_w - 30
    pill_x1 = pill_x2 - (save_badge_w + pill_px * 2)
    pill_y1 = 30
    pill_y2 = pill_y1 + (font_badge_size + pill_py * 2)
    draw.rounded_rectangle([(pill_x1, pill_y1), (pill_x2, pill_y2)], radius=15, fill=(143, 31, 40, 230))
    draw.text((pill_x1 + pill_px, pill_y1 + pill_py), save_badge_text, font=badge_font, fill=(255, 255, 255, 255))

    # Convert canvas back to RGB and save
    canvas.convert("RGB").save(output_path, "JPEG", quality=95)
    print(f"   [Layout] Split-Screen Vertical card compiled successfully at: {output_path}")
    return True

def design_pin_premium(image_path, title, output_path, board_type="recipe", secondary_image_path=None, hook_text=None):
    if not os.path.exists(image_path):
        print(f"   [Layout Error] Image file not found: {image_path}")
        return False

    force_split = os.getenv("FORCE_SPLIT_SCREEN", "true").lower() == "true"
    
    # If forced, use split screen format
    if force_split:
        if create_split_screen_layout(image_path, title, output_path, board_type, secondary_image_path, hook_text=hook_text):
            return True
            
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    
    # Selection of Layout
    layouts = ['bottom_fade', 'center_box', 'top_fade', 'solid_block', 'split_screen']
    layout_style = random.choice(layouts)
    print(f"   [Layout] Selected layout style: {layout_style}")
    
    # Font setup
    font_size = int(width * 0.08)
    fonts_dir = root_dir / "fonts"
    
    anton_path = str(fonts_dir / "Anton-Regular.ttf")
    montserrat_path = str(fonts_dir / "Montserrat-Bold.ttf")
    
    primary_font_path = anton_path if layout_style == 'center_box' else montserrat_path
    
    font = None
    try:
        if os.path.exists(primary_font_path):
            font = ImageFont.truetype(primary_font_path, font_size)
        else:
            # Fallback to system fonts
            fallbacks = ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "arialbd.ttf"]
            for f_path in fallbacks:
                if os.path.exists(f_path):
                    font = ImageFont.truetype(f_path, font_size)
                    break
    except: pass
    
    if not font: font = ImageFont.load_default()
    
    # CTA Setup
    ctas = CTA_OPTIONS.get(board_type, CTA_OPTIONS["recipe"])
    cta_text = random.choice(ctas)
    cta_font = None
    try:
        if os.path.exists(montserrat_path):
            cta_font = ImageFont.truetype(montserrat_path, int(width * 0.045))
    except: pass
    if not cta_font: cta_font = font

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    wrapped_lines = textwrap.wrap(title, width=15 if layout_style == 'center_box' else 20)
    line_h = font_size * 1.2
    total_text_h = len(wrapped_lines) * line_h
    
    margin = int(width * 0.08)
    
    if layout_style == 'bottom_fade':
        grad_h = int(height * 0.45)
        for y in range(height - grad_h, height):
            progress = (y - (height - grad_h)) / grad_h
            alpha = int(220 * (progress ** 1.5))
            draw_overlay.rectangle([(0, y), (width, y+1)], fill=(0, 0, 0, alpha))
        text_y = height - total_text_h - int(height * 0.15)
        
    elif layout_style == 'top_fade':
        grad_h = int(height * 0.40)
        for y in range(0, grad_h):
            progress = 1.0 - (y / grad_h)
            alpha = int(220 * (progress ** 1.5))
            draw_overlay.rectangle([(0, y), (width, y+1)], fill=(0, 0, 0, alpha))
        text_y = int(height * 0.10)
        
    elif layout_style == 'center_box':
        box_padding = int(height * 0.05)
        box_h = total_text_h + (box_padding * 2) + int(height * 0.05)
        box_y = (height - box_h) // 2
        draw_overlay.rectangle([(margin//2, box_y), (width - margin//2, box_y + box_h)], fill=(0, 0, 0, 180))
        text_y = box_y + box_padding
        
    elif layout_style == 'solid_block':
        block_h = total_text_h + int(height * 0.18)
        block_y = height - block_h
        draw_overlay.rectangle([(0, block_y), (width, height)], fill=(30, 20, 15, 255))
        text_y = block_y + int(height * 0.04)

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    for line in wrapped_lines:
        w = draw.textlength(line, font=font)
        draw.text(((width-w)/2, text_y), line, font=font, fill=(255,255,255,255))
        text_y += line_h
        
    # Draw CTA
    if cta_text:
        cw = draw.textlength(cta_text, font=cta_font)
        cx = (width - cw) // 2
        cy = text_y + int(height * 0.02) if layout_style != 'bottom_fade' else text_y
        if layout_style == 'bottom_fade': cy = height - int(height * 0.08)
        
        draw.text((cx, cy), cta_text, font=cta_font, fill=(255, 255, 255, 200))

    img.convert("RGB").save(output_path, "JPEG", quality=95)



def update_weekly_magazine(slug, title, target_url, excerpt, image_file_name):
    import re
    now = datetime.datetime.now()
    week_num = now.isocalendar()[1]
    year = now.year
    week_slug = f"edition-{week_num}-{year}"
    
    discovery_dir = BRIDGE_PAGE_ROOT / "discovery"
    assets_dir = discovery_dir / "assets"
    discovery_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    dest_img_path = assets_dir / f"{slug}.jpg"
    shutil.copy(image_file_name, dest_img_path)
    
    html_file = discovery_dir / f"{week_slug}.html"
    
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
        </div>"""

    if not html_file.exists():
        base_html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>El Mordjene Weekly Finds - Week {week_num}</title>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>{WEEKLY_MAGAZINE_CSS}</style>
</head>
<body>
    <div class='header'>
        <h1>Weekly Edition</h1>
        <p>Curated Top Trends & Beautiful Recipes • Week {week_num}</p>
    </div>
    <div class='gallery-container'>
        <!-- CARDS BEGIN -->
        {card_html}
        <!-- CARDS END -->
    </div>
    <script>{DEEP_LINK_JS}</script>
</body>
</html>"""
        html_file.write_text(base_html, encoding="utf-8")
    else:
        content = html_file.read_text(encoding="utf-8")
        
        # Prevent Duplicates: If card with same slug exists, replace it
        pattern = rf"<!-- POST: {re.escape(slug)} -->.*?</div>\s*</div>"
        if re.search(pattern, content, re.DOTALL):
            print(f"   [Gallery] Updating existing card: {slug}")
            content = re.sub(pattern, card_html.strip(), content, flags=re.DOTALL)
            html_file.write_text(content, encoding="utf-8")
        else:
            marker = "<!-- CARDS BEGIN -->"
            if marker in content:
                print(f"   [Gallery] Appending new card: {slug}")
                html_file.write_text(content.replace(marker, f"{marker}\n{card_html}"), encoding="utf-8")

    return f"{BRIDGE_PAGE_URL_BASE.strip('/')}/discovery/{week_slug}.html#{slug}"

def _build_and_generate_bridge_url(slug, title, gemini_data, raw_img, target_wp_url):
    """Generate static recipe bridge page with Schema.org/Recipe JSON-LD for Pinterest Rich Pins."""
    recipe_dict = {
        "recipe_name": (gemini_data.get("recipe_name") if gemini_data else "") or title,
        "description": (gemini_data.get("description") if gemini_data else "") or f"Delicious {title} recipe guide.",
        "prep_time_minutes": gemini_data.get("prep_time_minutes", 10) if gemini_data else 10,
        "cook_time_minutes": gemini_data.get("cook_time_minutes", 15) if gemini_data else 15,
        "recipe_yield": gemini_data.get("recipe_yield", "4 servings") if gemini_data else "4 servings",
        "ingredients": gemini_data.get("ingredients") if gemini_data else [],
        "instructions": gemini_data.get("instructions") if gemini_data else [],
        "recipe_category": gemini_data.get("recipe_category", "Dinner") if gemini_data else "Dinner",
        "recipe_cuisine": gemini_data.get("recipe_cuisine", "American") if gemini_data else "American",
    }
    try:
        import sys
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))
        from bridge_page.generator import generate_recipe_bridge_page
        b_url = generate_recipe_bridge_page(
            slug=slug,
            title=title,
            recipe_data=recipe_dict,
            image_path=raw_img,
            target_wp_url=target_wp_url or f"https://el-mordjene.info/{slug}/"
        )
        print(f"   [Rich Pin Bridge] Created pre-rendered static recipe page: {b_url}")
        return b_url
    except Exception as e:
        print(f"   [Rich Pin Bridge Warning] Generator failed: {e}. Falling back to default URL.")
        return f"{BRIDGE_PAGE_URL_BASE.strip('/')}/?id={slug}"

pin_session = requests.Session()
def pin_request(method, endpoint, **kwargs):
    url = f"https://api.pinterest.com/v5{endpoint}"
    try:
        if method == "GET": return pin_session.get(url, **kwargs)
        return pin_session.post(url, **kwargs)
    except Exception as e:
        print(f"   [Pinterest API] Request Exception: {e}", flush=True)
        return None

def publish_pin(image_path, title, description, bridge_url, board_id, alt_text=None, retry=True):
    if MOCK_MODE: return True
    global PINTEREST_ACCESS_TOKEN
    if not PINTEREST_ACCESS_TOKEN: 
        print("   [Pinterest API] ERROR: No PINTEREST_ACCESS_TOKEN found.", flush=True)
        return False
    
    if not board_id:
        board_id = os.getenv("PINTEREST_BOARD_RECIPES") or os.getenv("PINTEREST_BOARD_ID") or "976859044115152343"

    with open(image_path, "rb") as f: img_b64 = base64.b64encode(f.read()).decode()
    if not alt_text: alt_text = title
    payload = {
        "board_id": str(board_id), "title": title[:100], "description": description[:500],
        "link": bridge_url,
        "alt_text": alt_text[:500],
        "media_source": {"source_type": "image_base64", "content_type": "image/jpeg", "data": img_b64}
    }
    headers = {"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}", "Content-Type": "application/json"}
    res = pin_request("POST", "/pins", headers=headers, json=payload, timeout=60)
    
    if res is not None and res.status_code in (200, 201):
        return True
    elif res is not None and res.status_code == 401 and retry:
        print("   [Pinterest API] Token expired (401). Attempting automatic refresh...", flush=True)
        if refresh_pinterest_token():
            return publish_pin(image_path, title, description, bridge_url, board_id, alt_text, retry=False)
        else:
            return False
    else:
        error_msg = res.text if res is not None else "No response"
        status_code = res.status_code if res is not None else "N/A"
        print(f"   [Pinterest API] ERROR Publishing Pin: HTTP {status_code} - {error_msg}", flush=True)
        return False

def refresh_pinterest_token():
    global PINTEREST_ACCESS_TOKEN
    # Try to get refresh token
    refresh_token = os.getenv("PINTEREST_REFRESH_TOKEN")
    if not refresh_token:
        # Check token_file
        try:
            with open(token_file, "r") as f:
                token_data = json.load(f)
                refresh_token = token_data.get("refresh_token")
        except: pass

    app_id = os.getenv("PINTEREST_APP_ID")
    app_secret = os.getenv("PINTEREST_APP_SECRET")

    if not refresh_token or not app_id or not app_secret:
        print("   [Pinterest API] Cannot refresh token: Missing PINTEREST_REFRESH_TOKEN, APP_ID, or APP_SECRET.")
        return False

    auth = base64.b64encode(f"{app_id.strip()}:{app_secret.strip()}".encode()).decode()
    try:
        response = requests.post("https://api.pinterest.com/v5/oauth/token", headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.strip()
        }, timeout=30)

        if response.status_code == 200:
            data = response.json()
            PINTEREST_ACCESS_TOKEN = data.get("access_token")
            # Save the new token data to file
            with open(token_file, "w") as f:
                json.dump(data, f, indent=2)
            print("   [Pinterest API] Successfully refreshed token and saved to pinterest_auth.json")
            return True
        else:
            print(f"   [Pinterest API] Failed to refresh token: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   [Pinterest API] Error during token refresh: {e}")
        return False

def get_board_id(board_name):
    if not PINTEREST_ACCESS_TOKEN: return None
    headers = {"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}"}
    res = pin_request("GET", "/boards", headers=headers)
    if res is not None and res.status_code == 200:
        for b in res.json().get("items", []):
            if b.get("name", "").lower().strip() == board_name.lower().strip():
                return b.get("id")
    return None

def process_new_pin(title, slug, url, description, board_id):
    print(f"--- Pinterest Flow: {title} ---")
    angles = ["A luxury editorial food photography hero shot, professional lighting", "A beautiful overhead flat-lay photography"]
    success = 0
    for i, angle in enumerate(angles):
        iter_slug = f"{slug}-pin-{i+1}"
        raw_img = f"temp_raw_{iter_slug}.jpg"
        sec_img = f"temp_raw_{iter_slug}_sec.jpg"
        final_img = f"final_pin_{iter_slug}.jpg"
        
        # Pass pin_index to guarantee unique overlays and descriptions per pin
        gemini_data = generate_pin_content_with_gemini(title, pin_index=i)
        if gemini_data:
            p_title = gemini_data.get("title", title)
            p_desc = gemini_data.get("description", description) + f" {gemini_data.get('hashtags', '')}"
            recipe_name = gemini_data.get("recipe_name", title)
            hook_text = gemini_data.get("hook", "")
            alt_text = gemini_data.get("alt_text", p_title)
            image_prompt = gemini_data.get("image_prompt")
            secondary_image_prompt = gemini_data.get("secondary_image_prompt")
        else:
            p_title, p_desc, recipe_name = title, description, title
            hook_text = ""
            alt_text = p_title
            image_prompt = None
            secondary_image_prompt = None

        if not image_prompt:
            image_prompt = f"{angle} of {title}"

        # 50% chance of attempting a two-image collage
        collage_mode = random.choice([True, False])
        sec_img_path = None

        if generate_image_master(image_prompt, raw_img):
            if collage_mode and secondary_image_prompt:
                print(f"   [Collage] Attempting to generate secondary image for collage variant...")
                if generate_image_master(secondary_image_prompt, sec_img):
                    sec_img_path = sec_img
                else:
                    print(f"   [Collage Warning] Secondary image generation failed. Falling back to extreme zoom.")

            design_pin_premium(raw_img, recipe_name, final_img, secondary_image_path=sec_img_path, hook_text=hook_text)
            b_url = _build_and_generate_bridge_url(slug, title, gemini_data, raw_img, url)
            if publish_pin(final_img, p_title, p_desc, b_url, board_id, alt_text=alt_text): 
                success += 1
                
            # Cleanup
            if os.path.exists(raw_img): os.remove(raw_img)
            if sec_img_path and os.path.exists(sec_img_path): os.remove(sec_img_path)
            if os.getenv("MOCK_MODE", "false").lower() != "true" and os.path.exists(final_img):
                os.remove(final_img)
    print(f"--- Finished: {success} Pins Published ---")
    return success > 0

def _load_queue():
    queue_path = root_dir / "topic_queue.json"
    if queue_path.exists():
        try:
            with open(queue_path, "r") as f: return json.load(f)
        except: return []
    return []

def _save_queue(queue):
    queue_path = root_dir / "topic_queue.json"
    with open(queue_path, "w") as f: json.dump(queue, f, indent=2)

def _load_pin_log():
    log_path = root_dir / "pinterest_engine" / "pin_log.json"
    if log_path.exists():
        try:
            with open(log_path, "r") as f: return json.load(f)
        except: return {}
    return {}

def _save_pin_log(log):
    log_path = root_dir / "pinterest_engine" / "pin_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as f: json.dump(log, f, indent=2)

def run_pin_worker():
    """Pick a topic from queue that needs pins (1:3 ratio) and publish 1 pin."""
    queue = _load_queue()
    pin_log = _load_pin_log()
    
    # 7-day cooldown (168 hours)
    cooldown_seconds = 7 * 24 * 3600
    now = datetime.datetime.now().timestamp()
    
    # Filter: WP is done and needs more pins, AND URL is not in 7-day cooldown, AND topic is not excluded
    EXCLUDED_TOPIC_KEYWORDS = ["mordjene", "el-mordjene", "el mordjene", "cebon", "hazelnut spread", "algerian spread"]
    target = None
    for t in queue:
        topic_title = t.get("topic", "").lower()
        url_path = t.get("wp_url", "").replace("https://el-mordjene.info/", "").lower()
        if any(ex in topic_title or ex in url_path for ex in EXCLUDED_TOPIC_KEYWORDS):
            continue

        if t.get("wp_status") == "done" and t.get("pin_count", 0) < 1:
            url = t.get("wp_url", "")
            last_pinned = pin_log.get(url, 0)
            if now - last_pinned >= cooldown_seconds:
                target = t
                break
    
    if not target:
        print("No topics in queue waiting for pins.")
        return

    title = target["topic"]
    url = target.get("wp_url", "")
    wp_slug = ""
    if url:
        wp_slug = url.rstrip('/').split('/')[-1]
    slug = wp_slug if wp_slug else target.get("topic", "").lower().replace(" ", "-")
    description = f"Check out this amazing {title} recipe and guide on el-mordjene.info!"
    pin_index = target.get("pin_count", 0)
    
    print(f"--- PIN WORKER: Processing '{title}' (Pin {pin_index + 1}/1) ---")
    
    # Rotate angles based on which pin we are on
    angles = [
        "A luxury editorial food photography hero shot, professional lighting",
        "A beautiful overhead flat-lay of ingredients and preparation",
        "A close-up macro shot showing texture and delicious details"
    ]
    angle = angles[pin_index % len(angles)]
    
    iter_slug = f"{slug}-pin-{pin_index + 1}"
    raw_img = f"temp_raw_{iter_slug}.jpg"
    final_img = f"final_pin_{iter_slug}.jpg"
    
    # --- GENERATE PREMIUM CONTENT ---
    # Pass pin_index to guarantee unique overlays and descriptions per pin
    gemini_data = generate_pin_content_with_gemini(title, pin_index=pin_index)
    if gemini_data:
        p_title = gemini_data.get("title", title)
        p_desc = gemini_data.get("description", description)
        recipe_name = gemini_data.get("recipe_name", title)
        hook_text = gemini_data.get("hook", "")
        alt_text = gemini_data.get("alt_text", p_title)
        image_prompt = gemini_data.get("image_prompt")
        secondary_image_prompt = gemini_data.get("secondary_image_prompt")
    else:
        p_title, p_desc, recipe_name = title, description, title
        hook_text = ""
        alt_text = p_title
        image_prompt = None
        secondary_image_prompt = None

    # BOARD SELECTION LOGIC (Specialized - FoodTrendsBlog)
    board_mapping = {
        "dessert": os.getenv("PINTEREST_BOARD_DESSERTS") or "976859044115152346",
        "dinner": os.getenv("PINTEREST_BOARD_DINNER") or "976859044115152345",
        "trend": os.getenv("PINTEREST_BOARD_TRENDS") or "976859044115152343",
        "salad": os.getenv("PINTEREST_BOARD_SALADS") or "976859044115152344",
        "recipe": os.getenv("PINTEREST_BOARD_RECIPES") or "976859044115152343"
    }
    
    # Simple keyword matching
    t_lower = title.lower()
    board_key = "recipe"
    if any(k in t_lower for k in ["cake", "cookie", "dessert", "sweet", "chocolate", "crepe", "bake"]):
        board_key = "dessert"
    elif any(k in t_lower for k in ["dinner", "wrap", "pasta", "chicken", "meat", "main"]):
        board_key = "dinner"
    elif any(k in t_lower for k in ["salad", "healthy", "bowl", "chickpea", "vegan"]):
        board_key = "salad"
    elif any(k in t_lower for k in ["viral", "trending", "trend", "new"]):
        board_key = "trend"
    
    selected_board = board_mapping[board_key]
    
    if not image_prompt:
        image_prompt = f"{angle} of {title}"

    # 50% chance of attempting a two-image collage
    collage_mode = random.choice([True, False])
    sec_img = f"temp_raw_{iter_slug}_sec.jpg"
    sec_img_path = None

    if generate_image_master(image_prompt, raw_img):
        if collage_mode and secondary_image_prompt:
            print(f"   [Collage] Attempting to generate secondary image for collage variant...")
            if generate_image_master(secondary_image_prompt, sec_img):
                sec_img_path = sec_img
            else:
                print(f"   [Collage Warning] Secondary image generation failed. Falling back to extreme zoom.")

        design_pin_premium(raw_img, recipe_name, final_img, board_type=board_key, secondary_image_path=sec_img_path, hook_text=hook_text)
        b_url = _build_and_generate_bridge_url(slug, title, gemini_data, raw_img, url)
        if publish_pin(final_img, p_title, p_desc, b_url, selected_board, alt_text=alt_text):
            target["pin_count"] = pin_index + 1
            _save_queue(queue)
            
            # Log the pin timestamp for the 7-day cooldown safety protocol
            pin_log[url] = now
            _save_pin_log(pin_log)
            
            print(f"SUCCESS: Pin {pin_index + 1} published for {title}")
        else:
            print(f"FAILURE: Pinterest API rejected the pin (e.g. token expired) for {title}", flush=True)
            if os.path.exists(raw_img): os.remove(raw_img)
            if sec_img_path and os.path.exists(sec_img_path): os.remove(sec_img_path)
            import sys
            sys.exit(1)
            
        if os.path.exists(raw_img): os.remove(raw_img)
        if sec_img_path and os.path.exists(sec_img_path): os.remove(sec_img_path)
        if os.getenv("MOCK_MODE", "false").lower() != "true" and os.path.exists(final_img):
            os.remove(final_img)
    else:
        print(f"FAILURE: Could not generate image for {title}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trend")
    parser.add_argument("--worker", action="store_true", help="Run as a queue worker")
    args = parser.parse_args()
    
    if args.worker:
        run_pin_worker()
    elif args.trend:
        process_new_pin(args.trend, "cli-test", "https://google.com", "CLI Description", os.getenv("PINTEREST_BOARD_ID"))
