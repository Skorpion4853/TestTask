import pytest
import os
from dotenv import load_dotenv

load_dotenv()  # читает .env и кладёт значения в переменные окружения

API_KEY = os.getenv("API_KEY")
WEBHOOK = os.getenv("WEBHOOK_SECRET")
pytestmark = pytest.mark.anyio


#------------------ test №1 Проверка суммы со скидкой и без --------------

async def test1()






def payment_body(tariff_id: int, **extra) -> dict:
    return {"tariff_id": tariff_id, "email": "user@example.com", "method": "card", **extra}


# ---------- GET /tariffs ----------

async def test_get_tariffs(client, tariff):
    response = await client.get("/tariffs")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["title"] == "Базовый"
    assert data[0]["price"] == 1000


# ---------- POST /payments ----------

async def test_create_payment(client, tariff):
    response = await client.post("/payments", json=payment_body(tariff.id))

    assert response.status_code == 201
    data = response.json()
    assert data["tariff_id"] == tariff.id
    assert data["amount"] == 1000


async def test_create_payment_same_idempotency_key(client, tariff):
    headers = {"Idempotency-Key": "key-123"}

    first = await client.post("/payments", json=payment_body(tariff.id), headers=headers)
    second = await client.post("/payments", json=payment_body(tariff.id), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


async def test_create_payment_different_idempotency_keys(client, tariff):
    first = await client.post("/payments", json=payment_body(tariff.id), headers={"Idempotency-Key": "a"})
    second = await client.post("/payments", json=payment_body(tariff.id), headers={"Idempotency-Key": "b"})

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


async def test_create_payment_unknown_tariff(client):
    response = await client.post("/payments", json=payment_body(999))

    assert response.status_code == 404


async def test_create_payment_without_email(client, tariff):
    body = payment_body(tariff.id)
    del body["email"]

    response = await client.post("/payments", json=body)

    assert response.status_code == 422


# ---------- GET /payments/{id} ----------

async def test_get_payment_status(client, tariff):
    created = (await client.post("/payments", json=payment_body(tariff.id))).json()

    response = await client.get(f"/payments/{created['id']}")

    assert response.status_code == 200
    assert response.json()["status"] == created["status"]


async def test_get_unknown_payment(client):
    response = await client.get("/payments/999")

    assert response.status_code == 404


# ---------- POST /webhooks/bank ----------

@pytest.mark.skip(reason="TODO: заполнить, когда будет готов формат вебхука")
async def test_bank_webhook(client, tariff):
    created = (await client.post("/payments", json=payment_body(tariff.id))).json()

    response = await client.post("/webhooks/bank", json={"payment_id": created["id"], "status": "paid"})

    assert response.status_code == 200
    assert (await client.get(f"/payments/{created['id']}")).json()["status"] == "paid"
