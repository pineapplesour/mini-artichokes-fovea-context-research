# Product App Entrypoints

Each product now has its own FastAPI entrypoint and can be run as a separate
server/app while sharing the reusable `shared_platform` core.

```bash
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.islam.server:app --host 127.0.0.1 --port 8061
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.tcm.server:app --host 127.0.0.1 --port 8062
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.simli.server:app --host 127.0.0.1 --port 8063
```

Production defaults should remove `RELIGION_LLM_DISABLED=1` so the shared
Gemma/Lawkey client can run. The per-product apps expose only their own product
profile and product pages; cross-product pages are intentionally not served from
these entrypoints.

Lawkey is different on purpose: it must preserve the original UI and engine.
Run it through the original-app adapter, which imports
`external/lawkey-original/backend.server:app` and serves the original Expo dist
at `/`.

```bash
RELIGION_LAWKEY_DB_PATH=/var/lib/universal-artichoke/lawkey/precedents.sqlite3 \
  python3 -m uvicorn apps.lawkey.server:app --host 127.0.0.1 --port 8037
```
