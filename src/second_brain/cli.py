from __future__ import annotations

import argparse
import asyncio
import json

import httpx

from second_brain.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="The Second Brain CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    query_p = sub.add_parser("query", help="Run a query against the API")
    query_p.add_argument("text", help="Query text")
    query_p.add_argument("--url", default=None)

    ingest_p = sub.add_parser("ingest", help="Ingest a markdown/text file")
    ingest_p.add_argument("path", help="File path")
    ingest_p.add_argument("--title", default=None)
    ingest_p.add_argument("--url", default=None)

    sub.add_parser("health", help="Check API health")

    args = parser.parse_args()
    settings = get_settings()
    base_url = args.url if hasattr(args, "url") and args.url else f"http://localhost:{settings.api_port}"

    if args.command == "health":
        resp = httpx.get(f"{base_url}/health", timeout=10)
        print(json.dumps(resp.json(), indent=2))
    elif args.command == "query":
        resp = httpx.post(
            f"{base_url}/query",
            json={"query": args.text},
            timeout=60,
        )
        print(json.dumps(resp.json(), indent=2))
    elif args.command == "ingest":
        from pathlib import Path

        path = Path(args.path)
        content = path.read_text(encoding="utf-8")
        resp = httpx.post(
            f"{base_url}/ingest/document",
            json={
                "uri": f"file://{path.as_posix()}",
                "title": args.title or path.name,
                "content": content,
            },
            timeout=60,
        )
        print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()
