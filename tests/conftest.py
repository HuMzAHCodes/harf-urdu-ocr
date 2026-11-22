"""Shared pytest fixtures for every Harf test.

Scripted tests run on CPU with tiny fixtures and never touch the network,
Google Drive or a GPU (D-15). Tests that need any of those are marked
`live` and are excluded with `pytest -m "not live"`.
"""

from pathlib import Path

import pytest

# tests/conftest.py -> tests/ -> repository root
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repository_root() -> Path:
    """Absolute path of the code repository's root folder."""
    return REPOSITORY_ROOT


@pytest.fixture(scope="session")
def fixtures_directory(repository_root: Path) -> Path:
    """Absolute path of tests/fixtures/, the only place small test data may live."""
    return repository_root / "tests" / "fixtures"
