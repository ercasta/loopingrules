"""Slow tests (full Rubik solves, ~30 s each) are skipped unless pytest runs with --slow."""

import pytest


def pytest_addoption(parser):
    parser.addoption("--slow", action="store_true", default=False, help="also run the tests marked slow")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: a long test (e.g. a full Rubik solve); run with --slow")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--slow"):
        return
    skip = pytest.mark.skip(reason="slow: run with --slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
