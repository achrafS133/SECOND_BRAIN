from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel

from second_brain.config import get_settings
from second_brain.schemas import (
    ActionDecision,
    IngestDocumentRequest,
    IoTTelemetryEvent,
    PendingAction,
    ProposedAction,
    QueryRequest,
    QueryResponse,
)
from second_brain.services.container import ServiceContainer

logger = logging.getLogger(__name__)


class ConsolidateRequest(BaseModel):
    session_id: str


class ProposeActionRequest(BaseModel):
    session_id: str
    proposed: ProposedAction


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    container = ServiceContainer(settings)
    await container.startup()
    app.state.container = container
    logger.info("Second Brain API started (%s)", settings.app_env)
    yield
    await container.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="The Second Brain",
        description="Cognitive Operating System API",
        version="0.4.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        container: ServiceContainer = app.state.container
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": "0.4.0",
            "llm_configured": settings.llm_configured,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.active_llm_model,
            "services": await container.health(),
        }

    @app.post("/query", response_model=QueryResponse)
    async def query(body: QueryRequest) -> QueryResponse:
        container: ServiceContainer = app.state.container
        response = await container.cogos.run(
            query=body.query,
            session_id=body.session_id,
            task_type=body.task_type,
        )
        await container.record_session_observation(
            body.session_id,
            f"Q: {body.query}\nA: {response.answer[:500]}",
            importance=0.65,
        )
        return response

    @app.post("/query/stream")
    async def query_stream(body: QueryRequest) -> StreamingResponse:
        container: ServiceContainer = app.state.container
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def trace_hook(name: str, desc: str, state: str = "done") -> None:
            await queue.put({"name": name, "desc": desc, "state": state})

        async def generate():
            yield f"data: {json.dumps({'name': 'User Query', 'desc': body.query[:120], 'state': 'done'})}\n\n"

            task = asyncio.create_task(
                container.cogos.run(
                    query=body.query,
                    session_id=body.session_id,
                    task_type=body.task_type,
                    trace_hook=trace_hook,
                )
            )

            while True:
                if task.done() and queue.empty():
                    break
                try:
                    step = await asyncio.wait_for(queue.get(), timeout=0.25)
                    yield f"data: {json.dumps(step)}\n\n"
                except asyncio.TimeoutError:
                    continue

            response = await task
            await container.record_session_observation(
                body.session_id,
                f"Q: {body.query}\nA: {response.answer[:500]}",
                importance=0.65,
            )
            payload = {
                "event": "complete",
                "response": json.loads(response.model_dump_json()),
            }
            yield f"data: {json.dumps(payload)}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/ingest/document")
    async def ingest_document(body: IngestDocumentRequest) -> dict:
        container: ServiceContainer = app.state.container
        chunk_ids = await container.ingest_document(body)
        return {
            "status": "ingested",
            "uri": body.uri,
            "chunk_count": len(chunk_ids),
            "chunk_ids": chunk_ids,
        }

    @app.post("/graph/communities/build")
    async def build_communities() -> dict:
        container: ServiceContainer = app.state.container
        summaries = await container.build_communities()
        return {"count": len(summaries), "communities": summaries}

    @app.post("/stream/iot")
    async def stream_iot(event: IoTTelemetryEvent) -> dict:
        container: ServiceContainer = app.state.container
        return await container.process_iot(event)

    @app.post("/memory/consolidate")
    async def consolidate_memory(body: ConsolidateRequest) -> dict:
        container: ServiceContainer = app.state.container
        return await container.consolidate_session(body.session_id)

    @app.get("/actions/pending", response_model=list[PendingAction])
    async def list_pending_actions() -> list[PendingAction]:
        container: ServiceContainer = app.state.container
        return await container.list_pending_actions()

    @app.post("/actions/propose", response_model=PendingAction)
    async def propose_action(body: ProposeActionRequest) -> PendingAction:
        container: ServiceContainer = app.state.container
        return await container.propose_action(body.proposed, body.session_id)

    @app.post("/actions/{action_id}/approve", response_model=PendingAction)
    async def approve_action(action_id: str, decision: ActionDecision) -> PendingAction:
        container: ServiceContainer = app.state.container
        try:
            return await container.approve_action(action_id, decision)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    static_dir = Path(__file__).parent / "static"
    index_path = static_dir / "index.html"

    @app.get("/")
    async def root():
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        raise HTTPException(status_code=404, detail="Dashboard not found")

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "second_brain.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "development",
    )
