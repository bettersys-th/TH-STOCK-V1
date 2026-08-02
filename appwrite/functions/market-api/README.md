# market-api

Read-only gateway from the public website to the private versioned market-data bucket.

## Staging function settings

- Function ID: `market-api`
- Runtime: latest supported Python 3.12
- Root directory: `appwrite/functions/market-api`
- Entrypoint: `main.py` or `handler.py` (`main.py` is a file-based compatibility loader)
- Build command: `pip install -r requirements.txt`
- Execute access: `Any` (market prices are public; Storage remains private)
- Dynamic API key scopes: `files.read`, `rows.read` only
- Timeout: 15 seconds

Function environment variables:

- `ALLOWED_ORIGINS=https://bettersys-th.github.io`
- `MARKET_DATABASE_ID=app`
- `MARKET_VERSIONS_TABLE_ID=data_versions`
- `MARKET_BUCKET_ID=market-data`
- `MARKET_CHANNEL=staging`

Add the exact custom-domain origin later as another comma-separated `ALLOWED_ORIGINS` value.
Do not create an API-key variable: Appwrite injects a per-execution dynamic key through the
`x-appwrite-key` request header.

## Endpoints

- `GET /health` — verifies pointer, manifest, and Storage access
- `GET /v1/manifest` — public dataset metadata and ticker names; no private file IDs
- `GET /v1/stocks/{TICKER}` — one verified ticker payload
- `OPTIONS *` — allowlisted browser preflight

All other methods and paths are rejected. Internal exceptions are logged in Appwrite but returned
to clients only as `service_unavailable`.
