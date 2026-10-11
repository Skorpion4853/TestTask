import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()  # читает .env и кладёт значения в переменные окружения

API_KEY = os.getenv("API_KEY")
WEBHOOK = os.getenv("WEBHOOK_SECRET")


async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        response = await client.get("http://127.0.0.1:8000/tariffs")
        print(response.status_code)

        response1 = await client.get("http://127.0.0.1:8000/tariffs", headers={"X-API-KEY": API_KEY})
        print(response1.status_code, response1.text)

        response2 = await client.post(
            "/payments",
            json={"tariff_id": 1,
                  "email": "MyEmail@gmail.com",
                  "method": "installment",
                  "installment_months": 3,
                  "promo_code": "KvIttO10"},
            headers={"idempotency_key": "abc222", "X-API-Key": API_KEY}
        )
        print(response2.status_code, response2.json())

        response3 = await client.get("http://127.0.0.1:8000/payments/2", headers={"X-API-KEY": API_KEY})
        print(response3.status_code, response3.text)

        response4 = await client.post("/webhooks/bank",
                                      json={"payment_id": 5,
                                            "status": "succeeded"
                                      },
                                      headers={"X-API-KEY": API_KEY,
                                               "X-Signature": WEBHOOK})
        print(response4.status_code, response4.json())

        response5 = await client.post("/webhooks/bank",
                                      json={"payment_id": 5,
                                            "status": "succees"
                                            },
                                      headers={"X-API-KEY": API_KEY,
                                               "X-Signature": WEBHOOK})
        print(response5.status_code, response5.json())

        response6 = await client.post("/webhooks/bank",
                                      json={"payment_id": 5,
                                            "status": "failed"
                                            },
                                      headers={"X-API-KEY": API_KEY,
                                               "X-Signature": "heheheh"})
        print(response6.status_code, response6.json())
asyncio.run(main())