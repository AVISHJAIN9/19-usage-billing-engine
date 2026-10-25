# F1: Idempotent Raw Usage Ingestion Pipeline

## Overview & Architecture
The usage event ingestion pipeline in `backend/src/metering/ingestion.py` ingests high-frequency consumption events (API requests, storage megabytes, model tokens) while guaranteeing exactly-once accounting.

```mermaid
flowchart TD
    RawEvent[Incoming Usage Event JSON] --> PydanticVal[Pydantic v2 Schema Validation]
    PydanticVal --> DriftCheck{Timestamp Drift > 90d or > 1h future?}
    DriftCheck -->|Yes| RejectDrift[HTTP 422 TIMESTAMP_OUT_OF_BOUNDS]
    DriftCheck -->|No| IdempotencyQuery{Check (tenant_id, idempotency_key) in DB}
    IdempotencyQuery -->|Key Exists| ReturnAck[Return Status: DUPLICATE (200 OK)]
    IdempotencyQuery -->|New Key| PersistEvent[INSERT into usage_events table]
    PersistEvent --> UpdateRollup[Increment Pre-Aggregated Hourly Rollup]
    UpdateRollup --> Return201[Return Status: ACCEPTED (201 Created)]
```

## Say It Out Loud
> "I designed the ingestion pipeline in `metering/ingestion.py` to absorb millions of raw consumption events while guaranteeing exactly-once accounting. When a client service reports API calls or compute runtimes, the pipeline first runs strict Pydantic validation to verify field formats and check that quantities are positive.
> 
> Next, it performs a timestamp drift check: events with timestamps older than 90 days or more than one hour into the future are rejected to prevent backdated billing fraud. Then it queries the idempotency index. If the event is new, it persists it and returns status ACCEPTED; if it has already been processed, it acknowledges it with status DUPLICATE so the caller knows it was received without double-counting.
> 
> I chose this synchronous database verification model rather than an eventual consistency queue because billing accuracy cannot tolerate race conditions during period close.
> 
> When payload validation fails, the pipeline returns a 422 Unprocessable Entity with an explicit machine-readable code like TIMESTAMP_TOO_OLD.
> 
> A known trade-off is that checking the database on every event limits single-node throughput, which is why I would add a Redis bloom filter or key-value cache for deduplication at higher scale."
