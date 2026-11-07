"""Turns differently written product text into one comparable form.

Every function here is pure, so the same rules apply to Amazon and to every marketplace.
"""

import re

BRAND_ALIASES = {
    "mi": "xiaomi",
    "redmi": "xiaomi",
}

GENDER_WORDS = {
    "men": "men", "mens": "men", "man": "men", "male": "men", "boys": "men",
    "women": "women", "womens": "women", "woman": "women", "female": "women",
    "ladies": "women", "girls": "women",
    "unisex": "unisex",
}  # fmt: skip

# Words in titles that describe the product but are not part of the model name.
TITLE_NOISE_WORDS = {
    "5g", "4g", "ai", "smartphone", "mobile", "dual", "sim", "new", "android",
    "for", "shoes", "shoe", "sneakers", "sneaker", "running", "casual", "sports", "sport",
    "walking", "training", "trainers", "polo", "polos", "tshirt", "tshirts", "tee", "tees",
    "jersey", "jerseys",
} | set(GENDER_WORDS)  # fmt: skip

# "Samsung Galaxy S24 Ultra" and "Samsung S24 Ultra" are the same model.
MODEL_FILLER_WORDS = TITLE_NOISE_WORDS | {"galaxy"}

# Abbreviations brands use in model names: Puma writes "Essentials" as "ESS".
MODEL_WORD_ALIASES = {"ess": "essential", "essentials": "essential"}

# A short bracket with a digit is part of the model: the "(3a)" in "Nothing Phone (3a)".
# Any other bracket, like "(Black, 8GB, 256GB)" or "(128 GB)", holds details.
MODEL_BRACKET = re.compile(r"\((?=[a-z]*\d)([a-z0-9]{1,4})\)", re.I)

SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(gb|tb|mb|gigabytes?|terabytes?)\b", re.I)
INCH_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:inches|inch|in\b|\"|”)", re.I)
CM_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*cm\b", re.I)

# Colour words -> the basic colour they belong to. Stores name colours freely
# ("Wolf Grey", "Desert Dust", "Titanium Gray"), but the basic colour is stable.
COLOUR_FAMILIES = {
    "black": "black", "jet": "black", "onyx": "black", "ebony": "black",
    "white": "white", "ivory": "white",
    "grey": "grey", "gray": "grey", "silver": "grey", "charcoal": "grey", "slate": "grey",
    "ash": "grey", "smoke": "grey", "graphite": "grey", "steel": "grey",
    "blue": "blue", "navy": "blue", "teal": "blue", "turquoise": "blue", "aqua": "blue",
    "cobalt": "blue", "indigo": "blue", "denim": "blue",
    "green": "green", "olive": "green", "mint": "green", "emerald": "green", "sage": "green",
    "lime": "green",
    "red": "red", "maroon": "red", "burgundy": "red", "wine": "red", "crimson": "red",
    "scarlet": "red", "cherry": "red",
    "pink": "pink", "rose": "pink", "fuchsia": "pink", "magenta": "pink", "peach": "pink",
    "purple": "purple", "violet": "purple", "lavender": "purple", "lilac": "purple",
    "mauve": "purple", "plum": "purple",
    "yellow": "yellow", "mustard": "yellow", "lemon": "yellow", "gold": "yellow",
    "orange": "orange", "rust": "orange", "coral": "orange",
    "brown": "brown", "tan": "brown", "chocolate": "brown", "coffee": "brown",
    "mocha": "brown", "camel": "brown", "gum": "brown", "cognac": "brown", "hazel": "brown",
    "sail": "white", "platinum": "grey",
    "beige": "beige", "sand": "beige", "khaki": "beige", "desert": "beige", "dust": "beige",
    "stone": "beige", "cream": "beige", "nude": "beige", "taupe": "beige",
    "multicolor": "multi", "multicolour": "multi", "multi": "multi",
    # adidas writes colours as codes: "CBLACK/FTWWHT", "CGRANI/GRESIX".
    "cblack": "black", "ftwwht": "white", "cwhite": "white", "gresix": "grey",
    "grefiv": "grey", "grefou": "grey", "grethr": "grey", "gretwo": "grey", "greone": "grey",
    "cgrani": "grey", "carbon": "grey", "silvmt": "grey", "conavy": "blue", "legink": "blue",
    "scarle": "red",
    # Short colour codes several brands use (Skechers "MVE", "BKW", "NVY").
    "blk": "black", "wht": "white", "gry": "grey", "nvy": "blue", "blu": "blue",
    "grn": "green", "brn": "brown", "pnk": "pink", "mve": "purple", "lav": "purple",
    "prp": "purple", "ylw": "yellow", "org": "orange", "slt": "grey", "char": "grey",
}  # fmt: skip


def normalize_text(text: str) -> str:
    text = text.lower().replace("+", " plus ")
    text = re.sub(r"['’]s\b", "s", text)  # men's -> mens
    text = re.sub(r"\bt[\s-]?shirts?\b", "tshirt", text)
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_brand(brand: str) -> str:
    """Spaces are dropped so 'One Plus' and 'OnePlus' compare equal."""
    brand = normalize_text(brand).replace(" ", "")
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


