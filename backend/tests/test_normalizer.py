import pytest

from app.matching.normalizer import (
    model_from_title,
    model_tokens,
    normalize_brand,
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
