# Tasks

All tests and checks in this change run on a local machine. None runs on AWS infrastructure or against a deployed environment.

## 1. Usage limiter

- [x] 1.1 Add `usage_ip_daily_limit` (30), `usage_global_daily_limit` (500), `usage_insight_daily_limit` (100), `trusted_proxy_hops` (0) and `chat_enabled` (false) to `src/serka/settings.py`, with a comment that history limits are required before enabling chat in production; verify defaults in `tests/test_settings.py`
- [x] 1.2 Add `src/serka/usage.py` with `UsageLimiter` (`admit`, `claim_insight`) with in-memory counts as described in design.md; verify with new `tests/test_usage.py` that counts stop at each cap, a client rejection leaves the overall count unchanged, and a new UTC day resets counts
- [x] 1.3 Discard client addresses when the UTC day changes; verify in `tests/test_usage.py` that no earlier-day address or count remains after a new day
- [x] 1.4 Add a client address function that counts `X-Forwarded-For` entries from the right using `trusted_proxy_hops`; verify the spoofed header, no-hops and too-short-header scenarios in `tests/test_usage.py`
- [x] 1.5 Document the new settings in `.env.example`; verify that `tests/test_settings.py` loads the file

## 2. API enforcement

- [x] 2.1 Add `MAX_QUERY_CHARS = 500` as the `max_length` of `QueryRequest.message` and `q`; verify in `tests/test_chat_api.py` and `tests/test_app.py` that 500 characters is accepted, and that 501 returns 422 with no model call, no count change and no feedback log entry
- [x] 2.2 Add a side-effect-free `get_usage_limiter` dependency and call `admit` in the `/v1/chat/stream` handler body, returning 429 with `Retry-After` and a `{code, message}` detail for each cap; verify each response in `tests/test_chat_api.py`, including that no model is called
- [x] 2.3 Override the limiter in test mode in `src/serka/main.py` so caps are not enforced; verify in `tests/test_app.py` with more than 30 requests
- [x] 2.4 Gate `/v1/chat/stream/agui` on `chat_enabled` with a dependency that raises 404; when enabled, call `admit` and apply the length limit to the latest user message; verify both states in `tests/test_chat_api.py`, enabling the setting for the existing agui tests
- [x] 2.5 Document the limits, status codes and `chat_enabled` in `README.md`; verify the documented values match `src/serka/settings.py`

## 3. Pipeline limits

- [x] 3.1 Change `MAX_ATTEMPTS["insight"]` to 2, the scripted `max_attempts` in `src/serka/routers/mock.py`, and the limit in `README.md`; update `tests/test_chat_pipeline.py` and `tests/test_chat_api.py`, rewrite `test_three_failed_attempts_return_best_draft` for two drafts, and verify with `uv run pytest tests/test_chat_pipeline.py tests/test_chat_api.py`
- [x] 3.2 Add a `stage` argument to `_run` that applies the per-stage `max_tokens` from design.md and logs the tokens used, without query text; verify in `tests/test_chat_pipeline.py` that each stage's model request carries its limit and that usage is logged
- [x] 3.3 Pass `UsageLimits(request_limit=10, total_tokens_limit=200_000)` in `Execute`, with usage shared across the run's attempts, catch `UsageLimitExceeded`, and continue to `Synthesize`; verify in `tests/test_chat_pipeline.py` that gathered results reach composition, and that no results composes as an empty retrieval
- [x] 3.4 Add `claim_insight` to `ChatDeps`, wire it through `make_stream_fn`, claim a slot in `Route` for insight queries, and add the `InsightLimit` node, `INSIGHT_LIMIT_MESSAGE` and `insight_limit_reached` status; verify in `tests/test_chat_pipeline.py` the steps classify, route and limit, the outcome values, no later model calls, one claim across two attempts, and that keyword runs never claim
- [x] 3.5 Add a `quota` query scenario to `_select_run` in `src/serka/routers/mock.py` that plays the insight limit run; verify in `tests/test_chat_api.py`

