from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(path: str) -> str:
    return (FIXTURES / path).read_text()
