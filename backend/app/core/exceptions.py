class ProductFinderError(Exception):
    """Base class for expected, user-facing application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "An unexpected error occurred.") -> None:
        super().__init__(message)
        self.message = message


class InvalidURLError(ProductFinderError):
    status_code = 400
    code = "invalid_url"


class NotFoundError(ProductFinderError):
    status_code = 404
    code = "not_found"


class UnsupportedProductError(ProductFinderError):
    status_code = 422
    code = "unsupported_product"
