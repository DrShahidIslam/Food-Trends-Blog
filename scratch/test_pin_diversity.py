import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from pinterest_engine.pin_generator import generate_pin_content_with_gemini

test_topics = [
    "Crispy Air Fryer Buffalo Chicken Tenders",
    "Slow Cooker Creamy Chicken and Wild Rice Soup",
    "Brown Butter Sea Salt Toffee Chocolate Chip Cookies",
    "Cheesy Hot Roast Beef and Cheddar Hawaiian Roll Sliders"
]

print("--- TESTING DIVERSIFIED PIN CONTENT GENERATION ---\n")
for i, topic in enumerate(test_topics):
    res = generate_pin_content_with_gemini(topic, pin_index=0)
    if res:
        print(f"Topic: {topic}")
        print(f"Title: {res.get('title')}")
        print(f"Hook:  {res.get('hook')}")
        print(f"Desc:  {res.get('description')[:110]}...")
        print("-" * 65)
    else:
        print(f"Failed for topic: {topic}")
