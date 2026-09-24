"""Brand removal for single-SKU M.Video listings.

Every single-SKU upload uses M.Video's no-brand value. Brand words are removed
from title/description, while an exact model code is protected and retained.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

NO_BRAND = "Нет бренда"
MODEL_PLACEHOLDER = "\x00SINGLE_SKU_MODEL\x00"

NO_BRAND_TERMS = {
    "без бренда",
    "нет бренда",
    "no brand",
    "unbranded",
    "none",
    "null",
    "undefined",
    "generic",
}
BRAND_MARKER_WORDS = {
    "бренд",
    "brand",
    "торговая марка",
    "торгова марка",
    "тм",
    "tm",
}
CORPORATE_WORDS = {
    "inc",
    "ltd",
    "co",
    "corp",
    "corporation",
    "company",
    "gmbh",
    "llc",
    "ooo",
    "ооо",
    "зао",
    "оао",
    "пао",
}
KNOWN_BRANDS = [
    "apple",
    "iphone",
    "ipad",
    "samsung",
    "xiaomi",
    "redmi",
    "huawei",
    "honor",
    "realme",
    "oppo",
    "vivo",
    "lenovo",
    "nokia",
    "sony",
    "lg",
    "philips",
    "bosch",
    "makita",
    "dewalt",
    "baseus",
    "anker",
    "jbl",
    "dyson",
    "siemens",
    "electrolux",
    "tefal",
    "polaris",
    "redmond",
    "kitfort",
    "эппл",
    "айфон",
    "самсунг",
    "ксиаоми",
    "хуавей",
    "хонор",
    "реалми",
    "оппо",
    "виво",
    "леново",
    "нокиа",
    "сони",
    "элджи",
    "филипс",
    "бош",
    "макита",
    "деволт",
    "базеус",
    "анкер",
    "сименс",
    "электролюкс",
    "тефаль",
    "поларис",
    "редмонд",
    "китфорт",
]


@dataclass
class SanitizationResult:
    brand: str = NO_BRAND
    title: str = ""
    description: str = ""
    model: str = ""
    removed_terms: list[str] = field(default_factory=list)
    detected_brands: list[str] = field(default_factory=list)
    title_brand_mentions: int = 0
    description_brand_mentions: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "brand": self.brand,
            "title": self.title,
            "description": self.description,
            "model": self.model,
            "removed_terms": self.removed_terms,
            "detected_brands": self.detected_brands,
            "title_brand_mentions": self.title_brand_mentions,
            "description_brand_mentions": self.description_brand_mentions,
            "warnings": self.warnings,
        }


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strip_html(text: Any) -> str:
    raw = str(text or "")
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?</style>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return _normalize_spaces(raw)


def _clean_candidate(text: str) -> str:
    cleaned = text.lower()
    cleaned = re.sub(r"[®™©]", " ", cleaned)
    for word in tuple(BRAND_MARKER_WORDS) + tuple(CORPORATE_WORDS):
        cleaned = re.sub(rf"(?<![a-zа-яё0-9]){re.escape(word)}(?![a-zа-яё0-9])", " ", cleaned)
    cleaned = re.sub(r"[^0-9a-zа-яё\s&'.-]", " ", cleaned)
    return _normalize_spaces(cleaned)


def brand_candidates(source_brand: Any) -> list[str]:
    """Extract exact brand terms while ignoring no-brand and legal markers."""
    candidates: list[str] = []

    def add(value: str) -> None:
        cleaned = _clean_candidate(value)
        if not cleaned or cleaned in NO_BRAND_TERMS:
            return
        if cleaned not in candidates:
            candidates.append(cleaned)

    raw = str(source_brand or "").strip()
    if raw:
        add(raw)
        for part in re.split(r"[|/,;]+", raw):
            add(part)
    for known in KNOWN_BRANDS:
        if known not in candidates:
            candidates.append(known)
    return sorted(candidates, key=lambda item: (-len(item), item))


def _brand_pattern(terms: list[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(term) for term in terms)
    return re.compile(
        rf"(?<![0-9A-Za-zА-Яа-яЁё])(?:{alternatives})(?![0-99A-Za-zА-Яа-яЁё])",
        flags=re.IGNORECASE,
    )


def _protect_model(text: str, model: str) -> str:
    model_text = str(model or "").strip()
    if not model_text:
        return text
    return re.sub(re.escape(model_text), MODEL_PLACEHOLDER, text, flags=re.IGNORECASE)


def _remove_brands(text: str, pattern: re.Pattern[str], terms: list[str]) -> tuple[str, int, list[str]]:
    found: list[str] = []

    def repl(match: re.Match[str]) -> str:
        value = match.group(0).strip()
        key = value.lower()
        if key not in found:
            found.append(key)
        return " "

    new_text, count = pattern.subn(repl, text)
    return new_text, count, found


def _clean_punctuation(text: str) -> str:
    text = _normalize_spaces(text)
    text = re.sub(r"\s+([,.!?;:()])", r"\1", text)
    text = re.sub(r"([,.!?;:()])\1+", r"\1", text)
    text = re.sub(r"\(\s*\)", " ", text)
    text = re.sub(r"(?<![\d.])[.,;](?![\d.])", " ", text)
    text = re.sub(r"\s*[-–]\s*", " - ", text)
    text = re.sub(r"([-])\1+", r"\1", text)
    text = re.sub(r"^[\s,.\-:;!?()]+", "", text)
    return _normalize_spaces(text)


def sanitize_listing(
    title: Any,
    description: Any = "",
    source_brand: Any = "",
    model: Any = "",
) -> SanitizationResult:
    """Remove brand content and return a quality report."""
    model_text = str(model or "").strip()
    title_text = _normalize_spaces(strip_html(title))
    description_text = strip_html(description)
    title_text = _protect_model(title_text, model_text)
    description_text = _protect_model(description_text, model_text)

    terms = brand_candidates(source_brand)
    pattern = _brand_pattern(terms)
    title_text, title_count, title_found = _remove_brands(title_text, pattern, terms)
    description_text, desc_count, desc_found = _remove_brands(description_text, pattern, terms)

    title_text = title_text.replace(MODEL_PLACEHOLDER, model_text)
    description_text = description_text.replace(MODEL_PLACEHOLDER, model_text)
    title_text = _clean_punctuation(title_text)
    description_text = _clean_punctuation(description_text)

    detected = title_found + [item for item in desc_found if item not in title_found]
    remaining = [term for term in terms if pattern.search(title_text) or pattern.search(description_text)]
    warnings: list[str] = []
    source_clean = _clean_candidate(source_brand)
    if source_clean and source_clean not in NO_BRAND_TERMS and source_clean not in terms:
        warnings.append("来源品牌未识别，需要人工复核标题和描述")
    if remaining:
        warnings.append("净化后仍检测到品牌内容：" + ", ".join(remaining))
    if not title_text:
        warnings.append("品牌清除后标题为空，需要人工补充型号或品类词")

    return SanitizationResult(
        title=title_text,
        description=description_text,
        model=model_text,
        removed_terms=detected,
        detected_brands=detected,
        title_brand_mentions=title_count,
        description_brand_mentions=desc_count,
        warnings=warnings,
    )
