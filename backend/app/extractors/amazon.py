import logging
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.errors import ExtractionError, FetchError, InvalidUrlError
from app.http import fetch, host_allowed, make_client
from app.matching.normalizer import (
    find_sizes,
    model_from_title,
    normalize_screen_size,
    normalize_size,
    size_in_gb,
)
from app.schemas import REQUIRED_ATTRIBUTES, Category, FailureReason, Product

logger = logging.getLogger(__name__)

AMAZON_HOSTS = {"amazon.in", "amazon.com", "amzn.in", "amzn.to", "amzn.eu"}
SHORT_LINK_HOSTS = {"amzn.in", "amzn.to", "amzn.eu"}
ASIN_PATTERN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)")

# Breadcrumb on the Amazon page -> our category. The most specific crumb that is
# listed here wins, so "Electronics > ... > Televisions > Smart Televisions" is a TV.
CATEGORY_BREADCRUMBS = {
    "smartphones": Category.SMARTPHONE,
    "televisions": Category.TELEVISION,
    "sneakers": Category.SNEAKER,
    "casual shoes": Category.SNEAKER,
    "running shoes": Category.SNEAKER,
    "walking shoes": Category.SNEAKER,
    "training shoes": Category.SNEAKER,
    "basketball shoes": Category.SNEAKER,
    "t-shirts": Category.CLOTHING,
    "polos": Category.CLOTHING,
    "t-shirts & polos": Category.CLOTHING,
    "jerseys": Category.CLOTHING,
    "sports t-shirts & jerseys": Category.CLOTHING,
}

ATTRIBUTE_LABELS = {
    "ram": "RAM",
    "storage": "storage",
    "screen_size": "screen size",
    "colour": "colour",
}


def validate_amazon_url(url: str) -> str:
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise InvalidUrlError("Enter a full Amazon product link starting with https://")
    if not host_allowed(parts.hostname, AMAZON_HOSTS):
        raise InvalidUrlError("Only Amazon product links are supported")
    is_short_link = host_allowed(parts.hostname, SHORT_LINK_HOSTS)
    if not is_short_link and not ASIN_PATTERN.search(parts.path):
        raise InvalidUrlError("This does not look like an Amazon product page link")
    return url.replace("http://", "https://", 1)


async def extract_product(url: str) -> Product:
    url = validate_amazon_url(url)
    try:
        async with make_client(AMAZON_HOSTS) as client:
            response = await fetch(client, url)
    except FetchError as exc:
        logger.warning("amazon fetch failed: %s", exc)
        if exc.reason == FailureReason.TIMEOUT:
            raise ExtractionError("Amazon took too long to respond. Try again.") from exc
        raise ExtractionError("Amazon refused the request. Try again in a minute.") from exc

    final_url = str(response.url)
    asin = ASIN_PATTERN.search(urlsplit(final_url).path)
    if not asin:
        raise ExtractionError("The link did not lead to an Amazon product page")
    canonical_url = f"https://{urlsplit(final_url).hostname}/dp/{asin.group(1)}"
    return parse_product_page(response.text, canonical_url)


def parse_product_page(html: str, url: str) -> Product:
    if "validateCaptcha" in html:
        raise ExtractionError("Amazon asked for a CAPTCHA. Try again in a minute.")

    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("#productTitle")
    if not title_node:
        raise ExtractionError("Could not read the product from the Amazon page")
    title = title_node.get_text(" ", strip=True)

    breadcrumbs = [
        a.get_text(strip=True) for a in soup.select("#wayfinding-breadcrumbs_feature_div a")
    ]
    category = resolve_category(breadcrumbs, title)
    specs = read_specs(soup)

    brand = specs.get("brand") or read_byline_brand(soup) or title.split()[0]
    model = extract_model(category, title, brand, specs)
    if not model:
        label = "model number" if category == Category.TELEVISION else "model name"
        raise ExtractionError(f"The Amazon page does not state the {label}")

    attributes = extract_attributes(category, title, specs, soup)
    missing = [name for name in REQUIRED_ATTRIBUTES[category] if name not in attributes]
    if missing:
        labels = ", ".join(ATTRIBUTE_LABELS.get(name, name) for name in missing)
        raise ExtractionError(f"The Amazon page does not state the {labels}")

    image = soup.select_one("#landingImage")
    return Product(
        url=url,
        title=title,
        brand=brand,
        model=model,
        category=category,
        attributes=attributes,
        image_url=image and small_image(image.get("data-old-hires") or image.get("src")),
        search_query=build_search_query(category, title, brand, model),
    )


def small_image(url: str | None) -> str | None:
    """Amazon resizes images from the URL: '..._SL1500_.jpg' -> '..._SL300_.jpg'.

    The page shows the image at about 100px, so the large original only slows it down.
    """
    if not url or not url.startswith("https://"):
        return None
    return re.sub(r"\._[A-Z0-9_,]+_\.(jpg|jpeg|png|webp)$", r"._SL300_.\1", url)


