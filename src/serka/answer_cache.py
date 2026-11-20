"""Semantic cache of accepted first-turn AI Summary answers.

Backed by RedisVL's `SemanticCache` on the search Redis. Moving to Redis LangCache means
building a `LangCacheSemanticCache` in `_semantic_cache` instead: both share check/store/clear.
"""

import logging
from dataclasses import asdict, dataclass
from typing import Any, Callable, Protocol

from serka.settings import Settings

logger = logging.getLogger(__name__)

CACHE_NAME = "answer-cache"


@dataclass
class CachedAnswer:
	text: str
	path: str | None
	score: int | None
	model: str


class CacheBackend(Protocol):
	def check(self, prompt: str) -> list[dict[str, Any]]: ...

	def store(self, prompt: str, response: str, *, metadata: dict[str, Any] | None = None) -> str: ...

	def clear(self) -> None: ...


class AnswerCache:
	"""`lookup`, `store` and `clear`; any backend error is logged and treated as a miss."""

	def __init__(self, backend_factory: Callable[[], CacheBackend] | None) -> None:
		self._factory = backend_factory
		self._backend: CacheBackend | None = None

	@property
	def enabled(self) -> bool:
		return self._factory is not None

	def _get(self) -> CacheBackend | None:
		if self._backend is None and self._factory is not None:
			self._backend = self._factory()
		return self._backend

	def lookup(self, query: str) -> CachedAnswer | None:
		try:
			backend = self._get()
			if backend is None:
				return None
			hits = backend.check(prompt=query)
		except Exception:
			logger.exception("Answer cache lookup failed; treating as a miss")
			return None
		if not hits:
			return None
		hit = hits[0]
		meta = hit.get("metadata") or {}
		return CachedAnswer(
			text=hit["response"],
			path=meta.get("path"),
			score=meta.get("score"),
			model=meta.get("model", ""),
		)

	def store(self, query: str, answer: CachedAnswer) -> None:
		try:
			backend = self._get()
			if backend is None:
				return
			meta = {k: v for k, v in asdict(answer).items() if k != "text"}
			backend.store(prompt=query, response=answer.text, metadata=meta)
		except Exception:
			logger.exception("Answer cache store failed")

	def clear(self) -> None:
		try:
			backend = self._get()
			if backend is not None:
				backend.clear()
		except Exception:
			logger.exception("Answer cache clear failed")


def _semantic_cache(settings: Settings) -> CacheBackend:
	from haystack_integrations.components.embedders.amazon_bedrock import AmazonBedrockTextEmbedder
	from redisvl.extensions.cache.llm import SemanticCache  # type: ignore[import-untyped]
	from redisvl.utils.vectorize import CustomVectorizer  # type: ignore[import-untyped]

	# RedisVL's Bedrock vectorizer only takes explicit keys; this one uses the AWS credentials chain.
	embedder = AmazonBedrockTextEmbedder(model=settings.models_embedding)

	def embed(text: str) -> list[float]:
		return list(embedder.run(text=text)["embedding"])

	cache: CacheBackend = SemanticCache(
		name=CACHE_NAME,
		distance_threshold=settings.answer_cache_distance_threshold,
		ttl=settings.answer_cache_ttl_seconds,
		vectorizer=CustomVectorizer(embed=embed),
		redis_url=settings.redis_url,
	)
	return cache


def from_settings(settings: Settings) -> AnswerCache:
	"""The configured cache, or a disabled one in test mode or when turned off."""
	if settings.test_mode or not settings.answer_cache_enabled:
		return AnswerCache(None)
	return AnswerCache(lambda: _semantic_cache(settings))
