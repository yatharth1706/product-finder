"""Turns differently written product text into one comparable form.

Every function here is pure, so the same rules apply to Amazon and to every marketplace.
"""

import re

BRAND_ALIASES = {
    "mi": "xiaomi",
    "redmi": "xiaomi",
}

# Words in titles that describe the product but are not part of the model name.
TITLE_NOISE_WORDS = {"5g", "4g", "ai", "smartphone", "mobile", "dual", "sim", "new", "android"}

# "Samsung Galaxy S24 Ultra" and "Samsung S24 Ultra" are the same model.
MODEL_FILLER_WORDS = TITLE_NOISE_WORDS | {"galaxy"}

# A short bracket with a digit is part of the model: the "(3a)" in "Nothing Phone (3a)".
# Any other bracket, like "(Black, 8GB, 256GB)" or "(128 GB)", holds details.
MODEL_BRACKET = re.compile(r"\((?=[a-z]*\d)([a-z0-9]{1,4})\)", re.I)

SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(gb|tb|mb|gigabytes?|terabytes?)\b", re.I)


def normalize_text(text: str) -> str:
    text = text.lower().replace("+", " plus ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_brand(brand: str) -> str:
    brand = normalize_text(brand)
    return BRAND_ALIASES.get(brand, brand)


def normalize_size(text: str) -> str | None:
    """'12GB', '12 gb RAM', '12 Gigabytes' -> '12 GB'. Returns None if no size is present."""
    match = SIZE_PATTERN.search(text)
    if not match:
        return None
    number = match.group(1).removesuffix(".0")
    unit = match.group(2).lower()
    unit = {"gigabyte": "gb", "gigabytes": "gb", "terabyte": "tb", "terabytes": "tb"}.get(
        unit, unit
    )
    return f"{number} {unit.upper()}"


def find_sizes(text: str) -> list[str]:
    """All storage-like sizes in a text, normalized, in order of appearance."""
    return [s for m in SIZE_PATTERN.finditer(text) if (s := normalize_size(m.group(0)))]


def size_in_gb(size: str) -> float:
    number, unit = size.split()
    return float(number) * {"MB": 1 / 1024, "GB": 1, "TB": 1024}[unit]


def model_from_title(title: str, brand: str) -> str:
    """Take the model name out of a listing title, keeping its original casing.

    The model is the start of the title, after the brand and before the first
    bracket, separator or 'with': 'REDMI Turbo 5 (8GB + 256GB) | ...' -> 'Turbo 5'.
    """
    title = MODEL_BRACKET.sub(r" \1 ", title)
    head = re.split(r"[(|,\[]| with | - ", title, maxsplit=1)[0]
    words = head.split()
    brand_words = normalize_text(brand).split()
    if [normalize_text(w) for w in words[: len(brand_words)]] == brand_words:
        words = words[len(brand_words) :]
    elif words and normalize_brand(words[0]) == normalize_brand(brand):
        words = words[1:]
    return " ".join(w for w in words if normalize_text(w) not in TITLE_NOISE_WORDS)


def model_tokens(model: str) -> set[str]:
    """Identifying words of a model, with letters and digits split apart.

    'Galaxy S24 Ultra 5G' -> {'s', '24', 'ultra'}; 'Nord CE6' -> {'nord', 'ce', '6'}.
    """
    tokens = set()
    for word in normalize_text(model).split():
        if word in MODEL_FILLER_WORDS:
            continue
        tokens.update(re.findall(r"[a-z]+|\d+(?:\.\d+)?", word))
    return tokens
