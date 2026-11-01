# Reusable portfolio module

This subproject is the distribution boundary. Build this directory, not the repository root.

- Importing the package must not read configuration, environment, home, data, a database or the network.
- Do not import the legacy analyzer, WebUI, plotting stack or application code.
- Providers accept caller-supplied public identity, clock and transport. Fixed read methods only; no signing, transaction submission, credentials discovery, endpoint failover around a denial or implicit persistence.
- Holdings use integer base units and decimals. Financial arithmetic uses Decimal; never silently convert through float.
- Valuation accepts an explicit clock, price set, freshness limit and optional explicit basis. Missing inputs remain null. Ownership, transfers, representation selection, source precedence, aggregation and tax policy belong to the consumer.
- Include only generic source, docs and synthetic tests in Git. Never copy a real wallet, account binding, balance, transaction, basis, price snapshot or secret into a fixture.
- Run the isolated core tests, build the wheel and check its allowlisted file inventory. No legacy or live network execution in CI.
