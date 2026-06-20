"""Pytest config for the trading-bench test suite.

Registers the `slow` marker used by the sweep-harness validation/regression
test (which runs a full multi-window walk-forward and fetches bars). Run the
slow path explicitly with `pytest -m slow`; the default `pytest` run includes
it. This file is additive infra — it changes no existing test behavior.
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: marks tests that run a full walk-forward sweep (deselect with "
        "-m 'not slow')")
