import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("TEST_MODE", "true")


@pytest.fixture(autouse=True)
def restore_dependency_overrides() -> Iterator[None]:
	"""Undoes a test's overrides, keeping the test mode ones that `serka.main` installs at import."""
	from serka.main import app

	saved = dict(app.dependency_overrides)
	yield
	app.dependency_overrides.clear()
	app.dependency_overrides.update(saved)


@pytest.fixture
def no_mock_delays(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Plays the test mode scripted runs without their realistic delays."""

	async def no_sleep(_: float) -> None:
		return None

	monkeypatch.setattr("serka.routers.mock.asyncio.sleep", no_sleep)
