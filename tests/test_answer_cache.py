import logging
from typing import Any

import pytest

from serka import answer_cache
from serka.answer_cache import AnswerCache, CachedAnswer
from serka.settings import Settings

ANSWER = CachedAnswer(text="Pike are found in Windermere.", path="keyword", score=4, model="amazon.nova-lite-v1:0")


class FakeBackend:
	"""Stores entries by exact prompt; `fail` makes every call raise."""

	def __init__(self, fail: bool = False) -> None:
		self.entries: dict[str, dict[str, Any]] = {}
		self.fail = fail

	def check(self, prompt: str) -> list[dict[str, Any]]:
		if self.fail:
			raise ConnectionError("redis down")
		return [self.entries[prompt]] if prompt in self.entries else []

	def store(self, prompt: str, response: str, metadata: dict[str, Any] | None = None) -> str:
		if self.fail:
			raise ConnectionError("redis down")
		self.entries[prompt] = {"prompt": prompt, "response": response, "metadata": metadata, "vector_distance": 0.0}
		return prompt

	def clear(self) -> None:
		if self.fail:
			raise ConnectionError("redis down")
		self.entries.clear()


def test_hit_returns_the_stored_answer() -> None:
	cache = AnswerCache(FakeBackend)
	cache.store("pike in windermere", ANSWER)
	assert cache.lookup("pike in windermere") == ANSWER


def test_miss_returns_none() -> None:
	cache = AnswerCache(FakeBackend)
	cache.store("pike in windermere", ANSWER)
	assert cache.lookup("perch in windermere") is None


def test_clear_empties_the_cache() -> None:
	cache = AnswerCache(FakeBackend)
	cache.store("pike in windermere", ANSWER)
	cache.clear()
	assert cache.lookup("pike in windermere") is None


def test_errors_are_logged_and_treated_as_a_miss(caplog: pytest.LogCaptureFixture) -> None:
	cache = AnswerCache(lambda: FakeBackend(fail=True))
	with caplog.at_level(logging.ERROR, logger="serka.answer_cache"):
		assert cache.lookup("pike") is None
		cache.store("pike", ANSWER)
		cache.clear()
	assert len(caplog.records) == 3


def test_backend_construction_error_is_a_miss() -> None:
	def broken() -> FakeBackend:
		raise RuntimeError("no credentials")

	assert AnswerCache(broken).lookup("pike") is None


def test_disabled_cache_never_hits() -> None:
	cache = AnswerCache(None)
	cache.store("pike", ANSWER)
	assert not cache.enabled
	assert cache.lookup("pike") is None


def test_threshold_and_ttl_are_passed_to_the_semantic_cache(monkeypatch: pytest.MonkeyPatch) -> None:
	captured: dict[str, Any] = {}

	class FakeSemanticCache(FakeBackend):
		def __init__(self, **kwargs: Any) -> None:
			super().__init__()
			captured.update(kwargs)

	monkeypatch.setattr("redisvl.extensions.cache.llm.SemanticCache", FakeSemanticCache)
	monkeypatch.setattr("redisvl.utils.vectorize.CustomVectorizer", lambda embed: "vectorizer")
	settings = Settings(
		_env_file=None,  # type: ignore[call-arg]
		test_mode=False,
		answer_cache_distance_threshold=0.02,
		answer_cache_ttl_seconds=60,
		redis_url="redis://cache:6379",
	)
	cache = answer_cache.from_settings(settings)
	assert cache.lookup("pike") is None
	assert captured["distance_threshold"] == 0.02
	assert captured["ttl"] == 60
	assert captured["redis_url"] == "redis://cache:6379"
	assert captured["name"] == answer_cache.CACHE_NAME


def test_test_mode_and_disabled_setting_turn_the_cache_off() -> None:
	assert not answer_cache.from_settings(Settings(_env_file=None, test_mode=True)).enabled  # type: ignore[call-arg]
	off = Settings(_env_file=None, test_mode=False, answer_cache_enabled=False)  # type: ignore[call-arg]
	assert not answer_cache.from_settings(off).enabled
