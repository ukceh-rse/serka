# Serka UI
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
