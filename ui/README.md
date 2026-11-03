# Serka UI
## Running locally
```bash
npm install
npm run dev          # http://localhost:5173, proxies /v1/ to localhost:8000
```

## Testing
```bash
npm test             # Vitest: unit tests for the AI Summary run-trace reducer (src/run/)
```

With the backend in test mode (`TEST_MODE=true`), the AI Summary stream replays a scripted run chosen by the query text, so every summary state can be seen without Bedrock or the MCP server:

| Query contains | Scripted run |
|---|---|
| `trend` | Insight run whose first draft fails evaluation, accepted on attempt 2 |
| `weather` | Out-of-scope run, refused |
| anything else | Keyword run, accepted |

## Building
```bash
npm run build        # outputs to dist/
```

## Configuration
| Setting | Dev | Production |
|---|---|---|
| API proxy | `vite.config.ts` → `/v1/` to `localhost:8000` | `nginx.conf` → `/v1/` to `http://serka:8000` |
| Theme | System preference (dark/light), togglable, persisted in `localStorage` | Same |
| Consent | Persisted in `localStorage` via Zustand | Same |
