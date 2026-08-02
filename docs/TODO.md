# Project TODO

## P0 — Price data completeness

- [ ] Produce a coverage report for every ticker: first date, last date, bar count, and missing trading-date gaps.
- [ ] Separate expected gaps (IPO date, suspension, delisting, no-trade day) from provider/download failures.
- [ ] Compare suspicious tickers against a second price source before repairing data.
- [ ] Prevent incomplete or materially stale ticker histories from being published silently.
- [ ] Show data-coverage warnings in Cycle, Accumulation, Swing, and DCA when analysis is unreliable.
- [ ] Rebuild and re-upload Appwrite summaries only after the repaired price store passes validation.

## Deferred — Staging and production separation

- [ ] Create a production channel/pointer separate from staging.
- [ ] Add a staging validation gate and an explicit staging-to-production promotion command.
- [ ] Make the public website read production only while new uploads remain in staging.

Status: deferred until price coverage and the remaining analysis features are reliable.

## Deferred — Free/Pro packages

See `DCA_PACKAGES_ROADMAP.md`. Membership, payments, and entitlements remain deferred.