def resolve_category(breadcrumbs: list[str], title: str) -> Category:
    for crumb in reversed(breadcrumbs):
        if category := CATEGORY_BREADCRUMBS.get(crumb.lower()):
            return category
    if breadcrumbs:
        raise ExtractionError(f"Unsupported category: {breadcrumbs[-1]}")
    # Some pages have no breadcrumb; fall back to the title.
    if "smartphone" in title.lower():
        return Category.SMARTPHONE
    raise ExtractionError("Could not tell which category this product belongs to")


def read_specs(soup: BeautifulSoup) -> dict[str, str]:
    """Every 'label | value' row in the page's spec sections, with lowercase labels.

    Amazon spreads specs over several layouts depending on the category; the first
    value seen for a label wins.
    """
    specs: dict[str, str] = {}

    def add(label: str, value: str) -> None:
        label = re.sub(r"[\s\u200e\u200f:]+", " ", label).strip().lower()
        value = re.sub(r"[\s\u200e\u200f]+", " ", value).strip()
        if label and value:
            specs.setdefault(label, value)

    for row in soup.select("#productOverview_feature_div tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            add(cells[0].get_text(" ", strip=True), cells[-1].get_text(" ", strip=True))
    for row in soup.select("table.prodDetTable tr"):
        label, value = row.find("th"), row.find("td")
        if label and value:
            add(label.get_text(" ", strip=True), value.get_text(" ", strip=True))
    for item in soup.select("#detailBullets_feature_div li"):
        label, _, value = item.get_text(" ", strip=True).partition(":")
        add(label, value)
    return specs


def read_byline_brand(soup: BeautifulSoup) -> str | None:
    """'Visit the Samsung Store' or 'Brand: Samsung'."""
    byline = soup.select_one("#bylineInfo")
    if not byline:
        return None
    text = byline.get_text(" ", strip=True)
    match = re.match(r"(?:Visit the (.+) Store|Brand: (.+))", text)
    return match and (match.group(1) or match.group(2))


def extract_model(category: Category, title: str, brand: str, specs: dict[str, str]) -> str:
    if category == Category.TELEVISION:
        # A TV is identified by its model number; names like "Crystal 4K" cover many sets.
        return specs.get("model number") or specs.get("item model number") or ""
    if category in (Category.SNEAKER, Category.CLOTHING):
        # Fashion titles are often generic ("Puma Men Polos"); the spec name is cleaner.
        return specs.get("model name") or model_from_title(title, brand)
    return model_from_title(title, brand)


def build_search_query(category: Category, title: str, brand: str, model: str) -> str:
    if category == Category.TELEVISION:
        # Marketplaces do not index model numbers well, so search by the product name:
        # "Samsung 55 inch (138cm) Crystal UHD 4K Vision AI 2026 Smart TV | ..." -> before "|".
        return re.split(r"[|,]", title, maxsplit=1)[0].strip()
    return f"{brand} {model}"


def extract_attributes(
    category: Category, title: str, specs: dict[str, str], soup: BeautifulSoup
) -> dict[str, str]:
    if category == Category.SMARTPHONE:
        return extract_phone_attributes(title, specs)
    if category == Category.TELEVISION:
        size = normalize_screen_size(specs.get("screen size", "")) or normalize_screen_size(title)
        return {"screen_size": size} if size else {}
    colour = read_selected_colour(soup) or specs.get("colour") or specs.get("color")
    return {"colour": colour} if colour else {}


def read_selected_colour(soup: BeautifulSoup) -> str | None:
    """The colour picked in the variant selector, e.g. 'WHITE/BLACK-WOLF GREY'."""
    node = soup.select_one("#inline-twister-expanded-dimension-text-color_name")
    return node.get_text(" ", strip=True) or None if node else None


def extract_phone_attributes(title: str, specs: dict[str, str]) -> dict[str, str]:
    """RAM and storage from the spec table, falling back to the title.

    Titles write them in several ways: '12GB RAM, 256GB Storage', '(8GB + 256GB)',
    '(Black, 8GB, 128GB)'. When unlabelled, the smaller size is RAM and the larger is storage.
    """
    ram = normalize_size(specs.get("ram memory installed size", ""))
    storage = normalize_size(specs.get("memory storage capacity", ""))

    if not ram:
        labelled = re.search(r"(\d+\s*(?:GB|TB))\s*RAM", title, re.I)
        ram = labelled and normalize_size(labelled.group(1))
    if not storage:
        labelled = re.search(r"(\d+\s*(?:GB|TB))\s*(?:Storage|ROM)", title, re.I)
        storage = labelled and normalize_size(labelled.group(1))

    sizes = sorted(set(find_sizes(title)), key=size_in_gb)
    if not ram and len(sizes) >= 2:
        ram = sizes[0]
    other_sizes = [size for size in sizes if size != ram]
    if not storage and ram and other_sizes:
        storage = other_sizes[-1]

    attributes = {}
    if ram:
        attributes["ram"] = ram
    if storage:
        attributes["storage"] = storage
    return attributes
