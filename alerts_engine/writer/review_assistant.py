"""
Review helper checks for warning-first editorial QA.
"""
import re

from database.db import is_topic_already_covered

EN_MARKERS = {"the", "and", "with", "from", "what", "where", "how", "recipe", "ingredients", "price", "availability"}
FR_MARKERS = {"le", "la", "les", "avec", "pour", "dans", "comment", "recette", "ingredients", "prix", "disponibilite"}


def _strip_html(text):
    clean = re.sub(r"<script[^>]*>.*?</script>", " ", text or "", flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<style[^>]*>.*?</style>", " ", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    return re.sub(r"\s+", " ", clean).strip().lower()


def _marker_hits(text, markers):
    hits = 0
    for m in markers:
        hits += len(re.findall(rf"\b{re.escape(m)}\b", text))
    return hits


def language_consistency(article):
    text = _strip_html(article.get("content", ""))
    en = _marker_hits(text, EN_MARKERS)
    fr = _marker_hits(text, FR_MARKERS)
    declared = (article.get("language") or "en").lower()

    mixed = en >= 6 and fr >= 6 and 0.6 <= (en / max(fr, 1)) <= 1.8
    mismatch = (declared == "en" and fr > en + 4) or (declared == "fr" and en > fr + 4)

    if mixed or mismatch:
        return False, f"Language warning (declared={declared}, EN hits={en}, FR hits={fr})"
    return True, f"Language looks consistent (declared={declared})"


def schema_presence(article):
    content = article.get("content", "")
    has_faq = bool(re.search(r'"@type"\s*:\s*"FAQPage"', content, flags=re.IGNORECASE))
    has_recipe = bool(re.search(r'"@type"\s*:\s*"Recipe"', content, flags=re.IGNORECASE))
    is_recipe_like = (article.get("category", "").lower() in {"recipes", "recettes"}) or bool((article.get("acf_fields") or {}).get("ingredients"))

    status = []
    status.append("FAQ schema: yes" if has_faq else "FAQ schema: no")
    if is_recipe_like:
        status.append("Recipe schema: present" if has_recipe else "Recipe schema: missing")
    else:
        status.append("Recipe schema: not required" if not has_recipe else "Recipe schema: present on non-recipe")

    ok = (not is_recipe_like or has_recipe)
    if not is_recipe_like and has_recipe:
        ok = False

    return ok, "; ".join(status)


def duplicate_risk(conn, topic_title, threshold=0.35):
    if not topic_title:
        return False, "No topic title"
    is_dup, dup_title, score = is_topic_already_covered(conn, topic_title, threshold=threshold)
    if is_dup:
        return True, f"Possible cannibalization: similar to '{dup_title[:70]}' (score {score:.2f})"
    return False, f"No strong duplicate detected (threshold {threshold:.2f})"


def rankmath_polylang_warnings(article):
    warnings = []
    lang = (article.get("language") or "").lower().strip()
    if lang not in {"en", "fr"}:
        warnings.append("Language should be 'en' or 'fr' for Polylang mapping.")

    slug = (article.get("slug") or "").strip()
    if not slug:
        warnings.append("Slug is empty.")
    elif slug != slug.lower() or " " in slug:
        warnings.append("Slug should be lowercase with hyphens only.")

    meta = (article.get("meta_description") or "").strip()
    if len(meta) < 120:
        warnings.append("Meta description looks too short for RankMath snippet quality.")

    focus_kw = (article.get("matched_keyword") or "").strip()
    tags = article.get("tags") or []
    if not focus_kw and not tags:
        warnings.append("No focus keyword/tags found for RankMath focus field fallback.")

    return warnings


def policy_warnings(article):
    checks = article.get("policy_checks") or {}
    warnings = list(checks.get("warnings") or [])
    if checks.get("block_publish"):
        warnings.append("Publish guard is active until sourcing/editorial issues are fixed.")
    return warnings


def build_preapproval_checklist(article, topic, conn=None, duplicate_warning=None):
    sources = [s for s in (article.get("sources_used") or []) if s and s != "aggregated_summaries"]
    src_count = len(set(sources))
    words = int(article.get("word_count") or len(_strip_html(article.get("content", "")).split()))
    policy_checks = article.get("policy_checks") or {}
    source_quality = policy_checks.get("source_quality") or {}
    trusted_count = int(source_quality.get("trusted_unique_count") or 0)
    policy_notes = policy_warnings(article)

    lang_ok, lang_msg = language_consistency(article)
    schema_ok, schema_msg = schema_presence(article)

    lines = [
        "Pre-approval checklist",
        f"- Sources used: {src_count}",
        f"- Trusted source domains: {trusted_count}",
        f"- Word count: {words}",
        f"- {lang_msg}",
        f"- {schema_msg}",
    ]

    if duplicate_warning:
        lines.append(f"- {duplicate_warning}")

    if src_count < 2:
        lines.append("- Warning: low source diversity (<2 domains)")
    for warning in policy_notes[:5]:
        lines.append(f"- Warning: {warning}")
    if not lang_ok:
        lines.append("- Warning: language consistency needs review")
    if not schema_ok:
        lines.append("- Warning: schema issue detected")

    return "\n".join(lines)
