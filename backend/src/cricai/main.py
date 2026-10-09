import asyncio
import contextlib
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from cricai.auction.domain import AuctionError, Command, Model, RuleConfig
from cricai.auction.service import AuctionService
from cricai.config import Settings
from cricai.db import DataSnapshot, make_engine
from cricai.players.ingestion import PlayerImport, publish

logger = logging.getLogger("cricai")
bearer = HTTPBearer(auto_error=False)


class CreateAuction(Model):
    snapshot_id: str = Field(min_length=64, max_length=64)
    franchises: list[str] = Field(min_length=2, max_length=10)
    rules: RuleConfig = Field(default_factory=RuleConfig)


def create_app(
    settings: Settings | None = None, engine: Engine | None = None, timers: bool = True
) -> FastAPI:
    configuration = settings or Settings()
    database = engine or make_engine(configuration.database_url)
    service = AuctionService(database, configuration.allow_test_data)
    timer_healthy = True

    async def run_timer() -> None:
        nonlocal timer_healthy
        while True:
            try:
                await asyncio.to_thread(service.advance)
                timer_healthy = True
            except SQLAlchemyError:
                timer_healthy = False
                logger.error("Database timer unavailable; retrying without changing auction state")
            await asyncio.sleep(0.25)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = None
        if timers:
            await asyncio.to_thread(service.advance, True)
            task = asyncio.create_task(run_timer())
        try:
            yield
        finally:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            if engine is None:
                database.dispose()

    application = FastAPI(title="cricAI", version="0.1.0", lifespan=lifespan)

    @application.exception_handler(AuctionError)
    async def auction_error(_: Request, error: AuctionError) -> JSONResponse:
        return JSONResponse(
            status_code=401 if error.code == "unauthorized" else 409, content={"error": error.code}
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, __: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": "database_unavailable"})

    def participant_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> str:
        if credentials is None:
            raise HTTPException(401, "Participant capability required")
        return credentials.credentials

    def developer(token: Annotated[str, Depends(participant_token)]) -> None:
        if len(configuration.dev_token) < 32 or not secrets.compare_digest(
            token, configuration.dev_token
        ):
            raise HTTPException(401, "Developer authorization required")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "product": "cricAI"}

    @application.get("/ready")
    def ready() -> dict[str, str]:
        with database.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(select(DataSnapshot.id).limit(1))
        if not timer_healthy:
            raise HTTPException(503, "Auction timer unavailable")
        return {"status": "ready"}

    @application.get("/v1/catalog")
    def catalog() -> dict[str, Any]:
        with Session(database) as session:
            snapshots = list(
                session.scalars(
                    select(DataSnapshot).order_by(DataSnapshot.created_at.desc()).limit(100)
                )
            )
            return {
                "snapshots": [
                    {"id": item.id, **item.manifest}
                    for item in snapshots
                    if configuration.allow_test_data or not item.manifest["test_data"]
                ],
                "mode": "local_foundation",
                "production_pool_available": any(
                    not item.manifest["test_data"] for item in snapshots
                ),
            }

    @application.post("/v1/dev/import", dependencies=[Depends(developer)], status_code=201)
    def import_players(payload: PlayerImport) -> dict[str, str]:
        with Session(database) as session, session.begin():
            snapshot_id = publish(session, payload, configuration.allow_test_data)
        return {"snapshot_id": snapshot_id}

    @application.post("/v1/dev/auctions", dependencies=[Depends(developer)], status_code=201)
    def create(payload: CreateAuction) -> dict[str, Any]:
        return service.create(payload.snapshot_id, payload.franchises, payload.rules)

    @application.get("/v1/auctions/{auction_id}")
    def snapshot(
        auction_id: UUID, token: Annotated[str, Depends(participant_token)]
    ) -> dict[str, Any]:
        return service.snapshot(str(auction_id), token)

    @application.get("/v1/auctions/{auction_id}/events")
    def events(
        auction_id: UUID,
        token: Annotated[str, Depends(participant_token)],
        after: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        return {"events": service.history(str(auction_id), token, after)}

    @application.post("/v1/auctions/{auction_id}/commands")
    def command(
        auction_id: UUID,
        payload: Command,
        token: Annotated[str, Depends(participant_token)],
        request_id: Annotated[UUID, Header(alias="Idempotency-Key")],
    ) -> dict[str, Any]:
        return service.command(str(auction_id), token, str(request_id), payload)

    @application.websocket("/v1/auctions/{auction_id}/stream")
    async def stream(socket: WebSocket, auction_id: UUID) -> None:
        await socket.accept()
        try:
            authentication = await asyncio.wait_for(socket.receive_json(), timeout=5)
            token = authentication.get("token", "")
            if not isinstance(token, str) or not 20 <= len(token) <= 200:
                await socket.close(code=1008)
                return
            while True:
                result = await asyncio.to_thread(service.snapshot, str(auction_id), token)
                await socket.send_json(result)
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            return
        except (AuctionError, TimeoutError, ValueError, AttributeError):
            await socket.close(code=1008)
        except SQLAlchemyError:
            await socket.close(code=1013)

    return application


app = create_app()
