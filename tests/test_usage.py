from datetime import UTC, datetime

from starlette.requests import Request

from serka.usage import UsageLimiter, client_address

DAY_1 = datetime(2026, 11, 6, 23, 59, 30, 500000, tzinfo=UTC)
DAY_2 = datetime(2026, 11, 7, 0, 0, 1, tzinfo=UTC)
ADDRESS = "203.0.113.7"


class Clock:
	def __init__(self, now: datetime = DAY_1) -> None:
		self.now = now

	def __call__(self) -> datetime:
		return self.now


def limiter(clock: Clock | None = None, *, client: int = 2, overall: int = 3, insight: int = 2) -> UsageLimiter:
	return UsageLimiter(client_limit=client, overall_limit=overall, insight_limit=insight, clock=clock or Clock())


# --- caps ---


def test_client_cap_stops_only_that_client() -> None:
	usage = limiter(overall=10)
	assert usage.admit("a") is None
	assert usage.admit("a") is None
	assert usage.admit("a") == "client_daily_limit"
	assert usage.admit("b") is None


def test_overall_cap() -> None:
	usage = limiter()
	assert [usage.admit(c) for c in "abc"] == [None, None, None]
	assert usage.admit("d") == "global_daily_limit"
	assert usage.overall_count == 3


def test_client_rejection_leaves_overall_count_unchanged() -> None:
	usage = limiter(overall=10)
	usage.admit("a")
	usage.admit("a")
	assert usage.overall_count == 2
	assert usage.admit("a") == "client_daily_limit"
	assert usage.overall_count == 2


def test_overall_rejection_does_not_count_or_record_the_client() -> None:
	usage = limiter(client=1, overall=1)
	assert usage.admit("a") is None
	assert usage.admit("b") == "global_daily_limit"
	assert list(usage._clients) == ["a"]


def test_insight_cap_is_separate_from_admission() -> None:
	usage = limiter(insight=2)
	assert [usage.claim_insight() for _ in range(3)] == [True, True, False]
	assert usage.overall_count == 0
	assert usage.admit("a") is None


def test_new_utc_day_resets_counts() -> None:
	clock = Clock()
	usage = limiter(clock, client=1, insight=1)
	usage.admit("a")
	usage.claim_insight()
	assert usage.admit("a") == "client_daily_limit"
	clock.now = DAY_2
	assert usage.claim_insight() is True
	assert usage.admit("a") is None
	assert usage.overall_count == 1


def test_new_day_discards_earlier_addresses() -> None:
	clock = Clock()
	usage = limiter(clock)
	usage.admit(ADDRESS)
	clock.now = DAY_2
	usage.admit("198.51.100.1")
	assert list(usage._clients) == ["198.51.100.1"]


def test_seconds_until_reset_rounds_up_to_next_midnight() -> None:
	assert limiter(Clock(DAY_1)).seconds_until_reset() == 30
	midnight = datetime(2026, 11, 7, tzinfo=UTC)
	assert limiter(Clock(midnight)).seconds_until_reset() == 86400


# --- client address ---


def request(*forwarded: str, connecting: str = "10.0.0.9") -> Request:
	headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
	return Request({"type": "http", "headers": headers, "client": (connecting, 1234)})


def test_spoofed_entries_on_the_left_are_ignored() -> None:
	assert client_address(request("1.1.1.1, 203.0.113.7, 10.0.0.5"), 1) == "203.0.113.7"
	assert client_address(request("9.9.9.9, 203.0.113.7, 10.0.0.5"), 1) == "203.0.113.7"


def test_two_hops_counts_further_from_the_right() -> None:
	assert client_address(request("1.1.1.1, 203.0.113.7, 10.0.0.5, 10.0.0.6"), 2) == "203.0.113.7"


def test_no_hops_ignores_the_header() -> None:
	assert client_address(request("203.0.113.7, 10.0.0.5"), 0) == "10.0.0.9"


def test_too_short_header_uses_the_connecting_address() -> None:
	assert client_address(request("10.0.0.5"), 1) == "10.0.0.9"
	assert client_address(request(), 1) == "10.0.0.9"


def test_separate_header_lines_are_read_together() -> None:
	assert client_address(request("1.1.1.1", "203.0.113.7, 10.0.0.5"), 1) == "203.0.113.7"


def test_missing_connection_info_has_a_shared_key() -> None:
	assert client_address(Request({"type": "http", "headers": [], "client": None}), 0) == "unknown"
