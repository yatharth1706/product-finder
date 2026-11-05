import pytest

from app.matching.normalizer import (
    colour_families,
    colours_match,
    gender_of,
    model_from_title,
    model_tokens,
    normalize_brand,
    normalize_model_number,
    normalize_screen_size,
    normalize_size,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12GB", "12 GB"),
        ("12 GB RAM", "12 GB"),
        ("12 Gigabytes", "12 GB"),
        ("256GB ROM", "256 GB"),
        ("1TB", "1 TB"),
        ("no size here", None),
    ],
)
def test_normalize_size(text: str, expected: str | None) -> None:
    assert normalize_size(text) == expected


def test_brand_aliases() -> None:
    assert normalize_brand("REDMI") == normalize_brand("Xiaomi")
    assert normalize_brand("Samsung") == "samsung"
    assert normalize_brand("One Plus") == normalize_brand("OnePlus")


@pytest.mark.parametrize(
    ("title", "brand", "model"),
    [
        (
            "Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB Storage)",
            "Samsung",
            "Galaxy S25 Ultra",
        ),
        ("REDMI Turbo 5 (8GB + 256GB) Turbo White | MediaTek Dimensity", "Redmi", "Turbo 5"),
        ("OnePlus Nord CE6 | 8GB+256GB | Pitch Black", "OnePlus", "Nord CE6"),
        ("Samsung S25 Ultra 5G (Titanium Gray, 256 GB)", "Samsung", "S25 Ultra"),
        ("Nothing Phone (3a) 5G (Blue, 8GB, 128GB)", "Nothing", "Phone 3a"),
        ("Apple iPhone 15 (128 GB) - Black", "Apple", "iPhone 15"),
        ("OnePlus Nord CE6 5G 256 GB, 8 GB RAM, Pitch Black, Mobile Phone", "OnePlus", "Nord CE6"),
    ],
)
def test_model_from_title(title: str, brand: str, model: str) -> None:
    assert model_from_title(title, brand) == model


def test_model_tokens_ignore_filler_and_split_digits() -> None:
    assert model_tokens("Galaxy S24 Ultra 5G") == {"s", "24", "ultra"}
    assert model_tokens("Nord CE6") == model_tokens("Nord CE 6")
    assert model_tokens("Note 13 Pro+") == {"note", "13", "pro", "plus"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("55 Inches", "55 inch"),
        ("Samsung 138 cm (55 inch) Ultra HD", "55 inch"),
        ("139.7 cm - 55 inch", "55 inch"),
        ("(138cm)", "54 inch"),
        ("43 in", "43 inch"),
        ("no size", None),
    ],
)
def test_normalize_screen_size(text: str, expected: str | None) -> None:
    assert normalize_screen_size(text) == expected


def test_model_numbers_ignore_case_and_punctuation() -> None:
    assert normalize_model_number("ua-55ue85ahulxl") == "UA55UE85AHULXL"


@pytest.mark.parametrize(
    ("title", "gender"),
    [
        ("Nike Mens Air Max Bia Sneakers", "men"),
        ("Nike Air Max Bia Men's Shoes", "men"),
        ("NIKE Air Max Bia Sneakers For Women", "women"),
        ("Crocs Unisex Classic Clog", "unisex"),
        ("Samsung Galaxy S25 Ultra", None),
    ],
)
def test_gender_of(title: str, gender: str | None) -> None:
    assert gender_of(title) == gender


def test_colour_families() -> None:
    assert colour_families("WHITE/BLACK-WOLF GREY") == ["white", "black", "grey"]
    assert colour_families("Desert Dust") == ["beige"]
    assert colour_families("CBLACK/FTWWHT") == ["black", "white"]
    assert colour_families("Volt") == []


@pytest.mark.parametrize(
    ("expected", "found", "same"),
    [
        ("Titanium Grey", "titanium gray", True),
        ("WHITE/BLACK-WOLF GREY", "White", True),
        ("Desert Dust", "Beige", True),
        ("WHITE/BLACK-WOLF GREY", "WHITE/EMERALD GREEN-GUM MED BROWN", False),
        ("WHITE/BLACK-WOLF GREY", "Black", False),
        ("Volt", "Yellow", False),
        ("Volt", "VOLT", True),
    ],
)
def test_colours_match(expected: str, found: str, same: bool) -> None:
    assert colours_match(expected, found) is same


def test_brand_abbreviations_in_model_names() -> None:
    assert model_tokens("ESS Zippered Placket Polo") == model_tokens(
        "Essential Men's Zippered Placket Polo"
    )
