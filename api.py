import secrets
from fastapi import FastAPI, status, HTTPException, Header, Security, Depends
from pydantic import BaseModel, EmailStr
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from database.DBCommand import Payment, Tariff, get_tariffs, get_payment, get_payment_by_key, payment_to_dict, tariffs_to_list, SessionLocal, get_payment_by_id
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
if not API_KEY:
    raise RuntimeError("Не задана переменная окружения API_KEY")
if not WEBHOOK_SECRET:
    raise RuntimeError("Не задан WEBHOOK_SECRET")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
x_signature_header = APIKeyHeader(name="X-Signature", auto_error=False)

async def verify_api_key(api_key: str | None = Security(api_key_header)):
    if not api_key or not secrets.compare_digest(api_key.encode(), API_KEY.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

async def verify_signature(signature: str | None = Security(x_signature_header)):
    if not signature or not secrets.compare_digest(signature.encode(), WEBHOOK_SECRET.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook signature",
        )

app = FastAPI(dependencies=[Depends(verify_api_key)])

#--------- Pydantic models ---------

class PaymentCreate(BaseModel):
    tariff_id: int
    email: EmailStr
    method: str
    installment_months: int | None = None
    promo_code: str | None = None

class WebhookRequest(BaseModel):
    payment_id: int
    status: str


@app.get("/tariffs") #Запрос для возврата всех возможных тарифов
async def tariffs():
    try:
        result = await get_tariffs()
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database Error")
    else:
        if not result:
            raise HTTPException(status_code=404, detail="Tarrifs not found")
        else:
            return tariffs_to_list(result)


@app.post("/payments", status_code=status.HTTP_201_CREATED) #Запрос для добавление записи
async def create_payment(
        body: PaymentCreate,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    async with SessionLocal() as session:
        #Проверка нахождения ключа сессии в бд
        if idempotency_key:
            existing = await get_payment_by_key(session, idempotency_key)
            if existing:
                return JSONResponse(payment_to_dict(existing), status_code=status.HTTP_200_OK)

        #Проверка реально ли существует выбранный тариф
        tariff = await session.get(Tariff, body.tariff_id)
        if tariff is None:
            raise HTTPException(status_code=404, detail="Tariff not found")

        #Проверка существования метода
        if body.method not in ["installment", "card", "sbp"]:
            raise HTTPException(status_code=409, detail="Method not supported")

        if body.method == "installment" and body.installment_months is None:
            raise HTTPException(status_code=412, detail="Installment months required")

        #Проверка промокода, расчёт discount и amount (При условии что amount - стоимость)
        if body.promo_code:
            if body.promo_code.upper() in ["KVITTO10"]:
                if body.promo_code.upper() == "KVITTO10":
                    discount = round(tariff.price * 10 / 100)
            else:
                raise HTTPException(status_code=422, detail="Promo Code not found")
        else:
            discount = 0
        amount = tariff.price - discount


        #Расчёт рассрочки
        if body.installment_months and body.method == "installment":
            schedule = []
            first_month = amount - amount // body.installment_months * (body.installment_months - 1)
            schedule.append(first_month)
            for _ in range(body.installment_months-1):
                schedule.append(amount // body.installment_months)
        else:
            schedule = None

        payment = Payment(
            idempotency_key=idempotency_key,
            status = "pending",
            tariff_id = tariff.id,
            amount = amount,
            discount = discount,
            method = body.method,
            installment_months = body.installment_months,
            schedule = schedule,
            email = body.email,
        )
        session.add(payment)
        try:
            await session.commit()
        except IntegrityError:
            #Если два запроса пришли одновременно
            await session.rollback()
            existing = await get_payment_by_key(session, idempotency_key)
            return JSONResponse(payment_to_dict(existing), status_code=status.HTTP_200_OK)

        await session.refresh(payment)
        return payment_to_dict(payment)


@app.get("/payments/{payment_id}") #Запрос для возврата статуса оплаты сделал с idempotency_key для защиты данных
async def view_payment(payment_id: int):
    try:
        result = await get_payment(payment_id)
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database Error")
    else:
        if not result:
            raise HTTPException(status_code=404, detail="Payment not found")
        else:
            return payment_to_dict(result)


@app.post("/webhooks/bank", dependencies=[Depends(verify_signature)]) #Запрос на добавление статуса платежа
async def webhook(body: WebhookRequest):
    async with SessionLocal() as session:
        payment = await get_payment_by_id(session, body.payment_id)
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        if body.status not in ["succeeded", "failed", "refunded"]:
            raise HTTPException(status_code=409, detail="Status not supported")
        if payment.status == "pending" and body.status == "refunded":
            raise HTTPException(status_code=409, detail="invalid_transition")
        elif payment.status == "succeeded" and body.status != "refunded":
            raise HTTPException(status_code=409, detail="invalid_transition")

        payment.status = body.status
        await session.commit()
        raise HTTPException(status_code=200, detail="The status was successfully changed.")