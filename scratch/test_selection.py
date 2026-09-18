import sys, re, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pinterest_engine.pin_generator import _load_queue, _load_pin_log
from alerts_engine.sources.seasonal_calendar import get_active_seasonal_themes

q = _load_queue()
p = _load_pin_log()
active_themes = get_active_seasonal_themes()
seasonal_keywords = set()
for t in active_themes:
    for kw in t.get("keywords", []):
        seasonal_keywords.add(kw.lower())

now = datetime.datetime.now().timestamp()
cooldown = 20 * 24 * 3600

eligible = [
    t for t in q 
    if t.get("wp_status") == "done" 
    and t.get("pin_count", 0) < 3 
    and (now - p.get(t.get("wp_url", ""), 0)) >= cooldown
]

def score(item):
    title = item.get("topic", "").lower()
    s = 0
    if any(re.search(r"\b" + re.escape(kw) + r"\b", title) for kw in seasonal_keywords):
        s += 150
    pc = item.get("pin_count", 0)
    s += 100 if pc == 0 else (3 - pc) * 15
    if item.get("priority", 99) == 1:
        s += 50
    return s

eligible.sort(key=score, reverse=True)
print(f"Total eligible posts (>20-day cooldown): {len(eligible)}")
print("\nTop 5 topics prioritized for upcoming pins:")
for i, t in enumerate(eligible[:5]):
    print(f"{i+1}. {t['topic']} (Score: {score(t)}, Pins: {t.get('pin_count', 0)}, URL: {t.get('wp_url')})")
