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

## Next steps

1. Create the Appwrite project, database, bucket, and two Functions.
2. Upload the manifest objects to a private staging bucket.
3. Implement `market-api` and validate its responses against this local contract.
4. Add a frontend data-provider switch, keeping the current embedded provider as rollback.
5. Add Auth and server-enforced Free/Pro entitlements before moving premium calculations.
