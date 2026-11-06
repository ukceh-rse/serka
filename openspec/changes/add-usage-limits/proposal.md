# Proposal

## Why

The AI Summary endpoint is public and unauthenticated, and each run pays for Bedrock model calls, including Sonnet on the insight path. Nothing limits how many runs happen, how long a query can be, how much a model can write, or how many model calls one retrieval can make, so the Bedrock bill has no upper limit. We want a known daily ceiling, enforced in the app because only the app can tell what a run costs.

## What Changes

- Add daily caps on model-backed runs, enforced at admission: 30 per client IP and 500 overall. Requests over a cap get HTTP 429 with `Retry-After`, and no model is called. Counters are kept in memory and reset at midnight UTC and on restart.
- Add a daily cap of 100 `insight` runs. The label is only known after classification, so a request over this cap ends inside the stream with a fixed message and a new `insight_limit_reached` outcome. It does not fall back to the keyword path.
- Limit `message` and `q` to 500 characters in the API, and stop the search box accepting more. Rejected queries use no allowance.
- **BREAKING**: `/v1/chat/stream/agui` returns 404 unless the new `chat_enabled` setting is on (default off), and the `/chat` UI route is removed. Chat is a possible future feature; only search and AI Summary are live. The code stays in place.
- **BREAKING**: lower the `insight` attempt limit from 3 to 2.
- Set an output token limit for every pipeline stage, and limit retrieval in each insight run to 10 model calls and 200,000 tokens across its attempts. Reaching a retrieval limit moves on to answering with the data already gathered.
- Tell the answer stage to write at most 300 words, not counting link URLs, whatever length the user asks for, and never to drop a citation to save words.
- Have the evaluator fail answers that are clearly over the word limit or that use retrieved data without citing it.
- Have the classifier refuse instruction-override attempts and demands for excessive output, even when they mention datasets.
- Show usage limits in the AI Summary as their own outcome rather than as a generic error.

Plain search (`/v1/query/semantic`) is length-limited but does not count towards any daily cap: it reranks locally and should make at most one short embedding call.

## Capabilities

### New Capabilities
- `usage-limits`: daily caps on model-backed runs, query length limits, client identification, how limits are reported, and whether the chat endpoint is available.

### Modified Capabilities
- `chat-agent`: stricter refusal rules, a limit of 2 insight attempts, answer length and citation rules that the evaluator checks, and limits on output and retrieval.
- `chat-agent-events`: the agui endpoint is conditional, requests can be rejected before a stream starts, and runs have a new outcome status.
- `ai-summary-run-overview`: a distinct presentation for usage limits, scenarios updated for 2 attempts, and a scripted test mode run for the insight cap.

## Impact

- **API**: `/v1/chat/stream` can return 429, and returns 422 for queries over the limit. `/v1/query/semantic` returns 422 for queries over the limit. `/v1/chat/stream/agui` returns 404 by default. The stream gains the `insight_limit_reached` status.
- **Code**: `src/serka/settings.py`, `src/serka/routers/chat.py`, `src/serka/routers/query.py`, `src/serka/routers/dependencies.py`, `src/serka/routers/mock.py`, `src/serka/main.py`, `src/serka/chat/pipeline.py`, `src/serka/chat/service.py`, `src/serka/prompts.py`, and a new usage limiter module.
- **UI**: `ui/src/App.tsx`, `ui/src/api/chat.ts`, `ui/src/components/SearchBar.tsx`, `ui/src/components/RunOverview.tsx`, `ui/src/pages/ResultsPage.tsx`, `ui/src/run/runTrace.ts`.
- **Config and data**: new settings in `.env.example`. Daily counts are held in memory only, so client IPs are never written to disk and are discarded at each reset. No new Python dependency. A deployment behind proxies must set `TRUSTED_PROXY_HOPS`, or all users share one IP allowance.
- **Tests and docs**: `tests/test_chat_pipeline.py`, `tests/test_chat_api.py`, `tests/test_app.py`, `ui/src/run/runTrace.test.ts`, `scripts/smoke-test.py`, `README.md`. All tests run on a local machine, never on AWS infrastructure or against a deployed environment. The smoke test is the only one that calls Bedrock models.
- **Out of scope**: limits on chat history (needed before `chat_enabled` is used in production), a code check that cited URLs appear in the retrieved data, WAF or nginx rate limiting, per-user accounts, daily caps on plain search, and AWS budget alerts and deployment scripts (the deployment is being reworked separately).
