from app.schemas import FailureReason


class InvalidUrlError(ValueError):
    """The submitted URL is not an accepted Amazon product link."""


class ExtractionError(Exception):
    """The Amazon product could not be read. The message is safe to show to users."""


class FetchError(Exception):
    """An outbound request failed for a technical reason (blocked, timed out, unreadable)."""

    def __init__(self, reason: FailureReason, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else str(reason))
        self.reason = reason
