import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from metering.ingestion import UsageIngestionPipeline, IngestEventPayload

@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_BIL_032_usage_dimensions(async_session):
    """
    BIL-032: Usage dimensions.
    Tests recording events with multi-dimensional attributes (e.g. model, region)
    and aggregating usage broken down by dimensions.
    """
    pipeline = UsageIngestionPipeline(async_session)

    events = [
        IngestEventPayload(
            event_id=f"evt-dim-{i}",
            tenant_id="tenant-ai",
            customer_id="cust-ml-user",
            event_type="tokens.completion",
            quantity=qty,
            idempotency_key=f"dim-key-{i}",
            dimensions={"model": model, "region": region}
        )
        for i, (qty, model, region) in enumerate([
            (100, "gemini-flash", "us-central1"),
            (250, "gemini-pro", "us-central1"),
            (150, "gemini-flash", "europe-west1"),
            (300, "gemini-pro", "europe-west1"),
        ])
    ]

    await pipeline.ingest_batch(events)

    # 1. Aggregate by model dimension
    by_model = await pipeline.aggregate_by_dimension(
        tenant_id="tenant-ai",
        customer_id="cust-ml-user",
        event_type="tokens.completion",
        dimension_key="model"
    )
    assert by_model["gemini-flash"] == 250  # 100 + 150
    assert by_model["gemini-pro"] == 550    # 250 + 300

    # 2. Aggregate by region dimension
    by_region = await pipeline.aggregate_by_dimension(
        tenant_id="tenant-ai",
        customer_id="cust-ml-user",
        event_type="tokens.completion",
        dimension_key="region"
    )
    assert by_region["us-central1"] == 350   # 100 + 250
    assert by_region["europe-west1"] == 450  # 150 + 300
