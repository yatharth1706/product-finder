from app.matching.matcher import match, rank_matches
from app.schemas import Candidate, Category, Platform, Product

SOURCE = Product(
    url="https://www.amazon.in/dp/B0DSKNQW8F",
    title="Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB Storage)",
    brand="Samsung",
    model="Galaxy S25 Ultra",
    category=Category.SMARTPHONE,
    attributes={"ram": "12 GB", "storage": "256 GB"},
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
