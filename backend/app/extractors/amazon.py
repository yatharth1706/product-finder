import logging
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.errors import ExtractionError, FetchError, InvalidUrlError
from app.http import fetch, host_allowed, make_client
from app.matching.normalizer import find_sizes, model_from_title, normalize_size, size_in_gb
from app.schemas import REQUIRED_ATTRIBUTES, Category, FailureReason, Product

logger = logging.getLogger(__name__)

AMAZON_HOSTS = {"amazon.in", "amazon.com", "amzn.in", "amzn.to", "amzn.eu"}
SHORT_LINK_HOSTS = {"amzn.in", "amzn.to", "amzn.eu"}
ASIN_PATTERN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)")

# Last breadcrumb on the Amazon page -> our category.
CATEGORY_BREADCRUMBS = {
    "smartphones": Category.SMARTPHONE,
}

ATTRIBUTE_LABELS = {"ram": "RAM", "storage": "storage"}


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
    overview = read_overview_table(soup)

    brand = overview.get("brand") or read_byline_brand(soup) or title.split()[0]
    model = model_from_title(title, brand)
    if not model:
        raise ExtractionError("Could not find the model name on the Amazon page")

    attributes = extract_attributes(category, title, overview)
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
        image_url=image and (image.get("data-old-hires") or image.get("src")),
    )


def resolve_category(breadcrumbs: list[str], title: str) -> Category:
    if breadcrumbs:
        category = CATEGORY_BREADCRUMBS.get(breadcrumbs[-1].lower())
        if category:
            return category
        raise ExtractionError(f"Unsupported category: {breadcrumbs[-1]}")
    # Some pages have no breadcrumb; fall back to the title.
    if "smartphone" in title.lower():
        return Category.SMARTPHONE
    raise ExtractionError("Could not tell which category this product belongs to")


def read_overview_table(soup: BeautifulSoup) -> dict[str, str]:
    """The 'Brand | Samsung' style table near the top of the page, with lowercase keys."""
    table = {}
    for row in soup.select("#productOverview_feature_div tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            table[cells[0].get_text(" ", strip=True).lower()] = cells[-1].get_text(" ", strip=True)
    return table


def read_byline_brand(soup: BeautifulSoup) -> str | None:
    """'Visit the Samsung Store' or 'Brand: Samsung'."""
    byline = soup.select_one("#bylineInfo")
    if not byline:
        return None
    text = byline.get_text(" ", strip=True)
    match = re.match(r"(?:Visit the (.+) Store|Brand: (.+))", text)
    return match and (match.group(1) or match.group(2))


def extract_attributes(category: Category, title: str, overview: dict[str, str]) -> dict[str, str]:
    if category == Category.SMARTPHONE:
        return extract_phone_attributes(title, overview)
    return {}


def extract_phone_attributes(title: str, overview: dict[str, str]) -> dict[str, str]:
    """RAM and storage from the spec table, falling back to the title.

    Titles write them in several ways: '12GB RAM, 256GB Storage', '(8GB + 256GB)',
    '(Black, 8GB, 128GB)'. When unlabelled, the smaller size is RAM and the larger is storage.
    """
    ram = normalize_size(overview.get("ram memory installed size", ""))
    storage = normalize_size(overview.get("memory storage capacity", ""))

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
