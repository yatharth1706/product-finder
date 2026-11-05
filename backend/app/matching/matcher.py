"""Decides whether a marketplace listing is exactly the Amazon product.

Rules:
1. Brand must be the same.
2. Model must be the same: identical numbers and variant words (Pro, Ultra, ...),
   and a high fuzzy similarity for everything else.
3. Every required attribute of the category must be present on both sides and equal.
   A missing value is a failed check, never a pass.
The score only ranks listings that already passed every check.
"""

from rapidfuzz import fuzz

from app.matching.normalizer import (
    model_from_title,
    model_tokens,
    normalize_brand,
    normalize_size,
    normalize_text,
)
from app.schemas import REQUIRED_ATTRIBUTES, Candidate, MatchResult, Product

BRAND_WEIGHT = 25
MODEL_WEIGHT = 35
ATTRIBUTES_WEIGHT = 40
MODEL_SIMILARITY_THRESHOLD = 92

# Words that turn one model into a different one: "S24" vs "S24 Ultra".
VARIANT_WORDS = {
    "pro", "plus", "max", "ultra", "mini", "lite", "fe", "neo", "prime",
    "edge", "fold", "flip", "note", "se", "air",
}  # fmt: skip

ATTRIBUTE_LABELS = {"ram": "RAM", "storage": "Storage", "screen_size": "Screen size"}


def match(source: Product, candidate: Candidate) -> MatchResult:
    checks: dict[str, bool] = {}
    reasons: list[str] = []
    score = 0.0

    checks["brand"] = brand_matches(source.brand, candidate)
    if checks["brand"]:
        score += BRAND_WEIGHT
    else:
        reasons.append(f"Brand mismatch: expected {source.brand}, found '{candidate.title}'")

    candidate_model = model_from_title(candidate.title, candidate.brand or source.brand)
    model_ok, similarity, model_reason = compare_models(source.model, candidate_model)
    checks["model"] = model_ok
    if model_ok:
        score += MODEL_WEIGHT * similarity / 100
    else:
        reasons.append(model_reason)

    required = REQUIRED_ATTRIBUTES[source.category]
    for name in required:
        expected = normalize_attribute(name, source.attributes.get(name))
        found = normalize_attribute(name, candidate.attributes.get(name))
        label = ATTRIBUTE_LABELS.get(name, name.capitalize())
        checks[name] = expected is not None and expected == found
        if checks[name]:
            score += ATTRIBUTES_WEIGHT / len(required)
        elif expected is None:
            reasons.append(f"{label} missing on Amazon product")
        elif found is None:
            reasons.append(f"{label} missing on listing")
        else:
            reasons.append(f"{label} mismatch: expected {expected}, found {found}")

    return MatchResult(
        matched=all(checks.values()), score=round(score), checks=checks, reasons=reasons
    )


def brand_matches(source_brand: str, candidate: Candidate) -> bool:
    expected = normalize_brand(source_brand)
    if candidate.brand:
        return normalize_brand(candidate.brand) == expected
    # No brand field: listing titles start with the brand ("REDMI Turbo 5 5G ...").
    title = normalize_text(candidate.title)
    brand_text = normalize_text(source_brand)
    first_word = title.split(" ", 1)[0]
    return title.startswith(brand_text + " ") or normalize_brand(first_word) == expected


def compare_models(expected: str, found: str) -> tuple[bool, float, str]:
    """Returns (matched, similarity 0-100, reason if not matched)."""
    expected_tokens, found_tokens = model_tokens(expected), model_tokens(found)
    if not found_tokens:
        return False, 0.0, f"Model missing on listing: expected {expected}"

    similarity = fuzz.ratio(" ".join(sorted(expected_tokens)), " ".join(sorted(found_tokens)))

    expected_numbers = {t for t in expected_tokens if t[0].isdigit()}
    found_numbers = {t for t in found_tokens if t[0].isdigit()}
    if expected_numbers != found_numbers:
        return False, similarity, f"Model mismatch: expected {expected}, found {found}"

    if expected_tokens & VARIANT_WORDS != found_tokens & VARIANT_WORDS:
        return False, similarity, f"Model variant mismatch: expected {expected}, found {found}"

    if similarity < MODEL_SIMILARITY_THRESHOLD:
        return False, similarity, f"Model mismatch: expected {expected}, found {found}"

    return True, similarity, ""


def normalize_attribute(name: str, value: str | None) -> str | None:
    if not value:
        return None
    if name in ("ram", "storage"):
        return normalize_size(value)
    return normalize_text(value) or None


def rank_matches(
    source: Product, candidates: list[Candidate]
) -> list[tuple[Candidate, MatchResult]]:
    """Only the listings that are exactly the product, best score first.

    Ties keep the marketplace's own order, which is usually its relevance order.
    """
    results = [(candidate, match(source, candidate)) for candidate in candidates]
    exact = [(candidate, result) for candidate, result in results if result.matched]
    return sorted(exact, key=lambda pair: pair[1].score, reverse=True)
