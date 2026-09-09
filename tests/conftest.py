"""Pytest configuration for PawUI tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication instance for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def cleanup(qapp):
    """Clean up after each test."""
    yield
    # Process events to allow Qt to clean up
    qapp.processEvents()
