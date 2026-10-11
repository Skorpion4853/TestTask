# API платежей на FastAPI

Сервис, через который онлайн-школа принимает оплату курса: список тарифов, создание платежа (с промокодом и рассрочкой), просмотр платежа и вебхук банка для смены статуса.

Стек: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + SQLite (aiosqlite), pytest + httpx.

## Структура

```
api.py                  # FastAPI-приложение: эндпоинты, проверки, расчёт суммы и графика
database/DBCommand.py   # модели Tariff и Payment, подключение к SQLite, функции работы с БД
database/database.py    # создаёт таблицы и заполняет тарифы
tests.py                # тесты pytest
responce.py             # ручная проверка API через httpx (сервер должен быть запущен)
requirements.txt        # зависимости
```

## Запуск

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Создайте в корне проекта файл `.env`:

```
API_KEY=любой_секретный_ключ
WEBHOOK_SECRET=любой_секрет_вебхука
```

Создайте базу и тарифы (один раз, повторный запуск добавит тарифы ещё раз):

```bash
python database/database.py
```

Запустите сервер:

```bash
uvicorn api:app --reload
```

API доступно на http://127.0.0.1:8000, интерактивная документация на http://127.0.0.1:8000/docs.

## Тесты

```bash
pytest tests.py
```

Тесты используют тот же `.env` и ту же базу `database/database.db`: каждый тест создаёт себе тариф и платежи, поэтому после запуска в базе останутся тестовые записи.

Что проверяется:

1. Сумма и скидка без промокода, с `KVITTO10` и с `kvitto10` (регистр не важен).
2. График рассрочки на 3, 6 и 12 месяцев: сумма графика равна сумме к оплате.
3. Повторный запрос с тем же `Idempotency-Key` возвращает тот же платёж с кодом 200, в базе появляется ровно одна запись.
4. Запрещённый переход статуса возвращает 409 и не меняет статус.
5. Запрос несуществующего платежа возвращает 404.

## Авторизация

Все запросы требуют заголовок `X-API-Key` со значением `API_KEY` из `.env`, иначе ответ 401.
Вебхук дополнительно требует заголовок `X-Signature` со значением `WEBHOOK_SECRET`, иначе 401.

## Бизнес-правила

- Все суммы в API и в базе в копейках, целым числом: 19 900 ₽ = `1990000`.
- Тарифы: basic 9 900 ₽, standart 19 900 ₽, premium 29 900 ₽.
- Промокод `KVITTO10` даёт −10% от цены тарифа, регистр не важен. Неизвестный промокод: 422.
- Способы оплаты: `card`, `sbp`, `installment`. Для рассрочки обязателен `installment_months`: 3, 6 или 12.
- График рассрочки: сумма делится на число месяцев, лишние копейки по одной уходят в первые платежи, сумма графика ровно равна сумме к оплате. Пример: 1990000 на 3 месяца = `[663334, 663333, 663333]`.
- Статусы: новый платёж `pending`. Разрешены только `pending → succeeded`, `pending → failed`, `succeeded → refunded`.

## Эндпоинты

| Запрос | Ответ |
|---|---|
| `GET /tariffs` | 200, список `[{id, title, price}]` |
| `POST /payments` | 201, платёж создан; 200, если платёж с таким `Idempotency-Key` уже есть; 404, если тарифа нет |
| `GET /payments/{id}` | 200, платёж; 404, если его нет |
| `POST /webhooks/bank` | 200 `{"result": "ok"}`; 404, если платежа нет; 409 `{"error": "invalid_transition"}` при запрещённом переходе |

Платёж в ответах: `id`, `status`, `tariff_id`, `amount`, `discount`, `method`, `installment_months`, `schedule` (список сумм в копейках или `null`), `email`, `created_at`.

## Примеры запросов

Список тарифов:

```bash
curl http://127.0.0.1:8000/tariffs -H "X-API-Key: $API_KEY"
```

```json
[{"id":1,"title":"basic","price":990000},{"id":2,"title":"standart","price":1990000},{"id":3,"title":"premium","price":2990000}]
```

Создать платёж в рассрочку на 3 месяца с промокодом:

```bash
curl -X POST http://127.0.0.1:8000/payments \
  -H "X-API-Key: $API_KEY" \
  -H "Idempotency-Key: order-1" \
  -H "Content-Type: application/json" \
  -d '{"tariff_id": 2, "email": "user@example.com", "method": "installment", "installment_months": 3, "promo_code": "kvitto10"}'
```

```json
{"id":1,"status":"pending","tariff_id":2,"amount":1791000,"discount":199000,"method":"installment","installment_months":3,"schedule":[597000,597000,597000],"email":"user@example.com","created_at":"2026-10-11T16:53:21.647345"}
```

Посмотреть платёж:

```bash
curl http://127.0.0.1:8000/payments/1 -H "X-API-Key: $API_KEY"
```

Вебхук банка (платёж оплачен):

```bash
curl -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "X-API-Key: $API_KEY" \
  -H "X-Signature: $WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"payment_id": 1, "status": "succeeded"}'
```

```json
{"result":"ok"}
```

Повторный вебхук с `"status": "failed"` для того же платежа вернёт `409 {"error":"invalid_transition"}`.
