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
    result = match(SOURCE, candidate("Samsung Galaxy S25 Ultra 5G (Black, 256 GB)", ram="8 GB"))
    assert not result.matched
    assert result.reasons == ["RAM mismatch: expected 12 GB, found 8 GB"]


def test_storage_mismatch() -> None:
    result = match(
        SOURCE, candidate("Samsung Galaxy S25 Ultra 5G (Black, 512 GB)", storage="512 GB")
    )
    assert not result.matched
    assert result.score == 80
    assert result.reasons == ["Storage mismatch: expected 256 GB, found 512 GB"]


def test_missing_attribute_is_never_a_match() -> None:
    result = match(SOURCE, candidate("Samsung Galaxy S25 Ultra 5G (Black)", storage=""))
    assert not result.matched
    assert result.checks["storage"] is False
    assert result.reasons == ["Storage missing on listing"]


def test_rank_keeps_only_exact_matches_in_order() -> None:
    listings = [
        candidate("Samsung Galaxy S25 Ultra 5G (Black, 512 GB)", storage="512 GB"),
        candidate("Samsung Galaxy S25 Ultra 5G (Black, 256 GB)"),
        candidate("Samsung S25 Ultra 5G (Gray, 256 GB)"),
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


def shoe_listing(title: str, colour: str, brand: str = "Nike") -> Candidate:
    return Candidate(
        platform=Platform.FLIPKART,
        url="https://www.flipkart.com/shoe",
        title=title,
        brand=brand,
        attributes={"colour": colour},
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


def test_tv_matches_store_shortened_model_number() -> None:
    lg = TV.model_copy(update={"brand": "LG", "model": "43NU870BPLA"})
    listing = tv_listing("43NU870")
    listing.model_number_shortened = True
    listing.title = "LG NU870B 109.22 cm (55 inch) Nano Cell 4K Smart TV"
    assert match(lg, listing).checks["model"]


def test_short_model_number_must_be_a_fair_short_form() -> None:
    lg = TV.model_copy(update={"brand": "LG", "model": "43NU870BPLA"})
    for code in ["43NU885", "43NU"]:
        listing = tv_listing(code)
        listing.model_number_shortened = True
        assert not match(lg, listing).checks["model"]


def test_store_that_lists_full_model_numbers_must_match_exactly() -> None:
    # Flipkart's K-55S25B is the 2024 BRAVIA 2, not the 2025 K-55S25BM2.
    sony = TV.model_copy(update={"brand": "Sony", "model": "K-55S25BM2"})
    assert not match(sony, tv_listing("K-55S25B")).checks["model"]


def test_croma_short_code_with_letters_dropped() -> None:
    sony = TV.model_copy(update={"brand": "Sony", "model": "K-55S25BM2"})
    listing = tv_listing("55S25M2")
    listing.model_number_shortened = True
    assert match(sony, listing).checks["model"]


def test_5g_phone_does_not_match_a_listing_without_5g() -> None:
    redmi = SOURCE.model_copy(
        update={
            "title": "REDMI A7 Pro 5G (Black, 4GB, 64GB)",
            "brand": "Redmi",
            "model": "A7 Pro",
            "attributes": {"ram": "4 GB", "storage": "64 GB"},
        }
    )
    croma_4g = candidate("Redmi A7 Pro (4GB RAM, 64GB, Black)", ram="4 GB", storage="64 GB")
    flipkart_5g = candidate("REDMI A7 Pro 5G (Mist Blue, 64 GB)", ram="4 GB", storage="64 GB")
    assert match(redmi, croma_4g).reasons == [
        "Network mismatch: the Amazon product is 5G, the listing does not say 5G"
    ]
    assert match(redmi, flipkart_5g).matched


def test_shoe_listing_may_add_words_to_the_model() -> None:
    shoe_ = SNEAKER.model_copy(
        update={"title": "Nike Mens Revolution 8 Running Shoes", "model": "Revolution 8"}
    )
    for title in ["Nike Revolution 8 Men's Road Running Shoes", "NIKE Revolution 8 Running Shoes"]:
        assert match(shoe_, shoe_listing(title, "White")).checks["model"], title


def test_shoe_listing_must_keep_numbers_and_variants() -> None:
    breaknet = SNEAKER.model_copy(
        update={
            "title": "adidas Womens Breaknet 3.0 Ikd Sneaker",
            "brand": "adidas",
            "model": "Breaknet 3.0 Ikd",
        }
    )
    older = shoe_listing("ADIDAS Women BREAKNET 2.0 IKD Sneakers", "White", brand="ADIDAS")
    assert not match(breaknet, older).checks["model"]
    special = shoe_listing("Nike Air Max Bia SE Men's Shoes", "White")
    assert not match(SNEAKER, special).checks["model"]


def test_title_cut_at_dash_still_matches() -> None:
    skechers = SNEAKER.model_copy(
        update={
            "title": "Skechers Women Uno Lite Lighter One Sneakers",
            "brand": "Skechers",
            "model": "Uno Lite Lighter One",
            "attributes": {"colour": "MAUVE"},
        }
    )
    listing = shoe_listing(
        "Skechers UNO LITE - LIGHTER ONE Casual Shoes For Women", "Mauve", brand="Skechers"
    )
    assert match(skechers, listing).matched


def test_unknown_brand_colour_names_match_on_the_main_colour_word() -> None:
    alta = SNEAKER.model_copy(
        update={
            "title": "Nike Womens Court Vision Alta Sneakers",
            "model": "Court Vision Alta",
            "attributes": {"colour": "SHIMMER/LT COGNAC-SAIL"},
        }
    )
    flipkart = shoe_listing("NIKE Court Vision Alta Sneakers For Women", "Shimmer")
    myntra = shoe_listing("Nike Court Vision Alta Women's Shoes", "White")
    assert match(alta, flipkart).matched
    assert not match(alta, myntra).matched


IPHONE = Product(
    url="https://www.amazon.in/dp/B0HJB3GZ2C",
    title="iPhone 18 Pro (512 GB) - Silver",
    brand="Apple",
    model="iPhone 18 Pro",
    category=Category.SMARTPHONE,
    attributes={"storage": "512 GB", "colour": "Silver"},
    search_query="Apple iPhone 18 Pro",
)


def iphone_listing(title: str, storage: str = "512 GB") -> Candidate:
    return Candidate(
        platform=Platform.FLIPKART,
        url=f"https://www.flipkart.com/{title}",
        title=title,
        attributes={"storage": storage},
    )


def test_apple_phones_match_without_ram() -> None:
    result = match(IPHONE, iphone_listing("Apple iPhone 18 Pro (Black, 512 GB)"))
    assert result.matched
    assert result.checks == {"brand": True, "model": True, "storage": True}


def test_apple_phones_still_need_model_and_storage() -> None:
    assert not match(
        IPHONE, iphone_listing("Apple iPhone 18 Pro (Black, 256 GB)", "256 GB")
    ).matched
    assert not match(IPHONE, iphone_listing("Apple iPhone 18 Pro max (Black, 512 GB)")).matched
    assert not match(IPHONE, iphone_listing("Apple iPhone 17 Pro (Black, 512 GB)")).matched


def test_other_phones_still_need_ram() -> None:
    listing = candidate("Samsung Galaxy S25 Ultra 5G (Black, 256 GB)", ram="")
    assert match(SOURCE, listing).reasons == ["RAM missing on listing"]


def test_matches_in_the_amazon_colour_rank_first() -> None:
    listings = [
        iphone_listing("Apple iPhone 18 Pro (Burgundy, 512 GB)"),
        iphone_listing("Apple iPhone 18 Pro (Silver, 512 GB)"),
    ]
    assert rank_matches(IPHONE, listings)[0][0].title == "Apple iPhone 18 Pro (Silver, 512 GB)"


def top(title: str, model: str, colour: str, brand: str) -> Product:
    return Product(
        url="https://www.amazon.in/dp/X",
        title=title,
        brand=brand,
        model=model,
        category=Category.CLOTHING,
        attributes={"colour": colour},
        search_query=f"{brand} {model}",
    )


def top_listing(title: str, colour: str) -> Candidate:
    return Candidate(
        platform=Platform.MYNTRA,
        url=f"https://www.myntra.com/{title}",
        title=title,
        attributes={"colour": colour},
    )


def test_clothing_ignores_description_words() -> None:
    tiro = top("adidas Men TIRO 23 JSY Jerseys", "TIRO 23 JSY", "Blue", "adidas")
    assert match(tiro, top_listing("ADIDAS TIRO 23 JSY Printed T-Shirt", "Blue")).matched
    liga = top(
        "teamLIGA Men's Regular Fit Football Jersey",
        "teamLIGA Regular Fit Football",
        "Pepper Green-White",
        "PUMA",
    )
    assert match(liga, top_listing("Puma teamLIGA Striped Men's Football Jersey", "Green")).matched


def test_clothing_extra_identifying_words_are_a_different_product() -> None:
    polo = top(
        "Puma Men's Solid Slim Fit Cotton Essential Polo T-Shirt",
        "ESS Logo Polo",
        "Team Regal Red",
        "PUMA",
    )
    for title in [
        "Puma Ess Badge Logo Printed Pure Cotton Slim Fit Polo",
        "Puma Ess Logo Graphic Printed Pure Cotton Slim Fit Polo",
    ]:
        assert not match(polo, top_listing(title, "Red")).checks["model"], title
    flipkart = top_listing("PUMA ESS Logo M Men Solid Polo Neck Pure Cotton Red T-Shirt", "Red")
    assert match(polo, flipkart).matched


def test_clothing_numbers_must_match() -> None:
    levis = top(
        "Levi's 025 Men's Premium Soft Cotton Solid T-Shirt",
        "025 Premium Soft Cotton Solid",
        "Black(Red)",
        "Levi's",
    )
    assert match(
        levis,
        top_listing("LEVI'S 025 Premium Soft Cotton Solid Round Neck Men Black T-Shirt", "Black"),
    ).matched
    assert not match(
        levis, top_listing("Levis Pack of 2 Pure Cotton Lounge T-Shirt", "Black")
    ).matched


def test_tv_with_an_unverified_short_code_may_still_match() -> None:
    sony = TV.model_copy(
        update={"brand": "Sony", "model": "K-43S22M2", "attributes": {"screen_size": "43 inch"}}
    )
    listing = tv_listing("BRAVIA2", screen_size="43 inch")
    listing.title = "SONY BRAVIA 2 II 109 cm (43 inch) 4K Ultra HD LCD Smart Android TV"
    listing.model_number_shortened = True
    assert not match(sony, listing).matched
    assert may_match(sony, listing)
    listing.model_number_shortened = False
    assert not may_match(sony, listing)
