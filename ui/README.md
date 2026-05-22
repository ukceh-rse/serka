# Serka UI

Vite + React + TypeScript frontend for the Serka EIDC dataset search API.

## Structure

```
ui/
├── src/
│   ├── api/          # fetch wrappers (search, chat SSE, feedback)
│   ├── components/   # Layout, SearchBar, ResultCard, AISummary, FeedbackWidget, …
│   ├── pages/        # LandingPage, ResultsPage, ChatPage
│   ├── stores/       # Zustand: appStore (theme, consent), searchStore, chatStore
│   └── theme.ts      # MUI theme — UKCEH brand colours + DM Sans font
├── public/           # Static assets (UKCEH logos)
├── nginx.conf        # Production nginx config (proxies /v1/ to the API)
└── Containerfile     # Multi-stage build: node build → nginx serve
```

## Running locally

```bash
npm install
npm run dev          # http://localhost:5173, proxies /v1/ to localhost:8000
```

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

To point the production build at a different backend, update the `proxy_pass` URL in `nginx.conf`.
