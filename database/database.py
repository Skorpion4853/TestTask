import asyncio
from DBCommand import *

async def main():
    await create_database()
    # Пример использования: python -m database.crud
    tariffs = [["basic", 990000], ["standart", 1990000], ["premium", 2990000]]
    for tariff in tariffs:
        await create_tariff(tariff[0], tariff[1])

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
