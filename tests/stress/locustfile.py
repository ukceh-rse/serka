"""Locust stress test for the Serka API.

Simulated users mix semantic searches with streamed chat questions. As well as
Locust's normal request stats (throughput, response times, failures), the chat
stream is broken down into:

- "chat: time to first token": time from sending the request to the first
  TEXT_MESSAGE_CONTENT event. Reported as its own row in Locust's stats, so it
  shows up in the web UI, --csv output and distributed runs.
- tokens per second, per request (output tokens / generation time after the
  first token) and in aggregate (all output tokens / test duration). Tokens are
  estimated as characters / 4, since the AG-UI stream carries no token usage.
  These are printed at the end and written to --metrics-json if given.

Point --host at the API (local) or at the UI / ALB, which proxies /v1 (AWS):

	uv run locust -f tests/stress/locustfile.py --host http://localhost:9000 \\
		--headless -u 50 -r 5 -t 2m --csv stress --metrics-json stress_chat.json

Use --tags chat or --tags search to exercise one endpoint only. Every chat
request against a real deployment is a Bedrock call, so start small.
"""

import json
import random
import time

from locust import HttpUser, between, events, tag, task

CHARS_PER_TOKEN = 4
CHAT_TIMEOUT = 300  # seconds; agent runs with several tool calls can take minutes

SEARCH_QUERIES = [
	"pike eggs in Windermere",
	"telomere length in Seychelles warblers",
	"coral bleaching at high temperature",
	"radioactive contamination at Chernobyl",
	"oak gall wasps",
	"antibiotic resistance in cattle",
	"raspberry pollination",
	"urban weather in West Africa",
	"soil carbon in upland peat",
	"river flow records in Wales",
]
CHAT_QUESTIONS = [
	"Is there a dataset about pike in Windermere? Answer in one short sentence and give its title.",
	"What data is there on coral bleaching? Give the titles of up to three datasets.",
	"Are there any datasets on radioactivity around Chernobyl? Summarise briefly.",
	"Find datasets about pollinators on raspberry crops.",
	"What data does the EIDC hold on antibiotic resistance in livestock?",
]

_chat_runs: list[dict] = []
_test_start: float | None = None


@events.init_command_line_parser.add_listener
def _(parser):
	parser.add_argument(
		"--metrics-json",
		default="",
		help="Write chat stream metrics (TTFT, tokens/s) to this file",
	)


@events.test_start.add_listener
def _(environment, **kwargs):
	global _test_start
	_chat_runs.clear()
	_test_start = time.perf_counter()


class SerkaUser(HttpUser):
	wait_time = between(1, 5)

	@tag("search")
	@task(2)
	def semantic_search(self):
		self.client.get(
			"/v1/query/semantic",
			params={"q": random.choice(SEARCH_QUERIES)},
			name="/v1/query/semantic",
		)

	@tag("chat")
	@task(1)
	def chat(self):
		start = time.perf_counter()
		ttft = None
		chars = 0
		with self.client.post(
			"/v1/chat/stream",
			json={"message": random.choice(CHAT_QUESTIONS)},
			stream=True,
			catch_response=True,
			timeout=CHAT_TIMEOUT,
		) as r:
			try:
				# Decode ourselves: the API may send no charset (content-type mirrors the Accept header)
				for raw in r.iter_lines():
					line = raw.decode()
					if not line or not line.startswith("data:"):
						continue
					event = json.loads(line[5:])
					if event.get("type") == "TEXT_MESSAGE_CONTENT":
						if ttft is None:
							ttft = time.perf_counter() - start
						chars += len(event.get("delta", ""))
					elif event.get("type") == "RUN_ERROR":
						r.failure(f"RUN_ERROR: {event.get('message')}")
						return
			except Exception as e:
				r.failure(f"stream broken: {e!r}")
				return
			total = time.perf_counter() - start
			# With stream=True Locust would otherwise record only the time to response headers
			r.request_meta["response_time"] = total * 1000
			r.request_meta["response_length"] = chars
			if r.status_code != 200:
				r.failure(f"HTTP {r.status_code}")
				return
			if ttft is None:
				r.failure("no text in response")
				return

		self.environment.events.request.fire(
			request_type="SSE",
			name="chat: time to first token",
			response_time=ttft * 1000,
			response_length=0,
			exception=None,
			context={},
		)
		tokens = chars / CHARS_PER_TOKEN
		generation = total - ttft
		_chat_runs.append(
			{
				"ttft_s": ttft,
				"total_s": total,
				"tokens": tokens,
				"tokens_per_s": tokens / generation if generation > 0 else None,
			}
		)


def _pct(values: list[float], p: float) -> float:
	values = sorted(values)
	return values[min(len(values) - 1, int(p / 100 * len(values)))]


def _summary(values: list[float]) -> dict:
	if not values:
		return {}
	return {
		"mean": sum(values) / len(values),
		"p50": _pct(values, 50),
		"p95": _pct(values, 95),
		"max": max(values),
	}


@events.test_stop.add_listener
def _(environment, **kwargs):
	if not _chat_runs or _test_start is None:
		return
	duration = time.perf_counter() - _test_start
	total_tokens = sum(run["tokens"] for run in _chat_runs)
	metrics = {
		"duration_s": duration,
		"completed_chats": len(_chat_runs),
		"chats_per_s": len(_chat_runs) / duration,
		"output_tokens_estimated": total_tokens,
		"aggregate_tokens_per_s": total_tokens / duration,
		"ttft_s": _summary([run["ttft_s"] for run in _chat_runs]),
		"total_s": _summary([run["total_s"] for run in _chat_runs]),
		"tokens_per_s_per_request": _summary(
			[run["tokens_per_s"] for run in _chat_runs if run["tokens_per_s"]]
		),
	}

	print("\n=== Chat stream metrics (tokens estimated as chars/4) ===")
	print(
		f"completed chats      {metrics['completed_chats']} in {duration:.1f}s ({metrics['chats_per_s']:.2f}/s)"
	)
	print(f"aggregate tokens/s   {metrics['aggregate_tokens_per_s']:.1f}")
	print(f"{'':20} {'mean':>8} {'p50':>8} {'p95':>8} {'max':>8}")
	for key, label in [
		("ttft_s", "TTFT (s)"),
		("total_s", "total (s)"),
		("tokens_per_s_per_request", "tokens/s per req"),
	]:
		s = metrics[key]
		if s:
			print(
				f"{label:20} {s['mean']:8.2f} {s['p50']:8.2f} {s['p95']:8.2f} {s['max']:8.2f}"
			)

	if environment.parsed_options and environment.parsed_options.metrics_json:
		with open(environment.parsed_options.metrics_json, "w") as f:
			json.dump(metrics, f, indent=2)
