from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    SMARTPHONE = "smartphone"
    TELEVISION = "television"
    SNEAKER = "sneaker"
    CLOTHING = "clothing"


class Platform(StrEnum):
    FLIPKART = "flipkart"
    CROMA = "croma"
    RELIANCE_DIGITAL = "reliance_digital"
    MYNTRA = "myntra"


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class ResultStatus(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    NOT_LISTED = "not_listed"
    FAILED = "failed"


class FailureReason(StrEnum):
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    PARSE_ERROR = "parse_error"
    AVAILABILITY_UNKNOWN = "availability_unknown"
    UNEXPECTED = "unexpected"


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Attributes that must match (besides brand and model) for each category.
REQUIRED_ATTRIBUTES: dict[Category, list[str]] = {
    Category.SMARTPHONE: ["ram", "storage"],
    Category.TELEVISION: ["screen_size"],
    Category.SNEAKER: ["colour"],
    Category.CLOTHING: ["colour"],
}


class Product(BaseModel):
    """The Amazon product we are looking for."""

    url: str
    title: str
    brand: str
    # Model name, or for televisions the manufacturer's model number.
    model: str
    category: Category
    attributes: dict[str, str] = Field(default_factory=dict)
    image_url: str | None = None
    # What we type into each marketplace's search box.
    search_query: str


class Candidate(BaseModel):
    """A listing found on a marketplace that might be the same product."""

    platform: Platform
    url: str
    title: str
    # Set only when the marketplace gives the brand as a separate field.
    brand: str | None = None
    model_number: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    image_url: str | None = None
    availability: Availability = Availability.UNKNOWN


class MatchResult(BaseModel):
    matched: bool
    score: int
    checks: dict[str, bool]
    reasons: list[str] = Field(default_factory=list)


class MarketplaceResult(BaseModel):
    platform: Platform
    status: ResultStatus
    title: str | None = None
    url: str | None = None
    image_url: str | None = None
    match: MatchResult | None = None
    failure_reason: FailureReason | None = None
    candidates_checked: int = 0


class SearchRequest(BaseModel):
    amazon_url: str = Field(max_length=2048)


class SearchAccepted(BaseModel):
    search_id: str
    status: JobStatus


class SearchJob(BaseModel):
    search_id: str
    status: JobStatus
    source_url: str
    source_product: Product | None = None
    results: list[MarketplaceResult] | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
