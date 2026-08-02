# Public repository security checklist

The source is public, but credentials, private user data, paid-only logic, and provider data without
redistribution rights must never be committed.

## GitHub settings after pushing

1. Enable Secret scanning, Push protection, and Private vulnerability reporting under **Settings >
   Code security and analysis**.
2. Set the repository's default `GITHUB_TOKEN` permission to read-only. The scheduled update job
   grants `contents: write` only to its own job because it must commit generated data.
3. Add a default-branch ruleset: block force pushes and deletions and require the test workflow.
4. Store provider keys only in **Settings > Secrets and variables > Actions**—never in source,
   screenshots, issues, logs, or `.env.example`.
5. Review all Secret scanning alerts. Revoke and rotate any real key that ever appeared.

## Architecture boundary

GitHub Pages sends HTML, JavaScript, and public data to every visitor. UI hiding cannot protect a
paid feature. Before subscriptions, move entitlement checks, private datasets, provider keys, and
premium calculations to an authenticated backend, returning only authorized results.

## Market-data boundary

Before monetizing or redistributing generated datasets, verify the current license and terms for
every source. Technical API access does not itself grant redistribution rights.
