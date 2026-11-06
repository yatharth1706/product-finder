"""Decides whether a marketplace listing is exactly the Amazon product.

Rules:
1. Brand must be the same.
2. Model must be the same. Televisions compare manufacturer model numbers exactly.
   Everything else compares model names: identical numbers and variant words
   (Pro, Ultra, ...), the same gender when both say one, and a high fuzzy similarity.
3. Every required attribute of the category must be present on both sides and equal.
   A missing value is a failed check, never a pass.
The score only ranks listings that already passed every check.
"""

from rapidfuzz import fuzz

from app.matching.normalizer import (
    colours_match,
    gender_of,
    model_from_title,
    model_tokens,
    normalize_brand,
    normalize_model_number,
    normalize_screen_size,
    normalize_size,
    normalize_text,
)
from app.schemas import REQUIRED_ATTRIBUTES, Candidate, Category, MatchResult, Product

BRAND_WEIGHT = 25
MODEL_WEIGHT = 35
ATTRIBUTES_WEIGHT = 40
MODEL_SIMILARITY_THRESHOLD = 92

# Model names are shared across sizes and years, so only the model number identifies a TV.
MODEL_NUMBER_CATEGORIES = {Category.TELEVISION}

# Words that turn one model into a different one: "S24" vs "S24 Ultra".
VARIANT_WORDS = {
    "pro", "plus", "max", "ultra", "mini", "lite", "fe", "neo", "prime",
    "edge", "fold", "flip", "note", "se", "air",
}  # fmt: skip

ATTRIBUTE_LABELS = {
    "ram": "RAM",
    "storage": "Storage",
    "screen_size": "Screen size",
    "colour": "Colour",
}

ATTRIBUTE_NORMALIZERS = {
    "ram": normalize_size,
    "storage": normalize_size,
    "screen_size": normalize_screen_size,
}


def match(source: Product, candidate: Candidate) -> MatchResult:
    checks: dict[str, bool] = {}
    reasons: list[str] = []
    score = 0.0

    checks["brand"] = brand_matches(source.brand, candidate)
    if checks["brand"]:
        score += BRAND_WEIGHT
    else:
        reasons.append(f"Brand mismatch: expected {source.brand}, found '{candidate.title}'")

    if source.category in MODEL_NUMBER_CATEGORIES:
        model_ok, similarity, model_reason = compare_model_numbers(
            source.model, candidate.model_number
        )
    else:
        model_ok, similarity, model_reason = compare_models(
            source.model,
            model_from_title(candidate.title, candidate.brand or source.brand),
            gender_of(source.title),
            gender_of(candidate.title),
        )
    checks["model"] = model_ok
    if model_ok:
        score += MODEL_WEIGHT * similarity / 100
    else:
        reasons.append(model_reason)

    required = REQUIRED_ATTRIBUTES[source.category]
    for name in required:
        ok, reason = compare_attribute(
            name, source.attributes.get(name), candidate.attributes.get(name)
        )
        checks[name] = ok
        if ok:
            score += ATTRIBUTES_WEIGHT / len(required)
        else:
            reasons.append(reason)

    return MatchResult(
        matched=all(checks.values()), score=round(score), checks=checks, reasons=reasons
    )


def may_match(source: Product, candidate: Candidate) -> bool:
    """True if the listing could still be an exact match once its missing details are known.

    Used to decide which product pages are worth opening.
    """
    result = match(source, candidate)
    failed = [name for name, ok in result.checks.items() if not ok]
    return all(
        name in REQUIRED_ATTRIBUTES[source.category] and not candidate.attributes.get(name)
        for name in failed
    )


def rank_matches(
    source: Product, candidates: list[Candidate]
) -> list[tuple[Candidate, MatchResult]]:
    """Only the listings that are exactly the product, best score first.

    Ties keep the marketplace's own order, which is usually its relevance order.
    """
    results = [(candidate, match(source, candidate)) for candidate in candidates]
    exact = [(candidate, result) for candidate, result in results if result.matched]
    return sorted(exact, key=lambda pair: pair[1].score, reverse=True)


def brand_matches(source_brand: str, candidate: Candidate) -> bool:
    expected = normalize_brand(source_brand)
    if candidate.brand:
        return normalize_brand(candidate.brand) == expected
    # No brand field: listing titles start with the brand ("REDMI Turbo 5 5G ...").
    title = normalize_text(candidate.title)
    brand_text = normalize_text(source_brand)
    first_word = title.split(" ", 1)[0]
    return title.startswith(brand_text + " ") or normalize_brand(first_word) == expected


def compare_models(
    expected: str,
    found: str,
    expected_gender: str | None = None,
    found_gender: str | None = None,
) -> tuple[bool, float, str]:
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

    if (
        expected_gender
        and found_gender
        and "unisex" not in (expected_gender, found_gender)
        and expected_gender != found_gender
    ):
        return (
            False,
            similarity,
            f"Gender mismatch: expected {expected_gender}, found {found_gender}",
        )

    if similarity < MODEL_SIMILARITY_THRESHOLD:
        return False, similarity, f"Model mismatch: expected {expected}, found {found}"

    return True, similarity, ""


# Some stores list a shortened model number: Croma writes 43NU870 for LG's 43NU870BPLA.
MIN_SHORT_MODEL_NUMBER = 7


def compare_model_numbers(expected: str, found: str | None) -> tuple[bool, float, str]:
    """Identical, or one is a shortened form that the other starts with."""
    if not found:
        return False, 0.0, f"Model number missing on listing: expected {expected}"
    a, b = normalize_model_number(expected), normalize_model_number(found)
    shorter, longer = sorted((a, b), key=len)
    if a == b or (len(shorter) >= MIN_SHORT_MODEL_NUMBER and longer.startswith(shorter)):
        return True, 100.0, ""
    return False, 0.0, f"Model number mismatch: expected {expected}, found {found}"


def compare_attribute(name: str, expected: str | None, found: str | None) -> tuple[bool, str]:
    label = ATTRIBUTE_LABELS.get(name, name.capitalize())
    if not expected:
        return False, f"{label} missing on Amazon product"
    if not found:
        return False, f"{label} missing on listing"

    if name == "colour":
        ok = colours_match(expected, found)
    else:
        normalize = ATTRIBUTE_NORMALIZERS.get(name, normalize_text)
        expected, found = normalize(expected) or expected, normalize(found) or found
        ok = expected == found
    return ok, "" if ok else f"{label} mismatch: expected {expected}, found {found}"
