from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from test_postgres import activate, provision

from cricai.config import Settings
from cricai.main import create_app


def test_api_and_websocket_use_same_committed_state(database: Engine) -> None:
    service, auction_id, actors = provision(database)
    activate(database, auction_id)
    settings = Settings(allow_test_data=True)
    with TestClient(create_app(settings, database, timers=False)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.get(f"/v1/auctions/{auction_id}").status_code == 401
        assert client.post("/v1/dev/auctions", json={}).status_code == 401
        token = actors[0]["token"]
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())}
        payload = {
            "kind": "bid",
            "expected_version": 0,
            "player_id": "test-one",
            "amount": 2_000_000,
        }
        first = client.post(f"/v1/auctions/{auction_id}/commands", headers=headers, json=payload)
        assert first.status_code == 200
        retry = client.post(f"/v1/auctions/{auction_id}/commands", headers=headers, json=payload)
        assert retry.json() == first.json()
        with client.websocket_connect(f"/v1/auctions/{auction_id}/stream") as socket:
            socket.send_json({"token": token})
            snapshot = socket.receive_json()
            assert snapshot["state"]["current_bid"] == 2_000_000
            assert snapshot["state"]["version"] == 1
        history = client.get(f"/v1/auctions/{auction_id}/events", headers=headers).json()
        assert history["events"][0]["kind"] == "bid"
        assert service.snapshot(auction_id, token)["state"]["version"] == 1


def test_invalid_amount_and_capability_cannot_bid(database: Engine) -> None:
    _, auction_id, actors = provision(database)
    activate(database, auction_id)
    with TestClient(create_app(Settings(allow_test_data=True), database, timers=False)) as client:
        headers = {"Authorization": f"Bearer {actors[0]['token']}", "Idempotency-Key": str(uuid4())}
        payload = {"kind": "bid", "expected_version": 0, "player_id": "test-one", "amount": True}
        assert (
            client.post(
                f"/v1/auctions/{auction_id}/commands", headers=headers, json=payload
            ).status_code
            == 422
        )
        headers["Authorization"] = "Bearer wrong"
        payload["amount"] = 2_000_000
        assert (
            client.post(
                f"/v1/auctions/{auction_id}/commands", headers=headers, json=payload
            ).status_code
            == 401
        )
