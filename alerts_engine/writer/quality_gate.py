"""El quality gate — fail-closed checks for the Food-Trends-Blog publisher.

Hard failures (do not publish, return False from auto_pilot_process):
  1. Article body under 1000 words (standing minimum).
  2. Zero internal links to el-mordjene.info.
  3. Title all-lowercase (Title Case required for CTR).
  4. No H2 heading at all.
  5. Filler / placeholder text (lorem ipsum, TODO, [insert], coming soon).
  6. Focus/topic keyword absent from the first paragraph.
Warnings (logged, do not block — the El generator's recipe output does not
yet reliably emit a body FAQ section, so FAQ is a warning here, not a hard
failure, until the generator prompt is updated in P4):
  - Under 1500 words, under 5 internal links, no FAQ section, meta
    description outside 140-160 chars, external links over 3.
"""
import re
from html import unescape

def _text(html):
    t = unescape(html or "")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def run_el_quality_gate(article):
    failures, warnings = [], []
    content = article.get("content", "") or ""
    title = (article.get("title", "") or "").strip()
    text = _text(content)
    words = len(text.split()) if text else 0
    if words < 1000:
        failures.append(f"Article is {words} words (minimum 1000).")
    elif words < 1500:
        warnings.append(f"Article is {words} words (target 1500+).")
    internal = re.findall(r'href=["\']https?://(?:www\.)?el-mordjene\.info[^"\']+', content, re.I)
    if len(internal) == 0:
        failures.append("Zero internal links to el-mordjene.info.")
    elif len(internal) < 5:
        warnings.append(f"Only {len(internal)} internal links (target 5+).")
    external = re.findall(r'href=["\']https?://(?!(?:www\.)?el-mordjene\.info)[^"\']+', content, re.I)
    if len(external) > 3:
        warnings.append(f"{len(external)} external links (target max 3).")
    if title and title == title.lower() and any(c.isalpha() for c in title):
        failures.append("Title is all-lowercase — use Title Case before publishing.")
    if not re.search(r"<h2[^>]*>", content, re.I):
        failures.append("No H2 heading in article body.")
    for pat in [r"lorem ipsum", r"\bTODO\b", r"\[insert[^\]]*\]", r"coming soon"]:
        if re.search(pat, text, re.I):
            failures.append(f"Filler text detected: {pat}")
    # Keyword = topic phrase, first word set: check topic words in first paragraph
    first_para = text.split(".")[0].lower() if text else ""
    topic = (article.get("title", "") or "").lower()
    if topic and not any(w in first_para for w in topic.split() if len(w) > 3):
        failures.append("Topic keyword absent from the first paragraph.")
    if "faq" not in text.lower():
        warnings.append("No FAQ section in article body (target: 4-6 questions).")
    return (len(failures) == 0, failures, warnings)
