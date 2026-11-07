from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(path: str) -> str:
    return (FIXTURES / path).read_text()


@pytest.fixture(autouse=True)
def clear_details_cache() -> None:
    """Product pages are cached across searches; tests reuse URLs, so start empty."""
    from app.orchestrator import _details_cache

    _details_cache.clear()
