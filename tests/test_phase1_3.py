from second_brain.ingestion.extraction.entities import chunk_text, extract_entities, extract_relations
from second_brain.ingestion.stream.window import WindowStats
from second_brain.memory.retrieval.scoring import retrieval_score, MemoryUnit
from second_brain.agents.roles.stream_observer import StreamObserver
from second_brain.schemas import IoTTelemetryEvent


def test_chunk_text_splits_long_sections():
    text = "## Title\n" + ("paragraph. " * 300)
    chunks = chunk_text(text, max_chars=500, overlap=50)
    assert len(chunks) >= 2
    assert all(len(c) <= 500 for c in chunks)


def test_extract_entities_finds_services():
    text = "CheckoutService depends on PaymentGateway for authorization."
    entities = extract_entities(text)
    names = {e.name for e in entities}
    assert "CheckoutService" in names
    assert "PaymentGateway" in names


def test_extract_relations():
    text = "CheckoutService depends on PaymentGateway"
    entities = extract_entities(text)
    rels = extract_relations(text, entities)
    assert any(r.predicate == "DEPENDS_ON" for r in rels)


def test_retrieval_score_prefers_similarity():
    unit = MemoryUnit(
        id="1",
        text="memory tiers M0 M1 M2",
        embedding=[1.0, 0.0],
        importance=0.5,
    )
    score = retrieval_score(unit, "memory tiers", [1.0, 0.0])
    low = retrieval_score(unit, "unrelated topic", [0.0, 1.0])
    assert score > low


def test_stream_observer_detects_anomaly_after_warmup():
    observer = StreamObserver(sigma=2.0)
    event = IoTTelemetryEvent(
        device_id="d1", zone_id="z1", metric="temp", value=20.0
    )
    for v in [20, 20.1, 20.2, 20.0, 20.1, 20.2]:
        event.value = v
        observer.observe(event)
    event.value = 35.0
    result = observer.observe(event)
    assert result["anomaly_detected"] is True


def test_window_stats():
    w = WindowStats("d", "z", "temp")
    for v in [1, 2, 3, 4, 5]:
        w.update(float(v))
    assert w.mean == 3.0
    assert w.count == 5
