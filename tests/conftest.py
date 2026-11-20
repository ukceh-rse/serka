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


@pytest.fixture
def test_redis():
	"""A clean Redis for integration tests, from TEST_REDIS_URL (default localhost:6380), flushed
	before and after. Search indexes only work in db 0, so this must not be the development Redis."""
	import redis

	client = redis.Redis.from_url(os.environ.get("TEST_REDIS_URL", "redis://localhost:6380"))
	try:
		client.ping()
	except redis.ConnectionError:
		pytest.skip("no test Redis; run: docker run -d -p 6380:6379 redis:8.10.3")
	client.flushall()
	yield client
	client.flushall()
