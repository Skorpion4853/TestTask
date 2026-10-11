import pytest
import os
import httpx
from dotenv import load_dotenv
from database.DBCommand import Payment, SessionLocal, create_database, create_tariff
import uuid

from sqlalchemy import func, select


load_dotenv()

from api import app

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def client():
    await create_database()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 headers={"X-API-Key": API_KEY}) as client:
        yield client



@pytest.fixture
async def tariff(client):
    return await create_tariff("basic", 990000)



API_KEY = os.getenv("API_KEY")
WEBHOOK = os.getenv("WEBHOOK_SECRET")
pytestmark = pytest.mark.anyio


#------------------ test №1 Проверка суммы со скидкой и без --------------


@pytest.mark.parametrize(
    "promo_code, expected_discount, expected_amount",
    [
        (None, 0, 990000),  # без промокода
        ("KVITTO10", 99000, 891000),  # скидка 10%
        ("kvitto10", 99000, 891000),  # регистр не важен
    ],
)
async def test1(client, tariff, promo_code, expected_discount, expected_amount):
    body = {"tariff_id": tariff.id, "email": "user@example.com", "method": "card"}
    if promo_code:
        body["promo_code"] = promo_code

    response = await client.post("/payments", json=body)

    assert response.status_code == 201
    data = response.json()
    assert data["discount"] == expected_discount
    assert data["amount"] == expected_amount





#--------------- test №2 Проверка работы рассрочки ---------------------


@pytest.mark.parametrize(
    "installment_months, expected_total_price, expected_schedule",
    [
        (3, 990000, [330000, 330000, 330000]),  # 3 месяца
        (6, 990000, [165000, 165000, 165000, 165000, 165000, 165000]),  # 6 месяцев
        (12, 990000, [82500, 82500, 82500, 82500, 82500, 82500, 82500, 82500, 82500, 82500, 82500, 82500]),  # 12 месяцев
    ],
)
async def test2(client, tariff, installment_months, expected_total_price, expected_schedule):
    body = {"tariff_id": tariff.id, "email": "user@example.com", "method": "installment"}
    if installment_months:
        body["installment_months"] = installment_months

    response = await client.post("/payments", json=body)

    assert response.status_code == 201
    data = response.json()
    assert sum(data["schedule"]) == expected_total_price
    assert data["schedule"] == expected_schedule



#----------------- test №3 Повторный запрос ------------------------
async def count_payments() -> int:
    async with SessionLocal() as session:
        return await session.scalar(select(func.count()).select_from(Payment))


async def test3(client, tariff):
    # Уникальный ключ, чтобы тест не зависел от прошлых запусков (база общая)
    headers = {"Idempotency-Key": f"test-{uuid.uuid4()}"}
    body = {"tariff_id": tariff.id, "email": "user@example.com", "method": "card"}
    before = await count_payments()

    first = await client.post("/payments", json=body, headers=headers)
    second = await client.post("/payments", json=body, headers=headers)

    assert first.status_code == 201              # первый запрос создаёт платёж
    assert second.status_code == 200             # повтор возвращает уже существующий
    assert second.json() == first.json()         # тот же самый платёж
    assert await count_payments() == before + 1  # в базе ровно одна новая запись



#------------------ test №4 Запрещённый переход статуса --------------

async def send_webhook(client, payment_id: int, status: str):
    return await client.post(
        "/webhooks/bank",
        json={"payment_id": payment_id, "status": status},
        headers={"X-Signature": WEBHOOK},
    )


@pytest.mark.parametrize(
    "start_status, forbidden_status",
    [
        ("pending", "refunded"),   # нельзя вернуть деньги за неоплаченный платёж
        ("succeeded", "failed"),   # оплаченный платёж нельзя «провалить»
    ],
)
async def test4(client, tariff, start_status, forbidden_status):
    body = {"tariff_id": tariff.id, "email": "user@example.com", "method": "card"}
    payment_id = (await client.post("/payments", json=body)).json()["id"]
    if start_status != "pending":
        assert (await send_webhook(client, payment_id, start_status)).status_code == 200

    response = await send_webhook(client, payment_id, forbidden_status)

    assert response.status_code == 409
    # Статус в базе не изменился
    assert (await client.get(f"/payments/{payment_id}")).json()["status"] == start_status


#------------------ test №5 Запрос несуществующего платежа --------------

async def test5(client):
    response = await client.get("/payments/999999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"

