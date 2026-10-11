### какими инструментами и моделями пользовался: Claude

### 2–3 ключевых запроса к ассистенту — как ставил задачу и какой контекст давал: 
1) Создай database/database.py написать скрипт для создания базы SQLAlchemyданных с двумя таблицами:
- Первая таблица - Tarrifs:
id - int, primary key, autoincriment
title- str, notnull
price - int, notnull

- Вторая таблица - Payments:
id - int, primary key, autoincriment
status - nvarchar(9), notnull
tariff_id - int, foreigin key Tarrifs(id), notnull
amount - int, notnull
discount - int
method - nvarchar(10), notnull
installment_months - tinyint
schedule - list
email - str
created_at - DATETIME, notnull
2) Просмотри ТестовоеЗадание.pdf и посмотри на test.py всё ли я сделал?
3) Сделай так-же 4 и 5 тесты: запрещённый переход статуса возвращает 409 и не меняет статус запрос несуществующего платежа возвращает 404

### где модель ошиблась или предложила слабое решение и как ты это заметил. В целом, я почти всё что кидала ИИ разбирал и изменял под себя, не сказал бы что решение слабое, просто гордость не даёт не разобраться в коде, а когда разбираешься меняешь под себя

## Полный лог общения лежит в файле chat_log.md