# Appwrite migration

The migration is incremental so the existing GitHub Pages build remains the rollback path.

## Step 1 — cloud-ready market data (completed)

`scripts/cloud_export.py` converts the monolithic price store into provider-neutral objects under
`data/cloud_market/` after every successful daily update:

```text
cloud_market/
  manifest.json
  stocks/{TICKER}.json.gz
  summaries/cycles.json.gz
  summaries/dividends.json.gz
  summaries/accumulation.json.gz
  summaries/swing.json.gz
  summaries/dca.json.gz
```

`manifest.json` is the upload contract. It contains schema version, data date, ticker coverage,
bar counts, object sizes, and SHA-256 checksums. The pipeline verifies every generated ticker
against `prices.json.gz` before replacing the prior export. Gzip output is deterministic, so an
unchanged ticker does not create a new binary diff.

The browser still uses the embedded datasets in `index.html`; no production behavior changes in
this step.

## Step 2 — staging infrastructure contract (prepared)

`appwrite/resources.json` documents the database tables, private Storage bucket, two-Function
budget, and deny-by-default permissions. It is intentionally reviewed before resources are created;
the production project must not be provisioned from an unreviewed, broad admin key.

Create a staging project in Appwrite Console, then:

1. Create a private bucket with ID `market-data`, file security enabled, extensions `gz,json`,
   encryption enabled, and a 50 MB maximum file size. Grant no client permissions.
2. Create a server API key limited to Storage file read/write scopes for this bucket workflow.
   Do not grant key-management, user-management, or database scopes.
3. Store the endpoint, project ID, key, and bucket ID outside the repository using the names in
   `.env.example`. The API key must never use an `APP_*` browser-visible variable prefix.
4. Build and inspect the upload without network access:

   `python scripts/upload_appwrite.py`

5. Only after reviewing the dry-run, upload to staging with server environment variables present:

   `python scripts/upload_appwrite.py --apply`

The uploader verifies every object's size and SHA-256 checksum, uses immutable content-addressed
file IDs, skips existing objects, and uploads the manifest last. It does not delete remote data.
After the manifest exists, it upserts row ID `staging` in `app/data_versions` as the atomic current
pointer. The uploader key therefore needs only Storage file read/write and Database row read/write
scopes; table/schema administration scopes remain disabled.
The workflow job allows up to 90 minutes because a full Yahoo refresh and the first staging upload
can exceed 30 minutes. A canceled run is safe to retry: already uploaded objects are detected and
skipped.

Add the following GitHub Actions repository secrets. During staging, uploads run only from a manual
**Run workflow** with `upload_appwrite_staging` selected. Scheduled daily runs do not upload until
the database pointer and retention policy are implemented. Missing secrets also stop only the
staging upload and do not interrupt the existing daily website update:

- `APPWRITE_ENDPOINT`
- `APPWRITE_PROJECT_ID`
- `APPWRITE_API_KEY`
- `APPWRITE_MARKET_BUCKET_ID`

Manual staging upload deliberately uses the already verified `prices.json.gz` committed in the
repository. It does not call Yahoo first, keeping provider availability separate from an Appwrite
deployment test. Scheduled runs continue to use the full update-and-quality pipeline.

### Recommended first upload from Windows

Run `upload_appwrite_staging.bat`. The wrapper prompts for Project ID and API key, hides the key
while typed, keeps credentials only in the current process environment, builds and verifies the
export, shows a dry-run, and requires typing `UPLOAD` before any network write. It never creates an
`.env` file. Each run uses a unique ignored session directory and removes it afterward, avoiding
collisions with GitHub Desktop, antivirus, or another generated export. GitHub Actions remains an
optional staging fallback rather than the recommended first upload path.

If an upload is canceled, immutable objects from that incomplete attempt can remain safely but use
storage. Run `cleanup_appwrite_staging.bat` to inspect them. It downloads the newest completed
manifest, proves every referenced object exists, retains that manifest and all referenced objects,
and reports orphan count/bytes. Deletion occurs only after typing `DELETE ORPHANS`; unknown or
manually-created files are never deleted.

## Next steps

- DCA summary API is available at `/v1/summaries/dca`; the web page loads it on first opening the DCA tab and falls back to `data/dca_compact.json` on GitHub Pages.
- Cycle summary API is available at `/v1/summaries/cycles`; the Cycle tab lazy-loads it on first use and falls back to `data/cycles_compact.json` on GitHub Pages.
- Cycle and DCA payloads are no longer embedded in `index.html`, reducing the generated landing page by about 4.5 MiB while preserving a separate static rollback path.

1. Completed: deploy `market-api-v2` from `appwrite/functions/market-api` with `rows.read` and `files.read` only.
2. Completed: validate `/health`, `/v1/manifest`, and `/v1/stocks/PTT` against staging.
3. In progress: the frontend verifies the Appwrite manifest and uses its ticker catalog while retaining embedded calculations as rollback.
4. Next: migrate Cycle and DCA payloads lazily, one feature at a time, then add Auth and server-enforced Free/Pro entitlements.