def normalize_screen_size(text: str) -> str | None:
    """'55 Inches', '138 cm (55 inch)', '139.7 cm - 55 inch' -> '55 inch'.

    Inches are preferred because centimetre values are rounded differently by each store.
    """
    if match := INCH_PATTERN.search(text):
        inches = float(match.group(1))
    elif match := CM_PATTERN.search(text):
        inches = float(match.group(1)) / 2.54
    else:
        return None
    return f"{int(inches + 0.5)} inch"


def normalize_model_number(code: str) -> str:
    """'UA55UE85AHULXL', 'ua-55ue85ahulxl' -> 'UA55UE85AHULXL'."""
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def gender_of(title: str) -> str | None:
    """'men', 'women', 'unisex', or None when the title does not say."""
    genders = {GENDER_WORDS[w] for w in normalize_text(title).split() if w in GENDER_WORDS}
    if "unisex" in genders or genders == {"men", "women"}:
        return "unisex"
    return genders.pop() if genders else None


def first_word(text: str) -> str:
    words = normalize_text(text).split()
    return words[0] if words else ""


def colour_families(colour: str) -> list[str]:
    """Basic colours in order: 'WHITE/BLACK-WOLF GREY' -> ['white', 'black', 'grey']."""
    families: list[str] = []
    for word in normalize_text(colour).split():
        family = COLOUR_FAMILIES.get(word)
        if family and family not in families:
            families.append(family)
    return families


def colours_match(expected: str, found: str) -> bool:
    """Same main colour, and the same set of colours when both sides list several.

    'White/Black-Wolf Grey' matches 'White' but not 'White/Emerald Green-Gum Brown'.
    Colours with no known colour word match only on the same main colour word.
    """
    if normalize_text(expected) == normalize_text(found):
        return True
    expected_families, found_families = colour_families(expected), colour_families(found)
    if not expected_families or not found_families:
        # Brand colour names we do not know ("SHIMMER/LT COGNAC-SAIL" vs "Shimmer"):
        # fall back to the same main colour word.
        return first_word(expected) == first_word(found) != ""
    if expected_families[0] != found_families[0]:
        return False
    if len(expected_families) > 1 and len(found_families) > 1:
        return set(expected_families) == set(found_families)
    return True


def model_from_title(title: str, brand: str) -> str:
    """Take the model name out of a listing title, keeping its original casing.

    The model is the start of the title, after the brand and before the first
    bracket, separator or 'with': 'REDMI Turbo 5 (8GB + 256GB) | ...' -> 'Turbo 5'.
    """
    title = MODEL_BRACKET.sub(r" \1 ", title)
    # Cut at the first bracket, separator, "with" or size ("Nord CE6 5G 256 GB, ...").
    head = re.split(
        r"[(|,\[]| with | - | – | — |\b\d+\s*(?:GB|TB)\b", title, maxsplit=1, flags=re.I
    )[0]
    words = head.split()
    brand_words = normalize_text(brand).split()
    if [normalize_text(w) for w in words[: len(brand_words)]] == brand_words:
        words = words[len(brand_words) :]
    elif words and normalize_brand(words[0]) == normalize_brand(brand):
        words = words[1:]
    return " ".join(w for w in words if normalize_text(w) not in TITLE_NOISE_WORDS)


# Words that describe a garment rather than name it. Clothing names are mostly these
# ("Men Solid Polo Neck Pure Cotton Slim Fit T-Shirt"); the identifying words are the rest.
CLOTHING_DESCRIPTION_WORDS = {
    "round", "neck", "crew", "collar", "collared", "henley", "hooded", "zip",
    "slim", "regular", "relaxed", "oversized", "fit", "fitted", "comfort",
    "cotton", "pure", "blend", "polyester", "viscose", "linen", "dri", "dry",
    "solid", "plain", "printed", "print", "striped", "stripes", "colorblock",
    "colourblock", "self", "design", "pattern", "half", "full", "short", "long",
    "sleeve", "sleeves", "sleeveless", "premium", "soft", "lightweight", "breathable",
    "wear", "everyday", "football", "cricket", "gym", "top", "jsy", "replica",
    "x", "and", "with", "the", "of",
    "xs", "s", "m", "l", "xl", "xxl", "xxxl", "2xl", "3xl", "4xl",
} | set(COLOUR_FAMILIES)  # fmt: skip


def clothing_tokens(text: str) -> set[str]:
    """Identifying words of a clothing name: model tokens minus description, sizes and
    colours. 'TIRO 23 JSY Printed T-Shirt' -> {'tiro', '23'}."""
    words = [w for w in normalize_text(text).split() if w not in CLOTHING_DESCRIPTION_WORDS]
    return model_tokens(" ".join(words))


def clothing_name(text: str) -> str:
    """A clothing name without description words, for searching: keeps original casing."""
    return " ".join(
        w
        for w in text.split()
        if normalize_text(w) not in CLOTHING_DESCRIPTION_WORDS | TITLE_NOISE_WORDS
    )


def model_tokens(model: str) -> set[str]:
    """Identifying words of a model, with letters and digits split apart.

    'Galaxy S24 Ultra 5G' -> {'s', '24', 'ultra'}; 'Nord CE6' -> {'nord', 'ce', '6'}.
    """
    tokens = set()
    for word in normalize_text(model).split():
        if word in MODEL_FILLER_WORDS:
            continue
        word = MODEL_WORD_ALIASES.get(word, word)
        tokens.update(re.findall(r"[a-z]+|\d+(?:\.\d+)?", word))
    return tokens
