from app.matching.matcher import match, may_match, rank_matches
from app.schemas import Candidate, Category, Platform, Product

SOURCE = Product(
    url="https://www.amazon.in/dp/B0DSKNQW8F",
    title="Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB Storage)",
    brand="Samsung",
    model="Galaxy S25 Ultra",
    category=Category.SMARTPHONE,
    attributes={"ram": "12 GB", "storage": "256 GB"},
    search_query="Samsung Galaxy S25 Ultra",
)


def candidate(title: str, **attributes: str) -> Candidate:
    attrs = {"ram": "12 GB", "storage": "256 GB"} | attributes
    return Candidate(
        platform=Platform.FLIPKART,
        url="https://www.flipkart.com/x",
        title=title,
        attributes={k: v for k, v in attrs.items() if v},
    )


def test_exact_match() -> None:
    result = match(SOURCE, candidate("Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB)"))
    assert result.matched
    assert result.score == 100
    assert result.checks == {"brand": True, "model": True, "ram": True, "storage": True}
    assert result.reasons == []


def test_model_written_differently_still_matches() -> None:
    assert match(SOURCE, candidate("Samsung S25 Ultra 5G (Titanium Gray, 256 GB)")).matched


def test_brand_mismatch() -> None:
    result = match(SOURCE, candidate("Apple Galaxy S25 Ultra (Black, 256 GB)"))
    assert not result.matched
    assert result.checks["brand"] is False


def test_different_generation_is_rejected() -> None:
    result = match(SOURCE, candidate("Samsung Galaxy S24 Ultra 5G (Titanium Black, 256 GB)"))
    assert not result.matched
    assert result.checks["model"] is False


def test_variant_word_is_rejected() -> None:
    plain = SOURCE.model_copy(update={"model": "Galaxy S25"})
    result = match(plain, candidate("Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB)"))
    assert not result.matched
    assert "variant" in result.reasons[0]


def test_extra_model_word_is_rejected() -> None:
    redmi = SOURCE.model_copy(update={"brand": "Redmi", "model": "13"})
    assert not match(redmi, candidate("REDMI Note 13 5G (Black, 256 GB)")).matched


def test_ram_mismatch() -> None:
    result = match(SOURCE, candidate("Samsung Galaxy S25 Ultra (Black, 256 GB)", ram="8 GB"))
    assert not result.matched
    assert result.reasons == ["RAM mismatch: expected 12 GB, found 8 GB"]


def test_storage_mismatch() -> None:
    result = match(SOURCE, candidate("Samsung Galaxy S25 Ultra (Black, 512 GB)", storage="512 GB"))
    assert not result.matched
    assert result.score == 80
    assert result.reasons == ["Storage mismatch: expected 256 GB, found 512 GB"]


def test_missing_attribute_is_never_a_match() -> None:
    result = match(SOURCE, candidate("Samsung Galaxy S25 Ultra (Black)", storage=""))
    assert not result.matched
    assert result.checks["storage"] is False
    assert result.reasons == ["Storage missing on listing"]


def test_rank_keeps_only_exact_matches_in_order() -> None:
    listings = [
        candidate("Samsung Galaxy S25 Ultra (Black, 512 GB)", storage="512 GB"),
        candidate("Samsung Galaxy S25 Ultra (Black, 256 GB)"),
        candidate("Samsung S25 Ultra (Gray, 256 GB)"),
    ]
    ranked = rank_matches(SOURCE, listings)
    assert [c.title for c, _ in ranked] == [listings[1].title, listings[2].title]


def test_brand_field_written_differently() -> None:
    oneplus = SOURCE.model_copy(update={"brand": "OnePlus", "model": "Nord CE6"})
    listing = candidate("OnePlus Nord CE6 5G 256 GB, 12 GB RAM, Pitch Black, Mobile Phone")
    listing.brand = "One Plus"
    assert match(oneplus, listing).matched


def test_lite_variant_is_rejected() -> None:
    oneplus = SOURCE.model_copy(update={"brand": "OnePlus", "model": "Nord CE6"})
    listing = candidate("OnePlus Nord CE6 Lite 5G 256 GB, 12 GB RAM, Hyper Black, Mobile Phone")
    assert not match(oneplus, listing).matched


TV = Product(
    url="https://www.amazon.in/dp/B0GXV5313B",
    title="Samsung 55 inch (138cm) Vision AI 2026 4K Mini LED Smart TV",
    brand="Samsung",
    model="UA55M2EHAULXL",
    category=Category.TELEVISION,
    attributes={"screen_size": "55 inch"},
    search_query="Samsung 55 inch (138cm) Vision AI 2026 4K Mini LED Smart TV",
)


def tv_listing(model_number: str | None, screen_size: str = "55 inch") -> Candidate:
    return Candidate(
        platform=Platform.FLIPKART,
        url="https://www.flipkart.com/tv",
        title="Samsung Vision AI 138 cm (55 inch) Ultra HD (4K) Mini LED Smart Tizen TV",
        model_number=model_number,
        attributes={"screen_size": screen_size},
    )


def test_tv_matches_on_model_number() -> None:
    assert match(TV, tv_listing("UA55M2EHAULXL")).matched


def test_tv_with_similar_model_number_is_rejected() -> None:
    result = match(TV, tv_listing("UA55M2EHAFLXL"))
    assert not result.matched
    assert result.reasons == ["Model number mismatch: expected UA55M2EHAULXL, found UA55M2EHAFLXL"]


def test_tv_without_model_number_is_rejected() -> None:
    assert not match(TV, tv_listing(None)).matched


def test_tv_screen_size_mismatch() -> None:
    result = match(TV, tv_listing("UA55M2EHAULXL", screen_size="65 inch"))
    assert not result.matched
    assert result.checks["screen_size"] is False


SNEAKER = Product(
    url="https://www.amazon.in/dp/B0FQN7T937",
    title="Nike Mens Air Max Bia Sneakers",
    brand="Nike",
    model="Air Max Bia",
    category=Category.SNEAKER,
    attributes={"colour": "WHITE/BLACK-WOLF GREY"},
    search_query="Nike Air Max Bia",
)


def shoe(title: str, colour: str | None) -> Candidate:
    return Candidate(
        platform=Platform.MYNTRA,
        url="https://www.myntra.com/shoe",
        title=title,
        brand="Nike",
        attributes={"colour": colour} if colour else {},
    )


def test_sneaker_matches_on_model_and_main_colour() -> None:
    assert match(SNEAKER, shoe("Nike Air Max Bia Men's Shoes", "White")).matched


def test_sneaker_colourway_mismatch() -> None:
    result = match(SNEAKER, shoe("Nike Air Max Bia Men's Shoes", "Black"))
    assert not result.matched
    assert result.checks["colour"] is False


def test_sneaker_gender_mismatch() -> None:
    result = match(SNEAKER, shoe("Nike Air Max Bia Women's Shoes", "White"))
    assert not result.matched
    assert result.reasons == ["Gender mismatch: expected men, found women"]


def test_sneaker_without_colour_is_never_a_match() -> None:
    result = match(SNEAKER, shoe("Nike Air Max Bia Men's Shoes", None))
    assert not result.matched
    assert may_match(SNEAKER, shoe("Nike Air Max Bia Men's Shoes", None))
    assert not may_match(SNEAKER, shoe("Nike Air Max SC Men's Shoes", None))
