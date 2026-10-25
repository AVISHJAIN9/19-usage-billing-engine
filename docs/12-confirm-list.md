# Items Requiring Developer Confirmation [CONFIRM WITH DEVELOPER]

The following architectural assumptions were derived from code inspection and should be verified with the lead engineer:

1. **[CONFIRM WITH DEVELOPER]**: Confirm whether production deployment will use PostgreSQL 16 on AWS RDS with native declarative range partitioning or a distributed SQL engine like CockroachDB.
2. **[CONFIRM WITH DEVELOPER]**: Verify if the default currency code is permanently USD or if multi-currency rate conversion should be applied at rating time versus invoice finalization time.
3. **[CONFIRM WITH DEVELOPER]**: Confirm whether Stripe Billing or an open-source payment orchestration platform (e.g. Hyperswitch) will replace the local payment sandbox for production card processing.
4. **[CONFIRM WITH DEVELOPER]**: Validate whether the 90-day timestamp drift window for incoming usage events is sufficient or if historical data migration requires an administrative backfill endpoint.
5. **[CONFIRM WITH DEVELOPER]**: Confirm whether client invoice PDFs should be rendered server-side via Playwright/Chromium or if customer-side browser PDF generation is acceptable for MVP.
