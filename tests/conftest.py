"""Explicit opt-in requirements for local physical-policy integration evidence."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-physical-evidence",
        action="store_true",
        default=False,
        help="Fail rather than skip physical-policy integration tests with missing local evidence.",
    )
