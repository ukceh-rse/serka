"""Daily caps on model-backed runs, counted in memory.

See openspec `usage-limits`. Counts belong to one process and restart from zero with it. Callers run
on the event loop and these methods never await, so each check and increment happens as one step.
"""

import math
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from starlette.requests import Request

MAX_QUERY_CHARS = 500

LimitCode = Literal["client_daily_limit", "global_daily_limit"]

LIMIT_MESSAGES: dict[LimitCode, str] = {
	"client_daily_limit": "You have reached today's limit for AI summaries. Please try again tomorrow.",
	"global_daily_limit": "AI summaries have reached today's overall limit. Please try again tomorrow.",
}


def _utc_now() -> datetime:
	return datetime.now(UTC)


class UsageLimiter:
	def __init__(
		self,
		*,
		client_limit: int,
		overall_limit: int,
		insight_limit: int,
		clock: Callable[[], datetime] = _utc_now,
	) -> None:
		self.client_limit = client_limit
		self.overall_limit = overall_limit
		self.insight_limit = insight_limit
		self.clock = clock
		self.overall_count = 0
		self.insight_count = 0
		self._clients: Counter[str] = Counter()
		self._day: date | None = None

	def _start_day(self) -> None:
		"""Discards every count, including client addresses, when the UTC day has changed."""
		day = self.clock().date()
		if day != self._day:
			self._day = day
			self.overall_count = 0
			self.insight_count = 0
			self._clients.clear()

	def admit(self, client: str) -> LimitCode | None:
		"""Counts a run for `client`, or returns the cap that rejects it without counting anything."""
		self._start_day()
		# The client goes first, so a client over its own cap uses no overall allowance.
		if self._clients[client] >= self.client_limit:
			return "client_daily_limit"
		if self.overall_count >= self.overall_limit:
			return "global_daily_limit"
		self._clients[client] += 1
		self.overall_count += 1
		return None

	def claim_insight(self) -> bool:
		"""Takes one of today's insight slots; False when none is left."""
		self._start_day()
		if self.insight_count >= self.insight_limit:
			return False
		self.insight_count += 1
		return True

	def seconds_until_reset(self) -> int:
		now = self.clock()
		midnight = datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)
		return math.ceil((midnight - now).total_seconds())


def client_address(request: Request, trusted_proxy_hops: int) -> str:
	"""The address recorded by the outermost trusted proxy (`parts[-(hops + 1)]` of X-Forwarded-For).

	Entries further left are client-supplied and ignored. With no trusted hops, or a header too
	short for them, the client is the connecting address.
	"""
	if trusted_proxy_hops > 0:
		# All header lines, as a proxy may append its own line rather than extend the client's.
		header = ",".join(request.headers.getlist("x-forwarded-for"))
		parts = [p.strip() for p in header.split(",") if p.strip()]
		if len(parts) > trusted_proxy_hops:
			return parts[-(trusted_proxy_hops + 1)]
	return request.client.host if request.client else "unknown"
