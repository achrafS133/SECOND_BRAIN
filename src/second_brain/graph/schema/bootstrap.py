from __future__ import annotations

import logging
from pathlib import Path

from neo4j import GraphDatabase

from second_brain.config import Settings

logger = logging.getLogger(__name__)


def bootstrap_schema(settings: Settings, retries: int = 5, delay_seconds: float = 3.0) -> dict:
    import time

    schema_path = (
        Path(__file__).resolve().parents[4] / "graph" / "schema" / "init.cypher"
    )
    if not schema_path.exists():
        schema_path = Path("graph/schema/init.cypher")

    statements = [
        s.strip()
        for s in schema_path.read_text(encoding="utf-8").split(";")
        if s.strip() and not s.strip().startswith("//") and "CREATE" in s.upper()
    ]

    last_error = ""
    for attempt in range(1, retries + 1):
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        applied = 0
        errors: list[str] = []
        try:
            driver.verify_connectivity()
            with driver.session() as session:
                for stmt in statements:
                    try:
                        session.run(stmt)
                        applied += 1
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{stmt[:60]}... -> {exc}")
            logger.info("Neo4j schema bootstrap: %s statements applied", applied)
            return {"applied": applied, "errors": errors}
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            logger.warning("Neo4j bootstrap attempt %s/%s failed: %s", attempt, retries, exc)
            time.sleep(delay_seconds)
        finally:
            driver.close()

    return {"applied": 0, "errors": [last_error or "Neo4j unavailable"]}


def main() -> None:
    from second_brain.config import get_settings

    logging.basicConfig(level=logging.INFO)
    result = bootstrap_schema(get_settings())
    print(result)


if __name__ == "__main__":
    main()