## 4. Prompts

- [x] 4.1 Apply the classifier exception from design.md to `CLASSIFY_PROMPT`, placed before the decision rule; verify with a test in `tests/test_chat_pipeline.py` that the text is present and comes before "Decision rule"
- [x] 4.2 Add `MAX_ANSWER_WORDS = 300` and apply the word limit and citation wording to `SYNTHESIZE_PROMPT` and `EVALUATE_PROMPT`, including the `writing` problem definition; verify with a test that both prompts contain the value and the citation rules
- [x] 4.3 Add smoke cases to `scripts/smoke-test.py`: the 10,000 word essay and instruction-override queries are refused, the short-format and detailed-answer queries are not, and an in-scope answer with retrieved data contains at least one inline link and is at most about 330 words excluding URLs; verify with `python -m py_compile scripts/smoke-test.py`

## 5. UI

- [x] 5.1 Add `MAX_QUERY_CHARS` to `ui/src/constants` and set it as `maxLength` on the `SearchBar` input; verify `npm run build` passes and that the search box stops at 500 characters
- [x] 5.2 Remove the `/chat` route and `ChatPage` import from `ui/src/App.tsx`, keeping `ChatPage`, `chatStore` and `streamChat`; verify `npm run build` passes and `/chat` shows no chat page
- [x] 5.3 Add the `usage_limit` run status and `USAGE_LIMIT` event to `ui/src/run/runTrace.ts`, mapping `insight_limit_reached` to it, with a `limit` stage phrase and summary text; verify in `ui/src/run/runTrace.test.ts`, and update its attempt fixtures to a limit of 2
- [x] 5.4 Add neutral styling for `usage_limit` to `STATUS_STYLE` in `ui/src/components/RunOverview.tsx`; verify `npm run build` passes, which also checks that the status map is complete
- [x] 5.5 Throw a `UsageLimitError` with the server message from `streamSummary` on 429, and apply `USAGE_LIMIT` in `ResultsPage`; verify with a unit test for the 429 path, and confirm other HTTP errors keep the existing error state

## 6. Integration checks

- [x] 6.1 Run the full suites and confirm they pass: `uv run pytest` and `npm test` in `ui/`
- [x] 6.2 In test mode, run the API and UI and confirm the keyword, `trend`, `weather` and `quota` queries each show the expected summary row, using the `run` skill or a browser
- [x] 6.3 With the user's approval, because its model calls spend a small amount on Bedrock, run `uv run scripts/smoke-test.py` from a local machine, never on a deployed instance; confirm all checks pass, log token usage per stage, and adjust the token limits in design.md and `pipeline.py` if any stage nears its limit

## 7. Review follow-ups

- [x] 7.1 Correct the `TRUSTED_PROXY_HOPS` documentation to appending proxies minus one
- [x] 7.2 Keep the AI Summary and its run details when the type filter changes, re-running only the search; verify in a browser that a filter change sends no request to `/v1/chat/stream`, including during a run
- [x] 7.3 Name the retrieval limit in the summary row and timeline when a run ends with attempts left; verify in `ui/src/run/runTrace.test.ts`
- [x] 7.4 Compose from gathered results when `execute` reaches its output limit during a tool call; verify in `tests/test_chat_pipeline.py`
- [x] 7.5 Print the smoke test's token report when a run raises; verify with `python -m py_compile scripts/smoke-test.py`
- [x] 7.6 Hide feedback on the daily limit message; verify in a browser with consent given
- [x] 7.7 Reject blank queries and agui requests with no user message with 422; verify in `tests/test_chat_api.py`

## Workflow follow-up

- Set `TRUSTED_PROXY_HOPS` to the appending proxies minus one (1 for the current Terraform chain).
- Check the EU prices on the AWS pricing page.
- Watch the `limit_reached` rate after release.
- Archive the change after review.
